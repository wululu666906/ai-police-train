"""Tests for state contract post-check."""

from services.state_contract_postcheck import (
    apply_contract_postcheck,
    validate_response_against_contract,
)


def test_validate_angry_contract_flags_long_plain_reply():
    contract = {
        "primary_affect": "angry",
        "interruption_allowed": True,
        "max_sentences": 2,
        "must_include": [],
        "must_avoid": ["完整时间线"],
    }
    text = "我当时就在家里，后来听到外面吵起来，我就下楼看，然后看到他们推搡，具体谁先动手我不太清楚，但是场面很乱。"
    result = validate_response_against_contract(text, contract)
    assert result["ok"] is False
    assert "too_long_for_high_arousal" in result["issues"]


def test_validate_fearful_contract_requires_fear_markers():
    contract = {"primary_affect": "fearful", "max_sentences": 2, "must_include": [], "must_avoid": []}
    ok_text = "我不确定，我有点怕，真的记不清了。"
    bad_text = "事情就是这样，没有别的了。"
    assert validate_response_against_contract(ok_text, contract)["ok"] is True
    assert validate_response_against_contract(bad_text, contract)["ok"] is False


def test_validate_low_disclosure_flags_timeline():
    contract = {
        "primary_affect": "guarded",
        "disclosure_level": 0.22,
        "max_sentences": 2,
        "max_chars": 55,
        "escalation_bias": 0.2,
        "must_include": [],
        "must_avoid": [],
    }
    text = "我先在门口站着，然后再进去，最后看见他们打起来。"
    result = validate_response_against_contract(text, contract)
    assert result["ok"] is False
    assert "timeline_forbidden_at_low_disclosure" in result["issues"]


def test_apply_contract_postcheck_appends_follow_up_without_llm():
    contract = {
        "primary_affect": "fearful",
        "delivery": "fearful",
        "sentence_style": "broken",
        "max_sentences": 2,
        "tone_hint": "害怕",
        "must_include": [],
        "must_avoid": [],
        "interruption_allowed": False,
    }
    post = apply_contract_postcheck(
        "事情就是这样，没有别的了。",
        contract,
        use_llm=False,
    )
    assert post["adjusted"] is True
    assert post.get("follow_up")
