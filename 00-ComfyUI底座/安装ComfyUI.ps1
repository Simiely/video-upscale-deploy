<#
  00-ComfyUI底座\安装ComfyUI.ps1
  作用：为方案二(FlashVSR)与方案三(SeedVR2)准备同一个 ComfyUI 运行环境。
        只装底座，不装任何超分节点，节点由各自方案的安装脚本负责。
  产出：C:\AI\ComfyUI  +  C:\AI\ComfyUI\.venv（Python 3.12 + CUDA 版 PyTorch）
#>

. "$PSScriptRoot\..\common.ps1"

Write-Host "===== 方案底座：安装 ComfyUI =====" -ForegroundColor White

# ---------- 1. 环境检查 ----------
Write-Step 1 6 "检查环境（显卡 / git / Python 3.12+ / 磁盘）"
Show-Gpu
if (-not (Test-Cmd 'git')) { throw '未找到 git，请先安装 Git for Windows' }
Write-Detail "git 版本：$((& git --version))"

$basePy = Get-BasePython
if (-not $basePy) {
  throw @"
未找到 Python 3.12 / 3.13。请任选一种方式安装后重跑：
  1) py install 3.12          （Windows 官方启动器，最简单）
  2) winget install Python.Python.3.12
  3) 到 python.org 下载 3.12 安装包
"@
}
$pyVer = & $basePy --version
Write-Done "基础 Python：$basePy（$pyVer）"

New-ProjectDirs
Write-Done "目录就绪：$UPSCALE_ROOT（程序/模型）、$UPSCALE_IO（素材/输出）"

# ---------- 2. 拉取 ComfyUI ----------
Write-Step 2 6 "拉取 ComfyUI 源码"
if (Test-Path (Join-Path $COMFY_DIR 'main.py')) {
  Write-Done "已存在，跳过克隆"
} else {
  & git clone https://github.com/comfyanonymous/ComfyUI.git $COMFY_DIR
  if ($LASTEXITCODE -ne 0) { throw '克隆 ComfyUI 失败，请检查网络（必要时配置代理）' }
  Write-Done "已克隆到 $COMFY_DIR"
}

# ---------- 3. 建虚拟环境 ----------
Write-Step 3 6 "创建虚拟环境 .venv"
if (Test-Path $COMFY_PY) {
  Write-Done "已存在，跳过"
} else {
  & $basePy -m venv $COMFY_VENV
  if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
  Write-Done "已创建：$COMFY_VENV"
}
& $COMFY_PY -m pip install --upgrade pip setuptools wheel | Out-Null
Write-Done "pip 已升级"

# ---------- 4. 安装 CUDA 版 PyTorch ----------
Write-Step 4 6 "安装 CUDA 版 PyTorch（按 CUDA 13.0 -> 12.8 -> 12.6 依次尝试）"
$indexes = @(
  @{ Url = 'https://download.pytorch.org/whl/cu130'; Name = 'CUDA 13.0' },
  @{ Url = 'https://download.pytorch.org/whl/cu128'; Name = 'CUDA 12.8' },
  @{ Url = 'https://download.pytorch.org/whl/cu126'; Name = 'CUDA 12.6' }
)
$torchOk = $false
foreach ($idx in $indexes) {
  Write-Detail "尝试 $($idx.Name) ..."
  & $COMFY_PY -m pip install torch torchvision torchaudio --index-url $idx.Url
  if ($LASTEXITCODE -ne 0) { Write-Note "$($idx.Name) 安装失败，换下一个"; continue }

  & $COMFY_PY -c "import torch,sys;print('torch',torch.__version__,'| cuda',torch.version.cuda,'| 可用',torch.cuda.is_available());sys.exit(0 if torch.cuda.is_available() else 1)"
  if ($LASTEXITCODE -eq 0) { $torchOk = $true; Write-Done "$($idx.Name) 就绪且 CUDA 可用"; break }
  Write-Note "$($idx.Name) 装上了但 CUDA 不可用（多半是驱动太旧），换下一个"
}
if (-not $torchOk) {
  Write-Note 'PyTorch CUDA 安装未成功。请先更新 NVIDIA 驱动到最新版，再重跑本脚本。'
  throw 'PyTorch 环境未就绪'
}

# ---------- 5. 安装 ComfyUI 依赖 ----------
Write-Step 5 6 "安装 ComfyUI 依赖"
Push-Location $COMFY_DIR
try {
  & $COMFY_PY -m pip install -r requirements.txt
  if ($LASTEXITCODE -ne 0) { throw '安装 ComfyUI requirements.txt 失败' }
} finally { Pop-Location }
Write-Done "ComfyUI 依赖安装完成"

# ---------- 6. 安装 ComfyUI-Manager ----------
Write-Step 6 6 "安装 ComfyUI-Manager（后续装节点/查缺失节点都用它）"
$mgrDir = Join-Path $COMFY_NODES 'ComfyUI-Manager'
if (Test-Path $mgrDir) {
  Write-Done "已存在，跳过"
} else {
  & git clone https://github.com/ltdrdata/ComfyUI-Manager.git $mgrDir
  if ($LASTEXITCODE -ne 0) { throw '克隆 ComfyUI-Manager 失败' }
  & $COMFY_PY -m pip install -r (Join-Path $mgrDir 'requirements.txt')
  Write-Done "ComfyUI-Manager 安装完成"
}

Write-Host ""
Write-Host "底座安装完成。" -ForegroundColor Green
Write-Host "启动方式：powershell -File `"$PSScriptRoot\启动ComfyUI.ps1`"" -ForegroundColor Gray
Write-Host "浏览器打开：http://127.0.0.1:8188" -ForegroundColor Gray