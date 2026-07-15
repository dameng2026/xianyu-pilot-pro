import pytest

from app.services.automation_runtime import _resolve_account_chat_role, process_incoming_message


class _FakeResult:
    def __init__(self, *, row=None):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _EmptyRoleLookupDB:
    def __init__(self):
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return _FakeResult(row=None)


class _BuyerRoleLiveConversationSkipDB:
    def __init__(self):
        self.calls = []

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        if len(self.calls) == 1:
            return _FakeResult(row={"status": 1})
        return _FakeResult(row=None)


class _LiveConversationRoleClient:
    def __init__(self, body):
        self.is_connected = True
        self._body = body

    async def list_conversations(self, start_timestamp=None, limit=20):
        return self._body


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_resolve_account_chat_role_marks_buyer_from_live_conversation_when_payload_lacks_seller_hints(monkeypatch):
    import app.services.ws_client as ws_client

    client = _LiveConversationRoleClient({
        "userConvs": [
            {
                "singleChatUserConversation": {
                    "cid": "63388710901@goofish",
                    "singleChatConversation": {
                        "cid": "63388710901@goofish",
                        "extension": {
                            "itemId": "945499366206",
                            "ownerUserId": "2218826198310",
                            "itemSellerId": "2218826198310",
                        },
                    },
                },
            }
        ]
    })
    monkeypatch.setattr(ws_client.ws_manager, "get_client", lambda _account_id: client)

    role = await _resolve_account_chat_role(
        _EmptyRoleLookupDB(),
        tenant_id=1,
        account_id=1,
        payload={
            "sellerExternalUid": "2211422464341",
            "goodsId": "945499366206",
            "sId": "63388710901",
            "buyerId": "2218826198310@goofish",
        },
    )

    assert role == "buyer"


@pytest.mark.anyio
async def test_process_incoming_message_skips_when_live_conversation_marks_current_account_as_buyer(monkeypatch):
    import app.services.ws_client as ws_client

    client = _LiveConversationRoleClient({
        "userConvs": [
            {
                "singleChatUserConversation": {
                    "cid": "63388710901@goofish",
                    "singleChatConversation": {
                        "cid": "63388710901@goofish",
                        "extension": {
                            "itemId": "945499366206",
                            "ownerUserId": "2218826198310",
                            "itemSellerId": "2218826198310",
                        },
                    },
                },
            }
        ]
    })
    monkeypatch.setattr(ws_client.ws_manager, "get_client", lambda _account_id: client)
    db = _BuyerRoleLiveConversationSkipDB()

    result = await process_incoming_message(db, {
        "tenantId": 1,
        "accountId": 1,
        "sellerExternalUid": "2211422464341",
        "buyerId": "2218826198310@goofish",
        "content": "merchant auto reply",
        "sId": "63388710901",
        "goodsId": "945499366206",
    })

    assert result["ok"] is True
    assert result["matched"] is False
    assert result["autoSent"] is False
    assert "buyer" in result["message"].lower() or "买家" in result["message"]
    assert len(db.calls) == 2
