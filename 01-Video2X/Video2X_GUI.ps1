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
$txtLog = New-Object System.Windows.Forms.TextBox
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
  $txtLog.AppendText("$Msg`r`n")
  $txtLog.ScrollToCaret()
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

$btnStart.Add_Click({
  if ($script:isRunning) {
    # 停止逻辑在 job 层面处理，这里只是提示
    $lblStatus.Text = "处理中无法取消（请等待完成）"
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

  $script:isRunning = $true
  $btnStart.Text = "处理中..."
  $btnStart.Enabled = $false
  $progBar.Value = 0
  $txtLog.Clear()

  Add-Log "输入：$inputPath"
  Add-Log "处理器：$processor / $model"
  Add-Log "共 $($files.Count) 个文件"
  Add-Log "---"
  $lblStatus.Text = "准备中..."

  $filePaths = $files.FullName

  $job = Start-Job -ScriptBlock {
    param($exe, $filePaths, $outDir, $processor, $model, $scale, $w, $h,
          $gpu, $crfVal, $overwriteFlag)

    $results = @()
    $idx = 0
    foreach ($f in $filePaths) {
      $idx++
      $fi = Get-Item $f
      $base = [IO.Path]::GetFileNameWithoutExtension($fi.Name)

      if ($processor -eq 'rife') { $suffix = "_${scale}xfps" }
      elseif ($processor -eq 'libplacebo') { $suffix = "_$($w)x$h" }
      else { $suffix = "_${scale}x" }
      $outFile = Join-Path $outDir "$base$suffix.mp4"

      $r = @{
        Index = $idx
        Total = $filePaths.Count
        Name = $fi.Name
        OutFile = $outFile
        Skipped = $false
        Success = $false
        SizeMB = 0
        Error = ""
      }

      if ((Test-Path $outFile) -and -not $overwriteFlag) {
        $r.Skipped = $true
        $r.Success = $true
        $results += $r
        continue
      }

      $args = @('-i', $f, '-o', $outFile, '-p', $processor,
                '-c', 'libx264', '-e', "crf=$crfVal", '-e', 'preset=slow',
                '-d', $gpu, '--no-progress')
      switch ($processor) {
        'realesrgan' { $args += @('-s', $scale, '--realesrgan-model', $model) }
        'realcugan'  { $args += @('-s', $scale, '--realcugan-model', $model) }
        'libplacebo' { $args += @('-w', $w, '-h', $h, '--libplacebo-shader', $model) }
        'rife'       { $args += @('-m', $scale, '--rife-model', $model) }
      }

      $null = & $exe @args 2>&1
      $fileOk = (Test-Path $outFile) -and ((Get-Item $outFile).Length -gt 0)
      $r.Success = $fileOk
      if ($fileOk) { $r.SizeMB = [math]::Round((Get-Item $outFile).Length / 1MB, 1) }
      else { $r.Error = "处理失败" }
      $results += $r
    }
    return $results
  } -ArgumentList $script:exePath, $filePaths, $outDir, $processor, $model,
                   $scaleVal, $width, $height, $gpuIdx, $crf, $overwrite

  $timer = New-Object System.Windows.Forms.Timer
  $timer.Interval = 800
  $timer.Add_Tick({
    if ($job.State -eq 'Completed' -or $job.State -eq 'Failed') {
      $timer.Stop()
      $results = Receive-Job -Job $job
      Remove-Job -Job $job -Force

      $ok = 0; $skip = 0; $fail = 0
      foreach ($r in $results) {
        if ($r.Skipped) {
          $skip++
          Add-Log "[$($r.Index)/$($r.Total)] 跳过：$($r.Name)"
        } elseif ($r.Success) {
          $ok++
          Add-Log "[$($r.Index)/$($r.Total)] 完成：$($r.Name)（$($r.SizeMB) MB）"
        } else {
          $fail++
          Add-Log "[$($r.Index)/$($r.Total)] 失败：$($r.Name) - $($r.Error)"
        }
      }

      $progBar.Value = 100
      $lblStatus.Text = "完成：成功 $ok / 跳过 $skip / 失败 $fail"
      Add-Log "---"
      Add-Log "全部结束：成功 $ok / 跳过 $skip / 失败 $fail"
      Add-Log "输出目录：$outDir"

      $script:isRunning = $false
      $btnStart.Text = "▶  开始放大"
      $btnStart.Enabled = $true

      if ($fail -eq 0 -and ($ok + $skip) -gt 0) {
        $res = [System.Windows.Forms.MessageBox]::Show(
          "处理完成！成功 $ok，跳过 $skip`n是否打开输出目录？",
          "完成", "YesNo", "Question")
        if ($res -eq "Yes") { explorer $outDir }
      }
    } else {
      # 渐进式进度
      if ($progBar.Value -lt 90) {
        $progBar.Value = $progBar.Value + 1
      }
      $lblStatus.Text = "处理中...（请稍候）"
    }
  })
  $timer.Start()
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
