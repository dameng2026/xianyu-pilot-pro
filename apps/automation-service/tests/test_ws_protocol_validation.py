import base64
import json

from app.services.ws_protocol import (
    build_send_image_message,
    build_send_message,
    parse_numbered_fields,
    validate_parsed_message,
)


def test_validate_parsed_message_marks_seller_self_message_as_out_with_goofish_suffix():
    msg = {
        "sId": "63154410580",
        "pnmId": "4176436088690.PNM",
        "contentType": 1,
        "msgContent": "嗯，自动客服没救了",
        "senderUserId": "2211422464341@goofish",
        "receiverUserId": "",
        "direction": "IN",
        "sellerExternalUid": "2211422464341",
        "messageTime": 1719562531000,
    }

    result = validate_parsed_message(msg)

    assert result["direction"] == "OUT"


def test_validate_parsed_message_marks_misplaced_pnm_sender_as_failed():
    msg = {
        "sId": "62811007356@goofish",
        "pnmId": "1",
        "contentType": 1,
        "msgContent": "2215056191399@goofish",
        "senderUserId": "4185457792510.PNM",
        "receiverUserId": "",
        "direction": "IN",
        "sellerExternalUid": "2211422464341",
        "messageTime": 1782539127330,
    }

    result = validate_parsed_message(msg)

    assert result["parseStatus"] == "failed"


def test_build_send_message_preserves_chinese_text_and_normalizes_ids():
    payload = build_send_message(
        "63247704189",
        "3672669710",
        "2211422464341",
        "转换后不会乱码吗？",
        "session-token",
    )

    assert payload["body"][0]["cid"] == "63247704189@goofish"
    assert payload["body"][1]["actualReceivers"] == [
        "3672669710@goofish",
        "2211422464341@goofish",
    ]

    encoded = payload["body"][0]["content"]["custom"]["data"]
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert decoded["text"]["text"] == "转换后不会乱码吗？"


def test_build_send_image_message_normalizes_ids():
    payload = build_send_image_message(
        "sid:63247704189@goofish",
        "3672669710",
        "2211422464341@goofish",
        "https://example.com/demo.png",
        "session-token",
    )

    assert payload["body"][0]["cid"] == "63247704189@goofish"
    assert payload["body"][1]["actualReceivers"] == [
        "3672669710@goofish",
        "2211422464341@goofish",
    ]

    encoded = payload["body"][0]["content"]["custom"]["data"]
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
    assert payload["body"][0]["content"]["custom"]["type"] == 1
    assert decoded["contentType"] == 2
    assert decoded["image"]["url"] == "https://example.com/demo.png"
    assert decoded["image"]["pics"][0] == {
        "height": 600,
        "type": 0,
        "url": "https://example.com/demo.png",
        "width": 800,
    }


def test_parse_numbered_fields_extracts_image_message_url():
    payload = {
        "1": {
            "1": {"1": "3672669710@goofish", "2": "买家A"},
            "2": "63247704189",
            "3": "4176436088690.PNM",
            "5": 1719562531000,
            "6": {
                "3": {
                    "5": json.dumps(
                        {
                            "contentType": 2,
                            "image": {
                                "pics": [
                                    {"url": "https://img.alicdn.com/imgextra/demo-a.png"},
                                    {"url": "https://img.alicdn.com/imgextra/demo-b.png"},
                                ]
                            },
                        },
                        ensure_ascii=False,
                    )
                }
            },
        }
    }

    result = parse_numbered_fields(payload)

    assert result is not None
    assert result["contentType"] == 2
    assert result["msgContent"] == "https://img.alicdn.com/imgextra/demo-a.png"
    assert result["imageUrl"] == "https://img.alicdn.com/imgextra/demo-a.png"
    assert result["imageUrls"] == [
        "https://img.alicdn.com/imgextra/demo-a.png",
        "https://img.alicdn.com/imgextra/demo-b.png",
    ]


def test_parse_numbered_fields_extracts_image_message_url_from_base64_custom_data():
    encoded = base64.b64encode(
        json.dumps(
            {
                "contentType": 2,
                "image": {
                    "pics": [
                        {"url": "https://img.alicdn.com/imgextra/base64-a.png"},
                        {"url": "https://img.alicdn.com/imgextra/base64-b.png"},
                    ]
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
    ).decode("utf-8")
    payload = {
        "1": {
            "1": {"1": "3672669710@goofish", "2": "buyer-a"},
            "2": "63247704189",
            "3": "4176436088691.PNM",
            "5": 1719562532000,
            "6": {
                "3": {
                    "1": encoded,
                }
            },
            "10": {
                "reminderContent": "[图片]",
                "reminderUrl": "fleamarket://message_chat?itemId=1061663316195",
            },
        }
    }

    result = parse_numbered_fields(payload)

    assert result is not None
    assert result["contentType"] == 2
    assert result["msgContent"] == "https://img.alicdn.com/imgextra/base64-a.png"
    assert result["imageUrl"] == "https://img.alicdn.com/imgextra/base64-a.png"
    assert result["imageUrls"] == [
        "https://img.alicdn.com/imgextra/base64-a.png",
        "https://img.alicdn.com/imgextra/base64-b.png",
    ]
