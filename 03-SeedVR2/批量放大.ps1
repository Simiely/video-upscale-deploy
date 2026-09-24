<#
  03-SeedVR2\批量放大.ps1
  作用：调用 SeedVR2 节点自带的命令行 inference_cli.py 批量放大。
        它不像方案二那样需要 ComfyUI 服务在跑，直接起进程就行，最适合挂机跑通宵。

  -Profile 是「按显卡一键配好参数」，和 安装SeedVR2.ps1 的档位同名：
    12g  -> 4070 Super 12G     3B FP8 + BlockSwap 24 + VAE 分块
    16g  -> 4070 Ti Super 16G  3B FP16（画质优于 FP8）+ BlockSwap 16
    24g  -> 4090 24G           7B FP8(mixed) + torch.compile，画质优先
    custom -> 完全手动，用下面那些参数自己调

  下面的批大小/BlockSwap 是「起步值」，不是最优值：
  显存不够就减小 -BatchSize 或加大 -BlocksToSwap，显存有余就反向调。

  示例：
    # 4070S 挂机跑一整个文件夹
    .\批量放大.ps1 -Input "E:\VideoUpscale\input" -Profile 12g

    # 4090 上冲画质，输出 1080 短边、10bit
    .\批量放大.ps1 -Input "a.mp4" -Profile 24g -Resolution 1080 -TenBit

    # 两张卡一起跑一个长视频（帧级并行）
    .\批量放大.ps1 -Input "a.mp4" -Profile 24g -CudaDevice "0,1" -ChunkSize 330

    # 显存不够时的手动兜底
    .\批量放大.ps1 -Input "a.mp4" -Profile custom `
                   -DitModel seedvr2_ema_3b-Q4_K_M.gguf -BlocksToSwap 32 -OffloadCpu -BatchSize 5 -TiledVae
#>

param(
  [Parameter(Mandatory = $true)][string]$Input,

  [ValidateSet('12g', '16g', '24g', 'custom')][string]$Profile = '24g',

  # ---- 以下参数留空则用 Profile 的推荐值 ----
  [string]$DitModel = '',
  [int]$Resolution = 0,            # 目标短边像素（不是放大倍数）
  [int]$MaxResolution = 0,         # 任一边上限，0=不限
  [int]$BatchSize = 0,             # 必须是 4n+1：1/5/9/13/17/21...
  [int]$BlocksToSwap = -1,         # -1=跟随 Profile；0=关闭；3B 上限 32，7B 上限 36
  [int]$ChunkSize = 0,             # >0 开启流式分块，长视频省内存
  [int]$TemporalOverlap = -1,
  [string]$CudaDevice = '',        # "0" 或 "0,1"
  [int]$Seed = 42,
  [ValidateSet('lab', 'wavelet', 'wavelet_adaptive', 'hsv', 'adain', 'none')]
  [string]$ColorCorrection = 'lab',

  # ---- 开关 ----
  [switch]$OffloadCpu,             # DiT/VAE 平时放内存，省显存（BlockSwap 的前置条件）
  [switch]$TiledVae,               # VAE 分块编解码
  [switch]$UniformBatchSize,       # 末批补齐，减少闪烁
  [switch]$CompileDit,             # torch.compile 加速 DiT（首次编译慢）
  [switch]$CompileVae,
  [switch]$CacheModels,            # 批量时模型常驻内存，避免反复加载（需 -OffloadCpu）
  [switch]$TenBit,                 # 需要 ffmpeg，10bit 输出减少色带

  [string]$OutDir = '',
  [switch]$Overwrite
)

. "$PSScriptRoot\..\common.ps1"

# ---------- 1. 按显卡档次套用推荐参数 ----------
$rec = switch ($Profile) {
  '12g' { @{ Dit = 'seedvr2_ema_3b_fp8_e4m3fn.safetensors'; Res = 1080; Batch = 5;  Swap = 24; Offload = $true;  Tiled = $true;  Compile = $false } }
  '16g' { @{ Dit = 'seedvr2_ema_3b_fp16.safetensors';      Res = 1080; Batch = 9;  Swap = 16; Offload = $true;  Tiled = $true;  Compile = $false } }
  '24g' { @{ Dit = 'seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors'; Res = 1080; Batch = 21; Swap = 0; Offload = $false; Tiled = $false; Compile = $true } }
  'custom' { @{ Dit = ''; Res = 1080; Batch = 5; Swap = 0; Offload = $false; Tiled = $false; Compile = $false } }
}

if (-not $DitModel)     { $DitModel = $rec.Dit }
if ($Resolution -le 0)  { $Resolution = $rec.Res }
if ($BatchSize -le 0)   { $BatchSize = $rec.Batch }
if ($BlocksToSwap -lt 0) { $BlocksToSwap = $rec.Swap }
if ($TemporalOverlap -lt 0) { $TemporalOverlap = if ($BatchSize -ge 17) { 3 } else { 0 } }

if (-not $OffloadCpu -and $rec.Offload) { $OffloadCpu = $true }
if (-not $TiledVae   -and $rec.Tiled)   { $TiledVae   = $true }
if (-not $CompileDit -and $rec.Compile) { $CompileDit = $true }

if (($BatchSize - 1) % 4 -ne 0) {
  throw "BatchSize 必须是 4n+1（1/5/9/13/17/21...），当前是 $BatchSize"
}
if ($BlocksToSwap -gt 0 -and -not $OffloadCpu) {
  throw 'BlockSwap 需要配合 -OffloadCpu（--dit_offload_device）才能生效'
}
if ($CacheModels -and -not $OffloadCpu) {
  throw '-CacheModels 需要配合 -OffloadCpu：--cache_dit 要求先指定 --dit_offload_device'
}

# ---------- 2. 准备 ----------
$cli = Join-Path $COMFY_NODES 'seedvr2_videoupscaler\inference_cli.py'
if (-not (Test-Path $cli)) { throw "未安装 SeedVR2，请先运行 安装SeedVR2.ps1" }

$modelDir = Join-Path $COMFY_MODEL 'SEEDVR2'
if (-not (Test-Path $modelDir)) { throw "未找到权重目录 $modelDir，请先运行 安装SeedVR2.ps1" }
if ($DitModel -and -not (Test-Path (Join-Path $modelDir $DitModel))) {
  throw "缺少 DiT 权重 $DitModel`n请用对应档位重跑安装脚本，例如：  .\安装SeedVR2.ps1 -Profile $Profile"
}

if (-not $OutDir) { $OutDir = $OUTPUT_DIR }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$isDir = Test-Path $Input -PathType Container
if (-not (Test-Path $Input)) { throw "输入路径不存在：$Input" }

# ---------- 3. 拼命令行 ----------
# --model_dir 显式指定，免得 CLI 在 import folder_paths 失败时回退到 ./models/SEEDVR2
# 而受当前工作目录影响。
$a = @($cli, $Input, '--output', $OutDir, '--output_format', 'mp4',
       '--model_dir', $modelDir, '--resolution', $Resolution,
       '--batch_size', $BatchSize, '--seed', $Seed,
       '--color_correction', $ColorCorrection,
       '--temporal_overlap', $TemporalOverlap)
if ($DitModel)             { $a += @('--dit_model', $DitModel) }
if ($MaxResolution -gt 0)  { $a += @('--max_resolution', $MaxResolution) }
if ($ChunkSize -gt 0)      { $a += @('--chunk_size', $ChunkSize) }
if ($CudaDevice)           { $a += @('--cuda_device', $CudaDevice) }
if ($UniformBatchSize)     { $a += '--uniform_batch_size' }
if ($TiledVae)             { $a += @('--vae_encode_tiled', '--vae_decode_tiled') }
if ($CompileDit)           { $a += '--compile_dit' }
if ($CompileVae)           { $a += '--compile_vae' }
if ($TenBit)               { $a += @('--video_backend', 'ffmpeg', '--10bit') }
if ($OffloadCpu) {
  $a += @('--dit_offload_device', 'cpu', '--vae_offload_device', 'cpu')
  if ($BlocksToSwap -gt 0) { $a += @('--blocks_to_swap', $BlocksToSwap, '--swap_io_components') }
  if ($CacheModels)        { $a += @('--cache_dit', '--cache_vae') }
}

Write-Host "===== 方案三：SeedVR2 批量放大 =====" -ForegroundColor White
Write-Step 1 2 "参数确认"
Write-Detail "档位      : $Profile"
Write-Detail "DiT 模型  : $(if ($DitModel) { $DitModel } else { '（用 CLI 默认 3B FP8）' })"
Write-Detail "目标短边  : ${Resolution}p（上限 $MaxResolution）"
Write-Detail "批大小    : $BatchSize 帧/批，重叠 $TemporalOverlap 帧"
$swapNote = if ($OffloadCpu -and $BlocksToSwap -gt 0) { '（已启用）' } else { '' }
Write-Detail "BlockSwap : $BlocksToSwap 层$swapNote"
Write-Detail "输出目录  : $OutDir"
if ($TenBit) { Write-Note '已开启 10bit 输出，务必确认 ffmpeg 在 PATH 里' }

# 单文件模式下 CLI 会自己决定落盘文件名，用「起始时间戳」判断哪些文件是本次新产出的，
# 比对比文件名集合更可靠（同名文件被覆盖也能认出来）。
$watch = @($OutDir)
if (-not $isDir) { $watch += (Split-Path $Input -Parent) }
$startTime = Get-Date

# ---------- 4. 开跑 ----------
Write-Step 2 2 "开始处理（首次运行会加载模型，耐心等）"
Push-Location $COMFY_DIR
try {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & $COMFY_PY @a
  $code = $LASTEXITCODE
  $sw.Stop()
} finally { Pop-Location }

if ($code -ne 0) {
  Write-Host ""
  Write-Note "SeedVR2 退出码 $code，常见原因："
  Write-Detail '显存不足(OOM)  -> 调小 -BatchSize，或加大 -BlocksToSwap（如 32），或换 3B/GGUF 模型'
  Write-Detail '参数被拒绝     -> 检查 -DitModel 是不是 models\SEEDVR2 里真实存在的文件名'
  Write-Detail 'ffmpeg 报错    -> 去掉 -TenBit'
  exit $code
}

# ---------- 5. 收尾 ----------
if (-not $isDir) {
  $base = [IO.Path]::GetFileNameWithoutExtension($Input)
  $new = @()
  foreach ($d in $watch) {
    $new += Get-ChildItem $d -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -ge $startTime -and $_.Extension -match '^\.(mp4|mkv|mov|webm)$' }
  }
  if ($new.Count -gt 0) {
    $src = ($new | Sort-Object LastWriteTime -Descending)[0]
    $target = Join-Path $OutDir "${base}_${Resolution}p_seedvr2.mp4"
    if ((Test-Path $target) -and -not $Overwrite) {
      Write-Note "输出已存在：$target（加 -Overwrite 可覆盖）"
    } else {
      Move-Item -Path $src.FullName -Destination $target -Force
      $mb = [math]::Round((Get-Item $target).Length / 1MB, 1)
      Write-Done ("完成，用时 {0:hh\:mm\:ss}，输出 {1} MB" -f $sw.Elapsed, $mb)
    }
  } else {
    Write-Note '跑完了但没定位到新文件，请检查上面日志里的输出路径'
  }
} else {
  Write-Done ("处理完成，用时 {0:hh\:mm\:ss}" -f $sw.Elapsed)
}

Write-Host ""
Write-Host "输出目录：$OutDir" -ForegroundColor Green