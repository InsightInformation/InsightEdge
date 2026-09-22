# Install Quill for the current user on Windows. In PowerShell, from the repo folder:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = "Stop"
$Here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $env:LOCALAPPDATA "Quill"
$Venv   = Join-Path $AppDir "venv"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Quill needs Python 3.10 or newer. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again."
    exit 1
}
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))"
if ($LASTEXITCODE -ne 0) { Write-Host "Quill needs Python 3.10 or newer."; exit 1 }

Write-Host "Installing Quill..."
py -3 -m venv $Venv
& "$Venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install --quiet --upgrade $Here

$Shell = New-Object -ComObject WScript.Shell
$Link = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Quill.lnk"))
$Link.TargetPath = "$Venv\Scripts\quill.exe"
$Link.Description = "Your personal writing partner"
$Link.Save()
Write-Host "Added Quill to your Desktop - double-click it to start writing."

Write-Host "Starting Quill in your browser..."
& "$Venv\Scripts\quill.exe"
