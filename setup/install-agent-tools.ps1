# Installs the UEFN playtest automation used by AGENTS.md into %USERPROFILE%\.claude\uefn-tools
# and the uefn-mcp-automation skill into %USERPROFILE%\.claude\skills.
# Source: https://github.com/ViggoJonssonF/uefn-claude-automation (MIT), pinned to a reviewed commit.
# Needs git and Python 3.10+ on PATH.

$ErrorActionPreference = "Stop"
$Repo = "https://github.com/ViggoJonssonF/uefn-claude-automation.git"
$Commit = "b250768f87d2c7398e5aaf98c1640bddf114321d"
$Dest = Join-Path $env:TEMP "uefn-claude-automation"

if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
git clone --quiet $Repo $Dest
git -C $Dest checkout --quiet $Commit

python -m pip install --user pillow
& powershell -ExecutionPolicy Bypass -File (Join-Path $Dest "install.ps1")

Write-Host ""
Write-Host "Installed. Next: open the project in UEFN, enable Python Editor Scripting and UEFN MCP Toolsets"
Write-Host "in Project Settings, then run 'claude' (or 'codex') from the project root."
