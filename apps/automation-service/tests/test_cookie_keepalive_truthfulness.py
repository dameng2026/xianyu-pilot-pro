import pytest

from app.services import cookie_token_refresher


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('{"success": true}', True),
        ('{"hasLogin": true}', True),
        ('{"data": {"hasLogin": true}}', True),
        ('{"success": false, "hasLogin": false}', False),
        ('<html>defaultView=hasLogin</html>', False),
        ("", False),
    ],
)
def test_cookie_keepalive_requires_explicit_authenticated_evidence(body, expected):
    assert cookie_token_refresher._is_has_login_confirmed(body) is expected
