"""Director layer: orchestration only — who speaks, how many lines, interrupt vs respond."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import models
from .human_reaction_engine import build_director_human_context, scene_mood_shift
from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model, get_fast_generation_kwargs
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

真人化现场判断：
{human_context_block}

编排规则：
1. 判断本轮互动模式 interaction_mode：
   - address_named：学员点名某人
   - public_question：向全场公开提问
   - calm_scene：安抚、控制场面、要求冷静
   - interrupt_chain：现场争执、抢话、插话
   - supplement：学员提到未到场角色，由在场角色以证人/家属视角补充说明（不用第一人称冒充）
   - mixed：混合情况
2. cast_plan 最多 2 名角色参与发言（hold_silent 的不要放入）；speaker_name 必须来自上方「可对话角色」列表，禁止出现列表外人物。
3. 「主对话人」只是默认推荐对象，不是唯一发言人；学员点名几位就安排几位（最多 2 位），不得用未点名的主对话人顶替。
4. utterance_count（1-8）表示该角色在「一次发言段」内连续输出的台词条数（对应多个聊天气泡），学员在中间不用回复；不是训练轮次，不要理解成「说 1 句就等学员」。
5. 根据情绪、冲突、是否被点名决定 utterance_count；激动、辩解、交代经过时可 3-6 条，简短确认可 1-2 条。
6. participation：primary_respond（主回应）/ interrupt（插话打断）/ supplement（补充）
7. trigger_reason 写该角色本轮开口的具体触发原因（如"被民警点名"、"被对方指责后抢话"、"主动澄清误会"等），不要说空话。
8. intent 可选值及含义：
   - explain：说明事情经过
   - vent：发泄情绪、抱怨
   - defend：辩解、推卸责任、切割
   - respond：简短回应确认
   - witness_account：以在场第三人称提供信息（非本人视角）
   - calm_down：表达平静、配合
9. scene_mood 可取：stable（平稳）/ tense（升温）/ deadlock（僵持）/ chaotic（混乱）/ deescalate（缓和）/ edge_loss_control（失控边缘）。
10. scene_mood_shift 可取：stable（平稳）/ tense（紧张升温）/ deescalate（缓和降温），反映本轮互动对现场氛围的影响方向。
11. 利用 cast_summary 和真人化现场判断辅助决策：情绪高且风险高者更容易插话或抢话；配合度低者更容易回避、反问或僵持；清晰度低者台词宜短、跳跃、需要民警控场。
12. 每个 cast_plan 项增加 reaction_hint，写该角色本轮像真人一样的反应倾向，例如争执型、委屈倾诉型、防御否认型、回避沉默型、混乱失序型、求保护型、突然配合型。

注意：以下输出格式中的值为示例，请根据实际场景动态决定，不要照搬。

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
      "trigger_reason": "被民警点名要求说明经过",
      "reaction_hint": "委屈倾诉型"
    }}
  ],
  "scene_mood": "tense",
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
                "reaction_hint": "争执型" if mode == "interrupt_chain" else "试探观察型",
            }
        )
    return entries


def _multi_speaker_prompt(user_text: str) -> bool:
    text = _text(user_text)
    return any(
        token in text
        for token in (
            "你们",
            "双方",
            "两个人",
            "两位",
            "俩人",
            "两个",
            "大家",
            "都说",
            "分别",
            "轮流",
            "一个一个",
            "他们",
            "她们",
            "各自",
            "每个人",
        )
    )


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
        plan.setdefault("scene_mood", "tense")
        plan["scene_mood_shift"] = scene_mood_shift(plan.get("scene_mood") or "tense")
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
        plan.setdefault("scene_mood", "stable")
        plan["scene_mood_shift"] = scene_mood_shift(plan.get("scene_mood") or "stable")
        return plan

    if len(roles) >= 2 and _multi_speaker_prompt(user_text):
        plan["interaction_mode"] = "public_question"
        plan["routing_summary"] = "向现场多人发问，安排两人依次回应。"
        plan["cast_plan"] = _build_cast_entries(roles[:2], mode="public_question")
        plan.setdefault("scene_mood", "tense")
        plan["scene_mood_shift"] = scene_mood_shift(plan.get("scene_mood") or "tense")
        return plan

    # A normal question has one respondent. Letting the director freely keep
    # two speakers here caused unrelated roles to echo one another and made
    # their names/avatars look like they had swapped identities.
    cast_plan = plan.get("cast_plan") if isinstance(plan.get("cast_plan"), list) else []
    if cast_plan:
        plan["cast_plan"] = cast_plan[:1]
    return plan


def _rule_based_director_plan(
    user_text: str,
    roles: list[models.Role],
    addressed_on_scene: list[models.Role],
    target_role_name: Optional[str],
    *,
    addressed_off_scene: Optional[list[models.Role]] = None,
    role_snapshots: Optional[dict[str, dict[str, int]]] = None,
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
    if any(token in _text(user_text) for token in ("冷静", "别激动", "慢慢来", "控制", "安抚", "坐下来", "商量")):
        mode = "calm_scene"
    human_context = build_director_human_context(
        roles=roles,
        role_snapshots=role_snapshots or {},
        user_text=user_text,
        interaction_mode=mode,
    )
    scene_mood = human_context["scene_mood"]

    if off_scene and not addressed:
        witness = _pick_witness_responder(roles)
        if not witness:
            return {
                "interaction_mode": "mixed",
                "routing_summary": "无可对话角色",
                "cast_plan": [],
                "scene_mood": "stable",
                "scene_mood_shift": "stable",
            }
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
                    "reaction_hint": "回避沉默型",
                }
            ],
            "scene_mood": "stable",
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
            "scene_mood": scene_mood,
            "scene_mood_shift": scene_mood_shift(scene_mood),
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
            "scene_mood": scene_mood,
            "scene_mood_shift": scene_mood_shift(scene_mood),
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
                "reaction_hint": "委屈倾诉型" if mode == "public_question" else "试探观察型",
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
                "reaction_hint": "突然配合型" if mode == "calm_scene" else "争执型",
            }
        )

    return {
        "interaction_mode": mode,
        "routing_summary": "规则编排：优先回应被问角色，必要时第二人插话。",
        "cast_plan": cast_plan[:2],
        "scene_mood": scene_mood,
        "scene_mood_shift": scene_mood_shift(scene_mood),
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
                "reaction_hint": _text(item.get("reaction_hint")) or "",
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
    human_context = build_director_human_context(
        roles=roles,
        role_snapshots=snapshots,
        user_text=user_text,
        interaction_mode="",
    )
    if use_llm and os.getenv("ROLE_DIRECTOR_USE_LLM", "0").strip().lower() in {"1", "true", "yes"}:
        prompt = DIRECTOR_ORCHESTRATION_PROMPT.format(
            user_text=user_text,
            scene_name=_text(scene.name) or "训练场景",
            current_stage=current_stage or "训练中",
            current_stage_goal=current_stage_goal or "推进处置",
            cast_summary=_build_cast_summary(roles, snapshots),
            history_block=_build_history_block(history),
            human_context_block=human_context["block"],
        ) + hint
        try:
            response = create_json_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.45,
                model=get_chat_model(),
                max_tokens=max(128, int(os.getenv("ROLE_DIRECTOR_MAX_TOKENS", "320"))),
                extra_kwargs=get_fast_generation_kwargs(),
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
                    "scene_mood": _text(payload.get("scene_mood")) or human_context["scene_mood"],
                    "scene_mood_shift": _text(payload.get("scene_mood_shift")) or human_context["scene_mood_shift"],
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
            role_snapshots=snapshots,
        )

    if not plan.get("cast_plan"):
        fallback = _rule_based_director_plan(
            user_text,
            roles,
            addressed,
            target_role_name,
            addressed_off_scene=off_scene,
            role_snapshots=snapshots,
        )
        plan["cast_plan"] = fallback["cast_plan"]

    plan = _enforce_cast_plan(plan, addressed=addressed, roles=roles, user_text=user_text)
    plan["scene_mood"] = _text(plan.get("scene_mood")) or human_context["scene_mood"]
    plan["scene_mood_shift"] = _text(plan.get("scene_mood_shift")) or scene_mood_shift(plan["scene_mood"])
    plan["addressed_targets"] = addressed_targets
    if addressing_warning:
        plan["addressing_warning"] = addressing_warning
    elif off_scene and on_scene:
        missing = "、".join(_role_display_name(role) for role in off_scene)
        plan["addressing_warning"] = f"已安排在场角色回应；「{missing}」未到场可对话。"
    return plan
