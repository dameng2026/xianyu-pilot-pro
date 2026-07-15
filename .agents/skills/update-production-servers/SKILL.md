---
name: update-production-servers
description: "Deploy this repository to the current production topology: China backend Docker Compose at `/home/ubuntu/project` and US user/admin frontends served by Nginx from `/var/www/user-web` and `/var/www/admin-web`. Use when the user asks to update server code, sync local changes to production, deploy or redeploy, publish online, verify production, update the China backend, update the US frontend, 更新服务器代码, 同步到服务器, 同步到生产, 发布上线, 重新部署, 更新国内后端, 更新美国前端, or perform a post-deploy smoke check."
---

# Update Production Servers

Use this skill to push local changes to the real production servers and verify the official services.

## Quick Start

- Run from the repo root.
- Infer the smallest safe deploy target:
  - `backend` for `apps/core-api`, schema, Docker Compose, automation, crawler, or backend config changes.
  - `frontend` for `apps/user-web`, `apps/admin-web`, or US static or Nginx-facing frontend changes.
  - `all` when the scope is mixed or unclear.
- Execute with the project wrapper:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target all`
  - Replace `all` with `backend` or `frontend` when the scope is narrower.
- Use `-DryRun` only when the user explicitly asks to preview the deploy without changing production.

## Workflow

1. Inspect the request and changed files.
2. Infer `backend`, `frontend`, or `all`.
3. Prefer `scripts/deploy-prod.ps1` over hand-written SSH copy or restart commands.
4. Let the deploy wrapper run its built-in smoke checks.
5. Run focused regression for the changed area before reporting success.
6. If deploy output looks successful but production is still unhealthy, continue with server-side diagnosis instead of stopping at the wrapper result.
7. Diagnose and fix failures before declaring production healthy.

## Verification Checklist

- Verify the official user frontend at `http://154.9.254.86:81/#/login`.
- Verify the official admin frontend at `http://154.9.254.86:82/#/auth/login`.
- Verify China backend health at `http://1.12.66.249:18080/api/health`.
- Verify China admin health at `http://1.12.66.249:18080/admin-api/health`.
- Verify user login and admin login API after deploy.
- Verify the touched modules, not just the homepage.
- Check fresh backend logs after exercising changed modules; do not ignore new `bad SQL grammar`, `Unhandled exception`, or repeated 4xx or 5xx errors.
- Check US Nginx logs when auth, CORS, SSE, or proxy behavior changed.
- For admin billing changes, verify:
  - `GET /admin-api/ai-billing/summary`
  - `GET /admin-api/ai-billing/model-prices/page?current=1&size=20`
- For online message changes, verify:
  - `GET /api/msg/online/conversations?xianyuAccountId=<id>&pageSize=20`
  - `POST /api/msg/context`

## Known Failure Modes

- Login `403` on the US frontend usually means the China backend CORS whitelist no longer includes `http://154.9.254.86:81` or `http://154.9.254.86:82`.
- SSE failures on `/api/sse/subscribe` usually point to the US Nginx proxy config in `/etc/nginx/sites-enabled/nginx-full.conf`.
- Admin dashboard warnings after deploy usually mean production schema drift; inspect `SchemaCompatibilityRunner` and recent backend logs.
- If the admin browser login is blocked by the slider gate, verify admin availability through `POST /admin-api/auth/login`, dashboard APIs, and, when needed, a browser session with injected login state.
- `Unknown column 'xm.msg_time'` on online messages usually means production `xianyu_message` schema drift; confirm `SchemaCompatibilityRunner` has patched the table before assuming the page code is wrong.
- Missing `ai_model_price_config` or `token_balance_ledger` usually means production billing tables were never created; confirm startup compatibility SQL ran successfully.
- Backend health down right after deploy can be caused by legacy `DataInitializer` DDL running in production. Check for `prod-like profile detected, skipping legacy DataInitializer DDL` in fresh logs.
- If a backend rebuild stalls for a long time, first verify whether the source sync completed and whether the running container is still using an old `app.jar`; do not assume the wrapper already refreshed the live container.

## Resources

- Read [references/troubleshooting.md](references/troubleshooting.md) for production topology, commands, log locations, and recovery tips.
- Read [docs/production-deploy.md](../../docs/production-deploy.md) when you need the longer repo-level deploy guide.

When the user clearly asks to deploy or sync production, execute the deploy flow instead of only describing it.
