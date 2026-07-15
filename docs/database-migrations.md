# Database migration and recovery gate

## Release policy

`db/migrations-manifest.json` is the reviewed ledger for the three database adapters:

- `core_mysql` (`apps/core-api/src/main/resources/db/migration`)
- `automation_mysql` (`apps/automation-service/migrations`)
- `crawler_postgres` (`apps/crawler-service/migrations`)

Run `python scripts/validate_migrations.py` after every migration change. The command is read-only and fails on duplicate database/version/path declarations, version gaps, out-of-order versions, missing or untracked SQL, active filename/version mismatches, symlinks, path traversal, and checksum drift. Released SQL is immutable: add the next version instead of editing an existing file.

The former duplicate core `V1.1` is retained under `migration-quarantine` with a non-executable `.disabled` suffix, checksum, and reason. It is audit evidence, not a migration candidate.

Production containers set `SCHEMA_RUNTIME_MUTATIONS_ENABLED=false`:

- core-api verifies its required tables, compatibility columns, and indexes without DDL/DML;
- automation-service verifies ORM tables and compatibility columns without `create_all` or `ALTER TABLE`;
- crawler-service verifies migration history, the reviewed file checksum, columns, indexes, constraints, and tenant ownership without DDL/DML.

Missing or drifted schema therefore rejects production startup. Development retains the existing compatibility behavior. Production-like core and automation processes reject a mutation override in code, and crawler API/Worker processes ignore it. Never turn runtime mutations on in a long-running production API or Worker process.

## Important limitation

The core and automation SQL directories predate this ledger. Some scripts are non-idempotent, and automation `V1.5` performs a table backup, `TRUNCATE`, and rebuild. The core `SchemaCompatibilityRunner` also describes compatibility changes not yet represented as a complete historical Flyway chain. They must be treated as reviewed DBA inputs, not as a safe unattended migration engine.

Do not claim that a passing manifest check proves a database upgrade. Full Flyway adoption should happen only after baselining every deployed database and reconciling its real schema; guessing a baseline could silently mark unapplied changes as complete.

## Required maintenance-window sequence

1. Freeze the release revision and run `python scripts/validate_migrations.py`. Record the reported manifest SHA-256.
2. Take a production backup and copy it to an isolated rehearsal environment. Never rehearse against the only production volume.
3. Inventory the actual schema and data invariants. Compare them with the manifest, ORM metadata, core compatibility checks, and crawler history. Resolve drift explicitly.
4. Apply only the reviewed versions in numeric order in rehearsal. For automation `V1.5`, obtain a separate destructive-change approval, verify backup-table capacity, pause all writers, and reconcile row counts and conversation/message links before proceeding.
5. Exercise login, account/message ingestion, orders, delivery, billing, scheduled jobs, crawler API/Worker fencing, and backup restoration. Capture timings, locks, disk growth, and errors.
6. Prove rollback by restoring the backup to another isolated target and running the same checks. MySQL DDL can auto-commit; PostgreSQL transactional DDL does not make application/data rollback automatic.
7. Open the approved change window, stop or drain every writer, take a new immutable backup, verify its checksum, apply the rehearsed plan, run schema/data verification, then deploy with runtime mutations disabled.
8. If verification fails, prefer an approved forward fix only when it is safer and already rehearsed. Otherwise restore the captured backup. Image downgrade and MySQL major-version downgrade are not database rollback strategies.

The repository deliberately does not run these production data operations. Backup creation, restore, lock/drain control, provider-specific migration execution, and failover require infrastructure credentials and operator authority outside this workspace.

Crawler has a dedicated one-shot executor that applies the reviewed file, writes its database history checksum, closes the pool, and exits without starting HTTP or Worker workloads. After the evidence preflight passes, run the exact reviewed image with `NODE_ENV=production`, `MIGRATION_MAINTENANCE_APPROVED=true`, the concrete `RELEASE_ID`, and the `MIGRATION_MANIFEST_SHA256` printed by the validator, then invoke `npm run migrate:maintenance`. Core and automation remain DBA-executed maintenance plans because their historical scripts are not yet a safe complete chain.

## Release evidence

Copy `db/migration-evidence.example.json` to an operator-owned absolute path outside the repository. Do not place credentials in it. Set file permissions to owner-only on Linux. The production validator requires format version 2 and:

- a 3–128 character release ID matching the deploy command;
- `releaseRevision` set to the exact lowercase 40- or 64-character Git commit SHA selected by the deploy entrypoint;
- the exact current manifest SHA-256;
- an approval identity and change-ticket reference;
- evidence valid now with a lifetime no longer than 24 hours;
- for all three database IDs, a verified backup less than 24 hours old with artifact ID and SHA-256;
- for all three database IDs, a passed restore drill less than 90 days old on an explicitly isolated, non-production target.

Validate it without changing state:

```bash
python scripts/validate_migrations.py \
  --production \
  --release-id release-20260711-01 \
  --release-revision "$(git rev-parse --verify HEAD)" \
  --evidence-file /etc/xianyupilot/release/migration-evidence.json
```

Both the supported deploy entrypoint and legacy Compose preflight rerun this gate. The local gate compares format-v2 evidence with the actual clean Git `HEAD`, hashes the evidence before and after validation to detect a concurrent change, and passes its release ID plus SHA-256 to the staged remote preflight. The remote gate requires its `RELEASE_REVISION` and `RELEASE_ID` to match and requires the bytes at `DATABASE_MIGRATION_EVIDENCE_FILE` to have that exact SHA-256 before validating them again. Evidence, local source revision, and remote environment must therefore agree exactly. Missing, relative, stale, changed, byte-mismatched, in-repository, symlinked, or overly permissive evidence fails closed before a backend deployment.

This JSON is a local consistency/recency attestation, not independent proof that an object exists in backup storage. The change ticket must link an immutable, access-controlled backup inventory or object-store record and a signed restore report; the release manager must verify those systems out of band. Until that trust root and the real restore artifacts exist, the production-readiness decision remains blocked even when the local preflight passes.
