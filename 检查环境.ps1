<#
  检查环境.ps1
  作用：装之前先体检，5 秒看清这台机器能不能跑、该走哪个方案。
        只读检查，不改任何东西，随时可以重复跑。

  用法：powershell -ExecutionPolicy Bypass -File .\检查环境.ps1
#>

. "$PSScriptRoot\common.ps1"

Write-Host "===== 视频放大部署 · 环境体检 =====" -ForegroundColor White
Write-Host ""

# ---------- 1. 显卡 ----------
Write-Step 1 6 "显卡与驱动"
$gpus = @()
if (Test-Cmd 'nvidia-smi') {
  $rows = & nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader 2>$null
  foreach ($r in $rows) {
    $p = $r -split ',\s*'
    $gpus += [pscustomobject]@{
      Index  = [int]$p[0]
      Name   = $p[1]
      VramGB = [math]::Round(([int]($p[2] -replace '[^\d]', '')) / 1024, 0)
      Driver = $p[3]
    }
    Write-Host ("    [{0}] {1}  {2} GB  驱动 {3}" -f $p[0], $p[1], [math]::Round(([int]($p[2] -replace '[^\d]', '')) / 1024, 0), $p[3]) -ForegroundColor Gray
  }
  Write-Done "识别到 $($gpus.Count) 张 NVIDIA 显卡"
} else {
  Write-Note '没找到 nvidia-smi。装好 NVIDIA 驱动后重开终端再试；方案一（Video2X）走 Vulkan，对驱动要求更低。'
}

# ---------- 2. 基础工具 ----------
Write-Step 2 6 "基础工具（git / Python / ffmpeg）"
if (Test-Cmd 'git') {
  Write-Done "git：$(& git --version)"
} else {
  Write-Note '缺 git：ComfyUI 和节点都要用它拉代码。装法：winget install Git.Git'
}

$py = Get-BasePython
if ($py) {
  Write-Done "Python：$py（$(& $py --version)）"
} else {
  Write-Note '缺 Python 3.12/3.13：装法：winget install Python.Python.3.12'
}

if (Test-Cmd 'ffmpeg') {
  Write-Done "ffmpeg：$((& ffmpeg -version | Select-Object -First 1) -replace '\s+', ' ')"
} else {
  Write-Note '缺 ffmpeg：不装也能出片，但方案三用不了 10bit 输出、方案一少一层封装能力。装法：winget install Gyan.FFmpeg'
}

# ---------- 3. 磁盘 ----------
Write-Step 3 6 "磁盘空间"
foreach ($d in @($UPSCALE_ROOT, $UPSCALE_IO)) {
  $q = (Split-Path $d -Qualifier).TrimEnd(':')
  if (Test-Path "$($q):\") {
    $free = [math]::Round((Get-PSDrive -Name $q).Free / 1GB, 1)
    $mark = if ($free -ge 40) { '充足' } elseif ($free -ge 20) { '够用' } else { '偏紧' }
    Write-Host ("    {0}  剩余 {1} GB（{2}）" -f $d, $free, $mark) -ForegroundColor Gray
  } else {
    Write-Note "$d 所在的 $q 盘不存在，请改 common.ps1 里的 UPSCALE_ROOT / UPSCALE_IO"
  }
}
Write-Detail '参考占用：Video2X 便携包约 0.2 GB（放大用的模型首次运行时另下）；FlashVSR 约 7 GB；SeedVR2 按档位 3.9–42.4 GB'

# ---------- 4. 已有安装情况 ----------
Write-Step 4 6 "已有安装情况"
$checks = @(
  @{ Name = 'ComfyUI 底座';    Path = (Join-Path $COMFY_DIR 'main.py') },
  @{ Name = 'ComfyUI 虚拟环境'; Path = $COMFY_PY },
  @{ Name = 'Video2X';          Path = $VIDEO2X_DIR },
  @{ Name = 'FlashVSR 节点';    Path = (Join-Path $COMFY_NODES 'ComfyUI-FlashVSR_Ultra_Fast') },
  @{ Name = 'VideoHelperSuite'; Path = (Join-Path $COMFY_NODES 'ComfyUI-VideoHelperSuite') },
  @{ Name = 'SeedVR2 节点';     Path = (Join-Path $COMFY_NODES 'seedvr2_videoupscaler') }
)
foreach ($c in $checks) {
  if (Test-Path $c.Path) { Write-Host ("    [已装] {0}" -f $c.Name) -ForegroundColor Green }
  else { Write-Host ("    [未装] {0}" -f $c.Name) -ForegroundColor DarkGray }
}

# ---------- 5. 按显卡给建议 ----------
Write-Step 5 6 "这台机器怎么分配"
if ($gpus.Count -eq 0) {
  Write-Note '没读到显卡信息，先解决驱动问题，再决定方案。'
} else {
  foreach ($g in $gpus) {
    # 下面三个档位名和 03-SeedVR2\批量放大.ps1 的 -Profile 一一对应，别改名字
    $plan = if ($g.VramGB -ge 22) {
      '方案三 -Profile 24g（7B FP8 mixed + torch.compile，画质优先）+ 方案二 full；方案一出草稿'
    } elseif ($g.VramGB -ge 15) {
      '方案三 -Profile 16g（3B FP16 + BlockSwap 16）+ 方案二 tiny；方案一兜底'
    } else {
      '方案一 Real-CUGAN（最快最稳）+ 方案二 tiny-long；方案三 -Profile 12g（3B FP8 + BlockSwap 24）只用于关键镜头'
    }
    Write-Host ("    [{0}] {1} {2} GB -> {3}" -f $g.Index, $g.Name, $g.VramGB, $plan) -ForegroundColor Gray
  }
  if ($gpus.Count -ge 2) {
    Write-Host "    多卡可叠加：SeedVR2 支持 --cuda_device ""0,1"" 帧级并行。每张卡各载一份模型，显存需求不叠加；提速取决于两卡速度差，不会正好翻倍。" -ForegroundColor Gray
  }
}

# ---------- 6. 下一步 ----------
Write-Step 6 6 "下一步"
Write-Host "    1) 先跑方案一（最快见效，不吃显存）：" -ForegroundColor Gray
Write-Host "       powershell -File `"$PSScriptRoot\01-Video2X\安装Video2X.ps1`"" -ForegroundColor DarkGray
Write-Host "    2) 再装 ComfyUI 底座（方案二、三共用）：" -ForegroundColor Gray
Write-Host "       powershell -File `"$PSScriptRoot\00-ComfyUI底座\安装ComfyUI.ps1`"" -ForegroundColor DarkGray
Write-Host "    3) 按显卡档次装方案二 / 方案三，见 docs\使用指南.md" -ForegroundColor Gray
Write-Host ""