# Restart the companion overlay: keyboard overlay, the Jev edit guide (green boxes, yellow route, red ring) and the
# stats strip. Run it when the guide stops drawing:  powershell -ExecutionPolicy Bypass -File restart_overlay.ps1
# If an earlier overlay was started from an administrator window, run this from an administrator window too.
$companion = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\pythonw.exe'
$autostart = Join-Path $companion 'autostart.pyw'
# Overlay processes: matched by command line, plus pythonw windows whose command line Windows hides (elevated ones).
$targets = Get-CimInstance Win32_Process -Filter "name like 'python%'" | Where-Object {
    ($_.CommandLine -match 'keystroke_lab (keys|stats-panel)|keystroke_lab\.edit_window') -or
    (-not $_.CommandLine -and $_.Name -eq 'pythonw.exe')
}
$blocked = @()
foreach ($p in $targets) {
    try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { $blocked += $p.ProcessId }
}
if ($blocked) {
    Write-Host "Could not stop overlay process(es) $($blocked -join ', '): they were started as administrator."
    Write-Host "Open PowerShell as administrator and run this script again."
    exit 1
}
Start-Sleep -Seconds 1
# The keyboard overlay starts the edit guide itself; the stats strip is its own window.
Start-Process -FilePath $pythonw -ArgumentList '-m', 'keystroke_lab', 'keys' -WorkingDirectory $companion
Start-Process -FilePath $pythonw -ArgumentList '-m', 'keystroke_lab', 'stats-panel' -WorkingDirectory $companion
$watcher = Get-CimInstance Win32_Process -Filter "name like 'python%'" | Where-Object { $_.CommandLine -match 'autostart\.pyw' }
if (-not $watcher) { Start-Process -FilePath $pythonw -ArgumentList "`"$autostart`"" -WorkingDirectory $companion }
Write-Host "Overlay restarted. Click into Fortnite and open an edit."
