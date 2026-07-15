from unittest.mock import AsyncMock, patch

import pytest

import app.services.automation_runtime as automation_runtime


class _DummyDb:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_publish_node_uses_summary_mode_when_image_generate_already_published():
    db = _DummyDb()
    state = {
        "selected_account_id": 9,
        "publish_results": [
            {"idx": 0, "status": "published", "title": "商品A"},
            {"idx": 1, "status": "failed", "title": "商品B"},
            {"idx": 2, "status": "skipped_duplicate", "title": "商品C"},
        ],
    }
    context = {"__execution_id__": "exec-1", "__workflow_id__": "wf-1"}

    with patch.object(automation_runtime, "insert_timeline", new=AsyncMock(return_value=None)) as mocked_timeline:
        result = await automation_runtime._execute_workflow_node(
            db,
            1,
            "PUBLISH",
            {"platform": "xianyu"},
            context,
            state,
        )

    assert result["ok"] is True
    assert result["partial"] is True
    assert result["count"] == 3
    assert result["successCount"] == 1
    assert result["failedCount"] == 1
    assert result["skippedDuplicateCount"] == 1
    assert result["artifact"]["summaryMode"] is True
    assert "已发布 1 个商品" in result["message"]
    assert mocked_timeline.await_count == 1
    assert db.commits == 1
