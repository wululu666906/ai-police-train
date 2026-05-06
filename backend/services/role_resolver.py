import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

import models


NON_SPEAKABLE_STATUS_KEYWORDS = (
    "死亡",
    "死者",
    "重伤",
    "昏迷",
    "无意识",
    "无法接受审问",
    "无法接受询问",
    "无法问询",
)

WITNESS_HINTS = ("报警", "报案", "证人", "目击", "家属", "邻居", "朋友", "闺蜜", "同事")
SUSPECT_HINTS = ("嫌疑", "凶手", "加害", "作案")


def _text(value: Optional[str]) -> str:
    return str(value or "").strip()


def is_role_speakable(role: Optional[models.Role]) -> bool:
    if not role:
        return False
    status = _text(role.status)
    return not any(keyword in status for keyword in NON_SPEAKABLE_STATUS_KEYWORDS)


def _load_person_meta(case: Optional[models.Case]) -> Dict[str, dict]:
    if not case or not case.structured_data:
        return {}
    try:
        structured = json.loads(case.structured_data)
        persons = structured.get("persons") or []
    except Exception:
        return {}

    return {str(person.get("name", "")).strip(): person for person in persons if person.get("name")}


def _scene_text(scene: models.Scene) -> str:
    return " ".join(
        part
        for part in [
            _text(scene.name),
            _text(scene.description),
            _text(scene.dispatch_brief),
            _text(scene.first_impression),
        ]
        if part
    )


def _match_rank(scene_name: str, scene_text: str, role: models.Role, person_meta: dict) -> Tuple[int, int]:
    role_name = _text(role.name)
    person_role = _text(person_meta.get("role"))
    person_role_type = _text(person_meta.get("role_type"))

    explicit_name = bool(role_name and role_name in scene_text)
    witness_like = any(hint in person_role for hint in WITNESS_HINTS)
    suspect_like = any(hint in person_role for hint in SUSPECT_HINTS) or any(
        hint in person_role_type for hint in SUSPECT_HINTS
    )

    scene_rank = 50
    role_rank = 50

    if "接警" in scene_name:
        scene_rank = 10
        if "报警" in person_role or "报案" in person_role:
            role_rank = 0
        elif witness_like:
            role_rank = 10
        elif explicit_name:
            role_rank = 20
        elif suspect_like:
            role_rank = 80
        else:
            role_rank = 30
    elif any(keyword in scene_name for keyword in ("现场", "勘查", "调查")):
        scene_rank = 30
        if explicit_name and witness_like:
            role_rank = 0
        elif explicit_name:
            role_rank = 5
        elif witness_like:
            role_rank = 10
        elif suspect_like:
            role_rank = 30
        else:
            role_rank = 20
    elif any(keyword in scene_name for keyword in ("审讯", "讯问", "嫌疑人", "询问")):
        scene_rank = 20
        if explicit_name and suspect_like:
            role_rank = 0
        elif explicit_name:
            role_rank = 5
        elif suspect_like:
            role_rank = 10
        elif witness_like:
            role_rank = 40
        else:
            role_rank = 30
    else:
        if explicit_name:
            role_rank = 0
        elif witness_like:
            role_rank = 10
        elif suspect_like:
            role_rank = 30

    return scene_rank, role_rank


def _build_virtual_role(name: str, personality: str, speaking_style: str = "紧张") -> models.Role:
    return models.Role(
        name=name,
        role_type="配合型",
        personality=personality,
        speaking_style=speaking_style,
        init_emotion=65,
        init_trust=45,
        status="正常",
        iq_level="中等",
        eq_level="中等",
        lying_ability="一般",
        weakness="容易紧张，表达可能不完整",
        knows_facts="[]",
        does_not_know="[]",
        hidden_truths="[]",
    )


def resolve_scene_role(
    db: Session,
    scene: Optional[models.Scene],
    case: Optional[models.Case] = None,
) -> Optional[models.Role]:
    if not scene:
        return None

    if case is None:
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()

    person_meta_map = _load_person_meta(case)
    scene_name = _text(scene.name)
    scene_text = _scene_text(scene)

    linked_rows = db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).all()
    link_meta: Dict[int, Dict[str, bool]] = {}
    for row in linked_rows:
        current = link_meta.setdefault(row.role_id, {"linked": True, "primary": False})
        current["primary"] = current["primary"] or bool(row.is_primary)

    candidates: List[models.Role] = []
    seen_role_ids = set()

    linked_role_ids = list(link_meta.keys())
    if linked_role_ids:
        linked_roles = db.query(models.Role).filter(models.Role.id.in_(linked_role_ids)).all()
        for role in linked_roles:
            candidates.append(role)
            seen_role_ids.add(role.id)

    legacy_roles = db.query(models.Role).filter(models.Role.scene_id == scene.id).all()
    for role in legacy_roles:
        if role.id not in seen_role_ids:
            candidates.append(role)
            seen_role_ids.add(role.id)

    case_roles = db.query(models.Role).filter(models.Role.case_id == scene.case_id).all()
    for role in case_roles:
        if role.id not in seen_role_ids:
            candidates.append(role)
            seen_role_ids.add(role.id)

    if not candidates:
        return None

    speakable_candidates = [role for role in candidates if is_role_speakable(role)]
    if speakable_candidates:
        candidates = speakable_candidates

    if "接警" in scene_name:
        witness_candidates = []
        for role in candidates:
            person_meta = person_meta_map.get(_text(role.name), {})
            person_role = _text(person_meta.get("role"))
            if "报警" in person_role or "报案" in person_role or any(hint in person_role for hint in WITNESS_HINTS):
                witness_candidates.append(role)
        if not witness_candidates:
            return _build_virtual_role("报警人", "情绪紧张，正在向警方描述自己看到或发现的情况")

    def sort_key(role: models.Role):
        meta = link_meta.get(role.id, {})
        person_meta = person_meta_map.get(_text(role.name), {})
        scene_rank, role_rank = _match_rank(scene_name, scene_text, role, person_meta)
        return (
            scene_rank,
            role_rank,
            0 if meta.get("primary") else 1,
            0 if meta.get("linked") else 1,
            role.id,
        )

    return sorted(candidates, key=sort_key)[0]
