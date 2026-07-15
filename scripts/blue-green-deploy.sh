#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' \
  '[deploy] UNSUPPORTED: this entrypoint does not perform blue/green deployment.' \
  '' \
  'The current Compose topology uses fixed container_name values and fixed host ports.' \
  'Two colors therefore cannot coexist on one host, so calling this workflow' \
  '"blue/green" would provide a false rollback and availability guarantee.' \
  '' \
  'No deployment commands were run.' \
  '' \
  'Supported production path:' \
  '  1. python scripts/prod_deploy.py --preflight-only --nginx-config <secure-nginx.conf>' \
  '  2. python scripts/prod_deploy.py --config <local-deploy-config.json> --target all' \
  '' \
  'That path stages frontend files before a rename-based directory cutover, validates Nginx,' \
  'uses a controlled in-place backend recreation, and requires health/smoke checks to' \
  'pass. The backend replacement can have a short interruption; it is not blue/green.' \
  '' \
  'Implement a real dual-stack topology (unique container names, networks, volumes,' \
  'unpublished target ports, and an atomic reverse-proxy switch) before re-enabling' \
  'this filename.' >&2

exit 64
