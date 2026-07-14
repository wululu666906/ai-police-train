import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
from .avatar_service import _safe_json_loads, assign_avatar, get_avatar_url
from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
from .persona_engine import build_persona_profile, build_role_script, format_persona_block
from .role_resolver import is_role_speakable, resolve_scene_roles

# DEPRECATED: This prompt is no longer used at runtime.
# The active director prompt is DIRECTOR_ORCHESTRATION_PROMPT in multi_role_director.py.
# Kept here only as reference; remove once multi_role_service refactor is complete.
MULTI_ROLE_DIRECTOR_PROMPT = """
你是警情训练场景的“对话导演”，负责根据学员（执法民警）输入，决定现场哪些角色开口、各自说什么。

规则：
1. 只能让【可对话角色列表】中的角色发言，禁止旁白、禁止助手口吻。
2. 每轮最多安排 2 名角色发言；若学员明确点名某人，该角色必须发言。
3. 根据语境判断：调解/纠纷场景可双方轮流；询问单人时只让被问者回答；情绪激动时允许插话。
4. 每个角色的台词必须符合其性格、状态、已知/未知信息，不能串人设。
5. 只输出合法 JSON，不要 markdown。

场景：{scene_name}
阶段：{current_stage}（目标：{current_stage_goal}）
学员本轮输入：{user_text}

可对话角色（含人设摘要）：
{cast_block}

近期对话（带说话人标注）：
{history_block}

请输出 JSON：
{{
  "speakers": [
    {{
      "speaker_name": "角色姓名",
      "response": "该角色本轮台词",
      "inner_thought": "该角色心理活动，仅第一条可详细"
    }}
  ],
  "primary_speaker_name": "本轮主要影响情绪/信任的角色姓名",
  "updated_emotion": 55,
  "updated_trust": 35,
  "updated_risk": 50,
  "updated_clarity": 50,
  "new_fact_revealed": null,
  "is_stage_completed": false,
  "follow_up_response": null
}}
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


class _TransientActorMessage:
    def __init__(self, speaker_name: str, speaker_role_id: int | None, content: str, inner_thought: str = ""):
        self.role = "assistant"
        self.speaker_name = speaker_name
        self.speaker_role_id = speaker_role_id
        self.content = content
        self.inner_thought = inner_thought


def _append_actor_output_to_history(history: list[Any], actor_outputs: list[dict[str, Any]]) -> list[Any]:
    augmented = list(history)
    for actor in actor_outputs:
        speaker_name = actor.get("speaker_name") or ""
        speaker_role_id = actor.get("speaker_role_id")
        thought = actor.get("inner_thought") or ""
        first = True
        for utterance in actor.get("utterances") or []:
            content = _text(utterance.get("content") if isinstance(utterance, dict) else utterance)
            if not content:
                continue
            augmented.append(
                _TransientActorMessage(
                    speaker_name=speaker_name,
                    speaker_role_id=speaker_role_id,
                    content=content,
                    inner_thought=thought if first else "",
                )
            )
            first = False
    return augmented


def _role_display_name(role: models.Role) -> str:
    return _text(role.name) or "相关人员"


def _build_cast_block(roles: list[models.Role], case: Optional[models.Case], scene: Optional[models.Scene]) -> str:
    lines: list[str] = []
    for role in roles:
        profile = build_persona_profile(role, case, scene)
        script = build_role_script(role, case, scene, profile)
        persona = format_persona_block(profile, script, {}, {})
        lines.append(
            "\n".join(
                [
                    f"### {_role_display_name(role)}",
                    f"- 角色类型：{_text(role.role_type) or '相关人员'}",
                    f"- 状态：{_text(role.status) or '正常'}",
                    f"- 是否主对话人：{'是' if role else '否'}",
                    persona[:1200],
                ]
            )
        )
    return "\n\n".join(lines) if lines else "（无可对话角色）"


def _build_history_block(history: list[Any]) -> str:
    lines: list[str] = []
    for message in history[-10:]:
        role = _text(getattr(message, "role", ""))
        content = _text(getattr(message, "content", ""))
        if not content:
            continue
        if role in {"assistant", "ai"}:
            speaker = _text(getattr(message, "speaker_name", "")) or "角色"
            lines.append(f"{speaker}：{content}")
        elif role == "user":
            lines.append(f"执法民警：{content}")
        elif role == "action":
            lines.append(f"[动作] {content}")
    return "\n".join(lines) if lines else "（暂无历史）"


def _name_position(text: str, name: str) -> int:
    index = text.find(name)
    return index if index >= 0 else 10**9


def detect_addressed_roles(user_text: str, roles: list[models.Role]) -> list[models.Role]:
    text = _text(user_text)
    if not text or not roles:
        return []
    ordered = sorted(roles, key=lambda role: len(_role_display_name(role)), reverse=True)
    matched: list[models.Role] = []
    seen_ids: set[int] = set()
    for role in ordered:
        name = _role_display_name(role)
        if len(name) < 2 or name not in text:
            continue
        if role.id in seen_ids:
            continue
        seen_ids.add(role.id)
        matched.append(role)
    matched.sort(key=lambda role: _name_position(text, _role_display_name(role)))
    return matched


def list_case_speakable_roles(db: Session, case: Optional[models.Case]) -> list[models.Role]:
    if not case:
        return []
    rows = db.query(models.Role).filter(models.Role.case_id == case.id).all()
    return [role for role in rows if is_role_speakable(role)]


def partition_addressed_roles(
    user_text: str,
    scene_roles: list[models.Role],
    case_roles: Optional[list[models.Role]] = None,
) -> tuple[list[models.Role], list[models.Role]]:
    """Return (on_scene_named, off_scene_named) based on names appearing in user_text."""
    pool = case_roles if case_roles else scene_roles
    named = detect_addressed_roles(user_text, pool)
    scene_ids = {role.id for role in scene_roles}
    on_scene = [role for role in named if role.id in scene_ids]
    off_scene = [role for role in named if role.id not in scene_ids]
    return on_scene, off_scene


def should_use_scene_conversation(roles: list[models.Role], scene: Optional[models.Scene] = None) -> bool:
    """所有可对话角色场景均走导演层 + 角色层 + 场景引擎（含单角色案件）。"""
    del scene
    return any(is_role_speakable(role) for role in roles)


def should_use_multi_role(roles: list[models.Role], scene: Optional[models.Scene] = None) -> bool:
    return should_use_scene_conversation(roles, scene)


def _match_role_by_name(name: str, roles: list[models.Role]) -> Optional[models.Role]:
    clean = _text(name)
    if not clean:
        return None
    for role in roles:
        if _role_display_name(role) == clean:
            return role
    for role in roles:
        if clean in _role_display_name(role) or _role_display_name(role) in clean:
            return role
    return None


def _normalize_speaker_entries(raw_speakers: Any, roles: list[models.Role]) -> list[dict[str, Any]]:
    if not isinstance(raw_speakers, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for item in raw_speakers[:2]:
        if not isinstance(item, dict):
            continue
        role = _match_role_by_name(item.get("speaker_name"), roles)
        if not role:
            continue
        name = _role_display_name(role)
        if name in seen_names:
            continue
        response = _text(item.get("response"))
        if not response:
            continue
        seen_names.add(name)
        normalized.append(
            {
                "role": role,
                "speaker_name": name,
                "response": response,
                "inner_thought": _text(item.get("inner_thought")),
            }
        )
    return normalized


def _state_label(emotion: int, cooperation: int, risk: int) -> str:
    if risk >= 70:
        return "失控边缘"
    if emotion >= 72:
        return "情绪激动"
    if cooperation <= 28:
        return "抵触防备"
    if cooperation >= 65:
        return "愿意配合"
    return "僵持观望"


def generate_multi_role_turn(
    db: Session,
    *,
    scene: models.Scene,
    case: Optional[models.Case],
    roles: list[models.Role],
    history: list[Any],
    user_text: str,
    current_stage: str,
    current_stage_goal: str,
    target_role_name: Optional[str] = None,
    runtime_state: Optional[dict[str, Any]] = None,
    use_llm: bool = True,
) -> Optional[dict[str, Any]]:
    from .multi_role_actor import _build_role_brain, generate_role_dialogue
    from .multi_role_director import run_director
    from .scene_conversation_engine import consolidate_scene_conversation

    if not roles:
        return None

    runtime_state = runtime_state if isinstance(runtime_state, dict) else {}
    role_snapshots: dict[str, dict[str, int]] = dict(runtime_state.get("role_state_snapshots") or {})
    raw_role_brains = runtime_state.get("role_brains")
    role_brains: dict[str, dict[str, Any]] = dict(raw_role_brains) if isinstance(raw_role_brains, dict) else {}
    for role in roles:
        key = str(role.id)
        if key not in role_snapshots:
            role_snapshots[key] = {
                "emotion": int(getattr(role, "init_emotion", None) or 50),
                "cooperation": int(getattr(role, "init_trust", None) or 30),
                "risk": 50,
                "clarity": 50,
            }

    case_roles = list_case_speakable_roles(db, case) if case else []
    director_plan = run_director(
        scene=scene,
        roles=roles,
        history=history,
        user_text=user_text,
        current_stage=current_stage,
        current_stage_goal=current_stage_goal,
        target_role_name=target_role_name,
        role_snapshots=role_snapshots,
        case_roles=case_roles,
        use_llm=use_llm,
    )
    if not director_plan or not director_plan.get("cast_plan"):
        return None

    actor_outputs: list[dict[str, Any]] = []
    for cast_entry in director_plan["cast_plan"]:
        role = cast_entry.get("role")
        if not role:
            continue
        brain_key = str(role.id)
        snap = role_snapshots.get(str(role.id)) or {
            "emotion": int(getattr(role, "init_emotion", None) or 50),
            "cooperation": int(getattr(role, "init_trust", None) or 30),
            "risk": 50,
            "clarity": 50,
        }
        prior_brain = role_brains.get(brain_key) or {}
        actor_history = _append_actor_output_to_history(history, actor_outputs)
        built_brain = _build_role_brain(
            role=role,
            case=case,
            scene=scene,
            history=actor_history,
            previous_brain=prior_brain,
        )
        actor_output = generate_role_dialogue(
            role=role,
            cast_entry=cast_entry,
            director_plan=director_plan,
            scene=scene,
            case=case,
            history=actor_history,
            user_text=user_text,
            current_stage=current_stage,
            role_snapshot=snap,
            addressed_targets=director_plan.get("addressed_targets") or [],
            peer_utterances=actor_outputs,
            role_brain=built_brain,
            use_llm=use_llm,
        )
        role_brains[brain_key] = actor_output.get("role_brain") or built_brain
        actor_outputs.append(actor_output)

    if not actor_outputs:
        return None

    runtime_state["role_brains"] = role_brains
    previous_primary = actor_outputs[0].get("role") or roles[0]
    return consolidate_scene_conversation(
        director_plan=director_plan,
        actor_outputs=actor_outputs,
        role_snapshots=role_snapshots,
        previous_primary_role=previous_primary,
    )


def serialize_scene_roles(
    db: Session,
    scene: Optional[models.Scene],
    case: Optional[models.Case] = None,
    *,
    runtime_state: Optional[dict[str, Any]] = None,
    target_role_name: str = "",
    active_role_ids: Optional[list[int]] = None,
) -> list[dict[str, Any]]:
    roles = resolve_scene_roles(db, scene, case)
    linked_rows = (
        db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).all() if scene else []
    )
    primary_ids = {row.role_id for row in linked_rows if row.is_primary}
    if not primary_ids and roles:
        primary_ids = {roles[0].id}

    snapshots = (runtime_state or {}).get("role_state_snapshots") if isinstance(runtime_state, dict) else {}
    if not isinstance(snapshots, dict):
        snapshots = {}
    deltas = (runtime_state or {}).get("role_state_deltas") if isinstance(runtime_state, dict) else {}
    if not isinstance(deltas, dict):
        deltas = {}
    active_ids = set(active_role_ids or (runtime_state or {}).get("last_active_role_ids") or [])
    target_clean = _text(target_role_name)

    payload: list[dict[str, Any]] = []
    for role in roles:
        snap = snapshots.get(str(role.id)) or {
            "emotion": int(getattr(role, "init_emotion", None) or 50),
            "cooperation": int(getattr(role, "init_trust", None) or 30),
            "risk": 50,
            "clarity": 50,
        }
        emotion = int(snap.get("emotion", 50))
        cooperation = int(snap.get("cooperation", 30))
        risk = int(snap.get("risk", 50))
        clarity = int(snap.get("clarity", 50))
        delta = deltas.get(str(role.id)) if isinstance(deltas.get(str(role.id)), dict) else {}
        display_label = _state_label(emotion, cooperation, risk)

        # Assign avatar based on persona_meta
        persona_meta = _safe_json_loads(role.persona_meta, {})
        age = persona_meta.get("age") if isinstance(persona_meta, dict) else None
        gender = persona_meta.get("gender") if isinstance(persona_meta, dict) else None
        avatar_id = assign_avatar(age, gender, _role_display_name(role))
        avatar_url = get_avatar_url(avatar_id)

        payload.append(
            {
                "id": role.id,
                "name": _role_display_name(role),
                "role_type": _text(role.role_type),
                "status": _text(role.status),
                "is_primary": role.id in primary_ids,
                "speakable": is_role_speakable(role),
                "emotion": emotion,
                "cooperation": cooperation,
                "risk": risk,
                "clarity": clarity,
                "emotion_delta": int(delta.get("emotion", 0) or 0),
                "cooperation_delta": int(delta.get("cooperation", 0) or 0),
                "risk_delta": int(delta.get("risk", 0) or 0),
                "clarity_delta": int(delta.get("clarity", 0) or 0),
                "state_label": display_label,
                "is_active": role.id in active_ids,
                "is_targeted": target_clean == _role_display_name(role),
                "avatar_id": avatar_id,
                "avatar_url": avatar_url,
            }
        )
    return payload
