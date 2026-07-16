"""Tenant-scoped, durable governance for publicly served upload assets."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..core.config import settings
from ..core.database import engine
from ..core.http_failures import get_request_id
from ..core.image_security import ValidatedImage


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_-]+")
_ALLOWED_VISIBILITIES = frozenset({"private", "public"})
ALLOWED_PUBLIC_UPLOAD_PURPOSES = frozenset({"carousel", "open-source-content"})
_RESERVATION_STALE_SECONDS = 10 * 60
_GLOBAL_UPLOAD_WRITE_SEMAPHORE = asyncio.BoundedSemaphore(
    settings.resolved_upload_max_concurrent_global
)


class UploadGovernanceError(RuntimeError):
    def __init__(self, public_message: str, status_code: int):
        self.public_message = public_message
        self.status_code = status_code
        super().__init__(public_message)


class UploadGovernanceUnavailable(UploadGovernanceError):
    def __init__(self):
        super().__init__("上传治理服务暂时不可用，请稍后重试", 503)


@dataclass(frozen=True)
class GovernedUpload:
    asset_id: int
    storage_key: str
    public_url: str
    saved_name: str
    size: int
    sha256: str


def enforce_upload_admission(
    *, recent_count: int, concurrent_count: int, used_bytes: int,
    global_concurrent_count: int, global_used_bytes: int, incoming_bytes: int
) -> None:
    """Pure admission policy shared by the database reservation path and tests.

    存储配额（tenant / global）检查已被有意移除：用户上传不再受容量限制，
    磁盘占用由 UploadStorageCleanupService 每日清理 7 天前未被引用的图片来约束。
    此处仅保留请求频率与并发上限，用于防止滥用。
    """

    if recent_count >= settings.resolved_upload_rate_limit_requests:
        raise UploadGovernanceError("上传请求过于频繁，请稍后重试", 429)
    if concurrent_count >= settings.resolved_upload_max_concurrent_per_tenant:
        raise UploadGovernanceError("当前租户并发上传已达上限，请稍后重试", 429)
    if global_concurrent_count >= settings.resolved_upload_max_concurrent_global:
        raise UploadGovernanceError("平台并发上传已达上限，请稍后重试", 429)


def _positive_id(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise UploadGovernanceError(f"{field} 必须为正整数", 400) from exc
    if parsed <= 0:
        raise UploadGovernanceError(f"{field} 必须为正整数", 400)
    return parsed


def _safe_component(value: str, fallback: str) -> str:
    normalized = _SAFE_COMPONENT.sub("-", str(value or "").strip()).strip("-_")
    return (normalized or fallback)[:48]


def _validated_visibility(value: str) -> str:
    visibility = str(value or "private").strip().lower()
    if visibility not in _ALLOWED_VISIBILITIES:
        raise UploadGovernanceError("图片可见性参数无效", 400)
    return visibility


def _atomic_write_file(
    tenant_dir: Path,
    temporary_path: Path,
    final_path: Path,
    content: bytes,
) -> None:
    """Perform blocking durable filesystem work outside the event loop."""

    tenant_dir.mkdir(parents=True, exist_ok=True)
    with open(temporary_path, "xb") as file_obj:
        file_obj.write(content)
        file_obj.flush()
        os.fsync(file_obj.fileno())
    os.replace(temporary_path, final_path)
    if os.name != "nt":
        directory_fd = os.open(tenant_dir, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def _unlink_files(paths: tuple[Path | None, ...]) -> None:
    for candidate in paths:
        if candidate is None:
            continue
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            continue


def _purge_failed_files(
    root: Path,
    tenant_root: Path,
    rows: list[dict[str, Any]],
) -> list[int]:
    deleted_ids: list[int] = []
    for row in rows:
        candidate = (root / str(row["storage_key"])).resolve()
        if tenant_root not in candidate.parents:
            continue
        candidate.unlink(missing_ok=True)
        deleted_ids.append(int(row["id"]))
    if tenant_root.exists():
        cutoff = time.time() - _RESERVATION_STALE_SECONDS
        for part_file in tenant_root.glob("*.part"):
            try:
                if part_file.is_file() and part_file.stat().st_mtime < cutoff:
                    part_file.unlink(missing_ok=True)
            except OSError:
                continue
    return deleted_ids


def _probe_upload_storage_sync(root: Path) -> None:
    probe_dir = (root / ".readiness").resolve()
    if root not in probe_dir.parents:
        raise OSError("upload readiness path escapes root")
    token = secrets.token_urlsafe(18)
    temporary = probe_dir / f"probe-{token}.part"
    final = probe_dir / f"probe-{token}"
    try:
        _atomic_write_file(probe_dir, temporary, final, b"upload-ready")
        if final.read_bytes() != b"upload-ready":
            raise OSError("upload readiness content mismatch")
    finally:
        _unlink_files((temporary, final))


async def probe_upload_storage(base_dir: str) -> None:
    root = Path(base_dir).resolve()
    try:
        await asyncio.to_thread(_probe_upload_storage_sync, root)
    except OSError as exc:
        raise UploadGovernanceUnavailable() from exc


def _recover_deleting_file(root: Path, row: dict[str, Any]) -> str:
    tenant_id = int(row["tenant_id"])
    storage_key = str(row["storage_key"])
    tenant_root = (root / f"tenant-{tenant_id}").resolve()
    candidate = (root / storage_key).resolve()
    if tenant_root not in candidate.parents:
        return "failed"
    if candidate.exists():
        return "active"
    trash_files = sorted(candidate.parent.glob(f".{candidate.name}.trash-{int(row['id'])}-*"))
    if trash_files:
        os.replace(trash_files[0], candidate)
        return "active"
    return "failed"


def _remove_failed_file(root: Path, row: dict[str, Any]) -> None:
    storage_key = str(row["storage_key"])
    if storage_key.startswith("transient/"):
        return
    tenant_id = int(row["tenant_id"])
    tenant_root = (root / f"tenant-{tenant_id}").resolve()
    candidate = (root / storage_key).resolve()
    if tenant_root not in candidate.parents:
        return
    candidate.unlink(missing_ok=True)
    for trash_file in candidate.parent.glob(f".{candidate.name}.trash-{int(row['id'])}-*"):
        trash_file.unlink(missing_ok=True)


def _purge_stale_part_and_trash_files(root: Path) -> None:
    cutoff = time.time() - _RESERVATION_STALE_SECONDS
    for tenant_root in root.glob("tenant-*"):
        if not tenant_root.is_dir():
            continue
        for pattern in ("*.part",):
            for candidate in tenant_root.glob(pattern):
                try:
                    if candidate.is_file() and candidate.stat().st_mtime < cutoff:
                        candidate.unlink(missing_ok=True)
                except OSError:
                    continue


async def reconcile_storage_assets(base_dir: str, *, limit: int = 1000) -> dict[str, int]:
    """Recover stale DB/file states across all tenants after crashes."""

    root = Path(base_dir).resolve()
    safe_limit = max(1, min(int(limit), 5000))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(
                "UPDATE tenant_storage_asset SET status='failed', "
                "deletion_reason='reservation timeout', updated_time=NOW() "
                "WHERE status='reserved' AND created_time < "
                "TIMESTAMPADD(SECOND, -:stale_seconds, NOW())"
            ), {"stale_seconds": _RESERVATION_STALE_SECONDS})
        async with engine.connect() as connection:
            failed_rows = (await connection.execute(text(
                "SELECT id, tenant_id, storage_key FROM tenant_storage_asset "
                "WHERE status='failed' ORDER BY id ASC LIMIT :limit"
            ), {"limit": safe_limit})).mappings().all()
            deleting_rows = (await connection.execute(text(
                "SELECT id, tenant_id, storage_key FROM tenant_storage_asset "
                "WHERE status='deleting' AND updated_time < "
                "TIMESTAMPADD(SECOND, -:stale_seconds, NOW()) "
                "ORDER BY id ASC LIMIT :limit"
            ), {
                "stale_seconds": _RESERVATION_STALE_SECONDS,
                "limit": safe_limit,
            })).mappings().all()
            deleted_rows = (await connection.execute(text(
                "SELECT id, tenant_id, storage_key FROM tenant_storage_asset "
                "WHERE status='deleted' AND storage_key LIKE 'tenant-%' "
                "ORDER BY updated_time DESC LIMIT :limit"
            ), {"limit": safe_limit})).mappings().all()
    except SQLAlchemyError as exc:
        raise UploadGovernanceUnavailable() from exc

    recovered_active: list[int] = []
    recovered_failed: list[int] = []
    for row in deleting_rows:
        state = await asyncio.to_thread(_recover_deleting_file, root, dict(row))
        (recovered_active if state == "active" else recovered_failed).append(int(row["id"]))
    for row in failed_rows:
        await asyncio.to_thread(_remove_failed_file, root, dict(row))
    for row in deleted_rows:
        await asyncio.to_thread(_remove_failed_file, root, dict(row))
    await asyncio.to_thread(_purge_stale_part_and_trash_files, root)

    try:
        async with engine.begin() as connection:
            for asset_id in recovered_active:
                await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='active', cleaned_by=NULL, "
                    "deletion_reason='cleanup claim recovered', updated_time=NOW() "
                    "WHERE id=:asset_id AND status='deleting'"
                ), {"asset_id": asset_id})
            for asset_id in recovered_failed:
                await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='failed', "
                    "deletion_reason='cleanup claim missing asset', updated_time=NOW() "
                    "WHERE id=:asset_id AND status='deleting'"
                ), {"asset_id": asset_id})
            for row in failed_rows:
                await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='deleted', deleted_time=NOW(), "
                    "cleaned_by='storage-reconciler', updated_time=NOW() "
                    "WHERE id=:asset_id AND status='failed'"
                ), {"asset_id": int(row["id"])})
    except SQLAlchemyError as exc:
        raise UploadGovernanceUnavailable() from exc
    return {
        "failedPurged": len(failed_rows),
        "deletingRecovered": len(recovered_active),
        "deletingFailed": len(recovered_failed),
        "deletedArtifactsPurged": len(deleted_rows),
    }


async def store_governed_image(
    image: ValidatedImage,
    *,
    tenant_id: int,
    user_id: int | None,
    prefix: str,
    source_type: str,
    base_dir: str,
    visibility: str = "private",
    purpose: str = "user-media",
    owner_type: str | None = None,
    owner_id: int | None = None,
) -> GovernedUpload:
    """Reserve quota, atomically store an image, and persist its audit state."""

    if not settings.resolved_upload_governance_enabled:
        raise UploadGovernanceUnavailable()
    tenant_id = _positive_id(tenant_id, "tenantId")
    normalized_user_id = None
    if user_id not in (None, 0, "0", ""):
        normalized_user_id = _positive_id(user_id, "userId")
    if not image.content or len(image.content) <= 0:
        raise UploadGovernanceError("图片文件不能为空", 400)

    safe_prefix = _safe_component(prefix, "img")
    safe_source = _safe_component(source_type, "image")
    safe_visibility = _validated_visibility(visibility)
    safe_purpose = _safe_component(purpose, "user-media")
    safe_owner_type = _safe_component(
        owner_type or ("user" if normalized_user_id else "service"),
        "service",
    )[:32]
    if safe_visibility == "public" and (
        safe_purpose not in ALLOWED_PUBLIC_UPLOAD_PURPOSES
        or safe_owner_type != "service"
    ):
        raise UploadGovernanceError("公开图片用途或发布主体无效", 403)
    normalized_owner_id = None
    if owner_id not in (None, 0, "0", ""):
        normalized_owner_id = _positive_id(owner_id, "ownerId")
    elif normalized_user_id:
        normalized_owner_id = normalized_user_id
    saved_name = f"{safe_prefix}_{secrets.token_urlsafe(18)}{image.extension}"
    tenant_segment = f"tenant-{tenant_id}"
    storage_key = f"{tenant_segment}/{saved_name}"
    public_url = f"/uploads/images/{storage_key}"
    digest = hashlib.sha256(image.content).hexdigest()
    request_id = (get_request_id() or "")[:128] or None

    root = Path(base_dir).resolve()
    tenant_dir = (root / tenant_segment).resolve()
    if root not in tenant_dir.parents:
        raise UploadGovernanceUnavailable()
    final_path = (tenant_dir / saved_name).resolve()
    if tenant_dir not in final_path.parents:
        raise UploadGovernanceUnavailable()
    temporary_path = final_path.with_name(final_path.name + ".part")

    async with _GLOBAL_UPLOAD_WRITE_SEMAPHORE:
        asset_id = await _reserve_asset(
            tenant_id=tenant_id,
            user_id=normalized_user_id,
            storage_key=storage_key,
            public_url=public_url,
            media_type=image.media_type,
            source_type=safe_source,
            visibility=safe_visibility,
            purpose=safe_purpose,
            owner_type=safe_owner_type,
            owner_id=normalized_owner_id,
            size_bytes=len(image.content),
            sha256=digest,
            request_id=request_id,
        )
        try:
            await _purge_failed_assets(tenant_id, root)
            await asyncio.to_thread(
                _atomic_write_file,
                tenant_dir,
                temporary_path,
                final_path,
                image.content,
            )
            await _activate_asset(asset_id, tenant_id)
        except Exception as exc:
            await asyncio.to_thread(_unlink_files, (temporary_path, final_path))
            await _mark_failed(asset_id, tenant_id, type(exc).__name__)
            if isinstance(exc, UploadGovernanceError):
                raise
            raise UploadGovernanceUnavailable() from exc

    return GovernedUpload(
        asset_id=asset_id,
        storage_key=storage_key,
        public_url=public_url,
        saved_name=saved_name,
        size=len(image.content),
        sha256=digest,
    )


async def _reserve_asset(
    *,
    tenant_id: int,
    user_id: int | None,
    storage_key: str,
    public_url: str,
    media_type: str,
    source_type: str,
    visibility: str,
    purpose: str,
    owner_type: str | None,
    owner_id: int | None,
    size_bytes: int,
    sha256: str,
    request_id: str | None,
) -> int:
    lock_names = ("tenant-upload-global", f"tenant-upload-{tenant_id}")
    acquired_locks: list[str] = []
    try:
        async with engine.connect() as connection:
            for lock_name in lock_names:
                acquired = await connection.scalar(
                    text("SELECT GET_LOCK(:lock_name, 2)"), {"lock_name": lock_name}
                )
                await connection.commit()
                if int(acquired or 0) != 1:
                    for held_lock in reversed(acquired_locks):
                        try:
                            await connection.execute(
                                text("SELECT RELEASE_LOCK(:lock_name)"),
                                {"lock_name": held_lock},
                            )
                            await connection.commit()
                        except SQLAlchemyError:
                            pass
                    acquired_locks.clear()
                    raise UploadGovernanceError("当前上传请求过多，请稍后重试", 429)
                acquired_locks.append(lock_name)
            transaction = await connection.begin()
            try:
                await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='failed', "
                    "deletion_reason='reservation timeout', updated_time=NOW() "
                    "WHERE status='reserved' "
                    "AND created_time < TIMESTAMPADD(SECOND, -:stale_seconds, NOW())"
                ), {"stale_seconds": _RESERVATION_STALE_SECONDS})
                await connection.execute(text(
                    "DELETE FROM tenant_upload_rate_event "
                    "WHERE created_time < TIMESTAMPADD(SECOND, -:retention_seconds, NOW())"
                ), {
                    "retention_seconds": max(
                        settings.resolved_upload_rate_limit_window_seconds * 2, 3600
                    ),
                })

                recent_count = await connection.scalar(text(
                    "SELECT COUNT(*) FROM tenant_upload_rate_event WHERE tenant_id=:tenant_id "
                    "AND created_time >= TIMESTAMPADD(SECOND, -:window_seconds, NOW())"
                ), {
                    "tenant_id": tenant_id,
                    "window_seconds": settings.resolved_upload_rate_limit_window_seconds,
                })
                concurrent = await connection.scalar(text(
                    "SELECT COUNT(*) FROM tenant_storage_asset "
                    "WHERE tenant_id=:tenant_id AND status='reserved'"
                ), {"tenant_id": tenant_id})
                global_concurrent = await connection.scalar(text(
                    "SELECT COUNT(*) FROM tenant_storage_asset WHERE status='reserved'"
                ))
                # 存储配额检查已移除，无需查询 used_bytes / global_used_bytes。
                # 保留 enforce_upload_admission 调用以维持频率与并发上限策略。
                enforce_upload_admission(
                    recent_count=int(recent_count or 0),
                    concurrent_count=int(concurrent or 0),
                    global_concurrent_count=int(global_concurrent or 0),
                    used_bytes=0,
                    global_used_bytes=0,
                    incoming_bytes=size_bytes,
                )

                await connection.execute(text(
                    "INSERT INTO tenant_upload_rate_event(tenant_id,user_id,request_id,created_time) "
                    "VALUES(:tenant_id,:user_id,:request_id,NOW())"
                ), {"tenant_id": tenant_id, "user_id": user_id, "request_id": request_id})
                await connection.execute(text(
                    "INSERT INTO tenant_storage_asset(tenant_id,user_id,storage_key,public_url,media_type,"
                    "source_type,visibility,purpose,owner_type,owner_id,size_bytes,sha256,status,"
                    "request_id,created_time,updated_time) "
                    "VALUES(:tenant_id,:user_id,:storage_key,:public_url,:media_type,:source_type,"
                    ":visibility,:purpose,:owner_type,:owner_id,:size_bytes,:sha256,'reserved',"
                    ":request_id,NOW(),NOW())"
                ), {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "storage_key": storage_key,
                    "public_url": public_url,
                    "media_type": media_type,
                    "source_type": source_type,
                    "visibility": visibility,
                    "purpose": purpose,
                    "owner_type": owner_type,
                    "owner_id": owner_id,
                    "size_bytes": size_bytes,
                    "sha256": sha256,
                    "request_id": request_id,
                })
                asset_id = await connection.scalar(text("SELECT LAST_INSERT_ID()"))
                if not asset_id:
                    raise UploadGovernanceUnavailable()
                await transaction.commit()
                return int(asset_id)
            except Exception:
                if transaction.is_active:
                    await transaction.rollback()
                raise
            finally:
                for lock_name in reversed(acquired_locks):
                    try:
                        await connection.execute(
                            text("SELECT RELEASE_LOCK(:lock_name)"), {"lock_name": lock_name}
                        )
                        await connection.commit()
                    except SQLAlchemyError:
                        pass
    except UploadGovernanceError:
        raise
    except SQLAlchemyError as exc:
        raise UploadGovernanceUnavailable() from exc


async def _activate_asset(asset_id: int, tenant_id: int) -> None:
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(
                "UPDATE tenant_storage_asset SET status='active', activated_time=NOW(), "
                "published_time=CASE WHEN visibility='public' THEN NOW() ELSE NULL END, "
                "updated_time=NOW() "
                "WHERE id=:asset_id AND tenant_id=:tenant_id AND status='reserved'"
            ), {"asset_id": asset_id, "tenant_id": tenant_id})
            if result.rowcount != 1:
                raise UploadGovernanceUnavailable()
    except UploadGovernanceError:
        raise
    except SQLAlchemyError as exc:
        raise UploadGovernanceUnavailable() from exc


async def _mark_failed(asset_id: int, tenant_id: int, reason: str) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(text(
                "UPDATE tenant_storage_asset SET status='failed', deletion_reason=:reason, "
                "updated_time=NOW() WHERE id=:asset_id AND tenant_id=:tenant_id AND status='reserved'"
            ), {
                "asset_id": asset_id,
                "tenant_id": tenant_id,
                "reason": _safe_component(reason, "storage failure")[:255],
            })
    except SQLAlchemyError:
        pass


async def _purge_failed_assets(tenant_id: int, root: Path) -> None:
    """Remove crash leftovers for already failed reservations and audit deletion."""

    tenant_root = (root / f"tenant-{tenant_id}").resolve()
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(text(
                "SELECT id, storage_key FROM tenant_storage_asset "
                "WHERE tenant_id=:tenant_id AND status='failed' ORDER BY id ASC LIMIT 1000"
            ), {"tenant_id": tenant_id})).mappings().all()
        deleted_ids = await asyncio.to_thread(
            _purge_failed_files,
            root,
            tenant_root,
            [dict(row) for row in rows],
        )
        if deleted_ids:
            placeholders = ",".join(f":id_{index}" for index in range(len(deleted_ids)))
            params = {f"id_{index}": asset_id for index, asset_id in enumerate(deleted_ids)}
            params["tenant_id"] = tenant_id
            async with engine.begin() as connection:
                await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='deleted', deleted_time=NOW(), "
                    "cleaned_by='crash-recovery', updated_time=NOW() "
                    f"WHERE tenant_id=:tenant_id AND status='failed' AND id IN ({placeholders})"
                ), params)
    except (OSError, SQLAlchemyError) as exc:
        raise UploadGovernanceUnavailable() from exc


@asynccontextmanager
async def govern_transient_upload(
    content: bytes,
    *,
    tenant_id: int,
    user_id: int | None,
    source_type: str,
):
    """Apply the same rate/concurrency/quota admission to non-persisted uploads."""

    tenant_id = _positive_id(tenant_id, "tenantId")
    normalized_user_id = None
    if user_id not in (None, 0, "0", ""):
        normalized_user_id = _positive_id(user_id, "userId")
    payload = bytes(content or b"")
    if not payload:
        raise UploadGovernanceError("上传内容不能为空", 400)
    source = _safe_component(source_type, "transient")
    token = secrets.token_urlsafe(18)
    storage_key = f"transient/tenant-{tenant_id}/{source}-{token}"
    asset_id = await _reserve_asset(
        tenant_id=tenant_id,
        user_id=normalized_user_id,
        storage_key=storage_key,
        public_url="",
        media_type="application/octet-stream",
        source_type=source,
        visibility="private",
        purpose="transient",
        owner_type="user" if normalized_user_id else "service",
        owner_id=normalized_user_id,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        request_id=(get_request_id() or "")[:128] or None,
    )
    try:
        yield asset_id
        async with engine.begin() as connection:
            await connection.execute(text(
                "UPDATE tenant_storage_asset SET status='deleted', activated_time=NOW(), deleted_time=NOW(), "
                "deletion_reason='transient upload completed', cleaned_by='system', updated_time=NOW() "
                "WHERE id=:asset_id AND tenant_id=:tenant_id AND status='reserved'"
            ), {"asset_id": asset_id, "tenant_id": tenant_id})
    except Exception as exc:
        await _mark_failed(asset_id, tenant_id, type(exc).__name__)
        raise


def _quarantine_for_deletion(candidate: Path, trash_path: Path) -> bool:
    if not candidate.exists():
        return False
    os.replace(candidate, trash_path)
    return True


def _restore_quarantined_file(trash_path: Path, candidate: Path) -> bool:
    if trash_path.exists() and not candidate.exists():
        os.replace(trash_path, candidate)
    return candidate.is_file() and not trash_path.exists()


async def cleanup_expired_assets(
    *,
    tenant_id: int,
    older_than_days: int,
    dry_run: bool,
    actor: str,
    reason: str,
    reviewed_by: str | None = None,
    approved_by: str | None = None,
    base_dir: str,
    asset_ids: list[int] | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """List or delete policy-expired assets while preserving a durable audit row."""

    tenant_id = _positive_id(tenant_id, "tenantId")
    minimum_age = settings.resolved_upload_retention_days
    if older_than_days < minimum_age:
        raise UploadGovernanceError(f"清理期限不能短于配置的 {minimum_age} 天", 400)
    safe_actor = _safe_component(actor, "system")[:120]
    safe_reason = str(reason or "").strip()[:255]
    safe_reviewer = _safe_component(reviewed_by or "", "")[:120]
    safe_approver = _safe_component(approved_by or "", "")[:120]
    if not dry_run and (not safe_reason or len(safe_reason) < 3):
        raise UploadGovernanceError("执行清理时必须填写原因", 400)
    if not dry_run and (
        not safe_reviewer or not safe_approver or safe_reviewer == safe_approver
    ):
        raise UploadGovernanceError("执行清理必须由不同的复核人与批准人双人确认", 400)
    safe_limit = max(1, min(int(limit), 1000))
    reviewed_ids = {
        _positive_id(asset_id, "assetId") for asset_id in (asset_ids or [])
    }
    if not dry_run and not reviewed_ids:
        raise UploadGovernanceError("执行清理必须提交审核后的 assetIds", 400)

    root = Path(base_dir).resolve()
    await reconcile_storage_assets(base_dir)
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(text(
                "SELECT id, storage_key, public_url, size_bytes FROM tenant_storage_asset "
                "WHERE tenant_id=:tenant_id AND status='active' "
                "AND created_time < TIMESTAMPADD(DAY, -:older_than_days, NOW()) "
                "ORDER BY id ASC LIMIT :limit"
            ), {
                "tenant_id": tenant_id,
                "older_than_days": older_than_days,
                "limit": safe_limit,
            })).mappings().all()
    except SQLAlchemyError as exc:
        raise UploadGovernanceUnavailable() from exc

    if not dry_run:
        rows = [row for row in rows if int(row["id"]) in reviewed_ids]
        matched_ids = {int(row["id"]) for row in rows}
        if matched_ids != reviewed_ids:
            raise UploadGovernanceError(
                "部分 assetIds 不属于当前租户、仍被保留或尚未达到清理期限", 409
            )

    result = {
        "dryRun": dry_run,
        "candidateCount": len(rows),
        "candidateBytes": sum(int(row["size_bytes"] or 0) for row in rows),
        "deletedCount": 0,
        "deletedBytes": 0,
        "assets": [str(row["public_url"]) for row in rows],
    }
    if dry_run:
        return result

    tenant_root = (root / f"tenant-{tenant_id}").resolve()
    for row in rows:
        asset_id = int(row["id"])
        storage_key = str(row["storage_key"])
        candidate = (root / storage_key).resolve()
        if tenant_root not in candidate.parents:
            continue
        trash_path = candidate.with_name(
            f".{candidate.name}.trash-{asset_id}-{secrets.token_urlsafe(10)}"
        )
        quarantined = False
        deletion_recorded = False
        try:
            async with engine.begin() as connection:
                claimed = await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='deleting', cleaned_by=:actor, "
                    "reviewed_by=:reviewer, approved_by=:approver, "
                    "deletion_reason=:reason, updated_time=NOW() "
                    "WHERE id=:asset_id AND tenant_id=:tenant_id AND status='active'"
                ), {
                    "asset_id": asset_id,
                    "tenant_id": tenant_id,
                    "actor": safe_actor,
                    "reviewer": safe_reviewer,
                    "approver": safe_approver,
                    "reason": safe_reason,
                })
                if claimed.rowcount != 1:
                    continue
            quarantined = await asyncio.to_thread(
                _quarantine_for_deletion, candidate, trash_path
            )
            async with engine.begin() as connection:
                deleted = await connection.execute(text(
                    "UPDATE tenant_storage_asset SET status='deleted', deleted_time=NOW(), "
                    "updated_time=NOW() WHERE id=:asset_id AND tenant_id=:tenant_id AND status='deleting'"
                ), {"asset_id": asset_id, "tenant_id": tenant_id})
                if deleted.rowcount != 1:
                    raise UploadGovernanceUnavailable()
            deletion_recorded = True
            if quarantined:
                await asyncio.to_thread(trash_path.unlink, missing_ok=True)
            result["deletedCount"] += 1
            result["deletedBytes"] += int(row["size_bytes"] or 0)
        except (OSError, SQLAlchemyError, UploadGovernanceError):
            restore_succeeded = not quarantined
            if quarantined and not deletion_recorded:
                try:
                    restore_succeeded = await asyncio.to_thread(
                        _restore_quarantined_file, trash_path, candidate
                    )
                except OSError:
                    restore_succeeded = False
            if deletion_recorded:
                raise UploadGovernanceUnavailable()
            try:
                async with engine.begin() as connection:
                    if restore_succeeded:
                        await connection.execute(text(
                            "UPDATE tenant_storage_asset SET status='active', updated_time=NOW() "
                            "WHERE id=:asset_id AND tenant_id=:tenant_id AND status='deleting'"
                        ), {"asset_id": asset_id, "tenant_id": tenant_id})
                    else:
                        await connection.execute(text(
                            "UPDATE tenant_storage_asset SET status='failed', "
                            "deletion_reason='quarantine restore failure', updated_time=NOW() "
                            "WHERE id=:asset_id AND tenant_id=:tenant_id AND status='deleting'"
                        ), {"asset_id": asset_id, "tenant_id": tenant_id})
            except SQLAlchemyError:
                pass
            raise UploadGovernanceUnavailable()
    return result


__all__ = [
    "GovernedUpload",
    "UploadGovernanceError",
    "UploadGovernanceUnavailable",
    "cleanup_expired_assets",
    "enforce_upload_admission",
    "govern_transient_upload",
    "probe_upload_storage",
    "reconcile_storage_assets",
    "store_governed_image",
]
