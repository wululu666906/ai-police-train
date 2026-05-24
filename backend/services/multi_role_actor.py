"""Per-role actor: each selected character generates 1-8 utterances with own persona."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import models
from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
from .persona_engine import (
    analyze_dialogue_momentum,
    build_persona_profile,
    build_role_script,
    format_persona_block,
)
from .multi_role_service import _build_history_block, _role_display_name

ROLE_ACTOR_PROMPT = """
你正在扮演警情训练场景中的角色「{role_name}」，根据导演编排意图说出台词。

【导演编排】
- 互动模式：{interaction_mode}
- 你的参与方式：{participation}
- 本次连续发言最多 {utterance_count} 条台词（可少于该数，不可超过）；多条之间学员无需回复，你应顺着同一段思路往下说
- 发言意图：{intent}
- 触发原因：{trigger_reason}

【场景】{scene_name}  阶段：{current_stage}
【学员刚才说】{user_text}

【你的人设与状态】
{persona_block}

【你掌握的事实边界】
已知：{knows_facts}
不可透露：{hidden_truths}
不知道：{does_not_know}

【近期对话】
{history_block}

【视角约束】
{perspective_hint}

要求：
1. 一次生成 utterances 数组，含 1 到 utterance_count 条连续台词；每条对应界面一个气泡，条与条之间是同一角色接着说完，不是等学员回话再说下一句。
2. 多条台词应语义连贯、递进或补充，像真人一口气把话讲完，不要每条都重复同义。
3. 必须符合你的人设、情绪、配合度；不能串戏、不能全知。
4. 严禁用第一人称「我」冒充学员点名的其他角色作答；若你是证人/家属且学员在问别人，请用第三人称转述你观察到的情况。
5. 若 participation=interrupt，第一句可带打断感；若 calm_scene 模式，情绪应略有缓和但仍保角色性格。
6. 只输出 JSON：

{{
  "utterances": [
    {{"content": "第一句台词", "delivery": "angry"}},
    {{"content": "第二句台词", "delivery": "normal"}}
  ],
  "inner_thought": "心理活动",
  "state_delta": {{"emotion": 0, "cooperation": 0, "risk": 0, "clarity": 0}},
  "new_fact_revealed": null
}}
"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _format_facts(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(_text(item) for item in value if _text(item)) or "（无）"
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return "、".join(_text(item) for item in parsed if _text(item)) or "（无）"
        except Exception:
            pass
        return value or "（无）"
    return "（无）"


def _clamp_delta(value: Any, low: int = -15, high: int = 15) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(low, min(high, numeric))


def _rule_based_utterances(
    role: models.Role,
    cast_entry: dict[str, Any],
    user_text: str,
    utterance_count: int,
) -> dict[str, Any]:
    name = _role_display_name(role)
    participation = _text(cast_entry.get("participation"))
    lines: list[str] = []
    if participation == "interrupt":
        lines.append(f"{name}，你等一下，事情不是那样！")
    if "冷静" in user_text or "别激动" in user_text:
        lines.append("我知道你们是警察，我说就是了。")
    if "经过" in user_text or "怎么回事" in user_text:
        lines.append("事情是这样的，刚才确实吵了几句。")
    if not lines:
        lines.append("……你问的这些，我得想想怎么说。")
    while len(lines) < utterance_count:
        lines.append("反正我说的都是实话。")
    lines = lines[:utterance_count]
    return {
        "utterances": [{"content": line, "delivery": "normal"} for line in lines],
        "inner_thought": "先稳住，看看警察怎么问。",
        "state_delta": {"emotion": -2, "cooperation": 3, "risk": -1, "clarity": 2},
        "new_fact_revealed": None,
    }


def _build_perspective_hint(
    role: models.Role,
    user_text: str,
    cast_entry: dict[str, Any],
    addressed_targets: Optional[list[str]] = None,
) -> str:
    self_name = _role_display_name(role)
    intent = _text(cast_entry.get("intent"))
    others = []
    for name in addressed_targets or []:
        clean = _text(name)
        if clean and clean != self_name and clean not in others:
            others.append(clean)
    if not others:
        text = _text(user_text)
        for name in addressed_targets or []:
            if name and name != self_name and name in text:
                others.append(name)
    if intent == "witness_account" or others:
        joined = "、".join(others) if others else "对方"
        return (
            f"你是「{self_name}」（{_text(role.role_type) or '相关人员'}）。"
            f"学员主要在问「{joined}」，你必须以本人/旁观者身份回答，禁止用「我」冒充{joined}的第一人称经历。"
        )
    return f"你是「{self_name}」，必须以本人第一人称回答，不要替其他角色说话。"


def generate_role_dialogue(
    *,
    role: models.Role,
    cast_entry: dict[str, Any],
    director_plan: dict[str, Any],
    scene: Optional[models.Scene],
    case: Optional[models.Case],
    history: list[Any],
    user_text: str,
    current_stage: str,
    role_snapshot: dict[str, int],
    addressed_targets: Optional[list[str]] = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    utterance_count = max(1, min(8, int(cast_entry.get("utterance_count") or 1)))
    profile = build_persona_profile(role, case, scene)
    script = build_role_script(role, case, scene, profile)
    momentum = analyze_dialogue_momentum(
        user_text,
        profile,
        "",
        role_snapshot.get("cooperation", 30),
        role_snapshot.get("emotion", 50),
    )
    persona_block = format_persona_block(profile, script, {}, momentum)
    perspective_hint = _build_perspective_hint(
        role,
        user_text,
        cast_entry,
        addressed_targets or director_plan.get("addressed_targets"),
    )

    output: Optional[dict[str, Any]] = None
    if use_llm:
        prompt = ROLE_ACTOR_PROMPT.format(
            role_name=_role_display_name(role),
            interaction_mode=_text(director_plan.get("interaction_mode")) or "mixed",
            participation=_text(cast_entry.get("participation")) or "primary_respond",
            utterance_count=utterance_count,
            intent=_text(cast_entry.get("intent")) or "respond",
            trigger_reason=_text(cast_entry.get("trigger_reason")) or "现场对话",
            scene_name=_text(getattr(scene, "name", "")) or "现场",
            current_stage=current_stage or "训练中",
            user_text=user_text or "（学员沉默）",
            persona_block=persona_block,
            perspective_hint=perspective_hint,
            knows_facts=_format_facts(getattr(role, "knows_facts", [])),
            hidden_truths=_format_facts(getattr(role, "hidden_truths", [])),
            does_not_know=_format_facts(getattr(role, "does_not_know", [])),
            history_block=_build_history_block(history),
        )
        try:
            response = create_json_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.82,
                model=get_chat_model(),
                max_tokens=1800,
            )
            raw = extract_message_text(response) or ""
            match = re.search(r"\{[\s\S]*\}", raw)
            payload = json.loads(match.group(0) if match else raw)
            utterances = payload.get("utterances") if isinstance(payload.get("utterances"), list) else []
            cleaned = []
            for item in utterances[:utterance_count]:
                if isinstance(item, dict) and _text(item.get("content")):
                    cleaned.append({"content": _text(item.get("content")), "delivery": _text(item.get("delivery")) or "normal"})
                elif isinstance(item, str) and _text(item):
                    cleaned.append({"content": _text(item), "delivery": "normal"})
            if cleaned:
                delta = payload.get("state_delta") if isinstance(payload.get("state_delta"), dict) else {}
                output = {
                    "utterances": cleaned,
                    "inner_thought": _text(payload.get("inner_thought")) or "",
                    "state_delta": {
                        "emotion": _clamp_delta(delta.get("emotion")),
                        "cooperation": _clamp_delta(delta.get("cooperation")),
                        "risk": _clamp_delta(delta.get("risk")),
                        "clarity": _clamp_delta(delta.get("clarity")),
                    },
                    "new_fact_revealed": payload.get("new_fact_revealed"),
                }
        except Exception:
            output = None

    if not output:
        output = _rule_based_utterances(role, cast_entry, user_text, utterance_count)

    return {
        "speaker_name": _role_display_name(role),
        "speaker_role_id": role.id,
        "role": role,
        "participation": cast_entry.get("participation"),
        "utterances": output["utterances"][:utterance_count],
        "inner_thought": output.get("inner_thought") or "",
        "state_delta": output.get("state_delta") or {},
        "new_fact_revealed": output.get("new_fact_revealed"),
        "updated_snapshot": _apply_snapshot_delta(role_snapshot, output.get("state_delta") or {}),
    }


def _apply_snapshot_delta(snapshot: dict[str, int], delta: dict[str, Any]) -> dict[str, int]:
    base = dict(snapshot or {})
    for key in ("emotion", "cooperation", "risk", "clarity"):
        base[key] = max(0, min(100, int(base.get(key, 50)) + _clamp_delta(delta.get(key))))
    return base
