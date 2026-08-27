import pytest
from app.services.automation_runtime import _build_ai_cs_system_prompt


def test_prompt_without_kb_hits():
    cfg = {"systemPrompt": "你是客服"}
    prompt = _build_ai_cs_system_prompt(cfg, None, [], [], [], [])
    assert "学习知识库" not in prompt
    assert "我的知识库" not in prompt


def test_prompt_with_learned_kb():
    cfg = {"systemPrompt": "你是客服"}
    hits = [{"question": "Q1", "answer": "A1", "category": "电子", "score": 80}]
    prompt = _build_ai_cs_system_prompt(
        cfg, None, [], [], [], [],
        learned_kb_hits=hits
    )
    assert "学习知识库（按问题匹配，含分类标签）" in prompt
    assert "Q1" in prompt
    assert "A1" in prompt
    assert "电子" in prompt


def test_prompt_with_user_private_kb():
    cfg = {"systemPrompt": "你是客服"}
    hits = [{"title": "发货话术", "content": "亲爱的，已发货"}]
    prompt = _build_ai_cs_system_prompt(
        cfg, None, [], [], [], [],
        user_private_kb_hits=hits
    )
    assert "我的私有知识库（最高优先级）" in prompt
    assert "发货话术" in prompt
    assert "亲爱的，已发货" in prompt
