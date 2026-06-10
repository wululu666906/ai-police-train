# 停止旧进程并重启前后端（开发环境）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendRoot = Join-Path $Root "backend"
$FrontendRoot = Join-Path $Root "frontend"

. (Join-Path $Root "scripts\fix-terminal-env.ps1")

function Stop-PortListener {
    param([int]$Port)
    $procIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        if ($procId -and $procId -ne 0) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "已停止端口 $Port 上的进程 PID $procId" -ForegroundColor DarkYellow
        }
    }
}

Stop-PortListener 8000
Stop-PortListener 5175
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "启动后端 ..." -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $BackendRoot "start.ps1") `
    -WorkingDirectory $BackendRoot

Write-Host "启动前端 ..." -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile", "-Command", "Set-Location '$FrontendRoot'; npm run dev" `
    -WorkingDirectory $FrontendRoot

Start-Sleep -Seconds 5

Write-Host ""
Write-Host "前端: http://localhost:5175/" -ForegroundColor Green
Write-Host "后端: http://127.0.0.1:8000/docs" -ForegroundColor Green
