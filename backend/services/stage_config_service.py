from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


DEFAULT_STAGE_GOAL = "围绕本场景关键事实展开问询和处置。"


def _slugify(value: str, prefix: str, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text)
    text = text.strip("_")
    if not text:
        text = fallback
    return f"{prefix}_{text}"


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen = set()
    result: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


CASE_TYPE_ALIASES = {
    "酒驾": "酒驾醉驾",
    "醉驾": "酒驾醉驾",
    "交通事故": "交通事故",
    "邻里纠纷": "邻里/家庭纠纷",
    "家庭纠纷": "邻里/家庭纠纷",
    "情感纠纷": "邻里/家庭纠纷",
    "劳资纠纷": "邻里/家庭纠纷",
    "消费纠纷": "邻里/家庭纠纷",
}

SCENE_BEHAVIOR_MODES = ("核查取证型", "调解型", "危机干预型", "管控型")

SCENE_MODE_CASE_TYPE_MAP = {
    "邻里纠纷": "调解型",
    "家庭纠纷": "调解型",
    "情感纠纷": "调解型",
    "劳资纠纷": "调解型",
    "消费纠纷": "调解型",
    "噪音扰民": "调解型",
    "校园警情": "调解型",
    "宠物纠纷": "调解型",
    "自杀干预": "危机干预型",
    "醉酒闹事": "管控型",
    "酒驾醉驾": "管控型",
}

SCENE_MODE_KEYWORDS = {
    "危机干预型": ["轻生", "跳楼", "危机", "劝阻", "干预", "天台", "楼顶", "绝望", "安抚救助"],
    "管控型": ["管控", "稳控", "控制", "约束", "带离", "警戒", "隔离", "醉酒", "失控", "防止升级", "疏散围观"],
    "调解型": ["调解", "纠纷", "协商", "劝和", "分开双方", "矛盾化解", "稳定双方"],
    "核查取证型": ["取证", "调查", "核查", "笔录", "讯问", "询问", "压实", "时间线", "证据", "现场勘查", "信息初核"],
}


def normalize_case_template_key(case_type: str) -> str:
    raw = str(case_type or "").strip()
    if not raw:
        return "通用"
    return CASE_TYPE_ALIASES.get(raw, raw if raw in {"酒驾醉驾", "交通事故", "邻里/家庭纠纷"} else "通用")


def infer_scene_kind(scene_name: str, stage_name: str) -> str:
    scene_text = f"{scene_name or ''} {stage_name or ''}"
    if any(token in scene_text for token in ["接警", "信息初核", "接处警", "报警"]):
        return "intake"
    if any(token in scene_text for token in ["现场", "初查", "勘查", "核查", "控制", "摸排"]):
        return "onsite"
    if any(token in scene_text for token in ["询问", "压实", "矛盾", "审讯", "讯问", "笔录", "核录"]):
        return "investigation"
    return "generic"


def infer_scene_behavior_mode(scene_name: str, case_type: str = "", stages: Any | None = None) -> str:
    scene_text_parts = [str(scene_name or "").strip(), str(case_type or "").strip()]
    for stage in stages or []:
        if not isinstance(stage, dict):
            continue
        scene_text_parts.append(str(stage.get("stage_name") or "").strip())
        scene_text_parts.append(str(stage.get("stage_goal") or "").strip())
    scene_text = " ".join(part for part in scene_text_parts if part)

    for mode, keywords in SCENE_MODE_KEYWORDS.items():
        if any(keyword and keyword in scene_text for keyword in keywords):
            return mode

    mapped = SCENE_MODE_CASE_TYPE_MAP.get(str(case_type or "").strip())
    if mapped in SCENE_BEHAVIOR_MODES:
        return mapped

    if any(token in scene_text for token in ["现场", "初查", "勘查", "取证", "调查", "询问", "压实", "笔录"]):
        return "核查取证型"
    return "核查取证型"


def _point(
    point_id: str,
    label: str,
    *,
    category: str = "procedure",
    required: bool = True,
    weight: int = 10,
    keywords: list[str] | None = None,
    knowledge_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": point_id,
        "label": label,
        "category": category,
        "required": required,
        "weight": weight,
        "keywords": _dedupe_strings(keywords or []),
        "knowledge_refs": _dedupe_strings(knowledge_refs or []),
    }


def _action(
    action_id: str,
    label: str,
    *,
    action_type: str = "physical",
    aliases: list[str] | None = None,
    counts_for: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "type": action_type,
        "aliases": _dedupe_strings([label, *(aliases or [])]),
        "counts_for": _dedupe_strings(counts_for or []),
    }


def _build_stage_template(case_type: str, scene_name: str, stage_name: str, stage_goal: str) -> dict[str, Any]:
    case_key = normalize_case_template_key(case_type)
    scene_kind = infer_scene_kind(scene_name, stage_name)
    goal_text = str(stage_goal or "")

    if case_key == "酒驾醉驾":
        if scene_kind == "intake":
            points = [
                _point("ap_jj_location", "确认事发地点与车辆位置", keywords=["哪里", "具体位置", "地点", "车停在哪"]),
                _point("ap_jj_identity", "确认报警人/驾驶人身份关系", keywords=["身份", "姓名", "驾驶员", "谁在开车"]),
                _point("ap_jj_risk", "确认是否存在继续驾驶或现场风险", category="risk", keywords=["危险", "还在开车", "是否安全", "风险"]),
            ]
            actions = [
                _action("act_open_recorder", "开启执法记录仪", aliases=["打开记录仪", "开启记录仪"], counts_for=[]),
            ]
            required_point_ids = [item["id"] for item in points[:2]]
            return {
                "assessment_points": points,
                "action_catalog": actions,
                "completion_rules": {
                    "min_user_turns": 2,
                    "required_point_ids": required_point_ids,
                    "required_action_ids": [],
                },
                "end_conditions": {
                    "must_complete_current_stage": False,
                    "required_point_ids": [],
                    "required_action_ids": [],
                    "closure_actions": [],
                    "closing_script": "",
                },
            }

        if scene_kind == "onsite":
            points = [
                _point("ap_identity_notice", "规范出示证件并表明身份", keywords=["出示证件", "表明身份", "执法证", "我是公安民警"]),
                _point("ap_reason_notice", "告知检查事由与依据", keywords=["依法检查", "酒驾检查", "根据道路交通安全法", "检查事由"]),
                _point("ap_breath_test", "要求配合酒精呼气检测", keywords=["呼气检测", "酒精检测", "吹气", "酒精测试"]),
                _point("ap_evidence_fix", "提示固定现场证据", category="evidence", keywords=["拍照", "录像", "固定证据", "制作笔录"]),
            ]
            actions = [
                _action("act_open_recorder", "开启执法记录仪", aliases=["打开执法记录仪", "开启记录仪"], counts_for=["ap_identity_notice"]),
                _action("act_breath_test", "实施呼气酒精检测", aliases=["呼气检测", "酒精呼气检测", "吹气检测"], counts_for=["ap_breath_test"]),
                _action("act_photo_evidence", "固定现场证据", aliases=["拍照取证", "现场录像", "固定证据"], counts_for=["ap_evidence_fix"]),
                _action("act_control_vehicle", "控制车辆并防止继续驾驶", aliases=["扣留车辆", "禁止继续驾驶", "控制车辆"], counts_for=[]),
            ]
            required_point_ids = ["ap_identity_notice", "ap_reason_notice", "ap_breath_test"]
            required_action_ids = ["act_open_recorder", "act_breath_test"]
            return {
                "assessment_points": points,
                "action_catalog": actions,
                "completion_rules": {
                    "min_user_turns": 3,
                    "required_point_ids": required_point_ids,
                    "required_action_ids": ["act_open_recorder"],
                },
                "end_conditions": {
                    "must_complete_current_stage": True,
                    "required_point_ids": required_point_ids,
                    "required_action_ids": required_action_ids,
                    "closure_actions": ["带离", "笔录", "抽血", "移交"],
                    "closing_script": "本次现场酒驾处置已完成，现转入带离与后续笔录程序，本轮训练结束。",
                },
            }

        points = [
            _point("ap_timeline", "核实饮酒与驾驶时间线", keywords=["几点喝酒", "几点开车", "从哪里来", "去哪里"]),
            _point("ap_refusal_notice", "拒测时依法告知法律后果", keywords=["拒绝检测", "法律后果", "依法处理", "强制措施"]),
            _point("ap_follow_up", "明确后续带离、笔录或移交流程", keywords=["带回", "笔录", "后续处理", "移交"]),
        ]
        actions = [
            _action("act_escort_station", "带离至公安机关", aliases=["带回所里", "带回公安局", "带离"], counts_for=["ap_follow_up"]),
            _action("act_make_record", "制作笔录", aliases=["做笔录", "询问笔录", "制作笔录"], counts_for=["ap_follow_up"]),
        ]
        return {
            "assessment_points": points,
            "action_catalog": actions,
            "completion_rules": {
                "min_user_turns": 3,
                "required_point_ids": ["ap_timeline"],
                "required_action_ids": [],
            },
            "end_conditions": {
                "must_complete_current_stage": True,
                "required_point_ids": ["ap_timeline", "ap_follow_up"],
                "required_action_ids": ["act_make_record"],
                "closure_actions": ["笔录", "带离", "移交"],
                "closing_script": "关键情况已核实，后续带离和笔录程序已明确，本轮训练结束。",
            },
        }

    if case_key == "交通事故":
        if scene_kind == "intake":
            points = [
                _point("ap_accident_location", "确认事故地点", keywords=["事故地点", "在哪", "具体位置"]),
                _point("ap_accident_casualty", "确认伤情与救助需求", category="risk", keywords=["受伤", "120", "是否需要救护", "伤情"]),
                _point("ap_accident_vehicle", "确认涉事车辆和人员", keywords=["什么车", "车牌", "几辆车", "驾驶员"]),
            ]
            return {
                "assessment_points": points,
                "action_catalog": [],
                "completion_rules": {"min_user_turns": 2, "required_point_ids": [item["id"] for item in points[:2]], "required_action_ids": []},
                "end_conditions": {"must_complete_current_stage": False, "required_point_ids": [], "required_action_ids": [], "closure_actions": [], "closing_script": ""},
            }

        if scene_kind == "onsite":
            points = [
                _point("ap_scene_protect", "强调保护现场并设置警戒", keywords=["保护现场", "设置警戒", "不要移动车辆", "保持原状"]),
                _point("ap_identity_vehicle", "核实驾驶员和车辆信息", keywords=["驾驶证", "行驶证", "车牌", "身份"]),
                _point("ap_evidence_collect", "固定照片、视频和目击证据", category="evidence", keywords=["拍照", "录像", "监控", "证人"]),
            ]
            actions = [
                _action("act_set_warning", "设置警示与现场警戒", aliases=["设置警戒", "摆放警示标志"], counts_for=["ap_scene_protect"]),
                _action("act_photo_evidence", "拍照录像固定现场", aliases=["拍照取证", "现场录像"], counts_for=["ap_evidence_collect"]),
            ]
            return {
                "assessment_points": points,
                "action_catalog": actions,
                "completion_rules": {"min_user_turns": 3, "required_point_ids": ["ap_scene_protect", "ap_identity_vehicle"], "required_action_ids": []},
                "end_conditions": {
                    "must_complete_current_stage": True,
                    "required_point_ids": ["ap_scene_protect", "ap_identity_vehicle"],
                    "required_action_ids": ["act_photo_evidence"],
                    "closure_actions": ["事故认定", "移车", "笔录"],
                    "closing_script": "现场关键处置已完成，接下来进入后续笔录和事故认定程序，本轮训练结束。",
                },
            }

    if case_key == "邻里/家庭纠纷":
        if scene_kind == "onsite":
            points = [
                _point("ap_separate_parties", "先行分离双方并稳定情绪", category="risk", keywords=["分开", "冷静", "先别激动", "分别说明"]),
                _point("ap_identity_relation", "核实双方身份和关系", keywords=["姓名", "关系", "住址", "身份"]),
                _point("ap_process_risk", "问清经过、伤情和现实风险", keywords=["怎么回事", "经过", "受伤", "还有危险"]),
            ]
            actions = [
                _action("act_separate_parties", "分离双方当事人", aliases=["分开双方", "分别控制"], counts_for=["ap_separate_parties"]),
                _action("act_open_recorder", "开启执法记录仪", aliases=["打开记录仪"], counts_for=[]),
            ]
            return {
                "assessment_points": points,
                "action_catalog": actions,
                "completion_rules": {"min_user_turns": 3, "required_point_ids": ["ap_identity_relation", "ap_process_risk"], "required_action_ids": []},
                "end_conditions": {
                    "must_complete_current_stage": True,
                    "required_point_ids": ["ap_separate_parties", "ap_process_risk"],
                    "required_action_ids": ["act_separate_parties"],
                    "closure_actions": ["调解", "带离", "笔录"],
                    "closing_script": "现场纠纷处置已告一段落，后续将根据情况进入调解或笔录程序，本轮训练结束。",
                },
            }

        if scene_kind == "investigation":
            points = [
                _point("ap_conflict_reason", "追问矛盾起因和升级节点", keywords=["为什么", "起因", "先后", "谁先"]),
                _point("ap_contradiction_fix", "核实前后陈述矛盾", keywords=["前后不一致", "改口", "矛盾", "再确认"]),
                _point("ap_disposal_next", "明确调解、警告或后续处置路径", keywords=["怎么处理", "调解", "后续", "笔录"]),
            ]
            return {
                "assessment_points": points,
                "action_catalog": [
                    _action("act_make_record", "制作询问笔录", aliases=["做笔录", "询问笔录"], counts_for=["ap_disposal_next"]),
                ],
                "completion_rules": {"min_user_turns": 3, "required_point_ids": ["ap_conflict_reason"], "required_action_ids": []},
                "end_conditions": {
                    "must_complete_current_stage": True,
                    "required_point_ids": ["ap_conflict_reason", "ap_disposal_next"],
                    "required_action_ids": [],
                    "closure_actions": ["调解", "笔录", "传唤", "带离"],
                    "closing_script": "本轮纠纷处置问询已完成，后续依法进入调解或笔录环节，本轮训练结束。",
                },
            }

    if scene_kind == "intake":
        points = [
            _point("ap_identity", "确认身份或报警人关系", keywords=["姓名", "身份", "关系"]),
            _point("ap_location", "确认地点", keywords=["地点", "位置", "哪里"]),
            _point("ap_time_risk", "确认时间和现场风险", category="risk", keywords=["几点", "时间", "危险", "受伤"]),
        ]
        return {
            "assessment_points": points,
            "action_catalog": [],
            "completion_rules": {"min_user_turns": 2, "required_point_ids": ["ap_identity", "ap_location"], "required_action_ids": []},
            "end_conditions": {"must_complete_current_stage": False, "required_point_ids": [], "required_action_ids": [], "closure_actions": [], "closing_script": ""},
        }

    if scene_kind == "onsite":
        points = [
            _point("ap_onsite_identity", "核实在场人员身份", keywords=["姓名", "身份", "你是谁"]),
            _point("ap_onsite_process", "问清现场经过", keywords=["经过", "怎么回事", "发生了什么"]),
            _point("ap_onsite_risk", "识别伤情、风险和证据", category="risk", keywords=["受伤", "危险", "证据", "监控"]),
        ]
        actions = [
            _action("act_open_recorder", "开启执法记录仪", aliases=["打开记录仪"], counts_for=[]),
            _action("act_photo_evidence", "固定现场证据", aliases=["拍照", "录像", "固定证据"], counts_for=["ap_onsite_risk"]),
        ]
        return {
            "assessment_points": points,
            "action_catalog": actions,
            "completion_rules": {"min_user_turns": 3, "required_point_ids": ["ap_onsite_identity", "ap_onsite_process"], "required_action_ids": []},
            "end_conditions": {
                "must_complete_current_stage": True,
                "required_point_ids": ["ap_onsite_identity", "ap_onsite_process"],
                "required_action_ids": [],
                "closure_actions": ["笔录", "带离", "移交", "调解"],
                "closing_script": "现场主要处置已完成，后续进入进一步核查与笔录程序，本轮训练结束。",
            },
        }

    points = [
        _point("ap_timeline_generic", "核实时间线", keywords=["时间", "几点", "先后"]),
        _point("ap_process_generic", "追问经过与矛盾点", keywords=["经过", "具体", "为什么", "矛盾"]),
        _point("ap_next_step_generic", "明确后续处置方向", keywords=["后续", "怎么处理", "下一步"]),
    ]
    return {
        "assessment_points": points,
        "action_catalog": [
            _action("act_make_record", "制作笔录", aliases=["做笔录", "询问笔录"], counts_for=["ap_next_step_generic"]),
        ],
        "completion_rules": {"min_user_turns": 3, "required_point_ids": ["ap_timeline_generic"], "required_action_ids": []},
        "end_conditions": {
            "must_complete_current_stage": True,
            "required_point_ids": ["ap_timeline_generic", "ap_next_step_generic"],
            "required_action_ids": [],
            "closure_actions": ["笔录", "带离", "移交", "调解"],
            "closing_script": "关键事实核实已完成，训练进入收尾，本轮训练结束。",
        },
    }


def _normalize_assessment_point(point: dict[str, Any], stage_key: str, index: int) -> dict[str, Any]:
    label = str(point.get("label") or f"考察点{index}").strip()
    point_id = str(point.get("id") or _slugify(label, "ap", f"{stage_key}_{index}")).strip()
    keywords = _dedupe_strings(point.get("keywords") or [label])
    if not keywords:
        keywords = [label]
    return {
        "id": point_id,
        "label": label,
        "category": str(point.get("category") or "procedure").strip() or "procedure",
        "required": bool(point.get("required", True)),
        "weight": max(1, int(point.get("weight", 10) or 10)),
        "keywords": keywords,
        "knowledge_refs": _dedupe_strings(point.get("knowledge_refs") or []),
    }


def _normalize_action(action: dict[str, Any], stage_key: str, index: int) -> dict[str, Any]:
    label = str(action.get("label") or f"动作{index}").strip()
    action_id = str(action.get("id") or _slugify(label, "act", f"{stage_key}_{index}")).strip()
    aliases = _dedupe_strings([label, *(action.get("aliases") or [])])
    if not aliases:
        aliases = [label]
    return {
        "id": action_id,
        "label": label,
        "type": str(action.get("type") or "physical").strip() or "physical",
        "aliases": aliases,
        "counts_for": _dedupe_strings(action.get("counts_for") or []),
    }


def normalize_stage(stage: dict[str, Any] | None, index: int, case_type: str = "", scene_name: str = "") -> dict[str, Any]:
    stage = deepcopy(stage or {})
    stage_name = str(stage.get("stage_name") or stage.get("name") or f"处置步骤{index}").strip()
    stage_goal = str(stage.get("stage_goal") or stage.get("goal") or stage.get("description") or DEFAULT_STAGE_GOAL).strip()
    template = _build_stage_template(case_type, scene_name, stage_name, stage_goal)

    merged_points = stage.get("assessment_points")
    if not isinstance(merged_points, list) or not merged_points:
        merged_points = template.get("assessment_points", [])
    merged_actions = stage.get("action_catalog")
    if not isinstance(merged_actions, list):
        merged_actions = template.get("action_catalog", [])

    stage_key = _slugify(f"{scene_name}_{stage_name}", "stage", f"{index}")
    normalized_points = [
        _normalize_assessment_point(point, stage_key, point_index)
        for point_index, point in enumerate(merged_points or [], start=1)
        if isinstance(point, dict)
    ]
    normalized_actions = [
        _normalize_action(action, stage_key, action_index)
        for action_index, action in enumerate(merged_actions or [], start=1)
        if isinstance(action, dict)
    ]

    point_ids = [item["id"] for item in normalized_points]
    action_ids = [item["id"] for item in normalized_actions]
    completion_rules = stage.get("completion_rules") if isinstance(stage.get("completion_rules"), dict) else template.get("completion_rules", {})
    end_conditions = stage.get("end_conditions") if isinstance(stage.get("end_conditions"), dict) else template.get("end_conditions", {})

    raw_prompts = stage.get("recommended_prompts")
    recommended_prompts = _dedupe_strings(raw_prompts) if isinstance(raw_prompts, list) else []

    return {
        "stage_name": stage_name,
        "stage_goal": stage_goal,
        "recommended_prompts": recommended_prompts,
        "assessment_points": normalized_points,
        "action_catalog": normalized_actions,
        "completion_rules": {
            "min_user_turns": max(1, int(completion_rules.get("min_user_turns", 3) or 3)),
            "required_point_ids": [item for item in _dedupe_strings(completion_rules.get("required_point_ids") or point_ids[: min(len(point_ids), 2)]) if item in point_ids],
            "required_action_ids": [item for item in _dedupe_strings(completion_rules.get("required_action_ids") or []) if item in action_ids],
        },
        "end_conditions": {
            "must_complete_current_stage": bool(end_conditions.get("must_complete_current_stage", True)),
            "required_point_ids": [item for item in _dedupe_strings(end_conditions.get("required_point_ids") or []) if item in point_ids],
            "required_action_ids": [item for item in _dedupe_strings(end_conditions.get("required_action_ids") or []) if item in action_ids],
            "closure_actions": _dedupe_strings(end_conditions.get("closure_actions") or []),
            "closing_script": str(end_conditions.get("closing_script") or "").strip(),
        },
    }


def normalize_stages(stages: Any, case_type: str = "", scene_name: str = "") -> list[dict[str, Any]]:
    raw_stages = _safe_list(stages)
    normalized = [
        normalize_stage(stage, index, case_type=case_type, scene_name=scene_name)
        for index, stage in enumerate(raw_stages, start=1)
        if isinstance(stage, dict)
    ]
    if normalized:
        return normalized
    return [
        normalize_stage(
            {"stage_name": "初始处置", "stage_goal": DEFAULT_STAGE_GOAL},
            1,
            case_type=case_type,
            scene_name=scene_name,
        ),
        normalize_stage(
            {"stage_name": "关键压实", "stage_goal": "核实陈述细节、风险点和矛盾点。"},
            2,
            case_type=case_type,
            scene_name=scene_name,
        ),
    ]


def dumps_stages(stages: Any, case_type: str = "", scene_name: str = "") -> str:
    return json.dumps(normalize_stages(stages, case_type=case_type, scene_name=scene_name), ensure_ascii=False)


def find_stage_config(stages: Any, current_stage: str, case_type: str = "", scene_name: str = "") -> dict[str, Any] | None:
    normalized = normalize_stages(stages, case_type=case_type, scene_name=scene_name)
    current_stage = str(current_stage or "").strip()
    for stage in normalized:
        if stage.get("stage_name") == current_stage:
            return stage
    return normalized[0] if normalized else None
