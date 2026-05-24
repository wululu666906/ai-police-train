import json
import re
from typing import Any

from .stage_config_service import infer_scene_behavior_mode


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in values:
        clean = _clean_text(item)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _pick_first_non_empty(*values: Any) -> str:
    for value in values:
        clean = _clean_text(value)
        if clean:
            return clean
    return ""


def _clamp_score(value: Any, fallback: int) -> int:
    try:
        numeric = int(value)
    except Exception:
        numeric = fallback
    return max(0, min(100, numeric))


STATE_LEVEL_TO_SCORE = {
    "low": 22,
    "mid": 52,
    "high": 82,
}

SCENE_BOUNDARY_LIST_FIELDS = (
    "known_key_points",
    "withheld_key_points",
    "conflict_core",
    "acceptable_outcomes",
    "no_go_topics",
    "trigger_sources",
    "concerned_targets",
    "taboo_actions",
    "escalation_actions",
    "deescalation_conditions",
)


def _infer_level_from_score(value: Any, *, reverse: bool = False, fallback: str = "中") -> str:
    numeric = _clamp_score(value, 50)
    if reverse:
        if numeric >= 72:
            return "低"
        if numeric <= 34:
            return "高"
        return fallback
    if numeric >= 72:
        return "高"
    if numeric <= 34:
        return "低"
    return fallback


def _score_from_level(level: Any, fallback: int, *, reverse: bool = False) -> int:
    text = _clean_text(level)
    if text == "高":
        return 22 if reverse else 82
    if text == "低":
        return 82 if reverse else 22
    if text == "中":
        return 52
    return _clamp_score(fallback, fallback)


def _normalize_impairment_state(person: dict[str, Any] | None) -> str:
    person = person or {}
    direct = _pick_first_non_empty(person.get("impairment_state"), person.get("impairment_note"))
    if direct:
        return direct

    status = _clean_text(person.get("status"))
    speaking_style = _clean_text(person.get("speaking_style"))
    personality = _clean_text(person.get("personality"))
    source_text = " ".join([status, speaking_style, personality, _clean_text(person.get("behavior_archetype"))])
    if any(token in source_text for token in ["醉", "酒", "喝多"]):
        return "明显受酒精影响，反应慢、表达乱、容易受刺激升级。"
    if any(token in source_text for token in ["药", "嗑药", "药物"]):
        return "疑似受药物影响，情绪和表达稳定性偏差。"
    if any(token in source_text for token in ["精神", "恍惚", "幻觉", "妄想"]):
        return "疑似受精神状态影响，现场需要先稳控和保护。"
    return ""


BEHAVIOR_ARCHETYPE_LIBRARY: dict[str, dict[str, Any]] = {
    "求助配合型": {
        "interaction_style": "配合型",
        "personality": "愿意把问题解决掉，重视处理结果和反馈",
        "speaking_style": "会先讲自己的诉求，追问时愿意补充具体情况",
        "police_attitude": "主动求助",
        "authority_attitude": "把警方当成解决问题的人，但如果迟迟没有反馈会变得焦躁",
        "pressure_response": "如果迟迟得不到回应，会重复诉求并追问什么时候处理",
        "surface_stance": "我主要是想把事情处理好，该配合的我会配合。",
        "trigger_points": ["感觉被敷衍", "迟迟没人处理"],
        "calming_points": ["有人认真听完经过", "明确告诉我下一步怎么处理"],
        "coping_patterns": ["先重复自己的诉求", "希望尽快得到明确处理"],
        "init_emotion": 46,
        "init_trust": 56,
        "init_risk": 26,
        "init_expression_clarity": 78,
    },
    "委屈宣泄型": {
        "interaction_style": "情绪型",
        "personality": "委屈敏感，希望先被理解和照顾感受",
        "speaking_style": "会夹杂抱怨、重复和情绪宣泄，容易跳着讲",
        "police_attitude": "主动求助",
        "authority_attitude": "希望警方先理解自己的委屈和损失，否则会觉得没人替自己说话",
        "pressure_response": "被追急时会先抱怨、打断或反复强调自己吃亏",
        "surface_stance": "我先把我受的委屈说清楚，你们得先听我讲完。",
        "trigger_points": ["质疑自己夸大", "要求马上闭嘴或冷静"],
        "calming_points": ["先认可情绪和损失", "允许先把最委屈的部分说完"],
        "coping_patterns": ["反复强调自己吃亏", "先宣泄情绪再慢慢落回事实"],
        "init_emotion": 74,
        "init_trust": 42,
        "init_risk": 58,
        "init_expression_clarity": 58,
    },
    "谨慎回避型": {
        "interaction_style": "观察型",
        "personality": "谨慎怕事，不愿轻易卷入冲突中心",
        "speaking_style": "先试探、停顿、回避敏感点，再一点点补充",
        "police_attitude": "试探观望",
        "authority_attitude": "会先看警方掌握了多少，再决定是保守说还是慢慢补",
        "pressure_response": "会先说记不清或没看清，再根据警方态度慢慢补细节",
        "surface_stance": "我可以配合，但我只说我自己确定的部分。",
        "trigger_points": ["感觉会牵连自己", "被逼立刻表态"],
        "calming_points": ["先讲清不会乱定性", "先从自己确定看到的部分问起"],
        "coping_patterns": ["先试探警方掌握程度", "缩小自己看到的范围"],
        "init_emotion": 54,
        "init_trust": 28,
        "init_risk": 34,
        "init_expression_clarity": 74,
    },
    "防御切责型": {
        "interaction_style": "观察型",
        "personality": "自保意识强，先考虑怎么切开责任和后果",
        "speaking_style": "会先绕关键点，把行为说成误会、气头上或被逼无奈",
        "police_attitude": "防备排斥",
        "authority_attitude": "担心被定性或被压实责任，面对警方时本能先自保",
        "pressure_response": "先淡化责任，再切割关键行为，必要时慢慢改口",
        "surface_stance": "我配合归配合，但很多事不是你们想的那样。",
        "trigger_points": ["问谁先动手", "问证据链", "提到家属或赔偿后果"],
        "calming_points": ["先按时间线核实", "给其把话讲完整的台阶"],
        "coping_patterns": ["淡化主动性", "切割关键责任", "把行为说成误会或偶发"],
        "init_emotion": 63,
        "init_trust": 22,
        "init_risk": 46,
        "init_expression_clarity": 76,
    },
    "强硬对抗型": {
        "interaction_style": "对抗型",
        "personality": "好面子、冲、抗拒被压着走",
        "speaking_style": "说话强势，容易抢话、反问、顶嘴",
        "police_attitude": "敌对抵触",
        "authority_attitude": "面对警方时先本能对抗，不愿轻易接受定性或指令",
        "pressure_response": "越压越顶，先争辩、后反问，逼到角落才可能松口",
        "surface_stance": "你们别先给我扣帽子，我没你们想得那么严重。",
        "trigger_points": ["被直接定性", "被命令式压问", "被当众拆台"],
        "calming_points": ["先稳语气再问事实", "给台阶，不当众硬压"],
        "coping_patterns": ["抢话反问", "先争辩后补细节", "借情绪保持姿态"],
        "init_emotion": 76,
        "init_trust": 16,
        "init_risk": 74,
        "init_expression_clarity": 72,
    },
    "醉酒失控型": {
        "interaction_style": "情绪型",
        "personality": "受酒精影响，冲动、纠缠、容易被一句话点燃",
        "speaking_style": "表达断裂、反复、跑题，容易抓住一个点纠缠",
        "police_attitude": "敌对抵触",
        "authority_attitude": "在酒精作用下更抗拒约束和命令，容易把警方视为针对自己",
        "pressure_response": "被硬控或硬压时容易吼叫、挣扎、反复纠缠",
        "surface_stance": "我没事，你们别碰我，都是他们的问题。",
        "trigger_points": ["强行命令", "身体接触", "围观起哄"],
        "calming_points": ["简短明确的边界指令", "减少围观刺激，稳定语气重复沟通"],
        "coping_patterns": ["抓住一个点反复纠缠", "借情绪和酒劲抗拒配合"],
        "init_emotion": 84,
        "init_trust": 12,
        "init_risk": 90,
        "init_expression_clarity": 24,
    },
    "绝望封闭型": {
        "interaction_style": "观察型",
        "personality": "无力、绝望、封闭，对说教和逼问敏感",
        "speaking_style": "回答短、慢、空，容易说“没必要”“别管我”",
        "police_attitude": "试探观望",
        "authority_attitude": "未必敌视警方，但对说教、控制和空泛安慰会明显关闭自己",
        "pressure_response": "被逼急时可能沉默、转身、拒答，或突然情绪失控",
        "surface_stance": "我现在不想说太多，你们别逼我。",
        "trigger_points": ["说教式劝阻", "否定其痛苦", "逼问为什么这样做"],
        "calming_points": ["先稳住陪伴关系", "谈具体牵挂对象或下一分钟要做什么"],
        "coping_patterns": ["沉默或拒答", "反复说没意义", "尽量切断交流"],
        "init_emotion": 82,
        "init_trust": 20,
        "init_risk": 84,
        "init_expression_clarity": 30,
    },
    "围观起哄型": {
        "interaction_style": "对抗型",
        "personality": "爱起哄、好事、容易受现场情绪裹挟",
        "speaking_style": "喜欢插话、带节奏、夸张表达、重复煽动性片段",
        "police_attitude": "防备排斥",
        "authority_attitude": "容易把警方理解成在针对自己，喜欢借人群壮胆",
        "pressure_response": "感觉被针对时会继续起哄、反问或煽动旁人附和",
        "surface_stance": "我就是在旁边看，你们别总盯着我。",
        "trigger_points": ["当众点名", "围观者持续附和", "认为警方只针对自己"],
        "calming_points": ["快速切断围观互动", "单独带离后明确边界"],
        "coping_patterns": ["借场面起哄", "往人群里躲", "嘴上说和自己无关"],
        "init_emotion": 68,
        "init_trust": 18,
        "init_risk": 68,
        "init_expression_clarity": 56,
    },
}


def get_behavior_archetype_defaults(value: Any) -> dict[str, Any]:
    archetype = _clean_text(value)
    if archetype in BEHAVIOR_ARCHETYPE_LIBRARY:
        return BEHAVIOR_ARCHETYPE_LIBRARY[archetype]
    return BEHAVIOR_ARCHETYPE_LIBRARY["求助配合型"]


def _infer_behavior_archetype(person: dict[str, Any] | None) -> str:
    person = person or {}
    explicit = _clean_text(person.get("behavior_archetype"))
    if explicit in BEHAVIOR_ARCHETYPE_LIBRARY:
        return explicit

    role_type = _clean_text(person.get("role_type") or person.get("role"))
    status = _clean_text(person.get("status"))
    text = " ".join(
        [
            _clean_text(person.get("personality")),
            _clean_text(person.get("speaking_style")),
            _clean_text(person.get("interaction_style")),
            _clean_text(person.get("current_goal")),
            _clean_text(person.get("core_concern")),
            _clean_text(person.get("weakness")),
            _clean_text(person.get("pressure_response")),
            _clean_text(person.get("authority_attitude")),
        ]
    )

    if any(token in text for token in ["轻生", "跳楼", "绝望", "不想活", "没意义", "别管我"]):
        return "绝望封闭型"
    if any(token in (status + text) for token in ["醉", "酒", "喝多", "失控"]):
        return "醉酒失控型"
    if any(token in text for token in ["起哄", "围观", "带节奏", "煽动"]):
        return "围观起哄型"
    if role_type == "嫌疑人" or any(token in text for token in ["切责", "误会", "不是我先", "别定性", "先切责任"]):
        return "防御切责型"
    if role_type in {"被害人", "受害人"} or any(token in text for token in ["委屈", "吃亏", "受伤", "哭", "情绪"]):
        return "委屈宣泄型"
    if any(token in text for token in ["对抗", "强势", "嘴硬", "反问", "顶嘴", "不服"]):
        return "强硬对抗型"
    if any(token in text for token in ["观察", "谨慎", "怕事", "紧张", "试探", "回避"]):
        return "谨慎回避型"
    return "求助配合型"


def _build_surface_stance(police_attitude: str, defaults: dict[str, Any], current_goal: str) -> str:
    if current_goal and police_attitude == "主动求助":
        return f"我现在主要想{current_goal}，你们先帮我把事情稳下来。"
    if police_attitude == "试探观望":
        return "我可以配合，但我只说我自己确定的部分。"
    if police_attitude == "防备排斥":
        return "我可以说，但你们别先给我定性。"
    if police_attitude == "敌对抵触":
        return "你们别先冲着我来，我没你们想得那样。"
    return _clean_text(defaults.get("surface_stance"))


def normalize_scene_specific_fields(
    person: dict[str, Any] | None,
    *,
    scene: Any | None = None,
    case: Any | None = None,
    explicit_mode: str = "",
) -> dict[str, Any]:
    person = person or {}
    case_type = _pick_first_non_empty(person.get("case_type"), getattr(case, "case_type", ""))
    scene_name = _pick_first_non_empty(person.get("scene_name"), getattr(scene, "name", ""))
    scene_stages = person.get("scene_stages")
    if scene is not None and scene_stages in (None, ""):
        scene_stages = getattr(scene, "stages", [])

    scene_behavior_mode = _pick_first_non_empty(
        explicit_mode,
        person.get("scene_behavior_mode"),
        infer_scene_behavior_mode(scene_name, case_type, scene_stages),
    ) or "核查取证型"

    fields = {field: _dedupe(_to_list(person.get(field))) for field in SCENE_BOUNDARY_LIST_FIELDS}
    impairment_state = _normalize_impairment_state(person)

    legacy_known = _dedupe(_to_list(person.get("knows_facts")))
    legacy_hidden = _dedupe(_to_list(person.get("hidden_truths")))
    legacy_unknown = _dedupe(_to_list(person.get("does_not_know")))
    trigger_points = _dedupe(_to_list(person.get("trigger_points")) + _to_list(person.get("trigger_topics")))
    calming_points = _dedupe(_to_list(person.get("calming_points")))
    relationship_pressure = _dedupe(_to_list(person.get("relationship_pressure")))
    protected_targets = _dedupe(_to_list(person.get("protected_targets")))
    current_goal = _pick_first_non_empty(person.get("current_goal"), person.get("current_need"), person.get("private_drive"))
    core_concern = _pick_first_non_empty(person.get("core_concern"), person.get("weakness"))

    if scene_behavior_mode == "核查取证型":
        if not fields["known_key_points"]:
            fields["known_key_points"] = legacy_known[:4]
        if not fields["withheld_key_points"]:
            fields["withheld_key_points"] = legacy_hidden[:4]
    elif scene_behavior_mode == "调解型":
        if not fields["conflict_core"]:
            fields["conflict_core"] = _dedupe([core_concern, *legacy_known[:2]])[:3]
        if not fields["acceptable_outcomes"]:
            fields["acceptable_outcomes"] = _dedupe([current_goal, *calming_points[:2]])[:3]
        if not fields["no_go_topics"]:
            fields["no_go_topics"] = _dedupe([*trigger_points[:3], *legacy_hidden[:1]])[:4]
    elif scene_behavior_mode == "危机干预型":
        if not fields["trigger_sources"]:
            fields["trigger_sources"] = _dedupe([*trigger_points[:3], core_concern])[:4]
        if not fields["concerned_targets"]:
            fields["concerned_targets"] = _dedupe([*protected_targets[:3], *relationship_pressure[:2]])[:4]
        if not fields["taboo_actions"]:
            fields["taboo_actions"] = _dedupe([*legacy_hidden[:1], *legacy_unknown[:1]])[:3]
    elif scene_behavior_mode == "管控型":
        if not fields["escalation_actions"]:
            fields["escalation_actions"] = _dedupe([*trigger_points[:3], *legacy_hidden[:1]])[:4]
        if not fields["deescalation_conditions"]:
            fields["deescalation_conditions"] = _dedupe([*calming_points[:3], current_goal])[:4]

    return {
        "scene_behavior_mode": scene_behavior_mode,
        **fields,
        "impairment_state": impairment_state,
    }


def normalize_compact_persona_fields(person: dict[str, Any] | None) -> dict[str, Any]:
    person = person or {}
    behavior_archetype = _infer_behavior_archetype(person)
    archetype_defaults = get_behavior_archetype_defaults(behavior_archetype)
    scene_specific = normalize_scene_specific_fields(person)

    protected_targets = _to_list(person.get("protected_targets"))
    feared_people = _to_list(person.get("feared_people"))
    conflict_targets = _to_list(person.get("conflict_targets"))
    feared_consequences = _to_list(person.get("feared_consequences"))

    relationship_pressure = _dedupe(_to_list(person.get("relationship_pressure")))
    if not relationship_pressure:
        relationship_pressure = _dedupe(
            [f"护着{item}" for item in protected_targets[:2]]
            + [f"忌惮{item}" for item in feared_people[:2]]
            + [f"和{item}有旧怨或关系压力" for item in conflict_targets[:2]]
            + [str(item).strip() for item in feared_consequences[:2] if str(item).strip()]
        )

    current_goal = _pick_first_non_empty(
        person.get("current_goal"),
        person.get("current_need"),
        person.get("private_drive"),
    )
    if not current_goal:
        current_goal = _pick_first_non_empty(
            (scene_specific.get("acceptable_outcomes") or [None])[0],
            (scene_specific.get("deescalation_conditions") or [None])[0],
        )

    core_concern = _pick_first_non_empty(
        person.get("core_concern"),
        person.get("weakness"),
        feared_consequences[0] if feared_consequences else "",
        f"怕{protected_targets[0]}被牵连" if protected_targets else "",
    )
    if not core_concern:
        core_concern = _pick_first_non_empty(
            (scene_specific.get("conflict_core") or [None])[0],
            (scene_specific.get("trigger_sources") or [None])[0],
            (scene_specific.get("escalation_actions") or [None])[0],
        )

    police_attitude = _pick_first_non_empty(
        person.get("police_attitude"),
        person.get("authority_attitude"),
        archetype_defaults.get("police_attitude"),
    )

    surface_stance = _pick_first_non_empty(
        person.get("surface_stance"),
        person.get("public_mask"),
        _build_surface_stance(police_attitude, archetype_defaults, current_goal),
        person.get("self_image"),
    )

    pressure_response = _pick_first_non_empty(
        person.get("pressure_response"),
        person.get("stress_response"),
        archetype_defaults.get("pressure_response"),
        person.get("authority_attitude"),
    )

    trigger_points = _dedupe(_to_list(person.get("trigger_points")) + _to_list(person.get("trigger_topics")))
    trigger_points = _dedupe(
        trigger_points
        + (scene_specific.get("no_go_topics") or [])
        + (scene_specific.get("trigger_sources") or [])
        + (scene_specific.get("escalation_actions") or [])
        + [f"做出{item}" for item in scene_specific.get("taboo_actions") or []]
    )
    if not trigger_points:
        trigger_points = _dedupe(_to_list(archetype_defaults.get("trigger_points")))

    calming_points = _dedupe(_to_list(person.get("calming_points")))
    calming_points = _dedupe(
        calming_points
        + (scene_specific.get("acceptable_outcomes") or [])
        + (scene_specific.get("deescalation_conditions") or [])
    )
    if not calming_points:
        calming_points = _dedupe(_to_list(archetype_defaults.get("calming_points")))

    relationship_pressure = _dedupe(
        relationship_pressure
        + [f"牵挂{item}" for item in scene_specific.get("concerned_targets") or []]
    )

    emotion_level = _pick_first_non_empty(
        person.get("emotion_level"),
        _infer_level_from_score(person.get("init_emotion", archetype_defaults.get("init_emotion", 50))),
    )
    cooperation_level = _pick_first_non_empty(
        person.get("cooperation_level"),
        _infer_level_from_score(person.get("init_trust", archetype_defaults.get("init_trust", 30))),
    )
    risk_level = _pick_first_non_empty(
        person.get("risk_level"),
        _infer_level_from_score(person.get("init_risk", archetype_defaults.get("init_risk", 50))),
    )
    clarity_level = _pick_first_non_empty(
        person.get("clarity_level"),
        _infer_level_from_score(
            person.get("init_expression_clarity", archetype_defaults.get("init_expression_clarity", 52))
        ),
    )

    return {
        "behavior_archetype": behavior_archetype,
        "police_attitude": police_attitude,
        "current_goal": current_goal,
        "core_concern": core_concern,
        "relationship_pressure": relationship_pressure,
        "surface_stance": surface_stance,
        "pressure_response": pressure_response,
        "trigger_points": trigger_points,
        "calming_points": calming_points,
        "scene_behavior_mode": scene_specific.get("scene_behavior_mode") or "核查取证型",
        "emotion_level": emotion_level,
        "cooperation_level": cooperation_level,
        "risk_level": risk_level,
        "clarity_level": clarity_level,
        "init_emotion": _score_from_level(emotion_level, person.get("init_emotion") or archetype_defaults.get("init_emotion", 50)),
        "init_trust": _score_from_level(cooperation_level, person.get("init_trust") or archetype_defaults.get("init_trust", 30)),
        "init_risk": _score_from_level(risk_level, person.get("init_risk") or archetype_defaults.get("init_risk", 50)),
        "init_expression_clarity": _score_from_level(
            clarity_level,
            person.get("init_expression_clarity") or archetype_defaults.get("init_expression_clarity", 52),
        ),
        **scene_specific,
    }


def _load_case_structured(case) -> dict[str, Any]:
    if not case or not getattr(case, "structured_data", None):
        return {}
    try:
        parsed = json.loads(case.structured_data)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_role_persona_meta(role) -> dict[str, Any]:
    if not role:
        return {}
    raw_value = getattr(role, "persona_meta", None)
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _load_person_meta(role, case=None) -> dict[str, Any]:
    structured = _load_case_structured(case)
    persons = structured.get("persons") or []
    if not isinstance(persons, list):
        return _load_role_persona_meta(role)
    role_name = _clean_text(getattr(role, "name", ""))
    for person in persons:
        if _clean_text((person or {}).get("name")) == role_name:
            return person if isinstance(person, dict) else {}
    return _load_role_persona_meta(role)


def infer_persona_template(person: dict[str, Any]) -> dict[str, Any]:
    person = person or {}
    role_type = _clean_text(person.get("role_type") or person.get("role"))
    compact_fields = normalize_compact_persona_fields(person)
    scene_specific = normalize_scene_specific_fields(person, explicit_mode=compact_fields.get("scene_behavior_mode") or "")
    behavior_archetype = compact_fields.get("behavior_archetype") or "求助配合型"
    archetype_defaults = get_behavior_archetype_defaults(behavior_archetype)
    personality = _pick_first_non_empty(person.get("personality"), archetype_defaults.get("personality"))
    speaking_style = _pick_first_non_empty(person.get("speaking_style"), archetype_defaults.get("speaking_style"))
    weakness = _pick_first_non_empty(person.get("weakness"), compact_fields.get("core_concern"))
    status = _clean_text(person.get("status"))
    hidden_truths = _to_list(person.get("hidden_truths"))
    knows_facts = _to_list(person.get("knows_facts"))

    protected_targets = _to_list(person.get("protected_targets"))
    feared_people = _to_list(person.get("feared_people"))
    conflict_targets = _to_list(person.get("conflict_targets"))
    feared_consequences = _to_list(person.get("feared_consequences"))
    trigger_topics = compact_fields.get("trigger_points") or _to_list(person.get("trigger_topics"))
    calming_points = compact_fields.get("calming_points") or _to_list(person.get("calming_points"))
    coping_patterns = _to_list(person.get("coping_patterns"))

    self_image = _pick_first_non_empty(person.get("self_image"))
    current_need = _pick_first_non_empty(person.get("current_need"), compact_fields.get("current_goal"))
    authority_attitude = _pick_first_non_empty(
        person.get("authority_attitude"),
        person.get("police_attitude"),
        compact_fields.get("police_attitude"),
        archetype_defaults.get("authority_attitude"),
        compact_fields.get("pressure_response"),
    )
    stress_response = _pick_first_non_empty(person.get("stress_response"), compact_fields.get("pressure_response"))
    public_mask = _pick_first_non_empty(person.get("public_mask"), compact_fields.get("surface_stance"))
    private_drive = _pick_first_non_empty(person.get("private_drive"), compact_fields.get("current_goal"))

    if not self_image:
        if role_type == "嫌疑人":
            self_image = "自己不是坏人，只是被逼到那一步，或者事情没有外界说得那么严重"
        elif role_type in {"被害人", "受害人"}:
            self_image = "自己是吃亏和受委屈的一方，希望警方先理解自己的遭遇"
        elif role_type == "证人":
            self_image = "自己只是看到部分经过的人，不想无端卷入更大的麻烦"
        else:
            self_image = "自己是有现实难处的普通人，希望先把眼前风险稳住"

    if not current_need:
        if feared_consequences:
            current_need = feared_consequences[0]
        elif protected_targets:
            current_need = f"保住{protected_targets[0]}不被牵连"
        elif role_type == "嫌疑人":
            current_need = "先切开主动责任，避免把最重的后果落到自己头上"
        elif role_type == "证人":
            current_need = "既把事情说过去，又别让自己成为冲突中心"
        else:
            current_need = "先把最现实的损失、责任或关系风险降下来"

    if not authority_attitude:
        if any(token in personality + speaking_style for token in ["嘴硬", "冲", "对抗", "强势", "不服"]):
            authority_attitude = "表面容易顶撞或辩解，但如果警方抓住事实链，会慢慢收口"
        elif any(token in personality + speaking_style for token in ["怕事", "胆小", "紧张", "怯"]):
            authority_attitude = "本能紧张，既想配合又怕说多了惹祸"
        else:
            authority_attitude = "会先观察警方态度，再决定是保守说、试探说，还是逐步补充"

    if not stress_response:
        if any(token in personality + speaking_style for token in ["急躁", "冲动", "暴躁", "激动"]):
            stress_response = "被追急时会提高音量、打断、跑题，先把情绪顶在前面"
        elif any(token in personality + speaking_style for token in ["精明", "算计", "冷静", "自私"]):
            stress_response = "受压后会先算后果，优先切责任、缩细节、观察警方掌握到哪一步"
        else:
            stress_response = "受压后容易先模糊回答，再根据警方态度决定补多少"

    if not coping_patterns:
        if _to_list(archetype_defaults.get("coping_patterns")):
            coping_patterns = _to_list(archetype_defaults.get("coping_patterns"))
        elif role_type == "嫌疑人":
            coping_patterns = ["淡化主动性", "把行为说成误会或气头上", "先切割最重责任"]
        elif role_type == "证人":
            coping_patterns = ["缩小自己看到的范围", "先说记不清", "避免明确站队"]
        else:
            coping_patterns = ["先说对自己有利的部分", "对敏感点避重就轻"]

    if not trigger_topics:
        if protected_targets:
            trigger_topics.append(f"{protected_targets[0]}是否会被牵连")
        if feared_consequences:
            trigger_topics.append(feared_consequences[0])
        if conflict_targets:
            trigger_topics.append(f"和{conflict_targets[0]}的旧账或冲突")
        if weakness:
            trigger_topics.append(weakness)
        trigger_topics = _dedupe(trigger_topics)[:3]

    if not public_mask:
        default_surface = _build_surface_stance(
            compact_fields.get("police_attitude") or authority_attitude,
            archetype_defaults,
            compact_fields.get("current_goal") or current_need,
        )
        if default_surface:
            public_mask = default_surface
        elif role_type == "嫌疑人":
            public_mask = "我没有你们想得那么严重，很多事不是我主动挑起来的"
        elif role_type == "证人":
            public_mask = "我就是看到一点，不敢乱说，也不想冤枉谁"
        else:
            public_mask = "我先把我自己确定的部分讲出来，不确定的我不乱说"

    if not private_drive:
        if protected_targets:
            private_drive = f"先把{protected_targets[0]}或和对方有关的麻烦挡在自己这里，别继续扩大"
        elif feared_consequences:
            private_drive = f"尽量别让事情走到“{feared_consequences[0]}”那一步"
        elif hidden_truths:
            private_drive = "尽量把最伤自己的那部分细节往后拖，不到必要不主动说"
        else:
            private_drive = "边看警方掌握了多少，边决定哪些话现在能说、哪些先保留"

    return {
        "behavior_archetype": behavior_archetype,
        "police_attitude": compact_fields.get("police_attitude") or authority_attitude,
        "current_goal": compact_fields.get("current_goal") or current_need,
        "core_concern": compact_fields.get("core_concern") or weakness,
        "relationship_pressure": compact_fields.get("relationship_pressure") or [],
        "surface_stance": compact_fields.get("surface_stance") or public_mask,
        "pressure_response": compact_fields.get("pressure_response") or stress_response,
        "trigger_points": compact_fields.get("trigger_points") or trigger_topics,
        "calming_points": calming_points,
        "self_image": self_image,
        "current_need": current_need,
        "authority_attitude": authority_attitude,
        "stress_response": stress_response,
        "protected_targets": protected_targets,
        "feared_people": feared_people,
        "conflict_targets": conflict_targets,
        "feared_consequences": feared_consequences,
        "trigger_topics": trigger_topics,
        "coping_patterns": coping_patterns,
        "public_mask": public_mask,
        "private_drive": private_drive,
        "scene_behavior_mode": scene_specific.get("scene_behavior_mode") or compact_fields.get("scene_behavior_mode") or "核查取证型",
        "emotion_level": compact_fields.get("emotion_level") or _infer_level_from_score(compact_fields.get("init_emotion", 50)),
        "cooperation_level": compact_fields.get("cooperation_level") or _infer_level_from_score(compact_fields.get("init_trust", 30)),
        "risk_level": compact_fields.get("risk_level") or _infer_level_from_score(compact_fields.get("init_risk", 50)),
        "clarity_level": compact_fields.get("clarity_level") or _infer_level_from_score(compact_fields.get("init_expression_clarity", 52)),
        "init_emotion": compact_fields.get("init_emotion"),
        "init_trust": compact_fields.get("init_trust"),
        "init_risk": compact_fields.get("init_risk"),
        "init_expression_clarity": compact_fields.get("init_expression_clarity"),
        **scene_specific,
    }


PERSONA_SIGNAL_LIBRARY = [
    {
        "keywords": ["爱占便宜", "斤斤计较", "抠门", "贪小便宜"],
        "motives": ["对赔偿、损失和占便宜机会比较敏感"],
        "soft_spots": ["一谈到赔钱、吃亏、补偿，就更容易被触动"],
        "defenses": ["会先算账，再决定要不要配合"],
        "habits": ["喜欢反复强调自己吃了多少亏"],
        "breakthroughs": ["把损失、赔偿和责任讲清楚，更容易让其松口"],
    },
    {
        "keywords": ["冷漠", "自私", "只顾自己", "精明利己"],
        "motives": ["优先保护自身利益，不愿替别人承担风险"],
        "defenses": ["一旦觉得会牵连自己，就会迅速切割关系"],
        "triggers": ["被质疑责任或被要求站队时更容易防御"],
        "habits": ["常说和自己无关、只是路过、只是听说"],
    },
    {
        "keywords": ["护短", "溺爱", "心疼孩子", "护着家里人"],
        "soft_spots": ["涉及晚辈或家里人安危时更容易动摇"],
        "defenses": ["为了保住亲近的人，可能会选择性隐瞒或替人圆话"],
        "breakthroughs": ["从家人后果、老人担忧、未成年人影响切入更有效"],
        "triggers": ["感觉家里人被针对时，情绪更容易上升"],
    },
    {
        "keywords": ["嘴硬", "逞强", "好面子", "死要面子"],
        "motives": ["想保住体面，不愿当场示弱"],
        "defenses": ["即便心虚也可能先强撑"],
        "habits": ["会先反问、顶嘴、淡化问题严重性"],
        "breakthroughs": ["给台阶、留体面，比硬压更容易突破"],
    },
    {
        "keywords": ["急躁", "冲动", "暴躁", "易怒"],
        "triggers": ["被连续追问、被误解、被打断时更容易爆发"],
        "defenses": ["情绪上来时会打断、跑题、提高音量"],
        "breakthroughs": ["先稳情绪再问细节，否则信息质量会下降"],
    },
    {
        "keywords": ["胆小", "怕事", "怯懦", "容易紧张"],
        "motives": ["优先求稳，避免惹事上身"],
        "soft_spots": ["只要感到安全、被理解，就更愿意补充细节"],
        "defenses": ["容易说不知道、记不清，未必代表完全不知情"],
        "breakthroughs": ["降低压迫感、拆小问题、反复确认能提高开口率"],
    },
    {
        "keywords": ["讲义气", "护朋友", "重感情", "顾面子"],
        "motives": ["既想保住关系，又不想显得不仗义"],
        "defenses": ["会避免直接指认熟人或朋友"],
        "breakthroughs": ["先确认客观经过，再逐步切到人物责任更有效"],
    },
]


def _collect_signal_items(source_text: str, field_name: str) -> dict[str, list[str]]:
    result = {
        "motives": [],
        "soft_spots": [],
        "defenses": [],
        "triggers": [],
        "habits": [],
        "breakthroughs": [],
    }
    for item in PERSONA_SIGNAL_LIBRARY:
        if any(keyword in source_text for keyword in item["keywords"]):
            for key in result:
                for value in item.get(key, []):
                    result[key].append(f"{field_name}提示：{value}")
    return result


def build_relationship_map(role, case=None) -> dict[str, Any]:
    structured = _load_case_structured(case)
    fact_sheet = structured.get("fact_sheet", {}) if isinstance(structured, dict) else {}
    relationships = fact_sheet.get("relationships") or structured.get("relationships") or []
    role_name = _clean_text(getattr(role, "name", ""))

    direct_links = []
    protected_targets = []
    tension_targets = []
    dependency_targets = []

    for item in relationships:
        if not isinstance(item, dict):
            continue
        from_name = _clean_text(item.get("from"))
        to_name = _clean_text(item.get("to"))
        relation = _clean_text(item.get("relation"))
        if role_name not in {from_name, to_name}:
            continue

        other = to_name if from_name == role_name else from_name
        if not other:
            continue
        relation_text = relation or "关系待核实"
        direct_links.append(f"{other}:{relation_text}")

        if any(token in relation_text for token in ["家人", "母子", "父子", "夫妻", "祖孙", "亲属", "恋人", "同住"]):
            protected_targets.append(f"{other}:{relation_text}")
        if any(token in relation_text for token in ["矛盾", "冲突", "积怨", "纠纷", "对立", "欠款", "竞争"]):
            tension_targets.append(f"{other}:{relation_text}")
        if any(token in relation_text for token in ["依赖", "照顾", "雇佣", "跟着", "帮忙", "求助"]):
            dependency_targets.append(f"{other}:{relation_text}")

    return {
        "direct_links": _dedupe(direct_links)[:6],
        "protected_targets": _dedupe(protected_targets)[:4],
        "tension_targets": _dedupe(tension_targets)[:4],
        "dependency_targets": _dedupe(dependency_targets)[:4],
    }


def build_contradiction_archive(role, relationship_map: dict[str, Any]) -> dict[str, Any]:
    personality = _clean_text(getattr(role, "personality", ""))
    weakness = _clean_text(getattr(role, "weakness", ""))
    role_type = _clean_text(getattr(role, "role_type", "相关人员"))

    contradictions = []
    pressure_points = []

    if "爱占便宜" in personality and relationship_map["protected_targets"]:
        contradictions.append("平时很计较得失，但遇到自己护着的人时，可能宁可吃亏也先护短。")
    if any(token in personality for token in ["冷漠", "自私", "精明"]) and relationship_map["protected_targets"]:
        contradictions.append("表面强调先顾自己，但涉及亲近对象时会突然变得强势维护。")
    if any(token in personality for token in ["嘴硬", "好面子", "逞强"]) and weakness:
        contradictions.append("嘴上不愿示弱，但一旦被碰到弱点，态度会明显松动或反弹。")
    if role_type == "证人" and relationship_map["tension_targets"]:
        contradictions.append("既想把自己摘干净，也可能因为旧怨带着倾向性陈述。")
    if role_type == "嫌疑人" and relationship_map["protected_targets"]:
        contradictions.append("一边规避自我归责，一边可能替亲近对象揽事或圆话。")

    if relationship_map["protected_targets"]:
        pressure_points.append("提到其护着的人时，容易偏袒、激动或转移责任。")
    if relationship_map["tension_targets"]:
        pressure_points.append("提到旧账、积怨或利益冲突时，更容易带情绪。")
    if relationship_map["dependency_targets"]:
        pressure_points.append("一旦牵扯生计和现实依赖，回答会突然谨慎。")
    if weakness:
        pressure_points.append(f"原始弱点：{weakness}")

    if not contradictions:
        contradictions.append("这个人未必始终表里一致，现实处境可能让其嘴上和心里出现落差。")

    return {
        "contradictions": contradictions[:4],
        "pressure_points": pressure_points[:4],
    }


def build_persona_profile(role, case=None, scene=None) -> dict[str, Any]:
    personality = _clean_text(getattr(role, "personality", ""))
    interaction_style = _clean_text(getattr(role, "interaction_style", ""))
    speaking_style = _clean_text(getattr(role, "speaking_style", ""))
    weakness = _clean_text(getattr(role, "weakness", ""))
    role_type = _clean_text(getattr(role, "role_type", "相关人员"))
    status = _clean_text(getattr(role, "status", "正常"))
    hidden_truths = _to_list(getattr(role, "hidden_truths", []))
    knows_facts = _to_list(getattr(role, "knows_facts", []))
    unknown_facts = _to_list(getattr(role, "does_not_know", []))
    source_text = " ".join([personality, interaction_style, speaking_style, weakness, " ".join(hidden_truths)])
    person_meta = _load_person_meta(role, case)
    compact_fields = normalize_compact_persona_fields(person_meta)
    scene_specific = normalize_scene_specific_fields(
        person_meta,
        scene=scene,
        case=case,
        explicit_mode=compact_fields.get("scene_behavior_mode") or "",
    )
    behavior_archetype = compact_fields.get("behavior_archetype") or _infer_behavior_archetype(person_meta)
    protected_targets = _to_list(person_meta.get("protected_targets"))
    feared_people = _to_list(person_meta.get("feared_people"))
    conflict_targets = _to_list(person_meta.get("conflict_targets"))
    feared_consequences = _to_list(person_meta.get("feared_consequences"))
    relationship_pressure = compact_fields.get("relationship_pressure") or []
    trigger_topics = compact_fields.get("trigger_points") or _to_list(person_meta.get("trigger_topics"))
    calming_points = compact_fields.get("calming_points") or _to_list(person_meta.get("calming_points"))
    coping_patterns = _to_list(person_meta.get("coping_patterns"))
    self_image = _clean_text(person_meta.get("self_image"))
    current_need = _pick_first_non_empty(person_meta.get("current_need"), compact_fields.get("current_goal"))
    police_attitude = _pick_first_non_empty(person_meta.get("police_attitude"), compact_fields.get("police_attitude"))
    authority_attitude = _pick_first_non_empty(
        person_meta.get("authority_attitude"),
        police_attitude,
        compact_fields.get("pressure_response"),
    )
    stress_response = _pick_first_non_empty(person_meta.get("stress_response"), compact_fields.get("pressure_response"))
    public_mask = _pick_first_non_empty(person_meta.get("public_mask"), compact_fields.get("surface_stance"))
    private_drive = _pick_first_non_empty(person_meta.get("private_drive"), compact_fields.get("current_goal"))
    core_concern = _pick_first_non_empty(compact_fields.get("core_concern"), weakness)
    emotion_level = _pick_first_non_empty(person_meta.get("emotion_level"), compact_fields.get("emotion_level"))
    cooperation_level = _pick_first_non_empty(person_meta.get("cooperation_level"), compact_fields.get("cooperation_level"))
    risk_level = _pick_first_non_empty(person_meta.get("risk_level"), compact_fields.get("risk_level"))
    clarity_level = _pick_first_non_empty(person_meta.get("clarity_level"), compact_fields.get("clarity_level"))
    impairment_state = _pick_first_non_empty(person_meta.get("impairment_state"), scene_specific.get("impairment_state"))

    collected = {
        "motives": [],
        "soft_spots": [],
        "defenses": [],
        "triggers": [],
        "habits": [],
        "breakthroughs": [],
    }
    for text, name in [(personality, "性格"), (interaction_style, "互动风格"), (weakness, "弱点"), (speaking_style, "说话风格")]:
        signal_items = _collect_signal_items(text, name)
        for key in collected:
            collected[key].extend(signal_items[key])

    if interaction_style == "对抗型":
        collected["defenses"].extend([
            "互动风格提示：对质疑会本能反驳，容易抢话、顶嘴或质疑警方判断。",
            "互动风格提示：不愿轻易接受定性，更倾向先争辩再补细节。",
        ])
    elif interaction_style == "情绪型":
        collected["triggers"].append("互动风格提示：一旦感觉委屈、被误解或被逼迫，情绪起伏会更明显。")
        collected["habits"].append("互动风格提示：表达可能跳跃、重复、夹杂抱怨和情绪宣泄。")
    elif interaction_style == "观察型":
        collected["defenses"].append("互动风格提示：会先观察警方掌握程度和态度，再决定说多少。")
        collected["habits"].append("互动风格提示：回答更谨慎，容易停顿、试探、避免一次说满。")
    else:
        collected["breakthroughs"].append("互动风格提示：如果警方态度平稳、问题具体，通常更愿意继续配合。")

    if role_type == "嫌疑人":
        collected["defenses"].extend([
            "角色身份提示：会优先规避自我归责，避免留下直接承认责任的话柄。",
            "角色身份提示：更容易把问题说成误会、偶发冲突或对方先挑事。",
        ])
        collected["breakthroughs"].append("角色身份提示：围绕时间线、矛盾点和客观细节反复核实，更容易逼近真实说法。")
    elif role_type == "证人":
        collected["defenses"].append("角色身份提示：担心惹麻烦时，可能主动缩小自己看到的内容。")
        collected["breakthroughs"].append("角色身份提示：先给安全感，再逐步追问细节，证人更可能补充关键信息。")
    elif role_type in {"被害人", "受害人"}:
        collected["triggers"].append("角色身份提示：回忆受害经过时，可能出现明显情绪波动和表达跳跃。")
    elif role_type == "民警":
        collected["habits"].append("角色身份提示：表达更流程化，更强调现场处置与事实核查。")

    if "常规" in speaking_style or not speaking_style:
        collected["habits"].append("语言风格提示：多数情况下会用日常口语，不会一直书面化表达。")
    if any(token in speaking_style for token in ["急", "快", "慌", "乱"]):
        collected["habits"].append("语言风格提示：说话偏快，容易跳词、省略和重复。")
    if any(token in speaking_style for token in ["抗拒", "硬", "冲"]):
        collected["defenses"].append("语言风格提示：被追问时更可能反问、顶撞、转移话题。")
    if any(token in speaking_style for token in ["冷静", "平", "慢"]):
        collected["habits"].append("语言风格提示：回答表面克制，但不代表真实完全放松。")

    if hidden_truths:
        collected["defenses"].append("隐瞒信息提示：有明确不想主动说出的内容，通常不会第一轮追问就交代。")
    if protected_targets:
        collected["soft_spots"].append(f"明确护着的人：{'、'.join(protected_targets[:3])}")
        collected["defenses"].append("人物关系提示：涉及其护着的人时，更可能替对方遮挡、弱化或改口。")
    if feared_people:
        collected["defenses"].append(f"明确忌惮对象：{'、'.join(feared_people[:3])}")
    if feared_consequences:
        collected["soft_spots"].append(f"最怕后果：{'、'.join(feared_consequences[:3])}")
    if relationship_pressure:
        collected["soft_spots"].append(f"关系压力：{'、'.join(relationship_pressure[:3])}")
    if trigger_topics:
        collected["triggers"].append(f"明确敏感话题：{'、'.join(trigger_topics[:3])}")
    if calming_points:
        collected["breakthroughs"].append(f"明确安抚点：{'、'.join(calming_points[:3])}")
    if scene_specific.get("known_key_points"):
        collected["motives"].append(f"掌握的关键点：{'、'.join((scene_specific.get('known_key_points') or [])[:3])}")
    if scene_specific.get("withheld_key_points"):
        collected["defenses"].append(f"不愿主动说的关键点：{'、'.join((scene_specific.get('withheld_key_points') or [])[:3])}")
    if scene_specific.get("conflict_core"):
        collected["motives"].append(f"矛盾核心：{'、'.join((scene_specific.get('conflict_core') or [])[:3])}")
    if scene_specific.get("acceptable_outcomes"):
        collected["breakthroughs"].append(f"可接受结果：{'、'.join((scene_specific.get('acceptable_outcomes') or [])[:3])}")
    if scene_specific.get("no_go_topics"):
        collected["triggers"].append(f"不能碰的话：{'、'.join((scene_specific.get('no_go_topics') or [])[:3])}")
    if scene_specific.get("trigger_sources"):
        collected["triggers"].append(f"刺激源：{'、'.join((scene_specific.get('trigger_sources') or [])[:3])}")
    if scene_specific.get("concerned_targets"):
        collected["soft_spots"].append(f"牵挂对象：{'、'.join((scene_specific.get('concerned_targets') or [])[:3])}")
    if scene_specific.get("taboo_actions"):
        collected["defenses"].append(f"禁忌动作：{'、'.join((scene_specific.get('taboo_actions') or [])[:3])}")
    if scene_specific.get("escalation_actions"):
        collected["triggers"].append(f"升级动作：{'、'.join((scene_specific.get('escalation_actions') or [])[:3])}")
    if scene_specific.get("deescalation_conditions"):
        collected["breakthroughs"].append(f"收敛条件：{'、'.join((scene_specific.get('deescalation_conditions') or [])[:3])}")
    if impairment_state:
        collected["habits"].append(f"受酒精/药物/精神状态影响：{impairment_state}")
    if coping_patterns:
        collected["defenses"].append(f"常用防御动作：{'、'.join(coping_patterns[:3])}")
    if self_image:
        collected["motives"].append(f"自我定位：{self_image}")
    if current_need:
        collected["motives"].append(f"当下最想保住/达成：{current_need}")
    if behavior_archetype:
        collected["motives"].append(f"行为原型：{behavior_archetype}")
    if police_attitude:
        collected["defenses"].append(f"对警方基本态度：{police_attitude}")
    if authority_attitude:
        collected["defenses"].append(f"对权威/警方态度：{authority_attitude}")
    if stress_response:
        collected["habits"].append(f"受压后的反应：{stress_response}")
    if public_mask:
        collected["habits"].append(f"表面口径：{public_mask}")
    if private_drive:
        collected["motives"].append(f"内心盘算：{private_drive}")
    if weakness:
        collected["soft_spots"].append(f"弱点原文：{weakness}")
    if personality:
        collected["motives"].append(f"性格基调：{personality}")
    if source_text and not collected["breakthroughs"]:
        collected["breakthroughs"].append("优先从其在意的损失、关系、体面或风险后果切入，更容易打开缺口。")

    likely_biases = []
    if any(token in source_text for token in ["记不清", "糊涂", "紧张", "慢"]):
        likely_biases.append("在高压下可能记忆片段化，先后顺序会说乱。")
    if any(token in source_text for token in ["护短", "护着", "溺爱", "家里人"]):
        likely_biases.append("涉及亲属责任时，可能本能偏袒自己人。")
    if any(token in source_text for token in ["爱面子", "嘴硬", "逞强"]):
        likely_biases.append("即便内心动摇，也可能先表现出强硬或不在乎。")
    if any(token in source_text for token in ["爱占便宜", "算计", "抠门"]):
        likely_biases.append("谈到损失、补偿和谁吃亏时，会明显更较真。")

    disclosure_ladder = [
        "低信任时：优先给碎片化、模糊、保守的信息，必要时回避关键节点。",
        "中信任时：愿意补充可验证的客观细节，但对敏感责任仍会保留。",
        "高信任或被击中弱点时：会逐步松口，可能承认之前刻意省略的事实。",
    ]
    if hidden_truths:
        disclosure_ladder.append(f"特殊隐瞒点：{'; '.join(hidden_truths[:3])}")

    relationship_map = build_relationship_map(role, case)
    if protected_targets:
        relationship_map["protected_targets"] = _dedupe(protected_targets + relationship_map["protected_targets"])[:4]
    if conflict_targets:
        relationship_map["tension_targets"] = _dedupe(conflict_targets + relationship_map["tension_targets"])[:4]
    contradiction_archive = build_contradiction_archive(role, relationship_map)
    if public_mask and private_drive:
        contradiction_archive["contradictions"].insert(0, f"嘴上常表现为“{public_mask}”，但心里真正更在意“{private_drive}”。")
    if feared_consequences:
        contradiction_archive["pressure_points"] = _dedupe(
            [f"明确害怕的后果：{item}" for item in feared_consequences] + contradiction_archive["pressure_points"]
        )[:4]
    if current_need:
        contradiction_archive["pressure_points"] = _dedupe(
            [f"当前最想保住/达成：{current_need}"] + contradiction_archive["pressure_points"]
        )[:4]
    if authority_attitude and any(token in authority_attitude for token in ["敌意", "不信", "抗拒", "排斥", "怕"]):
        contradiction_archive["contradictions"].insert(0, f"面对警方/权威时常呈现“{authority_attitude}”的姿态。")

    return {
        "role_name": _clean_text(getattr(role, "name", "")) or "对话对象",
        "role_type": role_type or "相关人员",
        "behavior_archetype": behavior_archetype or "求助配合型",
        "interaction_style": interaction_style or "配合型",
        "status": status or "正常",
        "core_motives": _dedupe(collected["motives"])[:5],
        "soft_spots": _dedupe(collected["soft_spots"])[:5],
        "defensive_instincts": _dedupe(collected["defenses"])[:6],
        "emotional_triggers": _dedupe(collected["triggers"])[:5],
        "verbal_habits": _dedupe(collected["habits"])[:5],
        "breakthrough_cues": _dedupe(collected["breakthroughs"])[:5],
        "likely_biases": _dedupe(likely_biases)[:4],
        "known_facts_count": len(knows_facts),
        "hidden_truths_count": len(hidden_truths),
        "unknown_facts_count": len(unknown_facts),
        "disclosure_ladder": disclosure_ladder,
        "relationship_map": relationship_map,
        "contradictions": contradiction_archive["contradictions"],
        "pressure_points": contradiction_archive["pressure_points"],
        "police_attitude": police_attitude or authority_attitude,
        "current_goal": compact_fields.get("current_goal") or current_need,
        "core_concern": core_concern,
        "relationship_pressure": relationship_pressure,
        "surface_stance": compact_fields.get("surface_stance") or public_mask,
        "pressure_response": compact_fields.get("pressure_response") or stress_response,
        "trigger_points": trigger_topics,
        "calming_points": calming_points,
        "self_image": self_image,
        "current_need": current_need,
        "authority_attitude": authority_attitude,
        "stress_response": stress_response,
        "public_mask": public_mask,
        "private_drive": private_drive,
        "scene_behavior_mode": scene_specific.get("scene_behavior_mode") or compact_fields.get("scene_behavior_mode") or "核查取证型",
        "scene_boundary": scene_specific,
        "emotion_level": emotion_level or compact_fields.get("emotion_level") or "中",
        "cooperation_level": cooperation_level or compact_fields.get("cooperation_level") or "中",
        "risk_level": risk_level or compact_fields.get("risk_level") or "中",
        "clarity_level": clarity_level or compact_fields.get("clarity_level") or "中",
        "init_emotion": compact_fields.get("init_emotion", 50),
        "init_cooperation": compact_fields.get("init_trust", 30),
        "init_risk": compact_fields.get("init_risk", 50),
        "init_expression_clarity": compact_fields.get("init_expression_clarity", 52),
        "impairment_state": impairment_state,
        "realism_rules": [
            "回答可以犹豫、绕开、补充、反复，但不要像说明书一样机械整齐。",
            "情绪上来时允许打断、反问、讲废话、抓住某一点反复说。",
            "角色可以复杂矛盾，不必永远保持单一态度。",
        ],
    }


def build_role_script(role, case, scene, persona_profile: dict[str, Any]) -> dict[str, Any]:
    scene_name = _clean_text(getattr(scene, "name", "当前场景"))
    case_title = _clean_text(getattr(case, "title", "当前案件"))
    opening_tone = "先观察民警态度，再决定配合程度。"
    if persona_profile.get("risk_level") == "高":
        opening_tone = "眼前失控风险高，先看警方是在稳控还是继续刺激自己。"
    if persona_profile.get("clarity_level") == "低":
        opening_tone = "脑子和表达都不太稳，回答容易断、慢、跳着来。"
    if persona_profile.get("police_attitude") == "主动求助":
        opening_tone = "更在意警方是否认真处理，如果感到被重视，配合度会提升得更快。"
    elif persona_profile.get("police_attitude") == "敌对抵触":
        opening_tone = "会先摆出抗拒姿态，尤其不愿被命令式压问或当众定性。"
    if persona_profile["soft_spots"]:
        opening_tone = f"表面先稳住，但如果提到“{persona_profile['soft_spots'][0]}”相关内容，更容易出现情绪波动。"

    likely_evasions = []
    if persona_profile["defensive_instincts"]:
        likely_evasions.extend([
            "用“我记不清了”“我没太注意”先挡住关键问题。",
            "把焦点转移到别人行为、现场混乱或自己吃亏上。",
        ])
    if persona_profile["role_type"] == "嫌疑人":
        likely_evasions.append("避免直接承认主动行为，倾向说成误会、气头上或对方先挑事。")
    if persona_profile["role_type"] == "证人":
        likely_evasions.append("担心被牵连时，会缩小自己看到的范围或强调离得远。")

    return {
        "scene_anchor": f"{case_title} / {scene_name}",
        "opening_tone": opening_tone,
        "likely_evasions": _dedupe(likely_evasions)[:4],
        "pressure_breakpoints": persona_profile["emotional_triggers"][:3] or ["被持续压迫、被误解、被逼立刻表态。"],
        "comfort_topics": _dedupe(persona_profile.get("calming_points", []) + persona_profile["breakthrough_cues"])[:3] or ["从具体事实和可核实细节切入。"],
        "must_feel_human": [
            "不要每一轮都给完整答案，可以先说一半，再因为追问或情绪变化补充。",
            "不要无缘无故突然坦白，必须和信任、压力、弱点或证据触发相对应。",
            "允许说错顺序、口头修正、停顿和抱怨，让表达更像真人。",
        ],
    }


def build_recent_memory(history: list[Any]) -> dict[str, list[str]]:
    user_focuses = []
    ai_reactions = []
    thought_fragments = []
    for message in history[-6:]:
        role = _clean_text(getattr(message, "role", ""))
        content = _clean_text(getattr(message, "content", ""))
        thought = _clean_text(getattr(message, "inner_thought", ""))
        if not content:
            continue
        short = content[:50]
        if role == "user":
            user_focuses.append(short)
        elif role in {"assistant", "ai"}:
            ai_reactions.append(short)
            if thought:
                thought_fragments.append(thought[:60])
    return {
        "user_focuses": user_focuses[-3:],
        "ai_reactions": ai_reactions[-3:],
        "thought_fragments": thought_fragments[-3:],
    }


def summarize_session_memory(history: list[Any], revealed_info: list[str], current_stage_goal: str) -> dict[str, Any]:
    user_topics = []
    repeated_points = []
    role_posture = []

    for message in history[-8:]:
        role = _clean_text(getattr(message, "role", ""))
        content = _clean_text(getattr(message, "content", ""))
        thought = _clean_text(getattr(message, "inner_thought", ""))
        if not content:
            continue
        if role == "user":
            user_topics.append(content[:70])
        elif role in {"assistant", "ai"}:
            role_posture.append(content[:70])
            if thought:
                repeated_points.append(thought[:70])

    summary_lines = []
    if user_topics:
        summary_lines.append(f"最近民警主要在追问：{'；'.join(user_topics[-3:])}")
    if role_posture:
        summary_lines.append(f"角色最近表现为：{'；'.join(role_posture[-2:])}")
    if repeated_points:
        summary_lines.append(f"角色内心持续顾虑：{'；'.join(repeated_points[-2:])}")
    if revealed_info:
        summary_lines.append(f"已经被问出来的关键点：{'；'.join(revealed_info[-3:])}")
    if current_stage_goal:
        summary_lines.append(f"当前仍应围绕的目标：{current_stage_goal}")

    return {
        "summary_text": " | ".join(summary_lines) if summary_lines else "当前对话轮次较少，人物关系和心理路径仍在展开。",
        "user_topics": user_topics[-4:],
        "role_posture": role_posture[-3:],
        "persistent_concerns": repeated_points[-3:],
    }


def evaluate_truth_stage(
    persona_profile: dict[str, Any],
    momentum: dict[str, Any],
    current_trust: int,
    current_emotion: int,
    revealed_info: list[str],
) -> dict[str, Any]:
    hidden_count = int(persona_profile.get("hidden_truths_count", 0) or 0)
    defensive_count = len(persona_profile.get("defensive_instincts", []) or [])

    stage = "guarded_denial"
    guidance = "当前更可能回避、淡化、切割责任，或者只给外围信息。"

    if current_trust >= 65 or momentum.get("rapport") == "warming":
        stage = "partial_release"
        guidance = "当前更可能开始补充可验证细节，但仍会回避最伤自己的核心点。"
    if current_trust >= 78 and current_emotion <= 75:
        stage = "meaningful_disclosure"
        guidance = "当前已接近能说出关键细节的阶段，但通常仍需要一个合适切口或台阶。"
    if current_emotion >= 80 and current_trust < 50:
        stage = "emotional_leak"
        guidance = "虽然未必愿意坦白，但在激动状态下可能口误或抱怨式泄露部分真实信息。"
    if hidden_count == 0 and defensive_count <= 1:
        stage = "mostly_open"
        guidance = "这个角色隐瞒负担较轻，更像是表达不完整，而不是刻意藏事。"

    reveal_pressure = min(100, len(revealed_info) * 8 + current_trust // 2 + (10 if momentum.get("comfort_hits") else 0))
    return {
        "stage": stage,
        "guidance": guidance,
        "reveal_pressure": reveal_pressure,
        "should_hold_core_truth": hidden_count > 0 and stage not in {"meaningful_disclosure", "mostly_open"},
    }


def analyze_dialogue_momentum(
    user_message: str,
    persona_profile: dict[str, Any],
    current_stage_goal: str,
    current_trust: int,
    current_emotion: int,
) -> dict[str, Any]:
    text = _clean_text(user_message)
    strategy_tags = []
    trust_delta = 0
    emotion_delta = 0
    notes = []

    if re.search(r"(别急|慢慢说|不用着急|辛苦|先别慌)", text):
        strategy_tags.append("soft_contact")
        trust_delta += 4
        notes.append("语气相对平和，角色更容易维持交流。")

    if re.search(r"(快说|老实交代|别废话|是不是你干的|再不说)", text):
        strategy_tags.append("pressure")
        trust_delta -= 5
        emotion_delta += 7
        notes.append("强压式表达更容易激发角色防御或对抗。")

    if re.search(r"(时间|几点|地点|哪里|谁先|经过|当时|现场|看见|听见)", text):
        strategy_tags.append("fact_probe")
        trust_delta += 1
        notes.append("提问较具体，更容易得到可验证细节。")

    if re.search(r"(家里|孩子|家人|老人|赔偿|损失|吃亏|后果)", text):
        strategy_tags.append("soft_spot_probe")
        notes.append("触碰到了角色在意的现实后果或家庭关系。")
        if any(token in " ".join(persona_profile.get("soft_spots", [])) for token in ["家", "孩", "赔偿", "损失", "吃亏"]):
            trust_delta += 2
            emotion_delta += 3

    if current_stage_goal and not any(keyword in text for keyword in ["时间", "地点", "现场", "经过", "关系", "证据", "风险", "谁"]):
        strategy_tags.append("off_goal")
        notes.append("这一轮追问和当前训练目标的贴合度一般。")

    if len(text) <= 8:
        strategy_tags.append("too_short")
        trust_delta -= 1
        notes.append("问题过短，角色更容易用模糊回答带过。")

    trigger_hits = [item for item in persona_profile.get("emotional_triggers", []) if any(token in text for token in re.findall(r"[\u4e00-\u9fff]{2,8}", item))]
    comfort_hits = [item for item in persona_profile.get("breakthrough_cues", []) if any(token in text for token in re.findall(r"[\u4e00-\u9fff]{2,8}", item))]
    pressure_point_hits = [item for item in persona_profile.get("pressure_points", []) if any(token in text for token in re.findall(r"[\u4e00-\u9fff]{2,8}", item))]

    if trigger_hits:
        emotion_delta += 6
        notes.append("命中了角色情绪触发点。")
    if comfort_hits:
        trust_delta += 3
        notes.append("命中了更容易打开角色的话题入口。")
    if pressure_point_hits:
        emotion_delta += 4
        notes.append("命中了角色关系网或现实压力点。")

    rapport = "neutral"
    if trust_delta >= 4:
        rapport = "warming"
    elif trust_delta <= -3:
        rapport = "defensive"

    pressure = "medium"
    if emotion_delta >= 8:
        pressure = "high"
    elif emotion_delta <= 1:
        pressure = "low"

    return {
        "strategy_tags": strategy_tags,
        "trust_delta": trust_delta,
        "emotion_delta": emotion_delta,
        "rapport": rapport,
        "pressure": pressure,
        "notes": notes or ["互动尚未明显改变角色状态。"],
        "trigger_hits": trigger_hits[:3],
        "comfort_hits": comfort_hits[:3],
        "pressure_point_hits": pressure_point_hits[:3],
        "trust_band": "high" if current_trust >= 70 else "mid" if current_trust >= 40 else "low",
        "emotion_band": "high" if current_emotion >= 70 else "mid" if current_emotion >= 40 else "low",
    }


def blend_state_updates(
    current_emotion: int,
    current_trust: int,
    llm_emotion: Any,
    llm_trust: Any,
    momentum: dict[str, Any],
) -> dict[str, int]:
    try:
        next_emotion = int(llm_emotion)
    except Exception:
        next_emotion = current_emotion
    try:
        next_trust = int(llm_trust)
    except Exception:
        next_trust = current_trust

    next_emotion = max(0, min(100, next_emotion + int(momentum.get("emotion_delta", 0))))
    next_trust = max(0, min(100, next_trust + int(momentum.get("trust_delta", 0))))
    return {"emotion": next_emotion, "trust": next_trust}


def build_personalized_questions(
    persona_profile: dict[str, Any],
    current_stage: str,
    current_stage_goal: str,
    revealed_info: list[str],
    momentum: dict[str, Any],
    *,
    case_type: str = "",
    scene_name: str = "",
    role_name: str = "",
    role_type: str = "",
    target_role_name: str = "",
    scene_roles: list[dict[str, Any]] | None = None,
    missing_requirements: list[str] | None = None,
    truth_stage: str = "",
    emotion: int = 50,
    cooperation: int = 50,
    last_user_message: str = "",
    recent_messages: list[dict[str, Any]] | None = None,
    custom_prompts: list[str] | None = None,
    case_title: str = "",
    use_llm: bool = True,
) -> list[str]:
    from .recommended_questions_service import build_recommended_questions

    return build_recommended_questions(
        current_stage=current_stage,
        current_stage_goal=current_stage_goal,
        case_type=case_type,
        case_title=case_title,
        scene_name=scene_name,
        role_name=role_name,
        role_type=role_type,
        target_role_name=target_role_name,
        scene_roles=scene_roles,
        revealed_info=revealed_info,
        missing_requirements=missing_requirements,
        truth_stage=truth_stage,
        emotion=emotion,
        cooperation=cooperation,
        persona_profile=persona_profile,
        momentum=momentum,
        last_user_message=last_user_message,
        recent_messages=recent_messages,
        custom_prompts=custom_prompts,
        use_llm=use_llm,
    )


def format_persona_block(persona_profile: dict[str, Any], role_script: dict[str, Any], memory: dict[str, list[str]], momentum: dict[str, Any]) -> str:
    relation_map = persona_profile.get("relationship_map", {})
    scene_boundary = persona_profile.get("scene_boundary") or {}
    boundary_preview = []
    for key, value in scene_boundary.items():
        if not isinstance(value, list) or not value:
            continue
        boundary_preview.append(f"{key}={'、'.join(value[:2])}")
    sections = [
        f"行为原型：{persona_profile.get('behavior_archetype') or '暂无'}",
        f"场景行为模式：{persona_profile.get('scene_behavior_mode') or '核查取证型'}",
        f"角色核心动机：{'; '.join(persona_profile.get('core_motives', []) or ['暂无'])}",
        f"角色互动风格：{persona_profile.get('interaction_style') or '暂无'}",
        f"对警方基本态度：{persona_profile.get('police_attitude') or '暂无'}",
        f"四轴状态：情绪={persona_profile.get('emotion_level') or '中'} / 配合={persona_profile.get('cooperation_level') or '中'} / 失控风险={persona_profile.get('risk_level') or '中'} / 表达清晰度={persona_profile.get('clarity_level') or '中'}",
        f"角色软肋/在意点：{'; '.join(persona_profile.get('soft_spots', []) or ['暂无'])}",
        f"角色防御本能：{'; '.join(persona_profile.get('defensive_instincts', []) or ['暂无'])}",
        f"角色情绪触发点：{'; '.join(persona_profile.get('emotional_triggers', []) or ['暂无'])}",
        f"可安抚点：{'; '.join(persona_profile.get('calming_points', []) or ['暂无'])}",
        f"角色口头习惯：{'; '.join(persona_profile.get('verbal_habits', []) or ['暂无'])}",
        f"角色突破线索：{'; '.join(persona_profile.get('breakthrough_cues', []) or ['暂无'])}",
        f"角色可能偏差：{'; '.join(persona_profile.get('likely_biases', []) or ['暂无'])}",
        f"披露阶梯：{'; '.join(persona_profile.get('disclosure_ladder', []) or ['暂无'])}",
        f"关系网直连对象：{'; '.join(relation_map.get('direct_links', []) or ['暂无'])}",
        f"重点保护对象：{'; '.join(relation_map.get('protected_targets', []) or ['暂无'])}",
        f"紧张/冲突对象：{'; '.join(relation_map.get('tension_targets', []) or ['暂无'])}",
        f"人物内在矛盾：{'; '.join(persona_profile.get('contradictions', []) or ['暂无'])}",
        f"现实压力点：{'; '.join(persona_profile.get('pressure_points', []) or ['暂无'])}",
        f"当前诉求：{persona_profile.get('current_goal') or persona_profile.get('current_need') or '暂无'}",
        f"核心顾虑：{persona_profile.get('core_concern') or '暂无'}",
        f"关系压力：{'; '.join(persona_profile.get('relationship_pressure', []) or ['暂无'])}",
        f"对外口径：{persona_profile.get('surface_stance') or persona_profile.get('public_mask') or '暂无'}",
        f"受压反应：{persona_profile.get('pressure_response') or persona_profile.get('stress_response') or '暂无'}",
        f"触发点：{'; '.join(persona_profile.get('trigger_points', []) or ['暂无'])}",
        f"本场景动态边界：{'; '.join(boundary_preview[:4]) or '暂无'}",
        f"自我定位：{persona_profile.get('self_image') or '暂无'}",
        f"当前最想保住/达成：{persona_profile.get('current_need') or '暂无'}",
        f"对权威/警方态度：{persona_profile.get('authority_attitude') or '暂无'}",
        f"受压后的反应：{persona_profile.get('stress_response') or '暂无'}",
        f"表面口径：{persona_profile.get('public_mask') or '暂无'}",
        f"内心盘算：{persona_profile.get('private_drive') or '暂无'}",
        f"本场景开场状态：{role_script.get('opening_tone', '暂无')}",
        f"可能回避方式：{'; '.join(role_script.get('likely_evasions', []) or ['暂无'])}",
        f"最近民警关注点：{'; '.join(memory.get('user_focuses', []) or ['暂无'])}",
        f"最近角色回应表现：{'; '.join(memory.get('ai_reactions', []) or ['暂无'])}",
        f"当前互动动量：rapport={momentum.get('rapport')} / pressure={momentum.get('pressure')} / notes={'; '.join(momentum.get('notes', [])[:2])}",
    ]
    return "\n".join(f"- {item}" for item in sections)


def format_memory_block(session_memory: dict[str, Any], truth_stage: dict[str, Any]) -> str:
    sections = [
        f"会话记忆摘要：{session_memory.get('summary_text', '暂无')}",
        f"真实信息披露阶段：{truth_stage.get('stage', 'guarded_denial')}",
        f"当前披露指导：{truth_stage.get('guidance', '暂无')}",
        f"披露压力值：{truth_stage.get('reveal_pressure', 0)}/100",
        f"是否仍应守住核心隐瞒点：{'是' if truth_stage.get('should_hold_core_truth') else '否'}",
    ]
    return "\n".join(f"- {item}" for item in sections)
