import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services import automation_runtime


class _Rows:
    def __init__(self, row=None):
        self._row = row

    @classmethod
    def one(cls, row):
        return cls(row=row)

    def mappings(self):
        return self

    def first(self):
        return self._row


class _UpdateResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakeScheduledTaskDb:
    def __init__(
        self,
        task_type,
        config_json,
        *,
        completion_rowcount=1,
        consecutive_failure_count=0,
    ):
        self.task_type = task_type
        self.config_json = config_json
        self.completion_rowcount = completion_rowcount
        self.consecutive_failure_count = consecutive_failure_count
        self.execute_calls = []
        self.committed = False
        self.rolled_back = False

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.execute_calls.append((sql, params or {}))

        if "UPDATE scheduled_task" in sql and "SET lease_token = :lease_token" in sql:
            return _UpdateResult(1)

        if "SELECT * FROM scheduled_task" in sql:
            return _Rows.one({
                "id": 77,
                "tenant_id": 1,
                "account_id": 8,
                "task_type": self.task_type,
                "task_name": f"task-{self.task_type}",
                "config_json": self.config_json,
                "consecutive_failure_count": self.consecutive_failure_count,
            })

        if "UPDATE scheduled_task" in sql:
            return _UpdateResult(self.completion_rowcount)
        return _Rows.one(None)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class _NoopDb:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, _statement, _params=None):
        self.execute_calls.append((str(_statement), _params or {}))
        return _Rows.one(None)

    async def commit(self):
        return None


class _ExecutionRows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _MissingTenantExecutionDb:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, statement, params=None):
        self.execute_calls.append((str(statement), params or {}))
        if len(self.execute_calls) == 1:
            return _ExecutionRows([{
                "id": 77,
                "tenant_id": None,
                "workflow_id": 5,
                "status": "failed",
                "current_node_key": "node-1",
                "input_json": "{}",
                "output_json": "{}",
            }])
        return _ExecutionRows([])


@pytest.mark.asyncio
async def test_due_task_listing_excludes_unexpired_claims_and_keeps_tenant_scope():
    class DueDb:
        def __init__(self):
            self.execute_calls = []

        async def execute(self, statement, params=None):
            self.execute_calls.append((str(statement), params or {}))
            return _ExecutionRows([])

    db = DueDb()

    rows = await automation_runtime.list_due_tasks(db, tenant_id=7, limit=20)

    assert rows == []
    sql, params = db.execute_calls[0]
    assert "tenant_id = :tenant_id" in sql
    assert "lease_token IS NULL" in sql
    assert "lease_expires_at <= NOW(6)" in sql
    assert params == {"limit": 20, "tenant_id": 7}


class _ClaimConflictDb:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.execute_calls.append((sql, params or {}))
        assert "UPDATE scheduled_task" in sql
        assert "lease_token" in sql
        assert "tenant_id = :tenant_id" in sql
        return _UpdateResult(0)

    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_scheduled_task_conflict_is_rejected_before_loading_or_running_task():
    db = _ClaimConflictDb()

    result = await automation_runtime.execute_scheduled_task(
        db,
        77,
        1,
        manual=True,
    )

    assert result == {
        "ok": False,
        "claimed": False,
        "error": "TASK_ALREADY_RUNNING",
        "message": "定时任务正在其他执行器中运行或已不可用",
        "taskId": 77,
    }
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_lost_lease_cancels_long_running_task_and_never_commits_terminal_state(monkeypatch):
    db = _FakeScheduledTaskDb(task_type="redelivery", config_json='{"recordId":900}')
    body_started = asyncio.Event()
    body_cancelled = asyncio.Event()

    async def slow_runner(*_args, **_kwargs):
        body_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            body_cancelled.set()
            raise

    async def lease_lost(*_args, **_kwargs):
        await body_started.wait()
        return False

    monkeypatch.setattr(automation_runtime, "_run_redelivery_task", slow_runner)
    monkeypatch.setattr(automation_runtime, "_renew_scheduled_task_lease", lease_lost)

    result = await automation_runtime.execute_scheduled_task(db, 77, 1)

    assert result["ok"] is False
    assert result["error"] == "TASK_LEASE_LOST"
    assert result["claimed"] is True
    assert body_cancelled.is_set()
    assert not any(
        "lease_token = NULL" in sql
        for sql, _params in db.execute_calls
    )


@pytest.mark.asyncio
async def test_only_current_lease_token_can_commit_task_completion(monkeypatch):
    db = _FakeScheduledTaskDb(
        task_type="redelivery",
        config_json='{"recordId":900}',
        completion_rowcount=0,
    )

    async def completed_body(*_args, **_kwargs):
        return {"ok": True, "message": "done", "processed": 1}

    notify = AsyncMock(return_value=None)
    monkeypatch.setattr(automation_runtime, "_run_redelivery_task", completed_body)
    monkeypatch.setattr(automation_runtime, "insert_notification", notify)

    result = await automation_runtime.execute_scheduled_task(db, 77, 1)

    assert result["ok"] is False
    assert result["error"] == "TASK_LEASE_LOST"
    assert result["claimed"] is True
    assert db.rolled_back is True
    claim_params = next(
        params for sql, params in db.execute_calls
        if "SET lease_token = :lease_token" in sql
    )
    completion_sql, completion_params = next(
        (sql, params) for sql, params in db.execute_calls
        if "lease_token = NULL" in sql
    )
    assert "tenant_id = :tenant_id" in completion_sql
    assert "lease_expires_at > NOW(6)" in completion_sql
    assert completion_params["lease_token"] == claim_params["lease_token"]
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_task_failures_disable_schedule_at_bounded_threshold(monkeypatch):
    db = _FakeScheduledTaskDb(
        task_type="redelivery",
        config_json='{"recordId":900}',
        consecutive_failure_count=4,
    )

    async def failed_body(*_args, **_kwargs):
        return {"ok": False, "errorCode": "REDELIVERY_SEND_FAILED", "message": "unsafe detail"}

    monkeypatch.setattr(automation_runtime, "_run_redelivery_task", failed_body)
    monkeypatch.setattr(automation_runtime, "insert_notification", AsyncMock(return_value=None))

    result = await automation_runtime.execute_scheduled_task(db, 77, 1)

    assert result["ok"] is False
    assert result["disabledAfterFailures"] is True
    _sql, params = next(
        (sql, params) for sql, params in db.execute_calls
        if "lease_token = NULL" in sql
    )
    assert params["disable_after_failure"] == 1
    assert params["last_status"] == "disabled_after_failures"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("task_type", "helper_name", "config_json"),
    [
        ("redelivery", "_run_redelivery_task", '{"recordId": 900}'),
        ("sync_orders", "_run_sync_orders_task", '{"accountId": 8}'),
        ("sync_delivery_status", "_run_sync_delivery_status_task", '{"accountId": 8}'),
        ("polish_goods", "_run_polish_goods_task", '{"intervalMinutes": 1440}'),
    ],
)
async def test_execute_scheduled_task_dispatches_order_delivery_task_types(monkeypatch, task_type, helper_name, config_json):
    db = _FakeScheduledTaskDb(task_type=task_type, config_json=config_json)
    called = {}

    async def fake_runner(db_arg, tenant_id, task):
        called["tenant_id"] = tenant_id
        called["task_type"] = task["task_type"]
        return {"ok": True, "message": f"{task_type} ok", "processed": 1}

    monkeypatch.setattr(automation_runtime, helper_name, fake_runner)
    monkeypatch.setattr(automation_runtime, "insert_notification", AsyncMock(return_value=None))

    result = await automation_runtime.execute_scheduled_task(db, 77, 1)

    assert result["processed"] == 1
    assert result["taskType"] == task_type
    assert called == {"tenant_id": 1, "task_type": task_type}
    assert db.committed is True
    assert result["claimed"] is True
    task_updates = [
        (sql, params)
        for sql, params in db.execute_calls
        if "UPDATE scheduled_task" in sql
    ]
    assert len(task_updates) == 2
    claim_sql, claim_params = task_updates[0]
    completion_sql, completion_params = task_updates[1]
    assert "tenant_id = :tenant_id" in claim_sql
    assert "lease_token = :lease_token" in completion_sql
    assert "lease_token = NULL" in completion_sql
    assert completion_params["tenant_id"] == 1
    assert completion_params["lease_token"] == claim_params["lease_token"]


@pytest.mark.asyncio
async def test_unknown_scheduled_task_is_completed_and_disabled_without_retry_loop(monkeypatch):
    db = _FakeScheduledTaskDb(task_type="unknown-task", config_json="{}")
    notify = AsyncMock(return_value=None)
    monkeypatch.setattr(automation_runtime, "insert_notification", notify)

    result = await automation_runtime.execute_scheduled_task(db, 77, 1)

    assert result["ok"] is False
    assert result["error"] == "UNSUPPORTED_TASK_TYPE"
    assert result["claimed"] is True
    assert result["disabledAfterFailures"] is True
    completion_sql, completion_params = [
        (sql, params)
        for sql, params in db.execute_calls
        if "UPDATE scheduled_task" in sql and "lease_token = NULL" in sql
    ][0]
    assert "next_run_time" in completion_sql
    assert completion_params["disable_after_failure"] == 1
    assert completion_params["lease_token"]
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_event_driven_auto_reply_task_releases_lease_and_disables_schedule(monkeypatch):
    db = _FakeScheduledTaskDb(task_type="auto_reply", config_json="{}")
    notify = AsyncMock(return_value=None)
    monkeypatch.setattr(automation_runtime, "insert_notification", notify)

    result = await automation_runtime.execute_scheduled_task(db, 77, 1)

    assert result["ok"] is False
    assert result["error"] == "EVENT_DRIVEN_TASK"
    assert result["claimed"] is True
    assert result["disabledAfterFailures"] is True
    completion_sql, completion_params = [
        (sql, params)
        for sql, params in db.execute_calls
        if "UPDATE scheduled_task" in sql and "lease_token = NULL" in sql
    ][0]
    assert "next_run_time" in completion_sql
    assert completion_params["disable_after_failure"] == 1
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_continue_workflow_rejects_execution_without_tenant_context():
    db = _MissingTenantExecutionDb()

    result = await automation_runtime.continue_workflow_execution(db, 77)

    assert result == {
        "status": "failed",
        "errorCode": "WORKFLOW_TENANT_INVALID",
        "errorMessage": "执行记录缺少有效的租户上下文",
    }
    assert len(db.execute_calls) == 1


@pytest.mark.asyncio
async def test_sync_sold_orders_for_account_fetches_remote_orders_and_upserts(monkeypatch):
    captured_orders = []
    synced = {}

    async def fake_load_account(*_args, **_kwargs):
        return {"accountId": 8, "externalUid": "2211422464341"}

    async def fake_fetch_orders(*_args, **_kwargs):
        return [
            {
                "externalOrderId": "ORDER-001",
                "buyerName": "买家A",
                "buyerId": "buyer-1",
                "orderStatus": 2,
                "totalAmount": "99.00",
                "items": [
                    {
                        "goodsId": "12345",
                        "goodsTitle": "演示商品",
                        "goodsCount": 1,
                        "goodsPrice": "99.00",
                    }
                ],
            }
        ]

    async def fake_upsert_order(_db, _tenant_id, _account_id, order):
        captured_orders.append(order)
        return "inserted"

    async def fake_mark_synced(_db, tenant_id, account_id):
        synced["tenant_id"] = tenant_id
        synced["account_id"] = account_id
        return {"ok": True}

    monkeypatch.setattr(automation_runtime, "_load_order_sync_account", fake_load_account, raising=False)
    monkeypatch.setattr(automation_runtime, "_fetch_remote_sold_orders", fake_fetch_orders, raising=False)
    monkeypatch.setattr(automation_runtime, "_upsert_remote_sold_order", fake_upsert_order, raising=False)
    monkeypatch.setattr(automation_runtime, "mark_account_synced", fake_mark_synced)

    result = await automation_runtime.sync_sold_orders_for_account(_NoopDb(), 1, 8)

    assert result["ok"] is True
    assert result["processed"] == 1
    assert result["inserted"] == 1
    assert result["updated"] == 0
    assert synced == {"tenant_id": 1, "account_id": 8}
    assert captured_orders == [
        {
            "externalOrderId": "ORDER-001",
            "buyerName": "买家A",
            "buyerId": "buyer-1",
            "orderStatus": 2,
            "totalAmount": "99.00",
            "items": [
                {
                    "goodsId": "12345",
                    "goodsTitle": "演示商品",
                    "goodsCount": 1,
                    "goodsPrice": "99.00",
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_sync_delivery_status_for_account_updates_existing_columns_only():
    db = _NoopDb()

    result = await automation_runtime.sync_delivery_status_for_account(db, 1, 8, "ORDER-001")

    assert result["ok"] is True
    assert result["accountId"] == 8
    assert result["externalOrderId"] == "ORDER-001"
    assert db.execute_calls
    sql, params = db.execute_calls[0]
    assert "platform_delivery_status" not in sql
    assert "platform_sync_time" not in sql
    assert "SET dr.delivery_status = CASE" in sql
    assert params == {
        "tenant_id": 1,
        "account_id": 8,
        "external_order_id": "ORDER-001",
    }
