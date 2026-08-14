from __future__ import annotations

import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any


SCORING_VERSION = "adaptive_v1"
CURRENT_EVALUATION_POLICY_VERSION = "adaptive_v1_llm_cap_audit_v2"
COMMON_DIMENSIONS = [
    ("沟通表达与执法语言", "礼貌克制、身份立场清晰，避免压迫、诱导或激化。"),
    ("主动询问与逻辑推进", "主动提问、追问连贯，信息流由学员推动。"),
    ("关键信息整理能力", "归纳时间、地点、人物、经过、诉求、矛盾点等已获信息。"),
    ("处置闭环意识", "阶段总结、下一步安排、确认反馈，避免草率结束。"),
]
POINT_DIFFICULTY_FACTORS = {"低": 0.75, "简单": 0.75, "中": 1.0, "中等": 1.0, "普通": 1.0, "高": 1.25, "困难": 1.25}
GRADE_LEVELS = [(90, "卓越"), (80, "优秀"), (70, "良好"), (60, "合格"), (0, "需改进")]
RED_FLAG_RULES = {
    "coercive_language": {"cap": 59, "label": "明显威胁/侮辱/诱供", "keywords": ["闭嘴", "老实点", "快说", "少废话", "废话", "给我老实交代", "别装了", "不说就", "收拾你", "铐起来"]},
    "ignored_emergency_risk": {"cap": 59, "label": "忽视紧急人身风险", "keywords": ["流血", "昏迷", "刀", "持刀", "火", "煤气", "跳楼", "自杀", "爆炸", "重伤"]},
    "rights_violation": {"cap": 69, "label": "明显错误法律处置或侵犯权利", "keywords": ["不用手续", "随便搜", "直接关起来", "必须认罪", "不让你联系", "不许请律师", "我说了算"]},
}
ASSESSMENT_KEY_TERMS = ("报警人", "身份", "姓名", "联系方式", "电话", "时间", "地点", "地址", "人员", "在场", "经过", "原因", "诉求", "矛盾", "伤情", "危险", "风险", "安全", "证据", "监控", "现场", "处置", "派警", "控制", "告知", "闭环")
ASSESSMENT_TERM_ALIASES = {"电话": "联系方式", "地址": "地点", "人员": "在场", "伤情": "风险", "危险": "风险", "监控": "证据"}


def _strings(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value or "").strip() for value in values or [] if str(value or "").strip()))


def _identity(value: Any) -> str:
    return re.sub(r"[\s，。！？、；：“”‘’（）()《》【】\[\]{}<>.,!?;:'\"`~@#$%^&*\-_=+|\\/]+", "", str(value or "").lower())


def _ratio(point: dict[str, Any]) -> float:
    status = str(point.get("status") or "missed")
    if status == "hit":
        return 1.0
    if status in {"miss", "missed"}:
        return 0.0
    try:
        explicit = float(point.get("completion_ratio", point.get("hit_ratio", 0.5)))
    except (TypeError, ValueError):
        explicit = 0.5
    return max(0.25, min(0.85, explicit))


def _equivalent(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("id") and left.get("id") == right.get("id"):
        return True
    left_content = _identity(left.get("content") or left.get("requirement") or left.get("description"))
    right_content = _identity(right.get("content") or right.get("requirement") or right.get("description"))
    a = _identity(left.get("label") or left.get("content"))
    b = _identity(right.get("label") or right.get("content"))
    if a == b and a:
        return True
    if not left_content or not right_content:
        return False
    if (left_content in right_content or right_content in left_content) and SequenceMatcher(None, a, b).ratio() >= 0.5:
        return True
    left_text = a + left_content
    right_text = b + right_content
    left_terms = {ASSESSMENT_TERM_ALIASES.get(term, term) for term in ASSESSMENT_KEY_TERMS if term in left_text}
    right_terms = {ASSESSMENT_TERM_ALIASES.get(term, term) for term in ASSESSMENT_KEY_TERMS if term in right_text}
    union = left_terms | right_terms
    return bool(union and len(left_terms & right_terms) / len(union) >= 0.75)


def dedupe_assessment_result_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in points or []:
        if not isinstance(raw, dict):
            continue
        point = dict(raw)
        point["id"] = str(point.get("id") or point.get("point_id") or "").strip()
        point["label"] = str(point.get("label") or point.get("content") or "未命名考察点").strip()
        found = next((index for index, current in enumerate(result) if _equivalent(current, point)), None)
        if found is None:
            result.append(point)
            continue
        current = result[found]
        statuses = {"missed": 1, "miss": 1, "partial": 2, "hit": 3}
        best = max((current.get("status", "missed"), point.get("status", "missed")), key=lambda value: statuses.get(str(value), 0))
        result[found] = {
            **current, **point, "status": "missed" if best == "miss" else best,
            "required": bool(current.get("required", point.get("required", True))),
            "keywords": _strings((current.get("keywords") or []) + (point.get("keywords") or [])),
            "evidence": _strings((current.get("evidence") or []) + (point.get("evidence") or []))[:3],
            "completion_ratio": max(_ratio(current), _ratio(point)),
        }
    return result


def _difficulty(point: dict[str, Any]) -> tuple[str, float]:
    raw = str(point.get("difficulty") or point.get("difficulty_level") or "").strip()
    if raw in POINT_DIFFICULTY_FACTORS:
        return raw, POINT_DIFFICULTY_FACTORS[raw]
    weight = max(1, int(point.get("weight") or 10))
    return ("低", 0.75) if weight <= 10 else (("高", 1.25) if weight >= 14 else ("中等", 1.0))


def calculate_adaptive_weighting(point_results: list[dict[str, Any]]) -> dict[str, Any]:
    points = dedupe_assessment_result_points([point for point in point_results if str(point.get("label") or "").strip()])
    point_units = sum(_difficulty(point)[1] for point in points)
    distribution_units = sum(_difficulty(point)[1] * (1.15 if point.get("required", True) else 1.0) for point in points)
    common_share = 1.0 if not points else max(0.35, min(0.60, 4.0 / (4.0 + point_units)))
    assessment_share = 1.0 - common_share
    details = []
    for point in points:
        level, factor = _difficulty(point)
        unit = factor * (1.15 if point.get("required", True) else 1.0)
        share = assessment_share * unit / distribution_units if distribution_units else 0.0
        details.append({"id": point.get("id"), "label": point.get("label"), "difficulty_level": level, "difficulty_factor": factor,
                        "required": bool(point.get("required", True)), "unit": round(unit, 4), "score_share": share, "full_score": round(share * 100)})
    return {"scoring_version": SCORING_VERSION, "common_units": 4.0, "assessment_units": round(point_units, 4),
            "assessment_distribution_units": round(distribution_units, 4), "common_share": common_share, "assessment_share": assessment_share,
            "common_full_score": round(common_share * 100), "assessment_full_score": round(assessment_share * 100),
            "assessment_point_count": len(points), "point_weights": details}


def compute_grade_level(score: int) -> str:
    return next(label for threshold, label in GRADE_LEVELS if score >= threshold)


def _student_lines(transcript: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("content") or "").strip() for item in transcript if item.get("role") == "user" and str(item.get("content") or "").strip()]


def _common_ratios(lines: list[str], required_rate: float, ai_review: dict[str, Any], deductions: dict[str, Any]) -> list[dict[str, Any]]:
    joined = "\n".join(lines)
    turns = len(lines)
    questions = sum(any(token in line for token in ("?", "？", "吗", "什么", "哪里", "是否", "谁", "怎么", "为什么")) for line in lines)
    polite = sum(any(token in line for token in ("请", "麻烦", "您", "你好", "配合", "说明")) for line in lines)
    categories = sum(any(token in joined for token in group) for group in (("姓名", "身份", "电话"), ("时间", "几点"), ("地点", "地址", "哪里"), ("经过", "发生"), ("伤情", "危险", "安全"), ("证据", "监控", "物证")))
    closure = sum(any(token in line for token in ("下一步", "后续", "处理", "笔录", "移交", "告知")) for line in lines)
    seeds = [min(.93, .58 + polite * .055 + min(turns, 6) * .018), min(.9, .32 + questions * .075 + min(categories, 6) * .052 + required_rate * .08),
             min(.88, .30 + categories * .072 + required_rate * .16), min(.86, .42 + closure * .12 + required_rate * .12 + min(turns, 5) * .015)]
    llm_items = {str(item.get("dimension")): item for item in ai_review.get("common_reviews") or ai_review.get("dimensions") or [] if isinstance(item, dict)}
    result = []
    for (dimension, focus), seed in zip(COMMON_DIMENSIONS, seeds):
        item = llm_items.get(dimension) or {}
        try:
            llm_ratio = float(item.get("score")) / float(item.get("full_score"))
            ratio = max(0, min(1, llm_ratio))
        except (TypeError, ValueError, ZeroDivisionError):
            ratio = seed
        cap = .9 if dimension == COMMON_DIMENSIONS[0][0] and required_rate >= .35 else .75 if dimension == COMMON_DIMENSIONS[0][0] else .5 if required_rate <= 0 else .62 if required_rate < .35 else .72 if required_rate < .55 else .82 if required_rate < .75 else 1.0
        try:
            deduct_ratio = min(.35, float(deductions.get(dimension) or 0) / 25.0)
        except (TypeError, ValueError):
            deduct_ratio = 0
        result.append({"dimension": dimension, "focus": focus, "ratio": max(0, min(cap, ratio) - deduct_ratio),
                       "reason": str(item.get("reason") or item.get("comment") or focus), "evidence": [f"学员: {line[:120]}" for line in lines[:2]]})
    return result


def build_adaptive_report(*, transcript: list[dict[str, Any]], point_results: list[dict[str, Any]], action_results: list[dict[str, Any]], ai_review: dict[str, Any], scene_type: str, rule_checks: dict[str, Any], report_header: dict[str, Any], knowledge_refs: list[str]) -> dict[str, Any]:
    points = dedupe_assessment_result_points(point_results)
    weighting = calculate_adaptive_weighting(points)
    required = [point for point in points if point.get("required", True)]
    required_rate = sum(_ratio(point) for point in required) / len(required) if required else 1.0
    common = _common_ratios(_student_lines(transcript), required_rate, ai_review, rule_checks.get("deductions") or {})
    common_each = weighting["common_full_score"] / 4
    scores = []
    for item in common:
        full = round(common_each)
        level = "excellent" if item["ratio"] >= .9 else "good" if item["ratio"] >= .75 else "fair" if item["ratio"] >= .6 else "weak"
        scores.append({"group": "common", "dimension": item["dimension"], "score": round(full * item["ratio"]), "full_score": full,
                       "reason": item["reason"], "evidence": item["evidence"], "level": level, "status": level})
    weight_map = {item["id"]: item for item in weighting["point_weights"]}
    enriched = []
    for point in points:
        weight = weight_map.get(point.get("id"), {})
        full = int(weight.get("full_score") or 0)
        score = round(full * _ratio(point))
        enriched_point = {**point, "difficulty_level": weight.get("difficulty_level"), "difficulty_factor": weight.get("difficulty_factor"),
                          "score_share": weight.get("score_share", 0), "weighted_score": score, "full_score": full, "completion_ratio": _ratio(point)}
        enriched.append(enriched_point)
        scores.append({"group": "assessment", "dimension": f"考察点：{point.get('label')}", "score": score, "full_score": full,
                       "reason": point.get("feedback") or f"考察点状态：{point.get('status', 'missed')}", "evidence": point.get("evidence") or [],
                       "status": point.get("status", "missed"), "assessment_point_id": point.get("id"), "required": bool(point.get("required", True))})
    lines = _student_lines(transcript)
    joined = "\n".join(lines)
    red_flags = [{"key": key, "label": rule["label"], "cap": rule["cap"], "evidence": [word for word in rule["keywords"] if word in joined][:3]}
                 for key, rule in RED_FLAG_RULES.items() if any(word in joined for word in rule["keywords"])]
    caps = []
    if len(lines) <= 1: caps.append({"type": "turn_count", "cap": 55, "reason": "有效学员发言不超过 1 轮"})
    elif len(lines) == 2: caps.append({"type": "turn_count", "cap": 68, "reason": "有效学员发言不超过 2 轮"})
    elif len(lines) == 3: caps.append({"type": "turn_count", "cap": 78, "reason": "有效学员发言不超过 3 轮"})
    if required_rate < .35: caps.append({"type": "required_completion", "cap": 58, "reason": "必考点完成度低于 35%"})
    elif required_rate < .55: caps.append({"type": "required_completion", "cap": 70, "reason": "必考点完成度低于 55%"})
    elif required_rate < .75: caps.append({"type": "required_completion", "cap": 82, "reason": "必考点完成度低于 75%"})
    caps.extend({"type": "red_flag", "cap": item["cap"], "reason": item["label"]} for item in red_flags)
    uncapped = max(0, min(100, sum(int(item["score"]) for item in scores)))
    applied_cap = min([item["cap"] for item in caps], default=100)
    total = min(uncapped, applied_cap)
    if uncapped and total != uncapped:
        factor = total / uncapped
        for item in scores:
            item["score"] = round(item["score"] * factor)
        difference = total - sum(item["score"] for item in scores)
        if scores: scores[-1]["score"] = max(0, min(scores[-1]["full_score"], scores[-1]["score"] + difference))
    strengths = _strings(ai_review.get("strengths") or []) + [f"已覆盖考察点：{p.get('label')}" for p in enriched if p.get("status") == "hit"]
    improvements = _strings(ai_review.get("improvements") or []) + [f"必考点未完成：{p.get('label')}" for p in enriched if p.get("required", True) and p.get("status") == "missed"]
    return {
        "scores": scores, "total_score": total, "uncapped_total_score": uncapped, "grade_level": compute_grade_level(total),
        "assessment_point_results": enriched, "action_results": action_results, "strengths": _strings(strengths)[:6], "improvements": _strings(improvements)[:8],
        "suggestions": str(ai_review.get("suggestions") or "建议按通用能力和本场景考察点逐项复训，先补齐必考点，再提升追问质量与收尾表达。"),
        "overall_comment": str(ai_review.get("summary") or "已依据通用四维评分与动态考察点完成评估。"),
        "closure_summary": rule_checks.get("closure_summary") or {},
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "knowledge_refs": knowledge_refs,
        "evaluation_meta": {"scoring_version": SCORING_VERSION, "policy_version": CURRENT_EVALUATION_POLICY_VERSION, "scene_type": scene_type,
            "weighting": weighting, "score_caps": {"caps": caps, "final_cap": applied_cap}, "red_flags": red_flags, "rule_findings": rule_checks.get("findings") or [],
            "report_header": report_header, "prompt_version": "formal_report_v3", "scene_template_version": "formal_report_v3",
            "cap_audit": {"policy_version": CURRENT_EVALUATION_POLICY_VERSION, "policy_source": "evaluation_skill",
                "cap_sources": caps or [{"type": "no_cap", "cap": 100, "reason": "未触发上限规则"}], "applied_cap": applied_cap,
                "before_cap_score": uncapped, "after_cap_score": total, "score_items_total": sum(item["score"] for item in scores), "valid": total <= applied_cap,
                "enforced_at": datetime.now(timezone.utc).isoformat()}},
    }


def enforce_final_score_policy(report: dict[str, Any], *, policy_source: str = "unknown") -> dict[str, Any]:
    if not isinstance(report, dict):
        return report
    meta = report.setdefault("evaluation_meta", {})
    score_caps = meta.setdefault("score_caps", {"caps": [], "final_cap": 100})
    caps = [item for item in score_caps.get("caps") or [] if isinstance(item, dict) and isinstance(item.get("cap"), (int, float))]
    applied_cap = min([int(item["cap"]) for item in caps], default=int(score_caps.get("final_cap") or 100))
    before = max(0, min(100, round(float(report.get("total_score") or 0))))
    after = min(before, applied_cap)
    report.setdefault("uncapped_total_score", before)
    report["total_score"] = after
    report["grade_level"] = compute_grade_level(after)
    meta["scoring_version"] = SCORING_VERSION
    meta["policy_version"] = CURRENT_EVALUATION_POLICY_VERSION
    score_caps["final_cap"] = applied_cap
    meta["cap_audit"] = {"policy_version": CURRENT_EVALUATION_POLICY_VERSION, "policy_source": policy_source,
        "cap_sources": caps or [{"type": "no_cap", "cap": 100, "reason": "未触发上限规则"}], "applied_cap": applied_cap,
        "before_cap_score": before, "after_cap_score": after, "score_items_total": sum(int(item.get("score") or 0) for item in report.get("scores") or []),
        "valid": after <= applied_cap, "enforced_at": datetime.now(timezone.utc).isoformat()}
    return report


def is_current_evaluation_report(report: Any) -> bool:
    if not isinstance(report, dict) or not isinstance(report.get("evaluation_meta"), dict):
        return False
    meta = report["evaluation_meta"]
    audit = meta.get("cap_audit")
    try:
        score, cap, after = round(float(report.get("total_score"))), int(audit.get("applied_cap")), int(audit.get("after_cap_score"))
    except (AttributeError, TypeError, ValueError):
        return False
    return meta.get("scoring_version") == SCORING_VERSION and meta.get("policy_version") == CURRENT_EVALUATION_POLICY_VERSION and audit.get("valid") is True and 0 <= score <= cap <= 100 and after == score
