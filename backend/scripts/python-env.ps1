function Clear-PythonEnv {
    foreach ($name in @("PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE")) {
        if (Test-Path "Env:$name") { Remove-Item "Env:$name" }
    }
}

function Invoke-PythonExe {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [Parameter(Mandatory = $true)][string]$ArgumentString,
        [string]$WorkingDirectory = $script:BackendRoot
    )
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw "Python not found: $PythonExe"
    }
    Clear-PythonEnv
    $exePath = (Resolve-Path -LiteralPath $PythonExe).Path
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exePath
    $psi.Arguments = $ArgumentString
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    if ($psi.EnvironmentVariables.ContainsKey("Path") -and $psi.EnvironmentVariables.ContainsKey("PATH")) {
        $psi.EnvironmentVariables.Remove("PATH")
    }
    foreach ($key in @("PYTHONHOME", "PYTHONPATH", "PYTHONNOUSERSITE")) {
        if ($psi.EnvironmentVariables.ContainsKey($key)) { $psi.EnvironmentVariables.Remove($key) }
    }
    $p = [System.Diagnostics.Process]::Start($psi)
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    if ($stdout.Trim()) { Write-Host $stdout.TrimEnd() }
    if ($stderr.Trim()) { Write-Host $stderr.TrimEnd() -ForegroundColor DarkYellow }
    if ($p.ExitCode -ne 0) {
        throw "exit $($p.ExitCode): $exePath $ArgumentString"
    }
}

function Test-PythonOk {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe)) { return $false }
    try {
        Invoke-PythonExe -PythonExe $PythonExe -ArgumentString '-c "import encodings; print(''ok'')"'
        return $true
    } catch {
        return $false
    }
}

function Get-BasePythonCandidates {
    return @(
        "$env:USERPROFILE\anaconda3\envs\yolo8_vision\python.exe",
        "C:\Users\Auraa\anaconda3\envs\yolo8_vision\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "D:\APP\load\Miniconda3\python.exe"
    )
}
