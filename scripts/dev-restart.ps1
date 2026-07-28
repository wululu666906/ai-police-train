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
$FrontendLog = Join-Path $LogsRoot "dev-frontend.log"
$OpsFrontendLog = Join-Path $LogsRoot "dev-ops-frontend.log"

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

function Start-HiddenPowerShell {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell.exe"
    $encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
    $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $encodedCommand"
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $envVars = $psi.EnvironmentVariables
    if ($null -ne $envVars -and $envVars.ContainsKey("Path") -and $envVars.ContainsKey("PATH")) {
        $envVars.Remove("PATH")
    }
    [System.Diagnostics.Process]::Start($psi) | Out-Null
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
Start-Sleep -Seconds 2

Set-Content -Path $BackendLog -Value "" -Encoding UTF8
Set-Content -Path $FrontendLog -Value "" -Encoding UTF8
Set-Content -Path $OpsFrontendLog -Value "" -Encoding UTF8

$DatabaseUrl = "sqlite:///$($DatabasePath.Replace('\', '/'))"
$BackendCommand = @"
`$env:DATABASE_URL = '$DatabaseUrl'
`$env:CHROMA_DB_PATH = '$ChromaPath'
`$env:PYTHONIOENCODING = 'utf-8'
Remove-Item Env:SSL_CERT_FILE -ErrorAction SilentlyContinue
Remove-Item Env:SSL_CERT_DIR -ErrorAction SilentlyContinue
Remove-Item Env:REQUESTS_CA_BUNDLE -ErrorAction SilentlyContinue
Remove-Item Env:CURL_CA_BUNDLE -ErrorAction SilentlyContinue
Set-Location '$BackendRoot'
& '$PythonExe' -m uvicorn main:app --host 0.0.0.0 --port 8000 *> '$BackendLog'
"@

$FrontendCommand = @"
`$env:CI = 'true'
Set-Location '$FrontendRoot'
& '$BundledNodeExe' node_modules\vite\bin\vite.js --host 0.0.0.0 --port 5556 --strictPort *> '$FrontendLog'
"@

$OpsFrontendCommand = @"
`$env:CI = 'true'
Set-Location '$FrontendRoot'
& '$BundledNodeExe' node_modules\vite\bin\vite.js --host 0.0.0.0 --port 6670 --strictPort *> '$OpsFrontendLog'
"@

Write-Host "启动后端热重载服务 ..." -ForegroundColor Cyan
Start-HiddenPowerShell -Command $BackendCommand -WorkingDirectory $BackendRoot

Write-Host "启动前端 Vite 服务 ..." -ForegroundColor Cyan
Start-HiddenPowerShell -Command $FrontendCommand -WorkingDirectory $FrontendRoot

Write-Host "启动维护端 Vite 服务 ..." -ForegroundColor Cyan
Start-HiddenPowerShell -Command $OpsFrontendCommand -WorkingDirectory $FrontendRoot

Write-Host "检查后端 /healthz ..." -ForegroundColor Cyan
$backendResp = Wait-HttpOk -Url "http://127.0.0.1:8000/healthz" -Seconds 45
if (-not $backendResp) {
    Write-Host "后端启动校验失败，请查看 $BackendLog" -ForegroundColor Red
    exit 1
}

Write-Host "检查 Vite 热更新客户端 ..." -ForegroundColor Cyan
$frontendResp = Wait-HttpOk -Url "http://127.0.0.1:5556/" -Seconds 45
if (-not $frontendResp -or ($frontendResp.Content -notmatch "/@vite/client")) {
    Write-Host "前端热更新校验失败，请查看 $FrontendLog" -ForegroundColor Red
    exit 1
}

Write-Host "检查维护端 Vite 热更新客户端 ..." -ForegroundColor Cyan
$opsFrontendResp = Wait-HttpOk -Url "http://127.0.0.1:6670/" -Seconds 45
if (-not $opsFrontendResp -or ($opsFrontendResp.Content -notmatch "/@vite/client")) {
    Write-Host "维护端热更新校验失败，请查看 $OpsFrontendLog" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "本地开发环境已启动。" -ForegroundColor Green
Write-Host "  管理端/学员端: http://localhost:5556/" -ForegroundColor Green
Write-Host "  维护端: http://localhost:6670/" -ForegroundColor Green
Write-Host "  后端接口文档: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "  后端日志: $BackendLog" -ForegroundColor DarkGray
Write-Host "  前端日志: $FrontendLog" -ForegroundColor DarkGray
Write-Host "  维护端日志: $OpsFrontendLog" -ForegroundColor DarkGray
