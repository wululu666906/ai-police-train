"""Human-like scene dynamics for multi-role police training dialogue.

This module stays intentionally stateless: it turns role snapshots, persona
metadata, current learner input, and peer utterances into compact behavioral
instructions that the director and actor prompts can use.
"""

from __future__ import annotations

import json
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _score(value: Any, fallback: int = 50) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0, min(100, numeric))


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _has_meaningful_items(value: Any) -> bool:
    if isinstance(value, list):
        return any(_text(item) for item in value)
    if isinstance(value, dict):
        return any(_text(item) for item in value.values())
    clean = _text(value)
    if not clean or clean.lower() in {"null", "none", "无", "没有", "[]", "{}"}:
        return False
    try:
        parsed = json.loads(clean)
    except Exception:
        return True
    return _has_meaningful_items(parsed)


def _role_name(role: Any) -> str:
    return _text(getattr(role, "name", "")) or "相关人员"


def _role_type(role: Any) -> str:
    return _text(getattr(role, "role_type", ""))


def _archetype(role: Any, persona_profile: dict[str, Any] | None = None) -> str:
    profile = persona_profile or {}
    return _text(profile.get("behavior_archetype")) or _text(getattr(role, "behavior_archetype", ""))


def _snap(snapshot: dict[str, Any] | None, role: Any) -> dict[str, int]:
    snapshot = snapshot or {}
    return {
        "emotion": _score(snapshot.get("emotion"), _score(getattr(role, "init_emotion", None), 50)),
        "cooperation": _score(snapshot.get("cooperation"), _score(getattr(role, "init_trust", None), 30)),
        "risk": _score(snapshot.get("risk"), _score(getattr(role, "init_risk", None), 50)),
        "clarity": _score(snapshot.get("clarity"), _score(getattr(role, "init_expression_clarity", None), 50)),
    }


REACTION_LIBRARY: dict[str, dict[str, Any]] = {
    "argumentative_dispute": {
        "label": "争执型",
        "delivery": "angry",
        "rules": [
            "允许针对对方刚才的话反驳、抢白或纠正，但不要脱离案件事实。",
            "不要一次讲完全部经过，先抓住最在意的一点争辩。",
        ],
        "state_delta": {"emotion": 5, "cooperation": -3, "risk": 4, "clarity": -1},
    },
    "grievance_vent": {
        "label": "委屈倾诉型",
        "delivery": "sad",
        "rules": [
            "先表达委屈、损失或害怕被忽视，再补一小段事实。",
            "会重复核心诉求，但不能变成说明书式总结。",
        ],
        "state_delta": {"emotion": 2, "cooperation": 1, "risk": 0, "clarity": -1},
    },
    "defensive_denial": {
        "label": "防御否认型",
        "delivery": "defensive",
        "rules": [
            "先淡化责任、切割关键行为或反问民警依据。",
            "被问到证据、监控、伤情、时间线矛盾时只允许松动一小步。",
        ],
        "state_delta": {"emotion": 2, "cooperation": -4, "risk": 2, "clarity": 0},
    },
    "avoidant_silence": {
        "label": "回避沉默型",
        "delivery": "hesitant",
        "rules": [
            "回答短、含糊，先说没看清、记不准或不想惹事。",
            "只有民警降低顾虑或明确保护边界后，才补充更具体内容。",
        ],
        "state_delta": {"emotion": 0, "cooperation": -2, "risk": 1, "clarity": -3},
    },
    "protective_fear": {
        "label": "求保护型",
        "delivery": "anxious",
        "rules": [
            "优先确认自身或家人是否安全，追问警方下一步怎么保护。",
            "事实表达会被担心打断，可先说最紧急的一点。",
        ],
        "state_delta": {"emotion": 3, "cooperation": 1, "risk": 3, "clarity": -2},
    },
    "chaotic_confusion": {
        "label": "混乱失序型",
        "delivery": "anxious",
        "rules": [
            "表达可以跳跃、重复、跑题，但每条台词仍要能被学员理解。",
            "抓住一个刺激点反复说，等待民警控场或分离双方。",
        ],
        "state_delta": {"emotion": 4, "cooperation": -2, "risk": 5, "clarity": -5},
    },
    "provocative_challenge": {
        "label": "挑衅对抗型",
        "delivery": "angry",
        "rules": [
            "可以顶嘴、质疑民警是否偏袒，但不能辱骂或脱离训练边界。",
            "被强压时更抗拒，被稳住台阶时才可能稍微降温。",
        ],
        "state_delta": {"emotion": 5, "cooperation": -5, "risk": 5, "clarity": -2},
    },
    "topic_shift_bargain": {
        "label": "转移讨价型",
        "delivery": "defensive",
        "rules": [
            "被问关键点时转向赔偿、面子、家庭后果或对方责任。",
            "不要正面完整承认隐藏事实，用现实顾虑拖住对话。",
        ],
        "state_delta": {"emotion": 1, "cooperation": -3, "risk": 1, "clarity": -1},
    },
    "sudden_cooperation": {
        "label": "突然配合型",
        "delivery": "calm",
        "rules": [
            "被安抚、分离或说明程序后，语气缓和并愿意补充可核实细节。",
            "仍按掌握事实边界说，不主动替其他人下结论。",
        ],
        "state_delta": {"emotion": -5, "cooperation": 5, "risk": -4, "clarity": 3},
    },
    "probing_observation": {
        "label": "试探观察型",
        "delivery": "normal",
        "rules": [
            "先看民警态度，问一句答一句，不主动展开敏感内容。",
            "可以要求民警把问题问具体，避免一次性倾倒全部信息。",
        ],
        "state_delta": {"emotion": 0, "cooperation": 0, "risk": 0, "clarity": 0},
    },
}


SCENE_MOOD_LABELS = {
    "stable": "平稳",
    "tense": "升温",
    "deadlock": "僵持",
    "chaotic": "混乱",
    "deescalate": "缓和",
    "edge_loss_control": "失控边缘",
}


def infer_scene_mood(
    *,
    user_text: str,
    roles: list[Any],
    role_snapshots: dict[str, dict[str, Any]] | None = None,
    interaction_mode: str = "",
) -> str:
    text = _text(user_text)
    snapshots = role_snapshots or {}
    role_states = [_snap(snapshots.get(str(getattr(role, "id", ""))), role) for role in roles]
    max_emotion = max((item["emotion"] for item in role_states), default=50)
    max_risk = max((item["risk"] for item in role_states), default=50)
    min_cooperation = min((item["cooperation"] for item in role_states), default=50)
    min_clarity = min((item["clarity"] for item in role_states), default=50)

    if _contains_any(text, ("冷静", "别激动", "分开", "慢慢说", "一个一个", "先坐下", "我会处理")):
        return "deescalate"
    if max_risk >= 88 or _contains_any(text, ("别碰", "放下", "刀", "砸", "冲过去", "控制住")):
        return "edge_loss_control"
    if min_clarity <= 28 or _contains_any(text, ("喝多", "醉", "乱", "围观", "起哄")):
        return "chaotic"
    if interaction_mode == "interrupt_chain" or max_emotion >= 76 or max_risk >= 72:
        return "tense"
    if min_cooperation <= 22:
        return "deadlock"
    return "stable"


def scene_mood_shift(scene_mood: str) -> str:
    if scene_mood == "deescalate":
        return "deescalate"
    if scene_mood in {"tense", "chaotic", "edge_loss_control", "deadlock"}:
        return "tense"
    return "stable"


def build_director_human_context(
    *,
    roles: list[Any],
    role_snapshots: dict[str, dict[str, Any]] | None,
    user_text: str,
    interaction_mode: str = "",
) -> dict[str, Any]:
    scene_mood = infer_scene_mood(
        user_text=user_text,
        roles=roles,
        role_snapshots=role_snapshots,
        interaction_mode=interaction_mode,
    )
    lines = [f"现场气氛建议：{SCENE_MOOD_LABELS.get(scene_mood, scene_mood)}（scene_mood={scene_mood}）"]
    for role in roles:
        snap = _snap((role_snapshots or {}).get(str(getattr(role, "id", ""))), role)
        reaction = choose_role_reaction(
            role=role,
            role_snapshot=snap,
            user_text=user_text,
            scene_mood=scene_mood,
        )
        labels = " + ".join(reaction.get("labels") or [reaction.get("label") or "试探观察型"])
        lines.append(
            f"- {_role_name(role)}：本轮反应组合「{labels}」，"
            f"情绪{snap['emotion']} 配合{snap['cooperation']} 风险{snap['risk']} 清晰{snap['clarity']}"
        )
    return {
        "scene_mood": scene_mood,
        "scene_mood_shift": scene_mood_shift(scene_mood),
        "block": "\n".join(lines),
    }


def choose_role_reaction(
    *,
    role: Any,
    role_snapshot: dict[str, Any] | None,
    user_text: str,
    scene_mood: str = "",
    persona_profile: dict[str, Any] | None = None,
    cast_entry: dict[str, Any] | None = None,
    peer_utterances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    snap = _snap(role_snapshot, role)
    text = _text(user_text)
    role_type = _role_type(role)
    archetype = _archetype(role, persona_profile)
    participation = _text((cast_entry or {}).get("participation"))
    intent = _text((cast_entry or {}).get("intent"))
    has_peer = bool(peer_utterances)
    has_hidden = _has_meaningful_items(getattr(role, "hidden_truths", ""))

    scores: dict[str, int] = {key: 0 for key in REACTION_LIBRARY}
    reasons: dict[str, list[str]] = {key: [] for key in REACTION_LIBRARY}

    def add(key: str, points: int, reason: str) -> None:
        scores[key] = scores.get(key, 0) + points
        reasons.setdefault(key, []).append(reason)

    if scene_mood == "deescalate":
        add("sudden_cooperation", 8 if snap["cooperation"] >= 25 else 4, "民警正在安抚/分离/控场")
        add("probing_observation", 2, "缓和后仍会观察警方态度")
    if scene_mood in {"tense", "deadlock"}:
        add("argumentative_dispute", 3, "现场气氛紧张或僵持")
    if scene_mood in {"chaotic", "edge_loss_control"}:
        add("chaotic_confusion", 8, "现场混乱或接近失控")
        add("protective_fear", 2, "现场风险引发安全顾虑")
    if "醉" in archetype or "酒" in archetype or "醉" in _text(getattr(role, "status", "")):
        add("chaotic_confusion", 8, "酒精或混乱状态影响表达")
        add("provocative_challenge", 2, "酒后更容易顶撞")
    if snap["risk"] >= 84 and snap["cooperation"] <= 24:
        add("provocative_challenge", 8, "高风险且低配合")
        add("argumentative_dispute", 3, "容易抢话争辩")
    if snap["clarity"] <= 28:
        add("chaotic_confusion", 8, "表达清晰度很低")
    if snap["emotion"] >= 76 and (participation == "interrupt" or has_peer or scene_mood == "tense"):
        add("argumentative_dispute", 7, "情绪高且受到对方/现场刺激")
    if has_peer:
        add("argumentative_dispute", 3, "已经听到对方发言，需要接话或反驳")
    if _contains_any(text, ("保护", "报复", "安全吗", "害怕", "家里", "孩子")) or "创伤" in archetype:
        add("protective_fear", 8, "学员触及安全、报复或保护顾虑")
        add("avoidant_silence", 2, "害怕牵连时会先保留")
    if has_hidden and (
        snap["cooperation"] <= 35
        or _contains_any(text, ("证据", "监控", "伤情", "时间线", "谁先", "矛盾", "承认"))
        or "嫌疑" in role_type
        or "违法" in role_type
    ):
        add("defensive_denial", 8, "存在隐瞒事实且被触及责任/证据")
        add("topic_shift_bargain", 2, "可能转移到后果或处理方式")
    if snap["cooperation"] <= 22 or "回避" in archetype or ("证" in role_type and snap["cooperation"] <= 40):
        add("avoidant_silence", 7, "低配合或怕牵连")
    if intent == "vent" or "委屈" in archetype or "报警" in role_type or "受害" in role_type or "被害" in role_type:
        add("grievance_vent", 7, "身份/意图倾向先表达委屈诉求")
    if _contains_any(text, ("赔", "赔偿", "道歉", "算了", "私了", "面子", "工作", "家属")):
        add("topic_shift_bargain", 8, "学员触及赔偿、面子或现实后果")
    if snap["cooperation"] >= 65:
        add("sudden_cooperation", 5, "配合度较高，愿意补充事实")
    add("probing_observation", 1, "默认保持观察，不一次性说完")

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    primary_key = ranked[0][0] if ranked and ranked[0][1] > 1 else "probing_observation"
    companion_keys = [
        key
        for key, score in ranked
        if key != primary_key and score >= 3 and not (primary_key == "sudden_cooperation" and key == "argumentative_dispute")
    ][:2]
    keys = [primary_key, *companion_keys]

    reaction = dict(REACTION_LIBRARY[primary_key])
    reaction["key"] = primary_key
    reaction["keys"] = keys
    reaction["primary_key"] = primary_key
    reaction["companion_keys"] = companion_keys
    reaction["labels"] = [REACTION_LIBRARY[key]["label"] for key in keys]
    reaction["score_map"] = {key: score for key, score in scores.items() if score > 0}
    reaction["reasons"] = {key: reasons.get(key, []) for key in keys}
    merged_rules: list[str] = []
    for key in keys:
        for rule in REACTION_LIBRARY[key].get("rules") or []:
            if rule not in merged_rules:
                merged_rules.append(rule)
    reaction["rules"] = merged_rules[:6]
    reaction["label"] = reaction["labels"][0]
    reaction["scene_mood"] = scene_mood or "stable"
    reaction["delivery"] = reaction.get("delivery") or "normal"
    return reaction


def format_actor_reaction_block(reaction: dict[str, Any], peer_utterances: list[dict[str, Any]] | None = None) -> str:
    rules = reaction.get("rules") if isinstance(reaction.get("rules"), list) else []
    peer_hint = "本轮尚无其他角色发言。"
    if peer_utterances:
        names = []
        for item in peer_utterances:
            name = _text(item.get("speaker_name"))
            if name and name not in names:
                names.append(name)
        if names:
            peer_hint = f"你已经听到{'、'.join(names)}本轮发言，必须对其中与你立场冲突或相关的内容作出自然反应。"
    lines = [
        f"- 现场气氛：{SCENE_MOOD_LABELS.get(_text(reaction.get('scene_mood')), _text(reaction.get('scene_mood')) or '平稳')}",
        f"- 本轮主反应：{reaction.get('label') or '试探观察型'}",
        f"- 本轮辅助反应：{' + '.join(reaction.get('labels', [])[1:]) or '无'}",
        "- 重要：反应类型不是固定性格标签，只是本轮受学员话术、现场气氛、本人状态和对方发言共同触发的临时组合。",
        f"- 推荐语气 delivery：{reaction.get('delivery') or 'normal'}",
        f"- 同场听觉：{peer_hint}",
    ]
    lines.extend(f"- 行为要求：{rule}" for rule in rules)
    return "\n".join(lines)


def merge_reaction_delta(base_delta: dict[str, Any] | None, reaction: dict[str, Any] | None) -> dict[str, int]:
    base_delta = base_delta or {}
    reaction_deltas: list[dict[str, Any]] = []
    if isinstance(reaction, dict):
        keys = reaction.get("keys") if isinstance(reaction.get("keys"), list) else []
        for key in keys[:3]:
            delta = REACTION_LIBRARY.get(str(key), {}).get("state_delta")
            if isinstance(delta, dict):
                reaction_deltas.append(delta)
        if not reaction_deltas and isinstance(reaction.get("state_delta"), dict):
            reaction_deltas.append(reaction["state_delta"])
    merged: dict[str, int] = {}
    for axis in ("emotion", "cooperation", "risk", "clarity"):
        total = int(base_delta.get(axis, 0) or 0)
        for index, delta in enumerate(reaction_deltas):
            weight = 1.0 if index == 0 else 0.45
            total += round(int(delta.get(axis, 0) or 0) * weight)
        merged[axis] = max(-15, min(15, total))
    return merged


def reaction_preface(role: Any, reaction: dict[str, Any], peer_utterances: list[dict[str, Any]] | None = None) -> str:
    name = _role_name(role)
    key = _text(reaction.get("key"))
    if key == "argumentative_dispute":
        return f"{name}，你别把话说成那样。"
    if key == "defensive_denial":
        return "你们先别急着把责任都往我身上扣。"
    if key == "avoidant_silence":
        return "我不太想掺和这个事，我只能说我确定看到的。"
    if key == "protective_fear":
        return "你们先告诉我，我现在说了会不会还有麻烦？"
    if key == "chaotic_confusion":
        return "等一下，我脑子有点乱，你让我缓一口气。"
    if key == "provocative_challenge":
        return "你们是不是一来就认定是我的问题？"
    if key == "topic_shift_bargain":
        return "这事能不能先说怎么处理，别一上来就问责任。"
    if key == "sudden_cooperation":
        return "行，我按你说的慢慢讲。"
    if key == "grievance_vent":
        return "我就是觉得这事不能这么算了。"
    return ""
