<#
  01-Video2X\Video2X_GUI.ps1
  作用：Video2X 图形界面（WinForms）。选文件/目录、选处理器、调参数、一键放大。
  用法：右键 -> 使用 PowerShell 运行，或：
        powershell -File .\01-Video2X\Video2X_GUI.ps1
#>

. "$PSScriptRoot\..\common.ps1"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ==================== 准备 ====================

$exe = Get-ChildItem $VIDEO2X_DIR -Recurse -Filter 'video2x.exe' -ErrorAction SilentlyContinue |
       Select-Object -First 1
if (-not $exe) {
  [System.Windows.Forms.MessageBox]::Show(
    "未找到 video2x.exe，请先运行 安装Video2X.ps1`n目录：$VIDEO2X_DIR",
    "错误", "OK", "Error") | Out-Null
  exit 1
}
$script:exePath = $exe.FullName

# 枚举 GPU
$gpuList = @()
$deviceOutput = & $script:exePath --list-devices 2>&1
foreach ($line in $deviceOutput) {
  if ($line -match '^(\d+)\.\s+(.+)$') {
    $gpuList += "$($matches[1]) - $($matches[2].Trim())"
  }
}
if ($gpuList.Count -eq 0) { $gpuList = @('0 - 自动') }

# 模型列表
$RealCuganModels = @('models-se', 'models-pro', 'models-nose')
$RealEsrganModels = @('realesr-animevideov3', 'realesrgan-plus', 'realesrgan-plus-anime')
$RifeModels = @('rife-v4.6', 'rife-v4.26', 'rife-v4.25', 'rife-v4', 'rife-v3.1', 'rife-v3.0',
                'rife-v2.4', 'rife-v2.3', 'rife-v2', 'rife', 'rife-HD', 'rife-UHD', 'rife-anime')
$Anime4kShaders = @('anime4k-v4-a+a', 'anime4k-v4-a', 'anime4k-v4-b+b', 'anime4k-v4-b',
                     'anime4k-v4-c+a', 'anime4k-v4-c', 'anime4k-v4.1-gan')

$fontNormal = [System.Drawing.Font]::new("Microsoft YaHei UI", 9)
$fontBold = [System.Drawing.Font]::new("Microsoft YaHei UI", 9, [System.Drawing.FontStyle]::Bold)
$fontTitle = [System.Drawing.Font]::new("Microsoft YaHei UI", 11, [System.Drawing.FontStyle]::Bold)
$fontMono = [System.Drawing.Font]::new("Consolas", 8)

# ==================== 主窗口 ====================

$form = New-Object System.Windows.Forms.Form
$form.Text = "Video2X 图形界面"
$form.Size = [System.Drawing.Size]::new(520, 600)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.BackColor = "#f5f5f5"

$y = 16
$rowH = 30
$lx = 16
$cx = 110
$cw = 370

function lineY { $script:y += $script:rowH }

# ---- 输入 ----
$lblInput = New-Object System.Windows.Forms.Label
$lblInput.Text = "输入："
$lblInput.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblInput.Size = [System.Drawing.Size]::new(90, 20)
$lblInput.Font = $fontNormal
$form.Controls.Add($lblInput)

$txtInput = New-Object System.Windows.Forms.TextBox
$txtInput.Location = [System.Drawing.Point]::new($cx, $y)
$txtInput.Size = [System.Drawing.Size]::new(260, 25)
$txtInput.Font = $fontNormal
$txtInput.Text = $INPUT_DIR
$form.Controls.Add($txtInput)

$btnFile = New-Object System.Windows.Forms.Button
$btnFile.Text = "选文件"
$btnFile.Location = [System.Drawing.Point]::new($cx + 265, $y)
$btnFile.Size = [System.Drawing.Size]::new(50, 25)
$btnFile.Font = $fontNormal
$btnFile.Add_Click({
  $dlg = New-Object System.Windows.Forms.OpenFileDialog
  $dlg.Filter = "视频文件|*.mp4;*.mkv;*.mov;*.avi;*.webm;*.m4v|所有文件|*.*"
  $dlg.Title = "选择视频文件"
  if ($dlg.ShowDialog() -eq "OK") { $txtInput.Text = $dlg.FileName }
})
$form.Controls.Add($btnFile)

lineY

$btnDir = New-Object System.Windows.Forms.Button
$btnDir.Text = "选择文件夹..."
$btnDir.Location = [System.Drawing.Point]::new($cx, $y)
$btnDir.Size = [System.Drawing.Size]::new(120, 25)
$btnDir.Font = $fontNormal
$btnDir.Add_Click({
  $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
  $dlg.Description = "选择包含视频的文件夹"
  if ($dlg.ShowDialog() -eq "OK") { $txtInput.Text = $dlg.SelectedPath }
})
$form.Controls.Add($btnDir)

lineY; lineY

# ---- 处理器 ----
$lblProc = New-Object System.Windows.Forms.Label
$lblProc.Text = "处理器："
$lblProc.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblProc.Size = [System.Drawing.Size]::new(90, 20)
$lblProc.Font = $fontNormal
$form.Controls.Add($lblProc)

$cboProcessor = New-Object System.Windows.Forms.ComboBox
$cboProcessor.Location = [System.Drawing.Point]::new($cx, $y)
$cboProcessor.Size = [System.Drawing.Size]::new($cw, 25)
$cboProcessor.DropDownStyle = "DropDownList"
$cboProcessor.Font = $fontNormal
$cboProcessor.Items.AddRange(@("Real-CUGAN (推荐，真人/通用)",
                                "Real-ESRGAN (细节更好，动漫)",
                                "Anime4K (最快，番剧着色器)",
                                "RIFE (补帧，视频变丝滑)"))
$cboProcessor.SelectedIndex = 0
$form.Controls.Add($cboProcessor)

lineY

# ---- 模型 ----
$lblModel = New-Object System.Windows.Forms.Label
$lblModel.Text = "模型："
$lblModel.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblModel.Size = [System.Drawing.Size]::new(90, 20)
$lblModel.Font = $fontNormal
$form.Controls.Add($lblModel)

$cboModel = New-Object System.Windows.Forms.ComboBox
$cboModel.Location = [System.Drawing.Point]::new($cx, $y)
$cboModel.Size = [System.Drawing.Size]::new($cw, 25)
$cboModel.DropDownStyle = "DropDownList"
$cboModel.Font = $fontNormal
$cboModel.Items.AddRange($RealCuganModels)
$cboModel.SelectedIndex = 0
$form.Controls.Add($cboModel)

lineY

# ---- 倍数/尺寸 ----
$lblScale = New-Object System.Windows.Forms.Label
$lblScale.Text = "倍数："
$lblScale.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblScale.Size = [System.Drawing.Size]::new(90, 20)
$lblScale.Font = $fontNormal
$form.Controls.Add($lblScale)

$cboScale = New-Object System.Windows.Forms.ComboBox
$cboScale.Location = [System.Drawing.Point]::new($cx, $y)
$cboScale.Size = [System.Drawing.Size]::new(130, 25)
$cboScale.DropDownStyle = "DropDownList"
$cboScale.Font = $fontNormal
$cboScale.Items.AddRange(@("2 倍", "3 倍", "4 倍"))
$cboScale.SelectedIndex = 0
$form.Controls.Add($cboScale)

# Anime4K 用宽高
$lblW = New-Object System.Windows.Forms.Label
$lblW.Text = "宽："
$lblW.Location = [System.Drawing.Point]::new($cx + 140, $y + 3)
$lblW.Size = [System.Drawing.Size]::new(25, 20)
$lblW.Font = $fontNormal
$lblW.Visible = $false
$form.Controls.Add($lblW)

$txtW = New-Object System.Windows.Forms.TextBox
$txtW.Location = [System.Drawing.Point]::new($cx + 165, $y)
$txtW.Size = [System.Drawing.Size]::new(80, 25)
$txtW.Font = $fontNormal
$txtW.Text = "1920"
$txtW.Visible = $false
$form.Controls.Add($txtW)

$lblH = New-Object System.Windows.Forms.Label
$lblH.Text = "高："
$lblH.Location = [System.Drawing.Point]::new($cx + 250, $y + 3)
$lblH.Size = [System.Drawing.Size]::new(25, 20)
$lblH.Font = $fontNormal
$lblH.Visible = $false
$form.Controls.Add($lblH)

$txtH = New-Object System.Windows.Forms.TextBox
$txtH.Location = [System.Drawing.Point]::new($cx + 275, $y)
$txtH.Size = [System.Drawing.Size]::new(80, 25)
$txtH.Font = $fontNormal
$txtH.Text = "1080"
$txtH.Visible = $false
$form.Controls.Add($txtH)

lineY

# ---- 画质 ----
$lblCrf = New-Object System.Windows.Forms.Label
$lblCrf.Text = "画质 CRF："
$lblCrf.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblCrf.Size = [System.Drawing.Size]::new(90, 20)
$lblCrf.Font = $fontNormal
$form.Controls.Add($lblCrf)

$trkCrf = New-Object System.Windows.Forms.TrackBar
$trkCrf.Location = [System.Drawing.Point]::new($cx, $y - 4)
$trkCrf.Size = [System.Drawing.Size]::new(280, 30)
$trkCrf.Minimum = 15
$trkCrf.Maximum = 28
$trkCrf.Value = 17
$trkCrf.TickFrequency = 1
$form.Controls.Add($trkCrf)

$lblCrfVal = New-Object System.Windows.Forms.Label
$lblCrfVal.Text = "17"
$lblCrfVal.Location = [System.Drawing.Point]::new($cx + 285, $y + 3)
$lblCrfVal.Size = [System.Drawing.Size]::new(25, 20)
$lblCrfVal.Font = $fontBold
$form.Controls.Add($lblCrfVal)

$lblCrfHint = New-Object System.Windows.Forms.Label
$lblCrfHint.Text = "（高质量）"
$lblCrfHint.Location = [System.Drawing.Point]::new($cx + 310, $y + 3)
$lblCrfHint.Size = [System.Drawing.Size]::new(60, 20)
$lblCrfHint.Font = $fontNormal
$lblCrfHint.ForeColor = "Gray"
$form.Controls.Add($lblCrfHint)

$trkCrf.Add_ValueChanged({
  $lblCrfVal.Text = $trkCrf.Value.ToString()
  if ($trkCrf.Value -le 17) { $lblCrfHint.Text = "（高质量）" }
  elseif ($trkCrf.Value -le 23) { $lblCrfHint.Text = "（平衡）" }
  else { $lblCrfHint.Text = "（体积小）" }
})

lineY; lineY

# ---- 显卡 ----
$lblGpu = New-Object System.Windows.Forms.Label
$lblGpu.Text = "显卡："
$lblGpu.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblGpu.Size = [System.Drawing.Size]::new(90, 20)
$lblGpu.Font = $fontNormal
$form.Controls.Add($lblGpu)

$cboGpu = New-Object System.Windows.Forms.ComboBox
$cboGpu.Location = [System.Drawing.Point]::new($cx, $y)
$cboGpu.Size = [System.Drawing.Size]::new($cw, 25)
$cboGpu.DropDownStyle = "DropDownList"
$cboGpu.Font = $fontNormal
$cboGpu.Items.AddRange($gpuList)
$cboGpu.SelectedIndex = 0
$form.Controls.Add($cboGpu)

lineY

# ---- 输出 ----
$lblOut = New-Object System.Windows.Forms.Label
$lblOut.Text = "输出到："
$lblOut.Location = [System.Drawing.Point]::new($lx, $y + 3)
$lblOut.Size = [System.Drawing.Size]::new(90, 20)
$lblOut.Font = $fontNormal
$form.Controls.Add($lblOut)

$txtOutput = New-Object System.Windows.Forms.TextBox
$txtOutput.Location = [System.Drawing.Point]::new($cx, $y)
$txtOutput.Size = [System.Drawing.Size]::new(260, 25)
$txtOutput.Font = $fontNormal
$txtOutput.Text = $OUTPUT_DIR
$form.Controls.Add($txtOutput)

$btnOut = New-Object System.Windows.Forms.Button
$btnOut.Text = "选..."
$btnOut.Location = [System.Drawing.Point]::new($cx + 265, $y)
$btnOut.Size = [System.Drawing.Size]::new(50, 25)
$btnOut.Font = $fontNormal
$btnOut.Add_Click({
  $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
  $dlg.Description = "选择输出目录"
  if ($dlg.ShowDialog() -eq "OK") { $txtOutput.Text = $dlg.SelectedPath }
})
$form.Controls.Add($btnOut)

lineY

# ---- 选项 ----
$chkOver = New-Object System.Windows.Forms.CheckBox
$chkOver.Text = "覆盖已存在的输出文件"
$chkOver.Location = [System.Drawing.Point]::new($cx, $y + 2)
$chkOver.Size = [System.Drawing.Size]::new(200, 20)
$chkOver.Font = $fontNormal
$form.Controls.Add($chkOver)

lineY; lineY

# ---- 开始按钮 ----
$btnStart = New-Object System.Windows.Forms.Button
$btnStart.Text = "▶  开始放大"
$btnStart.Location = [System.Drawing.Point]::new($lx, $y)
$btnStart.Size = [System.Drawing.Size]::new(472, 42)
$btnStart.Font = $fontTitle
$btnStart.BackColor = "#4CAF50"
$btnStart.ForeColor = "White"
$btnStart.FlatStyle = "Flat"
$form.Controls.Add($btnStart)

$y += 52

# ---- 进度条 ----
$progBar = New-Object System.Windows.Forms.ProgressBar
$progBar.Location = [System.Drawing.Point]::new($lx, $y)
$progBar.Size = [System.Drawing.Size]::new(472, 20)
$progBar.Style = "Continuous"
$form.Controls.Add($progBar)

$y += 24

# ---- 状态 ----
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "就绪"
$lblStatus.Location = [System.Drawing.Point]::new($lx, $y)
$lblStatus.Size = [System.Drawing.Size]::new(472, 20)
$lblStatus.Font = $fontNormal
$lblStatus.ForeColor = "Gray"
$form.Controls.Add($lblStatus)

$y += 22

# ---- 日志 ----
$script:txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Location = [System.Drawing.Point]::new($lx, $y)
$txtLog.Size = [System.Drawing.Size]::new(472, 120)
$txtLog.Multiline = $true
$txtLog.ScrollBars = "Vertical"
$txtLog.ReadOnly = $true
$txtLog.Font = $fontMono
$txtLog.BackColor = "#1e1e1e"
$txtLog.ForeColor = "#d4d4d4"
$form.Controls.Add($txtLog)

# ==================== 交互逻辑 ====================

function Add-Log {
  param([string]$Msg)
  $script:txtLog.AppendText("$Msg`r`n")
  $script:txtLog.ScrollToCaret()
}

# 处理器切换
$cboProcessor.Add_SelectedIndexChanged({
  $idx = $cboProcessor.SelectedIndex
  $cboModel.Items.Clear()

  switch ($idx) {
    0 { # Real-CUGAN
      $cboModel.Items.AddRange($RealCuganModels)
      $cboModel.SelectedIndex = 0
      $lblScale.Text = "倍数："
      $cboScale.Items.Clear()
      $cboScale.Items.AddRange(@("2 倍", "3 倍", "4 倍"))
      $cboScale.SelectedIndex = 0
      $cboScale.Visible = $true
      $lblW.Visible = $false; $txtW.Visible = $false
      $lblH.Visible = $false; $txtH.Visible = $false
    }
    1 { # Real-ESRGAN
      $cboModel.Items.AddRange($RealEsrganModels)
      $cboModel.SelectedIndex = 0
      $lblScale.Text = "倍数："
      $cboScale.Items.Clear()
      $cboScale.Items.AddRange(@("2 倍", "3 倍", "4 倍"))
      $cboScale.SelectedIndex = 2
      $cboScale.Visible = $true
      $lblW.Visible = $false; $txtW.Visible = $false
      $lblH.Visible = $false; $txtH.Visible = $false
    }
    2 { # Anime4K
      $cboModel.Items.AddRange($Anime4kShaders)
      $cboModel.SelectedIndex = 0
      $lblScale.Text = ""
      $cboScale.Visible = $false
      $lblW.Visible = $true; $txtW.Visible = $true
      $lblH.Visible = $true; $txtH.Visible = $true
    }
    3 { # RIFE
      $cboModel.Items.AddRange($RifeModels)
      $cboModel.SelectedIndex = 0
      $lblScale.Text = "帧率倍数："
      $cboScale.Items.Clear()
      $cboScale.Items.AddRange(@("2 倍", "3 倍", "4 倍"))
      $cboScale.SelectedIndex = 0
      $cboScale.Visible = $true
      $lblW.Visible = $false; $txtW.Visible = $false
      $lblH.Visible = $false; $txtH.Visible = $false
    }
  }
})

# 模型切换时调整可用倍数
$cboModel.Add_SelectedIndexChanged({
  $procIdx = $cboProcessor.SelectedIndex
  if ($procIdx -eq 1 -and $cboModel.SelectedItem) {
    $m = $cboModel.SelectedItem.ToString()
    $cboScale.Items.Clear()
    if ($m -eq 'realesr-animevideov3') {
      $cboScale.Items.AddRange(@("2 倍", "3 倍", "4 倍"))
      $cboScale.SelectedIndex = 2
    } else {
      $cboScale.Items.Add("4 倍")
      $cboScale.SelectedIndex = 0
    }
  }
  if ($procIdx -eq 0 -and $cboModel.SelectedItem) {
    $m = $cboModel.SelectedItem.ToString()
    $prev = $cboScale.SelectedIndex
    $cboScale.Items.Clear()
    if ($m -eq 'models-se') {
      $cboScale.Items.AddRange(@("2 倍", "3 倍", "4 倍"))
      $cboScale.SelectedIndex = [Math]::Min($prev, 2)
    } elseif ($m -eq 'models-pro') {
      $cboScale.Items.AddRange(@("2 倍", "3 倍"))
      $cboScale.SelectedIndex = [Math]::Min($prev, 1)
    } else {
      $cboScale.Items.Add("2 倍")
      $cboScale.SelectedIndex = 0
    }
  }
})

# ==================== 开始处理 ====================

$script:isRunning = $false
$script:guiTimer = [System.Windows.Forms.Timer]::new()
$script:guiTimer.Interval = 500

# 处理队列状态
$script:procFiles = @()      # 待处理文件列表
$script:procIndex = 0        # 当前处理到第几个
$script:procTotal = 0        # 总文件数
$script:procOutDir = ""      # 输出目录
$script:procArgs = @{}       # 当前处理参数
$script:procCurrentFile = "" # 当前文件名
$script:procOutFile = ""     # 当前输出文件路径
$script:procProcess = $null  # 当前 video2x 进程
$script:procOk = 0
$script:procSkip = 0
$script:procFail = 0

function Build-ArgList {
  param([string]$InFile, [string]$OutFile)
  $p = $script:procArgs
  $a = @('-i', "`"$InFile`"", '-o', "`"$OutFile`"", '-p', $p.Processor,
        '-c', 'libx264', '-e', 'crf=' + $p.Crf, '-e', 'preset=slow',
        '-d', $p.Gpu, '--no-progress')
  switch ($p.Processor) {
    'realesrgan' { $a += @('-s', $p.Scale, '--realesrgan-model', $p.Model) }
    'realcugan'  { $a += @('-s', $p.Scale, '--realcugan-model', $p.Model) }
    'libplacebo' { $a += @('-w', $p.Width, '-h', $p.Height, '--libplacebo-shader', $p.Model) }
    'rife'       { $a += @('-m', $p.Scale, '--rife-model', $p.Model) }
  }
  return ($a -join ' ')
}

function Start-NextFile {
  if ($script:procIndex -ge $script:procTotal) {
    # 全部处理完
    $script:guiTimer.Stop()
    $script:isRunning = $false
    $script:procProcess = $null
    $progBar.Value = 100
    $ok = $script:procOk; $skip = $script:procSkip; $fail = $script:procFail
    $lblStatus.Text = "完成：成功 $ok / 跳过 $skip / 失败 $fail"
    Add-Log "---"
    Add-Log "全部结束：成功 $ok / 跳过 $skip / 失败 $fail"
    Add-Log "输出目录：$script:procOutDir"
    $btnStart.Text = "▶  开始放大"
    $btnStart.Enabled = $true

    if ($fail -eq 0 -and ($ok + $skip) -gt 0) {
      $res = [System.Windows.Forms.MessageBox]::Show(
        "处理完成！成功 $ok，跳过 $skip`n是否打开输出目录？",
        "完成", "YesNo", "Question")
      if ($res -eq "Yes") { explorer $script:procOutDir }
    }
    return
  }

  $script:procIndex++
  $f = $script:procFiles[$script:procIndex - 1]
  $fi = Get-Item $f
  $base = [IO.Path]::GetFileNameWithoutExtension($fi.Name)
  $p = $script:procArgs

  if ($p.Processor -eq 'rife') { $suffix = "_$($p.Scale)xfps" }
  elseif ($p.Processor -eq 'libplacebo') { $suffix = "_$($p.Width)x$($p.Height)" }
  else { $suffix = "_$($p.Scale)x" }
  $outFile = Join-Path $script:procOutDir "$base$suffix.mp4"
  $script:procCurrentFile = $fi.Name
  $script:procOutFile = $outFile

  # 跳过已存在且有效的输出（小于 10KB 认为是损坏文件，重新处理）
  if ((Test-Path $outFile) -and -not $p.Overwrite) {
    $outSize = (Get-Item $outFile).Length
    if ($outSize -ge 10KB) {
      $script:procSkip++
      Add-Log "[$($script:procIndex)/$($script:procTotal)] 跳过：$($fi.Name)"
      # 更新进度条
      $pct = [int](($script:procIndex / $script:procTotal) * 100)
      $progBar.Value = [Math]::Min(100, [Math]::Max(1, $pct))
      $lblStatus.Text = "处理中... $($script:procIndex)/$($script:procTotal)"
      Start-NextFile
      return
    } else {
      Add-Log "[$($script:procIndex)/$($script:procTotal)] 输出文件损坏（$([math]::Round($outSize/1KB,1)) KB），重新处理：$($fi.Name)"
      Remove-Item $outFile -Force -ErrorAction SilentlyContinue
    }
  }

  Add-Log "[$($script:procIndex)/$($script:procTotal)] 处理：$($fi.Name)"
  $lblStatus.Text = "处理中... $($script:procIndex)/$($script:procTotal) - $($fi.Name)"

  # 启动 video2x 进程
  $argList = Build-ArgList -InFile $f -OutFile $outFile
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $script:exePath
  $psi.Arguments = $argList
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true

  $proc = [System.Diagnostics.Process]::new()
  $proc.StartInfo = $psi
  $proc.EnableRaisingEvents = $true
  $script:procProcess = $proc
  $proc.Start() | Out-Null
  $proc.BeginOutputReadLine()
  $proc.BeginErrorReadLine()
}

$btnStart.Add_Click({
  if ($script:isRunning) {
    return
  }

  $inputPath = $txtInput.Text.Trim()
  $outDir = $txtOutput.Text.Trim()
  if (-not $inputPath) {
    [System.Windows.Forms.MessageBox]::Show("请先选择输入文件或目录", "提示", "OK", "Warning") | Out-Null
    return
  }
  if (-not (Test-Path $inputPath)) {
    [System.Windows.Forms.MessageBox]::Show("输入路径不存在：`n$inputPath", "错误", "OK", "Error") | Out-Null
    return
  }
  if (-not $outDir) { $outDir = $OUTPUT_DIR }
  if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

  $procIdx = $cboProcessor.SelectedIndex
  $processor = @('realcugan', 'realesrgan', 'libplacebo', 'rife')[$procIdx]
  $model = $cboModel.SelectedItem.ToString()
  $gpuIdx = [int]($cboGpu.SelectedItem -split ' - ')[0]
  $crf = $trkCrf.Value
  $overwrite = $chkOver.Checked

  $scaleVal = [int](($cboScale.SelectedItem -split ' ')[0])
  $width = [int]$txtW.Text
  $height = [int]$txtH.Text

  $files = Get-VideoFiles -Path $inputPath
  if ($files.Count -eq 0) {
    [System.Windows.Forms.MessageBox]::Show("输入路径下没有找到视频文件", "提示", "OK", "Warning") | Out-Null
    return
  }

  # 初始化状态
  $script:isRunning = $true
  $script:procFiles = @($files.FullName)
  $script:procIndex = 0
  $script:procTotal = $files.Count
  $script:procOutDir = $outDir
  $script:procOk = 0
  $script:procSkip = 0
  $script:procFail = 0
  $script:procArgs = @{
    Processor = $processor
    Model = $model
    Scale = $scaleVal
    Width = $width
    Height = $height
    Gpu = $gpuIdx
    Crf = $crf
    Overwrite = $overwrite
  }

  $btnStart.Text = "处理中..."
  $btnStart.Enabled = $false
  $progBar.Value = 0
  $script:txtLog.Clear()

  Add-Log "输入：$inputPath"
  Add-Log "处理器：$processor / $model"
  Add-Log "共 $($files.Count) 个文件"
  Add-Log "---"
  $lblStatus.Text = "准备中..."

  $script:guiTimer.Start()
  Start-NextFile
})

# ---------- Timer 轮询进程状态 ----------
$script:guiTimer.Add_Tick({
  if (-not $script:isRunning) { return }
  $proc = $script:procProcess
  if ($proc -and -not $proc.HasExited) {
    # 还在跑，渐进式进度
    $basePct = [int](($script:procIndex - 1) / $script:procTotal * 100)
    $nextPct = [int]($script:procIndex / $script:procTotal * 100)
    $current = $progBar.Value
    $target = $nextPct - 3
    if ($current -lt $target) {
      $progBar.Value = $current + 1
    }
    return
  }

  # 当前文件处理完了
  if ($proc) {
    $name = $script:procCurrentFile
    $outFile = $script:procOutFile
    $fileOk = (Test-Path $outFile) -and ((Get-Item $outFile).Length -ge 10KB)
    if ($fileOk) {
      $script:procOk++
      $sz = [math]::Round((Get-Item $outFile).Length / 1MB, 1)
      Add-Log "[$($script:procIndex)/$($script:procTotal)] 完成：$name（$sz MB）"
    } else {
      $script:procFail++
      Add-Log "[$($script:procIndex)/$($script:procTotal)] 失败：$name"
    }
    try { $proc.Close() } catch {}
    $script:procProcess = $null
  }

  # 处理下一个
  Start-NextFile
})

# 关闭确认
$form.Add_FormClosing({
  if ($script:isRunning) {
    $res = [System.Windows.Forms.MessageBox]::Show(
      "正在处理中，确定要关闭吗？", "确认", "YesNo", "Warning")
    if ($res -ne "Yes") { $_.Cancel = $true }
  }
})

# 显示窗口
$form.ShowDialog() | Out-Null
