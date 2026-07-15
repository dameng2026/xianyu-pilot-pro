param(
  [ValidateSet("all", "backend", "frontend")]
  [string]$Target = "all",

  [string]$Config = ".deploy.prod.json",

  [string]$ReleaseId,
  [string]$MigrationEvidence,

  [switch]$SkipFrontendBuild,
  [switch]$SkipSmoke,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$pythonScript = Join-Path $repoRoot "scripts/prod_deploy.py"

$argsList = @(
  $pythonScript,
  "--target", $Target,
  "--config", $Config
)

if ($Target -in @("all", "backend")) {
  if ([string]::IsNullOrWhiteSpace($ReleaseId)) {
    throw "-ReleaseId is required for backend production releases"
  }
  if ([string]::IsNullOrWhiteSpace($MigrationEvidence)) {
    throw "-MigrationEvidence is required for backend production releases"
  }
  $argsList += @("--release-id", $ReleaseId, "--migration-evidence", $MigrationEvidence)
}

if ($SkipFrontendBuild) { $argsList += "--skip-frontend-build" }
if ($SkipSmoke) { $argsList += "--skip-smoke" }
if ($DryRun) { $argsList += "--dry-run" }

Write-Host "[deploy] repo root: $repoRoot"
Write-Host "[deploy] target: $Target"
python @argsList

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
