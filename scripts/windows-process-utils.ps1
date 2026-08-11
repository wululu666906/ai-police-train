# Windows 进程树与端口清理公共函数。

function Get-WindowsProcessSnapshot {
    try {
        return @(Get-CimInstance Win32_Process -ErrorAction Stop)
    } catch {
        Write-Host "无法枚举 Windows 进程: $($_.Exception.Message)" -ForegroundColor Yellow
        return @()
    }
}

function Stop-WindowsProcessTree {
    param(
        [Parameter(Mandatory = $true)][int]$RootProcessId,
        [object[]]$ProcessSnapshot
    )

    if (-not $PSBoundParameters.ContainsKey("ProcessSnapshot")) {
        $ProcessSnapshot = Get-WindowsProcessSnapshot
    }

    $orderedIds = New-Object 'System.Collections.Generic.List[int]'
    $visitedIds = New-Object 'System.Collections.Generic.HashSet[int]'
    $visitProcessTree = {
        param([int]$CurrentProcessId)

        if (-not $visitedIds.Add($CurrentProcessId)) { return }
        # 先终止根进程，避免热重载守护进程在清理子进程时再次拉起服务。
        [void]$orderedIds.Add($CurrentProcessId)
        foreach ($child in @($ProcessSnapshot | Where-Object {
            [int]$_.ParentProcessId -eq $CurrentProcessId
        })) {
            & $visitProcessTree -CurrentProcessId ([int]$child.ProcessId)
        }
    }
    & $visitProcessTree -CurrentProcessId $RootProcessId

    $stoppedIds = New-Object 'System.Collections.Generic.List[int]'
    $failures = New-Object 'System.Collections.Generic.List[object]'
    foreach ($currentProcessId in $orderedIds) {
        $process = Get-Process -Id $currentProcessId -ErrorAction SilentlyContinue
        if (-not $process) { continue }

        try {
            Stop-Process -Id $currentProcessId -Force -ErrorAction Stop
            for ($attempt = 0; $attempt -lt 50; $attempt++) {
                if (-not (Get-Process -Id $currentProcessId -ErrorAction SilentlyContinue)) { break }
                Start-Sleep -Milliseconds 100
            }
            if (Get-Process -Id $currentProcessId -ErrorAction SilentlyContinue) {
                throw "已发送强制终止信号，但进程在 5 秒内未退出"
            }
            [void]$stoppedIds.Add($currentProcessId)
        } catch {
            [void]$failures.Add([PSCustomObject]@{
                ProcessId = $currentProcessId
                Message = $_.Exception.Message
            })
        }
    }

    return [PSCustomObject]@{
        RootProcessId = $RootProcessId
        StoppedIds = $stoppedIds.ToArray()
        Failures = $failures.ToArray()
    }
}

function Stop-PortListener {
    param([Parameter(Mandatory = $true)][int]$Port)

    $ownerIds = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    if ($ownerIds.Count -eq 0) { return }

    $snapshot = Get-WindowsProcessSnapshot
    foreach ($ownerId in $ownerIds) {
        if (-not $ownerId -or $ownerId -eq 0) { continue }

        $result = Stop-WindowsProcessTree -RootProcessId $ownerId -ProcessSnapshot $snapshot
        if ($result.StoppedIds.Count -gt 0) {
            Write-Host "已停止端口 $Port 的进程树 PID $($result.StoppedIds -join ', ')（监听归属 PID $ownerId）" -ForegroundColor DarkYellow
        }
        foreach ($failure in $result.Failures) {
            Write-Host "停止端口 $Port 的进程 PID $($failure.ProcessId) 失败: $($failure.Message)" -ForegroundColor Red
        }
    }
}

function Wait-PortReleased {
    param([Parameter(Mandatory = $true)][int]$Port, [int]$Seconds = 15)

    for ($i = 0; $i -lt $Seconds; $i++) {
        $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listener) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Write-PortListenerDiagnostics {
    param([Parameter(Mandatory = $true)][int]$Port)

    $ownerIds = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
    $snapshot = Get-WindowsProcessSnapshot

    foreach ($ownerId in $ownerIds) {
        $owner = $snapshot | Where-Object { [int]$_.ProcessId -eq $ownerId } | Select-Object -First 1
        if (-not $owner) {
            Write-Host "监听归属 PID $ownerId 已退出，正在检查其残留子进程。" -ForegroundColor Yellow
        }

        $related = @($snapshot | Where-Object {
            [int]$_.ProcessId -eq $ownerId -or [int]$_.ParentProcessId -eq $ownerId
        })
        foreach ($process in $related) {
            Write-Host "  PID=$($process.ProcessId) ParentPID=$($process.ParentProcessId) Name=$($process.Name)" -ForegroundColor Yellow
            Write-Host "  CommandLine=$($process.CommandLine)" -ForegroundColor DarkYellow
        }
    }
}
