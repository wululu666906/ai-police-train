from __future__ import annotations

import base64
import json
import math
from typing import Any, Optional

from .llm_provider import ACTIVE_API_KEY, client, extract_json_payload, extract_message_text, get_chat_model


def _default_assessment_points_for_auto_node(
    index: int,
    *,
    node_type: str,
    required_gesture: Optional[str],
    required_keywords: list[str],
    prop_mode: str,
) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = [
        {
            "id": f"node_{index + 1}_procedure",
            "label": "按节点要求完成处置流程",
            "content": "在触发时点完成本节点训练动作或处置流程。",
            "dimension": "procedure_execution",
            "required": True,
            "rule": {"channel": "result", "mode": "result_pass"},
        },
    ]
    if node_type in {"voice_qa", "action"} or required_keywords:
        points.append(
            {
                "id": f"node_{index + 1}_speech",
                "label": "话术与关键信息表达",
                "content": "说出节点要求的标准话术与关键信息。",
                "dimension": "verbal_communication",
                "required": bool(required_keywords) or node_type == "voice_qa",
                "rule": {"channel": "speech", "mode": "keywords"},
            }
        )
    if required_gesture:
        points.append(
            {
                "id": f"node_{index + 1}_gesture",
                "label": "动作/手势执行规范",
                "content": "按要求做出对应动作或手势，清晰稳定。",
                "dimension": "body_action",
                "required": True,
                "rule": {"channel": "gesture", "mode": "gesture_match"},
            }
        )
    points.append(
        {
            "id": f"node_{index + 1}_identity",
            "label": "身份/活体状态合规",
            "content": "保持单人入镜，活体与在场状态稳定。",
            "dimension": "professional_safety",
            "required": True,
            "rule": {"channel": "identity", "mode": "identity_ready"},
        }
    )
    if prop_mode == "manual":
        points.append(
            {
                "id": f"node_{index + 1}_prop",
                "label": "证件/装备操作规范",
                "content": "按要求完成证件、装备或虚拟道具操作。",
                "dimension": "professional_safety",
                "required": True,
                "rule": {"channel": "prop", "mode": "prop_ready"},
            }
        )
    if node_type in {"judge", "choice"}:
        points.append(
            {
                "id": f"node_{index + 1}_decision",
                "label": "节点判断准确",
                "content": "根据训练要求做出正确判断或选择。",
                "dimension": "professional_safety",
                "required": True,
                "rule": {"channel": "decision", "mode": "decision_correct"},
            }
        )
    return points


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


POLICE_SCORE_RUBRIC = {
    "risk_awareness": 30,
    "procedure": 25,
    "communication": 20,
    "lawfulness": 15,
    "safety": 10,
}

POLICE_NODE_LABELS = {
    "arrival_observation": "到场观察",
    "risk_identification": "风险识别",
    "disposal_decision": "处置决策",
    "standard_communication": "规范话术",
}

POLICE_INCIDENT_LABELS = {
    "family_dispute": "家庭/邻里纠纷",
    "alcohol_trouble": "酒后滋事",
    "school_conflict": "校园冲突",
    "public_help": "群众求助",
    "traffic_scene": "交通现场处置",
    "unstable_person": "突发人员失控",
}

POLICE_INCIDENT_TITLE_HINTS = {
    "family_dispute": "家庭纠纷模拟警情",
    "alcohol_trouble": "酒后滋事模拟警情",
    "school_conflict": "校园警情模拟警情",
    "public_help": "群众求助救助模拟警情",
    "traffic_scene": "交通现场处置模拟警情",
    "unstable_person": "人员失控处置模拟警情",
}

TRAINING_VARIANT_LABELS = {
    "base": "新警基础版",
    "law_standard": "执法规范版",
    "risk_focus": "风险识别强化版",
    "exam": "考核版",
}


def _normalize_police_scenario(value: Optional[str]) -> str:
    value = str(value or "").strip()
    return value if value in POLICE_INCIDENT_LABELS else ""


def _normalize_training_variant(value: Optional[str]) -> str:
    value = str(value or "").strip()
    return value if value in TRAINING_VARIANT_LABELS else "base"


def _normalize_difficulty_level(value: Optional[str]) -> str:
    value = str(value or "").strip()
    return value if value in {"basic", "normal", "advanced"} else "normal"


def _scenario_title_source(title: str, scenario_hint: Optional[str]) -> str:
    scenario = _normalize_police_scenario(scenario_hint)
    if not scenario:
        return title or ""
    return f"{POLICE_INCIDENT_TITLE_HINTS[scenario]} {title or ''}".strip()


def _append_unique(values: list[str], *items: str) -> list[str]:
    result = [str(item).strip() for item in values if str(item).strip()]
    for item in items:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _apply_training_metadata(
    payload: dict[str, Any],
    *,
    scenario_hint: Optional[str] = None,
    training_variant: Optional[str] = None,
    difficulty_level: Optional[str] = None,
) -> dict[str, Any]:
    scenario = _normalize_police_scenario(scenario_hint)
    variant = _normalize_training_variant(training_variant)
    difficulty = _normalize_difficulty_level(difficulty_level)
    scenario_label = POLICE_INCIDENT_LABELS.get(scenario, "")
    variant_label = TRAINING_VARIANT_LABELS.get(variant, TRAINING_VARIANT_LABELS["base"])
    difficulty_label = {"basic": "基础难度", "normal": "标准难度", "advanced": "进阶难度"}[difficulty]

    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    payload["tags"] = _append_unique(
        tags,
        "模拟警情" if scenario else "",
        scenario_label,
        variant_label,
        difficulty_label,
    )
    if scenario_label:
        payload["briefing"] = f"{payload.get('briefing') or ''} 当前训练场景：{scenario_label}；训练版本：{variant_label}；难度：{difficulty_label}。".strip()

    for node in payload.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_config = node.get("node_config") if isinstance(node.get("node_config"), dict) else {}
        prompt_content = node.get("prompt_content") if isinstance(node.get("prompt_content"), dict) else {}
        node_config["police_scenario"] = scenario
        node_config["training_variant"] = variant
        node_config["difficulty_level"] = difficulty
        prompt_content["training_focus"] = variant_label

        if variant == "risk_focus":
            node_config["semantic_pass_threshold"] = max(int(node_config.get("semantic_pass_threshold") or 50), 60)
            rubric = node_config.get("score_rubric") if isinstance(node_config.get("score_rubric"), dict) else dict(POLICE_SCORE_RUBRIC)
            rubric["risk_awareness"] = max(int(rubric.get("risk_awareness") or 0), 40)
            node_config["score_rubric"] = rubric
        elif variant == "law_standard":
            standard_points = node_config.get("standard_points")
            if isinstance(standard_points, list) and "依法告知并全程记录" not in standard_points:
                standard_points.append("依法告知并全程记录")
            law_points = node_config.get("law_points")
            if isinstance(law_points, list) and "全过程记录和规范告知" not in law_points:
                law_points.append("全过程记录和规范告知")
        elif variant == "exam":
            node["timeout_seconds"] = min(int(node.get("timeout_seconds") or 75), 60)
            node["retry_score_deduct"] = max(int(node.get("retry_score_deduct") or 5), 8)
            node["skip_score_deduct"] = max(int(node.get("skip_score_deduct") or 15), 20)

        node["node_config"] = node_config
        node["prompt_content"] = prompt_content

    payload["police_scenario"] = scenario
    payload["training_variant"] = variant
    payload["difficulty_level"] = difficulty
    return payload


def _police_assessment_points(index: int, police_node_type: str, standard_points: list[str]) -> list[dict[str, Any]]:
    dimension_by_type = {
        "arrival_observation": "risk_awareness",
        "risk_identification": "risk_awareness",
        "disposal_decision": "procedure",
        "standard_communication": "communication",
    }
    label = POLICE_NODE_LABELS.get(police_node_type, "警情处置")
    points: list[dict[str, Any]] = []
    for point_index, point in enumerate(standard_points[:6]):
        points.append(
            {
                "id": f"node_{index + 1}_police_{point_index + 1}",
                "label": point,
                "content": point,
                "dimension": dimension_by_type.get(police_node_type, "procedure"),
                "required": point_index < 3,
                "rule": {"channel": "semantic", "mode": "standard_point"},
            }
        )
    points.append(
        {
            "id": f"node_{index + 1}_police_safety",
            "label": f"{label}安全意识",
            "content": "回答应体现依法、安全、克制、先稳控再处置的原则。",
            "dimension": "safety",
            "required": True,
            "rule": {"channel": "semantic", "mode": "safety_principle"},
        }
    )
    return points


def _police_node_spec(
    *,
    title: str,
    police_node_type: str,
    question: str,
    scene_summary: str,
    standard_points: list[str],
    risk_signals: list[str],
    law_points: list[str],
    keywords: list[str],
) -> dict[str, Any]:
    badge = POLICE_NODE_LABELS.get(police_node_type, "警情处置")
    return {
        "title": title,
        "node_type": "voice_qa",
        "police_node_type": police_node_type,
        "instruction": question,
        "scene_summary": scene_summary,
        "police_question": question,
        "answer_mode": "text_or_voice",
        "speech_hint": "回答要覆盖现场风险、处置顺序、规范话术和依法安全要求。",
        "node_badge": badge,
        "standard_points": standard_points,
        "risk_signals": risk_signals,
        "law_points": law_points,
        "required_keywords": keywords,
    }


def _infer_police_incident_profile(title: str) -> dict[str, Any]:
    normalized = (title or "").lower()
    common_arrival = _police_node_spec(
        title="到场观察",
        police_node_type="arrival_observation",
        question="你到达现场后，首先应观察哪些情况？",
        scene_summary="模拟警情开始，民警需要在进入现场前完成环境、人员和风险初判。",
        standard_points=["观察人员数量和情绪状态", "观察危险物品和逃生通道", "确认自身站位和安全距离", "判断是否需要先控场", "同步开启执法记录"],
        risk_signals=["人员聚集", "情绪激动", "现场物品复杂"],
        law_points=["依法表明身份", "规范开启执法记录", "保护现场人员安全"],
        keywords=["观察", "人员", "危险", "站位", "记录"],
    )
    common_communication = _police_node_spec(
        title="规范话术",
        police_node_type="standard_communication",
        question="请说出你对现场当事人的第一句话。",
        scene_summary="现场需要先稳定秩序，避免刺激性语言导致冲突升级。",
        standard_points=["表明民警身份", "要求双方保持冷静", "使用清晰可执行指令", "告知配合调查", "避免威胁或刺激性语言"],
        risk_signals=["语言刺激", "情绪对抗", "围观干扰"],
        law_points=["依法文明规范执法", "履行告知和劝导职责"],
        keywords=["民警", "冷静", "配合", "调查", "安全"],
    )

    if _contains_any(normalized, ["家庭", "纠纷", "夫妻", "邻里", "争吵"]):
        return {
            "briefing": "系统已按家庭/邻里纠纷警情建模。训练重点：到场观察、隔离双方、危险物品控制、情绪稳控、依法调解与证据留存。",
            "tags": ["模拟警情", "家庭纠纷", "AI节点化"],
            "nodes": [
                common_arrival,
                _police_node_spec(
                    title="识别升级风险",
                    police_node_type="risk_identification",
                    question="当前现场有哪些风险点？你如何避免矛盾升级？",
                    scene_summary="双方情绪激动，可能存在推搡、砸物或持物伤害风险。",
                    standard_points=["识别情绪激动和肢体冲突风险", "识别酒瓶、刀具等危险物品", "拉开双方距离并分别询问", "控制围观人员和现场秩序", "必要时请求支援"],
                    risk_signals=["情绪激动", "危险物品", "肢体接近", "围观人员"],
                    law_points=["维护现场秩序", "保护人身安全", "必要时依法采取控制措施"],
                    keywords=["风险", "危险物品", "隔离", "支援", "秩序"],
                ),
                _police_node_spec(
                    title="处置决策",
                    police_node_type="disposal_decision",
                    question="你的下一步处置顺序是什么？是否需要呼叫支援？",
                    scene_summary="现场已出现争执升级迹象，需要先稳控再调查。",
                    standard_points=["先隔离双方并控制危险物品", "安抚情绪并明确禁止继续冲突", "分别询问双方和现场人员", "评估伤情并联系医疗救助", "根据违法事实依法处理"],
                    risk_signals=["冲突升级", "伤情不明", "证据可能灭失"],
                    law_points=["依法调查取证", "依法调解或处理违法行为", "必要时保护现场证据"],
                    keywords=["隔离", "控制", "询问", "救助", "依法"],
                ),
                common_communication,
            ],
        }

    if _contains_any(normalized, ["酒后", "醉酒", "滋事", "闹事", "寻衅"]):
        return {
            "briefing": "系统已按酒后滋事警情建模。训练重点：保持安全距离、识别攻击风险、呼叫支援、规范劝阻、依法控制。",
            "tags": ["模拟警情", "酒后滋事", "AI节点化"],
            "nodes": [
                common_arrival,
                _police_node_spec(
                    title="醉酒攻击风险识别",
                    police_node_type="risk_identification",
                    question="面对醉酒人员，你需要重点识别哪些风险？",
                    scene_summary="醉酒人员言语激动、动作不稳，可能突然冲撞、挥打或摔倒受伤。",
                    standard_points=["保持安全距离和侧向站位", "识别突然攻击和自伤风险", "移除酒瓶等危险物品", "请求同伴支援形成控制", "关注围观群众安全"],
                    risk_signals=["醉酒失控", "突然攻击", "摔倒受伤", "危险物品"],
                    law_points=["依法制止违法行为", "保护醉酒人员和群众安全"],
                    keywords=["安全距离", "攻击", "危险物品", "支援", "群众"],
                ),
                _police_node_spec(
                    title="依法稳控处置",
                    police_node_type="disposal_decision",
                    question="如果对方继续挑衅并靠近，你会如何处置？",
                    scene_summary="当事人持续靠近并挑衅，现场存在升级为肢体冲突的风险。",
                    standard_points=["口头警告并明确行为边界", "保持警戒站位并呼叫支援", "必要时依法采取控制措施", "避免单人近距离拉扯", "记录全过程并固定证据"],
                    risk_signals=["持续靠近", "不听劝阻", "单警处置风险"],
                    law_points=["依法警告", "依法采取必要控制措施", "全过程记录"],
                    keywords=["警告", "支援", "控制", "依法", "记录"],
                ),
                common_communication,
            ],
        }

    if _contains_any(normalized, ["校园", "学生", "学校", "未成年"]):
        return {
            "briefing": "系统已按校园警情建模。训练重点：保护未成年人、隔离风险源、稳定秩序、通知校方和监护人、依法依规处置。",
            "tags": ["模拟警情", "校园警情", "AI节点化"],
            "nodes": [
                common_arrival,
                _police_node_spec(
                    title="校园现场风险识别",
                    police_node_type="risk_identification",
                    question="校园场景中当前有哪些特殊风险？",
                    scene_summary="现场可能涉及未成年人、围观学生和校园秩序，需要兼顾安全和保护。",
                    standard_points=["优先保护未成年人安全", "隔离涉事人员和围观学生", "确认是否存在伤情或器械", "通知校方协助维持秩序", "必要时联系监护人和医疗救助"],
                    risk_signals=["未成年人", "围观学生", "伤情", "器械"],
                    law_points=["依法保护未成年人权益", "维护校园秩序"],
                    keywords=["未成年人", "隔离", "校方", "监护人", "救助"],
                ),
                _police_node_spec(
                    title="校园处置决策",
                    police_node_type="disposal_decision",
                    question="你会如何安排现场处置顺序？",
                    scene_summary="现场需要先保护学生安全，再开展调查核实。",
                    standard_points=["先控制现场秩序和安全范围", "分别询问涉事学生和目击人员", "通知校方与监护人到场", "固定证据并保护隐私", "依法依规移交或处理"],
                    risk_signals=["秩序混乱", "隐私泄露", "证据灭失"],
                    law_points=["保护未成年人隐私", "依法调查取证"],
                    keywords=["秩序", "询问", "校方", "监护人", "证据"],
                ),
                common_communication,
            ],
        }

    if _contains_any(normalized, ["求助", "救助", "伤害", "受伤", "群众"]):
        return {
            "briefing": "系统已按群众求助/救助警情建模。训练重点：快速评估危险、先救助后调查、联系医疗、稳定群众、记录和移交。",
            "tags": ["模拟警情", "群众求助", "AI节点化"],
            "nodes": [
                common_arrival,
                _police_node_spec(
                    title="救助风险识别",
                    police_node_type="risk_identification",
                    question="当前求助现场需要优先判断哪些风险？",
                    scene_summary="群众求助场景通常需要同时判断人身安全、伤情和现场持续风险。",
                    standard_points=["确认是否有持续危险源", "判断伤情和生命体征", "疏散围观并留出救助空间", "联系120或相关部门", "保护现场和个人隐私"],
                    risk_signals=["持续危险", "伤情", "围观", "隐私"],
                    law_points=["及时救助群众", "保护现场秩序"],
                    keywords=["危险", "伤情", "120", "疏散", "隐私"],
                ),
                _police_node_spec(
                    title="先救助后调查",
                    police_node_type="disposal_decision",
                    question="你下一步会先救助还是先询问？请说明处置顺序。",
                    scene_summary="人员可能受伤，处置顺序应优先保障生命安全。",
                    standard_points=["优先确认生命安全并呼叫医疗", "安排人员保护现场秩序", "待安全后再询问核实", "记录关键证据和求助信息", "必要时联动相关部门"],
                    risk_signals=["生命安全", "现场秩序", "证据灭失"],
                    law_points=["生命安全优先", "依法记录和移交"],
                    keywords=["救助", "医疗", "秩序", "询问", "记录"],
                ),
                common_communication,
            ],
        }

    if _contains_any(normalized, ["交通", "车辆", "事故", "路面", "拦停"]):
        return {
            "briefing": "系统已按交通现场处置警情建模。训练重点：安全站位、现场警戒、伤情救助、交通疏导、证据固定和依法处置。",
            "tags": ["模拟警情", "交通现场处置", "AI节点化"],
            "nodes": [
                common_arrival,
                _police_node_spec(
                    title="交通现场风险识别",
                    police_node_type="risk_identification",
                    question="到达交通现场后，你首先要识别哪些安全风险？",
                    scene_summary="车辆、行人和围观人员交织，现场可能存在二次事故、伤员救助和交通拥堵风险。",
                    standard_points=["设置安全警戒和提示标志", "观察车流方向和二次事故风险", "确认是否有伤员并优先救助", "疏导围观人员保持通道", "保护现场证据和行车记录"],
                    risk_signals=["二次事故", "车流穿行", "伤员", "围观聚集"],
                    law_points=["依法维护交通秩序", "保护现场证据", "生命安全优先"],
                    keywords=["警戒", "车流", "伤员", "疏导", "证据"],
                ),
                _police_node_spec(
                    title="交通处置决策",
                    police_node_type="disposal_decision",
                    question="你会如何安排现场处置顺序？",
                    scene_summary="现场需要在安全防护、救助伤员、恢复秩序和调查取证之间快速排序。",
                    standard_points=["先设置警戒确保人员安全", "优先救助伤员并联系医疗", "疏导交通避免拥堵和二次事故", "固定证据并询问当事人", "依法告知后续处理流程"],
                    risk_signals=["警戒不足", "救助延误", "交通拥堵", "证据灭失"],
                    law_points=["依法调查交通现场", "依法告知处理流程"],
                    keywords=["警戒", "救助", "疏导", "证据", "告知"],
                ),
                common_communication,
            ],
        }

    if _contains_any(normalized, ["失控", "精神", "异常", "扬言", "自伤"]):
        return {
            "briefing": "系统已按突发人员失控警情建模。训练重点：安全距离、刺激源控制、柔性沟通、支援联动、医疗协同和必要控制。",
            "tags": ["模拟警情", "突发人员失控", "AI节点化"],
            "nodes": [
                common_arrival,
                _police_node_spec(
                    title="失控人员风险识别",
                    police_node_type="risk_identification",
                    question="面对疑似失控人员，你要优先识别哪些风险？",
                    scene_summary="当事人情绪或行为明显异常，可能存在自伤、伤人、持物攻击或围观刺激风险。",
                    standard_points=["保持安全距离和退路", "识别自伤伤人和持物风险", "减少围观和刺激源", "呼叫支援并准备防护", "评估是否需要医疗协同"],
                    risk_signals=["自伤", "伤人", "持物", "围观刺激"],
                    law_points=["保护当事人和群众安全", "必要时依法采取保护性约束"],
                    keywords=["距离", "自伤", "伤人", "支援", "医疗"],
                ),
                _police_node_spec(
                    title="失控人员稳控决策",
                    police_node_type="disposal_decision",
                    question="如果对方持续激动并靠近群众，你会如何处置？",
                    scene_summary="失控人员可能向群众靠近，现场处置需要兼顾柔性稳控和必要安全控制。",
                    standard_points=["先疏散群众并建立安全范围", "使用低刺激语言安抚", "明确分工形成控制保护队形", "联系医疗或家属协助", "必要时依法采取控制措施并全程记录"],
                    risk_signals=["靠近群众", "失控升级", "单警处置", "记录缺失"],
                    law_points=["依法采取必要控制措施", "全过程记录", "医疗协同处置"],
                    keywords=["疏散", "安抚", "分工", "医疗", "控制"],
                ),
                common_communication,
            ],
        }

    return {
        "briefing": "系统已按通用模拟警情建模。训练重点：到场观察、风险识别、处置决策、规范话术和复盘评分。",
        "tags": ["模拟警情", "AI节点化"],
        "nodes": [
            common_arrival,
            _police_node_spec(
                title="现场风险识别",
                police_node_type="risk_identification",
                question="当前现场有哪些风险点？你下一步如何避免风险升级？",
                scene_summary="模拟警情进入关键处置阶段，需要先识别人、物、环境和情绪风险。",
                standard_points=["识别人员情绪和肢体冲突风险", "识别危险物品或环境风险", "保持安全站位和退路", "必要时请求支援", "先稳控秩序再调查"],
                risk_signals=["情绪激动", "危险物品", "现场混乱"],
                law_points=["依法维护秩序", "保护群众和民警安全"],
                keywords=["风险", "危险", "站位", "支援", "稳控"],
            ),
            _police_node_spec(
                title="处置决策",
                police_node_type="disposal_decision",
                question="你会如何安排下一步处置顺序？",
                scene_summary="现场需要在安全、合法和有效之间做出规范处置。",
                standard_points=["先控制现场秩序", "分离或稳控重点人员", "核实基本事实并固定证据", "根据风险请求支援", "依法告知和处置"],
                risk_signals=["秩序失控", "人员对抗", "证据灭失"],
                law_points=["依法调查取证", "依法告知", "依法处置"],
                keywords=["秩序", "分离", "证据", "支援", "依法"],
            ),
            common_communication,
        ],
    }


def _infer_scene_profile(title: str, scenario_hint: Optional[str] = None) -> dict[str, Any]:
    source = _scenario_title_source(title, scenario_hint)
    normalized = (source or "").lower()
    if _contains_any(
        normalized,
        ["警情", "家庭", "纠纷", "酒后", "醉酒", "滋事", "校园", "群众", "求助", "救助", "处置"],
    ):
        return _infer_police_incident_profile(source)
    profiles = [
        {
            "match": ["交通", "拦停", "查车", "路检"],
            "briefing": "系统已按交通执法场景自动建模，建议重点检查站位安全、拦停示意、证件查验和规范告知。",
            "tags": ["交通执法", "车辆检查"],
            "nodes": [
                {
                    "title": "安全示意停车",
                    "instruction": "请规范示意目标车辆靠边停车，并保持安全站位。",
                    "gesture_hint": "使用拦停或停止手势，动作清晰稳定。",
                    "speech_hint": "请靠边停车，配合检查。",
                    "required_gesture": "stop_signal",
                    "required_keywords": ["靠边停车", "配合检查"],
                    "prop_label": "执法指挥手势",
                },
                {
                    "title": "出示证件并表明身份",
                    "instruction": "请出示执法证件，并向对方说明身份与执法目的。",
                    "gesture_hint": "将证件稳定展示在胸前中部，便于对方辨认。",
                    "speech_hint": "您好，我是执勤民警，请出示相关证件。",
                    "required_gesture": "show_id",
                    "required_keywords": ["民警", "请出示"],
                    "prop_label": "检查证件",
                },
                {
                    "title": "说明检查事项",
                    "instruction": "请说明本次检查依据，以及对方需要配合的事项。",
                    "speech_hint": "现进行例行检查，请配合出示驾驶证和行驶证。",
                    "required_keywords": ["例行检查", "驾驶证", "行驶证"],
                    "node_type": "voice_qa",
                },
            ],
        },
        {
            "match": ["证件", "身份", "盘查", "核验"],
            "briefing": "系统已按身份核验场景自动建模，建议重点关注敬礼、证件出示、口头核查和结果告知。",
            "tags": ["身份核验", "证件检查"],
            "nodes": [
                {
                    "title": "规范敬礼与身份表明",
                    "instruction": "请先敬礼，再清晰表明执法身份。",
                    "gesture_hint": "右手抬至眉心附近完成标准敬礼。",
                    "speech_hint": "您好，我是执勤民警，请配合身份检查。",
                    "required_gesture": "salute",
                    "required_keywords": ["民警", "身份检查"],
                },
                {
                    "title": "出示证件",
                    "instruction": "请出示执法证件，并保持证件展示动作稳定。",
                    "gesture_hint": "双手在胸前中部稳定展示证件。",
                    "required_gesture": "show_id",
                    "prop_label": "执法证件",
                    "prop_hint": "请先取出执法证件，再进行身份核验说明。",
                },
                {
                    "title": "核验信息并说明要求",
                    "instruction": "请告知对方需要配合提供的身份信息。",
                    "speech_hint": "请出示身份证件，并保持原地配合核验。",
                    "required_keywords": ["身份证", "配合核验"],
                    "node_type": "voice_qa",
                },
            ],
        },
    ]
    for profile in profiles:
        if _contains_any(normalized, profile["match"]):
            return profile
    return {
        "match": [],
        "briefing": "系统已按通用交互实训视频自动建模，请检查节点节奏、动作要求和标准话术后直接使用。",
        "tags": ["自动建模"],
        "nodes": [
            {
                "title": "动作示意",
                "instruction": "请根据视频情境完成规范动作示意。",
                "gesture_hint": "动作清晰，保持短暂稳定。",
                "required_gesture": "raise_hand",
            },
            {
                "title": "出示证件",
                "instruction": "请出示执法证件并说明身份。",
                "gesture_hint": "双手胸前保持证件展示姿态。",
                "speech_hint": "您好，我是执勤民警，请配合检查。",
                "required_gesture": "show_id",
                "required_keywords": ["民警", "配合检查"],
                "prop_label": "执法证件",
            },
            {
                "title": "口头处置说明",
                "instruction": "请说明后续处置要求和注意事项。",
                "speech_hint": "请保持冷静，按要求配合后续处置。",
                "required_keywords": ["保持冷静", "配合"],
                "node_type": "voice_qa",
            },
        ],
    }


def _fallback_type(title_hint: str) -> str:
    interactive_keywords = ["实训", "训练", "考核", "演练", "执法", "处置", "盘查", "问答", "拦截", "interactive"]
    return "interactive" if _contains_any(title_hint, interactive_keywords) else "teaching"


def _sample_video_frames(video_path: str, max_frames: int = 6) -> list[dict[str, Any]]:
    try:
        import cv2  # type: ignore
    except Exception:
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_seconds = total_frames / fps if total_frames > 0 else 0
    if duration_seconds <= 0:
        positions = [0.0]
    else:
        slots = min(max_frames, max(1, int(math.ceil(duration_seconds / 20))))
        positions = [duration_seconds * (idx + 1) / (slots + 1) for idx in range(slots)]

    frames: list[dict[str, Any]] = []
    for seconds in positions:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(seconds, 0.0) * 1000)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        payload = encoded.tobytes()
        frames.append(
            {
                "timestamp": round(seconds, 1),
                "bytes": payload,
                "data_url": "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii"),
            }
        )
    cap.release()
    return frames


def _extract_ocr_hints(frames: list[dict[str, Any]], limit: int = 4) -> list[str]:
    try:
        from paddleocr import PaddleOCR  # type: ignore
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return []

    hints: list[str] = []
    try:
        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    except Exception:
        return []

    for frame in frames[:limit]:
        try:
            array = np.frombuffer(frame["bytes"], dtype=np.uint8)
            image = cv2.imdecode(array, cv2.IMREAD_COLOR)
            if image is None:
                continue
            result = ocr.ocr(image, cls=True) or []
            texts: list[str] = []
            for line in result:
                for item in line or []:
                    text = str((item[1] or [""])[0]).strip()
                    if text:
                        texts.append(text)
            joined = " ".join(texts[:8]).strip()
            if joined:
                hints.append(f"{frame['timestamp']}s: {joined}")
        except Exception:
            continue
    return hints


def _build_default_nodes(
    title_hint: str,
    duration_seconds: Optional[int],
    scenario_hint: Optional[str] = None,
) -> list[dict[str, Any]]:
    profile = _infer_scene_profile(title_hint, scenario_hint)
    specs = profile.get("nodes") or []
    if not specs:
        return []
    trigger_times = suggest_training_timestamps(None, duration_seconds, len(specs))

    nodes: list[dict[str, Any]] = []
    for index, spec in enumerate(specs):
        required_gesture = spec.get("required_gesture")
        required_keywords = spec.get("required_keywords") or []
        node_type = spec.get("node_type") or ("voice_qa" if required_keywords else "action")
        police_node_type = spec.get("police_node_type")
        standard_points = spec.get("standard_points") if isinstance(spec.get("standard_points"), list) else []
        risk_signals = spec.get("risk_signals") if isinstance(spec.get("risk_signals"), list) else []
        law_points = spec.get("law_points") if isinstance(spec.get("law_points"), list) else []
        prompt_content = {
            "instruction": spec.get("instruction") or f"请完成第 {index + 1} 个自动生成的训练动作。",
            "gesture_hint": spec.get("gesture_hint") or "",
            "speech_hint": spec.get("speech_hint") or "",
            "prop_label": spec.get("prop_label") or ("执法证件" if required_gesture == "show_id" else ""),
            "prop_hint": spec.get("prop_hint") or "",
            "gesture_config": {
                "min_confidence": 0.55,
                "hold_frames": 5,
                "tolerance": "standard",
            },
            "identity_config": {
                "mode": "presence",
                "require_single_face": True,
                "require_live_motion": True,
                "backend_cv": False,
            },
        }
        if police_node_type:
            prompt_content.update(
                {
                    "scene_summary": spec.get("scene_summary") or "",
                    "police_question": spec.get("police_question") or spec.get("instruction") or "",
                    "answer_mode": spec.get("answer_mode") or "text_or_voice",
                    "node_badge": spec.get("node_badge") or POLICE_NODE_LABELS.get(str(police_node_type), "警情处置"),
                }
            )
        assessment_points = (
            _police_assessment_points(index, str(police_node_type), [str(item) for item in standard_points])
            if police_node_type and standard_points
            else _default_assessment_points_for_auto_node(
                index,
                node_type=node_type,
                required_gesture=required_gesture,
                required_keywords=required_keywords,
                prop_mode="manual" if spec.get("prop_label") else "auto",
            )
        )
        nodes.append(
            {
                "title": spec.get("title") or f"自动节点 {index + 1}",
                "trigger_time": trigger_times[index],
                "pause_mode": "auto_pause",
                "timeout_seconds": 75 if police_node_type else (45 if node_type == "voice_qa" else 30),
                "retry_score_deduct": 5,
                "skip_score_deduct": 15,
                "prop_mode": "manual" if spec.get("prop_label") else "auto",
                "node_type": node_type,
                "required_gesture": required_gesture,
                "required_keywords": required_keywords,
                "score_weight": 10,
                "prompt_content": prompt_content,
                "node_config": {
                    **(
                        {
                            "police_node_type": police_node_type,
                            "standard_points": standard_points,
                            "risk_signals": risk_signals,
                            "law_points": law_points,
                            "score_rubric": POLICE_SCORE_RUBRIC,
                            "semantic_pass_threshold": 50,
                            "semantic_full_threshold": 85,
                        }
                        if police_node_type
                        else {}
                    ),
                    "speech_rule": {
                        "match_mode": "any",
                        "min_count": 1,
                        "min_length": 8 if police_node_type else 0,
                    },
                    "pass_rule": {
                        "mode": "speech_only" if police_node_type else ("all" if required_gesture and required_keywords else ("gesture_only" if required_gesture else "speech_only")),
                    },
                    "assessment_points": assessment_points,
                    "hybrid_signals": {
                        "use_template": True,
                        "use_frames": True,
                        "use_ocr": True,
                        "use_transcript": True,
                    },
                },
            }
        )
    return nodes


def suggest_training_timestamps(
    video_path: Optional[str],
    duration_seconds: Optional[int],
    target_count: int,
) -> list[int]:
    if target_count <= 0:
        return []

    duration = int(duration_seconds or 0)
    fallback = _evenly_spaced_timestamps(duration, target_count)
    if not video_path:
        return fallback

    try:
        sampled = _sample_visual_change_points(video_path, duration, target_count)
    except Exception:
        sampled = []
    return sampled or fallback


def _evenly_spaced_timestamps(duration: int, target_count: int) -> list[int]:
    if duration <= 0:
        return [15 + idx * 20 for idx in range(target_count)]

    start = max(8, min(20, duration // 8 or 8))
    end = max(duration - 10, start + target_count * 8)
    span = max(end - start, target_count * 6)
    return [
        max(1, min(max(duration - 2, 1), int(round(start + (span * idx) / max(target_count - 1, 1)))))
        for idx in range(target_count)
    ]


def _sample_visual_change_points(video_path: str, duration: int, target_count: int) -> list[int]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []

    resolved_duration = duration
    if resolved_duration <= 0:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        resolved_duration = int(total_frames / fps) if total_frames > 0 else 0
    if resolved_duration <= 0:
        cap.release()
        return []

    sample_count = max(target_count * 8, min(48, max(12, resolved_duration // 2)))
    candidate_times = sorted({
        max(0.0, min(float(resolved_duration - 0.3), resolved_duration * (idx + 1) / (sample_count + 1)))
        for idx in range(sample_count)
    })

    previous_small = None
    scored_points: list[tuple[float, float]] = []
    for seconds in candidate_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        if brightness < 10:
            continue

        small = cv2.resize(gray, (64, 36))
        edge_score = float(cv2.Laplacian(small, cv2.CV_64F).var())
        motion_score = 0.0
        if previous_small is not None:
            diff = cv2.absdiff(small, previous_small)
            motion_score = float(diff.mean())
        previous_small = small
        score = motion_score * 0.72 + edge_score * 0.18 + min(brightness, 120.0) * 0.10
        scored_points.append((seconds, score))

    cap.release()
    if not scored_points:
        return []

    min_gap = max(4.0, resolved_duration / max(target_count + 1, 2) * 0.55)
    selected: list[float] = []
    for seconds, _score in sorted(scored_points, key=lambda item: item[1], reverse=True):
        if any(abs(seconds - existing) < min_gap for existing in selected):
            continue
        selected.append(seconds)
        if len(selected) >= target_count:
            break

    if not selected:
        return []
    return sorted(max(1, min(max(resolved_duration - 2, 1), int(round(item)))) for item in selected)


def _fallback_analysis(
    title_hint: str,
    duration_seconds: Optional[int],
    preferred_type: Optional[str] = None,
    scenario_hint: Optional[str] = None,
    training_variant: Optional[str] = None,
    difficulty_level: Optional[str] = None,
) -> dict[str, Any]:
    scenario = _normalize_police_scenario(scenario_hint)
    if preferred_type in {"teaching", "interactive"}:
        video_type = preferred_type
    elif scenario:
        video_type = "interactive"
    else:
        video_type = _fallback_type(title_hint)
    nodes = _build_default_nodes(title_hint, duration_seconds, scenario_hint) if video_type == "interactive" else []
    profile = _infer_scene_profile(title_hint, scenario_hint) if video_type == "interactive" else {
        "briefing": "该视频已按教学素材自动入库，可直接用于预习和复盘。",
        "tags": ["教学素材"],
    }
    payload = {
        "analysis_mode": "template_fallback",
        "title": title_hint or "未命名视频",
        "description": "系统已自动完成基础分析；当前结果基于本地规则模板生成，可继续人工微调。",
        "video_type": video_type,
        "briefing": profile.get("briefing"),
        "tags": ["自动导入", *(profile.get("tags") or [])],
        "status": "draft",
        "nodes": nodes,
        "suggested_timestamps": [int(item.get("trigger_time") or 0) for item in nodes],
        "node_generation_mode": "scene_profile_fallback" if video_type == "interactive" else "teaching_no_nodes",
    }
    if video_type == "interactive":
        payload = _apply_training_metadata(
            payload,
            scenario_hint=scenario_hint,
            training_variant=training_variant,
            difficulty_level=difficulty_level,
        )
    return payload


def _normalize_node(raw: dict[str, Any], index: int, duration_seconds: Optional[int]) -> dict[str, Any]:
    duration = max(1, int(duration_seconds or 0) or 120)
    trigger_time = int(raw.get("trigger_time") or max(1, min(duration - 2, 12 + index * 18)))
    node_type = str(raw.get("node_type") or "action").strip() or "action"
    required_keywords = raw.get("required_keywords") if isinstance(raw.get("required_keywords"), list) else []
    prompt_content = raw.get("prompt_content") if isinstance(raw.get("prompt_content"), dict) else {}
    node_config = raw.get("node_config") if isinstance(raw.get("node_config"), dict) else {}
    police_node_type = str(
        raw.get("police_node_type")
        or node_config.get("police_node_type")
        or ""
    ).strip()
    standard_points = node_config.get("standard_points")
    if not isinstance(standard_points, list):
        standard_points = raw.get("standard_points") if isinstance(raw.get("standard_points"), list) else []
    risk_signals = node_config.get("risk_signals")
    if not isinstance(risk_signals, list):
        risk_signals = raw.get("risk_signals") if isinstance(raw.get("risk_signals"), list) else []
    law_points = node_config.get("law_points")
    if not isinstance(law_points, list):
        law_points = raw.get("law_points") if isinstance(raw.get("law_points"), list) else []

    prompt_content.setdefault("instruction", raw.get("instruction") or f"请完成节点 {index + 1} 的训练要求。")
    prompt_content.setdefault("gesture_hint", raw.get("gesture_hint") or "")
    prompt_content.setdefault("speech_hint", raw.get("speech_hint") or "")
    prompt_content.setdefault("prop_label", raw.get("prop_label") or "")
    prompt_content.setdefault("prop_hint", raw.get("prop_hint") or "")
    if police_node_type:
        prompt_content.setdefault("scene_summary", raw.get("scene_summary") or prompt_content.get("scene_summary") or "")
        prompt_content.setdefault("police_question", raw.get("police_question") or prompt_content.get("police_question") or prompt_content["instruction"])
        prompt_content.setdefault("answer_mode", raw.get("answer_mode") or "text_or_voice")
        prompt_content.setdefault("node_badge", raw.get("node_badge") or POLICE_NODE_LABELS.get(police_node_type, "警情处置"))
    prompt_content.setdefault(
        "gesture_config",
        {"min_confidence": 0.55, "hold_frames": 5, "tolerance": "standard"},
    )
    prompt_content.setdefault(
        "identity_config",
        {"mode": "presence", "require_single_face": True, "require_live_motion": True, "backend_cv": False},
    )

    if police_node_type:
        node_config.setdefault("police_node_type", police_node_type)
        node_config.setdefault("standard_points", [str(item) for item in standard_points if str(item).strip()])
        node_config.setdefault("risk_signals", [str(item) for item in risk_signals if str(item).strip()])
        node_config.setdefault("law_points", [str(item) for item in law_points if str(item).strip()])
        node_config.setdefault("score_rubric", POLICE_SCORE_RUBRIC)
        node_config.setdefault("semantic_pass_threshold", 50)
        node_config.setdefault("semantic_full_threshold", 85)

    default_pass_mode = "speech_only"
    if not police_node_type:
        if raw.get("required_gesture") and required_keywords:
            default_pass_mode = "all"
        elif raw.get("required_gesture"):
            default_pass_mode = "gesture_only"

    node_config.setdefault("speech_rule", {"match_mode": "any", "min_count": 1, "min_length": 8 if police_node_type else 0})
    node_config.setdefault(
        "pass_rule",
        {"mode": default_pass_mode},
    )
    node_config.setdefault(
        "assessment_points",
        _police_assessment_points(index, police_node_type, [str(item) for item in standard_points])
        if police_node_type and standard_points
        else _default_assessment_points_for_auto_node(
            index,
            node_type=node_type,
            required_gesture=raw.get("required_gesture"),
            required_keywords=required_keywords,
            prop_mode=str(raw.get("prop_mode") or ("manual" if prompt_content.get("prop_label") else "auto")),
        ),
    )
    node_config.setdefault(
        "hybrid_signals",
        {
            "use_template": True,
            "use_frames": True,
            "use_ocr": True,
            "use_transcript": True,
        },
    )

    return {
        "title": str(raw.get("title") or f"自动节点 {index + 1}").strip(),
        "trigger_time": trigger_time,
        "pause_mode": str(raw.get("pause_mode") or "auto_pause"),
        "timeout_seconds": int(raw.get("timeout_seconds") or (75 if police_node_type else (45 if node_type == "voice_qa" else 30))),
        "retry_score_deduct": int(raw.get("retry_score_deduct") or 5),
        "skip_score_deduct": int(raw.get("skip_score_deduct") or 15),
        "prop_mode": str(raw.get("prop_mode") or ("manual" if prompt_content.get("prop_label") else "auto")),
        "node_type": node_type,
        "required_gesture": raw.get("required_gesture"),
        "required_keywords": required_keywords,
        "score_weight": int(raw.get("score_weight") or 10),
        "prompt_content": prompt_content,
        "node_config": node_config,
    }


def _normalize_analysis(
    payload: dict[str, Any],
    title_hint: str,
    duration_seconds: Optional[int],
    preferred_type: Optional[str] = None,
    scenario_hint: Optional[str] = None,
    training_variant: Optional[str] = None,
    difficulty_level: Optional[str] = None,
) -> dict[str, Any]:
    fallback = _fallback_analysis(
        title_hint,
        duration_seconds,
        preferred_type,
        scenario_hint,
        training_variant,
        difficulty_level,
    )
    title = str(payload.get("title") or fallback["title"]).strip()
    scenario = _normalize_police_scenario(scenario_hint)
    if preferred_type in {"teaching", "interactive"}:
        video_type = preferred_type
    elif scenario:
        video_type = "interactive"
    else:
        video_type = str(payload.get("video_type") or fallback["video_type"]).strip().lower()
        if video_type not in {"teaching", "interactive"}:
            video_type = fallback["video_type"]

    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else fallback["tags"]
    tags = [str(item).strip() for item in tags if str(item).strip()]
    if "自动导入" not in tags:
        tags.insert(0, "自动导入")

    raw_nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else fallback["nodes"]
    nodes = [
        _normalize_node(item if isinstance(item, dict) else {}, index, duration_seconds)
        for index, item in enumerate(raw_nodes[:8])
    ]
    if video_type == "interactive" and not nodes:
        nodes = fallback["nodes"]

    normalized = {
        "analysis_mode": str(payload.get("analysis_mode") or "llm_vision"),
        "title": title or fallback["title"],
        "description": str(payload.get("description") or fallback["description"]).strip(),
        "video_type": video_type,
        "briefing": str(payload.get("briefing") or fallback["briefing"]).strip(),
        "tags": tags,
        "status": str(payload.get("status") or "draft") if str(payload.get("status") or "draft") in {"draft", "published", "archived"} else "draft",
        "nodes": nodes if video_type == "interactive" else [],
        "suggested_timestamps": [int(item.get("trigger_time") or 0) for item in nodes] if video_type == "interactive" else [],
        "node_generation_mode": "llm_generated" if payload.get("nodes") else fallback.get("node_generation_mode"),
    }
    if video_type == "interactive":
        normalized = _apply_training_metadata(
            normalized,
            scenario_hint=scenario_hint,
            training_variant=training_variant,
            difficulty_level=difficulty_level,
        )
    return normalized


def _request_llm_analysis(
    *,
    title_hint: str,
    duration_seconds: Optional[int],
    frames: list[dict[str, Any]],
    ocr_hints: list[str],
    preferred_type: Optional[str] = None,
    scenario_hint: Optional[str] = None,
    training_variant: Optional[str] = None,
    difficulty_level: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if not ACTIVE_API_KEY or not frames:
        return None

    user_content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "你是公安实战训练课程编排专家。请根据视频抽帧，把模拟警情视频拆解成可训练、可评分、可复盘的警情处置节点。"
                "必须只返回 JSON 对象，字段包括："
                "title, description, video_type(teaching|interactive), briefing, tags, status(draft|published|archived), nodes。"
                "nodes 是数组，每项包括：title, trigger_time, pause_mode, timeout_seconds, retry_score_deduct, "
                "skip_score_deduct, prop_mode, node_type, required_gesture, required_keywords, score_weight, "
                "prompt_content, node_config。node_config 内尽量补 assessment_points，"
                "每个 assessment_point 至少包含 id, label, content, dimension, required, rule(channel/mode)。"
                "如果是模拟警情或情景处置视频，video_type 必须为 interactive，节点数量控制在 4-6 个，"
                "优先按警情发展阶段切分，而不是平均切时间。警情节点必须使用 node_type=voice_qa，"
                "node_config 必须包含 police_node_type(arrival_observation|risk_identification|disposal_decision|standard_communication), "
                "standard_points, risk_signals, law_points, score_rubric。prompt_content 必须包含 scene_summary, police_question, answer_mode, node_badge。"
                "评分维度使用 risk_awareness, procedure, communication, lawfulness, safety。"
                "处置建议必须依法、安全、克制，不得生成越权、危险或刺激冲突的建议。"
                "如果视频明显是教学讲解或纯展示，video_type 设为 teaching 且 nodes 返回空数组；"
                "如果是执法演示、动作演练、情景化训练，则输出可暂停追问的训练节点。"
            ),
        },
        {
            "type": "text",
            "text": (
                f"title_hint={title_hint or '未提供'}; "
                f"duration_seconds={int(duration_seconds or 0)}; "
                f"preferred_type={preferred_type or 'auto'}; "
                f"police_scenario={_normalize_police_scenario(scenario_hint) or 'auto'}; "
                f"training_variant={_normalize_training_variant(training_variant)}; "
                f"difficulty_level={_normalize_difficulty_level(difficulty_level)}; "
                f"ocr_hints={' | '.join(ocr_hints[:6]) if ocr_hints else 'none'}; "
                "analysis_workflow=template+frames+ocr+transcript+llm"
            ),
        },
    ]
    for frame in frames[:6]:
        user_content.append(
            {
                "type": "text",
                "text": f"frame_timestamp={frame['timestamp']}s",
            }
        )
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": frame["data_url"]},
            }
        )

    response = client.chat.completions.create(
        model=get_chat_model(),
        messages=[
            {
                "role": "system",
                "content": "Return valid json only. Do not output markdown or explanation.",
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=3000,
    )
    payload = extract_json_payload(extract_message_text(response))
    return payload if isinstance(payload, dict) else None


def analyze_video_file(
    video_path: str,
    *,
    title_hint: str = "",
    duration_seconds: Optional[int] = None,
    preferred_type: Optional[str] = None,
    scenario_hint: Optional[str] = None,
    training_variant: Optional[str] = None,
    difficulty_level: Optional[str] = None,
) -> dict[str, Any]:
    fallback = _fallback_analysis(
        title_hint,
        duration_seconds,
        preferred_type,
        scenario_hint,
        training_variant,
        difficulty_level,
    )
    frames = _sample_video_frames(video_path)
    ocr_hints = _extract_ocr_hints(frames)

    def apply_suggested_timestamps(payload: dict[str, Any]) -> dict[str, Any]:
        nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
        if not nodes:
            payload["suggested_timestamps"] = []
            return payload
        suggested = suggest_training_timestamps(video_path, duration_seconds, len(nodes))
        if suggested:
            for index, timestamp in enumerate(suggested):
                if index < len(nodes) and isinstance(nodes[index], dict):
                    nodes[index]["trigger_time"] = int(timestamp)
        payload["nodes"] = nodes
        payload["suggested_timestamps"] = [int(item.get("trigger_time") or 0) for item in nodes if isinstance(item, dict)]
        return payload

    try:
        payload = _request_llm_analysis(
            title_hint=title_hint,
            duration_seconds=duration_seconds,
            frames=frames,
            ocr_hints=ocr_hints,
            preferred_type=preferred_type,
            scenario_hint=scenario_hint,
            training_variant=training_variant,
            difficulty_level=difficulty_level,
        )
        if not payload:
            return apply_suggested_timestamps({
                **fallback,
                "frame_count": len(frames),
                "ocr_hints": ocr_hints,
            })
        normalized = _normalize_analysis(
            payload,
            title_hint,
            duration_seconds,
            preferred_type,
            scenario_hint,
            training_variant,
            difficulty_level,
        )
        normalized = apply_suggested_timestamps(normalized)
        normalized["frame_count"] = len(frames)
        normalized["ocr_hints"] = ocr_hints
        return normalized
    except Exception as exc:
        fallback["analysis_error"] = str(exc)
        fallback["frame_count"] = len(frames)
        fallback["ocr_hints"] = ocr_hints
        return apply_suggested_timestamps(fallback)
