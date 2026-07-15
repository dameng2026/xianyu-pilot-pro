#!/usr/bin/env python3
"""Validate the repository migration ledger and production recovery evidence.

This command deliberately does not connect to a database or execute SQL.  It is
the fail-closed release seam shared by all database adapters: reviewed migration
files are immutable, every active file is declared exactly once, and production
releases carry fresh backup plus restore-drill evidence bound to this manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MIGRATION_NAME = re.compile(r"^V(?P<version>\d+(?:\.\d+)*)__[A-Za-z0-9][A-Za-z0-9_-]*\.sql$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
PRODUCTION_TARGET = re.compile(r"(?:^|[-_.])(prod|production|live|primary)(?:$|[-_.])", re.IGNORECASE)
MAX_BACKUP_AGE = timedelta(hours=24)
MAX_RESTORE_AGE = timedelta(days=90)
MAX_EVIDENCE_LIFETIME = timedelta(hours=24)


class MigrationValidationError(RuntimeError):
    """Raised with every detected release-safety violation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("migration validation failed:\n- " + "\n- ".join(errors))


@dataclass(frozen=True)
class ValidationResult:
    database_count: int
    migration_count: int
    manifest_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} does not exist: {path}")
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is not valid UTF-8 JSON ({type(exc).__name__})")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} root must be an object")
        return None
    return value


def _safe_repo_path(root: Path, raw_path: object, label: str, errors: list[str]) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        errors.append(f"{label} must be a non-empty POSIX-style repository-relative path")
        return None
    relative = Path(raw_path)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label} escapes the repository root")
        return None
    unresolved = root / relative
    current = unresolved
    while current != root:
        if current.is_symlink():
            errors.append(f"{label} must not contain symbolic links")
            return None
        current = current.parent
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        errors.append(f"{label} escapes the repository root")
        return None
    return candidate


def _version(value: object, label: str, errors: list[str]) -> tuple[int, ...] | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+)*", value):
        errors.append(f"{label} must be a dotted numeric version")
        return None
    parts = tuple(int(part) for part in value.split("."))
    if any(part < 0 for part in parts):
        errors.append(f"{label} contains a negative version component")
        return None
    return parts


def _is_next(previous: tuple[int, ...], current: tuple[int, ...]) -> bool:
    return len(previous) == len(current) and previous[:-1] == current[:-1] and current[-1] == previous[-1] + 1


def _parse_time(value: object, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        errors.append(f"{label} must be an RFC3339 UTC timestamp ending in Z")
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        errors.append(f"{label} must be a valid RFC3339 UTC timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        errors.append(f"{label} must use UTC")
        return None
    return parsed


def _require_text(document: dict[str, Any], key: str, label: str, errors: list[str]) -> str | None:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}.{key} must be a non-empty string")
        return None
    return value.strip()


def _validate_manifest(root: Path, manifest_path: Path, document: dict[str, Any], errors: list[str]) -> tuple[int, int]:
    if document.get("formatVersion") != 1:
        errors.append("manifest formatVersion must be 1")
    policy = document.get("policy")
    required_policy = {
        "immutableAfterRelease": True,
        "execution": "reviewed-maintenance-window-only",
        "productionRuntimeSchemaMutation": False,
        "rollback": "restore-or-forward-fix-only",
    }
    if not isinstance(policy, dict):
        errors.append("manifest policy must be an object")
    else:
        for key, expected in required_policy.items():
            if policy.get(key) != expected:
                errors.append(f"manifest policy.{key} must equal {expected!r}")
    databases = document.get("databases")
    if not isinstance(databases, list) or not databases:
        errors.append("manifest databases must be a non-empty array")
        return 0, 0

    database_ids: set[str] = set()
    all_paths: set[Path] = set()
    migration_count = 0
    for database_index, database in enumerate(databases):
        prefix = f"databases[{database_index}]"
        if not isinstance(database, dict):
            errors.append(f"{prefix} must be an object")
            continue
        database_id = _require_text(database, "id", prefix, errors)
        if database_id:
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", database_id):
                errors.append(f"{prefix}.id must use lowercase snake_case")
            if database_id in database_ids:
                errors.append(f"duplicate database id {database_id}")
            database_ids.add(database_id)
        if database.get("engine") not in {"mysql", "postgresql"}:
            errors.append(f"{prefix}.engine must be mysql or postgresql")

        directory = _safe_repo_path(root, database.get("directory"), f"{prefix}.directory", errors)
        if directory is not None and (not directory.exists() or not directory.is_dir()):
            errors.append(f"{prefix}.directory does not exist or is not a directory")

        migrations = database.get("migrations")
        if not isinstance(migrations, list) or not migrations:
            errors.append(f"{prefix}.migrations must be a non-empty array")
            continue

        versions: list[tuple[int, ...]] = []
        version_labels: list[str] = []
        active_paths: set[Path] = set()
        for migration_index, migration in enumerate(migrations):
            entry = f"{prefix}.migrations[{migration_index}]"
            if not isinstance(migration, dict):
                errors.append(f"{entry} must be an object")
                continue
            version_label = migration.get("version")
            parsed_version = _version(version_label, f"{entry}.version", errors)
            if parsed_version is not None:
                if parsed_version in versions:
                    errors.append(f"duplicate migration version {version_label} in {database_id or prefix}")
                versions.append(parsed_version)
                version_labels.append(str(version_label))
            _require_text(migration, "description", entry, errors)
            if migration.get("risk") not in {"expand", "backfill", "rebuild", "contract"}:
                errors.append(f"{entry}.risk must be expand, backfill, rebuild, or contract")
            if migration.get("rollback") not in {"restore", "forward-fix"}:
                errors.append(f"{entry}.rollback must be restore or forward-fix")
            path = _safe_repo_path(root, migration.get("path"), f"{entry}.path", errors)
            if path is None:
                continue
            if path in all_paths:
                errors.append(f"migration path is declared more than once: {path.relative_to(root).as_posix()}")
            all_paths.add(path)
            active_paths.add(path)
            if directory is not None and path.parent != directory:
                errors.append(f"{entry}.path must be directly inside {database.get('directory')}")
            if not path.exists() or not path.is_file():
                errors.append(f"migration file does not exist: {path.relative_to(root).as_posix()}")
                continue
            match = MIGRATION_NAME.fullmatch(path.name)
            if not match:
                errors.append(f"active migration filename is invalid: {path.name}")
            elif isinstance(version_label, str) and match.group("version") != version_label:
                errors.append(f"migration filename/version mismatch for {path.name}")
            expected_sha = migration.get("sha256")
            if not isinstance(expected_sha, str) or not SHA256.fullmatch(expected_sha):
                errors.append(f"{entry}.sha256 must be a lowercase SHA-256 digest")
            elif _sha256(path) != expected_sha:
                errors.append(f"checksum mismatch for {path.relative_to(root).as_posix()}")
            migration_count += 1

        baseline = database.get("baselineVersion")
        if version_labels and baseline != version_labels[0]:
            errors.append(f"{prefix}.baselineVersion must equal first migration version {version_labels[0]}")
        if versions != sorted(versions):
            errors.append(f"{prefix}.migrations must be sorted by version")
        if database.get("requireContiguousVersions") is not True:
            errors.append(f"{prefix}.requireContiguousVersions must be true")
        for previous, current in zip(versions, versions[1:]):
            if not _is_next(previous, current):
                errors.append(
                    f"version gap in {database_id or prefix}: "
                    f"{'.'.join(map(str, previous))} -> {'.'.join(map(str, current))}"
                )

        quarantined = database.get("quarantined")
        if not isinstance(quarantined, list):
            errors.append(f"{prefix}.quarantined must be an array")
            quarantined = []
        for quarantine_index, quarantine in enumerate(quarantined):
            entry = f"{prefix}.quarantined[{quarantine_index}]"
            if not isinstance(quarantine, dict):
                errors.append(f"{entry} must be an object")
                continue
            _require_text(quarantine, "reason", entry, errors)
            path = _safe_repo_path(root, quarantine.get("path"), f"{entry}.path", errors)
            if path is None:
                continue
            if path in all_paths:
                errors.append(f"quarantined path is declared more than once: {path.relative_to(root).as_posix()}")
            all_paths.add(path)
            if not path.exists() or not path.is_file():
                errors.append(f"quarantined migration does not exist: {path.relative_to(root).as_posix()}")
                continue
            if MIGRATION_NAME.fullmatch(path.name):
                errors.append(f"quarantined migration must not retain an active V*__*.sql filename: {path.name}")
            expected_sha = quarantine.get("sha256")
            if not isinstance(expected_sha, str) or not SHA256.fullmatch(expected_sha):
                errors.append(f"{entry}.sha256 must be a lowercase SHA-256 digest")
            elif _sha256(path) != expected_sha:
                errors.append(f"checksum mismatch for {path.relative_to(root).as_posix()}")

        if directory is not None and directory.is_dir():
            discovered = {path.resolve() for path in directory.rglob("V*__*.sql") if path.is_file()}
            for path in sorted(discovered - active_paths):
                errors.append(f"untracked migration: {path.relative_to(root).as_posix()}")

    return len(database_ids), migration_count


def _validate_evidence(
    root: Path,
    manifest_path: Path,
    database_ids: set[str],
    evidence_path: Path | None,
    release_id: str | None,
    release_revision: str | None,
    now: datetime,
    errors: list[str],
) -> None:
    if evidence_path is None:
        errors.append("production migration evidence file is required")
        return
    raw_evidence_path = evidence_path.expanduser()
    if not raw_evidence_path.is_absolute():
        errors.append("production migration evidence file must use an absolute path")
        return
    if raw_evidence_path.is_symlink():
        errors.append("production migration evidence file must not be a symbolic link")
        return
    evidence_path = raw_evidence_path.resolve()
    try:
        evidence_path.relative_to(root)
        errors.append("production migration evidence file must be stored outside the repository")
    except ValueError:
        pass
    document = _load_json(evidence_path, "migration evidence", errors)
    if document is None:
        return
    if os.name != "nt":
        evidence_stat = evidence_path.stat()
        mode = stat.S_IMODE(evidence_stat.st_mode)
        if mode & 0o077:
            errors.append("migration evidence permissions must not grant group or world access")
        if evidence_stat.st_uid != os.geteuid():
            errors.append("migration evidence must be owned by the deployment operator")
    if document.get("formatVersion") != 2:
        errors.append("migration evidence formatVersion must be 2")
    if (not release_id or not RELEASE_ID.fullmatch(release_id)
            or re.search(r"(?:yyyy|sequence|example|latest|current|unknown)", release_id, re.IGNORECASE)):
        errors.append("release_id must be a stable 3-128 character release identifier")
    elif document.get("releaseId") != release_id:
        errors.append("migration evidence releaseId does not match this release")
    if not isinstance(release_revision, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", release_revision):
        errors.append("release_revision must be the immutable lowercase Git commit SHA")
    elif document.get("releaseRevision") != release_revision:
        errors.append("migration evidence releaseRevision does not match this release")
    if document.get("manifestSha256") != _sha256(manifest_path):
        errors.append("migration evidence manifestSha256 does not match the reviewed manifest")
    _require_text(document, "approvedBy", "migration evidence", errors)
    _require_text(document, "changeTicket", "migration evidence", errors)

    created_at = _parse_time(document.get("createdAt"), "migration evidence.createdAt", errors)
    expires_at = _parse_time(document.get("expiresAt"), "migration evidence.expiresAt", errors)
    if created_at is not None and expires_at is not None:
        if created_at > now:
            errors.append("migration evidence createdAt must not be in the future")
        if not created_at <= now <= expires_at:
            errors.append("migration evidence is not currently valid")
        if expires_at - created_at > MAX_EVIDENCE_LIFETIME:
            errors.append("migration evidence lifetime must not exceed 24 hours")

    databases = document.get("databases")
    if not isinstance(databases, dict):
        errors.append("migration evidence.databases must be an object")
        return
    actual_ids = set(databases)
    if actual_ids != database_ids:
        missing = sorted(database_ids - actual_ids)
        extra = sorted(actual_ids - database_ids)
        if missing:
            errors.append(f"migration evidence is missing databases: {', '.join(missing)}")
        if extra:
            errors.append(f"migration evidence contains unknown databases: {', '.join(extra)}")

    for database_id in sorted(database_ids & actual_ids):
        evidence = databases.get(database_id)
        label = f"migration evidence.databases.{database_id}"
        if not isinstance(evidence, dict):
            errors.append(f"{label} must be an object")
            continue
        backup = evidence.get("backup")
        if not isinstance(backup, dict):
            errors.append(f"{label}.backup must be an object")
        else:
            if backup.get("status") != "verified":
                errors.append(f"{label}.backup.status must be verified")
            _require_text(backup, "artifactId", f"{label}.backup", errors)
            checksum = backup.get("sha256")
            if not isinstance(checksum, str) or not SHA256.fullmatch(checksum):
                errors.append(f"{label}.backup.sha256 must be a lowercase SHA-256 digest")
            completed_at = _parse_time(backup.get("completedAt"), f"{label}.backup.completedAt", errors)
            if completed_at is not None:
                if completed_at > now:
                    errors.append(f"{label} backup completedAt must not be in the future")
                elif now - completed_at > MAX_BACKUP_AGE:
                    errors.append(f"{label} backup must be less than 24 hours old")

        restore = evidence.get("restore")
        if not isinstance(restore, dict):
            errors.append(f"{label}.restore must be an object")
        else:
            if restore.get("status") != "passed":
                errors.append(f"{label}.restore.status must be passed")
            _require_text(restore, "drillId", f"{label}.restore", errors)
            target = _require_text(restore, "target", f"{label}.restore", errors)
            if target and (
                PRODUCTION_TARGET.search(target)
                or not any(marker in target.lower() for marker in ("isolated", "rehearsal"))
            ):
                errors.append(f"{label} restore target must be isolated and non-production")
            verified_at = _parse_time(restore.get("verifiedAt"), f"{label}.restore.verifiedAt", errors)
            if verified_at is not None:
                if verified_at > now:
                    errors.append(f"{label} restore verifiedAt must not be in the future")
                elif now - verified_at > MAX_RESTORE_AGE:
                    errors.append(f"{label} restore drill must be less than 90 days old")


def validate_repository(
    *,
    root: Path,
    manifest_path: Path,
    production: bool = False,
    evidence_path: Path | None = None,
    release_id: str | None = None,
    release_revision: str | None = None,
    now: datetime | None = None,
) -> ValidationResult:
    """Validate migration immutability and, optionally, production evidence."""
    errors: list[str] = []
    root = root.resolve()
    manifest_path = manifest_path.resolve()
    try:
        manifest_path.relative_to(root)
    except ValueError:
        errors.append("migration manifest must be stored inside the repository")
    document = _load_json(manifest_path, "migration manifest", errors)
    if document is None:
        raise MigrationValidationError(errors)
    database_count, migration_count = _validate_manifest(root, manifest_path, document, errors)
    databases = document.get("databases")
    database_ids = {
        item.get("id") for item in databases if isinstance(item, dict) and isinstance(item.get("id"), str)
    } if isinstance(databases, list) else set()
    if production:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            errors.append("validation time must be timezone-aware")
        else:
            _validate_evidence(
                root,
                manifest_path,
                database_ids,
                evidence_path,
                release_id,
                release_revision,
                current.astimezone(timezone.utc),
                errors,
            )
    if errors:
        raise MigrationValidationError(errors)
    return ValidationResult(database_count, migration_count, _sha256(manifest_path))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--evidence-file", type=Path)
    parser.add_argument("--release-id")
    parser.add_argument("--release-revision")
    parser.add_argument("--now", help="RFC3339 UTC timestamp used only for deterministic verification")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = args.root.resolve()
    manifest = (args.manifest or root / "db" / "migrations-manifest.json").resolve()
    now = None
    if args.now:
        parse_errors: list[str] = []
        now = _parse_time(args.now, "--now", parse_errors)
        if parse_errors:
            print("\n".join(parse_errors), file=sys.stderr)
            return 2
    try:
        result = validate_repository(
            root=root,
            manifest_path=manifest,
            production=args.production,
            evidence_path=args.evidence_file,
            release_id=args.release_id,
            release_revision=args.release_revision,
            now=now,
        )
    except MigrationValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "Migration validation passed: "
        f"databases={result.database_count} migrations={result.migration_count} "
        f"manifestSha256={result.manifest_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
