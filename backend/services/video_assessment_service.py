from __future__ import annotations

import json
import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Optional

import models
from services.evaluation_service import compute_grade_level, merge_assessment_point_results

VIDEO_DIMENSION_LABELS = {
    "procedure_execution": "流程执行完整度",
    "verbal_communication": "语言表达与告知",
    "body_action": "动作规范与指令执行",
    "professional_safety": "执法规范与安全意识",
    "risk_awareness": "风险识别能力",
    "procedure": "处置程序能力",
    "communication": "沟通稳控能力",
    "lawfulness": "依法处置能力",
    "safety": "现场安全意识",
}

FROZEN_REPORT_DIMENSIONS = {"attention_focus", "facial_expression", "behavior_response"}
FROZEN_REPORT_CHANNELS = {"focus", "face", "behavior"}


def _load_json(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _dedupe_strings(values: list[Any], limit: int = 6) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        output.append(text)
        seen.add(text)
        if len(output) >= limit:
            break
    return output


def _semantic_point_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("point") or item.get("label") or item.get("content") or "").strip()
    return str(item or "").strip()


def _share_weight(total_weight: int, count: int) -> list[int]:
    count = max(1, count)
    total_weight = max(count, int(total_weight or count))
    base = total_weight // count
    remain = total_weight % count
    return [base + (1 if idx < remain else 0) for idx in range(count)]


def _reason_label(reason: str) -> str:
    labels = {
        "keyword_mismatch": "话术关键词未命中",
        "gesture_mismatch": "动作/手势未达标",
        "identity_mismatch": "身份/活体校验未通过",
        "prop_missed": "道具或证件操作缺失",
        "judge_incorrect": "判断题作答错误",
        "choice_incorrect": "选择题作答错误",
        "police_answer_empty": "警情处置回答为空",
        "police_points_missing": "警情处置要点覆盖不足",
        "tab_switch": "训练期间发生切屏",
        "page_hide": "训练页面进入后台",
        "page_leave": "训练中途离开页面",
        "device_lost": "设备接入状态异常",
        "identity_lost": "身份校验中断",
        "training_finished_early": "主动结束训练",
    }
    return labels.get(reason, reason)


def _is_frozen_report_point(point: dict[str, Any]) -> bool:
    dimension = str(point.get("dimension") or point.get("category") or "")
    rule = point.get("rule") if isinstance(point.get("rule"), dict) else {}
    channel = str(rule.get("channel") or "")
    return dimension in FROZEN_REPORT_DIMENSIONS or channel in FROZEN_REPORT_CHANNELS


def _sanitize_report_points(points: list[Any]) -> list[dict[str, Any]]:
    return [point for point in points if isinstance(point, dict) and not _is_frozen_report_point(point)]


def _sanitize_report_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {}
    return {
        key: value
        for key, value in evidence.items()
        if key not in {"focus", "face", "behavior", "degradation", "tool_evidence"}
    }


def _legacy_grade(percentage: int) -> str:
    if percentage >= 90:
        return "优秀"
    if percentage >= 70:
        return "合格"
    return "待重修"


def _default_assessment_points(node: models.VideoNode) -> list[dict[str, Any]]:
    keywords = _load_json(node.required_keywords, [])
    points: list[dict[str, Any]] = []

    points.append(
        {
            "id": f"node_{node.node_index + 1}_procedure",
            "label": "按节点要求完成处置流程",
            "content": "在限定时间内完成本节点处置，不跳过、不超时，结果有效。",
            "category": "procedure_execution",
            "required": True,
            "dimension": "procedure_execution",
            "rule": {"channel": "result", "mode": "result_pass"},
        }
    )

    if node.node_type in {"voice_qa", "action"} or keywords:
        points.append(
            {
                "id": f"node_{node.node_index + 1}_speech",
                "label": "标准话术与关键信息表达",
                "content": "表达清晰，并覆盖节点要求的关键话术或告知内容。",
                "category": "verbal_communication",
                "required": bool(keywords) or node.node_type == "voice_qa",
                "dimension": "verbal_communication",
                "rule": {"channel": "speech", "mode": "keywords"},
            }
        )

    if node.required_gesture:
        points.append(
            {
                "id": f"node_{node.node_index + 1}_gesture",
                "label": "动作/手势执行规范",
                "content": "按节点要求做出对应手势或动作，动作清晰、稳定、达标。",
                "category": "body_action",
                "required": True,
                "dimension": "body_action",
                "rule": {"channel": "gesture", "mode": "gesture_match"},
            }
        )

    prompt_content = _load_json(node.prompt_content, {})
    identity_config = prompt_content.get("identity_config") if isinstance(prompt_content, dict) else {}
    if isinstance(identity_config, dict) and (
        identity_config.get("require_single_face", True)
        or identity_config.get("require_live_motion", True)
        or identity_config.get("backend_cv")
    ):
        points.append(
            {
                "id": f"node_{node.node_index + 1}_identity",
                "label": "身份/活体状态合规",
                "content": "训练过程中保持单人入镜、活体状态正常，身份校验不中断。",
                "category": "professional_safety",
                "required": True,
                "dimension": "professional_safety",
                "rule": {"channel": "identity", "mode": "identity_ready"},
            }
        )

    if node.prop_mode == "manual":
        points.append(
            {
                "id": f"node_{node.node_index + 1}_prop",
                "label": "证件或装备操作规范",
                "content": "根据节点要求完成证件、装备或虚拟道具操作。",
                "category": "professional_safety",
                "required": True,
                "dimension": "professional_safety",
                "rule": {"channel": "prop", "mode": "prop_ready"},
            }
        )

    if node.node_type in {"judge", "choice"}:
        points.append(
            {
                "id": f"node_{node.node_index + 1}_decision",
                "label": "节点判断结果准确",
                "content": "按标准处置逻辑做出正确判断与选择。",
                "category": "professional_safety",
                "required": True,
                "dimension": "professional_safety",
                "rule": {"channel": "decision", "mode": "decision_correct"},
            }
        )

    weights = _share_weight(max(node.score_weight or 10, len(points)), len(points))
    for idx, point in enumerate(points):
        point["weight"] = weights[idx]
        point.setdefault("stage_name", node.title or f"节点{node.node_index + 1}")
    return points


def resolve_node_assessment_points(node: models.VideoNode) -> list[dict[str, Any]]:
    config = _load_json(node.node_config, {})
    configured = config.get("assessment_points") if isinstance(config, dict) else None
    if isinstance(configured, list) and configured:
        output: list[dict[str, Any]] = []
        weights = _share_weight(max(node.score_weight or len(configured), len(configured)), len(configured))
        for idx, item in enumerate(configured):
            if not isinstance(item, dict):
                continue
            point = dict(item)
            point.setdefault("id", f"node_{node.node_index + 1}_point_{idx + 1}")
            point.setdefault("label", f"考察点 {idx + 1}")
            point.setdefault("content", point["label"])
            point.setdefault("required", True)
            point.setdefault("category", point.get("dimension") or "procedure_execution")
            point.setdefault("dimension", point.get("category") or "procedure_execution")
            point.setdefault("stage_name", node.title or f"节点{node.node_index + 1}")
            point.setdefault("rule", {"channel": point.get("channel") or "result", "mode": point.get("mode") or "result_pass"})
            point.setdefault("weight", weights[idx])
            output.append(point)
        if output:
            return output
    standard_points = config.get("standard_points") if isinstance(config, dict) else None
    if isinstance(standard_points, list) and standard_points:
        output: list[dict[str, Any]] = []
        weights = _share_weight(max(node.score_weight or len(standard_points), len(standard_points)), len(standard_points))
        for idx, item in enumerate(standard_points):
            text = str(item or "").strip()
            if not text:
                continue
            output.append(
                {
                    "id": f"node_{node.node_index + 1}_standard_{idx + 1}",
                    "label": text,
                    "content": text,
                    "category": "procedure_execution",
                    "dimension": "procedure_execution",
                    "required": True,
                    "stage_name": node.title or f"节点{node.node_index + 1}",
                    "rule": {"channel": "result", "mode": "result_pass"},
                    "weight": weights[idx],
                }
            )
        if output:
            return output
    return _default_assessment_points(node)


def build_node_multimodal_evidence(
    session: models.VideoTrainingSession,
    node: models.VideoNode,
    result: models.VideoNodeResult,
) -> dict[str, Any]:
    answer_data = _load_json(result.answer_data, {}) if isinstance(result.answer_data, str) else (result.answer_data or {})
    violations = _load_json(session.violation_log, [])
    violation_types = [str(item.get("type") or "") for item in violations if isinstance(item, dict)]
    speech_analysis = answer_data.get("speech_analysis") if isinstance(answer_data, dict) else {}
    gesture_result = answer_data.get("gesture_result") if isinstance(answer_data, dict) else {}
    identity_result = answer_data.get("identity_result") if isinstance(answer_data, dict) else {}
    prop_interaction = answer_data.get("prop_interaction") if isinstance(answer_data, dict) else {}
    focus_result = answer_data.get("focus_result") if isinstance(answer_data, dict) else {}
    face_result = answer_data.get("face_result") if isinstance(answer_data, dict) else {}
    action_result = answer_data.get("action_result") if isinstance(answer_data, dict) else {}
    police_semantic = answer_data.get("police_semantic") if isinstance(answer_data, dict) else {}

    if not isinstance(speech_analysis, dict):
        speech_analysis = {}
    if not isinstance(gesture_result, dict):
        gesture_result = {}
    if not isinstance(identity_result, dict):
        identity_result = {}
    if not isinstance(prop_interaction, dict):
        prop_interaction = {}
    if not isinstance(focus_result, dict):
        focus_result = {}
    if not isinstance(face_result, dict):
        face_result = {}
    if not isinstance(action_result, dict):
        action_result = {}
    if not isinstance(police_semantic, dict):
        police_semantic = {}

    keyword_hits = speech_analysis.get("keyword_hits") if isinstance(speech_analysis.get("keyword_hits"), list) else []
    transcript = str(result.speech_transcript or "").strip()
    severe_violations = [item for item in violation_types if item in {"page_leave", "device_lost", "identity_lost"}]
    minor_violations = [item for item in violation_types if item in {"tab_switch", "page_hide"}]
    focus_score = focus_result.get("focus_score")
    if focus_score is None:
        focus_score = max(0, 100 - len(minor_violations) * 12 - len(severe_violations) * 22)
    expression_score = face_result.get("expression_score")
    if expression_score is None:
        expression_score = 86 if identity_result.get("single_face") and identity_result.get("live_ready") else 62 if identity_result.get("single_face") else 40
    behavior_score = action_result.get("behavior_score")
    if behavior_score is None:
        behavior_score = 88 if result.result == "pass" else 65 if result.result in {"skip", "timeout"} else 38

    degradation: list[dict[str, Any]] = []
    if not transcript:
        degradation.append({"channel": "speech", "status": "degraded", "reason": "缺少有效转写文本"})
    if not gesture_result and node.required_gesture:
        degradation.append({"channel": "gesture", "status": "degraded", "reason": "未采集到动作识别结果"})
    if not face_result:
        degradation.append({"channel": "face", "status": "degraded", "reason": "未接入表情识别模型，使用身份在场状态兜底"})
    if not focus_result:
        degradation.append({"channel": "focus", "status": "degraded", "reason": "未接入专注度模型，使用页面行为与活体状态兜底"})
    if not action_result:
        degradation.append({"channel": "behavior", "status": "degraded", "reason": "未接入动作序列模型，使用节点结果与重试表现兜底"})

    return {
        "captured_at": datetime.utcnow().isoformat(),
        "result": result.result,
        "retry_count": int(result.retry_count or 0),
        "time_used": int(result.time_used or 0),
        "speech": {
            "transcript": transcript,
            "transcript_length": len(transcript),
            "keyword_hits": _dedupe_strings(keyword_hits, limit=8),
            "match_mode": speech_analysis.get("match_mode"),
            "min_count": speech_analysis.get("min_count"),
            "min_length": speech_analysis.get("min_length"),
        },
        "gesture": {
            "required_gesture": gesture_result.get("required_gesture") or node.required_gesture,
            "matched": bool(gesture_result.get("matched")),
            "confidence": round(_safe_float(gesture_result.get("confidence")), 4),
            "streak": _safe_int(gesture_result.get("streak")),
            "status": gesture_result.get("status"),
            "message": gesture_result.get("message"),
        },
        "identity": {
            "mode": identity_result.get("mode"),
            "verified": bool(identity_result.get("verified")),
            "single_face": bool(identity_result.get("single_face")),
            "live_ready": bool(identity_result.get("live_ready")),
            "matched": bool(identity_result.get("matched")),
        },
        "prop": {
            "mode": prop_interaction.get("mode") or node.prop_mode,
            "ready": bool(prop_interaction.get("ready")),
            "label": prop_interaction.get("label"),
            "activated_at": prop_interaction.get("activated_at"),
        },
        "focus": {
            "focus_score": round(_safe_float(focus_score, 0), 1),
            "minor_violation_count": len(minor_violations),
            "severe_violation_count": len(severe_violations),
            "violation_types": _dedupe_strings(violation_types, limit=10),
        },
        "face": {
            "expression_score": round(_safe_float(expression_score, 0), 1),
            "emotion": face_result.get("emotion") or face_result.get("dominant_emotion"),
            "attention_ready": bool(identity_result.get("single_face")) and bool(identity_result.get("live_ready")),
            "confidence": round(_safe_float(face_result.get("confidence")), 4),
        },
        "behavior": {
            "behavior_score": round(_safe_float(behavior_score, 0), 1),
            "action_label": action_result.get("action_label"),
            "matched": bool(action_result.get("matched")) if action_result else result.result == "pass",
        },
        "police_semantic": {
            "enabled": bool(police_semantic.get("enabled")),
            "police_node_type": police_semantic.get("police_node_type"),
            "node_badge": police_semantic.get("node_badge"),
            "semantic_score": _safe_int(police_semantic.get("semantic_score")),
            "pass_threshold": _safe_int(police_semantic.get("pass_threshold"), 50),
            "hit_count": _safe_int(police_semantic.get("hit_count")),
            "total_points": _safe_int(police_semantic.get("total_points")),
            "hit_points": police_semantic.get("hit_points") if isinstance(police_semantic.get("hit_points"), list) else [],
            "missed_points": police_semantic.get("missed_points") if isinstance(police_semantic.get("missed_points"), list) else [],
            "llm_rescued_points": police_semantic.get("llm_rescued_points") if isinstance(police_semantic.get("llm_rescued_points"), list) else [],
            "feedback": police_semantic.get("feedback"),
        },
        "degradation": degradation,
        "tool_evidence": [
            {"type": "transcript", "available": bool(transcript)},
            {"type": "gesture_result", "available": bool(gesture_result)},
            {"type": "identity_result", "available": bool(identity_result)},
            {"type": "focus_result", "available": bool(focus_result)},
            {"type": "face_result", "available": bool(face_result)},
            {"type": "action_result", "available": bool(action_result)},
            {"type": "police_semantic", "available": bool(police_semantic.get("enabled"))},
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# P0: 语音通道模糊匹配辅助函数
# ─────────────────────────────────────────────────────────────────────────────

_ASSESSMENT_KEYWORD_SYNONYMS: dict[str, list[str]] = {
    "表明身份": ["我是警察", "我是民警", "我是公安", "警察", "民警"],
    "民警": ["警察", "公安人员", "警官", "执法人员"],
    "执法记录": ["记录仪", "录像", "全程记录", "录音录像"],
    "告知权利": ["有权", "权利", "沉默权", "律师", "申辩"],
    "安全距离": ["保持距离", "退后", "站远一点", "别靠近"],
    "安抚": ["冷静", "别激动", "别着急", "放松", "慢慢说", "不要紧张"],
    "冷静": ["别激动", "别着急", "不要紧张", "稳定情绪"],
    "询问": ["问一下", "了解一下", "请问", "麻烦告诉", "说一下"],
    "调查": ["了解情况", "核实", "调查清楚", "查明"],
    "核实": ["确认", "验证", "查证", "核对"],
    "配合": ["协助", "帮个忙", "配合一下", "请配合"],
    "隔离": ["分开", "分离", "拉开", "各自", "两边"],
    "控制": ["制服", "按住", "控制住", "别动"],
    "120": ["急救", "救护车", "送医", "医院"],
    "依法": ["根据法律", "按照规定", "法律规定", "合法"],
    "什么时候": ["几点", "多久了", "多长时间", "时间"],
    "在哪里": ["什么地方", "地址", "位置", "哪里", "具体地点"],
}

_logger = logging.getLogger(__name__)


def _extract_point_keywords(point: dict[str, Any]) -> list[str]:
    """从考察点定义中提取关键词列表（用于模糊匹配兜底）"""
    rule = point.get("rule") if isinstance(point.get("rule"), dict) else {}
    keywords = rule.get("keywords") if isinstance(rule.get("keywords"), list) else []
    if keywords:
        return [str(k).strip() for k in keywords if str(k).strip()]
    # 从 label/content 中提取核心词作为备选
    label = str(point.get("label") or point.get("content") or "").strip()
    if not label:
        return []
    # 简单分词：提取2字以上的中文片段
    import re
    tokens = re.findall(r'[\u4e00-\u9fff]{2,6}', label)
    return tokens[:5] if tokens else []


def _fuzzy_keyword_check(keywords: list[str], transcript: str, threshold: float = 0.72) -> list[str]:
    """对关键词列表执行模糊匹配，返回命中的关键词"""
    if not keywords or not transcript:
        return []
    lowered_text = transcript.lower()
    hits: list[str] = []
    for kw in keywords:
        lowered_kw = kw.lower()
        # 1. 精确包含
        if lowered_kw in lowered_text:
            hits.append(kw)
            continue
        # 2. 同义词匹配
        synonyms = _ASSESSMENT_KEYWORD_SYNONYMS.get(kw, [])
        if any(syn.lower() in lowered_text for syn in synonyms):
            hits.append(kw)
            continue
        # 3. 滑动窗口模糊匹配
        if len(kw) >= 2:
            kw_len = len(kw)
            window_size = kw_len + max(2, kw_len // 2)
            matched = False
            for i in range(max(1, len(lowered_text) - window_size + 1)):
                window = lowered_text[i:i + window_size]
                ratio = SequenceMatcher(None, lowered_kw, window).ratio()
                if ratio >= threshold:
                    hits.append(kw)
                    matched = True
                    break
            if matched:
                continue
    return hits


def _evaluate_point_status(point: dict[str, Any], evidence: dict[str, Any], result: models.VideoNodeResult) -> tuple[str, list[str], str]:
    rule = point.get("rule") if isinstance(point.get("rule"), dict) else {}
    channel = str(rule.get("channel") or "result")
    mode = str(rule.get("mode") or "result_pass")
    failure_reasons = _dedupe_strings((_load_json(result.answer_data, {}) or {}).get("__validation_errors", []) if isinstance(_load_json(result.answer_data, {}), dict) else [], limit=6)

    if channel == "result":
        if result.result == "pass":
            return "hit", ["节点结果通过"], "节点在限定条件下完成。"
        if result.result in {"skip", "timeout"}:
            return "partial", [f"节点结果：{result.result}"], "节点未完全完成，流程中断或超时。"
        return "missed", [f"节点结果：{result.result}"], "节点未通过。"

    if channel == "speech":
        speech = evidence.get("speech") or {}
        hits = speech.get("keyword_hits") or []
        transcript = str(speech.get("transcript") or "").strip()
        if hits:
            return "hit", [f"关键词命中：{'、'.join(_dedupe_strings(hits, limit=3))}"], "关键话术已命中。"
        # P0 增强：当精确匹配未命中时，尝试模糊/同义词匹配
        if transcript:
            required_keywords = _extract_point_keywords(point)
            if required_keywords:
                fuzzy_hits = _fuzzy_keyword_check(required_keywords, transcript)
                if fuzzy_hits:
                    return "hit", [f"语义命中：{'、'.join(_dedupe_strings(fuzzy_hits, limit=3))}"], "关键话术通过语义匹配命中。"
            return "partial", [f"已有转写：{transcript[:30]}"], "已有表达，但未充分命中关键词。"
        return "missed", ["缺少有效转写"], "未采集到有效语言证据。"

    if channel == "gesture":
        gesture = evidence.get("gesture") or {}
        if gesture.get("matched") and _safe_float(gesture.get("confidence")) >= 0.45:
            return "hit", [f"动作匹配，置信度 {round(_safe_float(gesture.get('confidence')) * 100)}%"], "动作识别通过。"
        if _safe_float(gesture.get("confidence")) > 0:
            return "partial", [f"检测到动作但未达阈值，置信度 {round(_safe_float(gesture.get('confidence')) * 100)}%"], "动作有响应，但稳定性不足。"
        return "missed", ["未命中要求手势"], "动作证据不足。"

    if channel == "identity":
        identity = evidence.get("identity") or {}
        if identity.get("verified") and identity.get("single_face") and identity.get("live_ready"):
            return "hit", ["单人入镜且活体校验通过"], "身份在场状态稳定。"
        if identity.get("single_face") or identity.get("live_ready"):
            return "partial", ["身份在场部分达标"], "已检测到部分身份/活体条件。"
        return "missed", ["身份校验未通过"], "身份或活体状态不稳定。"

    if channel == "prop":
        prop = evidence.get("prop") or {}
        if prop.get("ready"):
            return "hit", [f"已完成 {prop.get('label') or '道具'} 操作"], "道具/证件操作完成。"
        return "missed", ["未检测到道具操作"], "缺少道具或证件操作证据。"

    if channel == "decision":
        if "judge_incorrect" not in failure_reasons and "choice_incorrect" not in failure_reasons and result.result == "pass":
            return "hit", ["节点结果正确"], "判断/选择结果正确。"
        return "missed", [_reason_label(item) for item in failure_reasons if item in {"judge_incorrect", "choice_incorrect"}] or ["节点判断错误"], "判断/选择未通过。"

    if channel == "focus":
        focus = evidence.get("focus") or {}
        severe = _safe_int(focus.get("severe_violation_count"))
        minor = _safe_int(focus.get("minor_violation_count"))
        score = _safe_float(focus.get("focus_score"), 0)
        if severe <= 0 and minor <= 0 and score >= 80:
            return "hit", [f"专注度 {round(score)} 分"], "训练过程专注稳定。"
        if severe <= 0 and score >= 60:
            return "partial", [f"专注度 {round(score)} 分"], "存在轻微专注度波动。"
        return "missed", [_reason_label(item) for item in focus.get("violation_types") or []] or [f"专注度 {round(score)} 分"], "专注度不足或存在明显中断。"

    if channel == "face":
        face = evidence.get("face") or {}
        score = _safe_float(face.get("expression_score"), 0)
        if score >= 80:
            return "hit", [f"表情状态 {round(score)} 分"], "面部状态自然稳定。"
        if score >= 60:
            return "partial", [f"表情状态 {round(score)} 分"], "面部状态基本可用，但稳定性一般。"
        return "missed", [f"表情状态 {round(score)} 分"], "面部状态较弱。"

    if channel == "behavior":
        behavior = evidence.get("behavior") or {}
        score = _safe_float(behavior.get("behavior_score"), 0)
        if score >= 80:
            return "hit", [f"行为响应 {round(score)} 分"], "动作、话术和节点衔接较连贯。"
        if score >= 60:
            return "partial", [f"行为响应 {round(score)} 分"], "行为响应基本连贯，但仍有停顿或重复。"
        return "missed", [f"行为响应 {round(score)} 分"], "行为响应连贯性较弱。"

    if channel == "semantic":
        semantic = evidence.get("police_semantic") or {}
        score = _safe_int(semantic.get("semantic_score"))
        hit_points = semantic.get("hit_points") if isinstance(semantic.get("hit_points"), list) else []
        missed_points = semantic.get("missed_points") if isinstance(semantic.get("missed_points"), list) else []
        llm_rescued = semantic.get("llm_rescued_points") if isinstance(semantic.get("llm_rescued_points"), list) else []
        label = str(point.get("label") or point.get("content") or "").strip()
        if not semantic.get("enabled"):
            return "missed", ["未生成警情语义评分"], "缺少警情语义评分证据。"
        # 检查是否在直接命中列表
        if label and any(label == str(item.get("point") or "") for item in hit_points if isinstance(item, dict)):
            return "hit", [f"命中处置点：{label}"], "回答覆盖该警情处置要点。"
        # P0 增强：检查是否被 LLM 语义救回
        if label and any(label == str(item.get("point") or "") for item in llm_rescued if isinstance(item, dict)):
            reason = next((str(item.get("reason") or "") for item in llm_rescued if isinstance(item, dict) and str(item.get("point") or "") == label), "")
            return "hit", [f"语义覆盖：{label}" + (f"（{reason}）" if reason else "")], "回答通过语义分析覆盖该处置要点。"
        if label and any(label == str(item.get("point") or "") for item in missed_points if isinstance(item, dict)):
            return "missed", [f"漏项：{label}"], "回答未覆盖该警情处置要点。"
        if score >= _safe_int(semantic.get("pass_threshold"), 50):
            return "hit", [f"警情语义评分 {score} 分"], "回答覆盖主要警情处置要求。"
        if score > 0:
            return "partial", [f"警情语义评分 {score} 分"], "回答覆盖了部分处置点，但仍有关键漏项。"
        return "missed", ["缺少有效警情处置回答"], "回答未形成可评估的警情处置方案。"

    return "missed", ["缺少判定规则"], "该考察点暂未配置有效规则。"


def build_runtime_assessment_snapshot(
    session: models.VideoTrainingSession,
    node: models.VideoNode,
    result: models.VideoNodeResult,
) -> dict[str, Any]:
    requirement_rows = _sanitize_report_points(resolve_node_assessment_points(node))
    evidence = build_node_multimodal_evidence(session, node, result)
    runtime_points: list[dict[str, Any]] = []
    for point in requirement_rows:
        status, evidence_lines, feedback = _evaluate_point_status(point, evidence, result)
        runtime_points.append(
            {
                "id": point["id"],
                "label": point["label"],
                "content": point.get("content") or point["label"],
                "stage_name": point.get("stage_name") or node.title or f"节点{node.node_index + 1}",
                "category": point.get("category") or point.get("dimension") or "procedure_execution",
                "dimension": point.get("dimension") or point.get("category") or "procedure_execution",
                "required": bool(point.get("required", True)),
                "weight": _safe_int(point.get("weight"), 1),
                "status": status,
                "evidence": evidence_lines,
                "feedback": feedback,
                "source": "runtime_video",
            }
        )

    merged_points = merge_assessment_point_results(runtime_points, [], requirement_rows)
    return {
        "assessment_points": merged_points,
        "requirement_rows": requirement_rows,
        "evidence": evidence,
    }


def _point_score(status: str, weight: int) -> float:
    if status == "hit":
        return float(weight)
    if status == "partial":
        return float(weight) * 0.5
    return 0.0


def _summarize_dimension_scores(node_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, float]] = {
        key: {"score": 0.0, "full_score": 0.0}
        for key in VIDEO_DIMENSION_LABELS
    }
    for payload in node_payloads:
        for point in payload.get("assessment_points") or []:
            if not isinstance(point, dict):
                continue
            dimension = str(point.get("dimension") or point.get("category") or "procedure_execution")
            if dimension not in summary:
                continue
            weight = max(_safe_int(point.get("weight"), 1), 1)
            summary[dimension]["full_score"] += weight
            summary[dimension]["score"] += _point_score(str(point.get("status") or "missed"), weight)

    dimension_scores: list[dict[str, Any]] = []
    for key, item in summary.items():
        if item["full_score"] <= 0:
            continue
        percentage = round(item["score"] / item["full_score"] * 100) if item["full_score"] else 0
        dimension_scores.append(
            {
                "key": key,
                "label": VIDEO_DIMENSION_LABELS[key],
                "score": round(item["score"], 1),
                "full_score": round(item["full_score"], 1),
                "percentage": percentage,
            }
        )

    return sorted(dimension_scores, key=lambda item: item["percentage"])


def build_video_evaluation_report(
    session: models.VideoTrainingSession,
    node_results: list[models.VideoNodeResult],
    video: Optional[models.TrainingVideo],
) -> dict[str, Any]:
    full_score = max(_safe_int(session.full_score, 100), 1)
    total_score = max(_safe_int(session.total_score, 0), 0)
    percentage = round(total_score / full_score * 100) if full_score else 0
    grade = _legacy_grade(percentage)
    ability_grade = compute_grade_level(percentage)

    node_payloads: list[dict[str, Any]] = []
    node_summaries: list[dict[str, Any]] = []
    failure_reason_summary: dict[str, int] = {}
    violation_summary: dict[str, int] = {}
    all_assessment_points: list[dict[str, Any]] = []

    violations = _load_json(session.violation_log, [])
    for item in violations:
        if not isinstance(item, dict):
            continue
        key = str(item.get("type") or "unknown")
        violation_summary[key] = violation_summary.get(key, 0) + 1

    for result in node_results:
        node = result.node
        if not node:
            continue
        payload = _load_json(result.assessment_payload, None)
        if not isinstance(payload, dict):
            payload = build_runtime_assessment_snapshot(session, node, result)
        evidence = _sanitize_report_evidence(payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {})
        points = _sanitize_report_points(payload.get("assessment_points") if isinstance(payload.get("assessment_points"), list) else [])
        node_payloads.append({"assessment_points": points, "evidence": evidence})
        all_assessment_points.extend(points)

        failure_reasons = _dedupe_strings((_load_json(result.answer_data, {}) or {}).get("__validation_errors", []) if isinstance(_load_json(result.answer_data, {}), dict) else [], limit=10)
        for reason in failure_reasons:
            failure_reason_summary[reason] = failure_reason_summary.get(reason, 0) + 1

        node_summaries.append(
            {
                "node_result_id": result.id,
                "node_index": result.node_index,
                "node_id": result.node_id,
                "node_title": node.title or f"节点{result.node_index + 1}",
                "node_type": node.node_type,
                "result": result.result,
                "retry_count": _safe_int(result.retry_count),
                "time_used": _safe_int(result.time_used),
                "score_earned": _safe_int(result.score_earned),
                "score_deducted": _safe_int(result.score_deducted),
                "speech_transcript": result.speech_transcript,
                "failure_reasons": failure_reasons,
                "assessment_points": points,
                "evidence": evidence,
                "police_semantic": evidence.get("police_semantic") if isinstance(evidence, dict) else None,
                "manual_review": None,
            }
        )

    dimension_scores = _summarize_dimension_scores(node_payloads)
    weakness_summary = [
        f"{item['label']}偏弱（{item['percentage']}%），建议针对相关节点复训。"
        for item in dimension_scores[:3]
        if item["percentage"] < 85
    ][:3]
    police_semantics = [
        item.get("police_semantic")
        for item in node_summaries
        if isinstance(item.get("police_semantic"), dict) and item["police_semantic"].get("enabled")
    ]
    police_hit_points: list[str] = []
    police_missed_points: list[str] = []
    for semantic in police_semantics:
        police_hit_points.extend([text for item in semantic.get("hit_points") or [] if (text := _semantic_point_text(item))])
        police_missed_points.extend([text for item in semantic.get("missed_points") or [] if (text := _semantic_point_text(item))])
    police_hit_points = _dedupe_strings(police_hit_points, limit=12)
    police_missed_points = _dedupe_strings(police_missed_points, limit=12)
    semantic_average = round(
        sum(_safe_int(item.get("semantic_score")) for item in police_semantics) / max(len(police_semantics), 1),
        1,
    ) if police_semantics else 0
    ability_profile = {
        "enabled": bool(police_semantics),
        "semantic_average": semantic_average,
        "standard_point_coverage": round(
            len(police_hit_points) / max(len(police_hit_points) + len(police_missed_points), 1) * 100
        ) if police_semantics else 0,
        "strengths": police_hit_points[:5],
        "risks": police_missed_points[:5],
        "next_training": [
            f"围绕“{item}”做一次针对性复训"
            for item in police_missed_points[:3]
        ] or weakness_summary[:3],
    }

    pass_count = sum(1 for item in node_results if item.result == "pass")
    skip_count = sum(1 for item in node_results if item.result in {"skip", "timeout"})
    fail_count = sum(1 for item in node_results if item.result == "fail")
    total_nodes = len(node_summaries)
    major_reasons = [
        _reason_label(key)
        for key, _ in sorted(failure_reason_summary.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    strongest_dimension = max(dimension_scores, key=lambda item: item["percentage"], default=None)
    weakest_dimension = min(dimension_scores, key=lambda item: item["percentage"], default=None)
    overall_comment = (
        f"本次视频实训得分率 {percentage}%，{pass_count}/{total_nodes or len(node_results)} 个节点通过。"
        f"{'主要失分集中在' + '、'.join(major_reasons) + '。' if major_reasons else '关键节点完成情况较稳定。'}"
        f"{'建议优先复盘' + weakest_dimension['label'] + '相关节点。' if weakest_dimension and weakest_dimension['percentage'] < 85 else '后续可继续保持规范流程和稳定表达。'}"
    )
    ability_evaluation = {
        "grade": ability_grade,
        "strongest_dimension": strongest_dimension,
        "weakest_dimension": weakest_dimension,
        "comment": (
            f"优势能力：{strongest_dimension['label']}（{strongest_dimension['percentage']}%）。"
            if strongest_dimension
            else "暂无足够节点形成优势能力画像。"
        ),
        "risk": (
            f"待提升能力：{weakest_dimension['label']}（{weakest_dimension['percentage']}%）。"
            if weakest_dimension
            else "暂无明显能力短板。"
        ),
    }
    return {
        "session_id": session.id,
        "video_id": session.video_id,
        "video_title": video.title if video else "",
        "mode": session.mode,
        "evaluation_status": "completed",
        "report_ready": True,
        "total_score": total_score,
        "full_score": full_score,
        "percentage": percentage,
        "grade": grade,
        "pass_count": pass_count,
        "skip_count": skip_count,
        "fail_count": fail_count,
        "total_nodes": total_nodes,
        "total_deducted": sum(_safe_int(item.score_deducted) for item in node_results),
        "violation_count": sum(violation_summary.values()),
        "violation_summary": violation_summary,
        "failure_reason_summary": failure_reason_summary,
        "overall_comment": overall_comment,
        "ability_evaluation": ability_evaluation,
        "dimension_scores": dimension_scores,
        "weakness_summary": weakness_summary,
        "ability_profile": ability_profile,
        "assessment_point_results": all_assessment_points,
        "node_summaries": node_summaries,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "evaluation_meta": {
            "scoring_version": "video_assessment_v2",
            "compatible_version": "adaptive_v1",
            "report_header": {
                "video_title": video.title if video else "",
                "finished_at": session.finished_at.isoformat() if session.finished_at else None,
                "grade_level": grade,
                "ability_grade": ability_grade,
                "total_score": total_score,
                "full_score": full_score,
            },
            "ability_grade": ability_grade,
            "ability_profile": ability_profile,
        },
        # 兼容 StudentEvaluation.vue 的字段格式
        "scores": [
            {
                "dimension": item["label"],
                "score": item["score"],
                "full_score": item["full_score"],
                "reason": f"通过视频实训节点考核，得分率 {item['percentage']}%",
                "group": "common",
            }
            for item in dimension_scores
        ],
        "improvements": weakness_summary,
        "strengths": ability_profile.get("strengths", [])[:3],
        "suggestions": ability_profile.get("next_training", [])[:3],
    }
