# Production Deploy

This project has one supported **single-stack** deploy flow for the current production layout:

- China server: backend stack only (`/home/ubuntu/project`, Docker Compose)
- Hong Kong server (`<FRONTEND_SERVER_IP>`): user/admin frontends only (`/var/www/user-web`, `/var/www/admin-web`, Nginx)

## Files

- `scripts/prod_deploy.py`
  Python deploy entrypoint. Uploads code/build artifacts, restarts services, and runs smoke checks.
- `scripts/deploy-prod.ps1`
  Windows-friendly wrapper.
- `.deploy.prod.example.json`
  Template for deploy configuration.
- `.deploy.prod.json`
  Local machine deploy config. This file is ignored by git and can contain real server credentials.
- `scripts/blue-green-deploy.sh`
  Disabled fail-fast entrypoint. The current fixed container names and host ports cannot run two colors concurrently.

## Release model (read this first)

This topology is **not blue/green**. `scripts/prod_deploy.py` stages both backend source and frontend files before rename-based cutovers, but the backend containers are still recreated in place. A backend release can have a short interruption. Do not advertise zero downtime or instant color rollback for this topology.

Backend source activation is atomic at the directory-rename boundary. The uploaded archive is checksum-verified and extracted only into a new sibling staging directory; `tar` never writes into the live source tree. The server-owned env file is validated before activation. A relative env path, including an absolute spelling that resolves inside `project_dir`, is held outside the renamed trees and restored; a genuinely external absolute env path is never moved. Activation errors and HUP/INT/TERM restore the old source and env. Build, recreate, Docker-health, monitoring-health, or public backend-health failure restores the previous source, reapplies its infrastructure Compose model, rebuilds/recreates its runtime, and health-gates the rollback. A failed release remains under a timestamped `.failed-*` path for operator forensics.

The deploy entrypoint retains a version-guarded compensating action after each successful cutover until every selected component and the final public smoke gate have passed. If a later frontend build/cutover or smoke check fails, or the operator interrupts that final gate with Ctrl+C, it rolls completed cutovers back in reverse order: Hong Kong frontend files and Nginx first, then China backend source/runtime. One rollback failure does not prevent the other rollback from being attempted. Any incomplete compensation is reported explicitly and keeps the release failed; a nonzero command must never be interpreted as “nothing changed.” A process kill, host loss, or network partition can still prevent automatic compensation, so retained rollback state and the external incident runbook remain mandatory.

This is process-level rollback, not a database rollback or an immutable-image rollback. The prior source is rebuilt, so mutable base-image resolution, registry availability, or dependency availability can still prevent byte-identical recovery until the approved registry/signing gate retains digest-pinned application images. The very first deployment has no previous source to restore and therefore reports rollback failure explicitly. Do not delete `.previous-*`, `.failed-*`, or `.env-hold-*` paths until the incident is resolved and the live env location has been verified.

The backend bundle uses an explicit allowlist: the three backend application roots, monitoring configuration, Compose files, and the production environment example. A denylist omits environment files, real deployment configuration, HAR/session captures, token/cookie exports, root-level test/debug helpers, editor/agent backup files, logs, caches, build output, archives, and temporary artifacts. This includes workspace-local dependency/tool trees such as `.npm-cache`, `.npm-bootstrap-cache`, `.pnpm-store`, `.uv-cache`, `.uv-tools`, `.uv-tools-bin`, and `.tools`; they are never release inputs. The preflight also rejects secret-like tracked paths, literal secret assignments, embedded private keys, and symbolic links. It reports paths/reasons only, never secret values.

The tracked infrastructure baseline uses MySQL `8.4.10` LTS, Redis `7.4.9`, and PostgreSQL `16.14`. MySQL 8.0 is no longer an approved production line. Before the first release on this baseline, restore a recent backup into an isolated rehearsal environment, run vendor upgrade checks, exercise critical queries and jobs, measure the maintenance window, and prove restore-based rollback. Never point the new image at the only copy of a production volume.

## Mandatory release preflight

Read `docs/production-readiness.md` first. A passing script preflight does not override an unresolved go-live gate.

Run this before every dry run or deployment:

```powershell
$revision = (git rev-parse --verify HEAD).Trim().ToLowerInvariant()
python .\scripts\prod_deploy.py --preflight-only --nginx-config .\deploy\nginx\us-nginx-full.conf --release-id release-20260711-01 --release-revision $revision --migration-evidence C:\secure\xianyupilot\migration-evidence.json
```

The gate is read-only: it does not read `.deploy.prod.json`, build, open SSH, upload, restart, or deploy. When migration evidence is supplied, it resolves and verifies the clean Git `HEAD` itself, rejects a mismatched `--release-revision`, and validates the immutable migration manifest plus the operator-owned backup/restore evidence described in `docs/database-migrations.md`. The command-line revision is an assertion, not a trust anchor. A failure **must not be bypassed**.

The legacy environment/Compose check uses the same gate before it parses the environment file as data (it never sources the file as shell code). For a release-bound run, supply the exact release ID and SHA-256 of the already validated operator evidence from the release record:

```bash
bash scripts/production-preflight.sh .env.production deploy/nginx/us-nginx-full.conf "$(git rev-parse --verify HEAD)" release-20260711-01 "$MIGRATION_EVIDENCE_SHA256"
```

Its second argument is the candidate Nginx config. Release-bound arguments three through five are an all-or-nothing tuple: the exact Git SHA, release ID, and lowercase SHA-256 of the operator evidence selected by the deploy entrypoint. They must equal `RELEASE_REVISION`, `RELEASE_ID`, and the bytes at `DATABASE_MIGRATION_EVIDENCE_FILE` on the remote host before that evidence is validated. The supported deploy entrypoint computes and supplies this tuple automatically after checking that the local evidence did not change during validation. A source-only check may omit the whole tuple; it is not release evidence. Both public plaintext HTTP and HTTPS without explicit certificate verification fail closed before environment values are loaded. If the candidate uses the managed `127.0.0.1:18081` origin, the preflight also validates the hardening contract in `deploy/systemd/xianyupilot-origin-tunnel.service.template`.

The same preflight rejects an insecure media cookie, a media session longer
than the access JWT, and missing, inverted, zero, or out-of-range upload quota,
rate, concurrency, and retention limits before Compose build or source cutover.
This early validation complements, but does not replace, the Java and Python
startup guards.

The supported `deploy/nginx/us-nginx-full.conf` routes backend traffic through a loopback-only, pinned-host-key SSH tunnel. A frontend deploy checks that `xianyupilot-origin-tunnel.service` is active and that `/api/health` returns `UP` through the tunnel before it uploads or cuts over files. Public application vhosts accept decrypted HTTP only from a same-host loopback TLS terminator; direct port-80 requests are redirected to HTTPS except ACME challenges. The legacy `deploy/nginx/xianyupilot-ssl.conf` still contains a public plaintext origin and is intentionally blocked. Client-facing TLS and `X-Forwarded-Proto: https` do not encrypt the Hong Kong-to-China origin hop. Supported designs are:

- Verified HTTPS to the origin: use `https://`, `proxy_ssl_verify on`, `proxy_ssl_server_name on`, a trusted CA bundle, and preferably mTLS client authentication.
- The tracked managed SSH tunnel: loopback HTTP is carried inside SSH with strict host-key verification. The origin account must be restricted to the single `127.0.0.1:18080` forward.
- A private/VPN route: use an RFC1918 or IPv6 ULA address reachable only through an operator-verified tunnel/private network. Plain HTTP is acceptable only inside that protected route.

Never use public `http://` as the origin transport. Update the candidate Nginx config and rerun preflight until it passes; do not merely change the forwarded-protocol header.

The current QR session manager owns live browser handles in one crawler process. Production must keep `crawler-service` at one replica until sticky instance routing or a dedicated session-owning browser worker is implemented. Enforce outbound firewall/proxy rules in addition to the application-level private-address guards.

## One-time setup

1. Check `.deploy.prod.json`. Use SSH keys plus a host-key file verified out of band; the example intentionally contains no SSH passwords. Protect the deployment key outside the repository and rotate it under the operator key-management policy. `china_backend.project_dir` must be a canonical application directory below `/home`, `/opt`, `/srv`, `/data`, or `/var/www`; system trees, top-level roots, traversal, control characters, and a symlink/file at the live project path are rejected before extraction. Frontend live, backup, and staging roots must be distinct, non-overlapping canonical children of `/var/www`; the Nginx site must be a canonical child of `/etc/nginx`. This validation occurs before any build or remote mutation because those paths participate in rollback `mv`/removal operations.
2. Confirm the China server already has a valid `/home/ubuntu/project/.env.production`, owned by the deployment operator and mode `0400` or `0600`. Generate every direct password/token/secret independently as at least 32 URL-safe ASCII characters; values containing dotenv/shell metacharacters, privileged database usernames (`root`, `mysql`, `postgres`), reused credentials, placeholders or wildcard/non-HTTPS origins fail preflight. Set `AI_PROVIDER_ALLOWED_HOSTS` to the exact reviewed provider domains; use an explicit `*.` rule only when every subdomain is controlled and approved. Both saved provider URLs and every outbound text/image request are revalidated against this allowlist, use HTTPS/443, reject private/reserved DNS answers, and never follow redirects. The tracked example is the key allowlist: undocumented variables (including `COMPOSE_*`/`DOCKER_*` controls) are rejected, and deploy commands force the local default Docker context so an ambient shell cannot redirect the release to another project or daemon. Do not hand-edit a rendered Compose file or print the environment to debug a failure.
3. Verify each production SSH host fingerprint out of band and add it to the operator account's `~/.ssh/known_hosts` (or set `known_hosts_file` in the local host config). Unknown host keys are rejected; never restore trust-on-first-use for convenience.
4. Provision the managed tunnel before the first frontend release:
   - Create the unprivileged `xianyupilot-tunnel` system user/group on the Hong Kong host.
   - Install its private key as `/etc/xianyupilot-origin-tunnel/id_ed25519` and a fingerprint verified out of band as `/etc/xianyupilot-origin-tunnel/known_hosts`; make both readable only by that account.
   - On the China origin, restrict the public key with `restrict,permitopen="127.0.0.1:18080"` and do not grant shell or unrelated forwarding access.
   - Replace `__ORIGIN_USER__` in `deploy/systemd/xianyupilot-origin-tunnel.service.template`, install it as `/etc/systemd/system/xianyupilot-origin-tunnel.service`, run `systemctl daemon-reload`, enable/start it, and verify `curl --fail http://127.0.0.1:18081/api/health` returns an `UP` status.
   - Add monitoring for unit restarts, tunnel health, SSH host-key changes, and key expiry/rotation. A locally passing preflight does not prove these operator steps occurred.
5. Confirm local frontend dependencies are installed:
   - `apps/user-web`
   - `apps/admin-web`
6. Production sign-off requires the monitoring profile. Provision one dedicated host group and record its numeric GID as `MONITORING_SECRET_GID`. Create the host file named by `OPS_METRICS_TOKEN_FILE`; its single-line value must exactly match `OPS_METRICS_TOKEN`. Also create `ALERTMANAGER_WEBHOOK_URL_FILE` containing one approved HTTPS incident/on-call webhook URL and `GRAFANA_ADMIN_PASSWORD_FILE` containing a distinct administrator credential of at least 32 characters. All three files must be owned by root or the deployment operator, grouped to `MONITORING_SECRET_GID`, and mode `0440` or `0640`; their real, non-symlink parent directory must use the same group and mode `0750`. Do not use `0400`: [Docker documents that local Compose implements file secrets as bind mounts and cannot remap their ownership](https://docs.docker.com/reference/compose-file/services/#secrets), so the non-root monitoring processes would be unable to read them. The production Compose model grants the dedicated GID to Prometheus and Alertmanager and as a supplementary group to Grafana, while the parent directory denies access to other host users. Prometheus reads its bearer token, Alertmanager reads the receiver URL, and Grafana reads its administrator password as Docker secrets, so none is embedded in tracked YAML or a monitoring container environment. Start the profile explicitly with `docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.monitoring.yml --profile monitoring --env-file .env.production up -d`; merely adding the overlay file does not activate profiled services. Validate the Alertmanager configuration with `amtool check-config`, fire a synthetic warning and critical alert, and prove both firing and resolved notifications reach the on-call receiver before sign-off. The receiver must treat absence of the `XianyuWatchdog` heartbeat for ten minutes as a page, because an in-stack alert cannot report its own total delivery outage. Prometheus, Grafana, Alertmanager, and blackbox_exporter are health-gated; the blackbox probes must show `probe_success=1` for the core API, automation service, crawler service, user web, public API, and admin web, and the TLS-expiry series must exist. Monitoring UIs bind to loopback. Expose Grafana only through the authenticated HTTPS `GRAFANA_ROOT_URL`; Prometheus/Alertmanager diagnostics may use an approved SSH tunnel without public port binding. Back up all monitoring named volumes and rehearse migration/rollback on production-like data before first use.
7. Replace every resource placeholder in `.env.production` with memory-byte, CPU and PID ceilings approved by production-like load, spike, endurance and failure-injection evidence. `PROMETHEUS_RETENTION_SIZE` is also mandatory. The preflight validates broad bounds and the rendered Compose model, but it cannot prove the selected numbers meet the service SLO; retain the capacity report and rollback/alert thresholds with the release record.

## Daily commands

First run the mandatory read-only preflight above. The deploy entrypoint repeats the relevant checks before any build, SSH connection, or upload. Every real deployment also requires a valid Git `HEAD` and a completely clean worktree; an uncommitted or untracked source tree is rejected without printing potentially sensitive paths. It rechecks the same clean revision immediately before and after packaging each backend/frontend release artifact, so a background worktree change cannot silently ship under the earlier revision marker. If a direct caller supplies `--release-revision`, it must equal that independently resolved `HEAD`; the deploy script never silently trusts or ignores a conflicting revision assertion.

The protected CI environment must define the `NVD_API_KEY` repository secret. The Java job fails if it is absent, generates CycloneDX JSON/XML, runs NVD + CISA KEV vulnerability analysis with any scored finding treated as release-blocking, and uploads the resulting evidence under the exact Git SHA.

Deploy backend + frontends:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target all -ReleaseId release-20260711-01 -MigrationEvidence C:\secure\xianyupilot\migration-evidence.json
```

Deploy backend only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target backend -ReleaseId release-20260711-01 -MigrationEvidence C:\secure\xianyupilot\migration-evidence.json
```

`-Target backend` rebuilds and recreates only the `backend` service by default, then waits for health recovery. It does not run `up` for MySQL, Redis, PostgreSQL, `crawler-service`, or other runtime services unless you explicitly use the broader `all` target or extend the reviewed service lists. This prevents an ordinary API patch from implicitly upgrading stateful infrastructure. The mandatory monitoring containers must already be healthy before source cutover and are checked again after backend recovery; a narrow patch never treats a monitoring outage as an acceptable deployment state.

Deploy frontends only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target frontend
```

Preview commands without executing:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target all -DryRun -ReleaseId release-20260711-01 -MigrationEvidence C:\secure\xianyupilot\migration-evidence.json
```

Preview a deployment while intentionally skipping frontend local builds (real cutovers cannot skip them):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target frontend -DryRun -SkipFrontendBuild
```

## What the deploy script does

### Backend deploy

1. Requires a committed, clean Git revision, then runs the tracked-sensitive-file, bundle-secret, migration-manifest, and release-input preflight. The clean revision is checked again on both sides of bundle creation.
2. Packs only the explicit backend allowlist (`apps/core-api`, `apps/automation-service`, `apps/crawler-service`, migration/preflight tooling, the reviewed Nginx transport config, Compose files, monitoring files, and `.env.production.example`).
3. Uploads the bundle to the China server, verifies its SHA-256, and extracts it into a collision-checked sibling `.release-<Git-SHA>` directory. The live source tree is not an extraction target.
4. Runs the remote production preflight from the staged source against the server-owned environment, monitoring secret files, fully rendered production + monitoring Compose model, and the exact Git SHA, release ID, and byte-for-byte migration/recovery evidence SHA-256 selected locally. A different remote evidence document cannot satisfy the release binding merely by claiming the same revision.
5. Renames the old live source to `.previous-*`, renames the staged source into the live path, writes the exact `.release-revision` and per-cutover `.release-transaction`, and safely restores an in-tree env. A genuinely external absolute env remains untouched. Both markers are required before a later gate may invoke that cutover's rollback, preventing an older process from overwriting a newer release of the same revision.
6. For `-Target backend`, rebuilds and recreates only:
   - `backend`
7. Before any managed infrastructure `up`, compares each existing container's configured image with the reviewed baseline. Image drift fails closed with exit 42; the general deploy command never performs a database/cache major or patch migration implicitly. Complete the backup/migration runbook separately first.
8. For `-Target all`, ensures the already-approved infrastructure services are up, then rebuilds and recreates the runtime services:
   - `automation`
   - `automation-worker`
   - `crawler-service`
   - `crawler-worker`
   - `backend`
9. Recreates the mandatory `blackbox-exporter`, `alertmanager`, `prometheus`, and `grafana` monitoring profile so tracked rules/configuration take effect. `-Target backend` leaves that stack untouched but fail-closed checks all four containers before source activation and after backend recovery.
10. Requires every recreated runtime container and every mandatory monitoring container to report Docker `healthy`; `-Target backend` gates the backend plus the pre-existing monitoring stack, while `-Target all` gates all five runtime containers plus the four recreated monitoring containers. A missing container fails immediately instead of consuming the whole readiness timeout. It then waits for explicit `external_health_urls` or, by default, both public HTTPS backend health routes derived from `smoke`. Any failure after activation restores the previous source and env, reapplies the old infrastructure model, rebuilds/recreates the old runtime and monitoring stack as applicable, and requires the restored containers to become healthy. A nonzero or unreachable rollback is reported as a rollback failure instead of being silently treated as success. This remains a health-gated in-place replacement, not blue/green or zero-downtime rolling deployment.

### Frontend deploy

1. Rejects insecure Nginx origin transport before local builds or SSH.
2. Builds `apps/user-web`.
3. Runs `typecheck` + `build` for `apps/admin-web`.
4. Secret-scans and packs both `dist/` folders with the artifact denylist, then rechecks that builds/packaging did not change the selected tracked source revision.
5. Uploads the staged bundles and the validated Hong Kong Nginx site config.
6. Replaces `/var/www/user-web` and `/var/www/admin-web` from staged directories and retains the prior directories under `/var/www/backups`.
7. Writes an Nginx config backup beside the live site file.
8. Retains a private rollback-state directory containing the exact Git revision, a per-cutover transaction marker, the live directory identities, and whether prior roots/Nginx existed. These markers are not placed in the public document roots.
9. Runs `nginx -t`, reloads Nginx, and requires both local frontend probes to pass. Any cutover, validation, reload, or probe failure restores both prior frontend directories and the prior Nginx site before exiting nonzero. Internal rollback failures are detected and reported rather than hidden behind the original error.
10. Keeps a version-, transaction-, and Nginx-digest-guarded compensating action alive through the final public smoke checks. A stale action refuses to overwrite a newer frontend/Nginx release. A failed post-cutover release is retained under timestamped failed paths for forensics.

### Smoke checks

After deploy, the script verifies:

- Public user API health
- Public admin API health
- Hong Kong user homepage
- Hong Kong admin homepage
- Public user login
- Public admin login
- User token accepted by `/api/system/currentUser`
- Admin token accepted by `/admin-api/user/info`

API health checks must return the structured `status=UP` result rather than an arbitrary HTTP 200 page. Each login must return a bounded, non-empty access token, and that token must resolve a non-empty authenticated identity through the corresponding protected endpoint. For `all`, each credential-bearing login is attempted once; the backend and frontend groups do not duplicate it, and tokens are never printed.

These checks are part of the deployment transaction, not a report-only epilogue. Any failure triggers the reverse-order compensation described above. Backend compensation requires a previous source tree and rebuilds/health-gates its old runtime; frontend compensation restores its recorded prior roots and Nginx state and reruns local probes. If the first backend deployment has no previous source, or if any rollback prerequisite changed or disappeared, compensation fails closed and the operator must treat the environment as incident state.

## Suggested release routine

For small updates:

1. Finish local code changes.
2. Run:
   `powershell -ExecutionPolicy Bypass -File .\scripts\deploy-prod.ps1 -Target all -ReleaseId release-20260711-01 -MigrationEvidence C:\secure\xianyupilot\migration-evidence.json`
3. Open the official user/admin URLs and do one quick browser sanity pass.

For larger updates:

1. Run local tests first.
2. Deploy backend with `-Target backend` if only Java API or database logic changed.
3. Use `-Target all` when Python automation or crawler code changed and must be rebuilt on the China server too.
4. Deploy frontends.
5. Run focused browser regression on login, dashboard, accounts, messages, workflow, auto-delivery, cards, and notifications.

## Production endpoints

Keep real hosts and credentials only in the ignored local deployment configuration. User/admin production URLs and all external health checks must be HTTPS. Compose binds the backend host port to `127.0.0.1`; do not reopen it publicly. Backend deployment health is checked over SSH from the China host, and public smoke checks go through the user/admin HTTPS origins and the encrypted origin tunnel.
