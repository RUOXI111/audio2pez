# ASCII source for Windows PowerShell 5.1. GUI provides Chinese guidance.
[CmdletBinding()]
param([switch]$CheckOnly,[switch]$Offline,[switch]$Repair,[string]$Root,[switch]$SkipShortcut)
if (-not $Root) { $Root=Split-Path -Parent $MyInvocation.MyCommand.Path }
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$OutputEncoding=[Console]::OutputEncoding
$env:PYTHONIOENCODING='utf-8';$env:PYTHONUTF8='1';$env:PIP_DISABLE_PIP_VERSION_CHECK='1'
$Root=(Resolve-Path -LiteralPath $Root).Path
$state=Join-Path $Root '.setup'
$logs=Join-Path $state 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$runId=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$script:counter=0
$script:backup=$null
$script:created=$false
$venv=Join-Path $Root '.venv'
$venvPy=Join-Path $venv 'Scripts\python.exe'
$mutex=$null;$held=$false
function Log([string]$Message) { Write-Output ((Get-Date -Format 'HH:mm:ss')+' '+$Message) }
function Q([string]$v) { return '"'+$v.Replace('"','"')+'"' }
function Run-Process([string]$File,[string[]]$Arguments,[int]$Timeout=300) {
    $script:counter++
    $prefix=Join-Path $logs ($runId+'-'+$script:counter)
    $stdout=$prefix+'.out.log';$stderr=$prefix+'.err.log'
    $quoted=($Arguments | ForEach-Object { Q $_ }) -join ' '
    $p=Start-Process -FilePath $File -ArgumentList $quoted -WorkingDirectory $Root -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    # Hold a process handle before Refresh/HasExited; PS5 can otherwise lose ExitCode.
    $nativeHandle=$p.Handle
    $watch=[Diagnostics.Stopwatch]::StartNew();$last=0
    while (-not $p.HasExited) {
        Start-Sleep -Milliseconds 250
        if ($watch.Elapsed.TotalSeconds -ge $Timeout) {
            & taskkill.exe /PID $p.Id /T /F | Out-Null
            throw ('Timed out after '+$Timeout+'s. Logs: '+$prefix)
        }
        if ($watch.Elapsed.TotalSeconds-$last -gt 10) {Log ('Working... '+[int]$watch.Elapsed.TotalSeconds+'s');$last=$watch.Elapsed.TotalSeconds}
        $p.Refresh()
    }
    $p.WaitForExit();$exit=$p.ExitCode
    if ($null -eq $exit) { throw ('Unable to read child exit status. Logs: '+$prefix) }
    foreach ($file in @($stdout,$stderr)) { if (Test-Path -LiteralPath $file) { Get-Content -LiteralPath $file -Encoding UTF8 | ForEach-Object { Write-Output $_ } } }
    $p.Dispose()
    $script:RunExit=[int]$exit
}
function Probe([string]$Exe) {
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) {return $null}
    $probeFile=Join-Path $state ('probe-'+[Guid]::NewGuid().ToString('N')+'.json')
    try {
        Run-Process $Exe @((Join-Path $Root 'setup_probe.py'),$probeFile) 20 | Out-Host
        if ($script:RunExit -eq 0 -and (Test-Path -LiteralPath $probeFile)) {
            $value=Get-Content -LiteralPath $probeFile -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($value.ok) { return $value }
        }
    } catch { Log ('Python probe failed: '+$Exe) | Out-Host }
    return $null
}
function Healthy([string]$Exe) {
    if (-not (Probe $Exe)) {return $false}
    Run-Process $Exe @((Join-Path $Root 'setup_dependencies.py'),'--root',$Root,'--check') 45 | Out-Host
    if ($script:RunExit -ne 0) {return $false}
    Run-Process $Exe @('-m','pip','check') 60 | Out-Host
    if ($script:RunExit -ne 0) {return $false}
    Run-Process $Exe @((Join-Path $Root 'setup_healthcheck.py')) 180 | Out-Host
    return ($script:RunExit -eq 0)
}
function Shortcut {
    if ($SkipShortcut) {Log 'Shortcut creation skipped.';return}
    $shell=New-Object -ComObject WScript.Shell
    $desktop=$shell.SpecialFolders.Item('Desktop')
    $icon=Join-Path $Root '.desktop\app.ico'
    # Point at the VBS launchers, never embed a non-ASCII path in Arguments:
    # .lnk Arguments with Chinese paths break on double-click (encoding), while
    # TargetPath is stored as Unicode and the VBS resolves paths relative to itself.
    $items=@(
        @{ Name='Audio2Phira 本地制谱.lnk'; Target=Join-Path $Root 'launch_desktop.vbs' },
        @{ Name='Audio2Phira 环境安装.lnk'; Target=Join-Path $Root 'Setup.vbs' }
    )
    foreach ($item in $items) {
        if (-not (Test-Path -LiteralPath $item.Target -PathType Leaf)) {Log ('Skip shortcut, launcher missing: '+$item.Target);continue}
        $path=Join-Path $desktop $item.Name
        $link=$shell.CreateShortcut($path)
        $link.TargetPath=$item.Target
        $link.Arguments=''
        $link.WorkingDirectory=$Root
        if (Test-Path -LiteralPath $icon) {$link.IconLocation=$icon}
        $link.Description='Audio2Phira local chart studio'
        $link.Save()
        Log ('Shortcut: '+$path)
    }
}
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {throw 'This installer requires x64 Windows.'}
    foreach ($required in @('desktop_app.py','anime_theme.py','desktop_worker.py','desktop_drums.py','setup_dependencies.py','setup_probe.py','setup_healthcheck.py','installer_wheels.lock.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $required))) {throw ('Missing application file: '+$required)}
    }
    $sha=[Security.Cryptography.SHA256]::Create()
    $key=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant())))).Replace('-','').Substring(0,20)
    $sha.Dispose()
    $mutex=New-Object Threading.Mutex($false,('Local\Audio2PhiraSetup_'+$key))
    try {$held=$mutex.WaitOne(0)} catch [Threading.AbandonedMutexException] {$held=$true}
    if (-not $held) {throw 'Another environment setup is already running for this folder.'}
    Log ('Project: '+$Root)
    if ($CheckOnly) {
        if (Healthy $venvPy) {Log 'CHECK_OK Environment is ready.';exit 0}
        throw 'Environment missing, incompatible, or unhealthy. Use Install / Repair.'
    }
    if (-not $Repair -and (Healthy $venvPy)) {
        Shortcut;Log 'SETUP_OK Existing environment reused; no packages changed.';exit 0
    }
    $running=@(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object {
        ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($venv,[StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.IndexOf((Join-Path $Root 'desktop_app.py'),[StringComparison]::OrdinalIgnoreCase) -ge 0)
    })
    if ($running.Count -gt 0) {throw 'Close Audio2Phira and all running generation tasks before repairing the environment.'}
    $candidates=New-Object 'System.Collections.Generic.List[string]'
    $current=Probe $venvPy
    if ($current) {$candidates.Add([string]$current.base)}
    $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Audio2Phira\Python312\python.exe'))
    $candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
    foreach ($reg in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath','HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
        if (Test-Path $reg) {$keyReg=Get-Item $reg;$loc=$keyReg.GetValue('');if ($loc) {$candidates.Add((Join-Path $loc 'python.exe'))}}
    }
    $base=$null
    foreach ($candidate in ($candidates | Select-Object -Unique)) { $probed=Probe $candidate; if ($probed) {$base=[string]$probed.base;break} }
    if (-not $base) {
        Log 'Compatible Python not found. Preparing official Python 3.12.10 x64.'
        $cache=Join-Path $state 'cache';New-Item -ItemType Directory -Force -Path $cache | Out-Null
        $installer=Join-Path $cache 'python-3.12.10-amd64.exe'
        $expected='67B5635E80EA51072B87941312D00EC8927C4DB9BA18938F7AD2D27B328B95FB'
        $valid=(Test-Path -LiteralPath $installer) -and ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -eq $expected)
        if (-not $valid) {
            if ($Offline) {throw 'Offline Python installer missing or invalid.'}
            [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
            $tmp=$installer+'.download'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $tmp -TimeoutSec 180
            if ((Get-FileHash -LiteralPath $tmp -Algorithm SHA256).Hash -ne $expected) {throw 'Python installer SHA256 mismatch'}
            Move-Item -LiteralPath $tmp -Destination $installer -Force
        }
        $signature=Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation') {throw 'Python installer Authenticode verification failed'}
        $runtime=Join-Path $env:LOCALAPPDATA 'Programs\Audio2Phira\Python312'
        $installLog=Join-Path $logs ($runId+'-python-install.log')
        Run-Process $installer @('/quiet','InstallAllUsers=0',('TargetDir='+$runtime),'PrependPath=0','Include_launcher=0','AssociateFiles=0','Shortcuts=0','Include_test=0','Include_doc=0','Include_pip=1','Include_tcltk=1','/log',$installLog) 600
        if ($script:RunExit -notin @(0,3010)) {throw ('Python installer failed: '+$script:RunExit)}
        $base=Join-Path $runtime 'python.exe'
        if (-not (Probe $base)) {throw 'Python installation finished but compatibility check failed. See install log.'}
    }
    Log ('Using Python: '+$base)
    if (Test-Path -LiteralPath $venv) {
        $script:backup=Join-Path $Root ('.venv-backup-'+$runId)
        Log ('Backing up existing environment to '+$script:backup)
        Move-Item -LiteralPath $venv -Destination $script:backup
    }
    $script:created=$true
    Run-Process $base @('-m','venv',$venv) 120
    if ($script:RunExit -ne 0) {throw 'Failed to create virtual environment'}
    $depArgs=@((Join-Path $Root 'setup_dependencies.py'),'--root',$Root)
    if ($Offline) {$depArgs+='--offline'}
    Run-Process $venvPy $depArgs 1200
    if ($script:RunExit -ne 0) {throw 'Dependency installation failed; see package logs'}
    if (-not (Healthy $venvPy)) {throw 'Post-install health check failed'}
    Shortcut
    Log 'SETUP_OK Installation and environment checks completed.'
    if ($script:backup) {Log ('Previous environment retained at '+$script:backup)}
    exit 0
} catch {
    Log ('ERROR: '+$_.Exception.Message)
    if ($script:created -and (Test-Path -LiteralPath $venv)) {
        $failed=Join-Path $Root ('.venv-failed-'+$runId)
        try {Move-Item -LiteralPath $venv -Destination $failed;Log ('Incomplete environment retained: '+$failed)} catch {Log 'Could not move incomplete environment; inspect logs before retry.'}
    }
    if ($script:backup -and (Test-Path -LiteralPath $script:backup) -and -not (Test-Path -LiteralPath $venv)) {
        try {Move-Item -LiteralPath $script:backup -Destination $venv;Log 'Previous environment restored.'} catch {Log ('Restore failed; backup remains: '+$script:backup)}
    }
    Log ('Logs: '+$logs)
    exit 1
} finally {
    if ($held) {$mutex.ReleaseMutex()}
    if ($mutex) {$mutex.Dispose()}
}
