$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
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

    throw "Python 3.10+ is required."
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
& $VenvPython -c "import yt_dlp, whisper, torch" *> $null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install -r requirements-transcribe.txt
}

& $VenvPython media_tui.py @args
