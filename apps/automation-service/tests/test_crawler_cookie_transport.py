import requests

from app.api.v1.routes import misc
from app.services import automation_runtime


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True, "items": []}


def _assert_cookie_is_sent_in_json(monkeypatch, callback):
    calls = []

    def post(url, *, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _Response()

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("authentication cookies must not be placed in a GET URL")
        ),
    )
    monkeypatch.setattr(requests, "post", post)

    callback()

    assert len(calls) == 1
    assert calls[0]["json"] == {
        "q": "显卡",
        "page": 2,
        "pageSize": 20,
        "cookie": "_m_h5_tk=sensitive",
    }
    assert "cookie" not in calls[0]["url"].lower()


def test_workflow_search_posts_cookie_in_json(monkeypatch):
    _assert_cookie_is_sent_in_json(
        monkeypatch,
        lambda: automation_runtime._workflow_search_slow(
            "显卡",
            2,
            20,
            7,
            "_m_h5_tk=sensitive",
        ),
    )


def test_business_search_posts_cookie_in_json(monkeypatch):
    _assert_cookie_is_sent_in_json(
        monkeypatch,
        lambda: misc._call_crawler_search(
            "显卡",
            2,
            20,
            7,
            "_m_h5_tk=sensitive",
        ),
    )
