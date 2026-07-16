#!/usr/bin/env bash
set -euo pipefail

# Production always targets the local Docker daemon and the Compose project
# derived from the approved project directory. Ambient CLI control variables
# must not redirect validation/deployment to another daemon or project.
unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES COMPOSE_ENV_FILES DOCKER_HOST DOCKER_CONTEXT
export DOCKER_CONTEXT=default

SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="${SCRIPT_PATH%/*}"
if [[ "$SCRIPT_DIR" == "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="."
fi
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
NGINX_CONFIG="${2:-$ROOT_DIR/deploy/nginx/us-nginx-full.conf}"
EXPECTED_RELEASE_REVISION="${3:-}"
EXPECTED_RELEASE_ID="${4:-}"
EXPECTED_MIGRATION_EVIDENCE_SHA256="${5:-}"

fail() { echo "[FAIL] $*" >&2; exit 1; }
warn() { echo "[WARN] $*" >&2; }
ok() { echo "[OK] $*"; }

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python >/dev/null 2>&1 && "$(command -v python)" -c "import sys" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1 && "$(command -v python3)" -c "import sys" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    fail "Python is required for the shared release security preflight"
  fi
fi

if ! "$PYTHON_BIN" "$ROOT_DIR/scripts/prod_deploy.py" \
  --preflight-only --nginx-config "$NGINX_CONFIG"; then
  fail "Shared release security preflight failed; no environment file was loaded"
fi
ok "Shared release security preflight passed"

[[ -f "$ENV_FILE" ]] || fail "Missing env file: $ENV_FILE"
[[ ! -L "$ENV_FILE" ]] || fail "Production env file must not be a symbolic link"
env_mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null)" || fail "Cannot inspect production env file permissions"
[[ "$env_mode" == "400" || "$env_mode" == "600" ]] \
  || fail "Production env file must use owner-only 0400 or 0600 permissions"
env_owner="$(stat -c '%u' "$ENV_FILE" 2>/dev/null)" || fail "Cannot inspect production env file owner"
[[ "$env_owner" == "$(id -u)" ]] || fail "Production env file must be owned by the deployment operator"

# Parse dotenv as data. Never source an operator-controlled file as shell code.
declare -A loaded_env_keys=()
declare -A loaded_env_values=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] \
    || fail "Production env file contains an invalid assignment"
  key="${BASH_REMATCH[1]}"
  value="${BASH_REMATCH[2]}"
  [[ -z "${loaded_env_keys[$key]+x}" ]] || fail "Production env file contains duplicate key $key"
  loaded_env_keys[$key]=1
  if [[ "$value" == \"* || "$value" == *\" || "$value" == \'* || "$value" == *\' ]]; then
    if [[ "$value" == \"*\" || "$value" == \'*\' ]]; then
      value="${value:1:${#value}-2}"
    else
      fail "Production env file contains unmatched quotes for $key"
    fi
  fi
  loaded_env_values[$key]="$value"
done < "$ENV_FILE"

# The documented template is the allowlist. This blocks misspelled settings and
# Compose/runner control variables from silently redirecting a release to a
# different project, daemon or toolchain.
ENV_TEMPLATE="$ROOT_DIR/.env.production.example"
[[ -f "$ENV_TEMPLATE" && ! -L "$ENV_TEMPLATE" ]] \
  || fail "Tracked production environment template is missing or unsafe"
declare -A documented_env_keys=()
while IFS= read -r template_line || [[ -n "$template_line" ]]; do
  template_line="${template_line%$'\r'}"
  [[ -z "$template_line" || "$template_line" =~ ^[[:space:]]*# ]] && continue
  [[ "$template_line" =~ ^([A-Z][A-Z0-9_]*)= ]] \
    || fail "Tracked production environment template contains an invalid assignment"
  documented_key="${BASH_REMATCH[1]}"
  [[ ! "$documented_key" =~ ^(COMPOSE_|DOCKER_|BUILDKIT_) ]] \
    || fail "Tracked production environment template contains a forbidden runtime control key"
  documented_env_keys[$documented_key]=1
done < "$ENV_TEMPLATE"
for loaded_key in "${!loaded_env_keys[@]}"; do
  [[ -n "${documented_env_keys[$loaded_key]+x}" ]] \
    || fail "Production env file contains undocumented key $loaded_key"
  value="${loaded_env_values[$loaded_key]}"
  [[ -z "$value" ]] && continue
  lowered_value="${value,,}"
  if [[ "$lowered_value" =~ (change-me|dev-only|123456|mock|sandbox|placeholder|replace-with) ]]; then
    fail "$loaded_key contains an unsafe placeholder-like value"
  fi
  if [[ "$loaded_key" =~ SECRET|TOKEN|PASSWORD ]] && [[ ! "$loaded_key" =~ _FILE$ ]] \
     && [[ "$loaded_key" != "MONITORING_SECRET_GID" ]]; then
    [[ ${#value} -ge 32 ]] || fail "$loaded_key must be at least 32 characters"
    [[ "$value" =~ ^[A-Za-z0-9._~+/=-]+$ ]] \
      || fail "$loaded_key must use URL-safe ASCII without dotenv or shell metacharacters"
  fi
done

required=(
  RELEASE_ID
  RELEASE_REVISION
  DATABASE_MIGRATION_EVIDENCE_FILE
  MYSQL_ROOT_PASSWORD
  MYSQL_APP_USER
  MYSQL_APP_PASSWORD
  CRAWLER_DB
  CRAWLER_DB_USER
  CRAWLER_DB_PASSWORD
  REDIS_PASSWORD
  ADMIN_JWT_SECRET
  COOKIE_CRYPTO_SECRET
  INTERNAL_API_TOKEN
  IMAGE_PROXY_ALLOWED_HOSTS
  AI_PROVIDER_ALLOWED_HOSTS
  JWT_EXPIRE_SECONDS
  MEDIA_COOKIE_SECURE
  MEDIA_SESSION_MAX_AGE_SECONDS
  UPLOAD_TENANT_QUOTA_BYTES
  UPLOAD_GLOBAL_QUOTA_BYTES
  UPLOAD_RATE_LIMIT_REQUESTS
  UPLOAD_RATE_LIMIT_WINDOW_SECONDS
  UPLOAD_MAX_CONCURRENT_PER_TENANT
  UPLOAD_MAX_CONCURRENT_GLOBAL
  UPLOAD_RETENTION_DAYS
  JWT_ISSUER
  JWT_AUDIENCE
  ADMIN_CORS_ALLOWED_ORIGINS
  USER_CORS_ALLOWED_ORIGINS
  CRAWLER_CORS_ALLOWED_ORIGINS
  BACKEND_PORT
  USER_WEB_PORT
  ADMIN_WEB_PORT
  MONITORING_ENABLED
  MYSQL_MEMORY_LIMIT_BYTES
  MYSQL_CPUS
  MYSQL_PIDS_LIMIT
  REDIS_MEMORY_LIMIT_BYTES
  REDIS_CPUS
  REDIS_PIDS_LIMIT
  POSTGRES_MEMORY_LIMIT_BYTES
  POSTGRES_CPUS
  POSTGRES_PIDS_LIMIT
  CORE_API_MEMORY_LIMIT_BYTES
  CORE_API_CPUS
  CORE_API_PIDS_LIMIT
  AUTOMATION_API_MEMORY_LIMIT_BYTES
  AUTOMATION_API_CPUS
  AUTOMATION_API_PIDS_LIMIT
  AUTOMATION_WORKER_MEMORY_LIMIT_BYTES
  AUTOMATION_WORKER_CPUS
  AUTOMATION_WORKER_PIDS_LIMIT
  CRAWLER_API_MEMORY_LIMIT_BYTES
  CRAWLER_API_CPUS
  CRAWLER_API_PIDS_LIMIT
  CRAWLER_WORKER_MEMORY_LIMIT_BYTES
  CRAWLER_WORKER_CPUS
  CRAWLER_WORKER_PIDS_LIMIT
  USER_WEB_MEMORY_LIMIT_BYTES
  USER_WEB_CPUS
  USER_WEB_PIDS_LIMIT
  ADMIN_WEB_MEMORY_LIMIT_BYTES
  ADMIN_WEB_CPUS
  ADMIN_WEB_PIDS_LIMIT
)

# Monitoring-specific keys are only required when MONITORING_ENABLED=true.
required_monitoring=(
  OPS_METRICS_TOKEN
  OPS_METRICS_TOKEN_FILE
  ALERTMANAGER_WEBHOOK_URL_FILE
  MONITORING_SECRET_GID
  GRAFANA_ADMIN_PASSWORD_FILE
  GRAFANA_ROOT_URL
  BLACKBOX_MEMORY_LIMIT_BYTES
  BLACKBOX_CPUS
  BLACKBOX_PIDS_LIMIT
  ALERTMANAGER_MEMORY_LIMIT_BYTES
  ALERTMANAGER_CPUS
  ALERTMANAGER_PIDS_LIMIT
  PROMETHEUS_MEMORY_LIMIT_BYTES
  PROMETHEUS_CPUS
  PROMETHEUS_PIDS_LIMIT
  GRAFANA_MEMORY_LIMIT_BYTES
  GRAFANA_CPUS
  GRAFANA_PIDS_LIMIT
  PROMETHEUS_RETENTION_SIZE
)

for required_key in "${required[@]}"; do
  value="${loaded_env_values[$required_key]:-}"
  [[ -n "$value" ]] || fail "Required variable $required_key is empty"
  # required_key comes only from the fixed array above; arbitrary dotenv keys
  # never become shell variables and therefore cannot replace PATH/PYTHON_BIN.
  printf -v "$required_key" '%s' "$value"
  export "$required_key"
  ok "$required_key is present"
done

# Validate MONITORING_ENABLED and conditionally enforce monitoring requirements.
if [[ "$MONITORING_ENABLED" != "true" && "$MONITORING_ENABLED" != "false" ]]; then
  fail "MONITORING_ENABLED must be 'true' or 'false'"
fi
if [[ "$MONITORING_ENABLED" == "true" ]]; then
  for required_key in "${required_monitoring[@]}"; do
    value="${loaded_env_values[$required_key]:-}"
    [[ -n "$value" ]] || fail "Required variable $required_key is empty (MONITORING_ENABLED=true)"
    printf -v "$required_key" '%s' "$value"
    export "$required_key"
    ok "$required_key is present"
  done
else
  ok "Monitoring disabled (MONITORING_ENABLED=false); skipping monitoring keys"
fi

for identity_key in MYSQL_APP_USER CRAWLER_DB_USER CRAWLER_DB; do
  identity_value="${!identity_key}"
  [[ "$identity_value" =~ ^[a-z][a-z0-9_]{2,31}$ ]] \
    || fail "$identity_key must be a canonical lowercase database identifier"
done
[[ "$MYSQL_APP_USER" != "root" && "$MYSQL_APP_USER" != "mysql" ]] \
  || fail "MYSQL_APP_USER must be a least-privilege application identifier"
[[ "$CRAWLER_DB_USER" != "root" && "$CRAWLER_DB_USER" != "postgres" ]] \
  || fail "CRAWLER_DB_USER must be a least-privilege application identifier"

if [[ -n "$EXPECTED_RELEASE_REVISION" ]]; then
  [[ "$EXPECTED_RELEASE_REVISION" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] \
    || fail "Expected release revision must be an immutable lowercase Git commit SHA"
  [[ "$RELEASE_REVISION" == "$EXPECTED_RELEASE_REVISION" ]] \
    || fail "RELEASE_REVISION does not match the Git revision selected by the deploy entrypoint"
  ok "Remote environment release revision matches the deploy entrypoint"
fi

if [[ -n "$EXPECTED_RELEASE_REVISION" || -n "$EXPECTED_RELEASE_ID" || -n "$EXPECTED_MIGRATION_EVIDENCE_SHA256" ]]; then
  [[ -n "$EXPECTED_RELEASE_REVISION" && -n "$EXPECTED_RELEASE_ID" && -n "$EXPECTED_MIGRATION_EVIDENCE_SHA256" ]] \
    || fail "Expected release revision, release ID, and migration evidence SHA-256 must be supplied together"
  [[ "$EXPECTED_RELEASE_ID" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$ ]] \
    || fail "Expected release ID is invalid"
  [[ "$RELEASE_ID" == "$EXPECTED_RELEASE_ID" ]] \
    || fail "RELEASE_ID does not match the release selected by the deploy entrypoint"
  [[ "$EXPECTED_MIGRATION_EVIDENCE_SHA256" =~ ^[0-9a-f]{64}$ ]] \
    || fail "Expected migration evidence SHA-256 is invalid"
  ok "Remote environment release ID matches the deploy entrypoint"
fi

ADMIN_CORS_ALLOWED_ORIGIN_PATTERNS="${loaded_env_values[ADMIN_CORS_ALLOWED_ORIGIN_PATTERNS]:-}"
USER_CORS_ALLOWED_ORIGIN_PATTERNS="${loaded_env_values[USER_CORS_ALLOWED_ORIGIN_PATTERNS]:-}"
ADMIN_SEED_ENABLED="${loaded_env_values[ADMIN_SEED_ENABLED]:-false}"
PAYMENT_SANDBOX_ENABLED="${loaded_env_values[PAYMENT_SANDBOX_ENABLED]:-false}"

read_monitoring_secret_file() {
  local variable_name="$1"
  local path="$2"
  local output_name="$3"
  local value line_count mode owner group current_user parent parent_mode parent_owner parent_group resolved

  [[ "$path" = /* ]] || fail "$variable_name must be an absolute operator-managed path"
  [[ -f "$path" ]] || fail "$variable_name does not point to a regular file"
  [[ ! -L "$path" ]] || fail "$variable_name must not point to a symbolic link"
  resolved="$(readlink -f -- "$path" 2>/dev/null)" || fail "Cannot resolve $variable_name"
  [[ "$resolved" == "$path" ]] || fail "$variable_name path must not contain symbolic links or traversal"
  line_count="$(awk 'END { print NR }' "$path")"
  [[ "$line_count" == "1" ]] || fail "$variable_name must contain exactly one line"
  value="$(head -n 1 "$path")"
  [[ -n "$value" ]] || fail "$variable_name must not be empty"

  mode="$(stat -c '%a' "$path" 2>/dev/null)" || fail "Cannot inspect permissions for $variable_name"
  [[ "$mode" == "440" || "$mode" == "640" ]] \
    || fail "$variable_name must use 0440 or 0640 permissions for the dedicated monitoring group"
  owner="$(stat -c '%u' "$path" 2>/dev/null)" || fail "Cannot inspect owner for $variable_name"
  group="$(stat -c '%g' "$path" 2>/dev/null)" || fail "Cannot inspect group for $variable_name"
  current_user="$(id -u)"
  [[ "$owner" == "0" || "$owner" == "$current_user" ]] \
    || fail "$variable_name must be owned by root or the deployment operator"
  [[ "$group" == "$MONITORING_SECRET_GID" ]] \
    || fail "$variable_name group must match MONITORING_SECRET_GID"

  parent="$(dirname -- "$path")"
  [[ -d "$parent" && ! -L "$parent" ]] || fail "$variable_name parent must be a real directory"
  parent_mode="$(stat -c '%a' "$parent" 2>/dev/null)" || fail "Cannot inspect parent permissions for $variable_name"
  parent_owner="$(stat -c '%u' "$parent" 2>/dev/null)" || fail "Cannot inspect parent owner for $variable_name"
  parent_group="$(stat -c '%g' "$parent" 2>/dev/null)" || fail "Cannot inspect parent group for $variable_name"
  [[ "$parent_mode" == "750" ]] \
    || fail "$variable_name parent directory must use 0750 permissions"
  [[ "$parent_owner" == "0" || "$parent_owner" == "$current_user" ]] \
    || fail "$variable_name parent directory must be owned by root or the deployment operator"
  [[ "$parent_group" == "$MONITORING_SECRET_GID" ]] \
    || fail "$variable_name parent directory group must match MONITORING_SECRET_GID"
  printf -v "$output_name" '%s' "$value"
}

metrics_token_file_value=""
incident_webhook_url=""
grafana_admin_password=""
if [[ "$MONITORING_ENABLED" == "true" ]]; then
  [[ "$MONITORING_SECRET_GID" =~ ^[1-9][0-9]{2,4}$ ]] \
    || fail "MONITORING_SECRET_GID must be a canonical numeric dedicated group between 100 and 65533"
  if (( MONITORING_SECRET_GID < 100 || MONITORING_SECRET_GID > 65533 )); then
    fail "MONITORING_SECRET_GID must be a canonical numeric dedicated group between 100 and 65533"
  fi
  read_monitoring_secret_file "OPS_METRICS_TOKEN_FILE" "$OPS_METRICS_TOKEN_FILE" metrics_token_file_value
  read_monitoring_secret_file "ALERTMANAGER_WEBHOOK_URL_FILE" "$ALERTMANAGER_WEBHOOK_URL_FILE" incident_webhook_url
  read_monitoring_secret_file "GRAFANA_ADMIN_PASSWORD_FILE" "$GRAFANA_ADMIN_PASSWORD_FILE" grafana_admin_password
  [[ "$metrics_token_file_value" == "$OPS_METRICS_TOKEN" ]] || fail "OPS_METRICS_TOKEN_FILE does not match OPS_METRICS_TOKEN"
  [[ "$incident_webhook_url" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?(/[^[:space:]]*)?$ ]] \
    || fail "ALERTMANAGER_WEBHOOK_URL_FILE must contain one credential-free HTTPS URL"
  [[ "$grafana_admin_password" =~ ^[A-Za-z0-9._~+/=-]{32,}$ ]] \
    || fail "GRAFANA_ADMIN_PASSWORD_FILE must contain at least 32 URL-safe ASCII characters"
  [[ "$grafana_admin_password" != "$metrics_token_file_value" ]] \
    || fail "Grafana and metrics credentials must be distinct"
  [[ "$GRAFANA_ROOT_URL" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?(/[^[:space:]]*)?$ ]] \
    || fail "GRAFANA_ROOT_URL must be an explicit HTTPS URL"
  ok "Monitoring secret files and public Grafana URL passed"
else
  ok "Monitoring disabled; skipping monitoring secret file checks"
fi

[[ "$DATABASE_MIGRATION_EVIDENCE_FILE" = /* ]] || fail "DATABASE_MIGRATION_EVIDENCE_FILE must be an absolute operator-owned path"
if [[ -n "$EXPECTED_MIGRATION_EVIDENCE_SHA256" ]]; then
  command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required to bind migration evidence"
  actual_migration_evidence_sha256="$(sha256sum -- "$DATABASE_MIGRATION_EVIDENCE_FILE" 2>/dev/null)" \
    || fail "Cannot hash the remote migration evidence file"
  actual_migration_evidence_sha256="${actual_migration_evidence_sha256%% *}"
  [[ "$actual_migration_evidence_sha256" == "$EXPECTED_MIGRATION_EVIDENCE_SHA256" ]] \
    || fail "Remote migration evidence does not match the locally validated evidence"
  ok "Remote migration evidence bytes match the deploy entrypoint"
fi
if ! "$PYTHON_BIN" "$ROOT_DIR/scripts/validate_migrations.py" \
  --root "$ROOT_DIR" \
  --manifest "$ROOT_DIR/db/migrations-manifest.json" \
  --production \
  --evidence-file "$DATABASE_MIGRATION_EVIDENCE_FILE" \
  --release-id "$RELEASE_ID" \
  --release-revision "$RELEASE_REVISION"; then
  fail "Migration manifest or backup/restore evidence validation failed"
fi
if [[ -n "$EXPECTED_MIGRATION_EVIDENCE_SHA256" ]]; then
  verified_migration_evidence_sha256="$(sha256sum -- "$DATABASE_MIGRATION_EVIDENCE_FILE" 2>/dev/null)" \
    || fail "Cannot re-hash the remote migration evidence file"
  verified_migration_evidence_sha256="${verified_migration_evidence_sha256%% *}"
  [[ "$verified_migration_evidence_sha256" == "$EXPECTED_MIGRATION_EVIDENCE_SHA256" ]] \
    || fail "Remote migration evidence changed while it was being validated"
  ok "Remote migration evidence remained byte-identical during validation"
fi
ok "Migration manifest and recovery evidence passed"

declare -A seen_production_credentials=()
for credential_key in \
  MYSQL_ROOT_PASSWORD MYSQL_APP_PASSWORD CRAWLER_DB_PASSWORD REDIS_PASSWORD \
  ADMIN_JWT_SECRET COOKIE_CRYPTO_SECRET INTERNAL_API_TOKEN; do
  credential_value="${!credential_key}"
  [[ -z "${seen_production_credentials[$credential_value]+x}" ]] \
    || fail "Production credentials must be distinct"
  seen_production_credentials[$credential_value]=1
done
if [[ "$MONITORING_ENABLED" == "true" ]]; then
  credential_value="${OPS_METRICS_TOKEN}"
  [[ -z "${seen_production_credentials[$credential_value]+x}" ]] \
    || fail "Production credentials must be distinct"
  seen_production_credentials[$credential_value]=1
  [[ -z "${seen_production_credentials[$grafana_admin_password]+x}" ]] \
    || fail "Production credentials must be distinct"
  seen_production_credentials[$grafana_admin_password]=1
fi
ok "Production credential separation passed"

for key in ADMIN_CORS_ALLOWED_ORIGINS USER_CORS_ALLOWED_ORIGINS CRAWLER_CORS_ALLOWED_ORIGINS; do
  value="${!key}"
  [[ "$value" != *"*"* ]] || fail "$key must not contain wildcard origins"
  IFS=',' read -ra origins <<< "$value"
  for origin in "${origins[@]}"; do
    [[ "$origin" =~ ^https://[A-Za-z0-9.-]+(:[0-9]+)?$ ]] || fail "$key must contain explicit HTTPS origins only"
  done
done

IFS=',' read -ra ai_provider_hosts <<< "$AI_PROVIDER_ALLOWED_HOSTS"
for rule in "${ai_provider_hosts[@]}"; do
  [[ -n "$rule" && "$rule" != *" "* && "$rule" != *".."* ]] \
    || fail "AI_PROVIDER_ALLOWED_HOSTS contains an invalid host rule"
  host="$rule"
  [[ "$host" != \*.* ]] || host="${host#*.}"
  [[ "$host" == *.* && "$host" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$ \
      && ! "$host" =~ ^[0-9.]+$ ]] \
    || fail "AI_PROVIDER_ALLOWED_HOSTS contains an invalid host rule"
done
ok "AI provider outbound allowlist passed"

[[ "${ADMIN_CORS_ALLOWED_ORIGIN_PATTERNS:-}" == "" ]] || fail "ADMIN_CORS_ALLOWED_ORIGIN_PATTERNS must be empty in production"
[[ "${USER_CORS_ALLOWED_ORIGIN_PATTERNS:-}" == "" ]] || fail "USER_CORS_ALLOWED_ORIGIN_PATTERNS must be empty in production"

[[ "$JWT_EXPIRE_SECONDS" =~ ^[0-9]+$ ]] || fail "JWT_EXPIRE_SECONDS must be an integer"
if (( JWT_EXPIRE_SECONDS < 300 || JWT_EXPIRE_SECONDS > 3600 )); then
  fail "JWT_EXPIRE_SECONDS must be between 300 and 3600"
fi

[[ "$MEDIA_COOKIE_SECURE" == "true" ]] || fail "MEDIA_COOKIE_SECURE must be true in production"
[[ "$MEDIA_SESSION_MAX_AGE_SECONDS" =~ ^[0-9]+$ ]] || fail "MEDIA_SESSION_MAX_AGE_SECONDS must be an integer"
if (( MEDIA_SESSION_MAX_AGE_SECONDS < 60 || MEDIA_SESSION_MAX_AGE_SECONDS > 1200 || MEDIA_SESSION_MAX_AGE_SECONDS > JWT_EXPIRE_SECONDS )); then
  fail "MEDIA_SESSION_MAX_AGE_SECONDS must be between 60 and 1200 and not exceed JWT_EXPIRE_SECONDS"
fi

# Keep the release gate aligned with the Java and Python startup guards.  A
# syntactically valid Compose model is not enough: zero, inverted, or
# unbounded storage limits would otherwise be discovered only after the live
# source cutover and force an avoidable rollback.
for key in \
  UPLOAD_TENANT_QUOTA_BYTES \
  UPLOAD_GLOBAL_QUOTA_BYTES \
  UPLOAD_RATE_LIMIT_REQUESTS \
  UPLOAD_RATE_LIMIT_WINDOW_SECONDS \
  UPLOAD_MAX_CONCURRENT_PER_TENANT \
  UPLOAD_MAX_CONCURRENT_GLOBAL \
  UPLOAD_RETENTION_DAYS; do
  value="${!key}"
  [[ "$value" =~ ^[1-9][0-9]{0,13}$ ]] || fail "$key must be a positive canonical integer"
done

if (( UPLOAD_TENANT_QUOTA_BYTES < 5242880 || UPLOAD_TENANT_QUOTA_BYTES > 1099511627776 )); then
  fail "UPLOAD_TENANT_QUOTA_BYTES must be between 5 MiB and 1 TiB"
fi
if (( UPLOAD_GLOBAL_QUOTA_BYTES < UPLOAD_TENANT_QUOTA_BYTES || UPLOAD_GLOBAL_QUOTA_BYTES > 10995116277760 )); then
  fail "UPLOAD_GLOBAL_QUOTA_BYTES must be at least the tenant quota and at most 10 TiB"
fi
if (( UPLOAD_RATE_LIMIT_REQUESTS < 1 || UPLOAD_RATE_LIMIT_REQUESTS > 10000 )); then
  fail "UPLOAD_RATE_LIMIT_REQUESTS must be between 1 and 10000"
fi
if (( UPLOAD_RATE_LIMIT_WINDOW_SECONDS < 1 || UPLOAD_RATE_LIMIT_WINDOW_SECONDS > 3600 )); then
  fail "UPLOAD_RATE_LIMIT_WINDOW_SECONDS must be between 1 and 3600"
fi
if (( UPLOAD_MAX_CONCURRENT_PER_TENANT < 1 || UPLOAD_MAX_CONCURRENT_PER_TENANT > 100 )); then
  fail "UPLOAD_MAX_CONCURRENT_PER_TENANT must be between 1 and 100"
fi
if (( UPLOAD_MAX_CONCURRENT_GLOBAL < UPLOAD_MAX_CONCURRENT_PER_TENANT || UPLOAD_MAX_CONCURRENT_GLOBAL > 1000 )); then
  fail "UPLOAD_MAX_CONCURRENT_GLOBAL must be at least the tenant limit and at most 1000"
fi
if (( UPLOAD_RETENTION_DAYS < 1 || UPLOAD_RETENTION_DAYS > 3650 )); then
  fail "UPLOAD_RETENTION_DAYS must be between 1 and 3650"
fi
ok "Upload quota, rate, concurrency, and retention limits passed"

# Compose must never start the commercial stack with unbounded memory, CPU or
# process counts. These checks validate syntax and broad safety bounds only;
# the approved values still have to come from production-like capacity tests.
validate_resource_ceiling() {
  local prefix="$1"
  local memory_key="${prefix}_MEMORY_LIMIT_BYTES"
  local cpu_key="${prefix}_CPUS"
  local pids_key="${prefix}_PIDS_LIMIT"
  local memory="${!memory_key}"
  local cpus="${!cpu_key}"
  local pids="${!pids_key}"
  local whole fraction cpu_millis

  [[ "$memory" =~ ^[1-9][0-9]{7,11}$ ]] \
    || fail "$memory_key must be a canonical byte count"
  if (( memory < 67108864 || memory > 274877906944 )); then
    fail "$memory_key must be between 64 MiB and 256 GiB"
  fi

  [[ "$cpus" =~ ^([0-9]|[1-9][0-9])([.]([0-9]{1,3}))?$ ]] \
    || fail "$cpu_key must be a canonical decimal CPU limit"
  whole="${BASH_REMATCH[1]}"
  fraction="${BASH_REMATCH[3]:-0}000"
  fraction="${fraction:0:3}"
  cpu_millis=$((10#$whole * 1000 + 10#$fraction))
  if (( cpu_millis < 100 || cpu_millis > 64000 )); then
    fail "$cpu_key must be between 0.1 and 64 CPUs"
  fi

  [[ "$pids" =~ ^[1-9][0-9]{1,4}$ ]] \
    || fail "$pids_key must be a canonical process limit"
  if (( pids < 32 || pids > 32768 )); then
    fail "$pids_key must be between 32 and 32768"
  fi
}

for resource_prefix in \
  MYSQL REDIS POSTGRES CORE_API AUTOMATION_API AUTOMATION_WORKER \
  CRAWLER_API CRAWLER_WORKER USER_WEB ADMIN_WEB; do
  validate_resource_ceiling "$resource_prefix"
done
if [[ "$MONITORING_ENABLED" == "true" ]]; then
  for resource_prefix in \
    BLACKBOX ALERTMANAGER PROMETHEUS GRAFANA; do
    validate_resource_ceiling "$resource_prefix"
  done
  [[ "$PROMETHEUS_RETENTION_SIZE" =~ ^[1-9][0-9]{0,5}(MB|GB|TB)$ ]] \
    || fail "PROMETHEUS_RETENTION_SIZE must be an explicit MB, GB, or TB ceiling"
fi
ok "Production resource ceilings passed"

if [[ "${ADMIN_SEED_ENABLED:-false}" == "true" ]]; then
  warn "ADMIN_SEED_ENABLED=true should only be used for one-time bootstrap, not steady-state production"
fi

if [[ -n "${PAYMENT_SANDBOX_ENABLED:-}" && "$PAYMENT_SANDBOX_ENABLED" != "false" && "$PAYMENT_SANDBOX_ENABLED" != "0" ]]; then
  fail "Payment sandbox must be disabled in production preflight"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  (cd "$ROOT_DIR" && docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    -f docker-compose.monitoring.yml \
    --profile monitoring \
    --env-file "$ENV_FILE" config --quiet)
  ok "production compose overlay validated without writing rendered secrets"
else
  fail "docker compose is required for production config validation"
fi

ok "Production preflight passed for $ENV_FILE"
