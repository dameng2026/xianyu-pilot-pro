# Backup, restore, and disaster-recovery runbook

Status: operator procedure template. **This procedure is not restore evidence.**
Commercial sign-off requires dated artifacts from an isolated rehearsal against
the exact release revision and production-like data. A successful backup job,
named Docker volume, screenshot, or locally passing unit test does not prove
recoverability.

## Recovery inventory and ownership

The service owner and infrastructure owner must maintain one inventory record
for every item below. It records the provider/account, region and residency,
immutable artifact ID, checksum, encryption key owner, retention/deletion
policy, backup operator, restore approver, and tested recovery dependency.

| Recovery set | Required data |
| --- | --- |
| Core business state | MySQL, including users/tenants, authorization and revocation state, payments/orders, `admin_module_record`, and `tenant_storage_asset` |
| Customer media | `uploads_data`, including private tenant images, public carousel/open-source content images, validated system logos, quarantine, and storage metadata reconciliation inputs |
| Crawler state | PostgreSQL schema/history, tenant jobs, snapshots, delivery/fencing state, and browser-session metadata that policy permits retaining |
| Queue/cache state | Redis AOF (`redis_data`), with an explicit classification of which keys are durable recovery inputs and which are safely rebuildable |
| Monitoring state | `alertmanager_data`, `prometheus_data`, and `grafana_data`; documented rebuild exceptions still require configuration and alert-routing recovery |
| Release/edge state | exact application image digests when the registry gate exists, frontend release directories, Nginx site/config checksum, tunnel unit/config, and deployment rollback markers |

Secrets and encryption keys are recovered from the approved secret manager or
KMS, never from an application backup. Their backup, escrow, rotation and
break-glass ownership must be tested independently. Do not put secret values in
the inventory or evidence report.

## Application-consistent recovery groups

MySQL and `uploads_data` are one application-consistent recovery group. Drain
the Java and Python writers (API, automation Worker, cleanup/reconciler and
content image uploads), record the consistency point, then capture both sides.
Restoring only files can revive deleted/private media; restoring only MySQL can
leave business records pointing at missing bytes. The restored
`tenant_storage_asset` rows and files must reconcile by tenant, storage key,
visibility, purpose, owner, byte length and SHA-256.

The `commercial-home` and `open-source-home` rows in `admin_module_record` must
remain namespace-separated and must reference active public assets with the
expected `carousel` or `open-source-content` purpose. A restore that silently
drops content, changes visibility, or reconnects one namespace to the other is
failed.

PostgreSQL and Redis require a documented queue consistency point. Drain API
publication and both Workers, capture PostgreSQL first/last transaction markers
and Redis AOF state, and define the replay/idempotency behavior for a job that
was reserved during the snapshot. “Redis is a cache” is not an acceptable
assumption while it carries queues, leases, fencing tokens or recovery state.

## Backup execution gate

1. Link the approved change/recovery ticket, release revision and responsible
   operators. Confirm the destination is encrypted, access-controlled,
   immutable for the retention window, and located in an approved residency.
2. Verify backup capacity, KMS access and clock synchronization. Record current
   database versions, image digests/tags, schema-manifest SHA-256, volume IDs
   and application health before touching writers.
3. Quiesce or fence every writer for the recovery group. Prove that new writes
   are rejected or drained; a process list alone is insufficient.
4. Capture provider-native point-in-time logs/snapshots where supported and an
   independently usable logical backup. Capture `uploads_data` at the same
   consistency point. Hash every exported artifact after transfer.
5. Resume writers only after snapshot completion, checksum verification and a
   dependency-aware readiness check. Alert if the freeze exceeds the approved
   maintenance window.
6. Replicate the encrypted artifacts to the approved failure domain and make
   the inventory immutable. A backup that remains on the source host is not a
   disaster-recovery copy.

Provider-specific commands and credentials intentionally do not live in this
repository. They belong in the controlled infrastructure runbook and must be
peer-reviewed before execution.

## Isolated restore drill

1. Create a new **isolated, non-production** account/project/network with no
   provider callbacks, customer messaging, payment capture, Xianyu publishing,
   or production DNS access. Record the isolation control and target identity.
2. Provision the exact approved database/runtime versions. Verify artifact and
   manifest checksums before decrypting or importing anything.
3. Restore MySQL, PostgreSQL, Redis and `uploads_data` into new targets. Never
   overwrite the only production copy and never treat an image downgrade as a
   database rollback.
4. Run schema/history validation with runtime schema mutations disabled. Run
   media/content reconciliation, tenant row-count/hash checks, queue redelivery
   and fencing checks, and monitoring configuration validation.
5. Exercise login/revocation, tenant isolation, content/carousel reads, private
   and public media authorization, orders/delivery, Worker recovery, crawler
   snapshots, and dependency-outage behavior using synthetic accounts only.
6. Measure data-loss window and elapsed restore/service-recovery time. Compare
   the results with the approved **RPO** and **RTO**; do not invent targets after
   seeing the result.
7. Obtain independent review, retain sanitized logs/checksums and destroy the
   drill target under the data-deletion policy.

Point-in-time recovery must additionally restore to at least one timestamp
between full backups and prove the selected business transaction boundary.
Disaster recovery must rehearse loss of the primary host/region and DNS/tunnel
cutover; a same-host restore is only a backup test.

## Evidence required for release sign-off

- immutable backup IDs and SHA-256 values for every recovery set;
- start/end time, consistency point, versions and exact release revision;
- isolated target ID and proof it could not call production providers;
- row/file/queue reconciliation results and critical-flow test output;
- measured RPO/RTO against pre-approved targets;
- encryption/KMS and retention evidence without key material;
- named executor, independent reviewer, incident/on-call owner and ticket;
- every exception, data loss, warning and remediation decision.

Any missing artifact, unexplained mismatch, unverifiable checksum, failed
critical flow, exceeded RPO/RTO, or unapproved exception keeps production
readiness blocked.
