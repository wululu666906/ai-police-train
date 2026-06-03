# Start backend in this window (Ctrl+C to stop)
$ErrorActionPreference = "Stop"
$script:BackendRoot = $PSScriptRoot
Set-Location -LiteralPath $script:BackendRoot
. (Join-Path $PSScriptRoot "scripts\python-env.ps1")
Clear-PythonEnv

$venvPy = Join-Path $script:BackendRoot "venv\Scripts\python.exe"
$python = $null

if (Test-PythonOk $venvPy) {
    $python = (Resolve-Path -LiteralPath $venvPy).Path
    Write-Host "Using venv: $python"
} else {
    Write-Host "venv not usable. Trying fallback ..." -ForegroundColor Yellow
    foreach ($candidate in (Get-BasePythonCandidates)) {
        if (Test-PythonOk $candidate) {
            $python = (Resolve-Path -LiteralPath $candidate).Path
            Write-Host "Using fallback: $python" -ForegroundColor Yellow
            Write-Host "Run .\fix-venv.ps1 to rebuild venv." -ForegroundColor Yellow
            break
        }
    }
}

if (-not $python) {
    Write-Host "No Python found. Run: .\fix-venv.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "API docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

Clear-PythonEnv
$uvicornArgs = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000")
if ($args.Count -gt 0) { $uvicornArgs += $args }

& $python @uvicornArgs
exit $LASTEXITCODE
