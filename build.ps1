$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtuelle Umgebung konnte nicht erstellt werden.' }
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $taskPython -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build-Abhängigkeiten konnten nicht installiert werden.' }
& $taskPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests fehlgeschlagen.' }
& $taskPython -m PyInstaller --noconfirm --clean --onefile --windowed --name Aion2Farm run.py
if ($LASTEXITCODE -ne 0) { throw 'EXE-Build fehlgeschlagen.' }

$taskExe = Join-Path $PSScriptRoot 'dist\Aion2Farm.exe'
$taskReport = Join-Path $PSScriptRoot 'dist\smoke-test.json'
if (Test-Path -LiteralPath $taskReport) { Remove-Item -LiteralPath $taskReport }
$taskProcess = Start-Process -FilePath $taskExe -ArgumentList @('--smoke-test', '--report', ('"' + $taskReport + '"')) -WindowStyle Hidden -PassThru -Wait
if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskReport)) { throw 'EXE-Smoke-Test fehlgeschlagen.' }
$taskResult = Get-Content -LiteralPath $taskReport -Raw | ConvertFrom-Json
if (-not $taskResult.ok) { throw 'EXE-Vorschau konnte nicht abgeschlossen werden.' }

$taskDigest = (Get-FileHash -LiteralPath $taskExe -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $PSScriptRoot 'dist\SHA256SUMS.txt') -Value ($taskDigest + '  Aion2Farm.exe') -Encoding ascii
Write-Output 'Build und Vorschau-Test erfolgreich: dist\Aion2Farm.exe'
