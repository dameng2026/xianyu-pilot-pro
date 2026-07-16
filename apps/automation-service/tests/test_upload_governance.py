import asyncio
import threading
from pathlib import Path

import pytest

from app.core.image_security import ValidatedImage
from app.services import upload_governance as governance


def _image() -> ValidatedImage:
    return ValidatedImage(
        content=b"validated-image-content",
        extension=".png",
        media_type="image/png",
        width=8,
        height=8,
    )


@pytest.mark.parametrize(
    ("values", "status"),
    [
        ({"recent_count": 30, "concurrent_count": 0, "global_concurrent_count": 0, "used_bytes": 0, "global_used_bytes": 0}, 429),
        ({"recent_count": 0, "concurrent_count": 2, "global_concurrent_count": 0, "used_bytes": 0, "global_used_bytes": 0}, 429),
        ({"recent_count": 0, "concurrent_count": 0, "global_concurrent_count": 8, "used_bytes": 0, "global_used_bytes": 0}, 429),
    ],
)
def test_upload_admission_enforces_rate_and_concurrency_only(values, status):
    """存储配额检查已被有意移除；仅保留频率与并发上限。"""
    with pytest.raises(governance.UploadGovernanceError) as error:
        governance.enforce_upload_admission(**values, incoming_bytes=1)

    assert error.value.status_code == status


@pytest.mark.parametrize(
    ("used_bytes", "global_used_bytes"),
    [
        (100 * 1024 * 1024, 0),    # 超出原租户配额
        (0, 10 * 1024 * 1024 * 1024),  # 超出原平台配额
        (1024 * 1024 * 1024 * 1024, 10 * 1024 * 1024 * 1024 * 1024),  # 远超任何配额
    ],
)
def test_upload_admission_no_longer_enforces_storage_quota(used_bytes, global_used_bytes):
    """无论 used_bytes / global_used_bytes 多大，都不应触发配额错误。"""
    governance.enforce_upload_admission(
        recent_count=0,
        concurrent_count=0,
        global_concurrent_count=0,
        used_bytes=used_bytes,
        global_used_bytes=global_used_bytes,
        incoming_bytes=1,
    )


@pytest.mark.asyncio
async def test_governed_store_uses_tenant_directory_and_activates_audit_row(monkeypatch, tmp_path: Path):
    activated = []

    async def _reserve(**kwargs):
        assert kwargs["tenant_id"] == 7
        assert kwargs["storage_key"].startswith("tenant-7/")
        assert kwargs["visibility"] == "private"
        assert kwargs["purpose"] == "user-media"
        assert kwargs["owner_type"] == "user"
        assert kwargs["owner_id"] == 3
        return 91

    async def _activate(asset_id, tenant_id):
        activated.append((asset_id, tenant_id))

    async def _purge(*_args):
        return None

    monkeypatch.setattr(governance, "_reserve_asset", _reserve)
    monkeypatch.setattr(governance, "_activate_asset", _activate)
    monkeypatch.setattr(governance, "_purge_failed_assets", _purge)

    result = await governance.store_governed_image(
        _image(),
        tenant_id=7,
        user_id=3,
        prefix="test",
        source_type="unit-test",
        base_dir=str(tmp_path),
    )

    assert result.public_url.startswith("/uploads/images/tenant-7/")
    assert (tmp_path / result.storage_key).read_bytes() == _image().content
    assert activated == [(91, 7)]


@pytest.mark.asyncio
async def test_activation_failure_removes_file_and_marks_reservation_failed(monkeypatch, tmp_path: Path):
    failed = []

    async def _reserve(**_kwargs):
        return 92

    async def _activate(*_args):
        raise governance.UploadGovernanceUnavailable()

    async def _mark(asset_id, tenant_id, reason):
        failed.append((asset_id, tenant_id, reason))

    async def _purge(*_args):
        return None

    monkeypatch.setattr(governance, "_reserve_asset", _reserve)
    monkeypatch.setattr(governance, "_activate_asset", _activate)
    monkeypatch.setattr(governance, "_mark_failed", _mark)
    monkeypatch.setattr(governance, "_purge_failed_assets", _purge)

    with pytest.raises(governance.UploadGovernanceUnavailable):
        await governance.store_governed_image(
            _image(),
            tenant_id=7,
            user_id=3,
            prefix="test",
            source_type="unit-test",
            base_dir=str(tmp_path),
        )

    assert list(tmp_path.rglob("*.png")) == []
    assert failed and failed[0][:2] == (92, 7)


@pytest.mark.asyncio
async def test_blocking_atomic_write_runs_off_the_event_loop(monkeypatch, tmp_path: Path):
    started = threading.Event()
    release = threading.Event()

    async def _reserve(**_kwargs):
        return 93

    async def _noop(*_args):
        return None

    def _blocking_write(*_args):
        started.set()
        assert release.wait(timeout=2)

    monkeypatch.setattr(governance, "_reserve_asset", _reserve)
    monkeypatch.setattr(governance, "_activate_asset", _noop)
    monkeypatch.setattr(governance, "_purge_failed_assets", _noop)
    monkeypatch.setattr(governance, "_atomic_write_file", _blocking_write)

    task = asyncio.create_task(governance.store_governed_image(
        _image(),
        tenant_id=7,
        user_id=3,
        prefix="test",
        source_type="unit-test",
        base_dir=str(tmp_path),
    ))
    assert await asyncio.to_thread(started.wait, 1)
    await asyncio.wait_for(asyncio.sleep(0), timeout=0.1)
    release.set()
    await task


def test_storage_governance_uses_cross_process_database_locks_and_durable_audit_tables():
    source = Path(governance.__file__).read_text(encoding="utf-8")

    assert '"tenant-upload-global"' in source
    assert "GET_LOCK" in source
    assert "tenant_storage_asset" in source
    assert "tenant_upload_rate_event" in source
    assert "global_concurrent_count" in source
    assert "SELECT COUNT(*) FROM tenant_storage_asset WHERE status='reserved'" in source
    assert "asyncio.to_thread" in source
    assert "idx_storage_asset_status_created" in Path(
        governance.__file__
    ).parents[3].joinpath(
        "core-api/src/main/resources/db/migration/V1.14__add_tenant_storage_governance.sql"
    ).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_cleanup_execution_requires_distinct_reviewer_and_approver(tmp_path: Path):
    with pytest.raises(governance.UploadGovernanceError, match="复核人"):
        await governance.cleanup_expired_assets(
            tenant_id=7,
            older_than_days=governance.settings.resolved_upload_retention_days,
            dry_run=False,
            actor="operator",
            reason="expired asset cleanup",
            reviewed_by="same-person",
            approved_by="same-person",
            base_dir=str(tmp_path),
            asset_ids=[1],
        )


def test_cleanup_quarantine_can_be_atomically_restored(tmp_path: Path):
    candidate = tmp_path / "asset.png"
    trash = tmp_path / ".asset.png.trash-1-token"
    candidate.write_bytes(b"asset")

    assert governance._quarantine_for_deletion(candidate, trash)
    assert not candidate.exists() and trash.read_bytes() == b"asset"
    assert governance._restore_quarantined_file(trash, candidate)
    assert candidate.read_bytes() == b"asset" and not trash.exists()


@pytest.mark.asyncio
async def test_public_asset_reservation_is_explicit_and_auditable(monkeypatch, tmp_path: Path):
    reservation = {}

    async def _reserve(**kwargs):
        reservation.update(kwargs)
        return 94

    async def _noop(*_args):
        return None

    monkeypatch.setattr(governance, "_reserve_asset", _reserve)
    monkeypatch.setattr(governance, "_activate_asset", _noop)
    monkeypatch.setattr(governance, "_purge_failed_assets", _noop)

    await governance.store_governed_image(
        _image(),
        tenant_id=7,
        user_id=None,
        prefix="carousel",
        source_type="carousel",
        base_dir=str(tmp_path),
        visibility="public",
        purpose="carousel",
        owner_type="service",
    )

    assert reservation["visibility"] == "public"
    assert reservation["purpose"] == "carousel"
    assert reservation["owner_type"] == "service"
    assert reservation["owner_id"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("purpose", "owner_type"),
    [("avatar", "service"), ("carousel", "user")],
)
async def test_public_asset_rejects_unapproved_purpose_or_owner_before_reservation(
    monkeypatch, tmp_path: Path, purpose: str, owner_type: str
):
    async def _unexpected(**_kwargs):
        raise AssertionError("invalid public publication must not reserve storage")

    monkeypatch.setattr(governance, "_reserve_asset", _unexpected)

    with pytest.raises(governance.UploadGovernanceError) as error:
        await governance.store_governed_image(
            _image(),
            tenant_id=7,
            user_id=None,
            prefix="content",
            source_type=purpose,
            base_dir=str(tmp_path),
            visibility="public",
            purpose=purpose,
            owner_type=owner_type,
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_invalid_visibility_is_rejected_before_reservation(monkeypatch, tmp_path: Path):
    async def _unexpected(**_kwargs):
        raise AssertionError("invalid visibility must not reserve storage")

    monkeypatch.setattr(governance, "_reserve_asset", _unexpected)
    with pytest.raises(governance.UploadGovernanceError) as error:
        await governance.store_governed_image(
            _image(),
            tenant_id=7,
            user_id=3,
            prefix="test",
            source_type="unit-test",
            base_dir=str(tmp_path),
            visibility="tenant-7",
        )

    assert error.value.status_code == 400


def test_cleanup_restore_failure_never_reactivates_a_missing_asset():
    source = Path(governance.__file__).read_text(encoding="utf-8")

    assert "restore_succeeded = False" in source
    assert "deletion_reason='quarantine restore failure'" in source
    assert "if restore_succeeded:" in source
