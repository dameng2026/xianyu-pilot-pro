# Production operations and incident runbook

Status: operator template. Replace every owner/escalation placeholder in the
controlled company copy and rehearse it before traffic. This tracked document
contains no phone numbers, credentials or privileged infrastructure commands.

## Roles and severity

- The **Incident Commander** owns severity, priorities, risk decisions and the
  event timeline; they do not simultaneously make unreviewed production edits.
- The Operations Lead executes approved infrastructure actions.
- The Application Lead diagnoses the affected domain and validates recovery.
- The Security/Privacy Lead owns evidence preservation, credential rotation,
  regulatory assessment and breach notification.
- The Communications Lead updates customers, support, providers and executives
  from verified facts only.
- The Scribe records timestamps, request/release IDs, hypotheses, commands,
  results and approvals in the incident system.

`SEV-1` includes broad authentication/tenant-isolation failure, confirmed or
suspected data exposure, payment integrity risk, destructive data loss, loss of
the only recoverable copy, or sustained outage of critical customer flows.
`SEV-2` is major degradation with a safe workaround or limited scope. `SEV-3`
is minor degradation without material security/data risk. Uncertainty about a
possible security incident is handled at the higher severity until disproved.

## First 15 minutes

1. Open the incident record, page the on-call roles and assign Incident
   Commander/Scribe. Record the UTC and local start time.
2. Confirm impact independently: public user/admin URLs, API readiness,
   dashboards, recent release revision and provider status. Distinguish customer
   impact from a monitoring-only failure.
3. Preserve volatile evidence and stop risky automation when needed; **never paste**
   tokens, cookies, passwords, HAR bodies, customer content or secret file
   values into chat, tickets, command history or screenshots.
4. Establish the last known good release/data consistency point. Freeze deploys,
   migrations, cleanup and credential changes until one coordinated owner
   approves them.
5. Choose contain, mitigate, rollback or recover. Record the hypothesis and
   success/abort condition before the action.

## Symptom routing

| Symptom | Safe checks | Escalation/action |
| --- | --- | --- |
| Public web/API unavailable | independent DNS/TLS probe, `public-availability`, US Nginx/tunnel, origin readiness | edge/network owner, then application owner; preserve request IDs |
| Core/database/Redis not ready | dependency metrics, container health, saturation/OOM, recent schema/change ticket | stop unsafe writers; database/cache owner; use restore runbook if integrity is uncertain |
| Worker backlog or duplicate actions | queue depth, heartbeat, lease/fencing, idempotency and provider callbacks | pause publication/retries; Worker/domain owner; never purge a queue to make a graph green |
| Upload/media errors | quota/rate/concurrency metrics, `tenant_storage_asset`, shared-volume capacity/inodes, core delivery logs | freeze cleanup; reconcile DB/files; never expose the volume through static Nginx/Python |
| Payment/provider degradation | provider status, signed callback/idempotency records and circuit state | disable unsafe capture/retry paths and show truthful unavailable state; finance/provider owner |
| Monitoring blind | external watchdog, container health, receiver and retention/disk state | use independent paging; restore monitoring before declaring application recovery |
| Suspected security/privacy event | revoke sessions/keys under dual control, preserve immutable logs, scope tenants/data flows | Security/Privacy Lead; legal/regulatory and customer notification procedure |

## Change and rollback safety

Use only `scripts/prod_deploy.py` through the controlled runner. A green local
test is not deployment authority. The script performs version-guarded
compensation in reverse order, but it is an in-place release, not blue/green or
zero downtime. Do not delete `.previous-*`, `.failed-*`, `.frontend-rollback-*`,
Nginx backups or release transaction markers during an incident.

If a final smoke gate fails, allow the supported automatic rollback to finish
and verify its result. A network partition, host loss, first deployment, stale
transaction marker or failed rebuild can make compensation incomplete; treat
that state as SEV-1/SEV-2 according to impact and do not rerun deploy until the
live source, environment, Nginx and container identities are reconciled.

Database rollback means an approved forward fix or restore from verified
backup. It never means downgrading a MySQL image or replaying destructive SQL
from memory. Follow `backup-restore.md` and `database-migrations.md`.

## Security incident containment

Preserve full-history secret-scan and deployment evidence before rotation.
Invalidate affected sessions/tokens at their authoritative provider, rotate
dependent credentials in a staged order, verify old credentials fail, then
remove local captures and rewrite repository history if required. Do not add an
allowlist/baseline to hide a real secret. Tenant-isolation, payment, SSRF/media,
browser automation and admin surfaces require independent forensic review.

Normal user/admin logout is a server-authoritative POST: it atomically advances
the account `security_version` and expires the host-only HttpOnly media cookie
at `Path=/uploads`. The frontend calls it before deleting the local bearer token.
If that call fails, the UI must report **“服务端撤销未确认”** and operations must
treat the remote session/media authorization as potentially active; clearing
browser storage is not revocation evidence. Acceptance and incident drills must
prove the previous API token and media cookie fail immediately on both user and
admin hosts, across tabs and after a service restart. Use the approved account
or tenant revocation workflow for broader containment instead of editing local
storage or deleting cookies by hand.

Containment must not destroy evidence or silently broaden access. Emergency
access is time-limited, MFA-protected, individually attributable and reviewed
after use. Record any data residency or cross-border implications immediately.

## Recovery and return to service

1. Define objective recovery checks before acting: dependency readiness,
   business-flow integrity, tenant isolation, queue consistency, media/content
   reconciliation and public probes.
2. Recover in an isolated target first when data integrity is uncertain. Use
   immutable artifacts/checksums and the exact schema/release evidence.
3. Re-enable traffic and background work gradually. Watch errors, duplicates,
   latency, resource ceilings and provider effects through the agreed soak.
4. The Incident Commander declares recovery only after customer-visible checks,
   monitoring/alert delivery and data integrity pass. “Container is running” is
   insufficient.
5. Keep enhanced monitoring and deployment freeze through the approved
   observation window.

## Closure

Within the policy deadline, publish a blameless timeline, root/contributing
causes, impact/data assessment, what detection missed, exact remediation owners
and due dates. Link sanitized logs, checksums, release/backup IDs, approvals and
customer/regulatory communications. Test every corrective action; closing a
ticket without verified evidence does not close the risk.

Related procedures: `monitoring.md`, `backup-restore.md`,
`upload-storage-governance.md`, `../production-deploy.md`, and
`../database-migrations.md`.
