"""Low-weight persona and deterministic state dynamics for realistic police contact."""
from __future__ import annotations

from typing import Any


_DEESCALATION = ("别着急", "冷静", "理解", "放心", "安全", "保护", "救护", "已经联系", "下一步", "会处理", "慢慢说")
_ESCALATION = ("闭嘴", "少废话", "老实点", "就是你", "肯定是你", "别装", "不说就", "马上承认")


def _clamp(value: Any, fallback: int) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return fallback


def blend_state_delta(
    snapshot: dict[str, int],
    model_delta: dict[str, Any],
    user_text: str,
    persona_profile: dict[str, Any],
) -> dict[str, int]:
    """Personality shapes sensitivity, but current interaction and recovery dominate."""
    soul = persona_profile.get("soul_profile") if isinstance(persona_profile.get("soul_profile"), dict) else {}
    emotion = _clamp(snapshot.get("emotion"), 50)
    cooperation = _clamp(snapshot.get("cooperation"), 50)
    emotion_base = _clamp(soul.get("arousal_baseline") or persona_profile.get("init_emotion"), 45)
    cooperation_base = _clamp(soul.get("cooperation_baseline") or persona_profile.get("init_cooperation"), 58)
    dynamic_weight = max(0.1, min(0.35, float(soul.get("dynamic_weight") or 0.22)))

    # Every turn naturally moves a person slightly back toward baseline.
    emotion_recovery = max(-5, min(5, round((emotion_base - emotion) * 0.18)))
    cooperation_recovery = max(-3, min(3, round((cooperation_base - cooperation) * 0.12)))
    text = str(user_text or "")
    supportive = any(token in text for token in _DEESCALATION)
    provocative = any(token in text for token in _ESCALATION)

    policy = {"emotion": emotion_recovery, "cooperation": cooperation_recovery, "risk": -1, "clarity": 1}
    if supportive:
        policy.update({"emotion": emotion_recovery - 7, "cooperation": cooperation_recovery + 7, "risk": -5, "clarity": 4})
    elif provocative:
        sensitivity = _clamp(soul.get("threat_sensitivity"), 50)
        scale = 1.0 + max(0, sensitivity - 50) / 100
        policy.update({"emotion": round(8 * scale), "cooperation": round(-7 * scale), "risk": round(5 * scale), "clarity": -3})

    result = {}
    for key in ("emotion", "cooperation", "risk", "clarity"):
        try:
            learned = int(model_delta.get(key) or 0)
        except (TypeError, ValueError):
            learned = 0
        # The model adds nuance but cannot dominate the state machine.
        result[key] = max(-15, min(15, round(policy[key] * (1 - dynamic_weight) + learned * dynamic_weight)))
    return result
