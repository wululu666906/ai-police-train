"""Opening preset scores for role compact V1 (no persona_engine dependency)."""

from __future__ import annotations

from typing import Any

OPENING_PRESET_SCORES: dict[str, dict[str, int]] = {
    "calm_cooperative": {
        "init_emotion": 42,
        "init_trust": 58,
        "init_risk": 24,
        "init_expression_clarity": 78,
    },
    "cautious_guarded": {
        "init_emotion": 54,
        "init_trust": 28,
        "init_risk": 34,
        "init_expression_clarity": 74,
    },
    "emotional_venting": {
        "init_emotion": 76,
        "init_trust": 38,
        "init_risk": 56,
        "init_expression_clarity": 54,
    },
    "defensive_evasive": {
        "init_emotion": 62,
        "init_trust": 20,
        "init_risk": 44,
        "init_expression_clarity": 70,
    },
    "confrontational": {
        "init_emotion": 78,
        "init_trust": 14,
        "init_risk": 72,
        "init_expression_clarity": 68,
    },
    "intoxicated_chaotic": {
        "init_emotion": 86,
        "init_trust": 10,
        "init_risk": 88,
        "init_expression_clarity": 22,
    },
    "withdrawn": {
        "init_emotion": 80,
        "init_trust": 18,
        "init_risk": 82,
        "init_expression_clarity": 28,
    },
}

ARCHETYPE_DEFAULT_PRESET: dict[str, str] = {
    "求助配合型": "calm_cooperative",
    "委屈宣泄型": "emotional_venting",
    "谨慎回避型": "cautious_guarded",
    "防御切责型": "defensive_evasive",
    "强硬对抗型": "confrontational",
    "醉酒失控型": "intoxicated_chaotic",
    "绝望封闭型": "withdrawn",
    "围观起哄型": "confrontational",
    "创伤受害型": "emotional_venting",
    "精神危机型": "intoxicated_chaotic",
    "利益算计型": "defensive_evasive",
    "权威敏感型": "confrontational",
    "沉默恐惧型": "withdrawn",
    "过度依赖型": "emotional_venting",
}


def _score(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return default
    try:
        score = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))


def infer_opening_preset(person: dict[str, Any] | None) -> str:
    person = person or {}
    explicit = str(person.get("opening_preset") or "").strip()
    if explicit in OPENING_PRESET_SCORES:
        return explicit

    archetype = str(person.get("behavior_archetype") or "").strip()
    if archetype in ARCHETYPE_DEFAULT_PRESET:
        return ARCHETYPE_DEFAULT_PRESET[archetype]

    emotion = _score(person.get("init_emotion"), 50)
    trust = _score(person.get("init_trust"), 30)
    risk = _score(person.get("init_risk"), 50)
    clarity = _score(person.get("init_expression_clarity") or person.get("init_clarity"), 52)

    if risk >= 80 and clarity <= 30:
        return "intoxicated_chaotic"
    if emotion >= 78 and trust <= 20:
        return "confrontational"
    if emotion >= 72 and trust >= 35:
        return "emotional_venting"
    if trust <= 22 and emotion >= 55:
        return "defensive_evasive"
    if emotion >= 78 and trust <= 25:
        return "withdrawn"
    if trust <= 32:
        return "cautious_guarded"
    return "calm_cooperative"


def apply_opening_preset(person: dict[str, Any], preset: str | None = None) -> dict[str, int]:
    key = str(preset or "").strip() or infer_opening_preset(person)
    scores = OPENING_PRESET_SCORES.get(key) or OPENING_PRESET_SCORES["calm_cooperative"]
    return dict(scores)
