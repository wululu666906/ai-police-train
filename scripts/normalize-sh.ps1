# 将 shell 脚本转为 Unix LF，避免 Docker 容器内 bash\r 报错
param(
    [string]$Root = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
)

$targets = @(
    (Join-Path $Root "start.sh"),
    (Join-Path $Root "backend\docker-entrypoint.sh"),
    (Join-Path $Root "scripts\server_deploy.sh")
)

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$fixed = 0

foreach ($path in $targets) {
    if (-not (Test-Path $path)) { continue }
    $raw = [System.IO.File]::ReadAllText($path)
    $normalized = $raw -replace "`r`n", "`n" -replace "`r", "`n"
    if (-not $normalized.EndsWith("`n")) {
        $normalized += "`n"
    }
    if ($normalized -ne $raw) {
        [System.IO.File]::WriteAllText($path, $normalized, $utf8NoBom)
        Write-Host "LF: $path" -ForegroundColor DarkGray
        $fixed++
    }
}

if ($fixed -eq 0) {
    Write-Host "Shell scripts already LF." -ForegroundColor DarkGray
}
