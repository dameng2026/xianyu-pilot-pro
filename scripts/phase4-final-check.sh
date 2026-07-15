#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

run() {
  echo "\n==> $*"
  "$@"
}

run node qa/security/phase3-static-quality-gate.mjs
run node --check qa/contracts/phase4-release-contract.test.mjs
run bash -n scripts/production-preflight.sh
run bash -n scripts/blue-green-deploy.sh

run npm --prefix apps/user-web ci --no-audit --no-fund --ignore-scripts
run npm --prefix apps/user-web run lint -- --quiet
run npm --prefix apps/user-web run test
run npm --prefix apps/user-web run build
run npm --prefix apps/user-web audit --omit=dev
if [[ -x /usr/bin/chromium || -n "${CHROMIUM_EXECUTABLE:-}" ]]; then
  (cd qa/e2e && CHROMIUM_EXECUTABLE="${CHROMIUM_EXECUTABLE:-/usr/bin/chromium}" run node userweb_bundle_smoke.mjs)
else
  echo "[warn] Chromium not found; skipped user-web bundle smoke."
fi

run npm --prefix apps/admin-web ci --no-audit --no-fund --ignore-scripts --prefer-offline
run npm --prefix apps/admin-web run lint -- --quiet
run npm --prefix apps/admin-web run typecheck
run npm --prefix apps/admin-web run build
run npm --prefix apps/admin-web audit --omit=dev

run npm --prefix apps/crawler-service ci --no-audit --no-fund --ignore-scripts
run npm --prefix apps/crawler-service run build
run npm --prefix apps/crawler-service audit --omit=dev

run python3 -m pytest -q apps/automation-service

if command -v mvn >/dev/null 2>&1; then
  (cd apps/core-api && run mvn -q -DskipTests package)
else
  echo "[warn] System Maven not found; Java package validation requires Maven or working ./mvnw download."
fi

echo "\nPhase 4 final local checks completed."
