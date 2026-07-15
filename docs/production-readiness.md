# Production readiness gate

Current decision: **BLOCKED until every external gate below has evidence**. Passing local tests is necessary, but it is not proof that the system is commercially deployable in the real production topology.

Operator procedures are tracked in
[`operations/backup-restore.md`](operations/backup-restore.md),
[`operations/monitoring.md`](operations/monitoring.md),
[`operations/production-runbook.md`](operations/production-runbook.md), and
[`operations/supply-chain-release.md`](operations/supply-chain-release.md).
They define how to gather evidence; their existence is not evidence that a drill,
approval or external control occurred.

## Automated code gates

The tracked `.github/workflows/ci.yml` must pass on the exact release revision:

- Secret history: the open-source Gitleaks CLI checks out and scans the complete Git history on every event, runs with findings fully redacted, and fails closed on every detected credential. The exact Linux archive is version-pinned and SHA-256 verified before extraction; the scheduled run provides a recurring audit even without repository activity.
- Java core API: Maven `verify`, CycloneDX 1.6 production SBOM, and fail-closed OWASP Dependency-Check with KEV/NVD data. Configure the repository `NVD_API_KEY` secret; its absence intentionally fails CI.
- Python automation service: hash-locked install, full pytest suite, strict `pip-audit` over the fully pinned transitive lock without re-resolving dependencies, and uploaded CycloneDX JSON plus machine-readable audit evidence.
- Crawler service: exact Node/npm toolchain assertion, install-script approval enforcement in CI and the production image build, tests, TypeScript build, zero-vulnerability runtime/build dependency audit, and uploaded CycloneDX JSON plus machine-readable audit evidence.
- User web: exact Node/npm toolchain assertion, fail-closed install-script policy, lint, truthful-state contracts, reproducible production build, zero-vulnerability runtime/build dependency audit, and uploaded CycloneDX JSON plus machine-readable audit evidence.
- Admin web: exact Node/npm toolchain assertion, fail-closed install-script policy, lint, typecheck, contracts, production build, zero-vulnerability runtime/build dependency audit, and uploaded CycloneDX JSON plus machine-readable audit evidence.
- Release contracts: hash-locked test/deployment tooling, packaging, secret exclusion, Compose/container, transport, and deployment safety tests.
- Monitoring configuration: CI runs the production Prometheus and Alertmanager tool versions in hardened, network-disabled containers and fails on invalid Prometheus rules/configuration or Alertmanager routing. Runtime scrape/notification acceptance remains external.
- Production containers: after all application gates pass, CI builds the five tracked production Dockerfiles and pulls every pinned infrastructure/monitoring image referenced by the production Compose topology. Each subject is resolved to an image ID or registry digest, receives a CycloneDX image SBOM and JSON vulnerability report, and fails on any `HIGH` or `CRITICAL` operating-system or library finding, including findings without a fix. Evidence upload still runs when the vulnerability step fails.

Every GitHub Action is pinned to an immutable reviewed commit SHA. Scanner versions are fixed (`Gitleaks 8.30.1`, `Trivy 0.70.0`); the Gitleaks archive is additionally pinned to SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`. CI downloads it as data, verifies the digest, and only then extracts it; it does not execute an unreviewed `curl | sh` installer. Generated Java, Python, npm, secret-scan, and image evidence uploads use failure-path retention where applicable, so a vulnerability rejection does not discard the report that explains it. Evidence artifacts are retained for 30 days and named with the exact Git revision. A release record must retain them outside the ephemeral CI retention window.

The release-contract job installs only `scripts/requirements-ci.lock` with pip's `--require-hashes` mode. Its auditable top-level input is `scripts/requirements-ci.txt`. Regenerate the lock for the CI Python/Linux target with the exact `uv pip compile ...` command recorded in the lock header, review every version/hash change, and commit the input and generated lock together.

Do not release from an untracked directory. The release revision, CI run, SBOM, vulnerability and secret-scan evidence, image digests, operator, and deployment time must be recorded.

### Image signing and provenance gate

The current repository has no approved immutable production registry, least-privilege push identity, or GitHub OIDC trust policy. Therefore CI intentionally blocks every Git tag in `release-provenance-gate`, even when tests and local image scans pass. This is an executable fail-closed release gate; a green branch build is not a signed release and must never be described as one.

Before removing that blocker, provision the external registry/OIDC controls and replace it with reviewed, digest-bound verification that proves all five application images were pushed by the release workflow, keyless-signed for the exact repository/workflow identity, and accompanied by in-toto/SLSA provenance plus the image SBOM. Verification must use immutable `repository@sha256:...` subjects and an exact certificate identity and issuer; wildcard identities, mutable tags, self-asserted JSON, and operator screenshots are not acceptable evidence. Grant `packages: write` and `id-token: write` only to that isolated release job, never to pull-request or ordinary CI jobs.

## Mandatory external gates

- Rotate and then remove every locally captured credential/session artifact. Known local-only paths include root `.env`, `.deploy.prod.json`, literal credentials in root deployment helper scripts/PowerShell files, token text files, HAR files, crawler response dumps, automation cookie files, and core login captures. Never copy their values into tickets or logs. Rotation must happen at the external provider first; then remove the files, rewrite affected Git history where applicable, invalidate old clones/caches, and run the redacted full-history Gitleaks gate again. Do not suppress a real finding with a baseline or allowlist.
- Provision and independently verify the pinned-host-key SSH origin tunnel used by `deploy/nginx/us-nginx-full.conf`, including the dedicated unprivileged service account, restricted origin `authorized_keys`, key rotation, monitoring, and restart alerting. The deploy entrypoint now refuses frontend cutover unless the tunnel unit is active and `/api/health` succeeds through its loopback endpoint. Verified HTTPS/mTLS remains an acceptable replacement; public plaintext HTTP is always rejected.
- Put Grafana and every operator surface behind the approved HTTPS identity proxy/SSO with MFA, least-privilege roles, access/audit logs and a tested break-glass procedure. Loopback binding and a strong local administrator password reduce exposure but are not workforce identity governance.
- Build and run every production image on Linux. Verify non-root execution, Chromium sandbox startup, health/readiness probes, read-only/container restrictions, and graceful SIGTERM behavior.
- Rehearse the tracked MySQL 8.0-to-8.4 LTS and Grafana 11-to-12 upgrades on restored production-like volumes. Capture pre-upgrade logical/physical backups, compatibility checks, timings, and a tested restore rollback; changing image tags is not migration evidence and MySQL downgrade is not the rollback path.
- Run PostgreSQL + Redis integration tests for crawler tenant isolation, queue publication crash recovery, Worker redelivery/fencing, current-item snapshots, QR lifecycle, and dependency outages.
- Run live end-to-end tests with dedicated non-production accounts for the configured payment gateway, SMS/email providers, AI provider, Feishu, Xianyu/Goofish login/search/publish/message/delivery flows, and callback replay/idempotency.
- Prove backup, restore, point-in-time recovery where applicable, disaster recovery, rollback, monitoring alerts, log retention/redaction, and on-call ownership. Recovery evidence must explicitly cover `uploads_data`, its application-consistent relationship with `core_mysql`, `redis_data`, and `alertmanager_data`/`prometheus_data`/`grafana_data`; named-volume existence is not a backup. The release rehearsal must inject a frontend-deploy failure and a final public-smoke failure after cutover, then prove the version-guarded reverse-order frontend/Nginx and backend/runtime compensation against the real hosts; unit tests alone are not operational rollback evidence.
- Supply operator-approved Terms, Privacy Policy, ICP/compliance details, support contacts, data retention/deletion policy, and required payment/provider agreements.
- Initialize a real Git repository and protected release branch. Require reviewed pull requests and the CI gate; this workspace currently has no usable Git history.
- Provision the immutable production image registry and GitHub OIDC trust described above. Until digest-bound signature and in-toto/SLSA attestation verification replaces the intentional tag blocker, commercial releases remain blocked.
- Obtain commercial legal approval for every production dependency license, including Hibernate's LGPL-2.1-only terms, and retain the SBOM/license review with the release evidence.
- Run an independent threat-model review plus authenticated and unauthenticated penetration/DAST assessment over tenant isolation/IDOR, authentication and recovery, payment callbacks, SSRF/egress, file/media handling, browser automation, and operator surfaces. Remediate every unaccepted finding and retain the report; dependency and secret scans are not a substitute for application-security testing.
- Establish measured capacity limits with production-like load, spike, endurance, and failure-injection tests. Production Compose now fails closed unless every service has memory/CPU/PID ceilings and a graceful-stop window, but the example values are deliberate placeholders and no limit is approved until the capacity evidence exists. Approve SLOs, alert thresholds, rate/abuse limits, autoscaling or explicit single-replica ceilings, and quantified RTO/RPO before accepting commercial traffic.
- Provision a hardened, auditable release runner/operator workstation with a reviewed Python runtime and hash-locked deployment dependencies, least-privilege credentials, MFA, session logging, and controlled updates. The current PowerShell wrapper invokes the ambient `python` executable and is not itself a hermetic deployment environment.
- Complete and approve the production data inventory/DPIA: classify personal and credential data, document China/US data flows and residency, determine PIPL/DSL/CSL and cross-border-transfer obligations, verify consent and purpose limitation, and rehearse user access/export/deletion plus breach-notification procedures. A generic Privacy Policy alone is not operational privacy evidence.
- Complete supported-browser/real-device, keyboard/accessibility, localization, and degraded-network acceptance testing for the user and admin critical journeys. Include logout under normal, concurrent and network-failure conditions: the previous bearer token and `/uploads` media cookie must be rejected after the authoritative POST, while a failed server call must visibly say “服务端撤销未确认” rather than imply revocation. Record severity-based exceptions with owners and expiry dates; passing static UI contracts is not an accessibility or compatibility certification.

## Explicit topology constraints

- QR browser sessions currently hold live browser handles in one crawler process. Keep `crawler-service` at one replica. A multi-replica deployment requires sticky instance routing or a dedicated session-owning browser worker before scaling.
- Browser URL guards block literal private, loopback, link-local, metadata, and non-web targets. Production must also enforce outbound firewall/proxy policy and DNS-aware private-address blocking; application URL checks are not an egress security boundary.
- Crawler schema changes now use a versioned, checksummed PostgreSQL file and database history row; production runtime is validation-only. A real PostgreSQL backup/restore and API/Worker concurrency rehearsal is still required before rollout.
- The current backend deployment is in-place and may briefly interrupt service; it is not blue/green.
- The current rollback restores source and rebuilds the prior runtime; it is not a digest-pinned artifact rollback. Until approved registry digests are retained and verified, registry/base-image drift or an unavailable package registry can prevent byte-identical recovery, so the operational rollback gate remains blocked.
- Compose currently names third-party images with version tags. CI records and scans the digest resolved during that run, but production deployment must also bind the approved digest; a scan of one digest does not make a later mutable-tag resolution trustworthy.
- Official WeChat/Alipay, SMS, and email paths must remain visibly unavailable until real provider adapters and credentials are configured. Sandbox/mock modes are forbidden in production.
- Java/MySQL `admin_module_record` is the durable operator-content authority, with `commercial-home` and `open-source-home` kept distinct. Python exposes no `/api/content/*` JSON CRUD; its sole content seam is the internal, allowlisted `/api/internal/content/public-images/upload` processor with service ownership and the exact `carousel`/`open-source-content` purposes. Nginx sends every `/uploads/` request to core-api for database visibility and byte-integrity enforcement.
- No uploads namespace has static compatibility. Before upgrade, inventory every legacy `/uploads/logos/**` reference, re-upload approved logos through the admin flow, and update it to the validated `/uploads/public/logos/YYYYMMDD/<uuid32>.png|jpg` form. Old URLs must return 404; restoring a static handler or rewrite is a security regression.
- The shared `uploads_data` volume is a single-host persistence design, not multi-instance storage. Before scaling Java/Python writers or moving hosts, prove shared storage semantics, locking, reconciliation, backup/restore and failure behavior; otherwise keep one approved stack.

## Release sign-off evidence

Record all of the following for each release:

| Evidence | Required value |
| --- | --- |
| Release revision | Immutable Git commit/tag |
| CI | Passing run URL/ID |
| Supply chain | SBOMs and zero-unaccepted-vulnerability reports |
| Images | Registry digests, not mutable tags |
| Database | Migration plan, backup ID, restore drill evidence, and the locally/remote matched evidence SHA-256 |
| Security | Secret rotation record, transport verification, external scan |
| Product | Real-account critical-flow E2E report |
| Compliance | Legal/security/operations owner approval |
| Operations | Alert drill, watchdog, capacity/resource limits, on-call exercise, backup/PITR/DR and measured RPO/RTO |
| Deployment | Operator, timestamp, smoke results, rollback checkpoint, and any compensation outcome |

Any missing value keeps the decision **BLOCKED**.
