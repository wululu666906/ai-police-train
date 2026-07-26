"""
瑙嗛瀹炶妯″潡 - 绗簩闃舵璺敱
Session 绠＄悊銆佽妭鐐瑰垽瀹氥€佽闊冲叧閿瘝鍖归厤銆佽瘎浼版姤鍛?
"""
import json
import logging
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

import database
import models
from routers.auth import get_current_user
from services.video_assessment_service import (
    build_node_multimodal_evidence,
    build_runtime_assessment_snapshot,
    build_video_evaluation_report,
)

router = APIRouter(prefix="/video-training", tags=["VideoTraining"])


# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
# 杈呭姪鍑芥暟
# 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

def _load_json(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


DIMENSION_LABELS = {
    "body_action": "肢体动作规范",
    "verbal_communication": "口头沟通规范",
    "procedure_execution": "流程执行完整度",
    "prop_operation": "虚拟道具操作规范",
    "professional_safety": "执法专业与安全处置",
}


def _mode_policy(mode: str) -> dict:
    is_exam = mode == "exam"
    return {
        "name": "exam" if is_exam else "practice",
        "label": "考核模式" if is_exam else "练习模式",
        "retry_penalty_scale": 1.0 if is_exam else 0.5,
        "skip_penalty_scale": 1.0 if is_exam else 0.6,
        "gesture_confidence_scale": 1.0 if is_exam else 0.85,
        "gesture_hold_relief": 0 if is_exam else 2,
        "speech_min_length_relief": 0 if is_exam else 6,
        "allow_partial_channel_pass": not is_exam,
    }


def _scaled_penalty(raw_penalty: int, scale: float, max_score: int) -> int:
    penalty = max(int(round(max(raw_penalty, 0) * scale)), 0)
    return min(penalty, max(max_score, 0))


def _calc_full_score(nodes: list[models.VideoNode]) -> int:
    return sum(n.score_weight for n in nodes) if nodes else 100


def _serialize_session(session: models.VideoTrainingSession) -> dict:
    node_records = _load_json(session.node_records, [])
    violation_log = _load_json(session.violation_log, [])
    node_total = len(session.video.nodes) if session.video and session.video.nodes else 0
    return {
        "id": session.id,
        "user_id": session.user_id,
        "video_id": session.video_id,
        "node_total": node_total,
        "mode": session.mode,
        "status": session.status,
        "current_node_index": session.current_node_index,
        "total_score": session.total_score,
        "full_score": session.full_score,
        "evaluation_status": session.evaluation_status or "pending",
        "report_ready": bool(session.evaluation_result),
        "evaluation_error": session.evaluation_error,
        "node_records": node_records,
        "violation_log": violation_log,
        "violation_count": len(violation_log),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "evaluation_started_at": session.evaluation_started_at.isoformat() if session.evaluation_started_at else None,
        "evaluation_completed_at": session.evaluation_completed_at.isoformat() if session.evaluation_completed_at else None,
    }


def _serialize_node_result(r: models.VideoNodeResult) -> dict:
    answer_data = _load_json(r.answer_data, None)
    assessment_payload = _load_json(r.assessment_payload, None)
    evidence_payload = _load_json(r.evidence_payload, None)
    return {
        "id": r.id,
        "session_id": r.session_id,
        "node_id": r.node_id,
        "node_index": r.node_index,
        "result": r.result,
        "retry_count": r.retry_count,
        "time_used": r.time_used,
        "score_earned": r.score_earned,
        "score_deducted": r.score_deducted,
        "answer_data": answer_data,
        "failure_reasons": answer_data.get("__validation_errors", []) if isinstance(answer_data, dict) else [],
        "assessment_points": assessment_payload.get("assessment_points", []) if isinstance(assessment_payload, dict) else [],
        "evidence": evidence_payload or (assessment_payload.get("evidence") if isinstance(assessment_payload, dict) else {}),
        "manual_review": _serialize_manual_review(r),
        "speech_transcript": r.speech_transcript,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _get_accessible_session(
    db: Session,
    session_id: int,
    current_user: models.User,
    *,
    allow_admin: bool = False,
) -> models.VideoTrainingSession:
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    if session.user_id != current_user.id and not (allow_admin and current_user.role == "admin"):
        raise HTTPException(status_code=403, detail="无权访问该训练记录")
    return session


def _match_keywords(transcript: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = transcript.lower()
    return any(kw.lower() in text for kw in keywords)


def _load_node_prompt_content(node: models.VideoNode) -> dict:
    return _load_json(node.prompt_content, {})


def _load_node_config(node: models.VideoNode) -> dict:
    return _load_json(node.node_config, {})


def _parse_choice_options(node: models.VideoNode) -> list:
    raw = _load_json(node.choice_options, [])
    return raw if isinstance(raw, list) else []


def _normalize_option_label(option: object, index: int) -> str:
    if isinstance(option, str):
        stripped = option.strip()
        if stripped and stripped[0].isalpha():
            return stripped[0].upper()
        return chr(65 + index)
    if isinstance(option, dict):
        label = str(option.get("label") or option.get("value") or "").strip()
        if label:
            return label[0].upper() if len(label) == 1 else label.upper()
    return chr(65 + index)


def _normalize_option_text(option: object) -> str:
    if isinstance(option, str):
        return option.strip()
    if isinstance(option, dict):
        for key in ("text", "content", "description", "label", "value"):
            value = str(option.get(key) or "").strip()
            if value:
                return value
    return ""


def _resolve_judge_boolean_answer(node: models.VideoNode, config: dict) -> bool | None:
    raw = config.get("correct_answer")
    if isinstance(raw, bool):
        return raw
    label = str(node.correct_answer or raw or "").strip()
    if label in {"对", "正确", "true", "True"}:
        return True
    if label in {"错", "错误", "false", "False"}:
        return False
    return None


def _is_choice_style_judge_node(node: models.VideoNode, config: dict) -> bool:
    options = _parse_choice_options(node)
    if len(options) < 3:
        return False
    if isinstance(config.get("correct_answer"), bool):
        return False
    label = str(node.correct_answer or config.get("correct_answer") or "").strip()
    if len(label) == 1 and label.isalpha():
        return True
    return False


def _resolve_correct_choice_index(node: models.VideoNode, config: dict) -> int | None:
    if isinstance(config.get("correct_index"), int):
        return config["correct_index"]
    label = str(node.correct_answer or config.get("correct_answer") or "").strip().upper()
    if not label:
        return None
    if len(label) == 1 and label.isalpha():
        return ord(label) - ord("A")
    options = _parse_choice_options(node)
    for index, option in enumerate(options):
        option_label = _normalize_option_label(option, index)
        option_text = _normalize_option_text(option).upper()
        if option_label == label or option_text == label:
            return index
    return None


def _normalize_speech_keywords(raw_keywords) -> list[str]:
    if not isinstance(raw_keywords, list):
        return []
    return [str(item).strip() for item in raw_keywords if str(item).strip()]


# ─────────────────────────────────────────────────────────────────────────────
# P0: 话术关键词同义词表 + 模糊匹配
# ─────────────────────────────────────────────────────────────────────────────

KEYWORD_SYNONYMS: dict[str, list[str]] = {
    # 身份表明
    "表明身份": ["我是警察", "我是民警", "我是公安", "警察", "民警", "公安机关"],
    "民警": ["警察", "公安人员", "警官", "执法人员"],
    "警察": ["民警", "公安人员", "警官", "执法人员"],
    # 执法记录
    "执法记录": ["记录仪", "录像", "全程记录", "录音录像"],
    # 告知权利
    "告知权利": ["有权", "权利", "沉默权", "律师", "申辩", "陈述"],
    "律师": ["辩护人", "法律援助", "请律师"],
    # 安全相关
    "安全距离": ["保持距离", "退后", "站远一点", "别靠近"],
    "注意安全": ["小心", "当心", "注意", "保护好自己"],
    # 安抚情绪
    "安抚": ["冷静", "别激动", "别着急", "放松", "慢慢说", "不要紧张"],
    "冷静": ["别激动", "别着急", "不要紧张", "稳定情绪", "深呼吸"],
    # 调查相关
    "询问": ["问一下", "了解一下", "请问", "麻烦告诉", "说一下"],
    "调查": ["了解情况", "核实", "调查清楚", "查明"],
    "核实": ["确认", "验证", "查证", "核对"],
    # 程序性
    "配合": ["协助", "帮个忙", "配合一下", "请配合"],
    "笔录": ["做个记录", "记录一下", "录口供", "制作笔录"],
    # 现场控制
    "隔离": ["分开", "分离", "拉开", "各自", "两边"],
    "控制": ["制服", "按住", "控制住", "别动"],
    # 救助
    "120": ["急救", "救护车", "送医", "医院"],
    "受伤": ["伤情", "流血", "疼", "伤"],
    # 法律
    "依法": ["根据法律", "按照规定", "法律规定", "合法"],
    "强制措施": ["拘留", "逮捕", "传唤", "约束"],
    # 报警/接警
    "报警": ["打110", "报案", "求助"],
    "什么时候": ["几点", "多久了", "多长时间", "时间"],
    "在哪里": ["什么地方", "地址", "位置", "哪里", "具体地点"],
}


def _fuzzy_keyword_match(keyword: str, text: str, threshold: float = 0.72) -> tuple[bool, str]:
    """模糊匹配：先精确包含 -> 同义词 -> 滑动窗口模糊比较。
    返回 (是否命中, 命中方式描述)"""
    lowered_kw = keyword.lower()
    lowered_text = text.lower()

    # 1. 精确包含（原有逻辑）
    if lowered_kw in lowered_text:
        return True, "exact"

    # 2. 同义词匹配
    synonyms = KEYWORD_SYNONYMS.get(keyword, [])
    for syn in synonyms:
        if syn.lower() in lowered_text:
            return True, f"synonym:{syn}"

    # 3. 滑动窗口模糊匹配（适用于2字以上的关键词）
    if len(keyword) >= 2:
        kw_len = len(keyword)
        window_size = kw_len + max(2, kw_len // 2)  # 允许比关键词略长的窗口
        for i in range(max(1, len(lowered_text) - window_size + 1)):
            window = lowered_text[i:i + window_size]
            ratio = SequenceMatcher(None, lowered_kw, window).ratio()
            if ratio >= threshold:
                return True, f"fuzzy:{window.strip()}({ratio:.2f})"

    return False, ""


def _evaluate_speech_rule(
    transcript: str,
    keywords: list[str],
    speech_rule: dict,
    speech_required: bool,
    mode: str = "practice",
) -> dict:
    normalized_keywords = _normalize_speech_keywords(keywords)
    text = str(transcript or "").strip()
    lowered = text.lower()
    policy = _mode_policy(mode)

    # 使用增强匹配：精确 + 同义词 + 模糊
    hits: list[str] = []
    hit_details: list[dict] = []
    for kw in normalized_keywords:
        matched, match_type = _fuzzy_keyword_match(kw, text)
        if matched:
            hits.append(kw)
            hit_details.append({"keyword": kw, "match_type": match_type})

    min_length = max(int(speech_rule.get("min_length") or 0) - int(policy["speech_min_length_relief"]), 0)
    match_mode = str(speech_rule.get("match_mode") or "any")
    min_count = max(int(speech_rule.get("min_count") or 1), 1)

    if speech_required and min_length and len(text) < min_length:
        return {
            "passed": False,
            "reason": "keyword_mismatch",
            "hits": hits,
            "hit_count": len(hits),
            "hit_details": hit_details,
        }

    if not normalized_keywords:
        return {
            "passed": not speech_required or bool(text) or min_length == 0,
            "reason": None if (not speech_required or bool(text) or min_length == 0) else "keyword_mismatch",
            "hits": hits,
            "hit_count": len(hits),
            "hit_details": hit_details,
        }

    if match_mode == "all":
        passed = len(hits) == len(normalized_keywords)
    elif match_mode == "min_count":
        passed = len(hits) >= min(min_count, len(normalized_keywords))
    else:
        passed = len(hits) >= 1

    return {
        "passed": passed,
        "reason": None if passed else "keyword_mismatch",
        "hits": hits,
        "hit_count": len(hits),
        "hit_details": hit_details,
    }


def _evaluate_gesture_rule(node: models.VideoNode, answer_data: dict, mode: str = "practice") -> dict:
    prompt_content = _load_node_prompt_content(node)
    gesture_rule = prompt_content.get("gesture_config") if isinstance(prompt_content, dict) else {}
    gesture_rule = gesture_rule if isinstance(gesture_rule, dict) else {}

    # Browser-side gesture recognition was removed from the training client.
    # Existing videos may retain required_gesture, but that legacy field must
    # not turn a normal submit into a failure unless a future client explicitly
    # opts in through an enabled gesture_config.
    if not node.required_gesture or gesture_rule.get("enabled") is not True:
        return {"required": False, "passed": True, "reason": None}

    policy = _mode_policy(mode)
    min_confidence = max(min(float(gesture_rule.get("min_confidence") or 0) * float(policy["gesture_confidence_scale"]), 1), 0)
    hold_frames = max(int(gesture_rule.get("hold_frames") or 1) - int(policy["gesture_hold_relief"]), 1)

    gesture_result = answer_data.get("gesture_result")
    if not isinstance(gesture_result, dict):
        return {"required": True, "passed": False, "reason": "gesture_mismatch"}

    gesture_ok = (
        gesture_result.get("required_gesture") == node.required_gesture
        and bool(gesture_result.get("matched")) is True
        and float(gesture_result.get("confidence") or 0) >= min_confidence
        and int(gesture_result.get("streak") or 0) >= hold_frames
    )
    return {"required": True, "passed": gesture_ok, "reason": None if gesture_ok else "gesture_mismatch"}


def _evaluate_identity_rule(node: models.VideoNode, answer_data: dict) -> dict:
    prompt_content = _load_node_prompt_content(node)
    identity_rule = prompt_content.get("identity_config") if isinstance(prompt_content, dict) else {}
    identity_rule = identity_rule if isinstance(identity_rule, dict) else {}
    identity_mode = str(identity_rule.get("mode") or "presence")
    require_live_motion = bool(identity_rule.get("require_live_motion", True))
    require_single_face = bool(identity_rule.get("require_single_face", True))
    backend_cv = bool(identity_rule.get("backend_cv"))

    identity_result = answer_data.get("identity_result")
    if not isinstance(identity_result, dict):
        return {"required": False, "passed": True, "reason": None}

    if identity_mode == "reference_face" or backend_cv:
        matched = bool(identity_result.get("matched")) is True
        return {"required": True, "passed": matched, "reason": None if matched else "identity_mismatch"}

    if not require_live_motion and not require_single_face:
        return {"required": False, "passed": True, "reason": None}

    verified = bool(identity_result.get("verified")) is True
    single_face = bool(identity_result.get("single_face")) is True
    live_ready = bool(identity_result.get("live_ready")) is True

    checks = [verified]
    if require_single_face:
        checks.append(single_face)
    if require_live_motion:
        checks.append(live_ready)

    passed = all(checks)
    return {"required": True, "passed": passed, "reason": None if passed else "identity_mismatch"}


def _normalize_answer_data(answer_data) -> dict:
    return answer_data if isinstance(answer_data, dict) else {}


POLICE_SEMANTIC_ALIASES = {
    "risk": ["风险", "危险", "隐患", "升级", "冲突", "失控"],
    "weapon": ["危险物品", "酒瓶", "刀", "棍", "器械", "凶器", "物品", "移除", "控制物品"],
    "separate": ["隔离", "分开", "分离", "拉开", "保持距离", "安全距离"],
    "support": ["支援", "增援", "呼叫", "请求", "报告", "同伴"],
    "calm": ["安抚", "冷静", "稳定情绪", "劝导", "沟通", "克制"],
    "identity": ["表明身份", "民警", "警察", "告知", "执法记录", "记录"],
    "procedure": ["先", "顺序", "流程", "控制", "稳控", "调查", "核实", "处置"],
    "law": ["依法", "法律", "规定", "告知", "强制措施", "违法", "合法"],
    "safety": ["安全", "站位", "退路", "警戒", "保护", "群众", "现场秩序"],
    "investigate": ["询问", "调查", "取证", "证据", "核实", "目击", "分别询问"],
    "medical": ["救助", "伤情", "医疗", "120", "急救", "送医", "生命"],
    "minor": ["未成年人", "学生", "校方", "监护人", "校园", "隐私"],
}


def _is_police_semantic_node(node_config: dict) -> bool:
    return bool(node_config.get("police_node_type") and isinstance(node_config.get("standard_points"), list))


def _semantic_aliases_for_point(point: str) -> list[str]:
    text = str(point or "").strip()
    aliases: list[str] = []
    for keyword, values in POLICE_SEMANTIC_ALIASES.items():
        if any(value in text for value in values) or keyword in text.lower():
            aliases.extend(values)
    for token in ["风险", "危险", "隔离", "支援", "安抚", "依法", "安全", "询问", "证据", "救助", "告知", "记录", "秩序"]:
        if token in text:
            aliases.append(token)
    aliases.append(text)
    return _dedupe_local_strings([item for item in aliases if len(str(item).strip()) >= 2], limit=12)


def _dedupe_local_strings(values: list[str], limit: int = 10) -> list[str]:
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


def _evaluate_police_semantic_answer(
    node: models.VideoNode,
    answer_data: dict,
    speech_transcript: str,
) -> dict:
    node_config = _load_node_config(node)
    if not _is_police_semantic_node(node_config):
        return {"enabled": False}

    prompt_content = _load_node_prompt_content(node)
    standard_points = [
        str(item).strip()
        for item in (node_config.get("standard_points") or [])
        if str(item).strip()
    ]
    answer_text = " ".join(
        str(item or "").strip()
        for item in [
            speech_transcript,
            answer_data.get("answer_text"),
            answer_data.get("manual_text"),
            answer_data.get("text"),
        ]
        if str(item or "").strip()
    ).strip()

    hit_points: list[dict] = []
    missed_points: list[dict] = []
    for point in standard_points:
        aliases = _semantic_aliases_for_point(point)
        hits = [alias for alias in aliases if alias and alias in answer_text]
        item = {
            "point": point,
            "aliases": aliases,
            "hits": _dedupe_local_strings(hits, limit=5),
        }
        if hits:
            hit_points.append(item)
        else:
            missed_points.append(item)

    # ─── P0: LLM 语义兜底判定 ───
    # 对别名匹配未命中的要点，使用 LLM 进行语义级别的覆盖判定
    llm_rescued_points: list[dict] = []
    if missed_points and answer_text and len(answer_text) >= 6:
        llm_rescued_points = _llm_semantic_rescue(
            answer_text=answer_text,
            missed_points=missed_points,
            question=prompt_content.get("police_question") or prompt_content.get("instruction") or "",
        )
        # 把 LLM 判定为覆盖的点从 missed 移到 hit
        rescued_set = {item["point"] for item in llm_rescued_points}
        new_missed = []
        for mp in missed_points:
            if mp["point"] in rescued_set:
                rescued_item = next((r for r in llm_rescued_points if r["point"] == mp["point"]), None)
                mp["hits"] = [f"(语义覆盖) {rescued_item.get('reason', '')}" if rescued_item else "(语义覆盖)"]
                mp["match_type"] = "llm_semantic"
                hit_points.append(mp)
            else:
                new_missed.append(mp)
        missed_points = new_missed

    total = max(len(standard_points), 1)
    hit_count = len(hit_points)
    base_score = round(hit_count / total * 100)
    safety_bonus = 0
    if any(alias in answer_text for alias in POLICE_SEMANTIC_ALIASES["law"]):
        safety_bonus += 5
    if any(alias in answer_text for alias in POLICE_SEMANTIC_ALIASES["safety"]):
        safety_bonus += 5
    semantic_score = min(100, base_score + safety_bonus)
    pass_threshold = int(node_config.get("semantic_pass_threshold") or 50)

    return {
        "enabled": True,
        "police_node_type": node_config.get("police_node_type"),
        "node_badge": prompt_content.get("node_badge"),
        "question": prompt_content.get("police_question") or prompt_content.get("instruction"),
        "answer_text": answer_text,
        "standard_points": standard_points,
        "hit_points": hit_points,
        "missed_points": missed_points,
        "llm_rescued_points": llm_rescued_points,
        "hit_count": hit_count,
        "total_points": total,
        "semantic_score": semantic_score,
        "pass_threshold": pass_threshold,
        "passed": bool(answer_text) and semantic_score >= pass_threshold,
        "feedback": (
            "回答覆盖了主要处置点。"
            if semantic_score >= pass_threshold
            else "回答未充分覆盖风险识别、处置顺序或依法安全要求。"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# P0: LLM 语义兜底 - 对别名匹配 miss 的点做 LLM 语义判定
# ─────────────────────────────────────────────────────────────────────────────

_LLM_SEMANTIC_RESCUE_PROMPT = """你是警务训练评估专家。请判断学员的回答是否在语义上覆盖了以下处置要点。
注意：学员可能用不同的措辞表达相同的意思，只要语义上实质性包含该要点的核心意图即可判定为覆盖。

警情问题：{question}

学员回答：
{answer_text}

待判定的处置要点：
{points_json}

请逐条判定，返回 JSON 数组，每条格式如下：
[{{"point": "要点原文", "covered": true或false, "reason": "简要理由(15字以内)"}}]

判定原则：
- 学员明确表达了该要点的核心动作或意图 → covered: true
- 学员只是模糊提及但未体现实质处置意图 → covered: false
- 宁严勿松：只有明确覆盖才判 true"""


logger = logging.getLogger(__name__)


def _llm_semantic_rescue(
    answer_text: str,
    missed_points: list[dict],
    question: str,
) -> list[dict]:
    """对别名匹配未命中的要点调用 LLM 做语义级覆盖判定。
    返回 LLM 判定为 covered 的要点列表。"""
    if not missed_points:
        return []

    # 限制单次判定数量（控制 token 消耗）
    points_to_check = missed_points[:8]
    points_json = json.dumps(
        [p["point"] for p in points_to_check],
        ensure_ascii=False,
    )

    prompt = _LLM_SEMANTIC_RESCUE_PROMPT.format(
        question=question or "(未提供具体问题)",
        answer_text=answer_text[:800],  # 截断过长回答
        points_json=points_json,
    )

    try:
        from services.llm_provider import create_json_chat_completion, extract_message_text, get_chat_model

        response = create_json_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=get_chat_model(),
            temperature=0.1,
            max_tokens=1000,
        )
        content = extract_message_text(response)
        if not content:
            return []

        payload = json.loads(content)
        # 支持两种返回格式：直接数组 或 {"results": [...]}
        if isinstance(payload, dict):
            payload = payload.get("results") or payload.get("items") or payload.get("points") or []
        if not isinstance(payload, list):
            return []

        rescued: list[dict] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("covered") is True:
                rescued.append({
                    "point": str(item.get("point") or "").strip(),
                    "reason": str(item.get("reason") or "").strip(),
                    "match_type": "llm_semantic",
                })
        return rescued

    except Exception as exc:
        logger.warning(f"LLM semantic rescue failed: {exc}")
        return []


def _grade_from_percentage(pct: int) -> str:
    if pct >= 90:
        return "优秀"
    if pct >= 70:
        return "合格"
    return "待重修"


def _extract_failure_reasons(result: models.VideoNodeResult) -> list[str]:
    answer_data = _load_json(result.answer_data, {})
    if isinstance(answer_data, dict):
        reasons = answer_data.get("__validation_errors", [])
        if isinstance(reasons, list):
            return [str(item) for item in reasons]
    return []


def _extract_manual_review(result: models.VideoNodeResult) -> Optional[dict]:
    answer_data = _load_json(result.answer_data, {})
    if isinstance(answer_data, dict):
        review_data = answer_data.get("__manual_review")
        if isinstance(review_data, dict):
            return review_data
    return None


def _manual_review_overridden(result: models.VideoNodeResult, review_data: Optional[dict] = None) -> bool:
    review = review_data or _extract_manual_review(result)
    if not isinstance(review, dict):
        return False
    original_result = review.get("original_result")
    original_score_earned = review.get("original_score_earned")
    original_score_deducted = review.get("original_score_deducted")
    return (
        original_result != result.result
        or int(original_score_earned or 0) != int(result.score_earned or 0)
        or int(original_score_deducted or 0) != int(result.score_deducted or 0)
    )


def _serialize_manual_review(result: models.VideoNodeResult) -> Optional[dict]:
    review = _extract_manual_review(result)
    if not isinstance(review, dict):
        return None
    payload = dict(review)
    payload["overridden"] = _manual_review_overridden(result, review)
    return payload


def _summarize_violation_log(session: models.VideoTrainingSession) -> dict:
    summary: dict[str, int] = {}
    for item in _load_json(session.violation_log, []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("type") or "unknown")
        summary[key] = summary.get(key, 0) + 1
    return summary


def _summarize_failure_reasons(node_results: list[models.VideoNodeResult]) -> dict:
    summary: dict[str, int] = {}
    for result in node_results:
        for reason in _extract_failure_reasons(result):
            summary[reason] = summary.get(reason, 0) + 1
    return summary


def _build_dimension_summary(
    session: models.VideoTrainingSession,
    node_results: list[models.VideoNodeResult],
) -> tuple[list[dict], list[str]]:
    summary = {
        key: {"label": label, "earned": 0.0, "max": 0.0}
        for key, label in DIMENSION_LABELS.items()
    }
    failure_summary = _summarize_failure_reasons(node_results)
    violation_summary = _summarize_violation_log(session)
    full_score = sum(max(int((result.node.score_weight if result.node else 0) or 0), 0) for result in node_results) or 100

    for result in node_results:
        node = result.node
        if not node:
            continue
        weight = max(int(node.score_weight or 0), 1)
        base_ratio = max(min((result.score_earned or 0) / weight, 1), 0)
        reasons = set(_extract_failure_reasons(result))
        prompt_content = _load_node_prompt_content(node)
        has_speech_requirement = bool(
            _load_json(node.required_keywords, [])
            or prompt_content.get("speech_hint")
            or node.node_type == "voice_qa"
        )
        has_prop_requirement = bool(node.prop_mode == "manual" or prompt_content.get("prop_label"))

        if node.required_gesture or node.node_type == "action":
            ratio = base_ratio
            if "gesture_mismatch" in reasons:
                ratio = min(ratio, 0.2)
            summary["body_action"]["max"] += weight
            summary["body_action"]["earned"] += weight * ratio

        if has_speech_requirement:
            ratio = base_ratio
            if "keyword_mismatch" in reasons:
                ratio = min(ratio, 0.2)
            summary["verbal_communication"]["max"] += weight
            summary["verbal_communication"]["earned"] += weight * ratio

        procedure_ratio = base_ratio
        if result.result in ("skip", "timeout"):
            procedure_ratio = min(procedure_ratio, 0.25)
        elif result.result == "fail":
            procedure_ratio = min(procedure_ratio, 0.1)
        elif result.retry_count:
            procedure_ratio = max(procedure_ratio - min(result.retry_count * 0.08, 0.3), 0)
        summary["procedure_execution"]["max"] += weight
        summary["procedure_execution"]["earned"] += weight * procedure_ratio

        if has_prop_requirement:
            ratio = 0 if "prop_missed" in reasons else base_ratio
            summary["prop_operation"]["max"] += weight
            summary["prop_operation"]["earned"] += weight * ratio

        professional_relevant = node.node_type in {"judge", "choice", "voice_qa"} or bool(node.required_gesture)
        if professional_relevant:
            ratio = base_ratio
            if {"judge_incorrect", "choice_incorrect", "identity_mismatch"} & reasons:
                ratio = min(ratio, 0.15)
            summary["professional_safety"]["max"] += weight
            summary["professional_safety"]["earned"] += weight * ratio

    if summary["professional_safety"]["max"] <= 0:
        summary["professional_safety"]["max"] = full_score
        summary["professional_safety"]["earned"] = sum(max((result.score_earned or 0), 0) for result in node_results)

    violation_penalty = (
        violation_summary.get("tab_switch", 0) * 4
        + violation_summary.get("page_hide", 0) * 4
        + violation_summary.get("page_leave", 0) * 6
        + violation_summary.get("device_lost", 0) * 5
        + violation_summary.get("identity_lost", 0) * 6
    )
    if summary["professional_safety"]["max"] > 0 and violation_penalty:
        summary["professional_safety"]["earned"] = max(summary["professional_safety"]["earned"] - violation_penalty, 0)

    dimension_scores: list[dict] = []
    for key, item in summary.items():
        if item["max"] <= 0:
            continue
        percentage = round(item["earned"] / item["max"] * 100) if item["max"] else 0
        dimension_scores.append({
            "key": key,
            "label": item["label"],
            "score": int(round(item["earned"])),
            "full_score": int(round(item["max"])),
            "percentage": percentage,
        })

    dimension_scores.sort(key=lambda item: item["percentage"])
    suggestions_map = {
        "body_action": "建议重点回看动作示范，先把关键手势和站姿做稳定。",
        "verbal_communication": "建议围绕标准话术和关键词做分段练习，先保证说全、说清。",
        "procedure_execution": "建议减少超时、跳过和重复重试，先把流程顺序走顺。",
        "prop_operation": "建议针对证件和装备节点单独复训，形成固定操作习惯。",
        "professional_safety": "建议重点复盘判断题、选择题和异常记录，强化执法规范与安全意识。",
    }
    weakness_summary = [
        f"{item['label']}偏弱（{item['percentage']}%）：{suggestions_map.get(item['key'], '建议针对性复训。')}"
        for item in dimension_scores[:2]
        if item["percentage"] < 85
    ]
    if failure_summary.get("gesture_mismatch", 0) and not any("肢体动作规范" in item for item in weakness_summary):
        weakness_summary.append("肢体动作规范偏弱：当前存在动作未达标记录，建议对照标准手势反复练习。")
    return dimension_scores, weakness_summary[:3]


def _update_session_node_records(
    session: models.VideoTrainingSession,
    node: models.VideoNode,
    node_result: models.VideoNodeResult,
    failure_reasons: list[str],
):
    node_records = _load_json(session.node_records, [])
    if not isinstance(node_records, list):
        node_records = []
    answer_data = _load_json(node_result.answer_data, {})
    police_semantic = answer_data.get("police_semantic") if isinstance(answer_data, dict) else None
    payload = {
        "node_id": node.id,
        "node_index": node_result.node_index,
        "node_title": node.title or f"节点{node_result.node_index + 1}",
        "node_type": node.node_type,
        "result": node_result.result,
        "retry_count": node_result.retry_count,
        "time_used": node_result.time_used,
        "score_earned": node_result.score_earned,
        "score_deducted": node_result.score_deducted,
        "failure_reasons": failure_reasons,
        "police_semantic": police_semantic if isinstance(police_semantic, dict) else None,
        "manual_review": _serialize_manual_review(node_result),
        "updated_at": datetime.utcnow().isoformat(),
    }
    replaced = False
    for idx, record in enumerate(node_records):
        if isinstance(record, dict) and int(record.get("node_index", -1)) == node_result.node_index:
            node_records[idx] = payload
            replaced = True
            break
    if not replaced:
        node_records.append(payload)
    node_records.sort(key=lambda item: int(item.get("node_index", 0)) if isinstance(item, dict) else 0)
    session.node_records = json.dumps(node_records, ensure_ascii=False)


def _validate_pass_submission(
    node: models.VideoNode,
    answer_data: dict,
    speech_transcript: str,
    payload: dict,
    mode: str = "practice",
) -> list[str]:
    errors: list[str] = []
    policy = _mode_policy(mode)
    node_config = _load_node_config(node)
    speech_rule = node_config.get("speech_rule") if isinstance(node_config, dict) else {}
    speech_rule = speech_rule if isinstance(speech_rule, dict) else {}
    pass_rule = node_config.get("pass_rule") if isinstance(node_config, dict) else {}
    pass_rule = pass_rule if isinstance(pass_rule, dict) else {}
    pass_mode = str(pass_rule.get("mode") or "").strip() or "all"
    semantic_node = _is_police_semantic_node(node_config)

    gesture_eval = _evaluate_gesture_rule(node, answer_data, mode=mode)
    identity_eval = _evaluate_identity_rule(node, answer_data)

    if node.prop_mode == "manual":
        prop_interaction = answer_data.get("prop_interaction")
        prop_ready = isinstance(prop_interaction, dict) and bool(prop_interaction.get("ready")) is True
        if not prop_ready and payload.get("prop_missed"):
            prop_ready = False
        if not prop_ready:
            errors.append("prop_missed")

    if node.node_type in ("action", "voice_qa"):
        keywords = [] if semantic_node else _load_json(node.required_keywords, [])
        speech_required = bool(
            node.node_type == "voice_qa"
            or keywords
            or semantic_node
            or pass_mode in ("all", "either", "speech_only")
        )
        speech_eval = _evaluate_speech_rule(speech_transcript, keywords, speech_rule, speech_required, mode=mode)

        if pass_mode == "gesture_only":
            if gesture_eval["required"] and not gesture_eval["passed"] and gesture_eval["reason"]:
                errors.append(str(gesture_eval["reason"]))
        elif pass_mode == "speech_only":
            if speech_required and not speech_eval["passed"] and speech_eval["reason"]:
                errors.append(str(speech_eval["reason"]))
        elif pass_mode == "either":
            gesture_gate = not gesture_eval["required"] or bool(gesture_eval["passed"])
            speech_gate = not speech_required or bool(speech_eval["passed"])
            if not (gesture_gate or speech_gate):
                if gesture_eval["required"] and gesture_eval["reason"]:
                    errors.append(str(gesture_eval["reason"]))
                if speech_required and speech_eval["reason"]:
                    errors.append(str(speech_eval["reason"]))
        else:
            if gesture_eval["required"] and not gesture_eval["passed"] and gesture_eval["reason"]:
                errors.append(str(gesture_eval["reason"]))
            if speech_required and not speech_eval["passed"] and speech_eval["reason"]:
                errors.append(str(speech_eval["reason"]))

        if (
            policy["allow_partial_channel_pass"]
            and pass_mode == "all"
            and set(errors).issubset({"gesture_mismatch", "keyword_mismatch"})
        ):
            gesture_gate = not gesture_eval["required"] or bool(gesture_eval["passed"])
            speech_gate = not speech_required or bool(speech_eval["passed"])
            if gesture_gate or speech_gate:
                errors = []

    else:
        if gesture_eval["required"] and not gesture_eval["passed"] and gesture_eval["reason"]:
            errors.append(str(gesture_eval["reason"]))

    if identity_eval["required"] and not identity_eval["passed"] and identity_eval["reason"]:
        errors.append(str(identity_eval["reason"]))

    if node.node_type == "judge":
        config = node_config if isinstance(node_config, dict) else {}
        if _is_choice_style_judge_node(node, config):
            correct_index = _resolve_correct_choice_index(node, config)
            submitted_choice = answer_data.get("selected")
            if submitted_choice is None or submitted_choice != correct_index:
                errors.append("judge_incorrect")
        else:
            correct_answer = _resolve_judge_boolean_answer(node, config)
            submitted_answer = answer_data.get("answer")
            if correct_answer is None or submitted_answer is None or submitted_answer != correct_answer:
                errors.append("judge_incorrect")

    if node.node_type == "choice":
        config = node_config if isinstance(node_config, dict) else {}
        correct_index = _resolve_correct_choice_index(node, config)
        submitted_choice = answer_data.get("selected")
        if submitted_choice is None or submitted_choice != correct_index:
            errors.append("choice_incorrect")

    return errors


def _build_evaluation_report(
    session: models.VideoTrainingSession,
    node_results: list[models.VideoNodeResult],
    video: models.TrainingVideo,
) -> dict:
    report = build_video_evaluation_report(session, node_results, video)
    report["mode_label"] = _mode_policy(session.mode)["label"]
    for item in report.get("node_summaries") or []:
        if isinstance(item, dict):
            matched = next((r for r in node_results if r.id == item.get("node_result_id")), None)
            item["manual_review"] = _serialize_manual_review(matched) if matched else None
    return report


def _generate_and_store_report(
    db: Session,
    session: models.VideoTrainingSession,
) -> dict:
    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session.id)
        .order_by(models.VideoNodeResult.node_index.asc())
        .all()
    )
    video = db.query(models.TrainingVideo).filter(
        models.TrainingVideo.id == session.video_id
    ).first()

    session.evaluation_status = "generating"
    session.evaluation_error = None
    if not session.evaluation_started_at:
        session.evaluation_started_at = datetime.utcnow()
    db.flush()

    try:
        for result in node_results:
            if not result.node:
                continue
            snapshot = build_runtime_assessment_snapshot(session, result.node, result)
            result.evidence_payload = json.dumps(snapshot.get("evidence") or {}, ensure_ascii=False)
            result.assessment_payload = json.dumps(snapshot, ensure_ascii=False)

        report = _build_evaluation_report(session, node_results, video)
        session.evaluation_result = json.dumps(report, ensure_ascii=False)
        session.evaluation_status = "completed"
        session.evaluation_completed_at = datetime.utcnow()
        session.evaluation_error = None
        db.commit()
        db.refresh(session)
        return report
    except Exception as exc:
        session.evaluation_status = "failed"
        session.evaluation_error = str(exc)
        db.commit()
        raise


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# Session 绠＄悊
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@router.post("/start/{video_id}")
def start_video_training(
    video_id: int,
    mode: str = "practice",
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    video = db.query(models.TrainingVideo).filter(
        models.TrainingVideo.id == video_id,
        models.TrainingVideo.status == "published",
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在或未发布")
    if video.video_type != "interactive":
        raise HTTPException(status_code=400, detail="仅交互式实训视频支持创建训练 Session")
    if mode not in ("practice", "exam"):
        mode = "practice"

    # 鏌ユ壘鏄惁鏈夎繘琛屼腑鐨?session锛堝悓鐢ㄦ埛鍚岃棰戯級
    # 查找同用户同视频同模式的 active session（仅恢复相同模式的）
    existing = (
        db.query(models.VideoTrainingSession)
        .filter(
            models.VideoTrainingSession.user_id == current_user.id,
            models.VideoTrainingSession.video_id == video_id,
            models.VideoTrainingSession.status == "active",
            models.VideoTrainingSession.mode == mode,
        )
        .order_by(models.VideoTrainingSession.created_at.desc())
        .first()
    )
    if existing:
        node_results = (
            db.query(models.VideoNodeResult)
            .filter(models.VideoNodeResult.session_id == existing.id)
            .order_by(models.VideoNodeResult.node_index.asc())
            .all()
        )
        return {
            **_serialize_session(existing),
            "resumed": True,
            "node_results": [_serialize_node_result(r) for r in node_results],
        }

    # 将同视频不同模式的 active session 标记为 abandoned
    stale_sessions = (
        db.query(models.VideoTrainingSession)
        .filter(
            models.VideoTrainingSession.user_id == current_user.id,
            models.VideoTrainingSession.video_id == video_id,
            models.VideoTrainingSession.status == "active",
            models.VideoTrainingSession.mode != mode,
        )
        .all()
    )
    for stale in stale_sessions:
        stale.status = "abandoned"
    if stale_sessions:
        db.flush()

    full_score = _calc_full_score(video.nodes)
    session = models.VideoTrainingSession(
        user_id=current_user.id,
        video_id=video_id,
        mode=mode,
        status="active",
        current_node_index=0,
        full_score=full_score,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        **_serialize_session(session),
        "resumed": False,
        "node_results": [],
    }


@router.get("/session/{session_id}")
def get_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")

    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session_id)
        .order_by(models.VideoNodeResult.node_index.asc())
        .all()
    )
    data = _serialize_session(session)
    data["node_results"] = [_serialize_node_result(r) for r in node_results]
    return data


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 节点鍒ゅ畾
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@router.post("/session/{session_id}/node/submit")
def submit_node_result(
    session_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Session 已结束")

    node_id = int(payload.get("node_id", 0))
    node_index = int(payload.get("node_index", 0))
    action = str(payload.get("action", "pass"))  # pass / skip / timeout
    retry_count = int(payload.get("retry_count", 0))
    time_used = payload.get("time_used")
    answer_data = _normalize_answer_data(payload.get("answer_data"))
    speech_transcript = str(payload.get("speech_transcript", "") or "")

    node = db.query(models.VideoNode).filter(models.VideoNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # 鈹€鈹€ 璁＄畻寰楀垎 鈹€鈹€
    if node.video_id != session.video_id:
        raise HTTPException(status_code=400, detail="节点不属于当前训练视频")
    if node_index != node.node_index:
        raise HTTPException(status_code=400, detail="节点序号与配置不一致")

    score_earned = node.score_weight
    score_deducted = 0
    policy = _mode_policy(session.mode)

    validation_errors: list[str] = []
    police_semantic_eval: dict = {"enabled": False}

    if action == "skip":
        score_deducted = _scaled_penalty(node.skip_score_deduct, float(policy["skip_penalty_scale"]), node.score_weight)
        score_earned = max(0, node.score_weight - score_deducted)
        result = "skip"
    elif action == "timeout":
        score_deducted = _scaled_penalty(node.skip_score_deduct, float(policy["skip_penalty_scale"]), node.score_weight)
        score_earned = max(0, node.score_weight - score_deducted)
        result = "timeout"
    else:
        validation_errors = _validate_pass_submission(node, answer_data, speech_transcript, payload, mode=session.mode)
        police_semantic_eval = _evaluate_police_semantic_answer(node, answer_data, speech_transcript)
        if police_semantic_eval.get("enabled"):
            if not police_semantic_eval.get("answer_text"):
                validation_errors.append("police_answer_empty")
            elif not police_semantic_eval.get("passed"):
                validation_errors.append("police_points_missing")
            answer_data["answer_text"] = police_semantic_eval.get("answer_text", "")
            answer_data["police_semantic"] = police_semantic_eval

        if validation_errors:
            score_deducted = node.score_weight
            score_earned = 0
            result = "fail"
        else:
            base_score = node.score_weight
            if police_semantic_eval.get("enabled"):
                base_score = min(
                    node.score_weight,
                    max(0, int(round(node.score_weight * int(police_semantic_eval.get("semantic_score") or 0) / 100))),
                )
            # pass：根据模式应用不同的重试扣分策略
            retry_penalty = _scaled_penalty(
                retry_count * node.retry_score_deduct,
                float(policy["retry_penalty_scale"]),
                node.score_weight,
            )
            score_earned = max(0, base_score - retry_penalty)
            score_deducted = max(0, node.score_weight - score_earned)
            result = "pass"

    # 鈹€鈹€ 淇濆瓨节点缁撴灉 鈹€鈹€
    # 妫€鏌ユ槸鍚﹀凡鏈夎节点缁撴灉锛堥噸澶嶆彁浜ゆ椂瑕嗙洊锛?
    existing_result = db.query(models.VideoNodeResult).filter(
        models.VideoNodeResult.session_id == session_id,
        models.VideoNodeResult.node_index == node_index,
    ).first()

    answer_data_to_store = dict(answer_data)
    if validation_errors:
        answer_data_to_store["__validation_errors"] = validation_errors
    elif "__validation_errors" in answer_data_to_store:
        answer_data_to_store.pop("__validation_errors", None)

    if existing_result:
        existing_result.result = result
        existing_result.retry_count = retry_count
        existing_result.time_used = time_used
        existing_result.score_earned = score_earned
        existing_result.score_deducted = score_deducted
        existing_result.answer_data = json.dumps(answer_data_to_store, ensure_ascii=False) if answer_data_to_store else None
        existing_result.speech_transcript = speech_transcript or None
        node_result = existing_result
    else:
        node_result = models.VideoNodeResult(
            session_id=session_id,
            node_id=node_id,
            node_index=node_index,
            result=result,
            retry_count=retry_count,
            time_used=time_used,
            score_earned=score_earned,
            score_deducted=score_deducted,
            answer_data=json.dumps(answer_data_to_store, ensure_ascii=False) if answer_data_to_store else None,
            speech_transcript=speech_transcript or None,
        )
        db.add(node_result)

    evidence_snapshot = build_node_multimodal_evidence(session, node, node_result)
    assessment_snapshot = build_runtime_assessment_snapshot(session, node, node_result)
    node_result.evidence_payload = json.dumps(evidence_snapshot, ensure_ascii=False)
    node_result.assessment_payload = json.dumps(assessment_snapshot, ensure_ascii=False)

    # 鏇存柊 Session 褰撳墠节点绱㈠紩
    if result != "fail":
        session.current_node_index = max(session.current_node_index, node_index + 1)
    session.evaluation_status = "pending"
    session.evaluation_result = None
    session.evaluation_error = None
    session.evaluation_started_at = None
    session.evaluation_completed_at = None
    _update_session_node_records(session, node, node_result, validation_errors)
    db.commit()
    db.refresh(node_result)

    return {
        "node_result": _serialize_node_result(node_result),
        "score_earned": score_earned,
        "score_deducted": score_deducted,
        "result": result,
        "feedback": {
            "passed": result == "pass",
            "reasons": validation_errors,
            "police_semantic": police_semantic_eval if police_semantic_eval.get("enabled") else None,
        },
    }


@router.post("/session/{session_id}/violation")
def record_violation(
    session_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")

    log = _load_json(session.violation_log, [])
    log.append({
        "type": str(payload.get("type", "unknown")),
        "detail": str(payload.get("detail", "")),
        "ts": datetime.utcnow().isoformat(),
    })
    session.violation_log = json.dumps(log, ensure_ascii=False)
    db.commit()
    return {"message": "记录成功", "violation_count": len(log)}


@router.post("/vision/evaluate")
def evaluate_visual_signal(
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session_id = payload.get("session_id")
    node_id = payload.get("node_id")
    mode = str(payload.get("mode") or "reference_face")
    provider = str(payload.get("provider") or "stub")

    if session_id:
        session = db.query(models.VideoTrainingSession).filter(
            models.VideoTrainingSession.id == session_id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="训练记录不存在")
        if current_user.role != "admin" and session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问该训练记录")

    if node_id:
        node = db.query(models.VideoNode).filter(models.VideoNode.id == node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail="节点不存在")

    return {
        "enabled": False,
        "status": "not_configured",
        "mode": mode,
        "provider": provider,
        "matched": False,
        "score": 0,
        "message": "后端视觉识别接口已预留，当前尚未接入实际 CV 模型或外部视觉服务",
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 瀹屾垚 & 璇勪及鎶ュ憡
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@router.post("/session/{session_id}/finish")
def finish_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    if session.status == "finished":
        # 宸插畬鎴愬垯鐩存帴杩斿洖鎶ュ憡
        return _get_report(db, session)

    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session_id)
        .all()
    )

    _recalculate_session_total_score(session)
    session.status = "finished"
    session.finished_at = datetime.utcnow()
    session.evaluation_status = "pending"
    session.evaluation_result = None
    session.evaluation_error = None
    session.evaluation_started_at = None
    session.evaluation_completed_at = None
    db.commit()
    db.refresh(session)

    return _get_report(db, session)


@router.get("/session/{session_id}/report")
def get_report(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id,
        models.VideoTrainingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    return _get_report(db, session)


def _get_report(db: Session, session: models.VideoTrainingSession) -> dict:
    if session.evaluation_result:
        cached = _load_json(session.evaluation_result, None)
        if isinstance(cached, dict):
            cached.setdefault("evaluation_status", session.evaluation_status or "completed")
            cached.setdefault("report_ready", True)
            cached.setdefault("evaluation_error", session.evaluation_error)
            cached.setdefault("failure_reason_summary", {})
            return cached

    if session.status != "finished":
        node_results = (
            db.query(models.VideoNodeResult)
            .filter(models.VideoNodeResult.session_id == session.id)
            .order_by(models.VideoNodeResult.node_index.asc())
            .all()
        )
        return {
            **_serialize_session(session),
            "evaluation_status": session.evaluation_status or "pending",
            "report_ready": False,
            "failure_reason_summary": _summarize_failure_reasons(node_results),
            "node_summaries": [_serialize_node_result(result) for result in node_results],
            "message": "训练尚未完成，暂未生成评估报告",
        }

    if session.evaluation_status == "generating":
        return {
            **_serialize_session(session),
            "evaluation_status": "generating",
            "report_ready": False,
            "message": "评估报告生成中，请稍后重试",
        }

    if session.evaluation_status == "failed":
        return {
            **_serialize_session(session),
            "evaluation_status": "failed",
            "report_ready": False,
            "message": "评估报告生成失败",
            "evaluation_error": session.evaluation_error,
        }

    node_results = (
        db.query(models.VideoNodeResult)
        .filter(models.VideoNodeResult.session_id == session.id)
        .order_by(models.VideoNodeResult.node_index.asc())
        .all()
    )
    if not node_results:
        return {
            **_serialize_session(session),
            "evaluation_status": "pending",
            "report_ready": False,
            "message": "暂无可评估的节点结果",
        }
    return _generate_and_store_report(db, session)


def _recalculate_session_total_score(session: models.VideoTrainingSession) -> int:
    total_score = sum((item.score_earned or 0) for item in session.node_results)
    session.total_score = total_score
    return total_score


def _resolve_review_scores(
    node: models.VideoNode,
    reviewed_result: str,
    payload: dict,
) -> tuple[int, int]:
    max_score = max(int(node.score_weight or 0), 0)
    raw_earned = payload.get("score_earned")
    raw_deducted = payload.get("score_deducted")

    if raw_earned is None and raw_deducted is None:
        if reviewed_result == "fail":
            return 0, max_score
        if reviewed_result in ("skip", "timeout"):
            deducted = min(max(int(node.skip_score_deduct or 0), 0), max_score)
            return max_score - deducted, deducted
        return max_score, 0

    if raw_earned is None:
        score_deducted = min(max(int(raw_deducted or 0), 0), max_score)
        return max_score - score_deducted, score_deducted

    score_earned = min(max(int(raw_earned or 0), 0), max_score)
    if raw_deducted is None:
        return score_earned, max_score - score_earned

    score_deducted = min(max(int(raw_deducted or 0), 0), max_score)
    return score_earned, score_deducted


def _session_matches_review_filters(
    session: models.VideoTrainingSession,
    reviewed_only: bool = False,
    override_only: bool = False,
) -> bool:
    reviewed_results = [item for item in session.node_results if _extract_manual_review(item)]
    if reviewed_only and not reviewed_results:
        return False
    if override_only and not any(_manual_review_overridden(item) for item in reviewed_results):
        return False
    return True


def _session_matches_violation_filter(
    session: models.VideoTrainingSession,
    violation_type: Optional[str] = None,
) -> bool:
    if not violation_type:
        return True
    for item in _load_json(session.violation_log, []):
        if isinstance(item, dict) and item.get("type") == violation_type:
            return True
    return False


def _serialize_review_record(result: models.VideoNodeResult) -> Optional[dict]:
    review = _serialize_manual_review(result)
    if not review:
        return None
    session = result.session
    user = session.user if session else None
    video = session.video if session else None
    return {
        "node_result_id": result.id,
        "session_id": result.session_id,
        "video_id": session.video_id if session else None,
        "video_title": video.title if video else "",
        "user_id": session.user_id if session else None,
        "username": user.username if user else "",
        "session_status": session.status if session else None,
        "node_id": result.node_id,
        "node_index": result.node_index,
        "node_title": result.node.title if result.node else f"节点{result.node_index + 1}",
        "current_result": result.result,
        "score_earned": result.score_earned,
        "score_deducted": result.score_deducted,
        "reviewer_username": review.get("reviewer_username"),
        "reviewed_at": review.get("reviewed_at"),
        "review_note": review.get("review_note"),
        "original_result": review.get("original_result"),
        "original_score_earned": review.get("original_score_earned"),
        "original_score_deducted": review.get("original_score_deducted"),
        "original_failure_reasons": review.get("original_failure_reasons") or [],
        "failure_reasons": _extract_failure_reasons(result),
        "overridden": bool(review.get("overridden")),
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 瀛﹀憳鍘嗗彶
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@router.get("/history")
def get_student_video_history(
    video_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    mode: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    offset = (page - 1) * page_size

    # 基础查询（不含 joinedload，用于 count 和筛选）
    base_query = (
        db.query(models.VideoTrainingSession)
        .filter(models.VideoTrainingSession.user_id == current_user.id)
    )
    if video_id:
        base_query = base_query.filter(models.VideoTrainingSession.video_id == video_id)
    if status and status in ("active", "finished", "abandoned"):
        base_query = base_query.filter(models.VideoTrainingSession.status == status)
    if mode and mode in ("practice", "exam"):
        base_query = base_query.filter(models.VideoTrainingSession.mode == mode)
    has_video_join = False
    if category:
        base_query = base_query.join(models.TrainingVideo).filter(
            models.TrainingVideo.scenario_type == category
        )
        has_video_join = True
    if keyword and keyword.strip():
        # A history page is server-paginated, so keyword filtering must happen
        # before count/offset rather than only against the loaded page.
        search = f"%{keyword.strip()}%"
        if not has_video_join:
            base_query = base_query.join(models.TrainingVideo)
        base_query = base_query.filter(models.TrainingVideo.title.ilike(search))

    def parse_history_date(value: Optional[str], field_name: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(tzinfo=None)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{field_name} 必须为 YYYY-MM-DD 格式")

    start_at = parse_history_date(date_start, "date_start")
    end_at = parse_history_date(date_end, "date_end")
    if start_at:
        base_query = base_query.filter(models.VideoTrainingSession.created_at >= start_at)
    if end_at:
        # The date picker sends an inclusive date; use the next midnight as
        # an exclusive upper bound so records from the full final day remain.
        base_query = base_query.filter(models.VideoTrainingSession.created_at < end_at + timedelta(days=1))

    total = base_query.count()
    session_ids_query = (
        base_query.order_by(models.VideoTrainingSession.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    # 带 joinedload 的实际加载
    sessions = (
        db.query(models.VideoTrainingSession)
        .options(
            joinedload(models.VideoTrainingSession.video).joinedload(models.TrainingVideo.nodes),
        )
        .filter(models.VideoTrainingSession.id.in_(
            [s.id for s in session_ids_query.all()]
        ))
        .order_by(models.VideoTrainingSession.created_at.desc())
        .all()
    )

    # 批量获取失分维度统计（仅 finished sessions）
    finished_ids = [s.id for s in sessions if s.status == "finished"]
    failure_map: dict[int, dict[str, int]] = {}
    if finished_ids:
        node_results_all = (
            db.query(models.VideoNodeResult)
            .filter(models.VideoNodeResult.session_id.in_(finished_ids))
            .all()
        )
        for nr in node_results_all:
            sid = nr.session_id
            if sid not in failure_map:
                failure_map[sid] = {}
            for reason in _extract_failure_reasons(nr):
                failure_map[sid][reason] = failure_map[sid].get(reason, 0) + 1

    items = []
    for s in sessions:
        data = _serialize_session(s)
        video = s.video
        data["video_title"] = video.title if video else f"视频#{s.video_id}"
        data["category"] = (video.scenario_type or "综合训练") if video else "综合训练"
        data["difficulty"] = (video.difficulty or "normal") if video else "normal"

        # 百分制得分和评级
        if s.status == "finished" and s.total_score is not None and s.full_score:
            pct = round(s.total_score / s.full_score * 100, 1)
            data["score_percentage"] = pct
            data["grade"] = _grade_from_percentage(round(pct))
            data["needs_retry"] = pct < 70
        else:
            data["score_percentage"] = None
            data["grade"] = None
            data["needs_retry"] = s.status == "abandoned"

        # 训练时长（秒）
        duration = None
        if s.finished_at and s.created_at:
            duration = int((s.finished_at - s.created_at).total_seconds())
        data["duration_seconds"] = duration

        # 失分原因统计
        data["failure_reasons"] = failure_map.get(s.id, {})

        items.append(data)

    # 汇总失分维度（全部已完成记录的聚合）
    all_finished_query = (
        db.query(models.VideoTrainingSession)
        .filter(
            models.VideoTrainingSession.user_id == current_user.id,
            models.VideoTrainingSession.status == "finished",
        )
    )
    if video_id:
        all_finished_query = all_finished_query.filter(models.VideoTrainingSession.video_id == video_id)
    if category:
        all_finished_query = all_finished_query.join(models.TrainingVideo).filter(
            models.TrainingVideo.scenario_type == category
        )
    all_finished_ids = [s.id for s in all_finished_query.all()]

    issue_summary: dict[str, int] = {}
    if all_finished_ids:
        all_node_results = (
            db.query(models.VideoNodeResult)
            .filter(models.VideoNodeResult.session_id.in_(all_finished_ids))
            .all()
        )
        for nr in all_node_results:
            for reason in _extract_failure_reasons(nr):
                issue_summary[reason] = issue_summary.get(reason, 0) + 1

    # 将 failure reason key 映射为用户可读标签
    failure_label_map = {
        "gesture_mismatch": "肢体动作不规范",
        "gesture_timeout": "动作超时未完成",
        "keyword_mismatch": "话术关键词缺失",
        "speech_too_short": "口头表达不完整",
        "prop_missed": "未正确使用道具/装备",
        "wrong_answer": "选项/判断答错",
        "timeout": "节点超时",
    }
    issue_top = sorted(issue_summary.items(), key=lambda x: x[1], reverse=True)[:5]
    issue_top_labeled = [
        {"key": key, "label": failure_label_map.get(key, key), "count": count}
        for key, count in issue_top
    ]

    # 获取可用的场景类型列表
    available_categories = (
        db.query(models.TrainingVideo.scenario_type)
        .join(models.VideoTrainingSession, models.VideoTrainingSession.video_id == models.TrainingVideo.id)
        .filter(
            models.VideoTrainingSession.user_id == current_user.id,
            models.TrainingVideo.scenario_type.isnot(None),
        )
        .distinct()
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
        "issue_top": issue_top_labeled,
        "available_categories": [c[0] for c in available_categories if c[0]],
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
# 绠＄悊绔細鏌ョ湅鍏ㄩ噺瀛﹀憳瀹炶鏁版嵁
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

@router.get("/admin/sessions")
def admin_list_sessions(
    video_id: Optional[int] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    status: Optional[str] = None,
    reviewed_only: bool = False,
    override_only: bool = False,
    violation_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    query = db.query(models.VideoTrainingSession).join(
        models.User, models.User.id == models.VideoTrainingSession.user_id
    )
    if video_id:
        query = query.filter(models.VideoTrainingSession.video_id == video_id)
    if user_id:
        query = query.filter(models.VideoTrainingSession.user_id == user_id)
    if username:
        query = query.filter(models.User.username.contains(username))
    if status:
        query = query.filter(models.VideoTrainingSession.status == status)

    sessions = query.order_by(models.VideoTrainingSession.created_at.desc()).all()
    if reviewed_only or override_only:
        sessions = [
            item for item in sessions
            if _session_matches_review_filters(item, reviewed_only=reviewed_only, override_only=override_only)
        ]
    if violation_type:
        sessions = [
            item for item in sessions
            if _session_matches_violation_filter(item, violation_type=violation_type)
        ]
    total = len(sessions)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    sessions = sessions[start:end]

    items = []
    for s in sessions:
        data = _serialize_session(s)
        user = db.query(models.User).filter(models.User.id == s.user_id).first()
        video = db.query(models.TrainingVideo).filter(models.TrainingVideo.id == s.video_id).first()
        data["username"] = user.username if user else ""
        data["video_title"] = video.title if video else ""
        if s.status == "finished" and s.total_score is not None and s.full_score:
            pct = round(s.total_score / s.full_score * 100)
            data["grade"] = _grade_from_percentage(pct)
        else:
            data["grade"] = None
        items.append(data)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/admin/analytics")
def admin_training_analytics(
    video_id: Optional[int] = None,
    username: Optional[str] = None,
    status: Optional[str] = None,
    reviewed_only: bool = False,
    override_only: bool = False,
    violation_type: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    query = db.query(models.VideoTrainingSession).join(
        models.User, models.User.id == models.VideoTrainingSession.user_id
    )
    if video_id:
        query = query.filter(models.VideoTrainingSession.video_id == video_id)
    if username:
        query = query.filter(models.User.username.contains(username))
    if status:
        query = query.filter(models.VideoTrainingSession.status == status)

    sessions = query.all()
    if reviewed_only or override_only:
        sessions = [
            item for item in sessions
            if _session_matches_review_filters(item, reviewed_only=reviewed_only, override_only=override_only)
        ]
    if violation_type:
        sessions = [
            item for item in sessions
            if _session_matches_violation_filter(item, violation_type=violation_type)
        ]
    session_ids = [item.id for item in sessions]
    node_results = []
    if session_ids:
        node_results = db.query(models.VideoNodeResult).filter(
            models.VideoNodeResult.session_id.in_(session_ids)
        ).all()

    failure_reason_summary: dict[str, int] = {}
    node_failure_summary: dict[str, dict] = {}
    violation_summary: dict[str, int] = {}
    total_violation_count = 0
    reviewed_count = 0
    overridden_count = 0

    for result in node_results:
        if _extract_manual_review(result):
            reviewed_count += 1
            if _manual_review_overridden(result):
                overridden_count += 1
        reasons = _extract_failure_reasons(result)
        if not reasons:
            continue
        node_key = str(result.node_id)
        if node_key not in node_failure_summary:
            node_failure_summary[node_key] = {
                "node_id": result.node_id,
                "node_title": result.node.title if result.node else f"节点{result.node_index + 1}",
                "node_type": result.node.node_type if result.node else None,
                "fail_count": 0,
                "reasons": {},
            }
        node_failure_summary[node_key]["fail_count"] += 1
        for reason in reasons:
            failure_reason_summary[reason] = failure_reason_summary.get(reason, 0) + 1
            node_failure_summary[node_key]["reasons"][reason] = node_failure_summary[node_key]["reasons"].get(reason, 0) + 1

    for session in sessions:
        violation_map = _summarize_violation_log(session)
        if violation_type:
            violation_map = {
                key: count for key, count in violation_map.items()
                if key == violation_type
            }
        total_violation_count += sum(violation_map.values())
        for key, count in violation_map.items():
            violation_summary[key] = violation_summary.get(key, 0) + count

    return {
        "session_count": len(sessions),
        "finished_count": sum(1 for item in sessions if item.status == "finished"),
        "active_count": sum(1 for item in sessions if item.status == "active"),
        "reviewed_count": reviewed_count,
        "overridden_count": overridden_count,
        "avg_score": round(
            sum((item.total_score or 0) for item in sessions if item.total_score is not None)
            / max(1, sum(1 for item in sessions if item.total_score is not None)),
            1,
        ) if any(item.total_score is not None for item in sessions) else 0,
        "total_violation_count": total_violation_count,
        "failure_reason_summary": sorted(
            [{"reason": key, "count": value} for key, value in failure_reason_summary.items()],
            key=lambda item: item["count"],
            reverse=True,
        ),
        "violation_summary": sorted(
            [{"type": key, "count": value} for key, value in violation_summary.items()],
            key=lambda item: item["count"],
            reverse=True,
        ),
        "node_failure_summary": sorted(
            node_failure_summary.values(),
            key=lambda item: item["fail_count"],
            reverse=True,
        ),
    }


@router.get("/admin/sessions/{session_id}/report")
def admin_get_session_report(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    session = db.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")
    return _get_report(db, session)


@router.get("/admin/reviews")
def admin_list_reviews(
    video_id: Optional[int] = None,
    username: Optional[str] = None,
    status: Optional[str] = None,
    override_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    query = (
        db.query(models.VideoNodeResult)
        .join(models.VideoTrainingSession, models.VideoTrainingSession.id == models.VideoNodeResult.session_id)
        .join(models.User, models.User.id == models.VideoTrainingSession.user_id)
    )
    if video_id:
        query = query.filter(models.VideoTrainingSession.video_id == video_id)
    if username:
        query = query.filter(models.User.username.contains(username))
    if status:
        query = query.filter(models.VideoTrainingSession.status == status)

    results = query.order_by(models.VideoNodeResult.created_at.desc()).all()
    items = []
    for result in results:
        review_item = _serialize_review_record(result)
        if not review_item:
            continue
        if override_only and not review_item["overridden"]:
            continue
        items.append(review_item)

    total = len(items)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start:end],
    }


@router.post("/admin/node-results/{result_id}/review")
def admin_review_node_result(
    result_id: int,
    payload: dict,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    node_result = db.query(models.VideoNodeResult).filter(
        models.VideoNodeResult.id == result_id
    ).first()
    if not node_result:
        raise HTTPException(status_code=404, detail="节点结果不存在")
    if not node_result.node:
        raise HTTPException(status_code=400, detail="节点配置不存在")
    if not node_result.session:
        raise HTTPException(status_code=400, detail="璁粌 Session 不存在")

    reviewed_result = str(payload.get("result") or node_result.result)
    if reviewed_result not in ("pass", "fail", "skip", "timeout"):
        raise HTTPException(status_code=400, detail="复核结果不合法")

    existing_answer_data = _normalize_answer_data(_load_json(node_result.answer_data, {}))
    original_failure_reasons = _extract_failure_reasons(node_result)
    manual_failure_reasons = payload.get("failure_reasons")
    if isinstance(manual_failure_reasons, list):
        failure_reasons = [str(item).strip() for item in manual_failure_reasons if str(item).strip()]
    elif reviewed_result == "fail":
        failure_reasons = original_failure_reasons or ["manual_review_failed"]
    else:
        failure_reasons = []

    score_earned, score_deducted = _resolve_review_scores(node_result.node, reviewed_result, payload)
    review_note = str(payload.get("review_note") or "").strip()
    reviewed_at = datetime.utcnow().isoformat()

    existing_answer_data["__manual_review"] = {
        "reviewer_id": current_user.id,
        "reviewer_username": current_user.username,
        "reviewed_at": reviewed_at,
        "review_note": review_note,
        "original_result": node_result.result,
        "original_score_earned": node_result.score_earned,
        "original_score_deducted": node_result.score_deducted,
        "original_failure_reasons": original_failure_reasons,
    }
    if failure_reasons:
        existing_answer_data["__validation_errors"] = failure_reasons
    else:
        existing_answer_data.pop("__validation_errors", None)

    node_result.result = reviewed_result
    node_result.score_earned = score_earned
    node_result.score_deducted = score_deducted
    node_result.answer_data = json.dumps(existing_answer_data, ensure_ascii=False)
    evidence_snapshot = build_node_multimodal_evidence(node_result.session, node_result.node, node_result)
    assessment_snapshot = build_runtime_assessment_snapshot(node_result.session, node_result.node, node_result)
    node_result.evidence_payload = json.dumps(evidence_snapshot, ensure_ascii=False)
    node_result.assessment_payload = json.dumps(assessment_snapshot, ensure_ascii=False)

    if reviewed_result != "fail":
        node_result.session.current_node_index = max(
            int(node_result.session.current_node_index or 0),
            int(node_result.node_index) + 1,
        )
    node_result.session.evaluation_status = "pending"
    node_result.session.evaluation_result = None
    node_result.session.evaluation_error = None
    node_result.session.evaluation_started_at = None
    node_result.session.evaluation_completed_at = None
    _update_session_node_records(node_result.session, node_result.node, node_result, failure_reasons)
    _recalculate_session_total_score(node_result.session)
    db.commit()
    db.refresh(node_result)
    db.refresh(node_result.session)

    return {
        "message": "复核完成",
        "node_result": _serialize_node_result(node_result),
        "session_total_score": node_result.session.total_score,
        "report": _get_report(db, node_result.session),
    }




