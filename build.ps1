$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing build dependencies..."
& $Python -m pip install --disable-pip-version-check -r requirements.txt

Write-Host "Generating application icon..."
& $Python scripts\make_icon.py

Write-Host "Building TimeTrace.exe..."
& (Join-Path $Root ".venv\Scripts\pyinstaller.exe") `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name TimeTrace `
    --icon assets\timetrace.ico `
    --version-file assets\version_info.txt `
    --paths src `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$Dist = Join-Path $Root "dist\TimeTrace"
Copy-Item (Join-Path $Root "README.md") -Destination $Dist -Force
Copy-Item (Join-Path $Root "LICENSE") -Destination $Dist -Force
$Docs = Join-Path $Dist "docs"
if (Test-Path $Docs) { Remove-Item $Docs -Recurse -Force }
Copy-Item (Join-Path $Root "docs") -Destination $Dist -Recurse -Force

$Zip = Join-Path $Root "dist\TimeTrace-Windows-x64.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Write-Host "Creating portable archive..."
Compress-Archive -Path (Join-Path $Dist "\*") -DestinationPath $Zip -CompressionLevel Optimal

Write-Host ""
Write-Host "Built: $Root\dist\TimeTrace\TimeTrace.exe"
Write-Host "Zip:   $Zip"
