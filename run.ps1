$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Python)) {
    throw "Missing .venv. Run: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
}
$env:PYTHONPATH = Join-Path $Root "src"
Start-Process -FilePath $Python -ArgumentList (Join-Path $Root "main.py") -WorkingDirectory $Root
