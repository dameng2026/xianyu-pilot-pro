import io
from pathlib import Path

import pytest
import requests
from PIL import Image

from app.services import xianyu_goods_sync as sync


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


def _publisher(*, tenant_id=7, verifier=None, remote_loader=None):
    return sync.XianyuItemPublisher(
        "_m_h5_tk=token_12345; cookie2=value",
        tenant_id,
        asset_verifier=verifier or (lambda _tenant, _url, _key: len(_png_bytes())),
        remote_image_loader=remote_loader or (lambda _url: _png_bytes()),
    )


def test_local_publish_image_requires_exact_tenant_path_and_active_asset(monkeypatch, tmp_path):
    fake_module = tmp_path / "app" / "services" / "xianyu_goods_sync.py"
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(sync, "__file__", str(fake_module))
    image_path = tmp_path / "uploads" / "images" / "tenant-7" / "cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(_png_bytes())

    seen = []
    publisher = _publisher(
        verifier=lambda tenant, url, key: seen.append((tenant, url, key)) or image_path.stat().st_size
    )
    content = publisher._read_publish_image("/uploads/images/tenant-7/cover.png")

    assert content == _png_bytes()
    assert seen == [(7, "/uploads/images/tenant-7/cover.png", "tenant-7/cover.png")]


@pytest.mark.parametrize(
    "url",
    [
        "/uploads/images/tenant-8/cover.png",
        "/uploads/images/cover.png",
        "/uploads/images/tenant-7/%2e%2e/tenant-8/cover.png",
        "/uploads/images/tenant-7/..\\tenant-8\\cover.png",
    ],
)
def test_local_publish_image_rejects_other_tenant_legacy_and_traversal(url):
    with pytest.raises(RuntimeError, match="无效|不属于当前租户|非法"):
        _publisher()._read_publish_image(url)


def test_local_publish_image_fails_closed_when_asset_is_not_active(monkeypatch, tmp_path):
    fake_module = tmp_path / "app" / "services" / "xianyu_goods_sync.py"
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(sync, "__file__", str(fake_module))
    image_path = tmp_path / "uploads" / "images" / "tenant-7" / "cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(_png_bytes())

    def inactive(*_args):
        raise ValueError("inactive")

    with pytest.raises(RuntimeError, match="已失效或不存在"):
        _publisher(verifier=inactive)._read_publish_image("/uploads/images/tenant-7/cover.png")


def test_remote_publish_image_rejects_private_dns_before_request(monkeypatch):
    monkeypatch.setattr(
        sync.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    monkeypatch.setattr(
        sync.requests,
        "get",
        lambda *_args, **_kwargs: pytest.fail("private destination must not be requested"),
    )

    with pytest.raises(ValueError, match="non-public"):
        sync._download_public_image_sync("https://localhost/internal.png")

    with pytest.raises(RuntimeError, match="远程商品图片无法安全下载"):
        _publisher(
            remote_loader=lambda _url: (_ for _ in ()).throw(ValueError("non-public"))
        )._read_publish_image("https://localhost/internal.png")


class _Socket:
    def getpeername(self):
        return ("8.8.8.8", 443)


class _Connection:
    sock = _Socket()


class _Raw:
    _connection = _Connection()


class _Response:
    status_code = 200
    raw = _Raw()

    def __init__(self, *, headers, chunks=()):
        self.headers = headers
        self._chunks = chunks
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self._chunks)

    def close(self):
        self.closed = True


def test_remote_publish_image_rejects_oversize_content_length(monkeypatch):
    response = _Response(headers={"Content-Length": str(sync.MAX_IMAGE_BYTES + 1)})
    monkeypatch.setattr(
        sync.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
    )
    monkeypatch.setattr(sync.requests, "get", lambda *_args, **_kwargs: response)

    with pytest.raises(ValueError, match="size limit"):
        sync._download_public_image_sync("https://images.example/large.png")
    assert response.closed


class _UploadResponse:
    def __init__(self, *, status_code=200, payload=None, text="", url="", headers=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text or payload is None else ""
        self.url = url or "https://stream-upload.goofish.com/api/upload.api"
        self.headers = headers or {"Content-Type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class _FakeSession:
    def __init__(self, response=None, error=None, responses=None):
        self._response = response
        self._error = error
        self._responses = list(responses or [])
        self.cookies = requests.cookies.RequestsCookieJar()
        self.last_request = None
        self.requests = []

    def post(self, url, **kwargs):
        self.last_request = {"url": url, **kwargs}
        self.requests.append(self.last_request)
        if self._error is not None:
            raise self._error
        if self._responses:
            return self._responses.pop(0)
        return self._response


def test_publish_image_upload_failure_never_returns_original_url(monkeypatch):
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(
        sync.requests,
        "Session",
        lambda: _FakeSession(error=requests.exceptions.Timeout()),
    )

    with pytest.raises(RuntimeError, match="超时"):
        publisher.upload_image_to_xianyu("https://images.example/cover.png")


def test_publisher_requires_a_positive_tenant_scope():
    with pytest.raises(ValueError, match="tenant_id"):
        _publisher(tenant_id=0)


@pytest.mark.parametrize(
    "payload,expected",
    [
        # 顶层 url：旧实现因 or/if 优先级会丢弃（data 非 dict 时）
        ({"url": "https://img.alicdn.com/i4/top.jpg", "data": None}, "https://img.alicdn.com/i4/top.jpg"),
        ({"url": "https://img.alicdn.com/i4/top2.jpg"}, "https://img.alicdn.com/i4/top2.jpg"),
        ({"data": {"url": "https://img.alicdn.com/i4/data.jpg"}}, "https://img.alicdn.com/i4/data.jpg"),
        ({"object": {"url": "https://img.alicdn.com/i4/object.jpg"}}, "https://img.alicdn.com/i4/object.jpg"),
        ({"result": {"url": "https://img.alicdn.com/i4/result.jpg"}}, "https://img.alicdn.com/i4/result.jpg"),
        ({"data": {"fileUrl": "https://img.alicdn.com/i4/file.jpg"}}, "https://img.alicdn.com/i4/file.jpg"),
        ({"data": {"cdnUrl": "https://img.alicdn.com/i4/cdn.jpg"}}, "https://img.alicdn.com/i4/cdn.jpg"),
        ([{"url": "https://img.alicdn.com/i4/list.jpg"}], "https://img.alicdn.com/i4/list.jpg"),
        # 协议相对地址
        ({"url": "//img.alicdn.com/i4/proto.jpg"}, "//img.alicdn.com/i4/proto.jpg"),
        # 仅嵌套字符串可被正则兜底
        ({"payload": {"x": "https://gw.alicdn.com/imgextra/regex.jpg"}}, "https://gw.alicdn.com/imgextra/regex.jpg"),
    ],
)
def test_extract_publish_cdn_url_supports_common_response_shapes(payload, expected):
    assert sync.XianyuItemPublisher._extract_publish_cdn_url(payload) == expected


def test_normalize_cdn_url_upgrades_protocol_relative_and_http():
    assert (
        sync.XianyuItemPublisher._normalize_cdn_url("//img.alicdn.com/a.jpg")
        == "https://img.alicdn.com/a.jpg"
    )
    assert (
        sync.XianyuItemPublisher._normalize_cdn_url("http://img.alicdn.com/a.jpg")
        == "https://img.alicdn.com/a.jpg"
    )
    with pytest.raises(RuntimeError, match="不安全"):
        sync.XianyuItemPublisher._normalize_cdn_url("ftp://img.alicdn.com/a.jpg")


def test_upload_image_to_xianyu_parses_top_level_url_when_data_is_null(monkeypatch):
    """回归：历史上 `a or b if c else d` 会在 data=null 时丢掉顶层 url，导致误报图片上传失败。"""
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    session = _FakeSession(
        response=_UploadResponse(
            payload={"code": "0", "url": "https://img.alicdn.com/i4/publish-ok.jpg", "data": None}
        )
    )
    monkeypatch.setattr(sync.requests, "Session", lambda: session)

    cdn = publisher.upload_image_to_xianyu("https://images.example/cover.png")
    assert cdn == "https://img.alicdn.com/i4/publish-ok.jpg"
    assert session.last_request is not None
    assert "files" in session.last_request
    assert session.last_request["files"]["file"][2] == "image/jpeg"
    # Cookie 必须以请求头完整透传，不能只依赖 CookieJar domain
    assert "Cookie" in session.last_request["headers"]
    assert "_m_h5_tk=" in session.last_request["headers"]["Cookie"]
    assert session.last_request.get("allow_redirects") is True


def test_upload_image_to_xianyu_parses_file_url_nested_field(monkeypatch):
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(
        sync.requests,
        "Session",
        lambda: _FakeSession(
            response=_UploadResponse(
                payload={"success": True, "data": {"fileUrl": "https://img.alicdn.com/i4/file-url.jpg"}}
            )
        ),
    )

    cdn = publisher.upload_image_to_xianyu("https://images.example/cover.png")
    assert cdn == "https://img.alicdn.com/i4/file-url.jpg"


def test_upload_image_preserves_specific_runtime_error_message(monkeypatch):
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(
        sync.requests,
        "Session",
        lambda: _FakeSession(response=_UploadResponse(payload={"code": 0, "data": {}})),
    )

    # 上传响应未包含 CDN 地址时，应抛出面向用户的友好错误（含"图片上传失败"）
    with pytest.raises(RuntimeError, match="图片上传失败"):
        publisher.upload_image_to_xianyu("https://images.example/cover.png")


def test_upload_image_passport_redirect_refreshes_cookie_then_succeeds(monkeypatch):
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    refresh_calls = []

    def _fake_refresh(cookie_str):
        refresh_calls.append(cookie_str)
        return cookie_str + "; refreshed=1"

    monkeypatch.setattr(sync, "_refresh_m_h5_tk", _fake_refresh)
    session = _FakeSession(
        responses=[
            _UploadResponse(
                status_code=200,
                url="https://passport.goofish.com/mini_login.htm",
                headers={"Content-Type": "text/html"},
                text="<html>请先登录</html>",
                payload=None,
            ),
            _UploadResponse(
                payload={"url": "https://img.alicdn.com/i4/after-refresh.jpg"}
            ),
        ]
    )
    monkeypatch.setattr(sync.requests, "Session", lambda: session)

    cdn = publisher.upload_image_to_xianyu("https://images.example/cover.png")
    assert cdn == "https://img.alicdn.com/i4/after-refresh.jpg"
    assert len(refresh_calls) == 1
    assert "refreshed=1" in session.requests[-1]["headers"]["Cookie"]


def test_upload_http_403_does_not_claim_login_dead_when_mtop_alive(monkeypatch):
    """回归：搜索/账号页 Cookie 正常时，stream-upload 403 不能误报登录失效。"""
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(sync, "_refresh_m_h5_tk", lambda cookie: cookie)
    monkeypatch.setattr(
        sync.requests,
        "Session",
        lambda: _FakeSession(
            response=_UploadResponse(status_code=403, payload={"msg": "forbidden"})
        ),
    )
    monkeypatch.setattr(publisher, "_mtop_session_alive", lambda: True)

    with pytest.raises(RuntimeError, match="登录状态正常"):
        publisher.upload_image_to_xianyu("https://images.example/cover.png")


def test_upload_http_403_claims_login_dead_only_when_mtop_dead(monkeypatch):
    publisher = _publisher()
    monkeypatch.setattr(sync.time, "sleep", lambda *_args: None)
    monkeypatch.setattr(sync, "_refresh_m_h5_tk", lambda cookie: cookie)
    monkeypatch.setattr(
        sync.requests,
        "Session",
        lambda: _FakeSession(
            response=_UploadResponse(status_code=403, payload={"msg": "forbidden"})
        ),
    )
    monkeypatch.setattr(publisher, "_mtop_session_alive", lambda: False)

    with pytest.raises(RuntimeError, match="重新登录"):
        publisher.upload_image_to_xianyu("https://images.example/cover.png")


def test_refresh_m_h5_tk_does_not_drop_original_login_cookies(monkeypatch):
    """回归：刷新只更新令牌字段，不得清空 unb/cookie2 等登录 cookie。"""
    original = (
        "_m_h5_tk=oldtoken_1; unb=12345; cookie2=keepme; sgcookie=sg1; other=1"
    )

    class _CookieMap:
        def __init__(self, data):
            self._data = data

        def get(self, name):
            return self._data.get(name)

        def set(self, name, value, **_kwargs):
            self._data[name] = value

        def __iter__(self):
            return iter([])

    class _RefreshSession:
        def __init__(self):
            self.cookies = _CookieMap({})

        def get(self, *_args, **_kwargs):
            self.cookies.set("_m_h5_tk", "newtoken_999")
            self.cookies.set("_m_h5_tk_enc", "enc999")
            # 模拟服务端错误地下发空 cookie2 —— 旧逻辑会覆盖掉 keepme
            self.cookies.set("cookie2", "")
            return _UploadResponse(payload={})

        def post(self, *_args, **_kwargs):
            self.cookies.set("_m_h5_tk", "newtoken_999")
            return _UploadResponse(payload={})

    monkeypatch.setattr(sync.requests, "Session", lambda: _RefreshSession())
    refreshed = sync._refresh_m_h5_tk(original)
    assert "unb=12345" in refreshed
    assert "cookie2=keepme" in refreshed
    assert "sgcookie=sg1" in refreshed
    assert "_m_h5_tk=newtoken_999" in refreshed
