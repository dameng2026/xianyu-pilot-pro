from datetime import datetime

import pytest

from app.services import ws_client as ws_client_module
from app.services import ws_storage


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_merge_context_messages_prefers_base_chat_timeline(monkeypatch):
    base_messages = [
        {
            "id": "buyer-1",
            "pnmId": "in-1",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "鲁大师才20万分",
            "senderUserId": "25945493@goofish",
            "receiverUserId": "2211422464341@goofish",
            "messageTime": 1719562432000,
            "direction": "IN",
        },
        {
            "id": "reply-1",
            "pnmId": "out-1",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "您好，自动客服已收到",
            "senderUserId": "2211422464341@goofish",
            "receiverUserId": "25945493@goofish",
            "messageTime": 1719562513000,
            "direction": "OUT",
            "isAutoReply": 1,
        },
        {
            "id": "buyer-2",
            "pnmId": "in-2",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "5500XT",
            "senderUserId": "25945493@goofish",
            "receiverUserId": "2211422464341@goofish",
            "messageTime": 1719562469000,
            "direction": "IN",
        },
    ]

    async def fake_resolve(*_args, **_kwargs):
        return [123]

    async def fake_load(*_args, **_kwargs):
        return [
            {
                "id": "legacy-auto-1",
                "sid": "63154410580",
                "contentType": 1,
                "msgContent": "您好，自动客服已收到",
                "senderUserId": "2211422464341@goofish",
                "receiverUserId": "25945493@goofish",
                "messageTime": 1719562513000,
                "direction": "OUT",
                "isAutoReply": 1,
            }
        ]

    monkeypatch.setattr(ws_storage, "_resolve_conversation_ids_for_context", fake_resolve)
    monkeypatch.setattr(ws_storage, "_load_ai_reply_context_messages", fake_load)

    merged = await ws_storage._merge_context_messages_with_ai_replies(
        db=None,
        tenant_id=1,
        account_id=1,
        base_messages=base_messages,
        s_id="63154410580",
        peer_user_id="25945493",
    )

    assert [item["msgContent"] for item in merged] == [
        "鲁大师才20万分",
        "5500XT",
        "您好，自动客服已收到",
    ]
    assert len(merged) == 3


@pytest.mark.anyio
async def test_merge_context_messages_filters_other_buyers_for_same_sid(monkeypatch):
    base_messages = [
        {
            "id": "buyer-a-1",
            "pnmId": "in-a-1",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "鲁大师才20万分",
            "senderUserId": "25945493@goofish",
            "receiverUserId": "seller-1@goofish",
            "messageTime": 1719562432000,
            "direction": "IN",
        },
        {
            "id": "buyer-b-1",
            "pnmId": "in-b-1",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "嗯，自动客服没救了",
            "senderUserId": "2211422464341@goofish",
            "receiverUserId": "seller-1@goofish",
            "messageTime": 1719562531000,
            "direction": "IN",
        },
    ]

    async def fake_resolve(*_args, **_kwargs):
        return [83, 84]

    async def fake_load(*_args, **_kwargs):
        return [
            {
                "id": "legacy-auto-a",
                "sid": "63154410580",
                "contentType": 1,
                "msgContent": "您好，建议您直接与卖家沟通议价",
                "senderUserId": "",
                "receiverUserId": "25945493@goofish",
                "peerExternalUid": "unknown",
                "messageTime": 1719562495000,
                "direction": "OUT",
                "isAutoReply": 1,
            },
            {
                "id": "legacy-auto-b",
                "sid": "63154410580",
                "contentType": 1,
                "msgContent": "价格问题请直接与卖家协商",
                "senderUserId": "",
                "receiverUserId": "2211422464341@goofish",
                "peerExternalUid": "unknown",
                "messageTime": 1719562591000,
                "direction": "OUT",
                "isAutoReply": 1,
            },
        ]

    monkeypatch.setattr(ws_storage, "_resolve_conversation_ids_for_context", fake_resolve)
    monkeypatch.setattr(ws_storage, "_load_ai_reply_context_messages", fake_load)

    merged = await ws_storage._merge_context_messages_with_ai_replies(
        db=None,
        tenant_id=1,
        account_id=1,
        base_messages=base_messages,
        s_id="63154410580",
        peer_user_id="2211422464341",
    )

    assert [item["msgContent"] for item in merged] == [
        "嗯，自动客服没救了",
        "价格问题请直接与卖家协商",
    ]
    assert all("25945493" not in str(item) for item in merged)


class _FakeResult:
    def __init__(self, *, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _statement, params=None):
        params = params or {}
        sid_variants = {
            str(params.get("s_id") or "").strip(),
            str(params.get("s_id_goofish") or "").strip(),
        } - {""}
        peer_variants = {
            str(params.get("peer_user_id") or "").strip(),
            str(params.get("peer_user_id_goofish") or "").strip(),
        } - {""}

        statement_text = str(_statement)

        filtered = [
            row for row in self._rows
            if not sid_variants or str(row.get("sid") or "").strip() in sid_variants
        ]
        should_filter_by_peer = (
            "base.sender_user_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)" in statement_text
            or "base.receiver_user_id COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)" in statement_text
            or "base.peer_external_uid COLLATE utf8mb4_unicode_ci IN (:peer_user_id, :peer_user_id_goofish)" in statement_text
        )
        if peer_variants and should_filter_by_peer:
            filtered = [
                row for row in filtered
                if str(row.get("senderUserId") or "").strip() in peer_variants
                or str(row.get("receiverUserId") or "").strip() in peer_variants
                or str(row.get("peerExternalUid") or "").strip() in peer_variants
                or (
                    str(row.get("senderUserId") or "").strip() == ""
                    and str(row.get("receiverUserId") or "").strip() == ""
                    and str(row.get("peerExternalUid") or "").strip() == ""
                )
            ]
        if "COUNT(*)" in statement_text:
            return _FakeResult(scalar_value=len(filtered))

        offset = int(params.get("offset") or 0)
        limit = int(params.get("limit") or len(filtered))
        return _FakeResult(rows=filtered[offset:offset + limit])


class _PreviewDB:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _statement, params=None):
        return _FakeResult(rows=self._rows)


def test_merge_context_source_messages_deduplicates_same_outgoing_text_with_different_remote_ids():
    messages = ws_storage._merge_context_source_messages(
        [
            {
                "id": 101,
                "pnmId": "local-uuid",
                "sid": "63154410580",
                "senderUserId": "seller@goofish",
                "receiverUserId": "buyer@goofish",
                "msgContent": "11",
                "direction": "OUT",
                "messageTime": 1783379158000,
            }
        ],
        [
            {
                "id": "live-remote-id",
                "pnmId": "remote-message-id",
                "sid": "63154410580",
                "senderUserId": "seller@goofish",
                "receiverUserId": "buyer@goofish",
                "msgContent": "11",
                "direction": "OUT",
                "messageTime": 1783379159000,
            }
        ],
    )

    assert len(messages) == 1
    assert messages[0]["id"] == 101


def test_merge_context_source_messages_keeps_separate_outgoing_repeats():
    messages = ws_storage._merge_context_source_messages(
        [
            {
                "id": 101,
                "pnmId": "first",
                "sid": "63154410580",
                "senderUserId": "seller@goofish",
                "receiverUserId": "buyer@goofish",
                "msgContent": "11",
                "direction": "OUT",
                "messageTime": 1783379158000,
            },
            {
                "id": 102,
                "pnmId": "second",
                "sid": "63154410580",
                "senderUserId": "seller@goofish",
                "receiverUserId": "buyer@goofish",
                "msgContent": "11",
                "direction": "OUT",
                "messageTime": 1783379178000,
            },
        ],
        [],
    )

    assert len(messages) == 2


def test_normalize_message_time_value_treats_database_datetime_as_shanghai_time():
    expected = 1783379158000

    assert ws_storage._normalize_message_time_value("2026-07-07 07:05:58") == expected
    assert ws_storage._normalize_message_time_value(datetime(2026, 7, 7, 7, 5, 58)) == expected


@pytest.mark.anyio
async def test_apply_ai_reply_preview_matches_naive_db_datetime_rows():
    conversations = [{
        "conversationId": None,
        "sid": "63437777355",
        "peerUserId": "3672669710@goofish",
        "peerKey": "sid:63437777355@goofish",
        "peerUserName": "buyer-live",
        "lastMessage": "买家原消息",
        "lastContentType": 1,
        "lastMessageTime": 1783379157526,
        "firstMessageTime": 1783348894126,
        "goodsId": "1063090658900",
        "goodsTitle": "demo-goods",
        "goodsCoverPic": "",
        "reminderContent": "codex-auto-reply-check-20260707-0706",
        "unreadCount": "8",
        "messageCount": 10,
        "conversationStatus": 0,
        "buyerAvatar": "",
        "goodsPrice": "6.88",
        "goodsStatus": 1,
    }]
    db = _PreviewDB([{
        "id": 52,
        "conversation_id": 77,
        "to_user_id": "3672669710@goofish",
        "content": "这是自动回复",
        "message_type": "text",
        "direction": 1,
        "is_auto_reply": 1,
        "msg_time": datetime(2026, 7, 7, 7, 5, 58),
        "created_time": datetime(2026, 7, 7, 7, 5, 58),
    }])

    result = await ws_storage._apply_ai_reply_preview(
        db=db,
        tenant_id=1,
        account_id=1,
        conversations=conversations,
    )

    assert result[0]["hasAiReply"] is True
    assert result[0]["lastIsAutoReply"] is True
    assert result[0]["lastMessage"] == "这是自动回复"


@pytest.mark.anyio
async def test_get_context_messages_keeps_all_sid_messages_when_peer_is_selected(monkeypatch):
    rows = [
        {
            "id": 732,
            "pnm_id": "4185399355781.PNM",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "鲁大师才20万分",
            "senderUserId": "25945493@goofish",
            "senderUserName": "czgcn",
            "xyGoodsId": "1061663316195",
            "messageTime": 1719562432000,
            "direction": "IN",
            "reminderContent": "鲁大师才20万分",
            "reminderUrl": "",
            "readStatus": 0,
            "receiverUserId": "",
            "peerExternalUid": "25945493@goofish",
        },
        {
            "id": 738,
            "pnm_id": "4176436088690.PNM",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "嗯，自动客服没救了",
            "senderUserId": "2211422464341@goofish",
            "senderUserName": "小龙菜菜",
            "xyGoodsId": "1061663316195",
            "messageTime": 1719562531000,
            "direction": "IN",
            "reminderContent": "嗯，自动客服没救了",
            "reminderUrl": "",
            "readStatus": 0,
            "receiverUserId": "",
            "peerExternalUid": "2211422464341@goofish",
        },
    ]

    async def passthrough_merge(_db, _tenant_id, _account_id, base_messages, _s_id, _peer_user_id, **_kwargs):
        return base_messages

    monkeypatch.setattr(ws_storage, "_merge_context_messages_with_ai_replies", passthrough_merge)

    messages, total = await ws_storage.get_context_messages(
        db=_FakeDB(rows),
        tenant_id=1,
        account_id=1,
        s_id="63154410580",
        limit=50,
        offset=0,
        user_id=None,
        peer_user_id="2211422464341",
    )

    assert total == 2
    assert [item["id"] for item in messages] == [732, 738]


@pytest.mark.anyio
async def test_get_context_messages_keeps_sid_only_messages_for_selected_peer(monkeypatch):
    rows = [
        {
            "id": 738,
            "pnm_id": "4176436088690.PNM",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "hello-a",
            "senderUserId": "2211422464341@goofish",
            "senderUserName": "buyer-a",
            "xyGoodsId": "1061663316195",
            "messageTime": 1719562531000,
            "direction": "IN",
            "reminderContent": "hello-a",
            "reminderUrl": "",
            "readStatus": 0,
            "receiverUserId": "",
            "peerExternalUid": "2211422464341@goofish",
        },
        {
            "id": 739,
            "pnm_id": "4176436088691.PNM",
            "sid": "63154410580",
            "contentType": 1,
            "msgContent": "hello-b",
            "senderUserId": "",
            "senderUserName": "",
            "xyGoodsId": "1061663316195",
            "messageTime": 1719562599000,
            "direction": "IN",
            "reminderContent": "shading_opening",
            "reminderUrl": "",
            "readStatus": 0,
            "receiverUserId": "",
            "peerExternalUid": "",
        },
    ]

    async def passthrough_merge(_db, _tenant_id, _account_id, base_messages, _s_id, _peer_user_id, **_kwargs):
        return base_messages

    monkeypatch.setattr(ws_storage, "_merge_context_messages_with_ai_replies", passthrough_merge)

    messages, total = await ws_storage.get_context_messages(
        db=_FakeDB(rows),
        tenant_id=1,
        account_id=1,
        s_id="63154410580",
        limit=50,
        offset=0,
        user_id=None,
        peer_user_id="2211422464341",
    )

    assert total == 2
    assert [item["msgContent"] for item in messages] == ["hello-a", "hello-b"]


def test_is_displayable_message_rejects_empty_sid_shell_message():
    assert ws_storage._is_displayable_message(
        {
            "sid": "5500XT",
            "pnmId": "",
            "senderUserId": "",
            "receiverUserId": "",
            "peerExternalUid": "",
            "msgContent": "",
            "reminderContent": "",
        }
    ) is False


def test_is_displayable_message_rejects_misplaced_pnm_sender_message():
    assert ws_storage._is_displayable_message(
        {
            "sid": "62811007356",
            "pnmId": "1",
            "senderUserId": "4185457792510.PNM",
            "receiverUserId": "",
            "peerExternalUid": "4185457792510.PNM",
            "msgContent": "2215056191399@goofish",
            "reminderContent": "",
        }
    ) is False


def test_is_displayable_conversation_rejects_misplaced_pnm_sender_conversation():
    assert ws_storage._is_displayable_conversation(
        {
            "sid": "62811007356",
            "peerUserId": "4185457792510.PNM",
            "lastMessage": "2215056191399@goofish",
            "goodsId": "",
            "messageCount": 1,
        }
    ) is False


def test_conversation_group_key_merges_sid_fallback_rows_into_real_peer_once_peer_is_known():
    fallback_row = {
        "sid": "63247704189",
        "peerUserId": "sid:63247704189",
        "peerKey": "sid:63247704189",
        "goodsId": "",
        "messageCount": 1,
    }
    resolved_row = {
        "sid": "63247704189",
        "peerUserId": "3672669710@goofish",
        "peerKey": "sid:63247704189@goofish",
        "goodsId": "1061440910180",
        "messageCount": 4,
    }

    assert ws_storage._conversation_group_key(fallback_row) == "sid:63247704189"
    assert ws_storage._conversation_group_key(resolved_row) == "sid:63247704189"


def test_merge_online_conversation_rows_absorbs_sid_fallback_duplicate():
    merged = ws_storage._merge_online_conversation_rows([
        {
            "sid": "63247704189",
            "peerUserId": "sid:63247704189",
            "peerKey": "sid:63247704189",
            "peerUserName": "oofish",
            "lastMessage": "latest-preview",
            "lastMessageTime": 200,
            "firstMessageTime": 200,
            "goodsId": "",
            "goodsTitle": "",
            "goodsCoverPic": "",
            "unreadCount": "0",
            "messageCount": 1,
            "hasAiReply": False,
            "lastIsAutoReply": False,
        },
        {
            "sid": "63247704189",
            "peerUserId": "3672669710@goofish",
            "peerKey": "sid:63247704189@goofish",
            "peerUserName": "buyer-name",
            "lastMessage": "older-preview",
            "lastMessageTime": 100,
            "firstMessageTime": 50,
            "goodsId": "1061440910180",
            "goodsTitle": "goods-title",
            "goodsCoverPic": "cover.jpg",
            "unreadCount": "2",
            "messageCount": 4,
            "hasAiReply": True,
            "lastIsAutoReply": True,
        },
    ])

    assert len(merged) == 1
    assert merged[0]["sid"] == "63247704189"
    assert merged[0]["peerUserId"] == "3672669710@goofish"
    assert merged[0]["goodsId"] == "1061440910180"
    assert merged[0]["goodsTitle"] == "goods-title"
    assert merged[0]["lastMessage"] == "latest-preview"
    assert int(merged[0]["messageCount"]) == 5
    assert int(merged[0]["unreadCount"]) == 2
    assert merged[0]["hasAiReply"] is True


def test_merge_online_conversation_rows_keeps_conflicting_real_peers_separate():
    merged = ws_storage._merge_online_conversation_rows([
        {
            "sid": "63247704189",
            "peerUserId": "3672669710@goofish",
            "peerKey": "3672669710@goofish",
            "lastMessageTime": 200,
            "messageCount": 1,
        },
        {
            "sid": "63247704189",
            "peerUserId": "25945493@goofish",
            "peerKey": "25945493@goofish",
            "lastMessageTime": 100,
            "messageCount": 1,
        },
    ])

    assert len(merged) == 2


@pytest.mark.anyio
async def test_get_context_messages_hides_seller_self_peer_queries(monkeypatch):
    async def passthrough_merge(_db, _tenant_id, _account_id, base_messages, _s_id, _peer_user_id, **_kwargs):
        return base_messages

    monkeypatch.setattr(ws_storage, "_merge_context_messages_with_ai_replies", passthrough_merge)

    class _SellerAwareDB(_FakeDB):
        async def execute(self, statement, params=None):
            statement_text = str(statement)
            if "SELECT external_uid" in statement_text and "FROM xianyu_account" in statement_text:
                return _FakeResult(scalar_value="2211422464341")
            return await super().execute(statement, params)

    messages, total = await ws_storage.get_context_messages(
        db=_SellerAwareDB(
            [
                {
                    "id": 738,
                    "pnm_id": "4176436088690.PNM",
                    "sid": "63154410580",
                    "contentType": 1,
                    "msgContent": "喂，自动客服没救啊",
                    "senderUserId": "2211422464341@goofish",
                    "senderUserName": "小龙菜菜",
                    "xyGoodsId": "1061663316195",
                    "messageTime": 1719562531000,
                    "direction": "IN",
                    "reminderContent": "喂，自动客服没救啊",
                    "reminderUrl": "",
                    "readStatus": 0,
                    "receiverUserId": "",
                    "peerExternalUid": "2211422464341@goofish",
                },
            ]
        ),
        tenant_id=1,
        account_id=1,
        s_id="63154410580",
        limit=50,
        offset=0,
        user_id=None,
        peer_user_id="2211422464341",
    )

    assert messages == []
    assert total == 0


@pytest.mark.anyio
async def test_get_online_conversations_uses_live_official_rows_when_local_storage_is_empty(monkeypatch):
    async def fake_seller_uid(*_args, **_kwargs):
        return ""

    async def passthrough_ai(_db, _tenant_id, _account_id, conversations):
        return conversations

    async def passthrough_avatar(_db, _tenant_id, _account_id, conversations):
        return conversations

    async def fake_live_conversations(*_args, **_kwargs):
        return [
            {
                "sid": "63247704189",
                "peerUserId": "3672669710@goofish",
                "peerKey": "sid:63247704189",
                "peerUserName": "buyer-live",
                "lastMessage": "live-preview",
                "lastContentType": 1,
                "lastMessageTime": 1719562531000,
                "firstMessageTime": 1719562432000,
                "goodsId": "1061440910180",
                "goodsTitle": "live-goods-title",
                "goodsCoverPic": "https://example.com/cover.png",
                "reminderContent": "",
                "unreadCount": 1,
                "messageCount": 8,
                "conversationStatus": 0,
                "buyerAvatar": "",
                "goodsPrice": "",
                "goodsStatus": None,
            }
        ]

    monkeypatch.setattr(ws_storage, "_load_seller_external_uid", fake_seller_uid)
    monkeypatch.setattr(ws_storage, "_apply_ai_reply_preview", passthrough_ai)
    monkeypatch.setattr(ws_storage, "_hydrate_online_conversation_avatars", passthrough_avatar)
    monkeypatch.setattr(ws_storage, "_fetch_live_online_conversations", fake_live_conversations, raising=False)

    conversations = await ws_storage.get_online_conversations(
        db=_FakeDB([]),
        tenant_id=1,
        account_id=1,
        limit=20,
        user_id=None,
    )

    assert len(conversations) == 1
    assert conversations[0]["sid"] == "63247704189"
    assert conversations[0]["peerUserName"] == "buyer-live"
    assert conversations[0]["goodsTitle"] == "live-goods-title"


@pytest.mark.anyio
async def test_get_online_conversations_paged_first_page_seeds_cache_and_estimates_next_cursor(monkeypatch):
    rows = [
        {
            "sid": f"sid-{index}",
            "peerUserId": f"buyer-{index}@goofish",
            "peerKey": f"sid:sid-{index}",
            "peerUserName": f"buyer-{index}",
            "lastMessage": f"preview-{index}",
            "lastContentType": 1,
            "lastMessageTime": 1_719_562_431_000 - index,
            "goodsId": f"goods-{index}",
            "goodsTitle": f"goods-title-{index}",
            "unreadCount": 0,
            "messageCount": 1,
            "conversationStatus": 0,
        }
        for index in range(100)
    ]

    async def fake_get_online_conversations(**_kwargs):
        return rows

    monkeypatch.setattr(ws_storage, "get_online_conversations", fake_get_online_conversations)
    monkeypatch.setattr(ws_client_module.ws_manager, "get_client", lambda _account_id: None)
    ws_storage._online_conversations_cache.clear()

    result = await ws_storage.get_online_conversations_paged(
        db=_FakeDB([]),
        tenant_id=1,
        account_id=1,
        cursor=None,
        page_size=100,
        user_id=None,
    )

    assert len(result["conversations"]) == 100
    assert result["hasMore"] is True
    assert result["nextCursor"] == rows[-1]["lastMessageTime"]
    assert (1, 1, None, 100) in ws_storage._online_conversations_cache


@pytest.mark.anyio
async def test_get_online_conversations_paged_first_page_returns_db_snapshot_before_live_refresh(monkeypatch):
    class _FakeClient:
        is_connected = True
        unb = ""

        async def list_conversations(self, start_timestamp=None, limit=20):
            assert start_timestamp is None
            assert limit == 20
            return {
                "userConvs": [
                    {
                        "sid": f"sid-{index}",
                        "peerUserId": f"buyer-{index}@goofish",
                        "peerKey": f"sid:sid-{index}",
                        "peerUserName": f"buyer-{index}-live",
                        "lastMessage": f"live-preview-{index}",
                        "lastContentType": 1,
                        "lastMessageTime": 500 - index,
                        "goodsId": f"goods-{index}",
                        "goodsTitle": f"goods-title-{index}-live",
                        "unreadCount": index % 2,
                        "messageCount": index + 1,
                        "conversationStatus": 0,
                    }
                    for index in range(20)
                ],
                "hasMore": True,
                "nextCursor": 180,
            }

    db_calls = {"count": 0}

    async def fake_get_online_conversations(**_kwargs):
        db_calls["count"] += 1
        return [
            {
                "sid": "sid-db-1",
                "peerUserId": "buyer-db-1@goofish",
                "peerKey": "sid:sid-db-1",
                "peerUserName": "buyer-db-1",
                "lastMessage": "db-preview-1",
                "lastContentType": 1,
                "lastMessageTime": 100,
                "goodsId": "goods-db-1",
                "goodsTitle": "goods-title-db-1",
                "unreadCount": 0,
                "messageCount": 1,
                "conversationStatus": 0,
            }
        ]

    async def fake_load_seller_uid(*_args, **_kwargs):
        return ""

    async def fake_refresh(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ws_storage, "get_online_conversations", fake_get_online_conversations)
    monkeypatch.setattr(ws_client_module.ws_manager, "get_client", lambda _account_id: _FakeClient())
    monkeypatch.setattr(ws_storage, "_load_seller_external_uid", fake_load_seller_uid)
    monkeypatch.setattr(ws_storage, "_refresh_im_conversations_background", fake_refresh)
    monkeypatch.setattr(ws_storage, "_parse_live_conversation", lambda item, _seller_uid: dict(item))
    monkeypatch.setattr(ws_storage, "_is_displayable_conversation", lambda _row: True)
    monkeypatch.setattr(ws_storage, "_hydrate_online_conversation_avatars_from_cache", lambda rows: rows)
    ws_storage._online_conversations_cache.clear()

    result = await ws_storage.get_online_conversations_paged(
        db=_FakeDB([]),
        tenant_id=1,
        account_id=1,
        cursor=None,
        page_size=20,
        user_id=None,
    )

    assert db_calls["count"] == 1
    assert len(result["conversations"]) == 1
    assert result["conversations"][0]["sid"] == "sid-db-1"
    assert result["hasMore"] is False
    assert result["nextCursor"] is None


@pytest.mark.anyio
async def test_get_online_conversations_paged_cursor_page_uses_db_snapshot_before_live_refresh(monkeypatch):
    class _FakeClient:
        is_connected = True
        unb = ""

    calls = []

    async def fake_get_online_conversations(**kwargs):
        calls.append(kwargs)
        return [
            {
                "sid": "sid-db-older",
                "peerUserId": "buyer-db-older@goofish",
                "peerKey": "sid:sid-db-older",
                "peerUserName": "buyer-db-older",
                "lastMessage": "db-preview-older",
                "lastContentType": 1,
                "lastMessageTime": 90,
                "goodsId": "goods-db-older",
                "goodsTitle": "goods-title-db-older",
                "unreadCount": 0,
                "messageCount": 1,
                "conversationStatus": 0,
            }
        ]

    async def fake_refresh(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ws_storage, "get_online_conversations", fake_get_online_conversations)
    monkeypatch.setattr(ws_client_module.ws_manager, "get_client", lambda _account_id: _FakeClient())
    monkeypatch.setattr(ws_storage, "_refresh_im_conversations_background", fake_refresh)
    ws_storage._online_conversations_cache.clear()

    result = await ws_storage.get_online_conversations_paged(
        db=_FakeDB([]),
        tenant_id=1,
        account_id=1,
        cursor=100,
        page_size=20,
        user_id=None,
    )

    assert len(calls) == 1
    assert calls[0]["before_message_time"] == 100
    assert result["conversations"][0]["sid"] == "sid-db-older"
    assert result["hasMore"] is False
    assert result["nextCursor"] is None


@pytest.mark.anyio
async def test_refresh_im_conversations_background_replaces_cached_db_snapshot_with_live_first_page(monkeypatch):
    class _FakeClient:
        is_connected = True
        unb = ""

        async def list_conversations(self, start_timestamp=None, limit=20):
            assert start_timestamp is None
            assert limit == 100
            return {
                "userConvs": [
                    {
                        "sid": "sid-1",
                        "peerUserId": "buyer-1@goofish",
                        "peerKey": "sid:sid-1",
                        "peerUserName": "buyer-1-live",
                        "lastMessage": "live-preview-1",
                        "lastContentType": 1,
                        "lastMessageTime": 400,
                        "goodsId": "goods-1",
                        "goodsTitle": "goods-title-1-live",
                        "unreadCount": 2,
                        "messageCount": 3,
                        "conversationStatus": 0,
                    },
                    {
                        "sid": "sid-4",
                        "peerUserId": "buyer-4@goofish",
                        "peerKey": "sid:sid-4",
                        "peerUserName": "buyer-4-live",
                        "lastMessage": "live-preview-4",
                        "lastContentType": 1,
                        "lastMessageTime": 250,
                        "goodsId": "goods-4",
                        "goodsTitle": "goods-title-4-live",
                        "unreadCount": 0,
                        "messageCount": 1,
                        "conversationStatus": 0,
                    },
                ],
                "hasMore": True,
                "nextCursor": 180,
            }

    async def fake_load_seller_uid(*_args, **_kwargs):
        return ""

    monkeypatch.setattr(ws_client_module.ws_manager, "get_client", lambda _account_id: _FakeClient())
    monkeypatch.setattr(ws_storage, "_load_seller_external_uid", fake_load_seller_uid)
    monkeypatch.setattr(ws_storage, "_parse_live_conversation", lambda item, _seller_uid: dict(item))
    monkeypatch.setattr(ws_storage, "_is_displayable_conversation", lambda _row: True)
    monkeypatch.setattr(ws_storage, "_hydrate_online_conversation_avatars_from_cache", lambda rows: rows)

    ws_storage._online_conversations_cache.clear()
    ws_storage._online_conversations_cache[(1, 1, None, 100)] = (
        0.0,
        {
            "conversations": [
                {
                    "sid": "sid-1",
                    "peerUserId": "buyer-1@goofish",
                    "peerKey": "sid:sid-1",
                    "peerUserName": "buyer-1-db",
                    "lastMessage": "db-preview-1",
                    "lastContentType": 1,
                    "lastMessageTime": 390,
                    "goodsId": "goods-1",
                    "goodsTitle": "goods-title-1-db",
                    "unreadCount": 0,
                    "messageCount": 10,
                    "conversationStatus": 0,
                },
                {
                    "sid": "sid-2",
                    "peerUserId": "buyer-2@goofish",
                    "peerKey": "sid:sid-2",
                    "peerUserName": "buyer-2-db",
                    "lastMessage": "db-preview-2",
                    "lastContentType": 1,
                    "lastMessageTime": 300,
                    "goodsId": "goods-2",
                    "goodsTitle": "goods-title-2-db",
                    "unreadCount": 0,
                    "messageCount": 8,
                    "conversationStatus": 0,
                },
                {
                    "sid": "sid-3",
                    "peerUserId": "buyer-3@goofish",
                    "peerKey": "sid:sid-3",
                    "peerUserName": "buyer-3-db",
                    "lastMessage": "db-preview-3",
                    "lastContentType": 1,
                    "lastMessageTime": 200,
                    "goodsId": "goods-3",
                    "goodsTitle": "goods-title-3-db",
                    "unreadCount": 0,
                    "messageCount": 4,
                    "conversationStatus": 0,
                },
            ],
            "hasMore": True,
            "nextCursor": 200,
        },
    )

    await ws_storage._refresh_im_conversations_background(
        tenant_id=1,
        account_id=1,
        cursor=None,
        page_size=100,
        user_id=None,
    )

    cached = ws_storage._online_conversations_cache[(1, 1, None, 100)][1]
    assert cached["hasMore"] is True
    assert cached["nextCursor"] == 180
    assert [item["sid"] for item in cached["conversations"]] == ["sid-1", "sid-4"]


@pytest.mark.anyio
async def test_get_context_messages_uses_live_history_when_local_rows_are_missing(monkeypatch):
    async def fake_seller_uid(*_args, **_kwargs):
        return ""

    async def passthrough_merge(_db, _tenant_id, _account_id, base_messages, _s_id, _peer_user_id, **_kwargs):
        return base_messages

    async def fake_live_messages(*_args, **_kwargs):
        return [
            {
                "id": "live-1",
                "pnmId": "live-pnm-1",
                "sid": "63154410580",
                "contentType": 2,
                "msgContent": "https://example.com/history-image.png",
                "imageUrls": ["https://example.com/history-image.png"],
                "senderUserId": "25945493@goofish",
                "senderUserName": "buyer-live",
                "receiverUserId": "2211422464341@goofish",
                "peerExternalUid": "25945493@goofish",
                "messageTime": 1719562432000,
                "direction": "IN",
                "readStatus": 0,
            }
        ]

    monkeypatch.setattr(ws_storage, "_load_seller_external_uid", fake_seller_uid)
    monkeypatch.setattr(ws_storage, "_merge_context_messages_with_ai_replies", passthrough_merge)
    monkeypatch.setattr(ws_storage, "_fetch_live_context_messages", fake_live_messages, raising=False)

    messages, total = await ws_storage.get_context_messages(
        db=_FakeDB([]),
        tenant_id=1,
        account_id=1,
        s_id="63154410580",
        limit=50,
        offset=0,
        user_id=None,
        peer_user_id="25945493",
    )

    assert total == 1
    assert messages[0]["contentType"] == 2
    assert messages[0]["msgContent"] == "https://example.com/history-image.png"


def test_parse_live_history_message_extracts_image_urls():
    model = {
        "message": {
            "messageId": "4185399355781.PNM",
            "createAt": 1719562432000,
            "content": {
                "custom": {
                    "data": "eyJjb250ZW50VHlwZSI6MiwiaW1hZ2UiOnsicGljcyI6W3sidXJsIjoiaHR0cHM6Ly9leGFtcGxlLmNvbS9oaXN0b3J5LmpwZyIsIndpZHRoIjo2NDAsImhlaWdodCI6NDgwfV19fQ=="
                }
            },
            "extension": {
                "senderUserId": "25945493@goofish",
                "reminderTitle": "buyer-live"
            }
        }
    }

    parsed = ws_storage._parse_live_history_message(
        model,
        sid="63154410580",
        seller_external_uid="2211422464341",
        peer_user_id="25945493",
    )

    assert parsed is not None
    assert parsed["contentType"] == 2
    assert parsed["msgContent"] == "https://example.com/history.jpg"
    assert parsed["imageUrls"] == ["https://example.com/history.jpg"]
    assert parsed["direction"] == "IN"
    assert parsed["senderUserId"] == "25945493@goofish"
