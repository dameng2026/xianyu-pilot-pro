"""消息过滤与默认回复功能的单元测试。"""

from unittest.mock import AsyncMock

import pytest

from app.services import automation_runtime
from app.services import ws_client as ws_client_module


class _FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None


class _FilterDB:
    def __init__(self, rows):
        self._rows = rows
        self.execute_calls = []

    async def execute(self, statement, params=None):
        self.execute_calls.append((str(statement), params or {}))
        return _FakeResult(rows=self._rows)


class _DefaultReplyDB:
    def __init__(self, config_row, record_row=None):
        self._config_row = config_row
        self._record_row = record_row
        self.commits = 0
        self.executed_sql = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.executed_sql.append(sql)
        if "FROM default_reply" in sql and "LIMIT 1" in sql:
            return _FakeResult(row=self._config_row)
        if "FROM default_reply_record" in sql:
            return _FakeResult(row=self._record_row)
        if "INSERT INTO auto_reply_log" in sql:
            return _FakeResult(row=None)
        if "INSERT IGNORE INTO default_reply_record" in sql:
            return _FakeResult(row=None)
        raise AssertionError(f"unexpected SQL: {sql}")

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass


class _ConnectedClient:
    is_connected = True

    def __init__(self):
        self.send_calls = []

    async def send_text_message(self, ws_sid, to_id, content, persist=False):
        self.send_calls.append((ws_sid, to_id, content, persist))
        return {"code": 200}


def test_split_reply_messages_splits_on_separator():
    parts = automation_runtime._split_reply_messages("第一条######第二条######第三条")
    assert parts == ["第一条", "第二条", "第三条"]


def test_split_reply_messages_ignores_empty_parts():
    parts = automation_runtime._split_reply_messages("A######   ######B")
    assert parts == ["A", "B"]


@pytest.mark.asyncio
async def test_send_reply_content_via_client_sends_all_parts():
    client = _ConnectedClient()

    result = await automation_runtime._send_reply_content_via_client(
        client, "sid-1", "buyer@goofish", "A######B",
    )

    assert result == {"code": 200}
    assert [call[2] for call in client.send_calls] == ["A", "B"]


@pytest.mark.asyncio
async def test_send_reply_content_via_client_stops_on_failure():
    class _FailClient:
        def __init__(self):
            self.calls = []

        async def send_text_message(self, ws_sid, to_id, content, persist=False):
            self.calls.append(content)
            if content == "A":
                return {"code": 400, "error": "rejected"}
            return {"code": 200}

    client = _FailClient()
    result = await automation_runtime._send_reply_content_via_client(
        client, "sid-1", "buyer@goofish", "A######B",
    )

    assert result["code"] == 400
    assert client.calls == ["A"]


@pytest.mark.asyncio
async def test_check_message_filter_returns_matched_types():
    rows = [
        {"keyword": "AD", "filter_type": "skip_reply"},
        {"keyword": "AD", "filter_type": "skip_notify"},
        {"keyword": "正常", "filter_type": "skip_reply"},
    ]
    db = _FilterDB(rows)

    hits = await automation_runtime._check_message_filter(
        db, tenant_id=1, account_id=1, content="this is an AD message",
    )

    assert hits == ["skip_reply", "skip_notify"]


@pytest.mark.asyncio
async def test_check_message_filter_returns_empty_when_no_match():
    db = _FilterDB([
        {"keyword": "AD", "filter_type": "skip_reply"},
    ])

    hits = await automation_runtime._check_message_filter(
        db, tenant_id=1, account_id=1, content="hello normal",
    )

    assert hits == []


@pytest.mark.asyncio
async def test_check_message_filter_fails_open():
    class _BrokenDB:
        async def execute(self, statement, params=None):
            raise RuntimeError("db down")

    hits = await automation_runtime._check_message_filter(
        _BrokenDB(), tenant_id=1, account_id=1, content="AD",
    )

    assert hits == []


@pytest.mark.asyncio
async def test_try_default_reply_sends_text_via_ws(monkeypatch):
    db = _DefaultReplyDB(config_row={
        "reply_type": "text",
        "reply_content": "亲，咨询较多回复慢了~",
        "reply_image": "",
        "api_url": "",
        "api_timeout": 30,
        "reply_once": 0,
    })
    client = _ConnectedClient()

    class _Manager:
        def get_client(self, account_id):
            return client

    monkeypatch.setattr(ws_client_module, "ws_manager", _Manager())

    result = await automation_runtime._try_default_reply(
        db=db,
        tenant_id=1,
        account_id=1,
        conversation_db_id=100,
        content="你好",
        buyer_id="12345@goofish",
        buyer_name="测试买家",
        ws_sid="sid-1",
        goods_id="",
        trigger_message_id=99,
        platform_message_id="PNM-1",
    )

    assert result is not None
    assert result["autoSent"] is True
    assert result["source"] == "default_reply"
    assert client.send_calls
    assert client.send_calls[0][1] == "12345@goofish"
    assert client.send_calls[0][2] == "亲，咨询较多回复慢了~"
    assert db.commits >= 1


@pytest.mark.asyncio
async def test_try_default_reply_respects_reply_once(monkeypatch):
    db = _DefaultReplyDB(
        config_row={
            "reply_type": "text",
            "reply_content": "仅回复一次",
            "reply_image": "",
            "api_url": "",
            "api_timeout": 30,
            "reply_once": 1,
        },
        record_row={"id": 1},
    )

    result = await automation_runtime._try_default_reply(
        db=db,
        tenant_id=1,
        account_id=1,
        conversation_db_id=100,
        content="你好",
        buyer_id="12345@goofish",
        buyer_name="测试买家",
        ws_sid="sid-1",
        goods_id="",
        trigger_message_id=99,
        platform_message_id="PNM-1",
    )

    assert result is None


@pytest.mark.asyncio
async def test_try_default_reply_returns_none_without_config():
    db = _DefaultReplyDB(config_row=None)

    result = await automation_runtime._try_default_reply(
        db=db,
        tenant_id=1,
        account_id=1,
        conversation_db_id=100,
        content="你好",
        buyer_id="12345@goofish",
        buyer_name="测试买家",
        ws_sid="sid-1",
        goods_id="",
        trigger_message_id=99,
        platform_message_id="PNM-1",
    )

    assert result is None
