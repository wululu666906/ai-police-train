"""Director layer: orchestration only — who speaks, how many lines, interrupt vs respond."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import models
from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
from .multi_role_service import (
    _build_history_block,
    _match_role_by_name,
    _role_display_name,
    detect_addressed_roles,
    partition_addressed_roles,
)

DIRECTOR_ORCHESTRATION_PROMPT = """
你是警情训练场景的「对话导演」。你只负责编排现场发言秩序，不写任何角色台词。

学员（执法民警）本轮输入：{user_text}
场景：{scene_name}
阶段：{current_stage}（目标：{current_stage_goal}）

可对话角色当前状态：
{cast_summary}

近期对话：
{history_block}

编排规则：
1. 判断本轮互动模式 interaction_mode：
   - address_named：学员点名某人
   - public_question：向全场公开提问
   - calm_scene：安抚、控制场面、要求冷静
   - interrupt_chain：现场争执、抢话、插话
   - mixed：混合情况
2. cast_plan 最多 2 名角色参与发言（hold_silent 的不要放入）；speaker_name 必须来自上方「可对话角色」列表，禁止出现列表外人物。
3. 「主对话人」只是默认推荐对象，不是唯一发言人；学员点名几位就安排几位（最多 2 位），不得用未点名的主对话人顶替。
4. utterance_count（1-8）表示该角色在「一次发言段」内连续输出的台词条数（对应多个聊天气泡），学员在中间不用回复；不是训练轮次，不要理解成「说 1 句就等学员」。
5. 根据情绪、冲突、是否被点名决定 utterance_count；激动、辩解、交代经过时可 3-6 条，简短确认可 1-2 条。
6. participation：primary_respond（主回应）/ interrupt（插话打断）/ supplement（补充）
7. 只输出 JSON，不要 markdown，不要写台词。

输出格式：
{{
  "interaction_mode": "address_named",
  "routing_summary": "一句话说明编排理由",
  "cast_plan": [
    {{
      "speaker_name": "角色姓名",
      "participation": "primary_respond",
      "utterance_count": 2,
      "intent": "vent",
      "trigger_reason": "被民警点名要求说明经过"
    }}
  ],
  "scene_mood_shift": "tense"
}}
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clamp_count(value: Any, default: int = 1) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = default
    return max(1, min(8, numeric))


def _default_role_snapshot(role: models.Role) -> dict[str, int]:
    return {
        "emotion": int(getattr(role, "init_emotion", None) or 50),
        "cooperation": int(getattr(role, "init_trust", None) or 30),
        "risk": 50,
        "clarity": 50,
    }


def _build_cast_summary(roles: list[models.Role], role_snapshots: dict[str, dict[str, int]]) -> str:
    lines: list[str] = []
    for role in roles:
        snap = role_snapshots.get(str(role.id)) or _default_role_snapshot(role)
        lines.append(
            f"- {_role_display_name(role)}（{_text(role.role_type) or '相关人员'}）"
            f" 情绪{snap.get('emotion', 50)} 配合{snap.get('cooperation', 30)}"
            f" 风险{snap.get('risk', 50)} 清晰{snap.get('clarity', 50)}"
        )
    return "\n".join(lines) if lines else "（无可对话角色）"


def _build_cast_entries(
    speakers: list[models.Role],
    *,
    mode: str,
    default_utterances: int = 2,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, role in enumerate(speakers[:2]):
        participation = "primary_respond" if index == 0 else "supplement"
        if mode == "interrupt_chain" and index == 1:
            participation = "interrupt"
        entries.append(
            {
                "speaker_name": _role_display_name(role),
                "speaker_role_id": role.id,
                "role": role,
                "participation": participation,
                "utterance_count": default_utterances,
                "intent": "explain" if index == 0 else "respond",
                "trigger_reason": "被民警点名或要求发言",
            }
        )
    return entries


def _multi_speaker_prompt(user_text: str) -> bool:
    return any(token in user_text for token in ("你们", "双方", "两个人", "俩人", "两个", "都", "他们"))


def _pick_witness_responder(roles: list[models.Role]) -> Optional[models.Role]:
    for role in roles:
        role_type = _text(role.role_type)
        if "证" in role_type or "旁观" in role_type or "家属" in role_type:
            return role
    return roles[0] if roles else None


def _enforce_cast_plan(
    plan: dict[str, Any],
    *,
    addressed: list[models.Role],
    roles: list[models.Role],
    user_text: str,
) -> dict[str, Any]:
    if len(addressed) >= 2:
        speakers = addressed[:2]
        plan["interaction_mode"] = "address_named"
        plan["routing_summary"] = f"学员点名{'、'.join(_role_display_name(role) for role in speakers)}，安排两人发言。"
        plan["cast_plan"] = _build_cast_entries(speakers, mode="address_named")
        return plan

    if len(addressed) == 1:
        speaker = addressed[0]
        cast_plan = plan.get("cast_plan") or []
        matched = False
        for item in cast_plan:
            role = item.get("role") or _match_role_by_name(item.get("speaker_name"), roles)
            if role and role.id == speaker.id:
                matched = True
                break
        if not matched:
            plan["interaction_mode"] = "address_named"
            plan["routing_summary"] = f"学员点名{_role_display_name(speaker)}，由其主回应。"
            plan["cast_plan"] = _build_cast_entries([speaker], mode="address_named")
        return plan

    if len(roles) >= 2 and _multi_speaker_prompt(user_text):
        plan["interaction_mode"] = "public_question"
        plan["routing_summary"] = "向现场多人发问，安排两人依次回应。"
        plan["cast_plan"] = _build_cast_entries(roles[:2], mode="public_question")
    return plan


def _rule_based_director_plan(
    user_text: str,
    roles: list[models.Role],
    addressed_on_scene: list[models.Role],
    target_role_name: Optional[str],
    *,
    addressed_off_scene: Optional[list[models.Role]] = None,
) -> dict[str, Any]:
    off_scene = addressed_off_scene or []
    addressed = addressed_on_scene
    mode = "public_question"
    if any(token in user_text for token in ("冷静", "别激动", "慢慢来", "控制", "安抚")):
        mode = "calm_scene"
    elif len(addressed) >= 2 or (addressed and target_role_name):
        mode = "address_named"
    elif addressed or target_role_name:
        mode = "address_named"
    elif _multi_speaker_prompt(user_text):
        mode = "interrupt_chain"

    if off_scene and not addressed:
        witness = _pick_witness_responder(roles)
        if not witness:
            return {"interaction_mode": "mixed", "routing_summary": "无可对话角色", "cast_plan": [], "scene_mood_shift": "stable"}
        missing = "、".join(_role_display_name(role) for role in off_scene)
        return {
            "interaction_mode": "supplement",
            "routing_summary": f"学员提到的「{missing}」未在本场景到场可对话，由{_role_display_name(witness)}在场补充说明（勿冒充对方第一人称）。",
            "cast_plan": [
                {
                    "speaker_name": _role_display_name(witness),
                    "speaker_role_id": witness.id,
                    "role": witness,
                    "participation": "supplement",
                    "utterance_count": 3,
                    "intent": "witness_account",
                    "trigger_reason": f"学员问及未到场角色：{missing}",
                }
            ],
            "scene_mood_shift": "stable",
            "addressed_targets": [_role_display_name(role) for role in off_scene],
            "addressing_warning": f"「{missing}」未勾选为本场景可对话角色，请在管理端「角色与文案」中勾选到场后再问。",
        }

    if len(addressed) >= 2:
        speakers = addressed[:2]
        return {
            "interaction_mode": "address_named",
            "routing_summary": f"学员点名{'、'.join(_role_display_name(role) for role in speakers)}，安排两人发言。",
            "cast_plan": _build_cast_entries(speakers, mode="address_named"),
            "scene_mood_shift": "stable",
            "addressed_targets": [_role_display_name(role) for role in speakers],
        }

    cast_plan: list[dict[str, Any]] = []
    primary = None
    if len(addressed) == 1:
        primary = addressed[0]
    elif target_role_name:
        primary = _match_role_by_name(target_role_name, roles)
    elif _multi_speaker_prompt(user_text) and len(roles) >= 2:
        return {
            "interaction_mode": mode,
            "routing_summary": "现场多人被问，安排两人依次回应。",
            "cast_plan": _build_cast_entries(roles[:2], mode=mode),
            "scene_mood_shift": "tense" if mode == "interrupt_chain" else "stable",
            "addressed_targets": [_role_display_name(role) for role in roles[:2]],
        }
    elif roles and not detect_addressed_roles(user_text, roles):
        primary = roles[0]

    if primary:
        solo = len(roles) <= 1
        utterance_count = 2 if mode == "address_named" else (4 if solo else 3)
        cast_plan.append(
            {
                "speaker_name": _role_display_name(primary),
                "speaker_role_id": primary.id,
                "role": primary,
                "participation": "primary_respond",
                "utterance_count": utterance_count,
                "intent": "explain",
                "trigger_reason": "回应民警提问",
            }
        )

    secondary = next((role for role in roles if role.id != getattr(primary, "id", None)), None)
    if secondary and mode in {"interrupt_chain", "mixed", "calm_scene"} and len(roles) >= 2:
        cast_plan.append(
            {
                "speaker_name": _role_display_name(secondary),
                "speaker_role_id": secondary.id,
                "role": secondary,
                "participation": "interrupt" if mode == "interrupt_chain" else "supplement",
                "utterance_count": 1 if mode == "calm_scene" else 2,
                "intent": "defend",
                "trigger_reason": "插话或补充",
            }
        )

    return {
        "interaction_mode": mode,
        "routing_summary": "规则编排：优先回应被问角色，必要时第二人插话。",
        "cast_plan": cast_plan[:2],
        "scene_mood_shift": "tense" if mode == "interrupt_chain" else "stable",
        "addressed_targets": [_role_display_name(role) for role in addressed] if addressed else [],
    }


def _normalize_cast_plan(raw_plan: Any, roles: list[models.Role]) -> list[dict[str, Any]]:
    if not isinstance(raw_plan, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_plan:
        if not isinstance(item, dict):
            continue
        role = _match_role_by_name(item.get("speaker_name"), roles)
        if not role:
            continue
        name = _role_display_name(role)
        if name in seen:
            continue
        participation = _text(item.get("participation")) or "primary_respond"
        if participation == "hold_silent":
            continue
        seen.add(name)
        normalized.append(
            {
                "speaker_name": name,
                "speaker_role_id": role.id,
                "role": role,
                "participation": participation,
                "utterance_count": _clamp_count(item.get("utterance_count"), 1),
                "intent": _text(item.get("intent")) or "respond",
                "trigger_reason": _text(item.get("trigger_reason")) or "现场对话需要",
            }
        )
        if len(normalized) >= 2:
            break
    return normalized


def run_director(
    *,
    scene: models.Scene,
    roles: list[models.Role],
    history: list[Any],
    user_text: str,
    current_stage: str,
    current_stage_goal: str,
    target_role_name: Optional[str] = None,
    role_snapshots: Optional[dict[str, dict[str, int]]] = None,
    case_roles: Optional[list[models.Role]] = None,
    use_llm: bool = True,
) -> Optional[dict[str, Any]]:
    if not roles:
        return None

    snapshots = role_snapshots or {}
    on_scene, off_scene = partition_addressed_roles(user_text, roles, case_roles)
    addressed = list(on_scene)
    if target_role_name:
        forced = _match_role_by_name(target_role_name, roles)
        if forced and forced not in addressed:
            addressed.insert(0, forced)

    addressed_targets = [_role_display_name(role) for role in on_scene] + [_role_display_name(role) for role in off_scene]
    addressing_warning = ""
    if off_scene and not on_scene:
        missing = "、".join(_role_display_name(role) for role in off_scene)
        addressing_warning = f"「{missing}」未在本场景勾选为可对话角色，请改问左侧「现场角色」中的人，或在管理端补勾到场。"

    hint = ""
    if on_scene:
        hint = f"\n学员点名（在场）：{'、'.join(_role_display_name(r) for r in on_scene)}，必须安排其本人发言，禁止由他人冒充第一人称。"
    if off_scene:
        hint += f"\n学员还提到（未在场可对话）：{'、'.join(_role_display_name(r) for r in off_scene)}，不得安排其开口；可由在场证人/家属第三人称补充。"
    if target_role_name:
        hint += f"\n指定对象：{target_role_name}。"

    plan: Optional[dict[str, Any]] = None
    if use_llm:
        prompt = DIRECTOR_ORCHESTRATION_PROMPT.format(
            user_text=user_text,
            scene_name=_text(scene.name) or "训练场景",
            current_stage=current_stage or "训练中",
            current_stage_goal=current_stage_goal or "推进处置",
            cast_summary=_build_cast_summary(roles, snapshots),
            history_block=_build_history_block(history),
        ) + hint
        try:
            response = create_json_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.45,
                model=get_chat_model(),
                max_tokens=1200,
            )
            raw = extract_message_text(response) or ""
            match = re.search(r"\{[\s\S]*\}", raw)
            payload = json.loads(match.group(0) if match else raw)
            cast_plan = _normalize_cast_plan(payload.get("cast_plan"), roles)
            if cast_plan:
                plan = {
                    "interaction_mode": _text(payload.get("interaction_mode")) or "mixed",
                    "routing_summary": _text(payload.get("routing_summary")) or "导演编排",
                    "cast_plan": cast_plan,
                    "scene_mood_shift": _text(payload.get("scene_mood_shift")) or "stable",
                }
        except Exception:
            plan = None

    if not plan:
        plan = _rule_based_director_plan(
            user_text,
            roles,
            addressed,
            target_role_name,
            addressed_off_scene=off_scene,
        )

    if not plan.get("cast_plan"):
        fallback = _rule_based_director_plan(
            user_text,
            roles,
            addressed,
            target_role_name,
            addressed_off_scene=off_scene,
        )
        plan["cast_plan"] = fallback["cast_plan"]

    plan = _enforce_cast_plan(plan, addressed=addressed, roles=roles, user_text=user_text)
    plan["addressed_targets"] = addressed_targets
    if addressing_warning:
        plan["addressing_warning"] = addressing_warning
    elif off_scene and on_scene:
        missing = "、".join(_role_display_name(role) for role in off_scene)
        plan["addressing_warning"] = f"已安排在场角色回应；「{missing}」未到场可对话。"
    return plan
