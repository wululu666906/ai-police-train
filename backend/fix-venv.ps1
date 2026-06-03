# Rebuild backend\venv (fix encodings error)
# Usage (new PowerShell window, do NOT activate venv first):
#   cd ...\backend
#   Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
#   .\fix-venv.ps1

$ErrorActionPreference = "Stop"
$script:BackendRoot = $PSScriptRoot
Set-Location -LiteralPath $script:BackendRoot
. (Join-Path $PSScriptRoot "scripts\python-env.ps1")
Clear-PythonEnv

$basePython = $null
foreach ($candidate in (Get-BasePythonCandidates)) {
    if (Test-PythonOk $candidate) {
        $basePython = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}

if (-not $basePython) {
    Write-Host "No working Python 3 found." -ForegroundColor Red
    Write-Host "Install Python 3.11+ from https://www.python.org/downloads/"
    Write-Host "Or ensure conda env exists: anaconda3\envs\yolo8_vision"
    exit 1
}

Write-Host "Base Python: $basePython" -ForegroundColor Cyan

$venvDir = Join-Path $script:BackendRoot "venv"
if (Test-Path -LiteralPath $venvDir) {
    Write-Host "Removing old venv ..."
    Remove-Item -LiteralPath $venvDir -Recurse -Force
}

Write-Host "Creating venv ..."
Invoke-PythonExe -PythonExe $basePython -ArgumentString "-m venv `"$venvDir`""

$venvPy = Join-Path $script:BackendRoot "venv\Scripts\python.exe"
if (-not (Test-PythonOk $venvPy)) {
    Write-Host "New venv still broken. Delete PYTHONHOME in System Environment Variables." -ForegroundColor Red
    exit 1
}

$cfg = Join-Path $script:BackendRoot "venv\pyvenv.cfg"
if (Test-Path -LiteralPath $cfg) {
    $homeLine = Get-Content -LiteralPath $cfg | Where-Object { $_ -match '^home\s*=' } | Select-Object -First 1
    Write-Host "pyvenv.cfg: $homeLine"
    if ($homeLine -match 'anaconda3\s*$' -or $homeLine -match 'anaconda3\\?\s*$') {
        Write-Host "ERROR: venv still uses broken Anaconda base. Use yolo8_vision or python.org Python." -ForegroundColor Red
        exit 1
    }
}

Write-Host "Installing dependencies (may take several minutes) ..."
Invoke-PythonExe -PythonExe $venvPy -ArgumentString "-m pip install --upgrade pip"
Invoke-PythonExe -PythonExe $venvPy -ArgumentString "-m pip install -r requirements.txt"

Write-Host ""
Write-Host "Done. Start backend:" -ForegroundColor Green
Write-Host "  Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue"
Write-Host "  .\start.ps1"
