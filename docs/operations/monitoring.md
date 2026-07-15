# Production monitoring and alerting runbook

Status: tracked configuration and operator procedure. A green config check is
local evidence only. Commercial sign-off still requires external acceptance of
real alerts, dashboards, retention, access control and on-call response in the
production topology.

## What is monitored

- Prometheus authenticates to the core metrics endpoint with the
  `ops_metrics_token` file secret. Metrics include core, database, Redis,
  payment, notification and client-error signals.
- blackbox_exporter probes dependency-aware readiness for core-api,
  automation-service and crawler-service on the private Compose network.
- The `public-availability` job probes the user frontend, public API health and
  admin frontend over real HTTPS. It therefore covers DNS, certificate
  validation, the US edge, the loopback origin tunnel and China origin path.
- Grafana provisions the production dashboard as non-editable and
  non-deletable, disables anonymous access/telemetry, and requires Secure,
  SameSite=Strict session cookies. All monitoring UIs bind to loopback. Grafana
  is accessed only through the authenticated HTTPS URL in `GRAFANA_ROOT_URL`;
  Prometheus/Alertmanager diagnostics may additionally use an approved SSH
  tunnel without exposing their ports publicly.
- Alertmanager reads its receiver URL from a file secret. Grafana reads its
  administrator password from `GRAFANA_ADMIN_PASSWORD_FILE`; neither value is
  stored in tracked YAML or a container environment variable.

CI runs the production-version `promtool` and `amtool` binaries with no network,
read-only filesystems, dropped capabilities and no-new-privileges. That proves
the tracked Prometheus rules and Alertmanager routing parse; it does not prove
the containers start, a scrape succeeds, a receiver delivers, or an operator
responds.

## Required alerts and first response

| Alert | First response |
| --- | --- |
| `PublicEndpointDown` | Confirm from an independent network, check DNS/TLS/edge, US Nginx and tunnel, then origin readiness; do not restart blindly |
| `PublicEndpointProbeMissing` | Treat monitoring configuration/scrape loss as an outage in observability and verify target discovery |
| `PublicTlsCertificateExpiresSoon` | Verify the reported certificate chain and renewal owner; renew and test before the 14-day threshold becomes an outage |
| `CriticalServiceNotReady` / `CriticalServiceProbeMissing` | Inspect the named service and its dependencies; preserve logs and request IDs |
| `DatabaseDown` / `RedisDown` | Freeze risky writes, confirm dependency health and invoke the data-service incident procedure |
| `BlackboxExporterDown` | Restore the exporter before trusting readiness dashboards |
| `AlertmanagerDown` / notification failures | Page through the independent receiver and treat in-stack alert delivery as unavailable |
| `WebhookDeliveryFailures` | Disable unsafe retry storms, validate allowlisted destination/provider health and preserve idempotency evidence |
| `ClientErrorsSpike` | Correlate release revision, route and request IDs; roll back only under the version-guarded deployment procedure |

`XianyuWatchdog` intentionally fires continuously. The external incident
receiver must page when its heartbeat is absent for ten minutes, because an
in-stack system cannot reliably report its own total failure.

## Capacity and retention

Every production service has explicit memory, CPU and PID ceilings plus a
graceful-stop window. Values in `.env.production` must come from reviewed load,
spike, endurance and failure-injection tests; the tracked example contains
fail-closed placeholders, not sizing recommendations.

Prometheus has both time retention and the mandatory
`PROMETHEUS_RETENTION_SIZE` ceiling. Container JSON logs rotate. The operator
must still monitor host filesystem/inode pressure, named-volume usage, OOM
kills, throttling, process saturation and backup growth outside this stack.
Retention must match the security, privacy, audit and incident-investigation
policy; increasing it is a data-governance decision, not just a disk setting.

## Production acceptance drill

1. Validate the rendered Compose model without printing secrets, then run
   `promtool`, `amtool` and the container health checks on Linux.
2. Prove every internal and `public-availability` target reports
   `probe_success=1`, the TLS-expiry series exists, and the dashboard shows the
   same labels.
3. Fire one synthetic warning and one critical alert. Record firing and resolved
   delivery, deduplication/grouping, receiver timestamps and the on-call ack.
4. Stop each monitored component in an approved rehearsal, break one public
   probe, simulate receiver failure, and prove the expected alert and recovery.
5. Verify an independent system detects a missing `XianyuWatchdog` heartbeat.
6. Measure detection, notification, acknowledgement and mitigation times and
   compare them with pre-approved SLO/incident targets.

Screenshots alone are insufficient. Retain sanitized Prometheus query results,
Alertmanager notification evidence, external receiver records, exact config
checksums, release revision, operator/reviewer and change ticket.

## Known external blind spots

The tracked stack does not itself prove host/volume telemetry, CDN/WAF abuse
controls, tunnel unit restart/key expiry, cloud database/storage health,
cross-region reachability, provider business-flow success, browser real-user
monitoring, workforce SSO/MFA/RBAC/audit for Grafana, or 24x7 staffing. Those signals and their escalation ownership are
mandatory external acceptance gates in `docs/production-readiness.md`.
