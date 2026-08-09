"""Sanitize role dialogue: block template-field leakage into spoken lines."""

from __future__ import annotations

import re
from typing import Any


SCENE_OPENING_EVENT_MARKER = "[SCENE_OPENING_EVENT]"


def is_internal_prompt_text(value: Any) -> bool:
    """Identify orchestration prompts that must never become dialogue data."""
    return SCENE_OPENING_EVENT_MARKER in str(value or "")


def is_internal_prompt_message(message: Any) -> bool:
    if isinstance(message, dict):
        return is_internal_prompt_text(message.get("content") or message.get("text"))
    return is_internal_prompt_text(getattr(message, "content", None))


def filter_internal_prompt_messages(messages: Any) -> list[Any]:
    return [message for message in (messages or []) if not is_internal_prompt_message(message)]


_META_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"我最怕的就是(.+?)，"), r"我现在特别担心\1，"),
    (re.compile(r"我最怕的是(.+?)，"), r"我现在特别担心\1，"),
    (re.compile(r"我最担心(的)?就是(.+?)，"), r"我现在特别担心\2，"),
    (re.compile(r"核心顾虑[是:]?\s*"), ""),
    (re.compile(r"当前诉求[是:]?\s*"), ""),
    (re.compile(r"触发点[是:]?\s*"), ""),
    (re.compile(r"可安抚点[是:]?\s*"), ""),
    (re.compile(r"行为原型[是:]?\s*"), ""),
    (re.compile(r"最担心[栏项字段][是:]?\s*"), ""),
)

_FORBIDDEN_SUBSTRINGS = (
    "核心顾虑",
    "当前诉求",
    "触发点",
    "可安抚点",
    "行为原型",
    "opening_preset",
    "core_concern",
)


_ROLE_META_TOKENS = (
    "信息边界",
    "事实边界",
    "已知事实",
    "未知事实",
    "不可透露",
    "不可告知",
    "当前角色大脑",
    "身体绑定",
    "身份锚点",
    "状态契约",
    "表现契约",
    "人设字段",
    "配置原文",
    "角色模板",
    "模板参数",
    "参数配置",
    "当前诉求",
    "核心顾虑",
    "情绪触发点",
    "行为原型",
    "可安抚点",
    "role_brain",
    "identity_anchor",
    "state_contract",
    "known_facts",
    "hidden_truths",
    "does_not_know",
    "core_concern",
    "current_goal",
    "trigger_points",
    "persona_meta",
)

_ROLE_COACHING_TOKENS = (
    "换个角度",
    "换个说法",
    "换一种问法",
    "换个问法",
    "别一直绕在同一个点",
    "绕在同一个点",
    "把问题拆开",
    "问题拆开",
    "你先把问题",
    "你先问",
    "你再问",
    "你问具体点",
    "你问清楚点",
    "你把问题说具体",
    "别让我重复",
    "刚才那段我说过",
    "刚才那句我说过",
    "问题一个一个",
    "一个问题一个问题",
    "你要问事实",
    "直接问事实",
)


def contains_role_meta_language(text: str) -> bool:
    """Return whether a visible line leaked an internal prompt/template concept."""
    content = str(text or "")
    return any(token in content for token in _ROLE_META_TOKENS)


def contains_role_coaching_language(text: str) -> bool:
    """Visible role speech must not coach the learner or narrate turn management."""
    content = str(text or "")
    return any(token in content for token in _ROLE_COACHING_TOKENS)


def sanitize_spoken_line(text: str) -> str:
    content = str(text or "").strip()
    if not content:
        return content
    if contains_role_meta_language(content):
        if "信息边界" in content or "事实边界" in content:
            return "我只能说自己亲眼看到、亲耳听到的，不敢乱讲。"
        return ""
    if contains_role_coaching_language(content):
        return ""
    for pattern, replacement in _META_PATTERNS:
        content = pattern.sub(replacement, content)
    for token in _FORBIDDEN_SUBSTRINGS:
        if token in content:
            content = content.replace(token, "")
    content = re.sub(r"\s{2,}", " ", content).strip()
    content = re.sub(r"^[，,、：:\s]+", "", content)
    return content or str(text or "").strip()


def _repeat_similarity(left: str, right: str) -> float:
    normalize = lambda value: re.sub(r"[\s，。！？,.!?、；;：“”\"'（）()…]+", "", str(value or ""))
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    grams_a = {a[index:index + 2] for index in range(max(0, len(a) - 1))}
    grams_b = {b[index:index + 2] for index in range(max(0, len(b) - 1))}
    return len(grams_a & grams_b) / max(1, len(grams_a | grams_b)) if grams_a and grams_b else 0.0


def repair_learner_echoed_spoken_line(text: str, user_text: str) -> str:
    """Do not let a role parrot the learner's whole instruction back at them."""
    content = sanitize_spoken_line(text)
    learner = str(user_text or "").strip()
    if len(content) < 10 or len(learner) < 10 or _repeat_similarity(content, learner) < 0.76:
        return content
    if re.search(r"赔|损失|多少钱|报数|金额", learner):
        return "具体数我一时算不清，但损失确实不小。"
    return "我听明白你的意思了，能确定的那部分我会照实说。"


def repair_repetitive_spoken_line(text: str, recent_lines: list[str], user_text: str) -> tuple[str, bool]:
    content = sanitize_spoken_line(text)
    if len(content) < 8 or not any(_repeat_similarity(content, previous) >= 0.58 for previous in recent_lines[-4:]):
        return content, False

    user = str(user_text or "")
    if re.search(r"时间|几点|什么时候", user):
        return "时间我只能记个大概，就是吵起来以后不久。", True
    if re.search(r"地点|哪里|哪儿", user):
        return "地点就在现场那一片，我当时离得不算近。", True
    if re.search(r"受伤|伤情|流血|意识|清醒|救护", user):
        return "我只看到有人受伤了，具体伤得怎么样我说不准。", True
    if re.search(r"安全|救护|120|分开|保护", user):
        return "现场当时很乱，后来有人过去处理了，别的我没看清。", True
    return "我能确定的只有当时亲眼看见、亲耳听见的那一段。", True


def sanitize_utterances(utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in utterances:
        if isinstance(item, dict):
            content = sanitize_spoken_line(item.get("content", ""))
            if not content:
                continue
            cleaned.append({**item, "content": content})
        elif isinstance(item, str):
            content = sanitize_spoken_line(item)
            if content:
                cleaned.append({"content": content, "delivery": "normal"})
    return cleaned
