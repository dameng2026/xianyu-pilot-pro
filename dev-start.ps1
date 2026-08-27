#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [string]$ValidationService,
    [int]$ValidationPort = 0,
    [switch]$NoPause
)

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RootDir

function Write-OK    { Write-Host "  [OK] $($args)" -ForegroundColor Green }
function Write-Warn  { Write-Host "  [!]  $($args)" -ForegroundColor Yellow }
function Write-Div   { Write-Host ('=' * 48) -ForegroundColor DarkGray }

function Test-Cmd($cmd) {
    # Try Get-Command first, then try running it directly
    try { Get-Command $cmd -ErrorAction Stop | Out-Null; return $true }
    catch {
        try { & $cmd --version 2>$null | Out-Null; return $LASTEXITCODE -eq 0 }
        catch { return $false }
    }
}

# Fail-closed pinned toolchain: must match CI (.github/workflows/ci.yml),
# the frontend Dockerfiles and .node-version exactly.
$RequiredNodeVersion = [Version]'24.18.0'
$RequiredNpmVersion = [Version]'11.16.0'

function Get-SemanticToolVersion($cmd) {
    try {
        $raw = (& $cmd --version 2>$null | Select-Object -First 1)
        if ([string]::IsNullOrWhiteSpace([string]$raw)) { return $null }
        $normalized = ([string]$raw).Trim().TrimStart('v')
        return [Version]$normalized
    }
    catch {
        return $null
    }
}

function Test-ExactVersion($version, [Version]$required) {
    return $null -ne $version -and $version -eq $required
}

function Import-DotEnv($path) {
    if (-not (Test-Path -LiteralPath $path)) { return }

    $allowedKeys = @('ADMIN_JWT_SECRET', 'COOKIE_CRYPTO_SECRET', 'INTERNAL_API_TOKEN')
    foreach ($line in Get-Content -LiteralPath $path -Encoding UTF8) {
        $text = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($text) -or $text.StartsWith('#')) { continue }
        if ($text -notmatch '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { continue }

        $key = $Matches[1]
        if ($key -notin $allowedKeys) { continue }
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2) {
            $quoted = ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            if ($quoted) { $value = $value.Substring(1, $value.Length - 2) }
        }
        Set-Item -Path "Env:$key" -Value $value
    }
}

function Get-ListeningProcessIds {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][int]$Port)

    $processIds = @()
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        try {
            $processIds = @(
                Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop |
                    Select-Object -ExpandProperty OwningProcess -Unique
            )
        }
        catch {
            $processIds = @()
        }
    }

    if ($processIds.Count -eq 0) {
        $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
        foreach ($line in @(netstat -ano -p TCP 2>$null)) {
            if ($line -match $pattern) {
                $processIds += [int]$Matches[1]
            }
        }
    }

    return @($processIds | Sort-Object -Unique)
}

function Get-ProcessMetadata {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    try {
        if (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
            return Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
        }
        return Get-WmiObject Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Test-ProcessTreeBelongsToPath {
    param(
        [Parameter(Mandatory = $true)][int]$ProcessId,
        [Parameter(Mandatory = $true)][string]$ExpectedPath
    )

    $expected = [IO.Path]::GetFullPath($ExpectedPath).TrimEnd('\', '/').Replace('/', '\').ToLowerInvariant()
    $currentId = $ProcessId
    $visited = @{}

    for ($depth = 0; $depth -lt 10 -and $currentId -gt 0; $depth++) {
        if ($visited.ContainsKey($currentId)) { break }
        $visited[$currentId] = $true
        $metadata = Get-ProcessMetadata -ProcessId $currentId
        if ($null -eq $metadata) { break }

        foreach ($candidate in @($metadata.ExecutablePath, $metadata.CommandLine)) {
            if ([string]::IsNullOrWhiteSpace([string]$candidate)) { continue }
            $normalized = ([string]$candidate).Replace('/', '\').ToLowerInvariant()
            if ($normalized.Contains($expected)) { return $true }
        }

        $currentId = [int]$metadata.ParentProcessId
    }

    return $false
}

function Test-ServiceIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$HealthUrl,
        [string[]]$ExpectedMarkers = @()
    )

    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ([int]$response.StatusCode -lt 200 -or [int]$response.StatusCode -ge 300) { return $false }
        $content = [string]$response.Content
        foreach ($marker in $ExpectedMarkers) {
            if ($content.IndexOf($marker, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
                return $false
            }
        }
        return $true
    }
    catch {
        return $false
    }
}

function Get-ServicePortState {
    param([Parameter(Mandatory = $true)]$Service)

    $processIds = @(Get-ListeningProcessIds -Port $Service.Port)
    if ($processIds.Count -eq 0) {
        return [PSCustomObject]@{ State = 'Free'; ProcessIds = @() }
    }

    $allOwnedByCheckout = $true
    foreach ($processId in $processIds) {
        if (-not (Test-ProcessTreeBelongsToPath -ProcessId $processId -ExpectedPath $Service.WorkDir)) {
            $allOwnedByCheckout = $false
            break
        }
    }
    $identityMatches = Test-ServiceIdentity -HealthUrl $Service.HealthUrl -ExpectedMarkers $Service.HealthMarkers

    if ($allOwnedByCheckout -and $identityMatches) {
        return [PSCustomObject]@{ State = 'OwnedHealthy'; ProcessIds = $processIds }
    }
    if ($allOwnedByCheckout) {
        return [PSCustomObject]@{ State = 'OwnedUnhealthy'; ProcessIds = $processIds }
    }
    if ($identityMatches) {
        return [PSCustomObject]@{ State = 'ForeignCheckout'; ProcessIds = $processIds }
    }
    return [PSCustomObject]@{ State = 'ForeignProcess'; ProcessIds = $processIds }
}

function Write-PortConflict {
    param(
        [Parameter(Mandatory = $true)]$Service,
        [Parameter(Mandatory = $true)]$Result
    )

    $processText = ($Result.ProcessIds -join ', ')
    if ($Result.State -eq 'ForeignCheckout') {
        Write-Warn "Port $($Service.Port) answers as $($Service.Name), but PID(s) $processText belong to another checkout or an unknown process."
        Write-Warn "Recovery: close $($Service.Name) in the other checkout, then rerun this launcher."
    }
    elseif ($Result.State -eq 'OwnedUnhealthy') {
        Write-Warn "Port $($Service.Port) belongs to this checkout (PID(s) $processText), but the expected $($Service.Name) health identity failed."
        Write-Warn "Recovery: close that service window, fix its startup error, then rerun this launcher."
    }
    else {
        Write-Warn "Port $($Service.Port) is occupied by an unrelated process (PID(s) $processText); expected $($Service.Name)."
        Write-Warn "Recovery: close the owning application or configure a non-conflicting port, then rerun this launcher."
    }
    Write-Warn "Safety: this launcher will not terminate external processes."
}

if (-not $ValidateOnly) { Clear-Host }
Write-Div
Write-Host "  Xianyu Assistant - Dev Launcher" -ForegroundColor Cyan
Write-Div
Write-Host ""

# --- 1. Environment Check ---
Write-Host "[1/4] Checking environment..." -ForegroundColor Gray
$hasDocker   = Test-Cmd "docker"
$hasJava     = Test-Cmd "java"
$mavenWrapper = Join-Path $RootDir 'apps\core-api\mvnw.cmd'
$hasMavenWrapper = Test-Path -LiteralPath $mavenWrapper
$hasNode     = Test-Cmd "node"
$hasNpm      = Test-Cmd "npm.cmd"
$hasPython   = Test-Cmd "python"
$nodeVersion = if ($hasNode) { Get-SemanticToolVersion 'node' } else { $null }
$npmVersion = if ($hasNpm) { Get-SemanticToolVersion 'npm.cmd' } else { $null }
$nodeToolchainReady = (Test-ExactVersion $nodeVersion $RequiredNodeVersion) -and
    (Test-ExactVersion $npmVersion $RequiredNpmVersion)

if ($hasDocker)   { Write-OK "Docker" }   else { Write-Warn "Docker (skipped)" }
if ($hasJava)     { Write-OK "Java" }     else { Write-Warn "Java (skipped)" }
if ($hasMavenWrapper) { Write-OK "Maven Wrapper 3.9.16" } else { Write-Warn "Maven Wrapper missing (core-api skipped)" }
if ($nodeToolchainReady) {
    Write-OK "Node.js $nodeVersion / npm $npmVersion"
}
elseif ($hasNode -or $hasNpm) {
    Write-Warn "Node toolchain incompatible; require Node 24.18.0 and npm 11.16.0 exactly (see .node-version; Node services skipped)"
}
else {
    Write-Warn "Node.js/npm not found (Node services skipped)"
}
if ($hasPython)   { Write-OK "Python" }   else { Write-Warn "Python (skipped)" }
Write-Host ""

$ServiceSpecs = @(
    [PSCustomObject]@{
        Name = 'core-api'; Port = 18080
        WorkDir = (Join-Path $RootDir 'apps\core-api')
        HealthUrl = 'http://127.0.0.1:18080/api/ops/liveness'
        HealthMarkers = @('xianyu-assistant', 'UP')
        Enabled = ($ValidateOnly -or ($hasJava -and $hasMavenWrapper))
    },
    [PSCustomObject]@{
        Name = 'automation-service'; Port = 12401
        WorkDir = (Join-Path $RootDir 'apps\automation-service')
        HealthUrl = 'http://127.0.0.1:12401/health'
        HealthMarkers = @('Python backend is running')
        Enabled = ($ValidateOnly -or $hasPython)
    },
    [PSCustomObject]@{
        Name = 'crawler-service'; Port = 3001
        WorkDir = (Join-Path $RootDir 'apps\crawler-service')
        HealthUrl = 'http://127.0.0.1:3001/api/health'
        HealthMarkers = @('crawler-service', 'ok')
        Enabled = ($ValidateOnly -or $nodeToolchainReady)
    },
    [PSCustomObject]@{
        Name = 'admin-web'; Port = 3006
        WorkDir = (Join-Path $RootDir 'apps\admin-web')
        HealthUrl = 'http://127.0.0.1:3006/'
        HealthMarkers = @('闲鱼助手管理后台')
        Enabled = ($ValidateOnly -or $nodeToolchainReady)
    },
    [PSCustomObject]@{
        Name = 'user-web'; Port = 5174
        WorkDir = (Join-Path $RootDir 'apps\user-web')
        HealthUrl = 'http://127.0.0.1:5174/'
        HealthMarkers = @('XianYuAssistant')
        Enabled = ($ValidateOnly -or $nodeToolchainReady)
    }
)

if (-not [string]::IsNullOrWhiteSpace($ValidationService)) {
    if (-not $ValidateOnly) {
        throw "-ValidationService is read-only and requires -ValidateOnly."
    }
    if ($ValidationPort -lt 1 -or $ValidationPort -gt 65535) {
        throw "-ValidationPort must be between 1 and 65535."
    }
    $selectedService = $ServiceSpecs |
        Where-Object { $_.Name -eq $ValidationService } |
        Select-Object -First 1
    if ($null -eq $selectedService) {
        throw "Unknown -ValidationService '$ValidationService'."
    }
    $healthUri = New-Object System.UriBuilder($selectedService.HealthUrl)
    $healthUri.Port = $ValidationPort
    $selectedService.Port = $ValidationPort
    $selectedService.HealthUrl = $healthUri.Uri.AbsoluteUri
    $selectedService.Enabled = $true
    $ServiceSpecs = @($selectedService)
}
elseif ($ValidationPort -ne 0) {
    throw "-ValidationPort requires -ValidationService and -ValidateOnly."
}

$ActiveServiceSpecs = @($ServiceSpecs | Where-Object { $_.Enabled })
$PortStates = @{}
$hasPortConflict = $false

Write-Host "[ports] Verifying listener identity and checkout ownership..." -ForegroundColor Gray
foreach ($service in $ActiveServiceSpecs) {
    $result = Get-ServicePortState -Service $service
    $PortStates[[string]$service.Port] = $result
    if ($result.State -eq 'Free') {
        Write-OK "$($service.Name) port $($service.Port) is free"
    }
    elseif ($result.State -eq 'OwnedHealthy') {
        Write-OK "$($service.Name) is already healthy in this checkout on port $($service.Port)"
    }
    else {
        $hasPortConflict = $true
        Write-PortConflict -Service $service -Result $result
    }
}
Write-Host ""

if ($hasPortConflict) {
    Write-Warn "Startup aborted before changing infrastructure or launching services."
    exit 2
}

if ($ValidateOnly) {
    Write-OK "Development port ownership preflight passed"
    exit 0
}

Import-DotEnv (Join-Path $RootDir '.env')

# --- 2. Docker Infrastructure ---
Write-Host "[2/4] Starting databases..." -ForegroundColor Gray
if ($hasDocker) {
    $infra = Join-Path $RootDir "docker-compose.infrastructure.yml"
    if (Test-Path $infra) {
        docker compose -f $infra up -d 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-OK "Database containers started" }
        else { Write-Warn "Docker compose failed" }

        Write-Host "  ->  Waiting for MySQL..." -ForegroundColor Cyan
        $ready = $false
        for ($i = 0; $i -lt 20; $i++) {
            docker exec xianyu-admin-mysql mysqladmin ping -uroot -proot --silent 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { $ready = $true; break }
            Start-Sleep -Seconds 1
        }
        if ($ready) { Write-OK "MySQL ready" } else { Write-Warn "MySQL timeout, continuing..." }
    }
} else { Write-Warn "Docker not available, skip databases" }
Write-Host ""

# --- 3. Install Dependencies ---
Write-Host "[3/4] Checking dependencies..." -ForegroundColor Gray
function Ensure-NodeDependencies($name, $dir) {
    $full = Join-Path $RootDir $dir
    $lockFile = Join-Path $full 'package-lock.json'
    $nodeModules = Join-Path $full 'node_modules'
    $hashMarker = Join-Path $nodeModules '.xianyu-package-lock.sha256'
    if (-not (Test-Path -LiteralPath $lockFile)) {
        throw "$name package-lock.json is missing; refusing a non-reproducible install."
    }

    $expectedHash = (Get-FileHash -LiteralPath $lockFile -Algorithm SHA256).Hash.ToLowerInvariant()
    $installedHash = if (Test-Path -LiteralPath $hashMarker) {
        (Get-Content -LiteralPath $hashMarker -Raw -ErrorAction SilentlyContinue).Trim().ToLowerInvariant()
    } else { '' }
    if ((Test-Path -LiteralPath $nodeModules) -and $installedHash -eq $expectedHash) {
        Write-OK "$name dependencies match package-lock.json"
        return
    }

    Write-Host "  ->  Installing $name from package-lock.json..." -ForegroundColor Cyan
    Push-Location $full
    try {
        & npm.cmd ci --registry=https://registry.npmjs.org --no-audit --no-fund --strict-allow-scripts
        if ($LASTEXITCODE -ne 0) { throw "$name npm ci failed with exit code $LASTEXITCODE" }
        Set-Content -LiteralPath $hashMarker -Value $expectedHash -Encoding ASCII -NoNewline
    }
    finally {
        Pop-Location
    }
}

function Ensure-PythonDependencies {
    $full = Join-Path $RootDir 'apps\automation-service'
    $requirements = Join-Path $full 'requirements.txt'
    $venvPython = Join-Path $full '.venv\Scripts\python.exe'
    $hashMarker = Join-Path $full '.venv\automation-requirements.sha256'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "  ->  Creating automation-service virtual environment..." -ForegroundColor Cyan
        & python -m venv (Join-Path $full '.venv')
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
            throw 'automation-service virtual environment creation failed'
        }
    }
    $expectedHash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash.ToLowerInvariant()
    $installedHash = if (Test-Path -LiteralPath $hashMarker) {
        (Get-Content -LiteralPath $hashMarker -Raw -ErrorAction SilentlyContinue).Trim().ToLowerInvariant()
    } else { '' }
    if ($installedHash -eq $expectedHash) {
        Write-OK "automation-service dependencies match requirements.txt"
        return
    }

    Write-Host "  ->  Installing automation-service pinned dependencies..." -ForegroundColor Cyan
    Push-Location $full
    try {
        & $venvPython -m pip install --disable-pip-version-check --index-url https://pypi.org/simple --only-binary=:all: -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "automation-service pip install failed with exit code $LASTEXITCODE" }
        Set-Content -LiteralPath $hashMarker -Value $expectedHash -Encoding ASCII -NoNewline
    }
    finally {
        Pop-Location
    }
}

function Test-DependencyRefreshAllowed([int]$port) {
    $key = [string]$port
    return -not $PortStates.ContainsKey($key) -or $PortStates[$key].State -ne 'OwnedHealthy'
}

if ($nodeToolchainReady) {
    if (Test-DependencyRefreshAllowed 3006) { Ensure-NodeDependencies 'admin-web' 'apps\admin-web' }
    if (Test-DependencyRefreshAllowed 5174) { Ensure-NodeDependencies 'user-web' 'apps\user-web' }
    if (Test-DependencyRefreshAllowed 3001) { Ensure-NodeDependencies 'crawler-service' 'apps\crawler-service' }
}
if ($hasPython -and (Test-DependencyRefreshAllowed 12401)) { Ensure-PythonDependencies }
Write-OK "Dependencies ready"
Write-Host ""

# --- 4. Start Services ---
Write-Host "[4/4] Starting 5 services..." -ForegroundColor Gray
Write-Host "  Each service opens in a separate window." -ForegroundColor Gray
Write-Host ""

function Start-Win($title, $workDir, $command, $port) {
    $full = Join-Path $RootDir $workDir
    if (-not (Test-Path $full)) { Write-Warn "Not found: $full"; return }
    if ($port) {
        $service = $ServiceSpecs | Where-Object { $_.Port -eq $port } | Select-Object -First 1
        if ($null -ne $service) {
            $freshState = Get-ServicePortState -Service $service
            if ($freshState.State -eq 'OwnedHealthy') {
                Write-OK "$title (already running in this checkout)"
                return
            }
            if ($freshState.State -ne 'Free') {
                Write-PortConflict -Service $service -Result $freshState
                throw "Port $port changed ownership after preflight; startup aborted safely."
            }
        }
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "powershell.exe"
    $psi.Arguments = "-NoExit -Command Set-Location '$full'; $command"
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Normal
    $psi.UseShellExecute = $true
    try { [System.Diagnostics.Process]::Start($psi) | Out-Null; Write-OK "$title" }
    catch { throw "$title failed: $($_.Exception.Message)" }
    Start-Sleep -Milliseconds 800
}

if ($hasJava -and $hasMavenWrapper) {
    Start-Win "core-api [18080]" "apps\core-api" -port 18080 @'
Write-Host 'core-api (Spring Boot) starting...' -ForegroundColor Green
Write-Host 'First start: ~30-60 sec compilation' -ForegroundColor Yellow
Write-Host '  ->  Compiling...' -ForegroundColor Cyan
.\mvnw.cmd --batch-mode --no-transfer-progress -DskipTests package
if ($LASTEXITCODE -ne 0) { Write-Host 'Compilation failed!' -ForegroundColor Red; exit 1 }
Write-Host '  ->  Running...' -ForegroundColor Cyan
$env:SPRING_PROFILES_ACTIVE = "dev"
$env:JAVA_TOOL_OPTIONS = "-Xmx512m -XX:+TieredCompilation -XX:TieredStopAtLevel=1 -XX:+UseParallelGC -Djava.awt.headless=true -Dfile.encoding=UTF-8"
java -jar "target\xianyu-assistant-admin-backend-1.0.0.jar"
'@
}

if ($hasPython) {
    Start-Win "automation-service [12401]" "apps\automation-service" -port 12401 @'
Write-Host 'automation-service (FastAPI) starting...' -ForegroundColor Green
.\.venv\Scripts\python.exe run-fast.py
'@
}

if ($nodeToolchainReady) {
    Start-Win "crawler-service [3001]" "apps\crawler-service" -port 3001 @'
Write-Host 'crawler-service (Node.js) starting...' -ForegroundColor Green
Write-Host '  ->  Building TypeScript (must run from dist, not tsx watch)...' -ForegroundColor Cyan
npm.cmd run build
if ($LASTEXITCODE -ne 0) { Write-Host 'Build failed!' -ForegroundColor Red; exit 1 }
Write-Host '  ->  Running from dist/server.js...' -ForegroundColor Cyan
npm.cmd start
'@
}

if ($nodeToolchainReady) {
    Start-Win "admin-web [3006]" "apps\admin-web" -port 3006 @'
Write-Host 'admin-web (Vue3 + Vite) starting...' -ForegroundColor Green
npm.cmd run dev
'@

    Start-Win "user-web [5174]" "apps\user-web" -port 5174 @'
Write-Host 'user-web (Vue3 + Vite) starting...' -ForegroundColor Green
npm.cmd run dev
'@
}

Write-Host ""
Write-Div
Write-Host "  Available services are starting; review any [!] warnings above." -ForegroundColor Cyan
Write-Div
Write-Host ""
Write-Host "  Admin UI : http://localhost:3006" -ForegroundColor Green
Write-Host "  User UI  : http://localhost:5174" -ForegroundColor Green
Write-Host "  API      : http://localhost:18080/api/health" -ForegroundColor Green
Write-Host ""
Write-Host "  Close service windows to stop." -ForegroundColor Gray
Write-Host "  Stop DB: docker compose -f docker-compose.infrastructure.yml down" -ForegroundColor Gray
Write-Host ""

if (-not $NoPause) {
    Read-Host "Press Enter to exit launcher (services keep running)"
}
