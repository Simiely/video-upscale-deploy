<#
  00-ComfyUI底座\启动ComfyUI.ps1
  作用：用底座虚拟环境启动 ComfyUI，并自动打开浏览器。
        方案二(FlashVSR)与方案三(SeedVR2)的图形界面都从这里进。
#>

param(
  [int]$Port = 8188,
  [switch]$ListenAll,             # 需要局域网其它机器访问时加上
  [string]$OutputDirectory = ''   # 成品落点；留空则跟随 common.ps1 的 UPSCALE_IO\output
)

. "$PSScriptRoot\..\common.ps1"

Assert-ComfyReady

if (-not $OutputDirectory) { $OutputDirectory = $OUTPUT_DIR }

$cliArgs = @((Join-Path $COMFY_DIR 'main.py'), '--port', $Port)
if ($ListenAll) { $cliArgs += @('--listen', '0.0.0.0') } else { $cliArgs += @('--listen', '127.0.0.1') }
if ($OutputDirectory) {
  if (-not (Test-Path $OutputDirectory)) { New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null }
  $cliArgs += @('--output-directory', $OutputDirectory)
}

Write-Host "启动 ComfyUI ..." -ForegroundColor Cyan
Write-Host "成品输出目录：$OutputDirectory" -ForegroundColor DarkGray
Write-Detail "$COMFY_PY $($cliArgs -join ' ')"
Start-Job -ScriptBlock { Start-Sleep -Seconds 12; Start-Process "http://127.0.0.1:$using:Port" } | Out-Null

Push-Location $COMFY_DIR
try { & $COMFY_PY @cliArgs } finally { Pop-Location }