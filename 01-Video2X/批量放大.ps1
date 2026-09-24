<#
  01-Video2X\批量放大.ps1
  作用：调用 Video2X 命令行，把输入文件或整个目录里的视频逐个放大。
        逐帧处理、显存占用很低、速度最快，适合批量出片。
  示例：
    # 最快：Real-CUGAN 2 倍，真人/通用素材
    .\批量放大.ps1 -Input "E:\VideoUpscale\input" -Scale 2

    # 细节更多：Real-ESRGAN 4 倍（realesrgan-plus / realesrgan-plus-anime 都只有 4 倍权重）
    .\批量放大.ps1 -Input "a.mp4" -Processor realesrgan -Scale 4 -Model realesrgan-plus

    # 番剧：Anime4K 着色器，几乎不耗时
    .\批量放大.ps1 -Input "E:\VideoUpscale\input" -Processor libplacebo -Width 3840 -Height 2160

    # 补帧：24fps -> 60fps
    .\批量放大.ps1 -Input "a.mp4" -Processor rife -FrameMul 3
#>

param(
  [Parameter(Mandatory = $true)][string]$InputPath,
  [ValidateSet('realcugan', 'realesrgan', 'libplacebo', 'rife')][string]$Processor = 'realcugan',
  [int]$Scale = 2,
  [string]$Model = '',
  [int]$NoiseLevel = 0,
  [int]$Width = 0,
  [int]$Height = 0,
  [string]$Shader = 'anime4k-v4-a+a',
  [int]$FrameMul = 2,
  [int]$Gpu = -1,
  [int]$Crf = 17,
  [string]$Codec = 'libx264',
  [string]$OutDir = '',
  [switch]$Overwrite
)

. "$PSScriptRoot\..\common.ps1"

# ---------- 准备 ----------
$exe = Get-ChildItem $VIDEO2X_DIR -Recurse -Filter 'video2x.exe' -ErrorAction SilentlyContinue |
       Select-Object -First 1
if (-not $exe) { throw "未找到 video2x.exe，请先运行 安装Video2X.ps1" }
$exePath = $exe.FullName

if (-not $OutDir) { $OutDir = $OUTPUT_DIR }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# 各处理器的默认模型
if (-not $Model) {
  switch ($Processor) {
    'realcugan'  { $Model = 'models-se' }
    'realesrgan' { $Model = 'realesr-animevideov3' }
    'rife'       { $Model = 'rife-v4.26' }
    'libplacebo' { $Model = '' }
  }
}

# ---------- 参数合法性（提前报错，避免跑到一半才失败） ----------
# 下面的模型名与缩放倍数是按 Video2X 6.4.0 的 validators.cpp 抄的，
# 版本升级后如果新增了模型，这里的白名单需要同步更新。
$RealCuganModels = @('models-se', 'models-pro', 'models-nose')
$RealEsrganModels = @('realesr-animevideov3', 'realesrgan-plus', 'realesrgan-plus-anime')
$RifeModels = @('rife', 'rife-HD', 'rife-UHD', 'rife-anime', 'rife-v2', 'rife-v2.3', 'rife-v2.4',
                'rife-v3.0', 'rife-v3.1', 'rife-v4', 'rife-v4.6', 'rife-v4.25', 'rife-v4.25-lite', 'rife-v4.26')
$Anime4kShaders = @('anime4k-v4-a', 'anime4k-v4-a+a', 'anime4k-v4-b', 'anime4k-v4-b+b',
                    'anime4k-v4-c', 'anime4k-v4-c+a', 'anime4k-v4.1-gan')

switch ($Processor) {
  'realesrgan' {
    if ($Model -notin $RealEsrganModels) {
      throw "Real-ESRGAN 没有模型 $Model。可选：$($RealEsrganModels -join ' / ')"
    }
    if ($Scale -lt 2 -or $Scale -gt 4) { throw 'Real-ESRGAN 的 -Scale 只能是 2/3/4' }
    # realesrgan-plus 和 realesrgan-plus-anime 只有 4 倍权重
    if ($Scale -ne 4 -and $Model -ne 'realesr-animevideov3') {
      throw "$Model 只有 4 倍权重；要 2/3 倍只能用 realesr-animevideov3"
    }
  }
  'realcugan' {
    if ($Model -notin $RealCuganModels) {
      throw "Real-CUGAN 没有模型 $Model。可选：$($RealCuganModels -join ' / ')"
    }
    if ($Scale -lt 2 -or $Scale -gt 4) { throw 'Real-CUGAN 的 -Scale 只能是 2/3/4' }
    # 只有 models-se 带 4 倍权重；models-nose 只有 2 倍
    if ($Scale -eq 4 -and $Model -ne 'models-se') { throw "$Model 没有 4 倍权重，要 4 倍只能用 models-se" }
    if ($Scale -gt 2 -and $Model -eq 'models-nose') { throw 'models-nose 只有 2 倍，要 3/4 倍请用 models-se' }
  }
  'libplacebo' {
    if ($Width -le 0 -or $Height -le 0) { throw 'libplacebo 必须指定 -Width 和 -Height，例如 3840 / 2160' }
    if ($Shader -notin $Anime4kShaders -and $Shader -notlike '*.glsl') {
      throw "着色器 $Shader 无效。内置可选：$($Anime4kShaders -join ' / ')；也可以直接给一个 .glsl 文件路径"
    }
  }
  'rife' {
    if ($FrameMul -lt 2) { throw 'RIFE 的 -FrameMul 至少为 2' }
    if ($Model -notin $RifeModels) {
      throw "RIFE 没有模型 $Model。可选：$($RifeModels -join ' / ')"
    }
  }
}

$files = Get-VideoFiles -Path $InputPath
if ($files.Count -eq 0) { throw "输入路径下没有找到视频文件：$InputPath" }

# ---------- 逐个处理 ----------
$ok = 0; $fail = 0; $skip = 0
$total = $files.Count
$i = 0

foreach ($f in $files) {
  $i++
  $base = [IO.Path]::GetFileNameWithoutExtension($f.Name)
  if ($Processor -eq 'rife') { $suffix = "_${FrameMul}xfps" } else { $suffix = "_${Scale}x" }
  $outFile = Join-Path $OutDir "$base$suffix.mp4"

  Write-Step $i $total "$($f.Name)  ->  $(Split-Path $outFile -Leaf)"

  if ((Test-Path $outFile) -and -not $Overwrite) {
    Write-Note '输出已存在，跳过（加 -Overwrite 可覆盖）'
    $skip++; continue
  }

  $a = @('-i', $f.FullName, '-o', $outFile, '-p', $Processor, '-c', $Codec, '-e', "crf=$Crf", '-e', 'preset=slow')
  switch ($Processor) {
    'realesrgan' { $a += @('-s', $Scale, '--realesrgan-model', $Model, '-n', $NoiseLevel) }
    'realcugan'  { $a += @('-s', $Scale, '--realcugan-model', $Model, '-n', $NoiseLevel) }
    'libplacebo' { $a += @('-w', $Width, '-h', $Height, '--libplacebo-shader', $Shader) }
    'rife'       { $a += @('-m', $FrameMul, '--rife-model', $Model) }
  }
  if ($Gpu -ge 0) { $a += @('-d', $Gpu) }

  Write-Detail "video2x $($a -join ' ')"
  $sw = [Diagnostics.Stopwatch]::StartNew()
  & $exePath @a
  $code = $LASTEXITCODE
  $sw.Stop()

  # Video2X 6.4.0 Windows 版有时处理成功但退出码非 0（Vulkan 清理阶段的访问冲突），
  # 所以以「输出文件存在 + 大小 > 0」为准，退出码只作为辅助参考。
  $fileOk = (Test-Path $outFile) -and ((Get-Item $outFile).Length -gt 0)
  if ($fileOk) {
    $mb = [math]::Round((Get-Item $outFile).Length / 1MB, 1)
    Write-Done ("完成，用时 {0:mm\:ss}，输出 {1} MB" -f $sw.Elapsed, $mb)
    if ($code -ne 0) { Write-Detail "（退出码 $code，文件正常，忽略）" }
    $ok++
  } else {
    Write-Note "失败（退出码 $code）"
    $fail++
  }
}

Write-Host ""
Write-Host "全部结束：成功 $ok / 跳过 $skip / 失败 $fail" -ForegroundColor Green
Write-Host "输出目录：$OutDir" -ForegroundColor Gray