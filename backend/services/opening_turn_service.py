"""Intake scene opening turn: caller speaks first before officer questions."""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from typing import Any

import models
from .llm_provider import create_roleplay_json_completion, extract_json_payload, extract_message_text
from .persona_engine import build_persona_profile
from .role_compact_service import person_to_role_compact_view
from .role_generation_context_service import compile_role_generation_context
from .role_resolver import is_role_speakable
from .stage_config_service import infer_scene_behavior_mode, infer_scene_kind
from .prompts.case_pipeline import build_opening_system_prompt
from .dialogue_sanitize_service import (
    ROLE_REPLY_MAX_CHARS,
    filter_internal_prompt_messages,
    limit_role_reply_turns_with_remainders,
    sanitize_utterances,
)
from .training_runtime_service import dump_runtime_state, load_runtime_state
from .role_resolver import resolve_scene_roles

INTAKE_MINIMAL_DISPATCH = "110 有新报警来电，等待接听。"
_OPENING_LOCKS: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)
logger = logging.getLogger(__name__)

CALLER_OPEN_ROLE_HINTS = ("报警", "报案", "证人", "被害人", "受害人")

def _text(value: Any) -> str:
    return str(value or "").strip()


def _opening_config(scene: models.Scene | None) -> dict[str, Any]:
    raw = getattr(scene, "opening_config", "") if scene else ""
    try:
        payload = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        # Every training scene follows the same automatic opening contract.
        "enabled": True,
        "mode": "preset" if payload.get("mode") == "preset" else "dynamic",
        "speaker_role_ids": [int(item) for item in (payload.get("speaker_role_ids") or []) if str(item).isdigit()][:3],
        "director_note": _text(payload.get("director_note")),
        "preset_turns": [item for item in (payload.get("preset_turns") or []) if isinstance(item, dict) and _text(item.get("content"))][:9],
    }


def infer_session_scene_kind(scene: models.Scene | None, session: models.TrainingSession | None) -> str:
    if not scene:
        return "generic"
    stage = _text(getattr(session, "current_stage", "")) if session else ""
    return infer_scene_kind(_text(scene.name), stage)


def resolve_dialogue_mode(scene: models.Scene | None, session: models.TrainingSession | None) -> str:
    if infer_session_scene_kind(scene, session) == "intake":
        return "caller_first"
    return "officer_led"


def is_caller_opening_role(role: models.Role | None) -> bool:
    if not role or not is_role_speakable(role):
        return False
    role_type = _text(role.role_type)
    role_name = _text(role.name)
    haystack = f"{role_type} {role_name} {_text(role.status)}"
    return any(hint in haystack for hint in CALLER_OPEN_ROLE_HINTS)


def redact_dispatch_brief_for_student(
    scene: models.Scene | None,
    session: models.TrainingSession | None,
) -> str | None:
    if not scene:
        return None
    if resolve_dialogue_mode(scene, session) == "caller_first":
        return INTAKE_MINIMAL_DISPATCH
    return _text(scene.dispatch_brief) or None


def redact_first_impression_for_student(
    scene: models.Scene | None,
    session: models.TrainingSession | None,
) -> str | None:
    if not scene:
        return None
    if resolve_dialogue_mode(scene, session) == "caller_first":
        return None
    return _text(scene.first_impression) or None


def _safe_structured(case: models.Case | None) -> dict[str, Any]:
    if not case or not case.structured_data:
        return {}
    try:
        payload = json.loads(case.structured_data)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _find_person_meta(case: models.Case | None, role: models.Role | None) -> dict[str, Any]:
    structured = _safe_structured(case)
    name = _text(getattr(role, "name", ""))
    for person in structured.get("persons") or []:
        if isinstance(person, dict) and _text(person.get("name")) == name:
            return person
    return {}


def _strip_document_voice(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"^(?:证人|被害人|受害人|嫌疑人)?[^，。]{1,12}(?:的)?(?:证言|陈述)[，,]?", "", text)
    text = re.sub(r"^(?:证实|证明|反映)(?:其|了)?", "", text)
    return text.strip(" ，,；;：:")


def _role_fact_lines(compact: dict[str, Any], max_chars: int = 900) -> list[str]:
    rows = compact.get("knowledge_ledger") or compact.get("role_memories") or []
    facts: list[str] = []
    used = 0
    for item in rows:
        if not isinstance(item, dict):
            continue
        content = _strip_document_voice(item.get("verbalization") or item.get("content") or item.get("statement"))
        if not content or content in facts:
            continue
        line = f"- {content}"
        if facts and used + len(line) > max_chars:
            break
        facts.append(content)
        used += len(line)
        if len(facts) >= 4:
            break
    return facts


def _incident_hints(case: models.Case | None, structured: dict[str, Any]) -> str:
    parts: list[str] = []
    case_type = _text(case.case_type if case else "") or _text(structured.get("case_type"))
    if case_type:
        parts.append(case_type)
    for key in ("conflict_points", "key_facts", "transcript_summary"):
        values = structured.get(key)
        if isinstance(values, list):
            parts.extend(_text(item) for item in values if _text(item))
        elif _text(values):
            parts.append(_text(values))
    narrative = _text(structured.get("full_narrative") or structured.get("case_background"))
    if narrative:
        parts.append(narrative)
    if not parts and case:
        parts.append(_text(case.background))
    return "；".join(dict.fromkeys(item for item in parts if item)) or "现场发生紧急情况"


def _build_opening_context(
    case: models.Case | None,
    role: models.Role | None,
    scene: models.Scene | None,
) -> dict[str, Any]:
    structured = _safe_structured(case)
    person_meta = _find_person_meta(case, role)
    behavior_mode = infer_scene_behavior_mode(
        _text(getattr(scene, "name", "")),
        _text(getattr(case, "case_type", "")),
        None,
    )
    compact = person_to_role_compact_view(person_meta or {}, scene_behavior_mode=behavior_mode)
    try:
        persona = build_persona_profile(role, case, scene) if role else {}
    except Exception:
        persona = {}

    generation_context = compile_role_generation_context(case, role) if case and role else {}
    story_source = generation_context.get("full_story_source") if isinstance(generation_context, dict) else {}
    story_source = story_source if isinstance(story_source, dict) else {}
    scene_kind = infer_scene_kind(_text(getattr(scene, "name", "")), "")
    opening_behavior = (
        "像真实报警人一样先说清发生了什么和当前紧迫诉求，保留时间、地点等细节等待追问。"
        if scene_kind == "intake"
        else "像在场人员一样先说一项与训练任务直接相关、且属于本人认知的关键事实，等待民警继续询问。"
    )
    return {
        "role_name": _text(getattr(role, "name", "")) or "报警人",
        "role_type": _text(compact.get("role_type") or getattr(role, "role_type", "")) or "报警人",
        "behavior_archetype": _text(compact.get("behavior_archetype") or persona.get("behavior_archetype")) or "求助配合型",
        "current_goal": _text(compact.get("current_goal") or persona.get("current_goal")),
        "core_concern": _text(compact.get("core_concern") or persona.get("core_concern")),
        "case_type": _text(getattr(case, "case_type", "")) or _text(structured.get("case_type")) or "警情",
        "incident_hints": _incident_hints(case, structured),
        "emotion_hint": _text(persona.get("emotion_level")) or "偏紧张",
        "scene_name": _text(getattr(scene, "name", "")) or "现场处置",
        "scene_description": _text(getattr(scene, "description", "")) or "根据当前训练任务开始对话",
        "case_story": _text(story_source.get("content")) or _text(getattr(case, "background", "")) or "暂无完整剧情文本",
        "role_facts": _role_fact_lines(compact),
        "opening_behavior": opening_behavior,
    }


def _fallback_opening_utterances(context: dict[str, Any]) -> list[dict[str, str]]:
    name = context.get("role_name") or "我"
    facts = context.get("role_facts") or []
    if facts:
        fact = _strip_document_voice(facts[0])
        return [{"content": f"我是{name}。我能确认的是，{fact}"}]
    if context.get("opening_behavior", "").startswith("像真实报警人"):
        incident = str(context.get("incident_hints") or context.get("case_type") or "现场出事了").split("；")[0]
        return [{"content": f"喂，110吗？我是{name}，这边{incident}，请你们尽快过来处理。"}]
    return [{"content": f"我是{name}。关于现在的情况，我只说明自己能够确认的部分。"}]


def _parse_opening_payload(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, dict):
        return []
    utterances = raw.get("utterances")
    if isinstance(utterances, list) and utterances:
        parsed: list[dict[str, str]] = []
        for item in utterances[:3]:
            if isinstance(item, dict) and _text(item.get("content")):
                parsed.append({"content": _text(item.get("content"))})
            elif _text(item):
                parsed.append({"content": _text(item)})
        if parsed:
            return parsed
    response = _text(raw.get("response"))
    if response:
        return [{"content": response}]
    return []


def generate_opening_utterances(
    case: models.Case | None,
    role: models.Role | None,
    scene: models.Scene | None,
    *,
    director_note: str = "",
) -> tuple[list[dict[str, str]], str]:
    context = _build_opening_context(case, role, scene)
    inner_thought = "电话刚接通，得先把最要紧的事说出来。"
    prompt = build_opening_system_prompt(
        role_name=context["role_name"],
        role_type=context["role_type"],
        scene_name=context["scene_name"],
        scene_description=context["scene_description"],
        case_story=context["case_story"],
        role_facts="\n".join(f"- {item}" for item in context["role_facts"]) or "- 暂无可直接披露的本人事实。",
        opening_behavior=_text(director_note) or context["opening_behavior"],
        max_reply_chars=ROLE_REPLY_MAX_CHARS,
    )
    try:
        response, trace = create_roleplay_json_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.65,
            max_tokens=900,
            return_trace=True,
        )
        payload = extract_json_payload(extract_message_text(response))
        utterances = _parse_opening_payload(payload)
        if payload and _text(payload.get("inner_thought")):
            inner_thought = _text(payload.get("inner_thought"))
        if utterances:
            return sanitize_utterances(utterances), inner_thought
        logger.warning("Opening role response was not valid JSON: role=%s trace=%s", context["role_name"], trace)
    except Exception as exc:
        logger.warning("Opening role generation failed: role=%s error=%s", context["role_name"], exc)
    return sanitize_utterances(_fallback_opening_utterances(context)), inner_thought


def generate_scene_opening_utterances(
    case: models.Case | None,
    scene: models.Scene | None,
    roles: list[models.Role],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = [role for role in roles if role.id in set(config.get("speaker_role_ids") or [])]
    if not selected:
        selected = [role for role in roles if is_role_speakable(role)][:1]
    if not selected:
        return []
    if config.get("mode") == "preset":
        role_map = {role.id: role for role in selected}
        rows: list[dict[str, Any]] = []
        for item in config.get("preset_turns") or []:
            if not _text(item.get("content")):
                continue
            try:
                role_id = int(item.get("speaker_role_id") or 0)
            except (TypeError, ValueError):
                role_id = 0
            rows.append({"content": _text(item.get("content")), "role": role_map.get(role_id) or selected[0]})
        return rows
    outputs: list[dict[str, Any]] = []
    for role in selected:
        utterances, _ = generate_opening_utterances(
            case,
            role,
            scene,
            director_note=config.get("director_note") or "",
        )
        outputs.extend({"content": item["content"], "role": role} for item in sanitize_utterances(utterances))
    return outputs


def should_generate_opening(
    scene: models.Scene | None,
    session: models.TrainingSession,
    role: models.Role | None,
    messages: list[models.Message],
) -> bool:
    runtime_state = load_runtime_state(session.revealed_info)
    if runtime_state.get("opening_delivered"):
        return False
    if messages:
        return False
    config = _opening_config(scene)
    return bool(config["enabled"]) and is_role_speakable(role)


def _ensure_opening_turn_unlocked(
    db,
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    role: models.Role | None,
) -> list[models.Message]:
    messages = filter_internal_prompt_messages(
        db.query(models.Message)
        .filter(models.Message.session_id == session.id)
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
        .all()
    )
    roles = resolve_scene_roles(db, scene, case) if scene else []
    speakable_roles = [item for item in roles if is_role_speakable(item)]
    opening_role = role if is_role_speakable(role) else (speakable_roles[0] if speakable_roles else None)
    if not should_generate_opening(scene, session, opening_role, messages):
        return []
    config = _opening_config(scene)
    if not speakable_roles and opening_role:
        speakable_roles = [opening_role]
    scene_opening = generate_scene_opening_utterances(case, scene, speakable_roles, config)
    if scene_opening:
        utterances = scene_opening
        inner_thought = "场景开场已按角色顺序进入对话。"
    else:
        utterances, inner_thought = generate_opening_utterances(case, opening_role, scene)
    utterances, pending_replies = limit_role_reply_turns_with_remainders([
        {
            **item,
            "role": item.get("role") or opening_role,
            "speaker_role_id": getattr(item.get("role") or opening_role, "id", None),
            "speaker_name": _text(getattr(item.get("role") or opening_role, "name", "")),
        }
        for item in utterances
        if isinstance(item, dict)
    ])
    created: list[models.Message] = []
    for index, item in enumerate(utterances):
        message = models.Message(
            session_id=session.id,
            role="assistant",
            content=item["content"],
            speaker_role_id=getattr(item.get("role") or opening_role, "id", None),
            speaker_name=_text(getattr(item.get("role") or opening_role, "name", "")) or None,
            inner_thought=inner_thought if index == 0 else None,
        )
        db.add(message)
        created.append(message)

    runtime_state = load_runtime_state(session.revealed_info)
    stored_pending = dict(runtime_state.get("pending_role_replies") or {})
    for role_key, pending in pending_replies.items():
        previous = stored_pending.get(role_key) if isinstance(stored_pending.get(role_key), dict) else {}
        stored_pending[role_key] = {
            "role_name": pending.get("role_name") or previous.get("role_name") or "",
            "content": f"{previous.get('content') or ''}{pending.get('content') or ''}",
        }
    runtime_state["pending_role_replies"] = stored_pending
    runtime_state["opening_delivered"] = True
    runtime_state["dialogue_mode"] = "caller_first" if resolve_dialogue_mode(scene, session) == "caller_first" else "scene_opening"
    session.revealed_info = dump_runtime_state(runtime_state)
    db.flush()
    runtime_state["opening_message_ids"] = [message.id for message in created if message.id]
    session.revealed_info = dump_runtime_state(runtime_state)
    db.flush()
    return created


def ensure_opening_turn(
    db,
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    role: models.Role | None,
) -> list[models.Message]:
    """Generate at most one opening turn per session in the application process."""
    with _OPENING_LOCKS[int(session.id)]:
        db.refresh(session)
        return _ensure_opening_turn_unlocked(db, session, scene, case, role)
