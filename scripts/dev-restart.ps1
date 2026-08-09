# 停止 Docker 单容器并重启本地热更新开发环境。
# 稳定本地部署入口保留给 Docker: http://localhost:5555/
# 实时开发入口使用 Vite:       http://localhost:5556/
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendRoot = Join-Path $Root "backend"
$FrontendRoot = Join-Path $Root "frontend"
$LogsRoot = Join-Path $Root "logs"
$PythonExe = Join-Path $BackendRoot "venv\Scripts\python.exe"
$BundledNodeExe = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
$DatabasePath = Join-Path $Root "data\ai_police.db"
$ChromaPath = Join-Path $Root "data\chroma_db"
$BackendLog = Join-Path $LogsRoot "dev-backend.log"
$BackendErrLog = Join-Path $LogsRoot "dev-backend.err.log"
$FrontendLog = Join-Path $LogsRoot "dev-frontend.log"
$FrontendErrLog = Join-Path $LogsRoot "dev-frontend.err.log"
$OpsFrontendLog = Join-Path $LogsRoot "dev-ops-frontend.log"
$OpsFrontendErrLog = Join-Path $LogsRoot "dev-ops-frontend.err.log"

. (Join-Path $Root "scripts\fix-terminal-env.ps1")

foreach ($name in @("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE")) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}

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

function Wait-PortReleased {
    param([int]$Port, [int]$Seconds = 15)
    for ($i = 0; $i -lt $Seconds; $i++) {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Wait-HttpOk {
    param([string]$Url, [int]$Seconds = 30)
    for ($i = 0; $i -lt $Seconds; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $resp
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return $null
}

function Start-HiddenNativeProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$StandardOutputPath,
        [Parameter(Mandatory = $true)][string]$StandardErrorPath
    )
    return Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StandardOutputPath `
        -RedirectStandardError $StandardErrorPath `
        -WindowStyle Hidden `
        -PassThru
}

function Stop-BackendDevProcesses {
    try {
        $processes = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
            $_.CommandLine -like "*uvicorn main:app*" -and
            $_.CommandLine -like "*--port 8000*" -and
            $_.CommandLine -notlike "*Get-CimInstance*"
        }
    } catch {
        Write-Host "无权限枚举后端开发进程，已跳过精确清理；端口清理仍会继续。" -ForegroundColor Yellow
        return
    }
    foreach ($proc in $processes) {
        if ($proc.ProcessId -and $proc.ProcessId -ne $PID) {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "已停止后端开发进程 PID $($proc.ProcessId)" -ForegroundColor DarkYellow
        }
    }
}

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogsRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $DatabasePath) | Out-Null
New-Item -ItemType Directory -Force -Path $ChromaPath | Out-Null

if (-not (Test-Path $PythonExe)) {
    Write-Host "未找到后端虚拟环境 Python: $PythonExe" -ForegroundColor Red
    Write-Host "请先执行: cd backend; python -m venv venv; .\venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

$HasBundledNode = Test-Path -LiteralPath $BundledNodeExe
if (-not $HasBundledNode) {
    Write-Host "未找到 bundled Node: $BundledNodeExe" -ForegroundColor Red
    Write-Host "请先安装 Node.js，或确认 Codex bundled Node 可用。" -ForegroundColor Yellow
    exit 1
}

Stop-PortListener 8000
Stop-PortListener 5556
Stop-PortListener 6666
Stop-PortListener 6670
Stop-PortListener 5175
Stop-BackendDevProcesses
foreach ($port in @(8000, 5556, 6666, 6670, 5175)) {
    if (-not (Wait-PortReleased -Port $port)) {
        $ownerIds = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        Write-Host "端口 $port 未释放，残留 PID: $($ownerIds -join ', ')" -ForegroundColor Red
        exit 1
    }
}

Set-Content -Path $BackendLog -Value "" -Encoding UTF8
Set-Content -Path $BackendErrLog -Value "" -Encoding UTF8
Set-Content -Path $FrontendLog -Value "" -Encoding UTF8
Set-Content -Path $FrontendErrLog -Value "" -Encoding UTF8
Set-Content -Path $OpsFrontendLog -Value "" -Encoding UTF8
Set-Content -Path $OpsFrontendErrLog -Value "" -Encoding UTF8

$DatabaseUrl = "sqlite:///$($DatabasePath.Replace('\', '/'))"
$env:DATABASE_URL = $DatabaseUrl
$env:CHROMA_DB_PATH = $ChromaPath
$env:PYTHONIOENCODING = "utf-8"
$env:CI = "true"

Write-Host "启动后端热重载服务 ..." -ForegroundColor Cyan
$backendProcess = Start-HiddenNativeProcess `
    -FilePath $PythonExe `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", ".") `
    -WorkingDirectory $BackendRoot `
    -StandardOutputPath $BackendLog `
    -StandardErrorPath $BackendErrLog

Write-Host "启动前端 Vite 服务 ..." -ForegroundColor Cyan
$frontendProcess = Start-HiddenNativeProcess `
    -FilePath $BundledNodeExe `
    -ArgumentList @("node_modules\vite\bin\vite.js", "--host", "0.0.0.0", "--port", "5556", "--strictPort") `
    -WorkingDirectory $FrontendRoot `
    -StandardOutputPath $FrontendLog `
    -StandardErrorPath $FrontendErrLog

Write-Host "启动维护端 Vite 服务 ..." -ForegroundColor Cyan
$opsFrontendProcess = Start-HiddenNativeProcess `
    -FilePath $BundledNodeExe `
    -ArgumentList @("node_modules\vite\bin\vite.js", "--host", "0.0.0.0", "--port", "6670", "--strictPort") `
    -WorkingDirectory $FrontendRoot `
    -StandardOutputPath $OpsFrontendLog `
    -StandardErrorPath $OpsFrontendErrLog

Write-Host "检查后端 /healthz ..." -ForegroundColor Cyan
$backendResp = Wait-HttpOk -Url "http://127.0.0.1:8000/healthz" -Seconds 90
if (-not $backendResp) {
    Write-Host "后端启动校验失败，请查看 $BackendLog" -ForegroundColor Red
    exit 1
}

Write-Host "检查后端开场流式路由版本 ..." -ForegroundColor Cyan
$openApiResp = Wait-HttpOk -Url "http://127.0.0.1:8000/openapi.json" -Seconds 15
$requiredOpeningRoute = "/training/session/{session_id}/opening-stream"
if (-not $openApiResp -or $openApiResp.Content -notmatch [Regex]::Escape($requiredOpeningRoute)) {
    Write-Host "后端版本校验失败：OpenAPI 未注册 $requiredOpeningRoute" -ForegroundColor Red
    Write-Host "请查看 $BackendLog 和 $BackendErrLog" -ForegroundColor Yellow
    exit 1
}

Write-Host "检查 Vite 热更新客户端 ..." -ForegroundColor Cyan
$frontendResp = Wait-HttpOk -Url "http://127.0.0.1:5556/" -Seconds 45
if (-not $frontendResp -or ($frontendResp.Content -notmatch "/@vite/client")) {
    Write-Host "前端热更新校验失败，请查看 $FrontendLog 和 $FrontendErrLog" -ForegroundColor Red
    exit 1
}

Write-Host "检查维护端 Vite 热更新客户端 ..." -ForegroundColor Cyan
$opsFrontendResp = Wait-HttpOk -Url "http://127.0.0.1:6670/" -Seconds 45
if (-not $opsFrontendResp -or ($opsFrontendResp.Content -notmatch "/@vite/client")) {
    Write-Host "维护端热更新校验失败，请查看 $OpsFrontendLog 和 $OpsFrontendErrLog" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "本地开发环境已启动。" -ForegroundColor Green
Write-Host "  管理端/学员端: http://localhost:5556/" -ForegroundColor Green
Write-Host "  维护端: http://localhost:6670/" -ForegroundColor Green
Write-Host "  后端接口文档: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "  后端日志: $BackendLog" -ForegroundColor DarkGray
Write-Host "  后端错误日志: $BackendErrLog" -ForegroundColor DarkGray
Write-Host "  前端日志: $FrontendLog" -ForegroundColor DarkGray
Write-Host "  维护端日志: $OpsFrontendLog" -ForegroundColor DarkGray
