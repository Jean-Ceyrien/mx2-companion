$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host 'Building MX2 for djay. Python 3.12 (64-bit) must already be installed.'
py -3.12 -m venv .build-venv
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 from python.org, including Tcl/Tk and the Python launcher.' }
& .\.build-venv\Scripts\python.exe -m pip install -r distribution/requirements-build.txt -r distribution/requirements-windows.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& .\.build-venv\Scripts\python.exe distribution/build_desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
Write-Host 'Finished. Open release and read the Windows validation notes before distribution.'
