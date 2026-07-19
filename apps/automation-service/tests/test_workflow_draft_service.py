"""草稿服务单元测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.workflow_draft_service import (
    list_drafts, retry_publish_draft, get_draft_stats
)


def _make_row(data):
    """构造一个模拟 SQLAlchemy Row 的对象，支持 ._mapping"""
    row = MagicMock()
    row._mapping = data
    return row


@pytest.mark.asyncio
async def test_list_drafts_returns_paged_records():
    """list_drafts 应返回分页结构 {records, total, page, pageSize}"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _make_row({
            "id": 1, "title": "测试商品", "publish_status": "draft",
            "price": "9.9", "cover_pic": "http://x/a.png",
            "workflow_name": "WF1", "created_time": None, "updated_time": None,
            "image_urls": None, "publish_time": None,
        })
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.scalar = AsyncMock(return_value=1)
    result = await list_drafts(mock_session, tenant_id=1, page=1, page_size=20)
    assert result["total"] == 1
    assert len(result["records"]) == 1
    assert result["page"] == 1
    assert result["pageSize"] == 20


@pytest.mark.asyncio
async def test_retry_publish_draft_rejects_already_publishing():
    """publish_status='publishing' 的草稿应拒绝重试发布"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = _make_row({
        "id": 1, "tenant_id": 1, "publish_status": "publishing", "title": "测试",
    })
    mock_session.execute = AsyncMock(return_value=mock_result)
    with pytest.raises(ValueError, match="正在发布中"):
        await retry_publish_draft(mock_session, draft_id=1, tenant_id=1)


@pytest.mark.asyncio
async def test_retry_publish_draft_rejects_already_published():
    """publish_status='published' 的草稿应拒绝重试发布"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = _make_row({
        "id": 1, "tenant_id": 1, "publish_status": "published", "title": "测试",
    })
    mock_session.execute = AsyncMock(return_value=mock_result)
    with pytest.raises(ValueError, match="已发布成功"):
        await retry_publish_draft(mock_session, draft_id=1, tenant_id=1)


@pytest.mark.asyncio
async def test_get_draft_stats_returns_correct_counts():
    """get_draft_stats 应返回 {total, draft, published, failed}"""
    mock_session = AsyncMock()
    # 4 次 scalar 调用：total / draft / published / failed
    mock_session.scalar = AsyncMock(side_effect=[100, 30, 50, 20])
    stats = await get_draft_stats(mock_session, tenant_id=1)
    assert stats["total"] == 100
    assert stats["draft"] == 30
    assert stats["published"] == 50
    assert stats["failed"] == 20
