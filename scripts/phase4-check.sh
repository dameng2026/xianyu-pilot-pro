#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
SKIP_JAVA="${SKIP_JAVA:-0}"

title() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
run() { title "$1"; shift; (cd "$ROOT_DIR" && "$@"); }

run "Static security and architecture gate" node qa/security/phase3-static-quality-gate.mjs

if [[ "$SKIP_INSTALL" != "1" ]]; then
  run "Install user-web dependencies" bash -lc 'cd apps/user-web && npm install --no-audit --no-fund --ignore-scripts'
fi
run "Build user-web" bash -lc 'cd apps/user-web && npm run build'

if [[ "$SKIP_INSTALL" != "1" ]]; then
  run "Install admin-web dependencies" bash -lc 'cd apps/admin-web && npm install --no-audit --no-fund --ignore-scripts --prefer-offline'
fi
run "Typecheck admin-web" bash -lc 'cd apps/admin-web && npm run typecheck'
run "Build admin-web" bash -lc 'cd apps/admin-web && npm run build'

if [[ "$SKIP_INSTALL" != "1" ]]; then
  run "Install crawler-service dependencies" bash -lc 'cd apps/crawler-service && npm install --no-audit --no-fund --ignore-scripts'
fi
run "Build crawler-service" bash -lc 'cd apps/crawler-service && npm run build'

run "Automation-service tests" bash -lc 'cd apps/automation-service && python3 -m pytest -q'

if [[ "$SKIP_JAVA" != "1" ]]; then
  title "Core API Java compile"
  if command -v mvn >/dev/null 2>&1; then
    (cd "$ROOT_DIR/apps/core-api" && mvn -B -DskipTests package)
  else
    (cd "$ROOT_DIR/apps/core-api" && ./mvnw -q -DskipTests package)
  fi
else
  title "Core API Java compile skipped because SKIP_JAVA=1"
fi

title "Phase 4 checks completed"
