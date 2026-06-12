# 本地 Docker 部署（Windows / PowerShell）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

. (Join-Path $Root "scripts\fix-terminal-env.ps1")

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Read-DotEnvValue {
    param([string]$Path, [string]$Key, [string]$Default)
    if (-not (Test-Path $Path)) { return $Default }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        if ($trimmed -match "^$([regex]::Escape($Key))=(.*)$") {
            return $Matches[1].Trim()
        }
    }
    return $Default
}

function Stop-PortListener {
    param([int]$Port)
    $procIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        if ($procId -and $procId -ne 0) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "已释放端口 $Port (PID $procId)" -ForegroundColor DarkYellow
        }
    }
}

if (-not (Test-CommandExists "docker")) {
    Write-Host "未检测到 Docker，请先安装 Docker Desktop 并启动。" -ForegroundColor Red
    exit 1
}

$envFile = Join-Path $Root "backend\.env"
$envExample = Join-Path $Root "backend\.env.example"
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host "已从模板创建 backend\.env，请填写 JWT_SECRET_KEY 与 LLM API Key 后重新运行。" -ForegroundColor Yellow
    exit 1
}

$composeEnv = Join-Path $Root ".env"
if (-not (Test-Path $composeEnv)) {
    Copy-Item (Join-Path $Root ".env.example") $composeEnv
    Write-Host "已创建根目录 .env（WEB_PORT / APP_PORT）。" -ForegroundColor DarkGray
}

$webPort = Read-DotEnvValue -Path $composeEnv -Key "WEB_PORT" -Default "5175"
$apiPort = Read-DotEnvValue -Path $composeEnv -Key "APP_PORT" -Default "8000"

Write-Host "[1/5] 规范化 shell 脚本行尾 (LF)..." -ForegroundColor Cyan
& (Join-Path $Root "scripts\normalize-sh.ps1") -Root $Root

Write-Host "[2/5] 部署前检查..." -ForegroundColor Cyan
$backendVenv = Join-Path $Root "backend\venv\Scripts\python.exe"
if (Test-Path $backendVenv) {
    & $backendVenv (Join-Path $Root "scripts\deploy_check.py")
} else {
    python (Join-Path $Root "scripts\deploy_check.py")
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[3/5] 准备数据目录并释放端口 $webPort ..." -ForegroundColor Cyan
$dataDir = Join-Path $Root "data"
$chromaDir = Join-Path $dataDir "chroma_db"
$dbFile = Join-Path $dataDir "ai_police.db"
New-Item -ItemType Directory -Force -Path $chromaDir | Out-Null
if (-not (Test-Path $dbFile)) {
    New-Item -ItemType File -Force -Path $dbFile | Out-Null
}
Stop-PortListener -Port ([int]$webPort)

Write-Host "[4/5] 停止旧容器并构建启动（单容器 app）..." -ForegroundColor Cyan
docker compose down --remove-orphans 2>$null | Out-Null
docker compose up -d --build app
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[5/5] 等待健康检查..." -ForegroundColor Cyan
$healthy = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$webPort/healthz" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    Write-Host "健康检查超时，请执行：docker compose logs -f app" -ForegroundColor Yellow
    exit 1
}

$containerState = docker inspect -f "{{.State.Status}}" ai_police_app 2>$null
if ($containerState -ne "running") {
    Write-Host "容器未处于 running 状态：$containerState" -ForegroundColor Yellow
    docker compose logs app --tail 30
    exit 1
}

Write-Host ""
Write-Host "Docker 部署完成。" -ForegroundColor Green
Write-Host "  首页：  http://127.0.0.1:$webPort/" -ForegroundColor Green
Write-Host "  API：   http://127.0.0.1:$webPort/docs" -ForegroundColor Green
Write-Host "  健康：  http://127.0.0.1:$webPort/healthz" -ForegroundColor Green
Write-Host ""
Write-Host "拆分模式：前端 $webPort + API $apiPort" -ForegroundColor DarkGray
Write-Host "  docker compose --profile split up -d --build api frontend" -ForegroundColor DarkGray
Write-Host "查看日志：docker compose logs -f app" -ForegroundColor DarkGray
