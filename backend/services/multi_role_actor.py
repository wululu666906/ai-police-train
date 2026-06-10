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
from .state_influence_engine import (
    apply_delivery_from_contract,
    build_state_contract,
    enrich_momentum_with_axis_deltas,
    format_state_contract_block,
)
from .canonical_facts_service import (
    extract_canonical_facts,
    format_canonical_facts_block,
    format_peer_utterances_block,
    merge_role_knows_facts,
)
from .dialogue_sanitize_service import sanitize_utterances
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

【本轮表现契约（必须严格遵守）】
{state_contract_block}

【案件基准事实（全角色必须一致，不得互相矛盾）】
{canonical_facts_block}

【你掌握的事实边界】
已知：{knows_facts}
不可透露：{hidden_truths}
不知道：{does_not_know}

【本轮已发言角色（勿与其时间/地点说法矛盾）】
{peer_utterances_block}

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
6. 若你是违法嫌疑人、配合度较低、lying_ability 较高，且 hidden_truths 不为空：初期不要主动承认 hidden_truths，可用淡化、推责、记不清、反问来回避；只有当学员明确追问证据、监控、证人、伤情、时间线矛盾时，才允许部分改口或松动。
7. 若学员只是笼统问“具体点/说清楚”，不要自动交代所有事实；应反问其要问时间、地点、谁先动手、证据还是伤情。
8. 若学员拿出证据或指出矛盾，回复中应体现被击中的心理变化：停顿、犹豫、缩小说法、改口一小步，而不是突然完整认罪。
9. 必须优先回应【学员刚才说】这一句；【近期对话】只能作为背景，不能把历史里的问题说成学员本轮刚问的问题。
10. 如果学员刚才是在告知、安抚、说明已采取措施（例如“已经叫救护车/已经通知/请稍等”），应回应这项措施是否让你安心、是否继续催促、需要什么确认；不得说“你们光问”“你刚才问这些”“你不是问了吗”等把历史追问当成本轮提问的话。
11. 人设配置（如核心顾虑、当前诉求、触发点）仅用于决定语气与反应，禁止在台词中念出字段名、配置原文或「我最怕的就是XXX」这类说明书句式；把担心融入自然口语。
12. 被问时间、地点时，若【案件基准事实】或【已知】中有标准答案，必须与其一致；证人可说「大概/记不清」，但不得换成不同路口或相差超过1小时的时间。
13. 严格遵守【视角约束】中的身份边界：若提示你是旁观者/证人，禁止用第一人称「我」替被问对象回答经历。
14. delivery 取值及含义：
    - normal：平常语气
    - angry：愤怒、激动
    - anxious：焦急、不安
    - sad：委屈、低落
    - defensive：防御、辩解
    - calm：冷静、缓和
    - hesitant：犹豫、吞吞吐吐
15. new_fact_revealed 只有在本轮确实新增了一条关键事实时才填写该事实文本，否则填 null。
16. state_delta 是四个轴的变化量（范围-15 到 +15），不是绝对值；没有明显变化时写 0，不要整条不填。
17. 注意：以下输出格式中的值为示例（delivery、数字等），请根据角色状态和本轮互动动态决定，不要照搬。只输出 JSON：

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


def _looks_like_question(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"[？?]|吗|么|什么|哪里|哪儿|几点|多久|是否|有没有|为什么|怎么|能不能", text))


def _acknowledges_action(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"已经|已|马上|正在|通知|叫.*救护车|救护车|120|请稍等|稍等|安排|派人|到场", text))


def _sanitize_utterances_for_last_user(utterances: list[dict[str, str]], user_text: str) -> list[dict[str, str]]:
    """Keep role replies anchored to the latest learner message, not stale history."""
    if _looks_like_question(user_text) or not _acknowledges_action(user_text):
        return utterances

    stale_question_patterns = (
        "你们别光问",
        "你们就光问",
        "光问这些",
        "你刚才问",
        "你们刚才问",
        "你不是问",
        "倒是问",
    )
    sanitized: list[dict[str, str]] = []
    replaced = False
    for item in utterances:
        content = _text(item.get("content"))
        if any(pattern in content for pattern in stale_question_patterns):
            if not replaced:
                sanitized.append(
                    {
                        "content": "那你们帮我确认一下，救护车到底什么时候能到？人现在还在这儿，我心里没底。",
                        "delivery": item.get("delivery") or "anxious",
                    }
                )
                replaced = True
            continue
        sanitized.append(item)
    return sanitized or utterances


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _string_items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, dict):
        primitive_values = [
            _text(item)
            for item in value.values()
            if not isinstance(item, (dict, list)) and _text(item)
        ]
        if primitive_values:
            return [" ".join(primitive_values)]
        items = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                items.extend(_string_items(item))
            else:
                text = _text(item)
                if text:
                    items.append(f"{key}：{text}")
        return items
    if isinstance(value, list):
        items = []
        for item in value:
            items.extend(_string_items(item))
        return items
    text = _text(value)
    return [text] if text else []


def _structured_items(case: Optional[models.Case], *keys: str) -> list[str]:
    data = _json_dict(getattr(case, "structured_data", None))
    for key in keys:
        value = data.get(key)
        if value is not None:
            items = _string_items(value)
            if items:
                return items
    return []


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _first_time_fact(case: Optional[models.Case]) -> str:
    timeline = _structured_items(case, "timeline", "时间线", "events", "事件")
    for item in timeline:
        match = re.search(r"\d{1,2}[:：]\d{2}", item)
        if match:
            return item
    return timeline[0] if timeline else ""


def _location_fact(scene: Optional[models.Scene], case: Optional[models.Case]) -> str:
    source = " ".join(
        _text(value)
        for value in (
            getattr(scene, "dispatch_brief", ""),
            getattr(scene, "first_impression", ""),
            getattr(scene, "description", ""),
            getattr(case, "background", ""),
        )
        if _text(value)
    )
    patterns = (
        r"[\u4e00-\u9fa5A-Za-z0-9]+(?:店|门口|路|街|巷|小区|市场|夜市|广场|现场|附近)",
        r"在([^，。；、\s]{2,20})",
    )
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return ""


def _role_fact(role: models.Role, case: Optional[models.Case]) -> str:
    name = _role_display_name(role)
    role_type = _text(getattr(role, "role_type", ""))
    people = _structured_items(case, "persons", "people", "人物", "相关人员")
    for person in people:
        if name and name in person:
            tokens = [token for token in re.split(r"\s+", person.replace(name, " ").strip()) if token]
            if role_type:
                tokens.append(role_type)
            deduped = list(dict.fromkeys(tokens))
            return " ".join(deduped)
    return role_type


def _append_unique(lines: list[str], line: str) -> None:
    clean = _text(line)
    if clean and clean not in lines:
        lines.append(clean)


def _role_voice(role: models.Role) -> str:
    role_type = _text(getattr(role, "role_type", ""))
    name = _role_display_name(role)
    if "被害" in role_type or "受害" in role_type or "赵阳" in name:
        return "victim"
    if "嫌疑" in role_type or "违法" in role_type or "刘军" in name:
        return "suspect"
    if "证" in role_type or "旁观" in role_type:
        return "witness"
    return "neutral"


def _time_reply(role: models.Role, time_fact: str) -> str:
    voice = _role_voice(role)
    if voice == "victim":
        return f"我记得差不多是{time_fact}，那会儿我和他已经在收银台那边吵起来了。"
    if voice == "suspect":
        return f"大概是{time_fact}吧。我当时喝了酒，时间可能没那么准。"
    if voice == "witness":
        return f"我看到的时候大概是{time_fact}，他们两个已经吵起来了。"
    return f"我记得大概是{time_fact}。"


def _identity_reply(role: models.Role, role_fact: str) -> list[str]:
    name = _role_display_name(role)
    voice = _role_voice(role)
    if voice == "victim":
        return [f"我是{name}，被打的是我，算是这事里的被害人。", "我现在就是想把当时怎么起冲突、谁先动手说清楚。"]
    if voice == "suspect":
        return [f"我是{name}。", "我和赵阳是起了冲突，但你们也先别一上来就说全是我的问题。"]
    if voice == "witness":
        return [f"我是{name}，我是在现场看到情况的人。"]
    if role_fact:
        return [f"我是{name}，{role_fact}。"]
    return [f"我是{name}，当时就在现场。"]


def _vague_reply(role: models.Role) -> str:
    voice = _role_voice(role)
    if voice == "victim":
        return "你问哪一段？是问他怎么动手，还是问我伤在哪儿？"
    if voice == "suspect":
        return "你问清楚点行不行？时间、地点、还是问谁先动的手？"
    if voice == "witness":
        return "你问具体哪一段，我只说我亲眼看到的。"
    return "你把问题说具体一点，我好回答。"


def _rule_based_utterances(
    role: models.Role,
    cast_entry: dict[str, Any],
    user_text: str,
    utterance_count: int,
    scene: Optional[models.Scene] = None,
    case: Optional[models.Case] = None,
) -> dict[str, Any]:
    name = _role_display_name(role)
    role_type = _text(getattr(role, "role_type", ""))
    participation = _text(cast_entry.get("participation"))
    text = _text(user_text)
    background = _text(getattr(case, "background", ""))
    first_impression = _text(getattr(scene, "first_impression", ""))
    canonical = extract_canonical_facts(case, scene)
    time_fact = canonical.get("case_time") if canonical.get("case_time") != "未明确" else _first_time_fact(case)
    location = canonical.get("case_location") if canonical.get("case_location") != "未明确" else _location_fact(scene, case)
    evidence = _structured_items(case, "evidence_points", "evidence", "证据", "证据要点")
    people = _structured_items(case, "persons", "people", "人物", "相关人员")
    role_fact = _role_fact(role, case)
    voice = _role_voice(role)
    lines: list[str] = []
    if participation == "interrupt":
        _append_unique(lines, f"{name}，你等一下，事情不是那样！")
    if _contains_any(text, ("冷静", "别激动", "放松", "慢慢说")):
        if voice == "suspect":
            _append_unique(lines, "行，我先不吵了。但你让我把话说完。")
        elif voice == "victim":
            _append_unique(lines, "我可以慢慢说，但他刚才确实动手了。")
        else:
            _append_unique(lines, "我配合，你问哪一段我说哪一段。")
    if _contains_any(text, ("身份", "你是谁", "叫什么", "关系")):
        for line in _identity_reply(role, role_fact):
            _append_unique(lines, line)
    if _contains_any(text, ("几点", "时间", "什么时候", "发生")) and time_fact:
        _append_unique(lines, _time_reply(role, time_fact))
    if _contains_any(text, ("哪里", "地点", "位置", "在哪", "现场")) and location:
        if voice == "suspect":
            _append_unique(lines, f"就在{location}，旁边人不少，我也不想在那儿丢这个脸。")
        elif voice == "victim":
            _append_unique(lines, f"就在{location}，当时旁边有人围着看。")
        else:
            _append_unique(lines, f"地点是在{location}，我是在旁边看到的。")
    if _contains_any(text, ("伤", "打", "疼", "伤情", "动手")):
        if voice == "victim":
            _append_unique(lines, "我眉弓这边被他打到了，现在还疼。")
        elif voice == "suspect":
            _append_unique(lines, "我承认有推搡，也碰到他了，但当时是吵急了。")
        elif voice == "witness":
            _append_unique(lines, "我看到他们有推搡，后来赵阳脸这边像是被打到了。")
    if _contains_any(text, ("证据", "监控", "证人", "谁看见", "付款")):
        fact = "；".join(evidence[:2]) if evidence else ""
        witness = next((item for item in people if "证人" in item or "孙桂兰" in item), "")
        if fact:
            _append_unique(lines, f"你们可以去看{fact}，别光听我们在这儿吵。")
        if witness:
            _append_unique(lines, f"{witness}，她当时也在，可以问她。")
    if _contains_any(text, ("经过", "怎么回事", "原因", "起因")):
        if voice == "suspect":
            _append_unique(lines, "一开始就是结账那点事吵起来的，我喝了酒，话赶话就急了。")
        elif voice == "victim":
            _append_unique(lines, "就是结账插队那点事，他说话冲，后面就推我、打到我脸上。")
        elif voice == "witness":
            _append_unique(lines, "我看到他们先因为结账的事吵，后来声音越来越大，就有人动手了。")
        elif background:
            _append_unique(lines, background)
        else:
            _append_unique(lines, "刚才确实先吵了几句，后来才动了手。")
    if first_impression and len(lines) < utterance_count and _contains_any(text, ("现场", "情况", "人多")):
        _append_unique(lines, first_impression)
    if not lines:
        _append_unique(lines, _vague_reply(role))
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
    peer_utterances: Optional[list[dict[str, Any]]] = None,
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
    momentum = enrich_momentum_with_axis_deltas(momentum, user_text, [])
    state_contract = build_state_contract(role_snapshot, momentum)
    persona_block = format_persona_block(profile, script, {}, momentum)
    state_contract_block = format_state_contract_block(state_contract)
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
            state_contract_block=state_contract_block,
            perspective_hint=perspective_hint,
            canonical_facts_block=format_canonical_facts_block(case, scene),
            knows_facts=merge_role_knows_facts(role, case),
            hidden_truths=_format_facts(getattr(role, "hidden_truths", [])),
            does_not_know=_format_facts(getattr(role, "does_not_know", [])),
            peer_utterances_block=format_peer_utterances_block(peer_utterances or []),
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
                cleaned = sanitize_utterances(cleaned)
                cleaned = _sanitize_utterances_for_last_user(cleaned, user_text)
                cleaned = apply_delivery_from_contract(cleaned, state_contract)
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
        output = _rule_based_utterances(role, cast_entry, user_text, utterance_count, scene, case)
    else:
        output["utterances"] = sanitize_utterances(
            _sanitize_utterances_for_last_user(output.get("utterances") or [], user_text)
        )

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
        "state_contract": state_contract,
    }


def _apply_snapshot_delta(snapshot: dict[str, int], delta: dict[str, Any]) -> dict[str, int]:
    base = dict(snapshot or {})
    for key in ("emotion", "cooperation", "risk", "clarity"):
        base[key] = max(0, min(100, int(base.get(key, 50)) + _clamp_delta(delta.get(key))))
    return base
