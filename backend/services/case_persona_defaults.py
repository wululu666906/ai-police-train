from __future__ import annotations

from typing import Any


def normalize_compact_persona_fields(persona: dict[str, Any]) -> dict[str, Any]:
    value = dict(persona or {})
    relationship_pressure = []
    relationship_pressure.extend(f"护着{item}" for item in value.get("protected_targets") or [])
    relationship_pressure.extend(f"忌惮{item}" for item in value.get("feared_people") or [])
    relationship_pressure.extend(f"和{item}有旧怨或关系压力" for item in value.get("conflict_targets") or [])
    relationship_pressure.extend(str(item) for item in value.get("feared_consequences") or [])
    return {
        "personality": str(value.get("personality") or value.get("traits") or "普通、符合案件材料"),
        "speaking_style": str(value.get("speaking_style") or "自然口语"),
        "interaction_style": str(value.get("interaction_style") or "配合型"),
        "relationship_pressure": relationship_pressure,
    }


def get_behavior_archetype_defaults(archetype: str = "", **kwargs) -> dict[str, Any]:
    defaults = {
        "防备型": {"init_trust": 25, "init_emotion": 60, "init_risk": 55},
        "激动型": {"init_trust": 35, "init_emotion": 75, "init_risk": 65},
        "配合型": {"init_trust": 65, "init_emotion": 40, "init_risk": 30},
    }
    return dict(defaults.get(str(archetype or ""), {"init_trust": 40, "init_emotion": 50, "init_risk": 50}))


def infer_persona_template(person: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
    value = dict(person or {})
    role = str(value.get("role") or value.get("role_type") or "相关人员")
    archetype = "防备型" if any(token in role for token in ("嫌疑", "违法", "被告")) else "配合型"
    return {"behavior_archetype": archetype, **get_behavior_archetype_defaults(archetype)}
