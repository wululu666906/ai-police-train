"""Intake dialogue sequence: officer question order guidance."""

from __future__ import annotations

from typing import Any

INTAKE_PHASES: list[tuple[str, str, list[str]]] = [
    (
        "incident_nature",
        "什么事/警情性质",
        ["什么事", "怎么回事", "发生什么", "什么情况", "什么警情", "出什么", "啥事", "经过", "怎样的事", "矛盾", "纠纷", "打架", "斗殴", "逃逸", "事故", "车祸"],
    ),
    ("safety_check", "安全与救助", ["安全", "受伤", "需要帮助", "要不要紧", "有没有事", "还在打", "还在闹", "危险", "120", "救护"]),
    ("location", "地点", ["哪里", "哪儿", "地点", "位置", "地址", "在哪", "什么地方"]),
    ("time", "时间", ["几点", "什么时候", "何时", "多久", "时间"]),
    ("identity", "身份关系", ["姓名", "叫什么", "你是谁", "身份", "什么关系", "联系方式", "电话多少", "手机号"]),
    ("details", "细节经过", ["怎么打", "谁先", "为什么", "具体", "细节", "经过"]),
    ("risk_dispatch", "风险派警", ["派警", "增援", "刀具", "持械", "逃跑", "逃逸"]),
]

PREMATURE_BEFORE_SAFETY: list[tuple[str, list[str]]] = [
    ("time", ["几点", "什么时候", "何时", "多久以前", "具体时间"]),
    ("identity", ["姓名", "叫什么", "你是谁", "身份证", "联系方式", "电话多少", "手机号", "报上名"]),
    ("location", ["哪里", "哪儿", "地址", "具体位置", "在哪个"]),
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _phase_index(phase_key: str) -> int:
    for index, (key, _, _) in enumerate(INTAKE_PHASES):
        if key == phase_key:
            return index
    return 0


def _assistant_opening_corpus(messages: list[Any]) -> str:
    parts: list[str] = []
    for message in messages or []:
        role = _text(getattr(message, "role", ""))
        if role not in {"assistant", "ai"}:
            continue
        content = _text(getattr(message, "content", ""))
        if content:
            parts.append(content)
    return "\n".join(parts)


def detect_satisfied_phases(
    user_messages: list[str],
    revealed_info: list[str] | None = None,
    assistant_corpus: str = "",
) -> set[str]:
    corpus = "\n".join([_text(item) for item in user_messages if _text(item)])
    if assistant_corpus:
        corpus = f"{corpus}\n{assistant_corpus}"
    if revealed_info:
        corpus = f"{corpus}\n" + "\n".join(_text(item) for item in revealed_info if _text(item))
    satisfied: set[str] = set()
    for key, _, keywords in INTAKE_PHASES:
        if _contains_any(corpus, keywords):
            satisfied.add(key)
    return satisfied


def detect_officer_phase(
    user_messages: list[str],
    revealed_info: list[str] | None = None,
    assistant_corpus: str = "",
) -> str:
    satisfied = detect_satisfied_phases(user_messages, revealed_info, assistant_corpus)
    latest = "incident_nature"
    for key, _, _ in INTAKE_PHASES:
        if key in satisfied:
            latest = key
    return latest


def check_premature_questions(
    latest_user_message: str,
    user_messages: list[str],
    revealed_info: list[str] | None = None,
    assistant_corpus: str = "",
) -> dict[str, Any] | None:
    message = _text(latest_user_message)
    if not message:
        return None

    satisfied = detect_satisfied_phases(user_messages, revealed_info, assistant_corpus)
    has_incident = "incident_nature" in satisfied or _contains_any(message, INTAKE_PHASES[0][2])
    has_safety = "safety_check" in satisfied or _contains_any(message, INTAKE_PHASES[1][2])

    for category, keywords in PREMATURE_BEFORE_SAFETY:
        if not _contains_any(message, keywords):
            continue
        if category == "time" and (has_safety or "time" in satisfied):
            continue
        if category == "identity" and has_incident and has_safety:
            continue
        if category == "location" and has_incident and has_safety:
            continue
        label = {"time": "具体时间", "identity": "身份或联系方式", "location": "地点"}[category]
        return {
            "level": "warning",
            "tags": ["question_order", f"premature_{category}"],
            "message": f"接警初期建议先弄清「出了什么事」并确认报警人是否安全，再追问{label}。",
            "all_messages": [
                f"接警初期建议先弄清「出了什么事」并确认报警人是否安全，再追问{label}。",
            ],
        }
    return None


def build_intake_sequence_feedback(
    messages: list[Any],
    latest_user_message: str,
    revealed_info: list[str] | None = None,
) -> dict[str, Any] | None:
    user_messages = [
        _text(getattr(message, "content", ""))
        for message in messages
        if _text(getattr(message, "role", "")) == "user" and _text(getattr(message, "content", ""))
    ]
    if latest_user_message and (not user_messages or user_messages[-1] != _text(latest_user_message)):
        user_messages.append(_text(latest_user_message))

    assistant_corpus = _assistant_opening_corpus(messages)
    warning = check_premature_questions(latest_user_message, user_messages, revealed_info, assistant_corpus)
    if warning:
        return warning

    # Opening delivered but officer hasn't spoken yet — gentle nudge
    has_assistant = any(_text(getattr(message, "role", "")) == "assistant" for message in messages)
    if has_assistant and not user_messages:
        return {
            "level": "info",
            "tags": ["intake_listen_first"],
            "message": "报警人已开口说明情况，建议先倾听并确认其安全与事件性质，再展开结构化问询。",
            "all_messages": ["报警人已开口说明情况，建议先倾听并确认其安全与事件性质，再展开结构化问询。"],
        }
    return None


def merge_sequence_feedback(base_feedback: dict[str, Any] | None, sequence_feedback: dict[str, Any] | None) -> dict[str, Any]:
    if not sequence_feedback:
        return base_feedback or {}
    if not base_feedback:
        return sequence_feedback

    merged = dict(base_feedback)
    if sequence_feedback.get("level") == "warning":
        merged["level"] = "warning"
    merged["message"] = sequence_feedback.get("message") or merged.get("message", "")
    merged["tags"] = list(dict.fromkeys([*(sequence_feedback.get("tags") or []), *(merged.get("tags") or [])]))
    merged["all_messages"] = list(
        dict.fromkeys([*(sequence_feedback.get("all_messages") or []), *(merged.get("all_messages") or [])])
    )
    return merged
