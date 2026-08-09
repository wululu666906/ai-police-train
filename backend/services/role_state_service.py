"""Scene-scoped four-axis initialization for role and training runtime state."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

AXES = ("emotion", "cooperation", "risk", "clarity")
STATE_VERSION = "scene_role_state_v1"
ROLE_FIELDS = {
    "emotion": "init_emotion",
    "cooperation": "init_trust",
    "risk": "init_risk",
    "clarity": "init_expression_clarity",
}


def clamp_axis(value: Any, fallback: int = 50) -> int:
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        numeric = fallback
    return max(0, min(100, numeric))


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _case_payload(case: Any) -> dict[str, Any]:
    return _json_object(getattr(case, "structured_data", None))


def _case_person(case: Any, role: Any) -> dict[str, Any]:
    role_name = str(getattr(role, "name", "") or "").strip()
    for person in _case_payload(case).get("persons") or []:
        if isinstance(person, dict) and str(person.get("name") or "").strip() == role_name:
            return person
    return {}


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, str):
        rows = value.splitlines()
    else:
        rows = []
    return [str(item).strip() for item in rows if str(item or "").strip()]


def _state_basis(role: Any, case: Any, scene: Any) -> dict[str, Any]:
    person = _case_person(case, role)
    meta = _json_object(getattr(role, "persona_meta", None))
    return {
        "case": {
            "title": str(getattr(case, "title", "") or "").strip(),
            "type": str(getattr(case, "case_type", "") or "").strip(),
            "background": str(getattr(case, "background", "") or "").strip(),
        },
        "scene": {
            "name": str(getattr(scene, "name", "") or "").strip(),
            "description": str(getattr(scene, "description", "") or "").strip(),
            "first_impression": str(getattr(scene, "first_impression", "") or "").strip(),
            "stages": str(getattr(scene, "stages", "") or "").strip(),
        },
        "role": {
            "name": str(getattr(role, "name", "") or "").strip(),
            "role_type": str(getattr(role, "role_type", "") or "").strip(),
            "status": str(getattr(role, "status", "") or "").strip(),
            "person": person,
            "meta": meta,
        },
    }


def _basis_hash(basis: dict[str, Any]) -> str:
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _explicit_scores(person: dict[str, Any], meta: dict[str, Any]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for axis, field in ROLE_FIELDS.items():
        value = person.get(field)
        if value in (None, ""):
            value = meta.get(field)
        if value not in (None, ""):
            scores[axis] = clamp_axis(value)
    return scores


def _contains(corpus: str, *tokens: str) -> bool:
    return any(token and token in corpus for token in tokens)


def calculate_scene_role_state(role: Any, case: Any = None, scene: Any = None) -> dict[str, int]:
    """Derive a stable state only from the case, scene and role narrative."""
    basis = _state_basis(role, case, scene)
    person = basis["role"]["person"]
    meta = basis["role"]["meta"]
    role_type = basis["role"]["role_type"]
    status = basis["role"]["status"]
    corpus = json.dumps(basis, ensure_ascii=False)

    # Role identity supplies the anchor; scene and persona evidence adjust it.
    anchors = {
        "报警人": (70, 58, 48, 68), "求助人": (72, 60, 50, 65),
        "被害人": (76, 48, 58, 58), "受害人": (76, 48, 58, 58),
        "嫌疑人": (58, 24, 62, 66), "违法行为人": (62, 20, 70, 60),
        "证人": (48, 52, 34, 72), "目击者": (52, 50, 36, 70),
        "家属": (66, 46, 50, 62), "调解对象": (58, 42, 46, 64),
    }
    emotion, cooperation, risk, clarity = next(
        (values for name, values in anchors.items() if name in role_type),
        (54, 44, 42, 64),
    )
    explicit = _explicit_scores(person, meta)
    emotion = explicit.get("emotion", emotion)
    cooperation = explicit.get("cooperation", cooperation)
    risk = explicit.get("risk", risk)
    clarity = explicit.get("clarity", clarity)

    if _contains(corpus, "醉酒", "酒后", "意识混乱", "精神异常"):
        emotion += 18; cooperation -= 20; risk += 24; clarity -= 30
    if _contains(corpus, "持刀", "持械", "自伤", "自杀", "跳楼", "爆炸", "失控"):
        emotion += 16; cooperation -= 10; risk += 30; clarity -= 10
    if _contains(corpus, "受伤", "流血", "疼痛", "惊吓", "恐惧") or "受伤" in status:
        emotion += 14; risk += 12; clarity -= 8
    if _contains(corpus, "激动", "愤怒", "争吵", "冲突", "威胁"):
        emotion += 12; cooperation -= 8; risk += 14
    if _contains(corpus, "冷静", "主动配合", "如实陈述", "愿意配合"):
        emotion -= 12; cooperation += 20; risk -= 12; clarity += 10
    if _contains(corpus, "隐瞒", "否认", "逃避", "抗拒", "拒不配合"):
        cooperation -= 20; risk += 10; clarity -= 4
    if _contains(corpus, "记不清", "断片", "含糊", "语无伦次", "表达困难"):
        clarity -= 24
    if _contains(corpus, "目睹", "亲眼", "详细", "清楚记得", "陈述稳定"):
        clarity += 14

    return {
        "emotion": clamp_axis(emotion),
        "cooperation": clamp_axis(cooperation),
        "risk": clamp_axis(risk),
        "clarity": clamp_axis(clarity),
    }


def build_scene_role_state_payload(
    role: Any,
    case: Any = None,
    scene: Any = None,
    *,
    source: str = "narrative_rules",
) -> dict[str, Any]:
    basis = _state_basis(role, case, scene)
    person = basis["role"]["person"]
    meta = basis["role"]["meta"]
    effective_source = "model_profile_with_scene_rules" if len(_explicit_scores(person, meta)) == len(AXES) else source
    return {
        **calculate_scene_role_state(role, case, scene),
        "source": effective_source,
        "version": STATE_VERSION,
        "basis_hash": _basis_hash(basis),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "basis": {
            "case_type": basis["case"]["type"],
            "scene_name": basis["scene"]["name"],
            "role_type": basis["role"]["role_type"],
            "role_status": basis["role"]["status"],
        },
    }


def resolve_role_initial_state(
    role: Any,
    case: Any = None,
    scene: Any = None,
    scene_role: Any = None,
) -> dict[str, int]:
    if scene_role is not None:
        stored = _json_object(getattr(scene_role, "initial_state", None))
        if all(stored.get(axis) not in (None, "") for axis in AXES):
            return {axis: clamp_axis(stored[axis]) for axis in AXES}
    if role is None:
        return {"emotion": 50, "cooperation": 40, "risk": 40, "clarity": 60}
    return calculate_scene_role_state(role, case, scene)


def ensure_scene_role_initial_state(
    scene_role: Any,
    role: Any,
    case: Any,
    scene: Any,
    *,
    force: bool = False,
    source: str = "narrative_rules",
) -> dict[str, Any]:
    basis_hash = _basis_hash(_state_basis(role, case, scene))
    current = _json_object(getattr(scene_role, "initial_state", None))
    if not force and current.get("version") == STATE_VERSION and current.get("basis_hash") == basis_hash:
        return current
    payload = build_scene_role_state_payload(role, case, scene, source=source)
    scene_role.initial_state = json.dumps(payload, ensure_ascii=False)
    return payload


def resolve_scene_role_initial_states(db: Any, roles: list[Any], case: Any, scene: Any) -> dict[str, dict[str, int]]:
    import models

    links = {
        row.role_id: row
        for row in db.query(models.SceneRole).filter(models.SceneRole.scene_id == getattr(scene, "id", None)).all()
    }
    return {
        str(role.id): resolve_role_initial_state(role, case, scene, links.get(role.id))
        for role in roles
    }


def backfill_role_initial_states(db: Any) -> int:
    """Backfill scene-role states deterministically without external model calls."""
    import models

    changed = 0
    cases = {item.id: item for item in db.query(models.Case).all()}
    scenes = {item.id: item for item in db.query(models.Scene).all()}
    roles = {item.id: item for item in db.query(models.Role).all()}
    for link in db.query(models.SceneRole).all():
        role = roles.get(link.role_id)
        scene = scenes.get(link.scene_id)
        case = cases.get(getattr(scene, "case_id", None)) if scene else None
        if not role or not scene:
            continue
        before = str(getattr(link, "initial_state", "") or "")
        ensure_scene_role_initial_state(link, role, case, scene, source="legacy_narrative_backfill")
        if str(link.initial_state or "") != before:
            changed += 1
    if changed:
        db.commit()
    return changed
