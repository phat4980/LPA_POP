[CmdletBinding()]
param(
    [switch]$Uninstall,
    [string]$NssmPath
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$automationRoot = Join-Path $repoRoot "apps\automation"
$logRoot = Join-Path $repoRoot "storage\logs"
$playwrightBrowsersPath = Join-Path $repoRoot "storage\playwright"
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$nssm = if ($NssmPath) { $NssmPath } else { Join-Path $PSScriptRoot "vendor\nssm\win64\nssm.exe" }

if (-not (Test-Path $nssm)) {
    $nssmCommand = Get-Command nssm.exe -ErrorAction SilentlyContinue
    if ($nssmCommand) { $nssm = $nssmCommand.Source }
}
if (-not (Test-Path $nssm)) {
    throw "NSSM was not found. Place nssm.exe under scripts\vendor\nssm\win64 or pass -NssmPath."
}
if (-not $Uninstall -and -not (Test-Path $pythonPath)) {
    throw "Python virtual environment was not found at .venv. Run the project setup first."
}
if (-not $Uninstall -and -not (Test-Path (Join-Path $automationRoot "dist\main.js"))) {
    throw "Built automation entrypoint was not found. Run npm run build in apps\automation first."
}
if (-not $Uninstall) {
    New-Item -ItemType Directory -Force -Path $playwrightBrowsersPath | Out-Null
    $browserExecutable = Get-ChildItem $playwrightBrowsersPath -Recurse -Filter "chrome-headless-shell.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $browserExecutable) {
        $previousBrowsersPath = $env:PLAYWRIGHT_BROWSERS_PATH
        $env:PLAYWRIGHT_BROWSERS_PATH = $playwrightBrowsersPath
        try {
            Push-Location $automationRoot
            & npm.cmd exec -- playwright install chromium
            if ($LASTEXITCODE -ne 0) { throw "Playwright browser installation failed." }
        } finally {
            Pop-Location
            $env:PLAYWRIGHT_BROWSERS_PATH = $previousBrowsersPath
        }
    }
    if (-not (Get-ChildItem $playwrightBrowsersPath -Recurse -Filter "chrome-headless-shell.exe" -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        throw "Playwright Chromium was not installed correctly."
    }
}

$services = @(
    @{
        Name = "LPA-POP-Web2"
        DisplayName = "LPA POP Web2"
        Application = $pythonPath
        Arguments = "src\web_app.py"
        Directory = $repoRoot
        Stdout = (Join-Path $logRoot "web2.out.log")
        Stderr = (Join-Path $logRoot "web2.err.log")
    },
    @{
        Name = "LPA-POP-Automation"
        DisplayName = "LPA POP Automation"
        Application = $nodePath
        Arguments = "dist\main.js"
        Directory = $automationRoot
        Stdout = (Join-Path $logRoot "automation.out.log")
        Stderr = (Join-Path $logRoot "automation.err.log")
    }
)

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

foreach ($service in $services) {
    $existing = Get-Service -Name $service.Name -ErrorAction SilentlyContinue
    if ($Uninstall) {
        if ($existing) {
            if ($existing.Status -ne "Stopped") { Stop-Service -Name $service.Name -Force }
            & $nssm remove $service.Name confirm | Out-Null
        }
        continue
    }

    if (-not $existing) {
        & $nssm install $service.Name $service.Application $service.Arguments | Out-Null
    }
    & $nssm set $service.Name DisplayName $service.DisplayName | Out-Null
    & $nssm set $service.Name Application $service.Application | Out-Null
    & $nssm set $service.Name AppParameters $service.Arguments | Out-Null
    & $nssm set $service.Name AppDirectory $service.Directory | Out-Null
    & $nssm set $service.Name AppStdout $service.Stdout | Out-Null
    & $nssm set $service.Name AppStderr $service.Stderr | Out-Null
    & $nssm set $service.Name AppNoConsole 1 | Out-Null
    & $nssm set $service.Name AppEnvironmentExtra "PLAYWRIGHT_BROWSERS_PATH=$playwrightBrowsersPath" | Out-Null
    & $nssm set $service.Name AppExit Default Restart | Out-Null
    & $nssm set $service.Name AppRestartDelay 5000 | Out-Null
    & $nssm set $service.Name Start SERVICE_AUTO_START | Out-Null
}

if ($Uninstall) {
    Write-Output "LPA POP services removed."
    exit 0
}

foreach ($service in $services) {
    if ((Get-Service -Name $service.Name).Status -ne "Running") {
        Start-Service -Name $service.Name
    }
}
Write-Output "LPA POP services installed and started."
