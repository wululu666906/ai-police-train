from __future__ import annotations

import json
import re
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


def build_recommended_question_items(*, stored_items=None, custom_prompts=None, missing_requirements=None, **kwargs) -> list[dict[str, Any]]:
    coach_re = re.compile(
        r"^(请立即|请先|请务必|请尽快|请具体说明|请核实|请确认|为推进|建议你|学员应|需要你|应当|必须先)"
    )

    def _ok(text: str) -> bool:
        value = str(text or "").strip()
        return bool(value) and not coach_re.search(value) and "…" not in value and "..." not in value

    items = [
        {
            "text": str(item.get("text") or "").strip(),
            "category": str(item.get("category") or "追问"),
            "kind": str(item.get("kind") or ("plot_advance" if "推进" in str(item.get("category") or "") else "hint")),
            "priority": str(item.get("priority") or "medium"),
            "target_role_name": item.get("target_role_name"),
            "related_point_id": item.get("related_point_id"),
        }
        for item in (stored_items or [])
        if isinstance(item, dict) and _ok(str(item.get("text") or ""))
    ]
    if items:
        return items[:6]
    items = []
    for item in (custom_prompts or []):
        if not isinstance(item, str) or not item.strip():
            continue
        normalized = _as_question_item(item.strip(), "快速发言", kind="hint")
        if normalized and _ok(normalized["text"]):
            items.append(normalized)
    for item in (missing_requirements or [])[:3]:
        normalized = _as_question_item(str(item), "推进剧情", kind="plot_advance")
        if normalized and _ok(normalized["text"]):
            items.append(normalized)
    return items[:6]


def _as_question_item(text: Any, category: str = "开场核实", *, kind: str = "hint") -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    # 去掉教练口吻前缀，改写成可说出口的口语
    cleaned = re.sub(
        r"^(请立即|请先|请务必|请尽快|请具体说明|请核实|请确认|为推进处置[，,]?请说明|为推进|建议你|学员应|需要你|应当|必须先)",
        "",
        cleaned,
    ).strip(" ：:，,。.")
    if not cleaned:
        return None
    if cleaned.endswith(("？", "?")):
        speakable = cleaned
    elif kind == "plot_advance":
        speakable = f"先说清楚：{cleaned[:18]}？"
    else:
        speakable = f"{cleaned[:18]}是怎么回事？"
    if len(speakable) > 56:
        speakable = speakable[:55].rstrip("，。；、 ") + "？"
    if speakable.startswith(("请立即", "请具体说明", "为推进")) or "…" in speakable or "..." in speakable:
        return None
    return {"text": speakable, "category": category, "kind": kind}


def _stage_prompts_from_scene(scene, case, *, current_stage: str = "") -> list[dict[str, Any]]:
    """按当前阶段取方向种子；仅作会话只读兜底，不得跨阶段回退到开场模板冒充新题。"""
    items: list[dict[str, Any]] = []
    stages = _safe_json(getattr(scene, "stages", None), []) if scene else []
    structured = _safe_json(getattr(case, "structured_data", None), {}) if case else {}
    scripts = [
        item for item in (structured.get("training_scripts") or structured.get("scene_scripts") or [])
        if isinstance(item, dict)
    ]
    scene_name = str(getattr(scene, "name", "") or "")
    matched = next((item for item in scripts if str(item.get("scene_name") or "") == scene_name), scripts[0] if scripts else {})
    script_stages = matched.get("stages") if isinstance(matched.get("stages"), list) else []
    stage_name = str(current_stage or "").strip()
    scene_stage = next(
        (item for item in stages if isinstance(item, dict) and str(item.get("stage_name") or "").strip() == stage_name),
        None,
    )
    script_stage = next(
        (item for item in script_stages if isinstance(item, dict) and str(item.get("stage_name") or "").strip() == stage_name),
        None,
    )
    if scene_stage is None and script_stage is None:
        # 无当前阶段匹配时：仅开场（尚无阶段名）可用首阶段；中后期返回空。
        if stage_name:
            return []
        scene_stage = next((item for item in stages if isinstance(item, dict)), {})
        script_stage = next((item for item in script_stages if isinstance(item, dict)), {})
    scene_stage = scene_stage or {}
    script_stage = script_stage or {}
    hint_sources = [
        *(scene_stage.get("recommended_prompts") or []),
        *(script_stage.get("recommended_prompts") or []),
    ]
    plot_sources = [
        *(scene_stage.get("learner_actions") or []),
        *(script_stage.get("learner_actions") or []),
        *(scene_stage.get("role_pressure_points") or []),
        *(script_stage.get("role_pressure_points") or []),
    ]
    seen: set[str] = set()
    for text in hint_sources:
        item = _as_question_item(text, "快速发言", kind="hint")
        if not item or item["text"] in seen:
            continue
        seen.add(item["text"])
        items.append(item)
        if len(items) >= 2:
            break
    for text in plot_sources:
        item = _as_question_item(text, "推进剧情", kind="plot_advance")
        if not item or item["text"] in seen:
            continue
        seen.add(item["text"])
        items.append(item)
        if sum(1 for row in items if row.get("kind") == "plot_advance") >= 2:
            break
    return items[:4]


def _opening_prompts_from_scene(scene, case) -> list[dict[str, Any]]:
    return _stage_prompts_from_scene(scene, case, current_stage="")


def build_intake_sequence_feedback(*args, **kwargs) -> dict[str, Any]:
    return {}


def merge_sequence_feedback(base: dict, sequence: dict) -> dict:
    return {**base, **sequence}


def resolve_role_initial_state(role=None, case=None, scene=None, scene_role_link=None) -> dict[str, int]:
    stored = {}
    if scene_role_link is not None and getattr(scene_role_link, "initial_state", None):
        try:
            stored = json.loads(scene_role_link.initial_state)
        except (TypeError, ValueError):
            stored = {}
    return {
        "emotion": int(stored.get("emotion", getattr(role, "init_emotion", None) or 50)),
        "cooperation": int(stored.get("cooperation", getattr(role, "init_trust", None) or 35)),
        "risk": int(stored.get("risk", getattr(role, "init_risk", None) or 50)),
        "clarity": int(stored.get("clarity", getattr(role, "init_expression_clarity", None) or 50)),
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
    from services.avatar_service import assign_avatar, get_avatar_url

    runtime_state = runtime_state or {}
    snapshots = runtime_state.get("role_state_snapshots") or {}
    deltas = runtime_state.get("role_state_deltas") or {}
    labels = runtime_state.get("role_state_labels") or {}
    active_role_ids = {str(item) for item in runtime_state.get("last_active_role_ids") or []}
    structured = _safe_json(getattr(case, "structured_data", None), {}) if case else {}
    persons_by_name = {
        repair_text(item.get("name") or ""): item
        for item in (structured.get("persons") or [])
        if isinstance(item, dict) and repair_text(item.get("name") or "")
    }
    links = db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).all()
    result = []
    for link in links:
        role = db.query(models.Role).filter(models.Role.id == link.role_id).first()
        if not role:
            continue
        state = snapshots.get(str(role.id)) or resolve_role_initial_state(role, case, scene, link)
        delta = deltas.get(str(role.id)) or {}
        participation = {}
        if getattr(link, "participation_config", None):
            try:
                participation = json.loads(link.participation_config)
            except (TypeError, ValueError):
                participation = {}
        present = participation.get("present") is not False
        role_name = repair_text(role.name or "")
        persona_meta = _safe_json(getattr(role, "persona_meta", None), {})
        structured_person = persons_by_name.get(role_name, {})
        age = persona_meta.get("age")
        if age is None:
            age = structured_person.get("age")
        try:
            age = int(age) if age is not None and str(age).strip() != "" else None
        except (TypeError, ValueError):
            age = None
        gender = (
            persona_meta.get("gender")
            or structured_person.get("gender")
            or persona_meta.get("sex")
            or structured_person.get("sex")
        )
        avatar_id = assign_avatar(age, gender, role_name or f"role-{role.id}")
        avatar_url = get_avatar_url(avatar_id)
        result.append({
            "id": role.id,
            "name": role_name,
            "role_type": role.role_type or "",
            "speakable": present,
            "present": present,
            "interaction_purpose": str(participation.get("interaction_purpose") or ""),
            "can_initiate": bool(participation.get("can_initiate", link.is_primary)),
            "can_interrupt": bool(participation.get("can_interrupt", False)),
            "emotion": state.get("emotion"),
            "cooperation": state.get("cooperation"),
            "risk": state.get("risk"),
            "clarity": state.get("clarity"),
            "emotion_delta": int(delta.get("emotion") or 0),
            "cooperation_delta": int(delta.get("cooperation") or 0),
            "risk_delta": int(delta.get("risk") or 0),
            "clarity_delta": int(delta.get("clarity") or 0),
            "state_label": labels.get(str(role.id)) or runtime_state.get("role_state_label"),
            "is_active": str(role.id) in active_role_ids,
            "avatar_id": avatar_id,
            "avatar_url": avatar_url,
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


def _safe_json(value: Any, default: Any):
    if isinstance(value, type(default)):
        return value
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(default)) else default
    except (TypeError, ValueError):
        return default


def _resolve_opening_preset_turns(scene, case, role) -> list[dict[str, Any]]:
    config = _safe_json(getattr(scene, "opening_config", None), {}) if scene else {}
    turns = []
    for item in config.get("preset_turns") or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        turns.append({
            "speaker_role_id": item.get("speaker_role_id"),
            "speaker_name": str(item.get("speaker_name") or "").strip(),
            "content": content[:500],
        })
    if turns:
        return turns[:3]
    structured = _safe_json(getattr(case, "structured_data", None), {}) if case else {}
    scripts = [
        item for item in (structured.get("scene_scripts") or structured.get("training_scripts") or [])
        if isinstance(item, dict)
    ]
    scene_name = str(getattr(scene, "name", "") or "")
    matched = next((item for item in scripts if str(item.get("scene_name") or "") == scene_name), scripts[0] if scripts else {})
    for item in matched.get("opening_lines") or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        turns.append({
            "speaker_role_id": None,
            "speaker_name": str(item.get("speaker_name") or "").strip(),
            "content": content[:500],
        })
    return turns[:3]


def _compose_plot_opening_turns(scene, case, role) -> list[dict[str, Any]]:
    role_name = repair_text(role.name) if role else "现场人员"
    structured = _safe_json(getattr(case, "structured_data", None), {}) if case else {}
    scripts = [item for item in (structured.get("scene_scripts") or structured.get("training_scripts") or []) if isinstance(item, dict)]
    scene_name = str(getattr(scene, "name", "") or "")
    matched = next((item for item in scripts if str(item.get("scene_name") or "") == scene_name), scripts[0] if scripts else {})
    plot = str(matched.get("plot_arc") or getattr(scene, "description", "") or "").strip()
    stages = matched.get("stages") if isinstance(matched.get("stages"), list) else _safe_json(getattr(scene, "stages", None), [])
    first_stage = next((item for item in stages if isinstance(item, dict)), {})
    pressure = ""
    points = first_stage.get("role_pressure_points") or []
    if points:
        pressure = str(points[0]).strip()
    impression = str(getattr(scene, "first_impression", "") or "").strip()
    kind = infer_session_scene_kind(scene, None)
    if kind == "intake":
        body = pressure or plot.split("。")[0] or impression[:80]
        content = f"警察同志，我是{role_name}。{body}。你们得先听我说完怎么回事。"
    else:
        body = pressure or impression[:80] or plot.split("。")[0]
        content = f"我是{role_name}。{body}。你们先看现场，我把刚才发生的事情说清楚。"
    return [{
        "speaker_role_id": role.id if role else None,
        "speaker_name": role_name,
        "content": repair_text(content)[:500],
    }]


def ensure_opening_turn(db: Session, session, scene, case, role) -> bool:
    state = load_runtime_state(session.revealed_info)
    if state.get("opening_delivered"):
        return True
    turns = _resolve_opening_preset_turns(scene, case, role)
    if not turns:
        return False
    message_ids = []
    for item in turns:
        speaker_name = repair_text(item.get("speaker_name") or (role.name if role else "现场人员"))
        speaker_id = item.get("speaker_role_id") or (role.id if role else None)
        message = models.Message(
            session_id=session.id,
            role="assistant",
            content=repair_text(item.get("content") or ""),
            speaker_role_id=speaker_id,
            speaker_name=speaker_name,
        )
        db.add(message)
        db.flush()
        message_ids.append(message.id)
    prompts = list(state.get("recommended_question_items") or []) or _opening_prompts_from_scene(scene, case)
    state.update({
        "opening_delivered": True,
        "opening_message_ids": message_ids,
        "recommended_question_items": prompts,
    })
    session.revealed_info = dump_runtime_state(state)
    return True
