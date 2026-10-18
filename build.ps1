param([string]$OutputDirectory = 'dist')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtuelle Umgebung konnte nicht erstellt werden.' }
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $taskPython -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build-Abhängigkeiten konnten nicht installiert werden.' }
& $taskPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests fehlgeschlagen.' }
& $taskPython -m PyInstaller --noconfirm --clean --onefile --windowed --name Aion2Farm --distpath $OutputDirectory run.py
if ($LASTEXITCODE -ne 0) { throw 'EXE-Build fehlgeschlagen.' }
& $taskPython -m PyInstaller --noconfirm --clean --onefile --console --name Aion2FarmMCP --distpath $OutputDirectory mcp_entry.py
if ($LASTEXITCODE -ne 0) { throw 'MCP-Build fehlgeschlagen.' }

$taskOutput = Join-Path $PSScriptRoot $OutputDirectory
$taskExe = Join-Path $taskOutput 'Aion2Farm.exe'
$taskReport = Join-Path $taskOutput 'smoke-test.json'
if (Test-Path -LiteralPath $taskReport) { Remove-Item -LiteralPath $taskReport }
$taskProcess = Start-Process -FilePath $taskExe -ArgumentList @('--smoke-test', '--report', ('"' + $taskReport + '"')) -WindowStyle Hidden -PassThru -Wait
if ($taskProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $taskReport)) { throw 'EXE-Smoke-Test fehlgeschlagen.' }
$taskResult = Get-Content -LiteralPath $taskReport -Raw | ConvertFrom-Json
if (-not $taskResult.ok) { throw 'EXE-Vorschau konnte nicht abgeschlossen werden.' }
& $taskPython scripts/check_mcp.py (Join-Path $taskOutput 'Aion2FarmMCP.exe')
if ($LASTEXITCODE -ne 0) { throw 'MCP-EXE-Protokolltest fehlgeschlagen.' }

$taskDigest = (Get-FileHash -LiteralPath $taskExe -Algorithm SHA256).Hash.ToLowerInvariant()
$taskMcpDigest = (Get-FileHash -LiteralPath (Join-Path $taskOutput 'Aion2FarmMCP.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $taskOutput 'SHA256SUMS.txt') -Value @(($taskDigest + '  Aion2Farm.exe'), ($taskMcpDigest + '  Aion2FarmMCP.exe')) -Encoding ascii
Write-Output ('Build und Vorschau-Test erfolgreich: ' + $taskExe)
