"""Tests for four-axis state influence engine."""

from services.state_influence_engine import (
    blend_four_axis_state,
    build_state_contract,
    compute_trigger_axis_deltas,
    enrich_momentum_with_axis_deltas,
    resolve_band,
)


def test_resolve_band_tiers():
    assert resolve_band(10) == "very_low"
    assert resolve_band(35) == "low"
    assert resolve_band(50) == "mid"
    assert resolve_band(75) == "high"
    assert resolve_band(95) == "very_high"


def test_high_emotion_clear_risk_angry_not_fearful():
    contract = build_state_contract(
        {"emotion": 88, "cooperation": 40, "risk": 78, "clarity": 62},
        {"rapport": "neutral", "pressure": "high"},
    )
    assert contract["primary_affect"] == "angry"
    assert contract["delivery"] == "angry"


def test_high_emotion_high_risk_low_clarity_fearful():
    contract = build_state_contract(
        {"emotion": 85, "cooperation": 35, "risk": 82, "clarity": 18},
        {"rapport": "defensive", "pressure": "high"},
    )
    assert contract["primary_affect"] == "fearful"
    assert contract["delivery"] == "fearful"
    assert contract["sentence_style"] in {"broken", "fragmented"}


def test_soft_contact_reduces_risk_and_raises_clarity_delta():
    deltas = compute_trigger_axis_deltas("你先别急，慢慢说，几点发生的？")
    assert deltas["emotion"] < 0
    assert deltas["risk"] < 0
    assert deltas["clarity"] > 0


def test_empathy_and_safety_reassurance_reduce_emotion_and_risk():
    deltas = compute_trigger_axis_deltas("我理解你着急，民警已经在路上，你先到安全位置，我们一步一步处理。")
    assert deltas["emotion"] <= -8
    assert deltas["risk"] <= -8
    assert deltas["cooperation"] > 0


def test_hard_pressure_raises_emotion_and_risk():
    deltas = compute_trigger_axis_deltas("快说，老实交代，是不是你干的")
    assert deltas["emotion"] > 0
    assert deltas["cooperation"] < 0
    assert deltas["risk"] > 0


def test_enrich_momentum_merges_axis_deltas():
    momentum = enrich_momentum_with_axis_deltas(
        {"emotion_delta": 2, "trust_delta": -1},
        "你必须老实交代",
        [],
    )
    assert momentum["risk_delta"] > 0
    assert momentum["clarity_delta"] < 0


def test_action_dict_deltas_are_applied():
    deltas = compute_trigger_axis_deltas(
        "",
        [{"label": "先安抚报警人并分离双方", "type": "procedure"}],
    )
    assert deltas["emotion"] < 0
    assert deltas["risk"] < 0
    assert deltas["cooperation"] > 0


def test_blend_four_axis_caps_step_from_current():
    current = {"emotion": 50, "cooperation": 40, "risk": 50, "clarity": 50}
    llm = {
        "updated_emotion": 95,
        "updated_cooperation": 10,
        "updated_risk": 90,
        "updated_clarity": 5,
    }
    momentum = {"emotion_delta": 10, "cooperation_delta": -10, "risk_delta": 10, "clarity_delta": -10}
    blended = blend_four_axis_state(current, llm, momentum)
    assert blended["emotion"] <= current["emotion"] + 12
    assert blended["cooperation"] >= current["cooperation"] - 12


def test_blend_four_axis_guarantees_deescalation_on_effective_comfort():
    current = {"emotion": 86, "cooperation": 35, "risk": 76, "clarity": 42}
    llm = {
        "updated_emotion": 88,
        "updated_cooperation": 34,
        "updated_risk": 78,
        "updated_clarity": 42,
    }
    momentum = enrich_momentum_with_axis_deltas(
        {
            "strategy_tags": ["soft_contact", "empathy_validation", "safety_reassurance"],
            "rapport": "warming",
            "pressure": "low",
        },
        "你先别急，我理解你着急，民警已经在路上，你先到安全位置，我们一步一步处理。",
        [],
    )
    blended = blend_four_axis_state(current, llm, momentum)
    assert blended["emotion"] <= current["emotion"] - 8
    assert blended["risk"] <= current["risk"] - 7
    assert blended["cooperation"] >= current["cooperation"] + 5


def test_low_cooperation_low_emotion_cold_guarded():
    contract = build_state_contract(
        {"emotion": 25, "cooperation": 18, "risk": 45, "clarity": 55},
        {},
    )
    assert contract["primary_affect"] == "cold"
    assert contract["disclosure_level"] <= 0.25


def test_contract_block_contains_must_avoid_for_very_high_emotion():
    contract = build_state_contract({"emotion": 92, "cooperation": 30, "risk": 40, "clarity": 70}, {})
    assert contract["primary_affect"] == "angry"
    assert "完整时间线" in contract.get("must_avoid", [])


def test_in_band_disclosure_interpolates_between_tiers():
    low_coop = build_state_contract({"emotion": 50, "cooperation": 22, "risk": 50, "clarity": 50}, {})
    high_coop = build_state_contract({"emotion": 50, "cooperation": 58, "risk": 50, "clarity": 50}, {})
    assert low_coop["disclosure_level"] < high_coop["disclosure_level"]
    assert low_coop["max_chars"] < high_coop["max_chars"]


def test_strictness_rises_when_disclosure_low():
    contract = build_state_contract({"emotion": 90, "cooperation": 15, "risk": 80, "clarity": 40}, {})
    assert contract.get("strictness") == "strict"


def test_persona_archetype_modifies_axis_deltas():
    neutral = enrich_momentum_with_axis_deltas(
        {
            "strategy_tags": ["empathy_validation", "safety_reassurance"],
            "rapport": "warming",
            "pressure": "low",
        },
        "我理解你害怕，先到安全位置，我们会保护你，慢慢说。",
        [],
    )
    trauma = enrich_momentum_with_axis_deltas(
        {
            "strategy_tags": ["empathy_validation", "safety_reassurance"],
            "rapport": "warming",
            "pressure": "low",
        },
        "我理解你害怕，先到安全位置，我们会保护你，慢慢说。",
        [],
        {"behavior_archetype": "创伤受害型"},
    )
    crisis_pressure = enrich_momentum_with_axis_deltas(
        {"strategy_tags": ["pressure"], "rapport": "defensive", "pressure": "high"},
        "快说，老实交代，别废话。",
        [],
        {"behavior_archetype": "精神危机型"},
    )

    assert trauma["persona_axis_modifiers"]["emotion"] < neutral["persona_axis_modifiers"]["emotion"]
    assert trauma["persona_axis_modifiers"]["risk"] < neutral["persona_axis_modifiers"]["risk"]
    assert crisis_pressure["risk_delta"] > 0
    assert crisis_pressure["clarity_delta"] < 0


def test_defensive_persona_caps_disclosure_even_when_warming():
    neutral = build_state_contract(
        {"emotion": 42, "cooperation": 86, "risk": 30, "clarity": 82},
        {"rapport": "warming", "pressure": "low"},
    )
    calculating = build_state_contract(
        {"emotion": 42, "cooperation": 86, "risk": 30, "clarity": 82},
        {"rapport": "warming", "pressure": "low"},
        {"behavior_archetype": "利益算计型"},
    )

    assert calculating["disclosure_level"] < neutral["disclosure_level"]
    assert calculating["disclosure_level"] <= 0.58
    assert "核心不利事实" in calculating["role_boundary_hint"]
