from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.validate_migrations import MigrationValidationError, validate_repository


NOW = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)
REVISION = "c" * 40


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(root: Path, versions: tuple[str, ...] = ("1.1", "1.2")) -> Path:
    migration_dir = root / "db"
    migration_dir.mkdir(parents=True)
    entries = []
    for version in versions:
        path = migration_dir / f"V{version}__change.sql"
        path.write_text(f"-- migration {version}\nSELECT 1;\n", encoding="utf-8")
        entries.append(
            {
                "version": version,
                "description": f"change {version}",
                "path": path.relative_to(root).as_posix(),
                "sha256": _sha(path),
                "risk": "expand",
                "rollback": "restore",
            }
        )
    manifest = {
        "formatVersion": 1,
        "policy": {
            "immutableAfterRelease": True,
            "execution": "reviewed-maintenance-window-only",
            "productionRuntimeSchemaMutation": False,
            "rollback": "restore-or-forward-fix-only",
        },
        "databases": [
            {
                "id": "core_mysql",
                "engine": "mysql",
                "baselineVersion": versions[0],
                "directory": "db",
                "requireContiguousVersions": True,
                "migrations": entries,
                "quarantined": [],
            }
        ],
    }
    manifest_path = root / "db-migrations.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _write_evidence(
    root: Path,
    manifest_path: Path,
    *,
    release_id: str = "release-20260711-01",
    release_revision: str = REVISION,
) -> Path:
    evidence = {
        "formatVersion": 2,
        "releaseId": release_id,
        "releaseRevision": release_revision,
        "manifestSha256": _sha(manifest_path),
        "createdAt": "2026-07-11T07:30:00Z",
        "expiresAt": "2026-07-11T20:00:00Z",
        "approvedBy": "release-manager@example.com",
        "changeTicket": "CHG-20260711-001",
        "databases": {
            "core_mysql": {
                "backup": {
                    "status": "verified",
                    "artifactId": "mysql-backup-20260711T070000Z",
                    "sha256": "a" * 64,
                    "completedAt": "2026-07-11T07:00:00Z",
                },
                "restore": {
                    "status": "passed",
                    "drillId": "restore-drill-20260701",
                    "verifiedAt": "2026-07-01T08:00:00Z",
                    "target": "isolated-rehearsal-db",
                },
            }
        },
    }
    path = root.parent / "migration-evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_valid_manifest_and_release_evidence_pass(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    evidence = _write_evidence(root, manifest)

    result = validate_repository(
        root=root,
        manifest_path=manifest,
        production=True,
        evidence_path=evidence,
        release_id="release-20260711-01",
        release_revision=REVISION,
        now=NOW,
    )

    assert result.database_count == 1
    assert result.migration_count == 2


def test_production_evidence_rejects_a_relative_operator_path(
    tmp_path: Path,
    monkeypatch,
):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    _write_evidence(root, manifest)
    monkeypatch.chdir(root)

    with pytest.raises(MigrationValidationError, match="must use an absolute path"):
        validate_repository(
            root=root,
            manifest_path=manifest,
            production=True,
            evidence_path=Path("../migration-evidence.json"),
            release_id="release-20260711-01",
            release_revision=REVISION,
            now=NOW,
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda doc: doc["databases"][0]["migrations"].append(dict(doc["databases"][0]["migrations"][0])), "duplicate migration version"),
        (lambda doc: doc["databases"][0].update({"baselineVersion": "1.0"}), "baselineVersion"),
        (lambda doc: doc["policy"].update({"productionRuntimeSchemaMutation": True}), "policy.productionRuntimeSchemaMutation"),
    ],
)
def test_manifest_rejects_duplicate_or_inconsistent_versions(tmp_path: Path, mutate, message: str):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    mutate(document)
    manifest.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MigrationValidationError, match=message):
        validate_repository(root=root, manifest_path=manifest)


def test_manifest_rejects_version_gap_checksum_drift_and_untracked_sql(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root, versions=("1.1", "1.3"))

    with pytest.raises(MigrationValidationError, match="version gap"):
        validate_repository(root=root, manifest_path=manifest)

    manifest = _write_manifest(tmp_path / "second")
    migration = tmp_path / "second" / "db" / "V1.2__change.sql"
    migration.write_text("-- modified after review\n", encoding="utf-8")
    with pytest.raises(MigrationValidationError, match="checksum mismatch"):
        validate_repository(root=tmp_path / "second", manifest_path=manifest)

    third = tmp_path / "third"
    third.mkdir()
    manifest = _write_manifest(third)
    (third / "db" / "V1.3__untracked.sql").write_text("SELECT 1;\n", encoding="utf-8")
    with pytest.raises(MigrationValidationError, match="untracked migration"):
        validate_repository(root=third, manifest_path=manifest)


def test_manifest_rejects_migration_paths_outside_the_declared_directory(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    original = root / document["databases"][0]["migrations"][0]["path"]
    outside = root / "other" / original.name
    outside.parent.mkdir()
    outside.write_bytes(original.read_bytes())
    original.unlink()
    entry = document["databases"][0]["migrations"][0]
    entry["path"] = outside.relative_to(root).as_posix()
    entry["sha256"] = _sha(outside)
    manifest.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(MigrationValidationError, match="must be directly inside"):
        validate_repository(root=root, manifest_path=manifest)


def test_production_evidence_is_fail_closed_and_bound_to_release_and_manifest(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)

    with pytest.raises(MigrationValidationError, match="evidence file is required"):
        validate_repository(
            root=root,
            manifest_path=manifest,
            production=True,
            release_id="release-1",
            release_revision=REVISION,
            now=NOW,
        )

    evidence = _write_evidence(root, manifest, release_id="release-1")
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["manifestSha256"] = "b" * 64
    evidence.write_text(json.dumps(document), encoding="utf-8")
    evidence.chmod(0o600)

    with pytest.raises(MigrationValidationError, match="manifestSha256"):
        validate_repository(
            root=root,
            manifest_path=manifest,
            production=True,
            evidence_path=evidence,
            release_id="release-1",
            release_revision=REVISION,
            now=NOW,
        )


def test_production_evidence_rejects_stale_backup_and_production_restore_target(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    evidence = _write_evidence(root, manifest)
    document = json.loads(evidence.read_text(encoding="utf-8"))
    database = document["databases"]["core_mysql"]
    database["backup"]["completedAt"] = "2026-07-09T07:00:00Z"
    database["restore"]["target"] = "production-primary"
    evidence.write_text(json.dumps(document), encoding="utf-8")
    evidence.chmod(0o600)

    with pytest.raises(MigrationValidationError) as exc_info:
        validate_repository(
            root=root,
            manifest_path=manifest,
            production=True,
            evidence_path=evidence,
            release_id="release-20260711-01",
            release_revision=REVISION,
            now=NOW,
        )

    message = str(exc_info.value)
    assert "backup must be less than 24 hours old" in message
    assert "restore target must be isolated" in message


def test_production_evidence_is_bound_to_exact_git_revision(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    evidence = _write_evidence(root, manifest)

    with pytest.raises(MigrationValidationError, match="releaseRevision"):
        validate_repository(
            root=root,
            manifest_path=manifest,
            production=True,
            evidence_path=evidence,
            release_id="release-20260711-01",
            release_revision="d" * 40,
            now=NOW,
        )


def test_production_evidence_requires_format_v2_revision_field(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    manifest = _write_manifest(root)
    evidence = _write_evidence(root, manifest)
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["formatVersion"] = 1
    document.pop("releaseRevision")
    evidence.write_text(json.dumps(document), encoding="utf-8")
    evidence.chmod(0o600)

    with pytest.raises(MigrationValidationError) as exc_info:
        validate_repository(
            root=root,
            manifest_path=manifest,
            production=True,
            evidence_path=evidence,
            release_id="release-20260711-01",
            release_revision=REVISION,
            now=NOW,
        )

    message = str(exc_info.value)
    assert "formatVersion must be 2" in message
    assert "releaseRevision does not match" in message
