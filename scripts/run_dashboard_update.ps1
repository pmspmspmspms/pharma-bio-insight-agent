$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$LogDir = Join-Path $ProjectRoot "logs"
$LogPath = Join-Path $LogDir "dashboard-update.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$stamp] Starting dashboard update" | Add-Content -LiteralPath $LogPath -Encoding UTF8

& $Python "src\main.py" "--no-ai" *>> $LogPath

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$stamp] Finished dashboard update" | Add-Content -LiteralPath $LogPath -Encoding UTF8
