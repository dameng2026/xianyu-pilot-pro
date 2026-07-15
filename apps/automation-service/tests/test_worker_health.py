from pathlib import Path

import pytest

from app import worker


def test_worker_heartbeat_is_written_atomically(tmp_path):
    heartbeat = tmp_path / "automation-worker-heartbeat"

    worker.record_heartbeat(heartbeat)

    assert heartbeat.is_file()
    assert heartbeat.read_text(encoding="ascii").strip().isdigit()
    assert not Path(str(heartbeat) + ".tmp").exists()


def test_worker_healthcheck_requires_a_recent_heartbeat(tmp_path):
    from app import worker_healthcheck

    heartbeat = tmp_path / "automation-worker-heartbeat"
    heartbeat.write_text("20\n", encoding="ascii")

    assert worker_healthcheck.heartbeat_is_fresh(heartbeat, max_age_seconds=90, now=100)
    assert not worker_healthcheck.heartbeat_is_fresh(heartbeat, max_age_seconds=90, now=1000)
    assert not worker_healthcheck.heartbeat_is_fresh(tmp_path / "missing", max_age_seconds=90, now=100)


@pytest.mark.asyncio
async def test_worker_processed_count_includes_only_tasks_it_claimed(monkeypatch):
    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    async def due_tasks(_db, limit):
        assert limit == 20
        return [
            {"id": 1, "tenant_id": 7},
            {"id": 2, "tenant_id": 7},
        ]

    async def execute(_db, task_id, tenant_id):
        assert tenant_id == 7
        if task_id == 1:
            return {"ok": False, "claimed": False, "error": "TASK_ALREADY_RUNNING"}
        return {"ok": True, "claimed": True, "taskId": task_id}

    monkeypatch.setattr(worker, "async_session", Session)
    monkeypatch.setattr(worker, "list_due_tasks", due_tasks)
    monkeypatch.setattr(worker, "execute_scheduled_task", execute)

    result = await worker.run_once()

    assert result["candidates"] == 2
    assert result["processed"] == 1
    assert result["skipped"] == 1
