"""Sanitize role dialogue: block template-field leakage into spoken lines."""

from __future__ import annotations

import re
from typing import Any


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


def sanitize_spoken_line(text: str) -> str:
    content = str(text or "").strip()
    if not content:
        return content
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


def repair_repetitive_spoken_line(text: str, recent_lines: list[str], user_text: str) -> tuple[str, bool]:
    content = sanitize_spoken_line(text)
    if len(content) < 8 or not any(_repeat_similarity(content, previous) >= 0.58 for previous in recent_lines[-4:]):
        return content, False

    user = str(user_text or "")
    if re.search(r"时间|几点|什么时候", user):
        return "时间我先说我记得的，具体分钟不敢乱讲。你再问地点，我接着答。", True
    if re.search(r"地点|哪里|哪儿", user):
        return "地点我先说大概范围，具体位置我再想一下。你问细一点，我能接着答。", True
    if re.search(r"安全|救护|120|分开|保护", user):
        return "安全安排我听到了。你再确认一下现场的人已经分开，我就继续说。", True
    return "刚才那一点我已经说过了。这次我补一个具体信息，你把当前问题单独问我。", True


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
    return cleaned or utterances
