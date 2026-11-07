#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Root = '',
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# ── 二次元皮肤调色板（与 anime_theme.py 的 C 类一致）──────────────────────
$script:INK    = [System.Drawing.Color]::FromArgb(13, 5, 24)
$script:BG     = [System.Drawing.Color]::FromArgb(23, 10, 40)
$script:CARD   = [System.Drawing.Color]::FromArgb(42, 18, 80)
$script:PINK   = [System.Drawing.Color]::FromArgb(255, 61, 154)
$script:PINKHI = [System.Drawing.Color]::FromArgb(255, 154, 208)
$script:CYAN   = [System.Drawing.Color]::FromArgb(34, 224, 230)
$script:YELLOW = [System.Drawing.Color]::FromArgb(255, 225, 77)
$script:PURPLE = [System.Drawing.Color]::FromArgb(155, 92, 255)
$script:TEXT   = [System.Drawing.Color]::FromArgb(255, 255, 255)
$script:DIM    = [System.Drawing.Color]::FromArgb(203, 185, 236)
$script:LOGBG  = [System.Drawing.Color]::FromArgb(16, 6, 32)
$script:LOGFG  = [System.Drawing.Color]::FromArgb(127, 245, 255)
$script:HDR1   = [System.Drawing.Color]::FromArgb(23, 10, 40)
$script:HDR2   = [System.Drawing.Color]::FromArgb(138, 26, 146)
$script:HDR3   = [System.Drawing.Color]::FromArgb(255, 61, 154)

# 让 WinForms 按真实像素渲染（125% 缩放下字体和描边不发虚）
try {
    Add-Type -Namespace Audio2Phira -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();'
    [void][Audio2Phira.Dpi]::SetProcessDPIAware()
    $script:dpiScale = 1.0
    $probe = [System.Drawing.Graphics]::FromHwnd([System.IntPtr]::Zero)
    $script:dpiScale = [double]$probe.DpiX / 96.0
    $probe.Dispose()
} catch { $script:dpiScale = 1.0 }
if ($script:dpiScale -le 0) { $script:dpiScale = 1.0 }
function Px([double]$Value) { return [int][math]::Round($Value * $script:dpiScale) }
function Sz([double]$w, [double]$h) { return [System.Drawing.Size]::new([int](Px $w), [int](Px $h)) }
function Pd([double]$l, [double]$t, [double]$r, [double]$b) { return [System.Windows.Forms.Padding]::new([int](Px $l), [int](Px $t), [int](Px $r), [int](Px $b)) }

if ([string]::IsNullOrWhiteSpace($Root)) { $Root = $PSScriptRoot }
$script:projectRoot = [System.IO.Path]::GetFullPath($Root)
$script:logDirectory = Join-Path $script:projectRoot '.setup\logs'
$script:worker = $null
$script:verified = $false
$script:streams = @()
$script:copyTasks = @()
$script:readers = @()
$script:decoders = @()

function Quote-ProcessArgument([string]$Value) {
    # Windows command-line quoting, including trailing backslashes.
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Audio2Phira · 一键环境安装'
$form.ClientSize = Sz 900 712
$form.MinimumSize = Sz 800 640
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10)
$form.AutoScaleMode = 'Dpi'
$form.BackColor = $script:BG
$form.ForeColor = $script:TEXT

# 窗口 / 任务栏图标用项目里的小恶魔头像
$script:bannerIcon = $null
$icoPath = Join-Path $script:projectRoot '.desktop\app.ico'
$pngPath = Join-Path $script:projectRoot '.desktop\app.png'
if (Test-Path -LiteralPath $icoPath) {
    try { $form.Icon = New-Object System.Drawing.Icon($icoPath) } catch { }
}
if (Test-Path -LiteralPath $pngPath) {
    try { $script:bannerIcon = [System.Drawing.Image]::FromFile($pngPath) } catch { }
}

$layout = New-Object System.Windows.Forms.TableLayoutPanel
$layout.Dock = 'Fill'
$layout.Padding = Pd 16 16 16 16
$layout.ColumnCount = 1
$layout.RowCount = 7
$layout.BackColor = $script:BG
@((Px 108), (Px 80), (Px 36), (Px 48), (Px 46)) | ForEach-Object {
    [void]$layout.RowStyles.Add([System.Windows.Forms.RowStyle]::new([System.Windows.Forms.SizeType]::Absolute, [int]$_))
}
[void]$layout.RowStyles.Add([System.Windows.Forms.RowStyle]::new([System.Windows.Forms.SizeType]::Percent, 100))
[void]$layout.RowStyles.Add([System.Windows.Forms.RowStyle]::new([System.Windows.Forms.SizeType]::Absolute, [int](Px 46)))
$form.Controls.Add($layout)

# ── 自绘头图：渐变 + 斜条纹 + 描边标题 + 角色图标 ─────────────────────
$banner = New-Object System.Windows.Forms.Panel
$banner.Dock = 'Fill'
$banner.BackColor = $script:HDR1
$banner.Margin = Pd 0 0 0 10
$banner.Add_Paint({
    param($sender, $paintArgs)
    $g = $paintArgs.Graphics
    if ($null -eq $g) { return }
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $bw = $sender.Width
    $bh = $sender.Height
    if ($bw -le 0 -or $bh -le 0) { return }

    $rect = New-Object System.Drawing.Rectangle(0, 0, $bw, $bh)
    $grad = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rect, $script:HDR1, $script:HDR3, 0)
    $blend = New-Object System.Drawing.Drawing2D.ColorBlend(3)
    $blend.Colors = @($script:HDR1, $script:HDR2, $script:HDR3)
    $blend.Positions = @(0.0, 0.55, 1.0)
    $grad.InterpolationColors = $blend
    $g.FillRectangle($grad, $rect)
    $grad.Dispose()

    # 斜条纹警戒带
    $stripe = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(30, 255, 225, 77))
    $sx = -($bw * 0.12)
    while ($sx -lt $bw) {
        $pts = @(
            [System.Drawing.Point]::new([int]$sx, [int]$bh),
            [System.Drawing.Point]::new([int]($sx + (Px 14)), [int]$bh),
            [System.Drawing.Point]::new([int]($sx + (Px 38)), 0),
            [System.Drawing.Point]::new([int]($sx + (Px 24)), 0)
        )
        $g.FillPolygon($stripe, $pts)
        $sx += (Px 60)
    }
    $stripe.Dispose()

    # 底部霓虹线
    $line1 = New-Object System.Drawing.SolidBrush($script:YELLOW)
    $g.FillRectangle($line1, 0, $bh - (Px 4), $bw, (Px 2))
    $line1.Dispose()
    $line2 = New-Object System.Drawing.SolidBrush($script:INK)
    $g.FillRectangle($line2, 0, $bh - (Px 2), $bw, (Px 2))
    $line2.Dispose()

    # 左侧竖色条
    $barPink = New-Object System.Drawing.SolidBrush($script:PINK)
    $g.FillRectangle($barPink, 0, 0, (Px 6), $bh)
    $barPink.Dispose()
    $barInk = New-Object System.Drawing.SolidBrush($script:INK)
    $g.FillRectangle($barInk, (Px 6), 0, (Px 2), $bh)
    $barInk.Dispose()

    # 小徽标
    $badgeFont = New-Object System.Drawing.Font('Consolas', 7.5, [System.Drawing.FontStyle]::Bold)
    $badgeBrush = New-Object System.Drawing.SolidBrush($script:YELLOW)
    $g.DrawString('MUSE POP · SETUP', $badgeFont, $badgeBrush, (Px 26), (Px 6))
    $badgeBrush.Dispose()

    # 描边主标题
    $titleFont = New-Object System.Drawing.Font('Microsoft YaHei UI', 19, [System.Drawing.FontStyle]::Bold)
    $titleText = 'Audio2Phira 环境安装'
    $inkBrush = New-Object System.Drawing.SolidBrush($script:INK)
    for ($dx = -2; $dx -le 2; $dx++) {
        for ($dy = -2; $dy -le 2; $dy++) {
            if ($dx -eq 0 -and $dy -eq 0) { continue }
            $g.DrawString($titleText, $titleFont, $inkBrush, (Px 24) + $dx, (Px 26) + $dy)
        }
    }
    $whiteBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $g.DrawString($titleText, $titleFont, $whiteBrush, (Px 24), (Px 26))
    $whiteBrush.Dispose()
    $inkBrush.Dispose()

    # 副标题
    $subFont = New-Object System.Drawing.Font('Microsoft YaHei UI', 9)
    $subBrush = New-Object System.Drawing.SolidBrush($script:DIM)
    $g.DrawString('Python 3.12 × 制谱依赖 × 本地环境', $subFont, $subBrush, (Px 26), (Px 68))
    $subBrush.Dispose()

    # 右侧角色头像
    if ($null -ne $script:bannerIcon) {
        $side = (Px 84)
        $g.DrawImage($script:bannerIcon, ($bw - $side - (Px 18)), [int](($bh - $side) / 2), $side, $side)
    }
})
$layout.Controls.Add($banner, 0, 0)

$intro = New-Object System.Windows.Forms.Label
$intro.Dock = 'Fill'
$intro.BackColor = $script:BG
$intro.ForeColor = $script:DIM
$intro.Text = "准备 Python 3.12（64 位）及制谱依赖，默认无需管理员权限。`r`n首次安装通常需要联网；缓存完整时可使用离线模式。本工具不安装 Phira。`r`n普通安装会复用健康环境。开始前请关闭 Audio2Phira，安装期间请保持此窗口开启。"
$layout.Controls.Add($intro, 0, 1)

$options = New-Object System.Windows.Forms.FlowLayoutPanel
$options.Dock = 'Fill'
$options.BackColor = $script:BG
$options.WrapContents = $false
$offline = New-Object System.Windows.Forms.CheckBox
$offline.Text = '离线模式'
$offline.AutoSize = $true
$offline.BackColor = $script:BG
$offline.ForeColor = $script:CYAN
$offline.FlatStyle = 'Flat'
$offline.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10, [System.Drawing.FontStyle]::Bold)
$offline.Margin = New-Object System.Windows.Forms.Padding(0, 3, 24, 0)
$repair = New-Object System.Windows.Forms.CheckBox
$repair.Text = '强制重建环境（先备份旧 .venv）'
$repair.AutoSize = $true
$repair.BackColor = $script:BG
$repair.ForeColor = $script:PINKHI
$repair.FlatStyle = 'Flat'
$repair.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10, [System.Drawing.FontStyle]::Bold)
$repair.Checked = $false
$options.Controls.AddRange(@($offline, $repair))
$layout.Controls.Add($options, 0, 2)

$actions = New-Object System.Windows.Forms.FlowLayoutPanel
$actions.Dock = 'Fill'
$actions.BackColor = $script:BG
$install = New-Object System.Windows.Forms.Button
$install.Text = '安装 / 修复环境'
$install.Size = Sz 220 38
$install.BackColor = $script:PINK
$install.ForeColor = $script:INK
$install.FlatStyle = 'Flat'
$install.FlatAppearance.BorderSize = 3
$install.FlatAppearance.BorderColor = $script:INK
$install.FlatAppearance.MouseOverBackColor = $script:PINKHI
$install.FlatAppearance.MouseDownBackColor = $script:YELLOW
$install.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 11, [System.Drawing.FontStyle]::Bold)
$install.Margin = Pd 0 3 12 0
$check = New-Object System.Windows.Forms.Button
$check.Text = '检查环境'
$check.Size = Sz 150 38
$check.BackColor = $script:PURPLE
$check.ForeColor = [System.Drawing.Color]::White
$check.FlatStyle = 'Flat'
$check.FlatAppearance.BorderSize = 3
$check.FlatAppearance.BorderColor = $script:INK
$check.FlatAppearance.MouseOverBackColor = $script:PINK
$check.FlatAppearance.MouseDownBackColor = $script:CYAN
$check.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10, [System.Drawing.FontStyle]::Bold)
$check.Margin = Pd 0 3 0 0
$actions.Controls.AddRange(@($install, $check))
$layout.Controls.Add($actions, 0, 3)

$status = New-Object System.Windows.Forms.Label
$status.Text = '尚未检查。选择选项后点击按钮开始；打开界面不会下载或安装。'
$status.Dock = 'Fill'
$status.TextAlign = 'MiddleLeft'
$status.BackColor = $script:CARD
$status.ForeColor = $script:YELLOW
$status.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 10, [System.Drawing.FontStyle]::Bold)
$status.Padding = Pd 14 0 14 0
$layout.Controls.Add($status, 0, 4)

$log = New-Object System.Windows.Forms.RichTextBox
$log.Dock = 'Fill'
$log.ReadOnly = $true
$log.WordWrap = $false
$log.BorderStyle = 'None'
$log.BackColor = $script:LOGBG
$log.ForeColor = $script:LOGFG
$log.Font = New-Object System.Drawing.Font('Consolas', 10)
$log.DetectUrls = $false
$layout.Controls.Add($log, 0, 5)

$footer = New-Object System.Windows.Forms.FlowLayoutPanel
$footer.Dock = 'Fill'
$footer.BackColor = $script:BG
$footer.Padding = Pd 0 6 0 0
$openApp = New-Object System.Windows.Forms.Button
$openApp.Text = '打开 Audio2Phira'
$openApp.Size = Sz 175 32
$openApp.Enabled = $false
$openApp.BackColor = $script:CYAN
$openApp.ForeColor = $script:INK
$openApp.FlatStyle = 'Flat'
$openApp.FlatAppearance.BorderSize = 2
$openApp.FlatAppearance.BorderColor = $script:INK
$openApp.FlatAppearance.MouseOverBackColor = $script:YELLOW
$openApp.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9.5, [System.Drawing.FontStyle]::Bold)
$openLogs = New-Object System.Windows.Forms.Button
$openLogs.Text = '打开日志目录'
$openLogs.Size = Sz 150 32
$openLogs.BackColor = $script:CARD
$openLogs.ForeColor = $script:CYAN
$openLogs.FlatStyle = 'Flat'
$openLogs.FlatAppearance.BorderSize = 2
$openLogs.FlatAppearance.BorderColor = $script:CYAN
$openLogs.FlatAppearance.MouseOverBackColor = $script:PURPLE
$openLogs.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9.5, [System.Drawing.FontStyle]::Bold)
$close = New-Object System.Windows.Forms.Button
$close.Text = '关闭'
$close.Size = Sz 100 32
$close.BackColor = $script:CARD
$close.ForeColor = $script:TEXT
$close.FlatStyle = 'Flat'
$close.FlatAppearance.BorderSize = 2
$close.FlatAppearance.BorderColor = $script:INK
$close.FlatAppearance.MouseOverBackColor = $script:PINK
$close.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9.5)
$footer.Controls.AddRange(@($openApp, $openLogs, $close))
$layout.Controls.Add($footer, 0, 6)

# 深色标题栏（Win10 1809+ / Win11）
try {
    Add-Type -Namespace Audio2Phira -Name Dwm -MemberDefinition '[DllImport("dwmapi.dll")] public static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);'
    $hwnd = $form.Handle
    $on = 1
    [void][Audio2Phira.Dwm]::DwmSetWindowAttribute($hwnd, 20, [ref]$on, 4)
    [void][Audio2Phira.Dwm]::DwmSetWindowAttribute($hwnd, 19, [ref]$on, 4)
    $caption = 0x00280A17
    [void][Audio2Phira.Dwm]::DwmSetWindowAttribute($hwnd, 35, [ref]$caption, 4)
    $captionText = 0x0029B9CB
    [void][Audio2Phira.Dwm]::DwmSetWindowAttribute($hwnd, 36, [ref]$captionText, 4)
} catch { }

# 日志框滚动条也走深色主题
$form.Add_Shown({
    try {
        Add-Type -Namespace Audio2Phira -Name Theme -MemberDefinition '[DllImport("uxtheme.dll", CharSet=CharSet.Unicode)] public static extern int SetWindowTheme(IntPtr hWnd, string pszSubAppName, string pszSubIdList);'
        [void][Audio2Phira.Theme]::SetWindowTheme($log.Handle, 'DarkMode_Explorer', $null)
    } catch { }
})

function Write-GuiLog([string]$Text) {
    $log.AppendText($Text)
    $log.SelectionStart = $log.TextLength
    $log.ScrollToCaret()
}

function Read-WorkerLogs {
    for ($index = 0; $index -lt $script:readers.Count; $index++) {
        $reader = $script:readers[$index]
        $bytes = New-Object byte[] 16384
        # Bound work per timer tick so even a noisy installer cannot freeze the UI.
        for ($chunk = 0; $chunk -lt 16; $chunk++) {
            $count = $reader.Read($bytes, 0, $bytes.Length)
            if ($count -eq 0) { break }
            $chars = New-Object char[] 16384
            $charCount = $script:decoders[$index].GetChars($bytes, 0, $count, $chars, 0, $false)
            if ($charCount -gt 0) { Write-GuiLog (-join $chars[0..($charCount - 1)]) }
        }
    }
}

function Dispose-WorkerResources {
    foreach ($item in $script:readers) { $item.Dispose() }
    foreach ($item in $script:streams) { $item.Dispose() }
    if ($null -ne $script:worker) { $script:worker.Dispose() }
    $script:worker = $null
    $script:readers = @()
    $script:streams = @()
    $script:copyTasks = @()
    $script:decoders = @()
}

function Set-Working([bool]$Working) {
    $install.Enabled = -not $Working
    $check.Enabled = -not $Working
    $offline.Enabled = -not $Working
    $repair.Enabled = -not $Working
    $close.Enabled = -not $Working
    $openApp.Enabled = (-not $Working) -and $script:verified -and (Test-Path -LiteralPath (Join-Path $script:projectRoot '.venv\Scripts\pythonw.exe'))
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 200
$timer.Add_Tick({
    if ($null -eq $script:worker) { return }
    try {
        Read-WorkerLogs
        if (-not $script:worker.HasExited) { return }
        # CopyToAsync is native .NET I/O; no PowerShell scriptblock runs on a pool thread.
        foreach ($task in $script:copyTasks) { if (-not $task.IsCompleted) { return } }
        foreach ($stream in $script:streams) { $stream.Flush() }
        Read-WorkerLogs
        # Drain any remaining file content on later ticks rather than blocking the UI.
        foreach ($reader in $script:readers) { if ($reader.Position -lt $reader.Length) { return } }
        $code = $script:worker.ExitCode
        $copyFailed = @($script:copyTasks | Where-Object { $_.IsFaulted -or $_.IsCanceled }).Count -gt 0
        $script:verified = ($code -eq 0) -and (-not $copyFailed)
        if ($script:verified) {
            $status.Text = '操作成功（退出码 0）。环境可用后可打开 Audio2Phira。'
        } else {
            $status.Text = "操作失败（退出码 $code）。请查看日志，修正后重试。"
            if ($copyFailed) { Write-GuiLog "`r`n[界面] 日志写入失败，请检查磁盘空间和权限。`r`n" }
        }
        Write-GuiLog ("`r`n[界面] 进程已结束，退出码：{0}`r`n" -f $code)
        $timer.Stop()
        Dispose-WorkerResources
        Set-Working $false
    } catch {
        # Keep the worker alive, keep close disabled, and allow a later poll to recover.
        $status.Text = '读取日志遇到问题，安装进程继续运行：' + $_.Exception.Message
    }
})

function Start-EnvironmentTask([bool]$CheckOnly) {
    if ($null -ne $script:worker) { return }
    $engine = Join-Path $script:projectRoot 'install_environment.ps1'
    if (-not (Test-Path -LiteralPath $engine -PathType Leaf)) {
        [void][System.Windows.Forms.MessageBox]::Show($form, "缺少 install_environment.ps1。请将完整安装包解压到同一目录后重试。`r`n项目目录：$script:projectRoot", '安装文件不完整', 'OK', 'Error')
        return
    }
    if ((-not $CheckOnly) -and $repair.Checked) {
        $answer = [System.Windows.Forms.MessageBox]::Show($form, "强制重建前请关闭 Audio2Phira 及正在使用此环境的程序。`r`n安装器会先备份旧 .venv，再创建新环境，不直接删除旧环境。`r`n确认已关闭程序并继续？", '确认强制重建', 'YesNo', 'Warning', 'Button2')
        if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) { return }
    }
    try {
        $script:verified = $false
        Set-Working $true
        [void][System.IO.Directory]::CreateDirectory($script:logDirectory)
        $stamp = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
        $stdoutPath = Join-Path $script:logDirectory ($stamp + '.stdout.log')
        $stderrPath = Join-Path $script:logDirectory ($stamp + '.stderr.log')
        foreach ($path in @($stdoutPath, $stderrPath)) {
            $script:streams += New-Object System.IO.FileStream($path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite, 1, [System.IO.FileOptions]::Asynchronous)
            $script:readers += [System.IO.File]::Open($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $script:decoders += (New-Object System.Text.UTF8Encoding($false)).GetDecoder()
        }
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File ' + (Quote-ProcessArgument $engine) + ' -Root ' + (Quote-ProcessArgument $script:projectRoot)
        if ($CheckOnly) { $arguments += ' -CheckOnly' }
        if ($offline.Checked) { $arguments += ' -Offline' }
        # Check is always non-destructive, regardless of the repair checkbox.
        if ((-not $CheckOnly) -and $repair.Checked) { $arguments += ' -Repair' }
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = Join-Path $PSHOME 'powershell.exe'
        $info.Arguments = $arguments
        $info.WorkingDirectory = $script:projectRoot
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $info.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false)
        $info.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
        $info.EnvironmentVariables['PYTHONUTF8'] = '1'
        $info.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $info
        if (-not $process.Start()) { throw '无法启动安装进程。' }
        $script:worker = $process
        $script:copyTasks = @(
            $process.StandardOutput.BaseStream.CopyToAsync($script:streams[0]),
            $process.StandardError.BaseStream.CopyToAsync($script:streams[1])
        )
        Write-GuiLog ("`r`n[界面] 开始操作：{0}`r`nstdout: {1}`r`nstderr: {2}`r`n" -f $arguments, $stdoutPath, $stderrPath)
        $status.Text = '正在运行。请勿关闭窗口；日志实时显示，完成后会自动恢复按钮。'
        $timer.Start()
    } catch {
        if (($null -ne $script:worker) -and (-not $script:worker.HasExited)) {
            $status.Text = '日志初始化异常，进程仍在运行。请等待结束。'
            $timer.Start()
        } else {
            Dispose-WorkerResources
            Set-Working $false
            $status.Text = '无法开始操作：' + $_.Exception.Message
        }
        Write-GuiLog ("`r`n[界面错误] {0}`r`n" -f $_.Exception.Message)
    }
}

$install.Add_Click({ Start-EnvironmentTask $false })
$check.Add_Click({ Start-EnvironmentTask $true })
$close.Add_Click({ $form.Close() })
$openLogs.Add_Click({
    try {
        [void][System.IO.Directory]::CreateDirectory($script:logDirectory)
        Start-Process -FilePath 'explorer.exe' -ArgumentList (Quote-ProcessArgument $script:logDirectory)
    } catch { [void][System.Windows.Forms.MessageBox]::Show($form, $_.Exception.Message, '无法打开日志目录', 'OK', 'Error') }
})
$openApp.Add_Click({
    $pythonw = Join-Path $script:projectRoot '.venv\Scripts\pythonw.exe'
    $app = Join-Path $script:projectRoot 'desktop_app.py'
    if ((-not $script:verified) -or (-not (Test-Path -LiteralPath $pythonw -PathType Leaf))) { return }
    try {
        if (-not (Test-Path -LiteralPath $app -PathType Leaf)) { throw '缺少 desktop_app.py，请重新解压完整项目。' }
        Start-Process -FilePath $pythonw -ArgumentList ('-X utf8 ' + (Quote-ProcessArgument $app)) -WorkingDirectory $script:projectRoot
    } catch { [void][System.Windows.Forms.MessageBox]::Show($form, $_.Exception.Message, '无法打开 Audio2Phira', 'OK', 'Error') }
})
$form.Add_FormClosed({
    if ($null -ne $script:bannerIcon) { try { $script:bannerIcon.Dispose() } catch { } }
})
$form.Add_FormClosing({
    param($sender, $eventArgs)
    if ($null -ne $script:worker) {
        $eventArgs.Cancel = $true
        [void][System.Windows.Forms.MessageBox]::Show($form, '安装或检查仍在运行。为避免中断 Python 或依赖安装，请等待完成后再关闭。', '请等待操作完成', 'OK', 'Information')
    }
})

try {
    if ($SmokeTest) {
        $form.Show()
        $form.Update()
        [System.Windows.Forms.Application]::DoEvents()
        if ($null -ne $script:worker) { throw '冒烟测试不应启动安装进程。' }
        $form.Close()
        Write-Output 'INSTALLER_GUI_SMOKE_TEST_OK'
    } else {
        [void]$form.ShowDialog()
    }
} finally {
    $timer.Stop()
    $timer.Dispose()
    if ($null -eq $script:worker) { Dispose-WorkerResources }
    $form.Dispose()
}
