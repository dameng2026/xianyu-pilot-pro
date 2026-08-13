"""Regression tests for the production delivery incident fixes.

1. WS sync cursor must advance from message times when the server omits maxPts
   (previously the cursor stayed stale and the same 250 messages replayed forever,
   so payment messages never reached auto-delivery / statement flows).
2. Multi-spec (property + SKU) normalization must accept both detail-API and
   publish-API shapes so local tables can be backfilled.
"""

import pytest

from app.services.multi_spec_storage import (
    derive_properties_from_skus,
    normalize_detail_properties,
    normalize_detail_sku_list,
)
from app.services.ws_client import XianyuWebSocketClient


def _bare_client() -> XianyuWebSocketClient:
    client = object.__new__(XianyuWebSocketClient)
    client._sync_pts = 1000
    client.account_id = 69
    return client


def test_sync_cursor_advances_from_message_time_when_max_pts_missing():
    client = _bare_client()
    client._advance_sync_pts_from_messages([
        {"messageTime": 5},
        {"messageTime": 10},
        {"messageTime": 0},
        {},
    ])
    # messageTime is ms; sync pts watermark is microseconds.
    assert client._sync_pts == 10 * 1000


def test_sync_cursor_never_moves_backwards():
    client = _bare_client()
    client._sync_pts = 20 * 1000
    client._advance_sync_pts_from_messages([{"messageTime": 10}])
    assert client._sync_pts == 20 * 1000


def test_sync_cursor_ignores_missing_timestamps():
    client = _bare_client()
    client._advance_sync_pts_from_messages([{}, {"messageTime": 0}])
    assert client._sync_pts == 1000


def test_normalize_detail_sku_list_handles_both_shapes():
    skus = normalize_detail_sku_list([
        {
            "skuId": "s1",
            "priceInCent": "3000",
            "quantity": "5",
            "properties": [{"name": "size", "value": "L"}],
        },
        {
            "skuId": "s2",
            "price": "50",
            "quantity": 2,
            "propertyList": [{"propertyText": "color", "valueText": "red"}],
        },
    ])
    assert skus[0]["propertyList"] == [{"propertyText": "size", "valueText": "L"}]
    assert skus[0]["priceInCent"] == 3000
    assert skus[1]["priceInCent"] == 5000
    assert skus[1]["quantity"] == 2
    assert skus[1]["propertyList"] == [{"propertyText": "color", "valueText": "red"}]


def test_normalize_detail_properties_accepts_string_and_object_values():
    groups = normalize_detail_properties([
        {
            "propertyName": "size",
            "values": [
                "L",
                {"propertyValue": "M", "propertyValueImg": "img-m"},
            ],
        }
    ])
    assert len(groups) == 1
    assert groups[0]["propertyValues"] == [
        {"propertyValue": "L", "propertyValueImg": ""},
        {"propertyValue": "M", "propertyValueImg": "img-m"},
    ]


def test_derive_properties_from_skus_when_item_properties_missing():
    skus = normalize_detail_sku_list([
        {
            "skuId": "s1",
            "priceInCent": 150,
            "quantity": 100,
            "propertyList": [{"propertyText": "版本", "valueText": "标准版"}],
        },
        {
            "skuId": "s2",
            "priceInCent": 250,
            "quantity": 50,
            "propertyList": [{"propertyText": "版本", "valueText": "高级版"}],
        },
    ])
    groups = derive_properties_from_skus(skus)
    assert groups == [
        {
            "propertyName": "版本",
            "supportImage": False,
            "propertyValues": [
                {"propertyValue": "标准版", "propertyValueImg": ""},
                {"propertyValue": "高级版", "propertyValueImg": ""},
            ],
        }
    ]


class _FakeRedis:
    def __init__(self):
        self.data = {}

    def set(self, key, value, ex=None):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, fake):
        self.fake = fake
        self.ops = []

    def set(self, key, value, ex=None):
        self.ops.append(("set", key, value, ex))
        return self

    def incr(self, key):
        self.ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        for op in self.ops:
            if op[0] == "set":
                self.fake.set(op[1], op[2], op[3])
            elif op[0] == "incr":
                self.fake.data[op[1]] = str(int(self.fake.get(op[1]) or 0) + 1)
            elif op[0] == "expire":
                pass


def test_ip_risk_breaker_survives_restart_via_redis(monkeypatch):
    import time

    from app.services import ws_token

    fake = _FakeRedis()
    monkeypatch.setattr(
        "app.services.x5sec_cache_client._get_redis_client",
        lambda: fake,
    )
    ws_token._IP_RGV587_TRIPPED_AT = 0.0

    ws_token.mark_ip_risk_tripped()
    assert ws_token.ip_risk_active()

    # Simulate a process restart: in-memory state is gone, Redis still holds it.
    ws_token._IP_RGV587_TRIPPED_AT = 0.0
    assert ws_token.ip_risk_active()

    # Once the window expires, the breaker is inactive again.
    fake.data[ws_token._IP_RGV587_REDIS_KEY] = str(int(time.time()) - 1000)
    ws_token._IP_RGV587_TRIPPED_AT = 0.0
    assert not ws_token.ip_risk_active()


def test_ip_risk_breaker_adapts_window_to_repeated_trips(monkeypatch):
    import time

    from app.services import ws_token

    fake = _FakeRedis()
    monkeypatch.setattr(
        "app.services.x5sec_cache_client._get_redis_client",
        lambda: fake,
    )
    ws_token._IP_RGV587_TRIPPED_AT = 0.0

    # Simulate a persistent ban: three trips in quick succession.
    for _ in range(3):
        ws_token.mark_ip_risk_tripped()

    # A 10-minute-old trip must still be inside the adaptive 60-minute window.
    fake.data[ws_token._IP_RGV587_REDIS_KEY] = str(int(time.time()) - 600)
    fake.data[ws_token._IP_RGV587_WINDOW_KEY] = str(3600)
    ws_token._IP_RGV587_TRIPPED_AT = 0.0
    assert ws_token.ip_risk_active()
    assert ws_token.ip_risk_remaining_seconds() > 0

    # A 2-hour-old trip is outside even the 60-minute window.
    fake.data[ws_token._IP_RGV587_REDIS_KEY] = str(int(time.time()) - 7200)
    ws_token._IP_RGV587_TRIPPED_AT = 0.0
    assert not ws_token.ip_risk_active()
    assert ws_token.ip_risk_remaining_seconds() == 0.0
