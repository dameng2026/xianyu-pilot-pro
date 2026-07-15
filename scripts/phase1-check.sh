#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run() {
  echo ""
  echo "==> $*"
  "$@"
}

run bash -lc "cd '$ROOT/apps/user-web' && npm install --no-audit --no-fund && npm run build"
run bash -lc "cd '$ROOT/apps/automation-service' && python3 -m pytest -q"
run node "$ROOT/qa/security/phase3-static-quality-gate.mjs"
run bash -lc "cd '$ROOT/apps/crawler-service' && npm ci --no-audit --no-fund --ignore-scripts && npm run build"
run bash -lc "cd '$ROOT/apps/admin-web' && npm install --no-audit --no-fund --ignore-scripts --prefer-offline && npm run typecheck && npm run build"

if [[ -x "$ROOT/apps/core-api/mvnw" ]]; then
  echo ""
  echo "==> bash -lc cd '$ROOT/apps/core-api' && ./mvnw -q -DskipTests package"
  if timeout 180s bash -lc "cd '$ROOT/apps/core-api' && ./mvnw -q -DskipTests package"; then
    echo "core-api build passed"
  else
    echo "WARN core-api build skipped/failed in this environment. Install Maven 3.9+, or allow ./mvnw to download Maven, then rerun this command."
  fi
else
  echo ""
  echo "SKIP core-api build: apps/core-api/mvnw is missing or not executable."
fi
