<#
  02-FlashVSR\批量放大.ps1
  作用：不开网页、纯命令行批量跑 FlashVSR 超分。
        原理：ComfyUI 本身是个 HTTP 服务，脚本把「工作流」以 API 格式 POST 给
              http://127.0.0.1:8188/prompt，等它跑完再把结果文件搬走。
              这样就能像方案一那样丢一个文件夹进去，出来一批成品。

  示例：
    # 4 倍放大整个输入目录（4090 建议这么跑）
    .\批量放大.ps1 -InputPath "E:\VideoUpscale\input" -Scale 4

    # 12G 显存（4070S）：长视频用 tiny-long，省显存
    .\批量放大.ps1 -InputPath "a.mp4" -Mode tiny-long -Scale 4

    # 追求画质：full 模式（更吃显存，适合 4090）
    .\批量放大.ps1 -InputPath "a.mp4" -Mode full -Scale 4

    # ComfyUI 还没开，让脚本自己拉起来
    .\批量放大.ps1 -InputPath "E:\VideoUpscale\input" -AutoStart
#>

param(
  [Parameter(Mandatory = $true)][string]$InputPath,
  [ValidateSet(2, 3, 4)][int]$Scale = 4,
  [ValidateSet('tiny', 'tiny-long', 'full')][string]$Mode = 'tiny',
  [ValidateSet('FlashVSR-v1.1', 'FlashVSR')][string]$Model = 'FlashVSR-v1.1',
  [switch]$NoTiledDit,          # 显存够大可以关掉，换速度
  [switch]$NoTiledVae,
  [switch]$UnloadDit,           # 解码前先卸下 DiT，压低显存峰值
  [int]$Seed = 0,
  [int]$Crf = 17,               # 只对 CPU 编码器(h264/h265-mp4)有效
  [int]$Bitrate = 10,           # 只对 nvenc 格式有效，单位 Mbps
  [ValidateSet('video/h264-mp4', 'video/h265-mp4', 'video/nvenc_h264-mp4', 'video/nvenc_hevc-mp4')]
  [string]$Format = 'video/h264-mp4',
  [string]$OutDir = '',
  [string]$Url = '',
  [int]$TimeoutSec = 14400,
  [switch]$AutoStart,           # 服务没在跑时自动启动 ComfyUI
  [switch]$Overwrite
)

. "$PSScriptRoot\..\common.ps1"

if ($Url) { $COMFY_URL = $Url }

# ---------- 1. 准备 ----------
$nodeDir = Join-Path $COMFY_NODES 'ComfyUI-FlashVSR_Ultra_Fast'
if (-not (Test-Path $nodeDir)) { throw "未安装 FlashVSR 节点，请先运行 安装FlashVSR.ps1" }
if (-not (Test-Path (Join-Path $COMFY_MODEL "$Model"))) {
  throw "未找到模型目录 $COMFY_MODEL\$Model，请先运行 安装FlashVSR.ps1"
}

if (-not $OutDir) { $OutDir = $OUTPUT_DIR }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$comfyOutDir = Join-Path $COMFY_DIR 'output\upscaled'
if (-not (Test-Path $comfyOutDir)) { New-Item -ItemType Directory -Path $comfyOutDir -Force | Out-Null }

# ---------- 2. 确保 ComfyUI 在跑 ----------
Write-Step 1 3 "检查 ComfyUI 服务（$COMFY_URL）"
if (Test-ComfyApi) {
  Write-Done "服务在线"
} elseif ($AutoStart) {
  Write-Detail "服务未启动，正在后台拉起 ComfyUI ..."
  $log = Join-Path $COMFY_DIR 'comfy-api.log'
  Start-Process -FilePath $COMFY_PY `
                -ArgumentList @((Join-Path $COMFY_DIR 'main.py'), '--port', '8188', '--listen', '127.0.0.1') `
                -WorkingDirectory $COMFY_DIR -WindowStyle Hidden `
                -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  if (-not (Wait-ComfyApi -TimeoutSec 300)) { throw "ComfyUI 启动超时，看看 $log.err" }
  Write-Done "服务已就绪"
} else {
  throw @"
ComfyUI 没在运行，脚本没法提交任务。二选一：
  1) 另开一个窗口先启动：powershell -File "$PSScriptRoot\..\00-ComfyUI底座\启动ComfyUI.ps1"
  2) 给本脚本加 -AutoStart 参数，让它自己拉起服务
"@
}

# ---------- 3. 逐个提交 ----------
$files = Get-VideoFiles -Path $InputPath
if ($files.Count -eq 0) { throw "输入路径下没有找到视频文件：$InputPath" }

$ok = 0; $fail = 0; $skip = 0
$total = $files.Count
$i = 0

foreach ($f in $files) {
  $i++
  $base = [IO.Path]::GetFileNameWithoutExtension($f.Name)
  $outFile = Join-Path $OutDir "${base}_${Scale}x_flashvsr.mp4"

  Write-Step $i $total "$($f.Name)  ->  $(Split-Path $outFile -Leaf)"

  if ((Test-Path $outFile) -and -not $Overwrite) {
    Write-Note '输出已存在，跳过（加 -Overwrite 可覆盖）'
    $skip++; continue
  }

  # 记下提交前已有的同名产物，跑完用差集精确取出本次结果，避免拿错旧文件
  $before = @(Get-ChildItem $comfyOutDir -File -Filter "$base`_*" -ErrorAction SilentlyContinue |
              ForEach-Object { $_.FullName })

  # API 格式工作流：节点ID -> 节点类型 + 输入
  #   1 VHS_LoadVideoPath  读视频成帧序列（0=IMAGE, 2=audio, 3=video_info）
  #   2 VHS_VideoInfo      从视频信息里取原始帧率（0=source_fps）
  #   3 FlashVSRNode       真正的超分
  #   4 VHS_VideoCombine   帧序列写回 mp4，并保留原音轨
  $prompt = @{
    '1' = @{
      class_type = 'VHS_LoadVideoPath'
      inputs = @{
        video = $f.FullName; force_rate = 0; custom_width = 0; custom_height = 0
        frame_load_cap = 0; skip_first_frames = 0; select_every_nth = 1
      }
    }
    '2' = @{
      class_type = 'VHS_VideoInfo'
      inputs = @{ video_info = @('1', 3) }
    }
    '3' = @{
      class_type = 'FlashVSRNode'
      inputs = @{
        frames = @('1', 0); model = $Model; mode = $Mode; scale = $Scale
        tiled_vae = (-not $NoTiledVae); tiled_dit = (-not $NoTiledDit)
        unload_dit = [bool]$UnloadDit; seed = $Seed
      }
    }
    '4' = @{
      class_type = 'VHS_VideoCombine'
      inputs = @{
        images = @('3', 0); frame_rate = @('2', 0); loop_count = 0
        filename_prefix = "upscaled/$base"; format = $Format
        pingpong = $false; save_output = $true
        audio = @('1', 2)
      }
    }
  }

  # 编码质量参数按格式分派：h264/h265-mp4 用 crf，nvenc_* 用 bitrate+megabit。
  # 两套格式的 widget 定义不同（见 VideoHelperSuite 的 video_formats\*.json），
  # 给 nvenc 传 crf 不会报错但会被忽略，质量会锁死在默认码率上。
  if ($Format -like '*nvenc*') {
    $prompt['4'].inputs['bitrate'] = $Bitrate
    $prompt['4'].inputs['megabit'] = $true
  } else {
    $prompt['4'].inputs['crf'] = $Crf
  }

  $sw = [Diagnostics.Stopwatch]::StartNew()
  try {
    Invoke-ComfyPrompt -Prompt $prompt -TimeoutSec $TimeoutSec | Out-Null
  } catch {
    Write-Note "失败：$($_.Exception.Message)"
    $fail++; continue
  }
  $sw.Stop()

  $after = @(Get-ChildItem $comfyOutDir -File -Filter "$base`_*" -ErrorAction SilentlyContinue |
             ForEach-Object { $_.FullName })
  $new = @($after | Where-Object { $before -notcontains $_ } |
           Sort-Object { (Get-Item $_).LastWriteTime } -Descending)

  if ($new.Count -eq 0) {
    Write-Note '跑完了但没找到输出文件，请到 ComfyUI 网页里看日志'
    $fail++; continue
  }

  Move-Item -Path $new[0] -Destination $outFile -Force
  $mb = [math]::Round((Get-Item $outFile).Length / 1MB, 1)
  Write-Done ("完成，用时 {0:hh\:mm\:ss}，输出 {1} MB" -f $sw.Elapsed, $mb)
  $ok++
}

Write-Host ""
Write-Host "全部结束：成功 $ok / 跳过 $skip / 失败 $fail" -ForegroundColor Green
Write-Host "输出目录：$OutDir" -ForegroundColor Gray