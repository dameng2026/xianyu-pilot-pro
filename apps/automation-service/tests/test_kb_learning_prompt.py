import pytest
from app.services.kb_learning_service import sanitize_text, md5_hash


def test_sanitize_phone():
    assert sanitize_text("我的电话是13800138000") == "我的电话是[手机号]"


def test_sanitize_qq():
    assert "123456789" not in sanitize_text("QQ：123456789")


def test_md5_hash_stable():
    assert md5_hash("hello") == "5d41402abc4b2a76b9719d911017c592"


def test_md5_hash_empty():
    assert md5_hash("") == "d41d8cd98f00b204e9800998ecf8427e"
