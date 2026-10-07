param([string]$Python = 'python', [string]$DistPath = 'dist')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$releaseVersion = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'VERSION') -Raw).Trim()
if ($releaseVersion -notmatch '^\d+\.\d+(\.\d+)?$') { throw 'Nieprawidłowy numer w VERSION.' }
$releaseName = 'LOPI-PQ-Report-v' + $releaseVersion
# PyInstaller can otherwise finish successfully with missing PDF dependencies.
& $Python -c "import reportlab.platypus, reportlab.pdfbase.ttfonts, matplotlib, PIL, tkinter, PyInstaller"
if ($LASTEXITCODE -ne 0) { throw 'Brak zależności. Zainstaluj requirements-build.txt w Pythonie użytym do budowania.' }
# Isolated build directory avoids cleaning OneDrive-locked intermediate files.
$buildWorkspace = Join-Path $PSScriptRoot ('build/run-' + [Guid]::NewGuid().ToString('N'))
$stagingPath = Join-Path $buildWorkspace 'release'
& $Python -m PyInstaller --noconfirm --onefile --windowed --workpath $buildWorkspace --distpath $stagingPath --name $releaseName --add-data 'assets;assets' --exclude-module pandas --exclude-module scipy --exclude-module IPython --exclude-module pytest launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Budowanie EXE nie powiodło się.' }
$builtExe = Join-Path $stagingPath ($releaseName + '.exe')
& $Python tools/smoke_test_exe.py $builtExe
if ($LASTEXITCODE -ne 0) { throw 'Test generowania PDF przez EXE nie powiódł się. Nie wydawaj tego pliku.' }
New-Item -ItemType Directory -Path $DistPath -Force | Out-Null
$releaseDirectory = (Resolve-Path -LiteralPath $DistPath).Path
$archiveBatch = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
foreach ($oldExe in Get-ChildItem -LiteralPath $releaseDirectory -File -Filter 'LOPI-PQ-Report*.exe') {
    $archiveDirectory = Join-Path $releaseDirectory ('Kontrola funkcji/' + $oldExe.BaseName + '/' + $archiveBatch)
    New-Item -ItemType Directory -Path $archiveDirectory -Force | Out-Null
    try { Move-Item -LiteralPath $oldExe.FullName -Destination $archiveDirectory -ErrorAction Stop }
    catch { throw "Nie można zarchiwizować $($oldExe.FullName). Nowy sprawdzony EXE pozostaje w $builtExe. Zamknij starą aplikację po zapisaniu projektu. $($_.Exception.Message)" }
}
$publishedExe = Join-Path $releaseDirectory ($releaseName + '.exe')
Copy-Item -LiteralPath $builtExe -Destination $publishedExe -ErrorAction Stop
Write-Host "Gotowe i sprawdzone: $publishedExe"
