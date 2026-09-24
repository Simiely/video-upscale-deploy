<#
  02-FlashVSR\安装FlashVSR.ps1
  作用：为方案二准备运行环境。
        1) 装 VideoHelperSuite 节点 —— 负责「读视频成帧序列 / 把帧序列写回视频」
        2) 装 FlashVSR Ultra-Fast 节点 —— 真正做超分的节点（低显存也不出鬼影）
        3) 从 HuggingFace 镜像下载 FlashVSR-v1.1 全套权重到 models\FlashVSR-v1.1
  产出：ComfyUI\custom_nodes\ComfyUI-FlashVSR_Ultra_Fast
        ComfyUI\models\FlashVSR-v1.1（约 7 GB）
  说明：FlashVSR 是扩散类「流式」视频超分，画质远好于逐帧的 Real-ESRGAN，
        代价是慢得多、吃显存，所以它放 4090 或 4070TiS 上跑最舒服。
#>

param(
  # 同时也把老版 FlashVSR（v1）下下来，便于对比
  [switch]$AlsoLegacyV1
)

. "$PSScriptRoot\..\common.ps1"

Write-Host "===== 方案二：安装 ComfyUI + FlashVSR =====" -ForegroundColor White

# ---------- 1. 环境检查 ----------
Write-Step 1 6 "检查环境"
Show-Gpu
Assert-ComfyReady
Write-Done "ComfyUI 虚拟环境已就绪：$COMFY_PY"
New-ProjectDirs

$free = (Get-PSDrive -Name (Split-Path $UPSCALE_ROOT -Qualifier).TrimEnd(':')).Free
if ($free -lt 15GB) { Write-Note "C 盘剩余空间 $([math]::Round($free/1GB,1)) GB，建议留 15 GB 以上（节点+权重约 8 GB）" }

# ---------- 2. 视频读写节点 ----------
Write-Step 2 6 "安装 VideoHelperSuite（视频 <-> 帧序列 的读写节点）"
Install-ComfyNode -RepoUrl 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git' `
                  -DirName 'ComfyUI-VideoHelperSuite'

# ---------- 3. FlashVSR 节点 ----------
Write-Step 3 6 "安装 FlashVSR Ultra-Fast 节点"
Install-ComfyNode -RepoUrl 'https://github.com/lihaoyun6/ComfyUI-FlashVSR_Ultra_Fast.git' `
                  -DirName 'ComfyUI-FlashVSR_Ultra_Fast'

# 该节点的稀疏注意力在 Windows 上依赖 triton-windows；缺了会在导入时报错。
# 节点自己的 requirements.txt 已经写了 platform_system=="Windows" 的条件依赖，
# 这里只是兜底：万一上一步没装上，再显式补一次。
& $COMFY_PY -c "import triton" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Note '缺少 triton，正在补装 triton-windows'
  & $COMFY_PY -m pip install -U triton-windows
  if ($LASTEXITCODE -ne 0) { throw 'triton-windows 安装失败，FlashVSR 节点无法导入' }
}

# posi_prompt.pth 不在 HuggingFace 权重里，而是随节点仓库一起提交（约 4 MB），
# 由 nodes.py 从节点目录自身加载。所以克隆必须是完整的，缺了会直接报错。
$promptPth = Join-Path $COMFY_NODES 'ComfyUI-FlashVSR_Ultra_Fast\posi_prompt.pth'
if (-not (Test-Path $promptPth)) {
  throw "缺少 $promptPth`n这个文件随节点仓库提供，请删除该节点目录后重新克隆（别用不完整的 zip 包）"
}
Write-Done "FlashVSR 节点依赖检查完成（posi_prompt.pth 就位）"

# ---------- 4. 下载权重 ----------
Write-Step 4 6 "下载 FlashVSR-v1.1 权重（约 7 GB，走 $HF_ENDPOINT）"
$v11Dir = Join-Path $COMFY_MODEL 'FlashVSR-v1.1'
Invoke-HfDownload -Repo 'JunhaoZhuang/FlashVSR-v1.1' -LocalDir $v11Dir

if ($AlsoLegacyV1) {
  Write-Detail "额外下载老版 FlashVSR（v1）"
  Invoke-HfDownload -Repo 'JunhaoZhuang/FlashVSR' -LocalDir (Join-Path $COMFY_MODEL 'FlashVSR')
}

# ---------- 5. 校验 ----------
Write-Step 5 6 "校验权重完整性"
Assert-ModelFiles -Dir $v11Dir -Files @(
  'diffusion_pytorch_model_streaming_dmd.safetensors',
  'Wan2.1_VAE.pth',
  'LQ_proj_in.ckpt',
  'TCDecoder.ckpt'
)

# ---------- 6. 冒烟测试 ----------
Write-Step 6 6 "冒烟测试：让 ComfyUI 真正加载一遍自定义节点"
# ComfyUI 自带的 --quick-test-for-ci 会加载全部自定义节点后立刻退出，
# 能真实暴露「节点导入失败」这类问题。比手动 import 可靠：
# custom_nodes 下的目录名带连字符、也不是 Python 包，没法用 import_module 直接导。
Push-Location $COMFY_DIR
try {
  $out = & $COMFY_PY main.py --quick-test-for-ci 2>&1
  $code = $LASTEXITCODE
  $bad = $out | Select-String -Pattern 'Traceback', 'Cannot import', 'ImportFailed', 'Failed to import'
  if ($bad) {
    Write-Note '节点导入报错，以下是关键几行：'
    $out | Select-Object -Last 20 | ForEach-Object { Write-Detail $_ }
    throw '自定义节点加载失败，请按上面日志排查'
  }
  if ($code -ne 0) {
    $out | Select-Object -Last 10 | ForEach-Object { Write-Detail $_ }
    throw "ComfyUI 自检退出码 $code"
  }
  Write-Done "节点加载正常"
} finally { Pop-Location }

Write-Host ""
Write-Host "安装完成。接下来：" -ForegroundColor Green
Write-Host "  1) 批量放大：powershell -File `"$PSScriptRoot\批量放大.ps1`" -InputPath `"$INPUT_DIR`" -Scale 4" -ForegroundColor Gray
Write-Host "     （脚本会自己拉起 ComfyUI，也可以先加 -AutoStart）" -ForegroundColor DarkGray
Write-Host "  2) 网页界面：powershell -File `"$PSScriptRoot\..\00-ComfyUI底座\启动ComfyUI.ps1`"" -ForegroundColor Gray
Write-Host "     界面里按 ..\docs\使用指南.md 第五节的连线表拖 4 个节点即可" -ForegroundColor DarkGray