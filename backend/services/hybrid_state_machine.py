"""Deterministic hybrid state derived from four continuous axes.

The four axes remain the continuous state.  A discrete interaction state is
derived with hysteresis and combined with the training phase, observable
events and objective coverage.  Models may describe reactions but cannot
directly choose the discrete state.
"""

from __future__ import annotations

from typing import Any


def _score(value: Any, fallback: int = 50) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return fallback


def _action_text(actions: list[Any] | None) -> str:
    parts = []
    for item in actions or []:
        if isinstance(item, dict):
            parts.extend(str(item.get(key) or "") for key in ("id", "type", "name", "label", "action"))
        else:
            parts.append(str(item or ""))
    return " ".join(parts)


def derive_hybrid_state(
    axes: dict[str, Any],
    *,
    phase: str,
    recognized_actions: list[Any] | None = None,
    missing_objectives: list[str] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    emotion = _score(axes.get("emotion"))
    cooperation = _score(axes.get("cooperation"), 30)
    risk = _score(axes.get("risk"))
    clarity = _score(axes.get("clarity"))
    previous = previous if isinstance(previous, dict) else {}
    previous_mode = str(previous.get("interaction_mode") or "")

    # Five-point release margins avoid flickering around boundaries.
    if risk >= 75 or (previous_mode == "crisis" and risk >= 70):
        mode = "crisis"
    elif clarity <= 30 or (previous_mode == "confused" and clarity <= 35):
        mode = "confused"
    elif cooperation <= 30 or (previous_mode == "resistant" and cooperation <= 35):
        mode = "resistant"
    elif emotion >= 75 or (previous_mode == "agitated" and emotion >= 70):
        mode = "agitated"
    elif cooperation >= 65 and risk <= 45 and clarity >= 45:
        mode = "engaged"
    else:
        mode = "guarded"

    action_text = _action_text(recognized_actions)
    events = []
    for key, event in (
        ("证据", "evidence_presented"),
        ("监控", "evidence_presented"),
        ("隔离", "risk_control"),
        ("救护", "medical_support"),
        ("告知", "procedure_explained"),
        ("矛盾", "contradiction_challenged"),
    ):
        if key in action_text and event not in events:
            events.append(event)

    missing = [str(item).strip() for item in (missing_objectives or []) if str(item).strip()]
    transition_allowed = mode != "crisis" and not missing
    blockers = []
    if mode == "crisis":
        blockers.append("风险尚未受控")
    if missing:
        blockers.append("仍有训练目标未完成")

    return {
        "schema_version": 1,
        "phase": str(phase or "训练中"),
        "interaction_mode": mode,
        "axes": {
            "emotion": emotion,
            "cooperation": cooperation,
            "risk": risk,
            "clarity": clarity,
        },
        "events": events,
        "missing_objectives": missing,
        "transition_allowed": transition_allowed,
        "transition_blockers": blockers,
    }
