from app.services.captcha_backoff import _cooldown_seconds
from app.services.captcha_queue import SERVICE_UNAVAILABLE_COOLDOWN_SEC, SOLVE_DEDUP_COOLDOWN_SEC


def test_backoff_policy_has_no_long_cooldown():
    assert _cooldown_seconds(1) == 60
    assert _cooldown_seconds(2) == 60
    assert _cooldown_seconds(7) == 60


def test_only_one_minute_queue_cooldown_remains():
    assert SOLVE_DEDUP_COOLDOWN_SEC == 60
    assert SERVICE_UNAVAILABLE_COOLDOWN_SEC == 60
