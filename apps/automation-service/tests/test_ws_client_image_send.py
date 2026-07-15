import base64
import json
import time

import pytest

from app.services import ws_client


class _FakeWs:
    def __init__(self):
        self.payloads = []

    async def send(self, data: str):
        self.payloads.append(data)


@pytest.mark.asyncio
async def test_send_image_message_fails_closed_when_ack_times_out(monkeypatch):
    fake_ws = _FakeWs()
    client = ws_client.XianyuWebSocketClient(
        account_id=1,
        tenant_id=1,
        cookie_str="k=v",
        m_h5_tk="2211422464341_token",
        unb="2211422464341",
    )
    client._connected = True
    client._ws = fake_ws
    client._sid = "session-token"
    client._last_recv_time = time.time()

    monkeypatch.setattr(ws_client, "MESSAGE_TIMEOUT", 0.01)

    result = await client.send_image_message(
        "63247704189@goofish",
        "3672669710@goofish",
        "https://example.com/demo.png",
        width=320,
        height=240,
    )

    assert result == {"code": 500, "error": "发送图片超时"}
    assert client.last_error == "发送图片超时（单条消息失败，连接保持）"
    assert client._send_futures == {}
    assert len(fake_ws.payloads) == 1

    payload = json.loads(fake_ws.payloads[0])
    encoded = payload["body"][0]["content"]["custom"]["data"]
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert decoded["image"]["pics"][0]["width"] == 320
    assert decoded["image"]["pics"][0]["height"] == 240
