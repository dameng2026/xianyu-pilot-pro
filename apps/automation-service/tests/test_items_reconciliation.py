from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.routes import items as items_route
from app.models.entities import XianyuGoodsSyncTask
from app.schemas.common import ItemOperateReqDTO, UpdateItemPriceReqDTO


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FailAfterReadsDb:
    def __init__(self, read_values):
        self._read_values = list(read_values)
        self.added = []
        self.rollback_count = 0
        self.commit_count = 0

    async def execute(self, _statement):
        if self._read_values:
            return _ScalarResult(self._read_values.pop(0))
        raise RuntimeError("database details that must never reach the client")

    async def rollback(self):
        self.rollback_count += 1

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commit_count += 1


def _assert_reconciliation_response(result, db, *, action, goods_id):
    assert result.code == 409
    assert result.data["remoteApplied"] is True
    assert result.data["reconciliationRequired"] is True
    assert result.data["reconciliationId"].startswith("reconcile-")
    assert "database details" not in result.msg

    assert db.rollback_count == 1
    assert db.commit_count == 1
    assert len(db.added) == 1
    task = db.added[0]
    assert isinstance(task, XianyuGoodsSyncTask)
    assert task.sync_id == result.data["reconciliationId"]
    assert task.tenant_id == 41
    assert task.account_id == 73
    assert task.status == "failed"
    assert task.progress == 0
    assert task.error_message == (
        f"RECONCILIATION_REQUIRED action={action} externalGoodsId={goods_id}"
    )


@pytest.mark.asyncio
async def test_remote_delete_reports_partial_success_and_records_reconciliation():
    goods = SimpleNamespace(id=12, status=0)
    db = _FailAfterReadsDb([None, goods])
    operator = MagicMock()

    with (
        patch.object(
            items_route,
            "_get_account_auth",
            return_value=SimpleNamespace(encrypted_cookie="encrypted-cookie"),
        ),
        patch.object(items_route, "_is_fish_shop_account", return_value=True),
        patch.object(items_route, "decrypt_cookie_if_needed", return_value="cookie"),
        patch.object(items_route, "XianyuItemOperator", return_value=operator),
    ):
        result = await items_route.remote_delete_item(
            ItemOperateReqDTO(
                tenant_id=41,
                xianyu_account_id=73,
                xy_goods_id="goods-delete-1",
            ),
            db=db,
            _=None,
        )

    operator.delete.assert_called_once_with("goods-delete-1")
    _assert_reconciliation_response(
        result,
        db,
        action="remote_delete",
        goods_id="goods-delete-1",
    )


@pytest.mark.asyncio
async def test_remote_price_update_reports_partial_success_and_records_reconciliation():
    goods = SimpleNamespace(id=12)
    account = SimpleNamespace(id=73, fish_shop=True)
    db = _FailAfterReadsDb([goods, account])
    operator = MagicMock()

    with (
        patch.object(
            items_route,
            "_get_account_auth",
            return_value=SimpleNamespace(encrypted_cookie="encrypted-cookie"),
        ),
        patch.object(items_route, "decrypt_cookie_if_needed", return_value="cookie"),
        patch.object(items_route, "XianyuItemOperator", return_value=operator),
    ):
        result = await items_route.update_item_price(
            UpdateItemPriceReqDTO(
                tenant_id=41,
                xianyu_account_id=73,
                xy_goods_id="goods-price-1",
                price="19.90",
            ),
            db=db,
            _=None,
        )

    operator.update_price.assert_called_once_with("goods-price-1", "19.9")
    _assert_reconciliation_response(
        result,
        db,
        action="remote_price_update",
        goods_id="goods-price-1",
    )
