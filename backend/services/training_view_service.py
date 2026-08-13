from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

import models
from services.text_repair import repair_text
from services.training_runtime_service import dump_runtime_state, load_runtime_state


INTERNAL_MARKERS = ("[system]", "[SYSTEM]", "SYSTEM_PROMPT", "你是一个AI", "你是AI助手")


def filter_internal_prompt_messages(messages: list[models.Message]) -> list[models.Message]:
    return [message for message in messages if not any(marker in (message.content or "") for marker in INTERNAL_MARKERS)]


def serialize_message_history(messages: list[models.Message]) -> list[dict[str, Any]]:
    return [{"role": item.role, "content": repair_text(item.content or "")} for item in (messages or [])[-20:]]


def filter_stale_missing_requirements_for_history(missing: list[str], **kwargs) -> list[str]:
    return list(missing or [])


def build_recommended_question_items(*, custom_prompts=None, missing_requirements=None, **kwargs) -> list[dict[str, Any]]:
    items = [
        {"text": item.strip(), "category": "推荐", "priority": "medium"}
        for item in (custom_prompts or [])
        if isinstance(item, str) and item.strip()
    ]
    items.extend(
        {"text": f"请问{item}？", "category": "缺失项", "priority": "high"}
        for item in (missing_requirements or [])[:3]
    )
    return items[:5]


def build_intake_sequence_feedback(*args, **kwargs) -> dict[str, Any]:
    return {}


def merge_sequence_feedback(base: dict, sequence: dict) -> dict:
    return {**base, **sequence}


def resolve_role_initial_state(role=None, case=None, scene=None, scene_role_link=None) -> dict[str, int]:
    return {
        "emotion": int(getattr(role, "init_emotion", None) or 50),
        "cooperation": int(getattr(role, "init_trust", None) or 35),
        "risk": int(getattr(role, "init_risk", None) or 50),
        "clarity": int(getattr(role, "init_expression_clarity", None) or 50),
    }


def ensure_scene_role_initial_state(scene_role_link, role, case, scene, *, source: str = "platform") -> dict[str, int]:
    state = resolve_role_initial_state(role, case, scene, scene_role_link)
    if scene_role_link is not None:
        scene_role_link.initial_state = json.dumps({**state, "source": source}, ensure_ascii=False)
    return state


def backfill_role_initial_states(db: Session) -> None:
    links = db.query(models.SceneRole).all()
    for link in links:
        if link.initial_state and link.initial_state not in ("{}", "null"):
            continue
        role = db.query(models.Role).filter(models.Role.id == link.role_id).first()
        scene = db.query(models.Scene).filter(models.Scene.id == link.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
        ensure_scene_role_initial_state(link, role, case, scene, source="backfill")
    db.commit()


def serialize_scene_roles(db: Session, scene, case, *, runtime_state=None) -> list[dict[str, Any]]:
    if not scene:
        return []
    runtime_state = runtime_state or {}
    snapshots = runtime_state.get("role_state_snapshots") or {}
    links = db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).all()
    result = []
    for link in links:
        role = db.query(models.Role).filter(models.Role.id == link.role_id).first()
        if not role:
            continue
        state = snapshots.get(str(role.id)) or resolve_role_initial_state(role, case, scene, link)
        result.append({
            "id": role.id,
            "name": repair_text(role.name or ""),
            "role_type": role.role_type or "",
            "speakable": True,
            "emotion": state.get("emotion"),
            "cooperation": state.get("cooperation"),
            "risk": state.get("risk"),
            "clarity": state.get("clarity"),
            "is_active": False,
        })
    return result


def infer_session_scene_kind(scene, session) -> str:
    text = f"{getattr(scene, 'name', '')} {getattr(scene, 'stages', '')}"
    return "onsite" if any(token in text for token in ("现场", "出警", "处置")) else "intake"


def resolve_dialogue_mode(scene, session) -> str:
    return "multi" if scene and len(getattr(scene, "roles", []) or []) > 1 else "single"


def redact_dispatch_brief_for_student(scene, session) -> str | None:
    return getattr(scene, "dispatch_brief", None) if scene else None


def redact_first_impression_for_student(scene, session) -> str | None:
    return getattr(scene, "first_impression", None) if scene else None


def ensure_opening_turn(db: Session, session, scene, case, role) -> None:
    state = load_runtime_state(session.revealed_info)
    if state.get("opening_delivered"):
        return
    role_name = repair_text(role.name) if role else "报警人"
    content = "喂，110吗？我要报警！" if infer_session_scene_kind(scene, session) == "intake" else "警察同志，你们来了。"
    message = models.Message(session_id=session.id, role="assistant", content=content, speaker_role_id=role.id if role else None, speaker_name=role_name)
    db.add(message)
    db.flush()
    state.update({"opening_delivered": True, "opening_message_ids": [message.id]})
    session.revealed_info = dump_runtime_state(state)
