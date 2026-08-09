"""Intake scene opening turn: caller speaks first before officer questions."""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from typing import Any

import models
from .llm_provider import create_json_chat_completion, extract_json_payload, extract_message_text
from .persona_engine import build_persona_profile
from .role_compact_service import person_to_role_compact_view
from .role_resolver import is_role_speakable
from .stage_config_service import infer_scene_behavior_mode, infer_scene_kind
from .dialogue_sanitize_service import filter_internal_prompt_messages, sanitize_utterances
from .training_runtime_service import dump_runtime_state, load_runtime_state
from .role_state_service import resolve_role_initial_state
from .role_resolver import resolve_scene_roles

INTAKE_MINIMAL_DISPATCH = "110 有新报警来电，等待接听。"
_OPENING_LOCKS: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)

CALLER_OPEN_ROLE_HINTS = ("报警", "报案", "证人", "被害人", "受害人")

OPENING_TURN_PROMPT = """你是警情训练模拟中的报警人/报案人，刚拨通110，接警员尚未发问。

【你的身份】{role_name}（{role_type}）
【行为原型（内部参考，禁止念出）】{behavior_archetype}
【当前诉求（内部参考，禁止念出）】{current_goal}
【内心担心（内部参考，禁止直说「我最怕/最担心/核心顾虑」）】{core_concern}
【情绪状态】{emotion_hint}

【案件背景（仅供你组织台词，勿像笔录一样一次说完）】
- 案件类型：{case_type}
- 事件线索：{incident_hints}

要求：
1. 你必须主动开口，不等接警员提问；像真实报警电话开头。
2. 输出 1-3 条连续台词 utterances，口语化，可慌乱、重复、跳跃。多条之间是报警人一口气说完，学员（接警员）在中间无需回复。
3. 必须让接警员听出「出了什么事」（如打架、纠纷、逃逸、求助、被盗等），可模糊但要有事件性质。
4. 可表达紧迫、害怕、催促，但不要一次性报全准确时间、地址、身份证号、电话。时间、地点等信息留待接警员追问时自然给出。
5. 内心担心只能体现在语气里（如「他们会不会找回来啊」），禁止念配置字段或说「我最怕的就是……」。
6. 不要以「民警」「同志」称呼对方；这是报警人视角。
7. 事件线索（incident_hints）可能包含多条信息，选择最紧急的一两条说，不要按清单逐条念。
8. inner_thought 写当前真实心理活动（如紧张、犹豫、怕说错），不要重复台词内容。
9. 注意：以下输出中的值为示例，请根据实际场景决定内容。只输出 JSON：
{{
  "utterances": [{{"content": "第一句"}}, {{"content": "第二句（可选）"}}],
  "inner_thought": "内心活动一句"
}}
"""


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
        "enabled": payload.get("enabled") is not False,
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


def _incident_hints(case: models.Case | None, structured: dict[str, Any]) -> str:
    parts: list[str] = []
    case_type = _text(case.case_type if case else "") or _text(structured.get("case_type"))
    if case_type:
        parts.append(case_type)
    for key in ("conflict_points", "key_facts", "transcript_summary"):
        values = structured.get(key)
        if isinstance(values, list):
            parts.extend(_text(item) for item in values[:3] if _text(item))
        elif _text(values):
            parts.append(_text(values))
    narrative = _text(structured.get("full_narrative") or structured.get("case_background"))
    if narrative:
        parts.append(narrative[:120])
    if not parts and case:
        parts.append(_text(case.background)[:120])
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

    return {
        "role_name": _text(getattr(role, "name", "")) or "报警人",
        "role_type": _text(compact.get("role_type") or getattr(role, "role_type", "")) or "报警人",
        "behavior_archetype": _text(compact.get("behavior_archetype") or persona.get("behavior_archetype")) or "求助配合型",
        "current_goal": _text(compact.get("current_goal") or persona.get("current_goal")),
        "core_concern": _text(compact.get("core_concern") or persona.get("core_concern")),
        "case_type": _text(getattr(case, "case_type", "")) or _text(structured.get("case_type")) or "警情",
        "incident_hints": _incident_hints(case, structured),
        "emotion_hint": _text(persona.get("emotion_level")) or "偏紧张",
    }


def _fallback_opening_utterances(context: dict[str, Any]) -> list[dict[str, str]]:
    incident = context.get("incident_hints") or context.get("case_type") or "出事了"
    short_incident = str(incident).split("；")[0][:40]
    name = context.get("role_name") or "我"
    lines = [
        f"喂，110吗？我是{name}，这边{short_incident}，你们能不能快点过来！",
        "我现在心里发慌，也不知道该怎么办……",
    ]
    concern = _text(context.get("core_concern"))
    if concern and len(lines) < 3:
        lines.append("你们先听我说，我现在真的挺急的。")
    return [{"content": line} for line in lines[:3]]


def _fallback_scene_opening(case: models.Case | None, scene: models.Scene | None, role: models.Role) -> list[dict[str, str]]:
    context = _build_opening_context(case, role, scene)
    timeline = _text(getattr(scene, "description", "")) or _text(context.get("incident_hints")) or "现场情况"
    memory = _text(context.get("core_concern"))
    lines = [f"我是{context['role_name']}，刚才现场{timeline[:90]}。"]
    if memory:
        lines.append(f"我最担心的是{memory[:70]}。")
    return [{"content": item} for item in lines]


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
) -> tuple[list[dict[str, str]], str]:
    context = _build_opening_context(case, role, scene)
    inner_thought = "电话刚接通，得先把最要紧的事说出来。"
    prompt = OPENING_TURN_PROMPT.format(
        role_name=context["role_name"],
        role_type=context["role_type"],
        behavior_archetype=context["behavior_archetype"],
        current_goal=context["current_goal"] or "希望警方尽快处理",
        core_concern=context["core_concern"] or "事态继续恶化",
        emotion_hint=context["emotion_hint"],
        case_type=context["case_type"],
        incident_hints=context["incident_hints"],
    )
    try:
        response = create_json_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.65,
            max_tokens=800,
        )
        payload = extract_json_payload(extract_message_text(response))
        utterances = _parse_opening_payload(payload)
        if payload and _text(payload.get("inner_thought")):
            inner_thought = _text(payload.get("inner_thought"))
        if utterances:
            return sanitize_utterances(utterances), inner_thought
    except Exception:
        pass
    return sanitize_utterances(_fallback_opening_utterances(context)), inner_thought


def generate_scene_opening_utterances(
    case: models.Case | None,
    scene: models.Scene | None,
    roles: list[models.Role],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = [role for role in roles if role.id in set(config.get("speaker_role_ids") or [])]
    if not selected:
        selected = [role for role in roles if is_role_speakable(role)][:3]
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
        context = _build_opening_context(case, role, scene)
        prompt = (
            f"你是警情训练场景中的{context['role_name']}（{context['role_type']}），刚进入场景。\n"
            f"场景：{_text(getattr(scene, 'name', ''))}；场景描述：{_text(getattr(scene, 'description', ''))[:500]}\n"
            f"案件线索：{context['incident_hints']}\n人物记忆与诉求：{context.get('current_goal') or '无'}；{context.get('core_concern') or '无'}\n"
            f"四维状态：{resolve_role_initial_state(role, case, scene)}\n导演约束：{config.get('director_note') or '自然开场，直接给出本角色此刻最重要的事实'}\n"
            "只输出1-2条角色气泡台词，不要旁白、不要编造未给出的事实。JSON：{\"utterances\":[{\"content\":\"台词\"}]}"
        )
        utterances: list[dict[str, str]] = []
        try:
            response = create_json_chat_completion(messages=[{"role": "user", "content": prompt}], temperature=0.6, max_tokens=420)
            payload = extract_json_payload(extract_message_text(response))
            utterances = _parse_opening_payload(payload)
        except Exception:
            utterances = []
        if not utterances:
            utterances = _fallback_scene_opening(case, scene, role)
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
