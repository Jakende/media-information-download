$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

function Get-PythonCommand {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($python) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @("python")
    }

    throw "Python 3.10+ is required. Install it from https://www.python.org/downloads/windows/ or with winget install Python.Python.3.12"
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Warning "ffmpeg is not available on PATH."
    Write-Warning "Install it with: winget install Gyan.FFmpeg"
}

$PythonCommand = Get-PythonCommand
$PythonExe = $PythonCommand[0]
$PythonArgs = @()
if ($PythonCommand.Length -gt 1) {
    $PythonArgs = $PythonCommand[1..($PythonCommand.Length - 1)]
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $PythonExe @PythonArgs -m venv .venv
}

$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements-transcribe.txt
& $VenvPython -m pip install -e ".[transcribe]"

Write-Host "Installed local environment."
Write-Host "Run: .\run.ps1"
Write-Host "Or:  media-information-download"
