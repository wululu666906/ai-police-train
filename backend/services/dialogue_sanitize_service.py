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
