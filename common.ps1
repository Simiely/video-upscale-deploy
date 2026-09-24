<#
  common.ps1 —— 三套方案共用的配置与工具函数
  用法：在其它脚本中通过  . "$PSScriptRoot\..\common.ps1"  引入
#>

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

# ================= 可按需修改的路径 =================
# 程序与模型：体积不大但读取频繁 -> 建议放 SSD
$Global:UPSCALE_ROOT = 'C:\AI'
# 视频素材与输出：体积大、顺序读写即可 -> 建议放机械盘
$Global:UPSCALE_IO   = 'E:\VideoUpscale'
# ====================================================

# HuggingFace 下载端点。国内直连 huggingface.co 基本不通，默认走 hf-mirror.com 镜像。
# 想换回官方源：先设置环境变量 HF_ENDPOINT=https://huggingface.co 再运行脚本。
$Global:HF_ENDPOINT = if ($env:HF_ENDPOINT) { $env:HF_ENDPOINT } else { 'https://hf-mirror.com' }
# ComfyUI 服务地址（方案二走 HTTP API 批量放大时用）
$Global:COMFY_URL = 'http://127.0.0.1:8188'

# 完整版 ffmpeg 的候选路径（支持通配符）。
# PATH 上的 ffmpeg 不一定是完整版：本机实测 TRAE 自带的
# `...\TRAE SOLO CN\resources\app\bin\ffmpeg.exe` 是 `--disable-everything` 的精简构建，
# 连 rawvideo 输入格式都没有，SeedVR2 走 ffmpeg 编码后端会直接崩
# （`Unknown input format: 'rawvideo'` → BrokenPipeError），也没有 libx265。
# 所以脚本会按「FFMPEG_PATH 环境变量 → PATH → 下面这些候选」的顺序找能用的那个。
# 换机器请改这里，或用环境变量 FFMPEG_PATH 直接指定。
$Global:FFMPEG_CANDIDATES = @(
  (Join-Path $UPSCALE_ROOT 'ffmpeg\bin\ffmpeg.exe'),
  (Join-Path $env:APPDATA 'TRAE SOLO CN\ModularData\ai-agent\vm\tools\app\ffmpeg\ffmpeg.exe'),
  (Join-Path $env:USERPROFILE '.workbuddy\binaries\ffmpeg\*\bin\ffmpeg.exe')
)

$Global:COMFY_DIR   = Join-Path $UPSCALE_ROOT 'ComfyUI'
$Global:COMFY_VENV  = Join-Path $COMFY_DIR '.venv'
$Global:COMFY_PY    = Join-Path $COMFY_VENV 'Scripts\python.exe'
$Global:COMFY_NODES = Join-Path $COMFY_DIR 'custom_nodes'
$Global:COMFY_MODEL = Join-Path $COMFY_DIR 'models'
$Global:VIDEO2X_DIR = Join-Path $UPSCALE_ROOT 'Video2X'
$Global:INPUT_DIR   = Join-Path $UPSCALE_IO 'input'
$Global:OUTPUT_DIR  = Join-Path $UPSCALE_IO 'output'

function Write-Step   { param([int]$Index,[int]$Total,[string]$Text)
  Write-Host ""
  Write-Host ("[{0}/{1}] {2}" -f $Index, $Total, $Text) -ForegroundColor Cyan }
function Write-Done   { param([string]$Text) Write-Host "  [完成] $Text" -ForegroundColor Green }
function Write-Note   { param([string]$Text) Write-Host "  [注意] $Text" -ForegroundColor Yellow }
function Write-Detail { param([string]$Text) Write-Host "         $Text" -ForegroundColor DarkGray }

function Test-Cmd { param([string]$Name) return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Test-FfmpegCapable {
  <#
    作用：判断这个 ffmpeg 能不能干我们的活。
          默认要能读 rawvideo（SeedVR2 的 ffmpeg 编码后端靠管道喂原始帧，
          没有这个 demuxer 就会 `Unknown input format: 'rawvideo'`）；
          加 -NeedX265 时还要求带 libx265（--10bit 输出用）。
  #>
  param([Parameter(Mandatory = $true)][string]$Exe, [switch]$NeedX265)
  if (-not (Test-Path $Exe)) { return $false }
  $dem = & $Exe -hide_banner -demuxers 2>$null
  if (-not ($dem | Select-String -Pattern '\brawvideo\b' -Quiet)) { return $false }
  if ($NeedX265) {
    $enc = & $Exe -hide_banner -encoders 2>$null
    if (-not ($enc | Select-String -Pattern 'libx265' -Quiet)) { return $false }
  }
  return $true
}

function Resolve-FfmpegTool {
  <#
    作用：找一个「能干活的」ffmpeg，返回绝对路径；找不到返回 $null。
    顺序：环境变量 FFMPEG_PATH > PATH 上的 ffmpeg（能力探测通过才用）> $FFMPEG_CANDIDATES。
    结果会缓存，避免每次调用都跑一遍探测。
  #>
  param([switch]$NeedX265)
  $key = if ($NeedX265) { 'x265' } else { 'basic' }
  if ($Global:FFMPEG_RESOLVED -and $Global:FFMPEG_RESOLVED.ContainsKey($key)) {
    return $Global:FFMPEG_RESOLVED[$key]
  }
  if (-not $Global:FFMPEG_RESOLVED) { $Global:FFMPEG_RESOLVED = @{} }

  $hit = $null
  if ($env:FFMPEG_PATH) {
    if (Test-FfmpegCapable -Exe $env:FFMPEG_PATH -NeedX265:$NeedX265) {
      $hit = $env:FFMPEG_PATH
    } else {
      Write-Note "FFMPEG_PATH 指向的 ffmpeg 不满足要求，继续往下找：$env:FFMPEG_PATH"
    }
  }
  if (-not $hit) {
    $onPath = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
    if ($onPath -and (Test-FfmpegCapable -Exe $onPath -NeedX265:$NeedX265)) { $hit = $onPath }
  }
  if (-not $hit) {
    foreach ($pat in $FFMPEG_CANDIDATES) {
      foreach ($c in @(Get-ChildItem -Path $pat -File -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)) {
        if (Test-FfmpegCapable -Exe $c.FullName -NeedX265:$NeedX265) { $hit = $c.FullName; break }
      }
      if ($hit) { break }
    }
  }
  $Global:FFMPEG_RESOLVED[$key] = $hit
  return $hit
}

function Enable-FfmpegOnPath {
  <#
    作用：把「能用的」ffmpeg 所在目录插到当前进程 PATH 的最前面，返回该 exe 的绝对路径。
          找不到可用的就返回 $null。

    为什么必须动 PATH：
      SeedVR2 的 inference_cli.py 里写死了裸命令 —— 校验用 `shutil.which("ffmpeg")`，
      编码用 `subprocess.Popen(['ffmpeg', ...])`。所以就算我们在 PowerShell 里探测出
      完整版路径也没用，子进程照样按 PATH 顺序拿到第一个 ffmpeg。
      本机实测 PATH 第一个是 TRAE 自带的精简构建（--disable-everything，无 rawvideo、
      无 libx265），CLI 走到 ffmpeg 后端会 `Unknown input format: 'rawvideo'` 直接崩。
      把完整版目录提到最前面，子进程才会用对的那个。

    注意：只影响当前 PowerShell 进程及其子进程，不改系统环境变量。
  #>
  param([switch]$NeedX265)
  $exe = Resolve-FfmpegTool -NeedX265:$NeedX265
  if (-not $exe) { return $null }
  $dir = Split-Path $exe -Parent
  $rest = @($env:PATH -split ';' | Where-Object { $_ -and ($_.TrimEnd('\') -ne $dir.TrimEnd('\')) })
  $env:PATH = $dir + ';' + ($rest -join ';')
  return $exe
}

function New-ProjectDirs {
  foreach ($d in @($UPSCALE_ROOT, $UPSCALE_IO, $INPUT_DIR, $OUTPUT_DIR)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
  }
}

function Show-Gpu {
  if (-not (Test-Cmd 'nvidia-smi')) { Write-Note '未找到 nvidia-smi，跳过显卡检查'; return }
  Write-Host "  当前显卡：" -ForegroundColor Gray
  $rows = & nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader 2>$null
  foreach ($r in $rows) { Write-Host "    $r" -ForegroundColor Gray }
}

function Get-BasePython {
  # 找一个 3.12 / 3.13 解释器，用作 ComfyUI 虚拟环境的基础
  $uvRoot = Join-Path $env:APPDATA 'uv\python'
  if (Test-Path $uvRoot) {
    foreach ($pat in @('cpython-3.13*', 'cpython-3.12*')) {
      $hit = Get-ChildItem $uvRoot -Directory -Filter $pat -ErrorAction SilentlyContinue |
             Sort-Object Name -Descending | Select-Object -First 1
      if ($hit) {
        $exe = Join-Path $hit.FullName 'python.exe'
        if (Test-Path $exe) { return $exe }
      }
    }
  }
  foreach ($p in @(
      (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
      (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
      'C:\Python313\python.exe',
      'C:\Python312\python.exe')) {
    if (Test-Path $p) { return $p }
  }
  if (Test-Cmd 'py') {
    foreach ($v in @('-3.13', '-3.12')) {
      $exe = & py $v -c "import sys;print(sys.executable)" 2>$null
      if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
  }
  return $null
}

function Assert-ComfyReady {
  if (-not (Test-Path $COMFY_PY)) {
    throw "未找到 ComfyUI 虚拟环境：$COMFY_PY`n请先运行 00-ComfyUI底座\安装ComfyUI.ps1"
  }
}

function Get-VideoFiles {
  param([string]$Path)
  if (Test-Path -Path $Path -PathType Leaf) { return @(Get-Item $Path) }
  if (Test-Path -Path $Path -PathType Container) {
    return @(Get-ChildItem $Path -File |
             Where-Object { $_.Extension -match '^\.(mp4|mkv|mov|avi|webm|flv|ts|m4v|wmv)$' })
  }
  throw "输入路径不存在：$Path"
}

# ================= ComfyUI 自定义节点安装 =================

function Install-ComfyNode {
  <#
    作用：把某个 ComfyUI 自定义节点仓库克隆到 custom_nodes，并装好它的 Python 依赖。
    参数 RepoUrl 形如 https://github.com/作者/仓库.git；DirName 是落在 custom_nodes 下的目录名。
    已存在则只补依赖，不重复克隆（方便升级后重跑）。
  #>
  param(
    [Parameter(Mandatory = $true)][string]$RepoUrl,
    [Parameter(Mandatory = $true)][string]$DirName
  )
  Assert-ComfyReady
  $target = Join-Path $COMFY_NODES $DirName
  if (Test-Path $target) {
    Write-Done "$DirName 已存在，跳过克隆"
  } else {
    & git clone $RepoUrl $target
    if ($LASTEXITCODE -ne 0) { throw "克隆 $RepoUrl 失败，请检查网络（必要时给 git 配代理）" }
    Write-Done "已克隆 $DirName"
  }
  $req = Join-Path $target 'requirements.txt'
  if (Test-Path $req) {
    & $COMFY_PY -m pip install -r $req
    if ($LASTEXITCODE -ne 0) { throw "$DirName 依赖安装失败" }
    Write-Done "$DirName 依赖已安装"
  } else {
    Write-Note "$DirName 没有 requirements.txt，跳过依赖安装"
  }
}

# ================= HuggingFace 模型下载 =================

function Get-HfProxy {
  <#
    作用：决定下载模型时用哪个 HTTP 代理。
    背景：实测 hf-mirror.com 直连只有 0.04 MB/s（同一时刻走本机代理 3.03 MB/s，差 75 倍），
          且直连时 huggingface_hub 会因 10 秒读超时抛 `ReadError ... _ssl.c:2580`，
          表现为「.incomplete 文件一直是 0 字节」的假死。
    优先级：环境变量 HF_PROXY > 自动探测本机常见代理端口 > 直连。
          设 HF_PROXY=none 可强制直连。
  #>
  if ($env:HF_PROXY) {
    if ($env:HF_PROXY -in @('none', 'off', 'direct')) { return '' }
    return $env:HF_PROXY
  }
  foreach ($port in @(7890, 7891, 10809, 1080)) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
      $iar = $client.BeginConnect('127.0.0.1', $port, $null, $null)
      if ($iar.AsyncWaitHandle.WaitOne(300) -and $client.Connected) { return "http://127.0.0.1:$port" }
    } catch {
    } finally { $client.Close() }
  }
  return ''
}

function Get-RemoteSize {
  <#
    作用：问出远端文件的真实字节数，用于下载完整性校验。
    先 HEAD（快），但 hf-mirror 对非 LFS 小文件偶尔回 `Content-Length: 0`，
    拿不到可信值时再用 1 字节 Range GET，从 `Content-Range: bytes 0-0/总长` 里读总长。
  #>
  param([string]$Url, [string[]]$ProxyArgs)
  $head = & curl.exe -sIL @ProxyArgs --max-time 60 $Url 2>$null
  $cl = ($head | Select-String -Pattern '^content-length:' | Select-Object -Last 1) -replace '.*?:\s*', ''
  if ($cl -match '^\d+$' -and [long]$cl -gt 0) { return [long]$cl }

  $dump = & curl.exe -sL @ProxyArgs --max-time 60 -r 0-0 -D - -o NUL $Url 2>$null
  $cr = ($dump | Select-String -Pattern '^content-range:' | Select-Object -Last 1) -replace '.*?:\s*', ''
  if ($cr -match '/(\d+)$') { return [long]$Matches[1] }
  return 0
}

function Invoke-HfDownload {
  <#
    作用：把 HuggingFace 仓库的文件拉到指定目录，断点续传 + 失败自动重试。
          Include 传逗号分隔的文件名（例如 "a.safetensors,b.safetensors"），
          默认 '*' 表示整仓全部文件（走 /api/models 拿清单）。
          已存在且大小正确的文件会跳过，所以重跑不会重下。

    为什么不用 huggingface_hub 的 snapshot_download：
      2026-09-24 实测，hf-mirror.com 直连只有 0.04 MB/s，10 秒读超时会抛
      `ReadError ... _ssl.c:2580`，表现为 .incomplete 文件长期停在 0 字节的假死
      （换成走本机代理也一样卡死，与网络无关，是该库自身的问题）。
      同一时刻 curl.exe 走本机代理稳定 3.07 MB/s（3 分钟 553 MB 不掉速），
      且 curl 自带 `-C -` 续传。所以下载统一走 curl.exe。

    注意：PowerShell 5.1 里 `curl` 是 Invoke-WebRequest 的别名，必须写全 `curl.exe`。
  #>
  param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$LocalDir,
    [string]$Include = '*'
  )
  if (-not (Test-Cmd 'curl.exe')) { throw '找不到 curl.exe（Windows 10 1803+ 自带），无法下载模型' }
  New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null

  $proxy = Get-HfProxy
  $proxyArgs = @()
  if ($proxy) { $proxyArgs = @('--proxy', $proxy) }
  Write-Detail "仓库 $Repo  ->  $LocalDir"
  Write-Detail "下载源：$HF_ENDPOINT"
  Write-Detail "代理：$(if ($proxy) { $proxy } else { '直连（如需代理请设 HF_PROXY=http://127.0.0.1:端口）' })"

  # ---------- 1. 确定要下哪些文件 ----------
  $files = @()
  if ($Include -eq '*') {
    $api = "$HF_ENDPOINT/api/models/$Repo"
    $raw = & curl.exe -sL @proxyArgs --max-time 60 $api 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $raw) { throw "拉取 $Repo 的文件清单失败（$api）" }
    $files = @(($raw | ConvertFrom-Json).siblings | ForEach-Object { $_.rfilename } |
               Where-Object { $_ -and $_ -ne '.gitattributes' })
  } else {
    $files = @($Include -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
  }
  if ($files.Count -eq 0) { throw "仓库 $Repo 没解析出任何待下载文件（Include=$Include）" }

  # ---------- 2. 逐个文件下载 ----------
  foreach ($f in $files) {
    $url = "$HF_ENDPOINT/$Repo/resolve/main/$f"
    $target = Join-Path $LocalDir $f
    $parent = Split-Path $target -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }

    $expect = Get-RemoteSize -Url $url -ProxyArgs $proxyArgs
    $have = if (Test-Path $target) { (Get-Item $target).Length } else { 0 }

    if ($expect -gt 0 -and $have -eq $expect) {
      Write-Detail "已完整，跳过：$f（$([math]::Round($expect / 1MB, 1)) MB）"
      continue
    }
    Write-Detail "开始下载：$f（约 $([math]::Round($expect / 1MB, 1)) MB）"

    # 单文件最多重试 5 轮，每轮 curl 自己还会重试 5 次；续传从已有字节接着写
    $ok = $false
    for ($i = 1; $i -le 5; $i++) {
      $curlArgs = @('-L', '--fail', '--progress-bar', '-C', '-', '-o', $target,
                    '--retry', '5', '--retry-delay', '3', '--retry-all-errors',
                    '--max-time', '7200') + $proxyArgs + @($url)
      $sw = [Diagnostics.Stopwatch]::StartNew()
      & curl.exe @curlArgs
      $code = $LASTEXITCODE
      $sw.Stop()

      $got = if (Test-Path $target) { (Get-Item $target).Length } else { 0 }
      if ($expect -gt 0 -and $got -eq $expect) {
        $ok = $true
        Write-Done ("{0} 下载完成，{1} MB，用时 {2:hh\:mm\:ss}" -f $f, [math]::Round($got / 1MB, 1), $sw.Elapsed)
        break
      }
      if ($expect -eq 0 -and $code -eq 0) {
        $ok = $true
        Write-Done "$f 下载完成（未取到远端大小，无法校验，$([math]::Round($got / 1MB, 1)) MB）"
        break
      }
      Write-Note ("「{0}」中断（已下 {1} MB，curl 退出码 {2}），第 {3}/5 轮重试" -f `
        $f, [math]::Round($got / 1MB, 1), $code, $i)
      Start-Sleep -Seconds 3
    }
    if (-not $ok) {
      throw "下载 $Repo/$f 失败（源：$HF_ENDPOINT，代理：$(if ($proxy) { $proxy } else { '直连' })）"
    }
  }
}

function Assert-ModelFiles {
  <#
    作用：校验模型目录里该有的关键文件都在。缺文件时直接报错，
          避免等到 ComfyUI 里跑一半才发现模型不全。
  #>
  param(
    [Parameter(Mandatory = $true)][string]$Dir,
    [Parameter(Mandatory = $true)][string[]]$Files
  )
  $missing = @()
  foreach ($f in $Files) {
    if (-not (Test-Path (Join-Path $Dir $f))) { $missing += $f }
  }
  if ($missing.Count -gt 0) {
    throw "模型目录 $Dir 缺少文件：`n  - " + ($missing -join "`n  - ")
  }
  $size = [math]::Round(((Get-ChildItem $Dir -File | Measure-Object Length -Sum).Sum / 1GB), 2)
  Write-Done "模型校验通过（$($Files.Count) 个关键文件，合计 $size GB）"
}

# ================= 音轨回接（SeedVR2 专用） =================

function Get-FFmpegExe {
  <#
    作用：拿一个能用的 ffmpeg 绝对路径。
          优先完整版（Resolve-FfmpegTool）；音轨回接只需要流拷贝，
          所以完整版找不到时退回 PATH 上的 ffmpeg——精简版也能干这活。
  #>
  $full = Resolve-FfmpegTool
  if ($full) { return $full }
  return (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
}

function Get-FfprobeExe {
  <# 作用：拿 ffprobe 的绝对路径，优先用完整版 ffmpeg 的同目录兄弟。 #>
  $full = Resolve-FfmpegTool
  if ($full) {
    $sibling = Join-Path (Split-Path $full -Parent) 'ffprobe.exe'
    if (Test-Path $sibling) { return $sibling }
  }
  return (Get-Command ffprobe -ErrorAction SilentlyContinue).Source
}

function Test-HasAudio {
  <# 作用：判断视频里有没有音轨。ffprobe 列出音频流就是有。#>
  param([Parameter(Mandatory = $true)][string]$Path)
  $probe = Get-FfprobeExe
  if (-not $probe) { return $false }
  $s = & $probe -v error -select_streams a -show_entries stream=index -of csv=p=0 $Path 2>$null
  return [bool]($s | Where-Object { $_ -match '^\d+' })
}

function Restore-AudioTrack {
  <#
    作用：把源视频的音轨原样搬到放大后的输出上（视频流 -c:v copy，不重编码）。
    背景：SeedVR2 的 inference_cli.py 只处理画面，没有任何音频相关参数，
          实测 720p 带 AAC 的素材放大后音轨整条丢失，所以必须自己用 ffmpeg 补回来。
    返回：$true 表示成功接上，$false 表示源没音轨或工具缺失（都不是错误）。
  #>
  param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Target
  )
  $exe = Get-FFmpegExe
  if (-not $exe) { Write-Note "没找到 ffmpeg，跳过音轨回接：$(Split-Path $Target -Leaf)"; return $false }
  if (-not (Test-HasAudio -Path $Source)) { return $false }

  $tmp = "$Target.audio.mp4"
  & $exe -y -loglevel error -i $Target -i $Source -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy $tmp 2>$null
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $tmp)) {
    Write-Note "音轨回接失败：$(Split-Path $Target -Leaf)"
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    return $false
  }
  Move-Item -Path $tmp -Destination $Target -Force
  Write-Detail "已回接音轨：$(Split-Path $Target -Leaf)"
  return $true
}

# ================= ComfyUI HTTP API（方案二批量放大用） =================

function Test-ComfyApi {
  <# 作用：探测 ComfyUI 服务是否已经在跑。跑着才走 API，否则只能提示用户先启动。 #>
  param([string]$Url = $COMFY_URL)
  try {
    Invoke-RestMethod -Uri "$Url/system_stats" -TimeoutSec 5 -UseBasicParsing | Out-Null
    return $true
  } catch { return $false }
}

function Wait-ComfyApi {
  param([string]$Url = $COMFY_URL, [int]$TimeoutSec = 300)
  $sw = [Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    if (Test-ComfyApi -Url $Url) { return $true }
    Start-Sleep -Seconds 3
  }
  return $false
}

function Invoke-ComfyPrompt {
  <#
    作用：把一个 API 格式的工作流提交给 ComfyUI 执行，并等它跑完。
          API 格式 = { "节点ID": { "class_type": "节点名", "inputs": {...} } }
          比在网页上点按钮更适合批量：可以脚本里循环几百个视频。
    返回：该次执行的 prompt_id
  #>
  param(
    [Parameter(Mandatory = $true)][hashtable]$Prompt,
    [string]$Url = $COMFY_URL,
    [int]$TimeoutSec = 7200
  )
  $payload = @{ prompt = $Prompt; client_id = [guid]::NewGuid().ToString() } | ConvertTo-Json -Depth 30 -Compress
  $resp = Invoke-RestMethod -Uri "$Url/prompt" -Method Post -Body $payload `
                            -ContentType 'application/json' -TimeoutSec 60
  if ($resp.node_errors -and $resp.node_errors.PSObject.Properties.Count -gt 0) {
    throw ("工作流被拒绝，节点报错：" + ($resp.node_errors | ConvertTo-Json -Depth 10 -Compress))
  }
  $pid_ = $resp.prompt_id
  if (-not $pid_) { throw "提交失败，服务端未返回 prompt_id" }

  $sw = [Diagnostics.Stopwatch]::StartNew()
  while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Seconds 3
    $hist = Invoke-RestMethod -Uri "$Url/history/$pid_" -TimeoutSec 30
    $entry = $hist.$pid_
    if ($entry) {
      $status = $entry.status.status_str
      if ($status -eq 'error') {
        $msg = ($entry.status.messages | ConvertTo-Json -Depth 10 -Compress)
        throw "ComfyUI 执行出错：$msg"
      }
      if ($status -eq 'success') { return $pid_ }
    }
    Write-Host "." -NoNewline -ForegroundColor DarkGray
  }
  throw "等待超时（$TimeoutSec 秒），任务可能还在跑，可到网页界面查看队列"
}