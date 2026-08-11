"""追问话术教练：为执法学员生成可直接说出口的追问问句。

提示词见 prompts/recommended_questions.py。
此文件只保留：LLM 调用、输出校验、去重、接口函数。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .prompts.recommended_questions import RECOMMENDED_QUESTIONS_PROMPT

_MAX_LEN = 42
_MAX_ITEMS = 4
_RECOMMENDATION_LLM_TIMEOUT_SECONDS = 3.0

_META_PATTERNS = (
    r"先围绕",
    r"把最关键",
    r"这一点",
    r"建议先",
    r"建议(民警|学员|你|其|对方|报警人)",
    r"(民警|学员)(应当|应该|需要|可以|可|要)",
    r"(可|可以)(询问|追问|核实|了解|确认)",
    r"下一步",
    r"后续",
    r"本阶段",
    r"缺口",
    r"训练已",
    r"训练",
    r"补齐这些",
)

_TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("time", ("几点", "什么时候", "何时", "多久", "时间", "开始", "结束")),
    ("location", ("哪里", "位置", "地点", "在哪", "何处")),
    ("identity", ("身份", "姓名", "你是谁", "叫什么", "联系方式", "电话")),
    ("people", ("涉事", "当事人", "对方", "双方", "几个人", "多少人", "哪些人", "谁在场", "还有谁")),
    ("witness", ("证人", "目击", "在场", "还有谁", "谁看到")),
    ("injury", ("伤", "120", "急救", "昏迷", "出血", "意识", "外伤")),
    ("safety", ("危险", "安全", "撤离", "警戒")),
    ("process", ("经过", "过程", "怎么回事", "发生什么", "什么事", "什么情况", "具体情况")),
    ("evidence", ("监控", "视频", "照片", "物证", "痕迹")),
    ("emotion", ("冷静", "别急", "慢慢", "安抚", "深呼吸")),
    ("mediation", ("调解", "协商", "双方", "对面")),
]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw)
        return value if value > 0 else default
    except (ValueError, AttributeError):
        return default


def _trim_question(text: str) -> str:
    clean = re.sub(r"\s+", " ", _text(text))
    if len(clean) <= _MAX_LEN:
        return clean
    cut = clean[: _MAX_LEN - 1]
    if "，" in cut:
        cut = cut.rsplit("，", 1)[0]
    elif "？" in cut:
        cut = cut[: cut.rfind("？") + 1]
    return cut.rstrip("，、；") + ("？" if not cut.endswith("？") else "")


def _is_meta_question(text: str) -> bool:
    lowered = _text(text)
    if not lowered:
        return True
    if len(lowered) > 46 and any(token in lowered for token in ("评估", "初步了解", "保护现场")):
        return True
    return any(re.search(pattern, lowered) for pattern in _META_PATTERNS)


def _is_officer_spoken_question(text: str) -> bool:
    clean = _text(text)
    if not clean or _is_meta_question(clean):
        return False
    if not clean.endswith(("？", "?")):
        return False
    if any(token in clean for token in ("我方", "警方应", "民警应", "学员应", "可进一步", "建议")):
        return False
    return True


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        text = _text(item.get("text"))
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(
            {
                "text": text,
                "category": _text(item.get("category")) or "追问",
                "target_role_name": _text(item.get("target_role_name")) or None,
            }
        )
    return result


def _role_names(scene_roles: list[dict[str, Any]] | None) -> list[str]:
    names = [_text(item.get("name")) for item in scene_roles or [] if item.get("speakable", True)]
    return [name for name in names if name]


def _detect_topics(corpus: str) -> set[str]:
    topics: set[str] = set()
    for topic, keywords in _TOPIC_RULES:
        if any(keyword in corpus for keyword in keywords):
            topics.add(topic)
    return topics


def _build_history_corpus(
    recent_messages: list[dict[str, Any]] | None,
    revealed_info: list[str] | None,
    last_user_message: str = "",
) -> str:
    parts: list[str] = []
    for message in recent_messages or []:
        role = _text(message.get("role"))
        content = _text(message.get("content"))
        speaker = _text(message.get("speaker_name"))
        if not content:
            continue
        prefix = f"{speaker}:" if speaker and role == "assistant" else role
        parts.append(f"{prefix} {content}")
    parts.extend(revealed_info or [])
    if last_user_message:
        parts.append(last_user_message)
    return "\n".join(parts)


def _last_assistant_text(recent_messages: list[dict[str, Any]] | None) -> str:
    for message in reversed(recent_messages or []):
        if _text(message.get("role")) == "assistant":
            return _text(message.get("content"))
    return ""


def _missing_label_keywords(label: str) -> list[str]:
    text = _text(label)
    if any(t in text for t in ("时间", "几点", "何时")):
        return ["时间", "几点", "何时", "多久"]
    if any(t in text for t in ("地点", "位置")):
        return ["地点", "位置", "在哪", "哪里"]
    if any(t in text for t in ("身份", "姓名", "联系")):
        return ["身份", "姓名", "联系", "叫什么"]
    if any(t in text for t in ("风险", "安全", "伤情")):
        return ["风险", "安全", "受伤", "危险"]
    if any(t in text for t in ("经过", "过程")):
        return ["经过", "过程", "发生"]
    return []


def _try_llm_question_items(
    *,
    case_title: str,
    scene_name: str,
    current_stage: str,
    current_stage_goal: str,
    case_type: str,
    last_assistant: str,
    last_user_message: str,
    missing_requirements: list[str],
    scene_roles: list[dict[str, Any]] | None,
    covered_topics: set[str],
) -> list[dict[str, Any]]:
    try:
        import services.llm_provider as _llm
        create_json_chat_completion = _llm.create_json_chat_completion
        extract_message_text = _llm.extract_message_text
        get_chat_model = _llm.get_chat_model

        role_hint = "、".join(_role_names(scene_roles)) or "对话对象"
        missing_hint = "、".join(missing_requirements[:4]) or "无"
        covered_hint = "、".join(sorted(covered_topics)) or "无"

        prompt = RECOMMENDED_QUESTIONS_PROMPT.format(
            case_title=case_title or case_type,
            scene_name=scene_name,
            current_stage=current_stage,
            current_stage_goal=current_stage_goal,
            role_hint=role_hint,
            last_assistant=last_assistant or "（尚无）",
            last_user_message=last_user_message or "（尚无）",
            missing_hint=missing_hint,
            covered_hint=covered_hint,
        )

        response = create_json_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            model=get_chat_model(),
            max_tokens=600,
            extra_kwargs={
                "timeout": _env_float(
                    "RECOMMENDED_QUESTIONS_LLM_TIMEOUT_SECONDS",
                    _RECOMMENDATION_LLM_TIMEOUT_SECONDS,
                )
            },
            retries=1,
            allow_plain_json_fallback=False,
        )
        raw = extract_message_text(response) or ""
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return []
        payload = json.loads(match.group(0))
        raw_items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            return []

        valid_categories = {"安抚", "核实", "追问", "程序", "调解", "定制"}
        items: list[dict[str, Any]] = []
        for entry in raw_items[:4]:
            if not isinstance(entry, dict):
                continue
            text = _trim_question(entry.get("text"))
            if not _is_officer_spoken_question(text):
                continue
            category = _text(entry.get("category")) or "追问"
            if category not in valid_categories:
                category = "追问"
            target = _text(entry.get("target_role_name"))
            if target and target not in _role_names(scene_roles):
                target = ""
            items.append({"text": text, "category": category, "target_role_name": target or None})
        return items
    except Exception as error:
        print(f"[recommended_questions] LLM unavailable, no fallback: {error}")
        return []


def _filter_stale_missing(
    missing_requirements: list[str] | None,
    covered_topics: set[str],
) -> list[str]:
    result: list[str] = []
    for label in missing_requirements or []:
        keywords = _missing_label_keywords(label)
        if keywords and any(kw in covered_topics or any(kw in t for t in covered_topics) for kw in keywords):
            continue
        result.append(label)
    return result


def build_recommended_question_items(
    *,
    current_stage: str = "",
    current_stage_goal: str = "",
    case_type: str = "",
    case_title: str = "",
    scene_name: str = "",
    scene_kind: str = "",
    role_name: str = "",
    role_type: str = "",
    target_role_name: str = "",
    scene_roles: list[dict[str, Any]] | None = None,
    revealed_info: list[str] | None = None,
    missing_requirements: list[str] | None = None,
    truth_stage: str = "",
    emotion: int = 50,
    cooperation: int = 50,
    persona_profile: dict[str, Any] | None = None,
    momentum: dict[str, Any] | None = None,
    last_user_message: str = "",
    recent_messages: list[dict[str, Any]] | None = None,
    custom_prompts: list[str] | None = None,
    use_llm: bool = True,
) -> list[dict[str, Any]]:
    corpus = _build_history_corpus(recent_messages, revealed_info, last_user_message)
    covered_topics = _detect_topics(corpus)
    last_assistant = _last_assistant_text(recent_messages)
    effective_missing = _filter_stale_missing(missing_requirements, covered_topics)

    items: list[dict[str, Any]] = []

    # 自定义话术优先
    for raw in custom_prompts or []:
        text = _trim_question(_text(raw))
        if text and not _is_meta_question(text):
            items.append({"text": text, "category": "定制", "target_role_name": None})

    # LLM 生成
    if use_llm:
        llm_items = _try_llm_question_items(
            case_title=case_title,
            scene_name=scene_name,
            current_stage=current_stage,
            current_stage_goal=current_stage_goal,
            case_type=case_type,
            last_assistant=last_assistant,
            last_user_message=last_user_message,
            missing_requirements=effective_missing,
            scene_roles=scene_roles,
            covered_topics=covered_topics,
        )
        items.extend(llm_items)

    # 兜底：LLM 无输出时给最基础一句
    if not items:
        addressee = _text(target_role_name) or _text(role_name)
        prefix = f"{addressee}，" if addressee and addressee not in {"对话对象", "相关人员"} else ""
        items.append({"text": f"{prefix}能把你知道的情况说一下吗？", "category": "追问", "target_role_name": addressee or None})

    cleaned: list[dict[str, Any]] = []
    for item in _dedupe_items(items):
        if _is_officer_spoken_question(item["text"]):
            cleaned.append(item)
        if len(cleaned) >= _MAX_ITEMS:
            break

    return cleaned


def build_recommended_questions(**kwargs: Any) -> list[str]:
    return [item["text"] for item in build_recommended_question_items(**kwargs)]


def filter_stale_missing_requirements_for_history(
    missing_requirements: list[str] | None,
    *,
    recent_messages: list[dict[str, Any]] | None = None,
    revealed_info: list[str] | None = None,
    last_user_message: str = "",
    use_intake_flow: bool = True,
) -> list[str]:
    corpus = _build_history_corpus(recent_messages, revealed_info, last_user_message)
    covered_topics = _detect_topics(corpus)
    return _filter_stale_missing(missing_requirements, covered_topics)


def apply_stage_hit_rate_correction(
    items: list[dict[str, Any]],
    *,
    satisfied: list[str] | None = None,
    missing: list[str] | None = None,
    addressee: str = "",
) -> list[dict[str, Any]]:
    """保持对外接口兼容；此版本直接返回原列表（逻辑已移入 LLM prompt）。"""
    return items


def serialize_message_history(messages: list[Any] | None) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in messages or []:
        role = _text(getattr(message, "role", ""))
        content = _text(getattr(message, "content", ""))
        if not content:
            continue
        normalized_role = "user" if role == "user" else ("assistant" if role == "assistant" else role or "system")
        payload.append(
            {
                "role": normalized_role,
                "content": content,
                "speaker_name": _text(getattr(message, "speaker_name", "")) or None,
            }
        )
    return payload[-10:]
