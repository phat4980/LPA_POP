[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$serviceNames = @("LPA-POP-Web2", "LPA-POP-Automation")
$timeoutSeconds = 30

function Read-EnvFile([string]$path) {
    $values = @{}
    if (-not (Test-Path $path)) { return $values }
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*([^#=]+?)\s*=\s*(.*?)\s*$') {
            $values[$matches[1].Trim()] = $matches[2].Trim().Trim('"').Trim("'")
        }
    }
    return $values
}

function Show-LauncherError([string]$message) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, "LPA POP", "OK", "Error") | Out-Null
    exit 1
}

try {
    $rootEnv = Read-EnvFile (Join-Path $repoRoot ".env")
    $automationEnv = Read-EnvFile (Join-Path $repoRoot "apps\automation\.env")
    $envValues = @{}
    foreach ($key in $rootEnv.Keys) { $envValues[$key] = $rootEnv[$key] }
    foreach ($key in $automationEnv.Keys) { if (-not $envValues.ContainsKey($key)) { $envValues[$key] = $automationEnv[$key] } }

    $dashboardUrl = if ($envValues.ContainsKey("DASHBOARD_URL")) { $envValues["DASHBOARD_URL"] } else { "http://127.0.0.1:8088/static/automation.html" }
    $web2BaseUrl = if ($envValues.ContainsKey("WEB2_BASE_URL")) { $envValues["WEB2_BASE_URL"].TrimEnd("/") } else { "http://127.0.0.1:8088" }
    $automationHost = if ($envValues.ContainsKey("AUTOMATION_HOST")) { $envValues["AUTOMATION_HOST"] } else { "127.0.0.1" }
    $automationPort = if ($envValues.ContainsKey("AUTOMATION_PORT")) { [int]$envValues["AUTOMATION_PORT"] } else { 8090 }

    foreach ($serviceName in $serviceNames) {
        $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
        if (-not $service) { Show-LauncherError "LPA POP chưa được cài đặt đầy đủ. Vui lòng liên hệ IT." }
        if ($service.Status -ne "Running") { Start-Service -Name $serviceName }
    }

    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    do {
        $web2Ready = $false
        try { $web2Ready = (Invoke-WebRequest -Uri "$web2BaseUrl/api/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { }
        $automationReady = Test-NetConnection -ComputerName $automationHost -Port $automationPort -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($web2Ready -and $automationReady) {
            Start-Process $dashboardUrl
            exit 0
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    Show-LauncherError "LPA POP chưa sẵn sàng. Vui lòng thử lại hoặc liên hệ IT."
} catch {
    Show-LauncherError "Không thể khởi động LPA POP. Vui lòng liên hệ IT."
}
