# Fix broken Baota Panel Python paths in terminal environment
$ErrorActionPreference = "Stop"

$BrokenPathEntries = @(
    "C:\Program Files\python",
    "C:\Program Files\python\Scripts"
)

function Remove-BrokenPathEntries {
    param([string]$PathValue)
    if (-not $PathValue) { return "" }
    ($PathValue -split ';' | Where-Object {
        $_ -and ($BrokenPathEntries -notcontains $_)
    }) -join ';'
}

$scope = "User"
$userPath = [Environment]::GetEnvironmentVariable("Path", $scope)
$cleanUserPath = Remove-BrokenPathEntries $userPath
if ($cleanUserPath -ne $userPath) {
    [Environment]::SetEnvironmentVariable("Path", $cleanUserPath, $scope)
    Write-Host "Cleaned broken Python paths from user PATH." -ForegroundColor Green
} else {
    Write-Host "User PATH already clean." -ForegroundColor DarkGray
}

foreach ($name in @("BT_PYTHON", "UNRAR_LIB_PATH", "PYTHONHOME", "PYTHONPATH")) {
    $userVal = [Environment]::GetEnvironmentVariable($name, $scope)
    if ($userVal) {
        [Environment]::SetEnvironmentVariable($name, $null, $scope)
        Write-Host "Removed user env var: $name" -ForegroundColor Green
    }
}

$machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$machineParts = @()
if ($machinePath) {
    $machineParts = $machinePath -split ';'
}
$machineBroken = @()
foreach ($entry in $BrokenPathEntries) {
    if ($machineParts -contains $entry) {
        $machineBroken += $entry
    }
}
if ($machineBroken.Count -gt 0) {
    Write-Host ""
    Write-Host "Machine PATH still contains broken entries (admin required):" -ForegroundColor Yellow
    foreach ($entry in $machineBroken) {
        Write-Host "  $entry" -ForegroundColor Yellow
    }
    Write-Host "Run this script as Administrator or remove them in System Environment Variables." -ForegroundColor Yellow
}

$env:Path = Remove-BrokenPathEntries $env:Path
Remove-Item Env:BT_PYTHON -ErrorAction SilentlyContinue
Remove-Item Env:UNRAR_LIB_PATH -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Current session cleaned. Restart Cursor terminal for full effect." -ForegroundColor Cyan
