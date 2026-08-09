# Production Topology

- China backend host: `/home/ubuntu/project`
- China backend runtime: `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production`
- Hong Kong user frontend root: `/var/www/user-web`
- Hong Kong admin frontend root: `/var/www/admin-web`
- Hong Kong Nginx config: `/etc/nginx/sites-enabled/nginx-full.conf`

# Deploy Commands

- All:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target all`
- Backend only:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target backend`
- Frontend only:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target frontend`
- Preview only:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target all -DryRun`

# Official URLs

- User frontend: `http://64.90.31.68:81/#/login`
- Admin frontend: `http://64.90.31.68:82/#/auth/login`
- China user health: `http://211.161.232.54:18080/api/health`
- China admin health: `http://211.161.232.54:18080/admin-api/health`

# Log Locations

- China backend logs:
  - `cd /home/ubuntu/project && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs --tail=400 backend`
- China automation logs:
  - `cd /home/ubuntu/project && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs --tail=400 automation`
- Hong Kong Nginx access log:
  - `/var/log/nginx/access.log`
- Hong Kong Nginx error log:
  - `/var/log/nginx/error.log`

# High-Value Checks

- Confirm `xianyu-admin-backend` is healthy after backend deploy.
- Confirm user login and admin login API both return `code=200`.
- Confirm changed modules do not introduce fresh `bad SQL grammar`, `Unhandled exception`, `403`, `502`, or `504` patterns.
- For auth or proxy changes, run a real browser login on the user frontend.

# Focused Smoke Tests

- Admin login payload uses `userName`, not `username`:
  - `POST http://64.90.31.68:82/admin-api/auth/login`
- User login payload uses `username`:
  - `POST http://64.90.31.68:81/api/login/login`
- Billing page smoke checks:
  - `GET /admin-api/ai-billing/summary`
  - `GET /admin-api/ai-billing/model-prices/page?current=1&size=20`
- Online message smoke checks:
  - `GET /api/msg/online/conversations?xianyuAccountId=<id>&pageSize=20`
  - `POST /api/msg/context`

# Known Failure Modes

- Hong Kong login `403`:
  - Usually caused by China backend CORS whitelist drift.
  - Check `.env.production` on the China host for:
    - `USER_CORS_ALLOWED_ORIGINS`
    - `ADMIN_CORS_ALLOWED_ORIGINS`
- SSE `504` on user frontend:
  - Usually caused by missing special-case proxy handling for `/api/sse/subscribe` in Hong Kong Nginx.
- Admin dashboard warnings:
  - Usually caused by production schema drift.
  - Check `SchemaCompatibilityRunner` and recent backend logs.
- Online messages page shows `Unknown column 'xm.msg_time'`:
  - Usually caused by production `xianyu_message` schema drift.
  - Confirm `SchemaCompatibilityRunner` has added compatibility columns before changing page code.
- Billing or token pages fail with missing table errors:
  - Usually caused by absent `ai_model_price_config` or `token_balance_ledger`.
  - Confirm startup compatibility SQL ran successfully.
- Backend starts and exits during production boot:
  - Check whether `DataInitializer` is still trying to run legacy DDL.
  - Fresh healthy logs should include `prod-like profile detected, skipping legacy DataInitializer DDL`.
