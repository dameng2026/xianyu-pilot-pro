# Upload storage operations

The shared upload volume is `/app/uploads` in every production writer and is
mounted from the same `uploads_data` volume. Both Java and Python readiness
probes perform a real write, fsync, atomic rename, read and delete. A failed
probe is a release blocker; do not bypass it by changing the health check.

Tenant image admission is serialized with MySQL named locks and enforced from
durable `tenant_storage_asset` reservations and `tenant_upload_rate_event`
rows. Production must explicitly configure tenant/global byte quotas,
tenant/global concurrency, the rate window and retention age. The global
limits are database-backed and therefore apply across web and worker replicas.

## Cleanup approval

1. Call the internal cleanup endpoint with `dryRun=true` and retain its
   candidate URLs, bytes and asset IDs in the change ticket.
2. Confirm that none of the candidates is referenced by a draft, carousel,
   workflow execution or published item. The application deliberately does
   not guess whether arbitrary JSON payloads are business references.
3. A reviewer and a different approver must sign the ticket.
4. Execute with the exact reviewed `assetIds`, a reason, `reviewedBy`,
   `approvedBy`, the confirmation phrase, and a matching
   `X-Internal-Tenant-Id`. IDs that changed tenant/state/age fail the whole
   request.
5. File deletion uses same-volume quarantine rename. The database is marked
   deleted before quarantine is unlinked; a database failure restores the
   original file.

The web service and worker reconcile stale reservations, failed writes,
partial files and interrupted deletion claims at startup and every five
minutes. Never manually delete files from the volume.

## Media delivery and cookie topology

Private media is delivered only through core-api. The browser first exchanges
its bearer token on the same origin for a short-lived, host-only media cookie.
That cookie is `HttpOnly`, `Secure`, `SameSite=Strict`, has no `Domain`
attribute, and is scoped to `Path=/uploads`; normal API authentication never
accepts it. Nginx must preserve the request cookie, must not rewrite its domain
or path, and must route every `/uploads/` request to core-api. Private media
responses remain `private, no-store` and must never be cached by Nginx or a CDN.

This contract requires the API and media path to be same-origin with each
frontend (`www` and `admin` each receive their own host-only cookie). A topology
that moves `/api` or `/uploads` to another site or embeds private media
cross-site is a breaking security change and requires a reviewed replacement
design plus real-browser acceptance evidence. `SameSite=None` and a shared
parent-domain cookie are not approved shortcuts.

Anonymous delivery is allowed only for assets whose database row is explicitly
classified `visibility=public`. A random filename, an old public URL, or a file
that merely exists in the shared volume is never publication authority.

## Content publication boundary

Java/MySQL is the durable source of truth for operator-managed content. The
`admin_module_record` table keeps the `commercial-home` and `open-source-home`
namespaces separate: commercial home carousels/announcements must never be
read from or written into the open-source about/content namespace. Backups,
restores and data reconciliation must cover both namespaces and their referenced
media assets as one consistency set.

The former Python JSON CRUD surface `/api/content/*` is removed and must not be
reintroduced or exposed through Nginx. Python has only the internal image
processing seam `/api/internal/content/public-images/upload`. It requires the
internal service identity, records `owner_type=service`, and accepts only the
reviewed public purposes `carousel` and `open-source-content`. URL imports pass
the same destination-host allowlist and media validation as byte uploads; an
internal token alone does not authorize an arbitrary purpose, owner, host or
public path.

The upload processor may create the verified bytes and storage reservation, but
core-api remains the publication and delivery authority. Nginx routes every
`/uploads/` request to core-api, never to Python or a static volume mount, so the
database visibility, tenant ownership, byte size, SHA-256 and media-decode checks
cannot be bypassed. The only anonymous exception is an explicitly active public
asset row with the matching approved purpose.

## System logo migration gate

There is no static uploads handler. Before upgrading, inventory every database,
configuration and rendered-content reference to the legacy `/uploads/logos/**`
namespace. Re-upload each still-approved logo through the administrator upload
flow and update the reference to `/uploads/public/logos/YYYYMMDD/<uuid32>` with
the validated `.png` or `.jpg` extension. Confirm the corresponding storage row
is active, public, published, byte/SHA/MIME/decode-valid, and that anonymous
delivery succeeds only through `MediaAssetController`.

An old logo URL must safely return **404** after cutover. Do not copy legacy
files into the new namespace, add a rewrite, or restore static compatibility;
any of those would bypass the database publication and integrity authority.
Keep the pre-upgrade reference inventory and successful re-upload/404 checks in
the change ticket.

## Backup and restore gate

The named volume is persistence, not a backup. Before commercial traffic, the
operator must implement encrypted, access-controlled, immutable backups for
`uploads_data` and retain a restore report that proves file bytes and
`tenant_storage_asset` rows reconcile by tenant, storage key, size, and SHA-256.
The upload snapshot and the corresponding `core_mysql` backup must share a
documented consistency point (writers drained or an equivalent
application-consistent snapshot). Restoring only one side can either lose customer media or
revive deleted/private data and is prohibited.

The same recovery inventory must cover `redis_data` and the monitoring state
volumes `alertmanager_data`, `prometheus_data`, and `grafana_data`, with an
approved rationale for any data intentionally treated as rebuildable. Record
backup artifact IDs and checksums, encryption/key ownership, retention and
deletion policy, an isolated restore target, measured restore time, the tested
release revision, RPO/RTO results, and reviewer approval. A Docker volume list,
snapshot-success screenshot, or unit test is not restore evidence.

`tenant_storage_asset` is the audit record. Keep deleted rows online for at
least 365 days and archive them to the organization's immutable audit store
before any later purge. Rate-event rows are operational data and are deleted
automatically after the configured window (with a minimum one-hour buffer).
Production DB maintenance must verify the archive row count and hash before
removing online audit rows; direct unaudited SQL deletion is prohibited.
