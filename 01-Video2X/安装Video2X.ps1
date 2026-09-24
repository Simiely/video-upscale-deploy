<#
  01-Video2X\安装Video2X.ps1
  作用：下载 Video2X 官方 Windows 便携版并解压。
        Video2X 是 C++/Vulkan 程序，不依赖 Python 和 CUDA，三张显卡都能直接跑。
  产出：C:\AI\Video2X\video2x.exe
#>

. "$PSScriptRoot\..\common.ps1"

Write-Host "===== 方案一：安装 Video2X =====" -ForegroundColor White

# ---------- 1. 检查环境 ----------
Write-Step 1 4 "检查环境"
Show-Gpu
New-ProjectDirs
Write-Done "输出目录：$OUTPUT_DIR"

# ---------- 2. 查询最新版本 ----------
Write-Step 2 4 "查询 GitHub 最新发行版"
$ghHeaders = @{ 'User-Agent' = 'video-upscale-deploy' }
# 有 GITHUB_TOKEN 环境变量就带上，避免匿名 API 限流（60次/小时）
if ($env:GITHUB_TOKEN) { $ghHeaders['Authorization'] = "token $env:GITHUB_TOKEN" }
$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/k4yt3x/video2x/releases/latest' `
                             -Headers $ghHeaders
$tag = $release.tag_name
$asset = $release.assets | Where-Object { $_.name -like 'video2x-windows-amd64*.zip' } | Select-Object -First 1
if (-not $asset) { throw "在 $tag 里没找到 Windows 压缩包，请手动到 https://github.com/k4yt3x/video2x/releases 下载" }
Write-Done "最新版本：$tag（$([math]::Round($asset.size/1MB,1)) MB）"

# ---------- 3. 下载并解压 ----------
Write-Step 3 4 "下载并解压到 $VIDEO2X_DIR"
New-Item -ItemType Directory -Path $VIDEO2X_DIR -Force | Out-Null
$zip = Join-Path $env:TEMP $asset.name

if (-not (Test-Path $zip)) {
  Write-Detail "下载中（GitHub 直连较慢时请开代理，或到 releases 页用镜像）..."
  Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -UseBasicParsing
}
Write-Done "已下载：$zip"

Expand-Archive -Path $zip -DestinationPath $VIDEO2X_DIR -Force
Write-Done "已解压到 $VIDEO2X_DIR"

# ---------- 4. 定位可执行文件并自检 ----------
Write-Step 4 4 "定位 video2x.exe 并自检"
$exe = Get-ChildItem $VIDEO2X_DIR -Recurse -Filter 'video2x.exe' -ErrorAction SilentlyContinue |
       Select-Object -First 1
if (-not $exe) { throw "解压后没找到 video2x.exe，请检查 $VIDEO2X_DIR" }
Write-Done "可执行文件：$($exe.FullName)"

& $exe.FullName --version
Write-Host ""
Write-Host "已识别的 Vulkan 设备（显卡）：" -ForegroundColor Gray
# 6.4.0 里列设备是 --list-devices/-l（不是 --list-gpus），选设备是 --device/-d
& $exe.FullName --list-devices
if ($LASTEXITCODE -ne 0) {
  Write-Note '列设备失败。Video2X 靠 Vulkan 跑推理，请确认显卡驱动是较新的版本。'
}

Write-Host ""
Write-Host "安装完成。放大视频：" -ForegroundColor Green
Write-Host "  powershell -File `"$PSScriptRoot\批量放大.ps1`" -InputPath `"$INPUT_DIR`" -Scale 2" -ForegroundColor Gray