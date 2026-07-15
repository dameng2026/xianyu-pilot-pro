import asyncio
import json

import pytest

from app.services.ws_sse import SSEBroadcaster


def _decode(message: str) -> dict:
    assert message.startswith("data: ")
    return json.loads(message.removeprefix("data: ").strip())


@pytest.mark.asyncio
async def test_broadcast_only_reaches_subscribers_in_the_same_tenant():
    broadcaster = SSEBroadcaster()
    tenant_a = await broadcaster.subscribe(11, "a-1")
    tenant_b = await broadcaster.subscribe(22, "b-1")

    await broadcaster.broadcast(11, "message", {"accountId": 7, "content": "private"})

    assert _decode(tenant_a.get_nowait()) == {
        "type": "message",
        "accountId": 7,
        "content": "private",
    }
    with pytest.raises(asyncio.QueueEmpty):
        tenant_b.get_nowait()


@pytest.mark.asyncio
async def test_unsubscribe_is_tenant_scoped():
    broadcaster = SSEBroadcaster()
    tenant_a = await broadcaster.subscribe(11, "same-id")
    tenant_b = await broadcaster.subscribe(22, "same-id")

    await broadcaster.unsubscribe(11, "same-id")
    await broadcaster.broadcast(11, "message", {"value": "a"})
    await broadcaster.broadcast(22, "message", {"value": "b"})

    with pytest.raises(asyncio.QueueEmpty):
        tenant_a.get_nowait()
    assert _decode(tenant_b.get_nowait())["value"] == "b"
    assert broadcaster.subscriber_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("tenant_id", [None, 0, -1, "invalid"])
async def test_broadcaster_rejects_invalid_tenant_ids(tenant_id):
    broadcaster = SSEBroadcaster()

    with pytest.raises(ValueError):
        await broadcaster.subscribe(tenant_id, "subscriber")
    with pytest.raises(ValueError):
        await broadcaster.broadcast(tenant_id, "message", {})
