<#
  03-SeedVR2\安装SeedVR2.ps1
  作用：为方案三准备运行环境。
        1) 装 SeedVR2 官方 ComfyUI 集成节点（ByteDance SeedVR2 的封装）
        2) 按显卡档次下载对应精度的权重到 ComfyUI\models\SEEDVR2
  产出：ComfyUI\custom_nodes\seedvr2_videoupscaler
        ComfyUI\models\SEEDVR2
  说明：SeedVR2 是「一步扩散」视频修复/放大模型，画质是三套里最好的，
        而且节点自带 inference_cli.py，天生适合命令行批量跑。
        代价是最慢、最吃显存，所以权重精度要按显存挑。

  -Profile 与 批量放大.ps1 的档位一一对应（同一个名字，装完直接就能跑）：
    12g   4070 Super 12G      3B FP8
    16g   4070 Ti Super 16G   3B FP16（比 FP8 画质好）+ 3B FP8 备用
    24g   4090 24G            7B FP8(mixed) + 7B FP16（画质天花板）
    all   三张卡都要用        全部权重 + 3B GGUF Q4 兜底

  权重仓库（节点源码 src\utils\model_registry.py 里写死的，不能改）：
    numz/SeedVR2_comfyUI      safetensors 类权重
    AInVFX/SeedVR2_comfyUI    GGUF 量化权重
#>

param(
  [ValidateSet('12g', '16g', '24g', 'all')]
  [string]$Profile = '12g',

  # 额外再下一份 3B GGUF Q4（体积小，显存极度紧张时用），任何档位都能叠加
  [switch]$AlsoGguf
)

. "$PSScriptRoot\..\common.ps1"

Write-Host "===== 方案三：安装 ComfyUI + SeedVR2 =====" -ForegroundColor White

# ---------- 1. 环境检查 ----------
Write-Step 1 5 "检查环境"
Show-Gpu
Assert-ComfyReady
Write-Done "ComfyUI 虚拟环境已就绪：$COMFY_PY"
New-ProjectDirs

# 注意：这里要的是「完整版」ffmpeg（能读 rawvideo），不能只看 PATH 上有没有 ffmpeg——
# 精简构建（如 TRAE 自带的 --disable-everything 版本）会被 Test-Cmd 误判为可用。
$ffOk = Resolve-FfmpegTool
$ffX265 = Resolve-FfmpegTool -NeedX265
if (-not $ffOk) {
  Write-Note '没找到可用的 ffmpeg（需要支持 rawvideo 的完整版）。不影响出片，但 --video_backend ffmpeg 用不了。'
  Write-Detail '装一个完整版：winget install Gyan.FFmpeg（装完重开终端），或设 FFMPEG_PATH 环境变量。'
} elseif (-not $ffX265) {
  Write-Detail "ffmpeg 就绪：$ffOk（不带 libx265，-TenBit 10bit 输出不可用，普通 H.264 不受影响）"
} else {
  Write-Detail "ffmpeg 就绪（含 libx265，支持 -TenBit）：$ffX265"
}

# ---------- 2. 安装节点 ----------
Write-Step 2 5 "安装 SeedVR2 节点"
Install-ComfyNode -RepoUrl 'https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler.git' `
                  -DirName 'seedvr2_videoupscaler'

# ---------- 3. 下载权重 ----------
Write-Step 3 5 "下载权重到 models\SEEDVR2（走 $HF_ENDPOINT）"
$modelDir = Join-Path $COMFY_MODEL 'SEEDVR2'

$VAE = 'ema_vae_fp16.safetensors'
$FP8_3B = 'seedvr2_ema_3b_fp8_e4m3fn.safetensors'
$FP16_3B = 'seedvr2_ema_3b_fp16.safetensors'
$FP16_7B = 'seedvr2_ema_7b_fp16.safetensors'
$FP8_7B = 'seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors'
$GGUF_3B = 'seedvr2_ema_3b-Q4_K_M.gguf'
$GGUF_7B = 'seedvr2_ema_7b-Q4_K_M.gguf'

# 两个仓库分开收集：fp16/fp8 走 numz，GGUF 和 7B mixed-fp8 走 AInVFX。
# 按仓库分组是必须的，文件名下错仓库会 404（例如 7B mixed-fp8 只在 AInVFX 有）。
$want = @{
  'numz/SeedVR2_comfyUI'   = @($VAE)
  'AInVFX/SeedVR2_comfyUI' = @()
}

switch ($Profile) {
  '12g' { $want['numz/SeedVR2_comfyUI'] += @($FP8_3B) }
  '16g' { $want['numz/SeedVR2_comfyUI'] += @($FP16_3B, $FP8_3B) }
  '24g' {
    $want['numz/SeedVR2_comfyUI']   += @($FP16_7B)
    $want['AInVFX/SeedVR2_comfyUI'] += @($FP8_7B)
  }
  'all' {
    $want['numz/SeedVR2_comfyUI']   += @($FP8_3B, $FP16_3B, $FP16_7B)
    $want['AInVFX/SeedVR2_comfyUI'] += @($FP8_7B)
  }
}

if ($AlsoGguf -or $Profile -eq 'all') {
  $want['AInVFX/SeedVR2_comfyUI'] += @($GGUF_3B)
}
if ($Profile -eq 'all') {
  $want['AInVFX/SeedVR2_comfyUI'] += @($GGUF_7B)
}

foreach ($repo in $want.Keys) {
  $files = @($want[$repo] | Sort-Object -Unique)
  if ($files.Count -eq 0) { continue }
  Invoke-HfDownload -Repo $repo -LocalDir $modelDir -Include ($files -join ',')
}

# ---------- 4. 校验 ----------
Write-Step 4 5 "校验权重完整性"
$need = @()
foreach ($repo in $want.Keys) { $need += $want[$repo] }
Assert-ModelFiles -Dir $modelDir -Files ($need | Sort-Object -Unique)

# ---------- 5. 自检 CLI ----------
Write-Step 5 5 "自检：确认命令行入口可用"
$cli = Join-Path $COMFY_NODES 'seedvr2_videoupscaler\inference_cli.py'
if (-not (Test-Path $cli)) { throw "没找到 $cli，节点可能没装好" }

# CLI 在 import 阶段就要用到 diffusers / peft / rotary_embedding_torch / gguf 等
# 依赖，所以「能打出 help」就说明依赖齐全。注意没带参数时它会自己补 --help。
Push-Location $COMFY_DIR
try {
  $help = & $COMFY_PY $cli --help 2>&1
  if ($LASTEXITCODE -ne 0) {
    Write-Detail ($help | Select-Object -Last 5 | Out-String)
    throw 'SeedVR2 CLI 自检失败，多半是依赖没装全'
  }
  $help | Select-Object -First 6 | ForEach-Object { Write-Detail $_ }
} finally { Pop-Location }
Write-Done "SeedVR2 CLI 可用"

Write-Host ""
Write-Host "安装完成。接下来：" -ForegroundColor Green
Write-Host "  1) 命令行批量放大：powershell -File `"$PSScriptRoot\批量放大.ps1`" -InputPath `"$INPUT_DIR`" -Profile $Profile" -ForegroundColor Gray
Write-Host "  2) 网页界面里用：powershell -File `"$PSScriptRoot\..\00-ComfyUI底座\启动ComfyUI.ps1`"" -ForegroundColor Gray