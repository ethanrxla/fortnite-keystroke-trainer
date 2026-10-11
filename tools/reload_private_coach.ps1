# One-shot interactive overlay launch from an SSH maintenance session.
# Does not stop Fortnite, alter locked guide code, or install a recurring task.
param([int]$OrphanGuideId = 0)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$companion = Join-Path $repo 'companion'
$pythonw = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\pythonw.exe'
if (-not (Test-Path $pythonw)) { throw 'Expected companion Python is unavailable' }
$existing = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match '-m keystroke_lab keys' }
if ($existing) { throw 'An overlay already runs; preserve it and inspect before reloading' }
if ($OrphanGuideId) {
    $guide = Get-CimInstance Win32_Process -Filter "ProcessId=$OrphanGuideId"
    if ($guide -and $guide.CommandLine -match 'keystroke_lab.edit_window' -and $guide.CommandLine.Contains($companion)) {
        Stop-Process -Id $OrphanGuideId
    } else { throw 'Guide identity did not match; nothing stopped' }
}
$name = 'KeystrokeTrainer-VoiceReload-' + [guid]::NewGuid().ToString('N')
$action = New-ScheduledTaskAction -Execute $pythonw -Argument '-m keystroke_lab keys' -WorkingDirectory $companion
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Principal $principal | Out-Null
try {
    Start-ScheduledTask -TaskName $name
    Start-Sleep -Seconds 3
    Get-ScheduledTask -TaskName $name | Select-Object TaskName, State
} finally {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
}
