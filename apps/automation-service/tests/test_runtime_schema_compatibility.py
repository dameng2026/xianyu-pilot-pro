import pytest

from app.main import ensure_runtime_schema_compatibility, validate_runtime_schema_compatibility


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConn:
    def __init__(self, missing=None):
        self.executed_sql = []
        self.missing = set(missing or [])

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.executed_sql.append((sql, params or {}))

        table_name = (params or {}).get("table_name")
        column_name = (params or {}).get("column_name")
        if "information_schema.tables" in sql:
            if table_name in self.missing:
                return _FakeScalarResult(0)
            return _FakeScalarResult(1)
        if "information_schema.columns" in sql:
            if f"{table_name}.{column_name}" in self.missing:
                return _FakeScalarResult(0)
            return _FakeScalarResult(1)
        return _FakeScalarResult(0)


class _FakeBegin:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, missing=None):
        self.url = "mysql+aiomysql://test"
        self.conn = _FakeConn(missing)

    def begin(self):
        return _FakeBegin(self.conn)

    def connect(self):
        return _FakeBegin(self.conn)


@pytest.mark.asyncio
async def test_ensure_runtime_schema_compatibility_adds_missing_goods_columns(monkeypatch):
    fake_engine = _FakeEngine({"xianyu_goods.image_urls", "xianyu_goods.raw_payload"})
    monkeypatch.setattr("app.main.engine", fake_engine)

    await ensure_runtime_schema_compatibility()

    alter_sql = [sql for sql, _ in fake_engine.conn.executed_sql if sql.startswith("ALTER TABLE xianyu_goods ADD COLUMN")]

    assert any("ADD COLUMN image_urls" in sql for sql in alter_sql)
    assert any("ADD COLUMN raw_payload" in sql for sql in alter_sql)


@pytest.mark.asyncio
async def test_validate_runtime_schema_compatibility_is_read_only(monkeypatch):
    fake_engine = _FakeEngine()
    monkeypatch.setattr("app.main.engine", fake_engine)

    await validate_runtime_schema_compatibility()

    sql = [statement for statement, _ in fake_engine.conn.executed_sql]
    assert sql
    assert all(statement.lstrip().startswith("SELECT") for statement in sql)


@pytest.mark.asyncio
async def test_validate_runtime_schema_compatibility_fails_closed_when_required_column_is_missing(monkeypatch):
    fake_engine = _FakeEngine({"xianyu_goods.image_urls"})
    monkeypatch.setattr("app.main.engine", fake_engine)

    with pytest.raises(RuntimeError, match="database schema is incomplete"):
        await validate_runtime_schema_compatibility()


@pytest.mark.asyncio
async def test_validate_runtime_schema_requires_explicit_media_visibility_columns(monkeypatch):
    fake_engine = _FakeEngine({"tenant_storage_asset.visibility"})
    monkeypatch.setattr("app.main.engine", fake_engine)

    with pytest.raises(RuntimeError, match="database schema is incomplete"):
        await validate_runtime_schema_compatibility()
