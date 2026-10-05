param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# Isolated build directory avoids cleaning OneDrive-locked intermediate files.
$buildWorkspace = Join-Path $PSScriptRoot ('build/run-' + [Guid]::NewGuid().ToString('N'))
& $Python -m PyInstaller --noconfirm --onefile --windowed --workpath $buildWorkspace --name 'LOPI-PQ-Report' --add-data 'assets;assets' --exclude-module pandas --exclude-module scipy --exclude-module IPython --exclude-module pytest launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Budowanie EXE nie powiodło się.' }
Write-Host 'Gotowe: dist/LOPI-PQ-Report.exe'
