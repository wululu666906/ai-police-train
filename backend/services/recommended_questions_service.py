"""Context-aware recommended questions for student training."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

_MAX_LEN = 42
_MAX_ITEMS = 4
_META_PATTERNS = (
    r"先围绕",
    r"把最关键",
    r"这一点",
    r"建议先",
    r"训练已",
    r"补齐这些",
)

_TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("time", ("几点", "什么时候", "何时", "多久", "时间", "开始", "结束", "9点", "点钟", "上午", "下午", "晚上")),
    ("location", ("哪里", "位置", "地点", "在哪", "何处")),
    ("identity", ("身份", "姓名", "你是谁", "叫什么", "联系方式", "电话")),
    ("contact", ("联系方式", "联系电话", "电话", "手机号", "回拨", "保持畅通")),
    ("people", ("涉事", "当事人", "对方", "双方", "几个人", "多少人", "哪些人", "谁在场", "还有谁")),
    ("witness", ("证人", "目击", "在场", "还有谁", "谁看到")),
    ("injury", ("伤", "120", "急救", "昏迷", "出血", "意识", "外伤")),
    ("safety", ("危险", "安全", "撤离", "警戒")),
    ("dispatch", ("派警", "民警", "出警", "处置", "到场", "增援")),
    ("process", ("经过", "过程", "怎么回事", "发生什么", "什么事", "什么情况", "具体情况", "顺序", "先后")),
    ("evidence", ("监控", "视频", "照片", "物证", "痕迹")),
    ("emotion", ("冷静", "别急", "慢慢", "安抚", "深呼吸")),
    ("mediation", ("调解", "协商", "双方", "对面")),
]

_INTAKE_CORE_TOPICS = {"process", "time", "location", "people"}


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _item(text: str, category: str = "追问", target_role_name: str = "") -> dict[str, Any]:
    return {
        "text": _trim_question(text),
        "category": category,
        "target_role_name": _text(target_role_name) or None,
    }


def _detect_topics(corpus: str) -> set[str]:
    topics: set[str] = set()
    for topic, keywords in _TOPIC_RULES:
        if any(keyword in corpus for keyword in keywords):
            topics.add(topic)
    return topics


def _question_topics(text: str) -> set[str]:
    return _detect_topics(_text(text))


def _is_redundant(question: str, covered_topics: set[str]) -> bool:
    q_topics = _question_topics(question)
    if not q_topics:
        return False
    return q_topics.issubset(covered_topics)


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


def _user_messages(recent_messages: list[dict[str, Any]] | None, last_user_message: str = "") -> list[str]:
    messages = [
        _text(message.get("content"))
        for message in recent_messages or []
        if _text(message.get("role")) == "user" and _text(message.get("content"))
    ]
    latest = _text(last_user_message)
    if latest and (not messages or messages[-1] != latest):
        messages.append(latest)
    return messages


def _assistant_corpus(recent_messages: list[dict[str, Any]] | None) -> str:
    return "\n".join(
        _text(message.get("content"))
        for message in recent_messages or []
        if _text(message.get("role")) == "assistant" and _text(message.get("content"))
    )


def _infer_emotion_state(corpus: str, emotion: int) -> str:
    text = _text(corpus)
    if emotion >= 72 or any(token in text for token in ("害怕", "慌", "急死", "怎么办", "哭", "激动", "吓")):
        return "high"
    return "normal"


def _intake_flow_step(covered_topics: set[str], intake_phases: set[str], corpus: str, emotion: int) -> str:
    if "incident_nature" not in intake_phases and "process" not in covered_topics:
        return "incident"
    if "safety_check" not in intake_phases and not ({"safety", "injury"} & covered_topics):
        return "risk"
    if "location" not in intake_phases and "location" not in covered_topics:
        return "location"
    if "time" not in intake_phases and "time" not in covered_topics:
        return "time"
    if "people" not in covered_topics and "witness" not in covered_topics:
        return "people"
    if "contact" not in covered_topics:
        return "contact"
    if "risk_dispatch" not in intake_phases and "dispatch" not in covered_topics:
        return "dispatch"
    if _infer_emotion_state(corpus, emotion) == "high":
        return "soothe"
    return "closure"


def _intake_flow_items(step: str, addressee: str) -> list[dict[str, Any]]:
    mapping: dict[str, list[tuple[str, str]]] = {
        "incident": [
            ("您先别着急，我需要确认几个情况。具体出了什么事？", "安抚"),
            ("现在事情还在发生吗？", "核实"),
        ],
        "risk": [
            ("现场现在还有人在冲突吗？有没有人受伤？", "核实"),
            ("对方还在现场吗？有没有持械或继续伤人的风险？", "核实"),
        ],
        "location": [
            ("你现在具体在什么位置？门牌号能说一下吗？", "核实"),
            ("事发地点和你现在的位置是同一个地方吗？", "核实"),
        ],
        "time": [
            ("事情是什么时候发生的？现在还在持续吗？", "核实"),
            ("从发生到你报警大概隔了多久？", "核实"),
        ],
        "people": [
            ("现场现在还有哪些人在？涉事双方都在吗？", "核实"),
            ("除了你，还有没有目击人或受伤的人？", "核实"),
        ],
        "contact": [
            ("请报一下你的姓名和联系电话，方便回拨。", "核实"),
            ("你和涉事人员是什么关系？", "核实"),
        ],
        "dispatch": [
            ("你先待在安全位置，民警到场前别再靠近对方，可以吗？", "程序"),
            ("现场情况有变化的话，能第一时间告诉我们吗？", "程序"),
        ],
        "soothe": [
            ("你先深呼吸，我们一个问题一个问题来，好吗？", "安抚"),
            ("你现在最担心的是什么？我先帮你稳住现场。", "安抚"),
        ],
        "closure": [
            ("你保持电话畅通，民警到场前先别离开，可以吗？", "程序"),
            ("如果对方靠近或情况升级，你能马上退到安全位置吗？", "程序"),
        ],
    }
    return [_item(_prefix_addressee(text, addressee), category, addressee) for text, category in mapping.get(step, [])]


def _role_names(scene_roles: list[dict[str, Any]] | None) -> list[str]:
    names = [_text(item.get("name")) for item in scene_roles or [] if item.get("speakable", True)]
    return [name for name in names if name]


def _extract_role_from_text(text: str, scene_roles: list[dict[str, Any]] | None) -> str:
    for name in _role_names(scene_roles):
        if text.startswith(f"{name}，") or text.startswith(f"{name},"):
            return name
    return ""


def _addressee(role_name: str, target_role_name: str = "") -> str:
    name = _text(target_role_name) or _text(role_name)
    if not name or name in {"对话对象", "相关人员", "未指定角色"}:
        return ""
    return name


def _prefix_addressee(question: str, addressee: str) -> str:
    if not addressee or addressee in question:
        return question
    if len(question) + len(addressee) + 1 > _MAX_LEN:
        return question
    return f"{addressee}，{question}"


def _followup_from_assistant(last_assistant: str, scene_roles: list[dict[str, Any]] | None, target_role_name: str) -> list[dict[str, Any]]:
    text = _text(last_assistant)
    if not text or len(text) < 6:
        return []
    speaker = _extract_role_from_text(text, scene_roles) or _text(target_role_name)
    addressee = speaker
    items: list[dict[str, Any]] = []
    if any(token in text for token in ("骂", "吵", "打", "推", "动手")):
        items.append(_item(_prefix_addressee("吵完之后有没有动手？当时还有谁在场？", addressee), "追问", speaker))
    if any(token in text for token in ("杂物", "堵", "楼道", "占地")):
        items.append(_item(_prefix_addressee("这些东西是你放的吗？大概放了多久？", addressee), "核实", speaker))
    if any(token in text for token in ("伤", "疼", "流血", "倒地")):
        items.append(_item(_prefix_addressee("现在哪里最不舒服？意识清楚吗？", addressee), "核实", speaker))
    if any(token in text for token in ("不对", "冤枉", "血口喷人", "诬陷")):
        items.append(_item(_prefix_addressee("你否认的部分，能说一下你看到的经过吗？", addressee), "追问", speaker))
    if any(token in text for token in ("报警", "110")):
        items.append(_item(_prefix_addressee("报警前你还做过什么处置？", addressee), "核实", speaker))
    if not items:
        items.append(_item(_prefix_addressee("你刚才说的这点，能再具体一点吗？", addressee), "追问", speaker))
    return items


def _goal_fragment_questions(fragment: str, addressee: str) -> list[dict[str, Any]]:
    text = _text(fragment)
    if not text or len(text) < 2:
        return []

    rules: list[tuple[tuple[str, ...], list[tuple[str, str]]]] = [
        (("120", "急救", "医护", "救护"), [("伤者现在意识清醒吗？有没有外伤？", "核实"), ("120到了吗？到场前你做了哪些处置？", "程序")]),
        (("现场安全", "安全风险", "危险", "安全"), [("现场还有没有继续伤人的危险？", "核实"), ("周围群众都撤到安全位置了吗？", "程序")]),
        (("伤者", "伤情", "受伤", "昏迷"), [("伤者现在能不能说话？哪里伤得最重？", "核实"), ("受伤后有没有移动过伤者？", "核实")]),
        (("保护现场", "保护", "警戒"), [("现场物品有没有被挪动？", "程序"), ("入口有人看守吗？", "程序")]),
        (("身份", "核实身份", "证件"), [("请报一下你的姓名和联系方式。", "核实"), ("你当时是以什么身份到现场的？", "核实")]),
        (("时间", "几点", "何时"), [("事情大概什么时候开始？", "核实"), ("从发生到你报警隔了多久？", "核实")]),
        (("地点", "位置", "哪里"), [("当时具体在哪个位置？", "核实"), ("事发点和你现在站的位置一致吗？", "核实")]),
        (("证人", "目击者", "在场"), [("现场还有谁看到了？能留个联系方式吗？", "核实"), ("除了你，还有谁离现场最近？", "核实")]),
        (("调解", "协商", "双方"), [("你们双方现在愿意当面沟通吗？", "调解"), ("对方刚才的态度怎么样？", "追问")]),
        (("纠纷", "口角", "争吵"), [("刚才因为什么事吵起来的？", "追问"), ("争吵时有没有动手或推搡？", "核实")]),
        (("情绪", "安抚", "激动"), [("你先冷静一下，我们慢慢说，好吗？", "安抚"), ("你现在最担心的是什么？", "安抚")]),
        (("经过", "过程", "怎么回事"), [("你把刚才的经过按顺序再说一遍。", "追问"), ("最先发生的是哪一件事？", "追问")]),
        (("物证", "监控", "视频", "拍照"), [("这附近有没有监控？拍到了吗？", "程序"), ("现场照片或视频你这边有吗？", "程序")]),
        (("酒精", "酒驾", "醉驾"), [("刚才有没有喝酒？喝了多少？", "核实"), ("事发前你在哪里喝酒？", "核实")]),
        (("损失", "赔偿", "财物"), [("这次大概损失了多少？", "核实"), ("有哪些物品受损？", "核实")]),
    ]

    items: list[dict[str, Any]] = []
    for keywords, templates in rules:
        if any(keyword in text for keyword in keywords):
            for sentence, category in templates:
                items.append(_item(_prefix_addressee(sentence, addressee), category, addressee))
    return items


def _goal_to_dialogue_questions(stage_goal: str, addressee: str) -> list[dict[str, Any]]:
    goal = _text(stage_goal)
    if not goal:
        return []
    items: list[dict[str, Any]] = []
    for fragment in re.split(r"[，,；;、/|]+", goal):
        items.extend(_goal_fragment_questions(fragment, addressee))
    if not items:
        if "了解" in goal or "核实" in goal:
            items.append(_item(_prefix_addressee("你把知道的情况如实说一下。", addressee), "核实", addressee))
        elif "处置" in goal or "控制" in goal:
            items.append(_item(_prefix_addressee("现场现在控制住了吗？", addressee), "程序", addressee))
    return items


def _missing_to_dialogue(label: str, addressee: str) -> Optional[dict[str, Any]]:
    text = _text(label)
    if not text or len(text) > 18:
        return None
    if any(token in text for token in ("时间", "几点")):
        return _item(_prefix_addressee("具体是几点发生的？", addressee), "核实", addressee)
    if any(token in text for token in ("地点", "位置")):
        return _item(_prefix_addressee("当时具体在哪个位置？", addressee), "核实", addressee)
    if "身份" in text:
        return _item(_prefix_addressee("请先说明你的身份。", addressee), "核实", addressee)
    if "证人" in text:
        return _item(_prefix_addressee("现场还有谁看到了？", addressee), "核实", addressee)
    if "经过" in text or "过程" in text:
        return _item(_prefix_addressee("事情经过能再说详细一点吗？", addressee), "追问", addressee)
    if "风险" in text or "安全" in text:
        return _item(_prefix_addressee("现场现在还有危险吗？", addressee), "核实", addressee)
    return _item(_prefix_addressee(f"关于{text}，你再具体说一下。", addressee), "追问", addressee)


def _case_type_questions(case_type: str, addressee: str) -> list[dict[str, Any]]:
    mapping = {
        "邻里纠纷": [("楼道杂物是你放的吗？放了多久？", "核实"), ("今天冲突前有没有口角？", "追问")],
        "交通事故": [("两车是怎么撞上的？", "追问"), ("事故后你有没有离开现场？", "核实")],
        "打架斗殴": [("是谁先动的手？", "追问"), ("对方受伤严重吗？", "核实")],
        "纠纷": [("你们矛盾是怎么开始的？", "追问"), ("之前有没有类似冲突？", "核实")],
        "求助": [("你现在最需要警方帮你解决什么？", "核实"), ("事发前有没有求助过别人？", "核实")],
    }
    for key, templates in mapping.items():
        if key in _text(case_type):
            return [_item(_prefix_addressee(text, addressee), category, addressee) for text, category in templates]
    return []


def _missing_label_keywords(label: str) -> list[str]:
    label = _text(label)
    keyword_map = {
        "时间": ("几点", "什么时候", "何时", "多久", "时间", "开始", "结束", "上午", "下午", "晚上"),
        "地点": ("哪里", "位置", "地点", "在哪", "何处", "哪个位置"),
        "身份": ("身份", "姓名", "你是谁", "叫什么", "关系", "什么关系"),
        "人物": ("人物", "在场", "还有谁", "谁在场", "当事人"),
        "证人": ("证人", "目击", "在场", "谁看到"),
        "风险": ("危险", "安全", "风险", "失控", "受伤", "伤情"),
        "经过": ("经过", "过程", "怎么回事", "顺序", "先后", "怎么发生"),
        "证据": ("监控", "视频", "照片", "物证", "痕迹", "录像"),
    }
    for key, keywords in keyword_map.items():
        if key in label:
            return list(keywords)
    return [label] if label else []


def _is_missing_label_already_covered(label: str, covered_topics: set[str], intake_phases: set[str] | None = None) -> bool:
    text = _text(label)
    intake_phases = intake_phases or set()
    if any(token in text for token in ("经过", "过程", "案情", "具体情况", "事件性质")):
        return "process" in covered_topics or "incident_nature" in intake_phases or "details" in intake_phases
    if any(token in text for token in ("时间", "几点")):
        return "time" in covered_topics or "time" in intake_phases
    if any(token in text for token in ("地点", "位置")):
        return "location" in covered_topics or "location" in intake_phases
    if any(token in text for token in ("身份", "姓名", "联系方式", "电话")):
        return "identity" in covered_topics or "identity" in intake_phases
    if any(token in text for token in ("风险", "安全", "伤情", "救助")):
        return "safety" in covered_topics or "injury" in covered_topics or "safety_check" in intake_phases
    return False


def _filter_stale_missing_requirements(
    missing_requirements: list[str] | None,
    covered_topics: set[str],
    intake_phases: set[str] | None = None,
) -> list[str]:
    return [
        label
        for label in (missing_requirements or [])
        if not _is_missing_label_already_covered(label, covered_topics, intake_phases)
    ]


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
    intake_phases: set[str] = set()
    if use_intake_flow:
        try:
            from .dialogue_sequence_service import detect_satisfied_phases

            intake_phases = detect_satisfied_phases(
                _user_messages(recent_messages, last_user_message),
                revealed_info,
                _assistant_corpus(recent_messages),
            )
        except Exception:
            intake_phases = set()
    return _filter_stale_missing_requirements(missing_requirements, covered_topics, intake_phases)


def _question_covers_missing_label(text: str, label: str) -> bool:
    keywords = _missing_label_keywords(label)
    if not keywords:
        return False
    lowered = _text(text)
    return any(keyword in lowered for keyword in keywords)


def _prioritize_missing_items(
    items: list[dict[str, Any]],
    missing_requirements: list[str] | None,
    addressee: str = "",
) -> list[dict[str, Any]]:
    if not missing_requirements:
        return items
    gap_items: list[dict[str, Any]] = []
    for label in missing_requirements[:3]:
        converted = _missing_to_dialogue(label, addressee)
        if converted:
            gap_items.append(converted)
    hits: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    for item in items:
        if any(_question_covers_missing_label(item.get("text", ""), label) for label in missing_requirements):
            hits.append(item)
        else:
            others.append(item)
    return _dedupe_items(gap_items + hits + others)


def _apply_missing_first_correction(
    items: list[dict[str, Any]],
    missing_requirements: list[str] | None,
    addressee: str = "",
) -> list[dict[str, Any]]:
    if not items or not missing_requirements:
        return items
    if _question_covers_missing_label(items[0].get("text", ""), missing_requirements[0]):
        return items
    replacement = _missing_to_dialogue(missing_requirements[0], addressee)
    if replacement:
        return [replacement, *items[1:]]
    return items


STAGE_HIT_RATE_THRESHOLD = 0.34


def apply_stage_hit_rate_correction(
    items: list[dict[str, Any]],
    *,
    satisfied: list[str] | None = None,
    missing: list[str] | None = None,
    addressee: str = "",
) -> list[dict[str, Any]]:
    missing = list(missing or [])
    if not missing:
        return items
    satisfied = list(satisfied or [])
    total = len(satisfied) + len(missing)
    hit_rate = (len(satisfied) / total) if total else 1.0
    if hit_rate >= STAGE_HIT_RATE_THRESHOLD and items:
        if _question_covers_missing_label(items[0].get("text", ""), missing[0]):
            return items
    return _apply_missing_first_correction(items, missing, addressee)


def _intake_questions(addressee: str, *, has_dialogue: bool, has_assistant_opening: bool) -> list[dict[str, Any]]:
    if has_assistant_opening and not has_dialogue:
        return [
            _item(_prefix_addressee("你先别慌，你现在人安全吗？有没有人受伤？", addressee), "安抚", addressee),
            _item(_prefix_addressee("你慢慢说，具体出了什么事？", addressee), "核实", addressee),
        ]
    if not has_dialogue:
        return [_item("110，请讲。", "接警", addressee)]
    return [
        _item(_prefix_addressee("你先别慌，你现在安全吗？有没有人受伤？", addressee), "安抚", addressee),
        _item(_prefix_addressee("你再把事情经过简单说一下。", addressee), "核实", addressee),
    ]


def _intake_progress_questions(
    addressee: str,
    *,
    recent_messages: list[dict[str, Any]] | None,
    revealed_info: list[str] | None,
    last_user_message: str = "",
) -> tuple[list[dict[str, Any]], set[str]]:
    try:
        from .dialogue_sequence_service import detect_satisfied_phases

        phases = detect_satisfied_phases(
            _user_messages(recent_messages, last_user_message),
            revealed_info,
            _assistant_corpus(recent_messages),
        )
    except Exception:
        phases = set()

    return [], phases


def _stage_questions(current_stage: str, addressee: str, scene_kind: str = "") -> list[dict[str, Any]]:
    stage = _text(current_stage)
    if scene_kind == "intake" or "接警" in stage:
        return []
    if any(token in stage for token in ("现场", "初查", "勘查", "处置")):
        return [
            _item(_prefix_addressee("你到现场后最先看到的是什么？", addressee), "追问", addressee),
            _item(_prefix_addressee("当时现场还有哪些人在？", addressee), "核实", addressee),
        ]
    if any(token in stage for token in ("调解", "核实")):
        return [
            _item(_prefix_addressee("对方现在怎么说？愿意当面沟通吗？", addressee), "调解", addressee),
            _item(_prefix_addressee("你这边最核心的诉求是什么？", addressee), "追问", addressee),
        ]
    return [
        _item(_prefix_addressee("你把前后经过按时间顺序再说一遍。", addressee), "追问", addressee),
        _item(_prefix_addressee("有没有和前面说法不一致的地方？", addressee), "追问", addressee),
    ]


def _truth_stage_questions(truth_stage: str, emotion: int, addressee: str) -> list[dict[str, Any]]:
    if truth_stage in {"guarded_denial", "partial_release"}:
        return [_item(_prefix_addressee("你先说你确定的部分，不确定的我会再核实。", addressee), "安抚", addressee)]
    if emotion >= 72:
        return [_item(_prefix_addressee("你先深呼吸，我们一个问题一个问题来。", addressee), "安抚", addressee)]
    return []


def _multi_role_questions(scene_roles: list[dict[str, Any]] | None, target_role_name: str) -> list[dict[str, Any]]:
    names = _role_names(scene_roles)
    if len(names) < 2:
        return []
    if _text(target_role_name):
        return [_item(f"{target_role_name}，你刚才说的能再具体点吗？", "追问", target_role_name)]
    return [
        _item(f"{names[0]}，你先说下你看到的情况。", "追问", names[0]),
        _item(f"{names[1]}，你这边有什么补充？", "追问", names[1]),
    ]


def _custom_prompt_items(custom_prompts: list[str] | None, scene_roles: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in custom_prompts or []:
        text = _trim_question(_text(raw))
        if not text or _is_meta_question(text):
            continue
        role = _extract_role_from_text(text, scene_roles)
        items.append(_item(text, "定制", role))
    return items


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
        from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model

        role_hint = "、".join(_role_names(scene_roles)) or "对话对象"
        missing_hint = "、".join(missing_requirements[:4]) or "无"
        covered_hint = "、".join(sorted(covered_topics)) or "无"

        prompt = f"""你是警情处置训练教练，为执法学员生成「可直接说出口」的追问话术。

要求：
1. 输出 3 条，每条不超过 38 字，必须是民警对现场角色说的话，带问号。
2. 不要出现“先围绕”“把最关键”“训练”等教学腔。
3. 不要重复已覆盖主题：{covered_hint}
4. 要承接对方上一句回复，不要像第一次到场。
5. category 只能是：安抚、核实、追问、程序、调解
6. 若需指定对象，填 target_role_name（从 {role_hint} 中选），否则 null
7. 若「本阶段还缺」不为“无”，前 2 条必须直接追问缺口项，且问题正文须含对应关键词（如时间/地点/身份/证人/风险/经过）。

案件：{case_title or case_type}
场景：{scene_name}
阶段：{current_stage}
阶段目标：{current_stage_goal}
本阶段还缺：{missing_hint}
对方上一句：{last_assistant or "（尚无）"}
学员上一句：{last_user_message or "（尚无）"}

只输出 JSON：
{{"items":[{{"text":"……","category":"核实","target_role_name":null}}]}}"""

        response = create_json_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.55,
            model=get_chat_model(),
            max_tokens=700,
        )
        raw = extract_message_text(response) or ""
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return []
        payload = json.loads(match.group(0))
        raw_items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            return []
        items: list[dict[str, Any]] = []
        valid_categories = {"安抚", "核实", "追问", "程序", "调解", "定制"}
        for entry in raw_items[:4]:
            if not isinstance(entry, dict):
                continue
            text = _trim_question(entry.get("text"))
            if not text or _is_meta_question(text):
                continue
            category = _text(entry.get("category")) or "追问"
            if category not in valid_categories:
                category = "追问"
            target = _text(entry.get("target_role_name"))
            if target and target not in _role_names(scene_roles):
                target = ""
            items.append(_item(text, category, target))
        return items
    except Exception:
        return []


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
    addressee = _addressee(role_name, target_role_name)
    corpus = _build_history_corpus(recent_messages, revealed_info, last_user_message)
    covered_topics = _detect_topics(corpus)
    last_assistant = _last_assistant_text(recent_messages)
    has_dialogue = bool(recent_messages) or bool(last_user_message) or bool(last_assistant)
    has_assistant_opening = bool(last_assistant)
    resolved_scene_kind = _text(scene_kind) or ("intake" if "接警" in _text(scene_name) or "接警" in _text(current_stage) else "")
    intake_progress_items: list[dict[str, Any]] = []
    intake_phases: set[str] = set()
    intake_step = ""
    if resolved_scene_kind == "intake":
        intake_progress_items, intake_phases = _intake_progress_questions(
            addressee,
            recent_messages=recent_messages,
            revealed_info=revealed_info,
            last_user_message=last_user_message,
        )
        intake_step = _intake_flow_step(covered_topics, intake_phases, corpus, emotion)
        intake_progress_items = _intake_flow_items(intake_step, addressee)
    effective_missing_requirements = _filter_stale_missing_requirements(
        missing_requirements,
        covered_topics,
        intake_phases,
    )

    items: list[dict[str, Any]] = []
    custom_items = _custom_prompt_items(custom_prompts, scene_roles)
    items.extend(custom_items)
    items.extend(intake_progress_items)

    if use_llm and (last_assistant or last_user_message):
        llm_items = _try_llm_question_items(
            case_title=case_title,
            scene_name=scene_name,
            current_stage=current_stage,
            current_stage_goal=current_stage_goal,
            case_type=case_type,
            last_assistant=last_assistant,
            last_user_message=last_user_message,
            missing_requirements=effective_missing_requirements,
            scene_roles=scene_roles,
            covered_topics=covered_topics,
        )
        items.extend(llm_items)

    if last_assistant:
        items.extend(_followup_from_assistant(last_assistant, scene_roles, target_role_name))

    items.extend(_multi_role_questions(scene_roles, target_role_name))
    items.extend(_goal_to_dialogue_questions(current_stage_goal, addressee))

    for label in effective_missing_requirements[:3]:
        converted = _missing_to_dialogue(label, addressee)
        if converted:
            items.append(converted)

    items.extend(_case_type_questions(case_type, addressee))
    if resolved_scene_kind == "intake":
        if not intake_progress_items:
            items.extend(
                _intake_questions(
                    addressee,
                    has_dialogue=bool(last_user_message),
                    has_assistant_opening=has_assistant_opening,
                )
            )
    else:
        items.extend(_stage_questions(current_stage, addressee, resolved_scene_kind))

    if "纠纷" in _text(scene_name):
        items.append(_item(_prefix_addressee("你们双方矛盾焦点是什么？", addressee), "调解", addressee))
    if "调解" in _text(scene_name):
        items.append(_item(_prefix_addressee("现在双方情绪怎么样？能坐下来谈吗？", addressee), "调解", addressee))

    items.extend(_truth_stage_questions(truth_stage, emotion, addressee))
    items = _prioritize_missing_items(items, effective_missing_requirements, addressee)

    if not has_dialogue and resolved_scene_kind != "intake":
        items.insert(0, _item(_prefix_addressee("你好，我是到场民警，先说说发生了什么？", addressee), "核实", addressee))
    elif revealed_info and last_assistant:
        items.append(_item(_prefix_addressee("刚才那点还有细节能补充吗？", addressee), "追问", addressee))

    if _text(role_type) in {"报警人", "被害人", "证人"}:
        items.append(_item(_prefix_addressee("你是怎么发现异常的？第一眼看到什么？", addressee), "追问", addressee))
    if _text(role_type) in {"嫌疑人", "被投诉人", "对方"}:
        items.append(_item(_prefix_addressee("对方说你做了什么，你怎么回应？", addressee), "追问", addressee))

    cleaned: list[dict[str, Any]] = []
    for raw in _dedupe_items(items):
        text = raw["text"]
        if _is_meta_question(text):
            continue
        q_topics = _question_topics(text)
        if _is_redundant(text, covered_topics) and not (
            resolved_scene_kind == "intake" and raw.get("category") in {"程序", "安抚"}
        ):
            continue
        if (
            resolved_scene_kind == "intake"
            and intake_step in {"contact", "dispatch", "soothe", "closure"}
            and q_topics
            and q_topics.issubset(_INTAKE_CORE_TOPICS)
        ):
            continue
        if not raw.get("target_role_name"):
            raw["target_role_name"] = _extract_role_from_text(text, scene_roles) or (_text(target_role_name) or None)
        cleaned.append(raw)
        if len(cleaned) >= _MAX_ITEMS:
            break

    if custom_items:
        custom_texts = {item["text"] for item in custom_items}
        cleaned = [item for item in custom_items] + [item for item in cleaned if item["text"] not in custom_texts]
    cleaned = _apply_missing_first_correction(cleaned, effective_missing_requirements, addressee)
    if not cleaned:
        cleaned = [
            _item(_prefix_addressee("你把知道的情况按顺序说一下。", addressee), "追问", addressee),
            _item(_prefix_addressee("现场现在还有什么风险？", addressee), "核实", addressee),
        ]
    return cleaned[:_MAX_ITEMS]


def build_recommended_questions(**kwargs: Any) -> list[str]:
    return [item["text"] for item in build_recommended_question_items(**kwargs)]


def serialize_message_history(messages: list[Any] | None) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in messages or []:
        role = _text(getattr(message, "role", ""))
        content = _text(getattr(message, "content", ""))
        if not content:
            continue
        if role == "user":
            normalized_role = "user"
        elif role == "assistant":
            normalized_role = "assistant"
        else:
            normalized_role = role or "system"
        payload.append(
            {
                "role": normalized_role,
                "content": content,
                "speaker_name": _text(getattr(message, "speaker_name", "")) or None,
            }
        )
    return payload[-10:]
