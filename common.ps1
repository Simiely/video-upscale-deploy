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

function Assert-HfHub {
  Assert-ComfyReady
  & $COMFY_PY -c "import huggingface_hub" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Note '虚拟环境里缺少 huggingface_hub，正在安装'
    & $COMFY_PY -m pip install -U huggingface_hub | Out-Null
  }
}

function Invoke-HfDownload {
  <#
    作用：用 huggingface_hub 的 snapshot_download 把模型仓库拉到指定目录，支持断点续传。
          Include 传文件名通配（逗号分隔，例如 "*.safetensors,*.ckpt"），默认全部文件。
  #>
  param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$LocalDir,
    [string]$Include = '*'
  )
  Assert-HfHub
  New-Item -ItemType Directory -Path $LocalDir -Force | Out-Null
  $env:HF_ENDPOINT = $HF_ENDPOINT
  $env:HF_HUB_DISABLE_TELEMETRY = '1'
  Write-Detail "仓库 $Repo  ->  $LocalDir"
  Write-Detail "下载源：$HF_ENDPOINT"

  $code = @'
import sys
from huggingface_hub import snapshot_download
repo, local, inc = sys.argv[1], sys.argv[2], sys.argv[3]
pats = None if inc == "*" else [p.strip() for p in inc.split(",") if p.strip()]
p = snapshot_download(repo_id=repo, local_dir=local, allow_patterns=pats, max_workers=4)
print("DOWNLOADED_TO", p)
'@
  & $COMFY_PY -c $code $Repo $LocalDir $Include
  if ($LASTEXITCODE -ne 0) { throw "从 $Repo 下载模型失败（源：$HF_ENDPOINT）" }
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