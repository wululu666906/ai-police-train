from __future__ import annotations

import json
from typing import Any

from ai_workflow_service.contracts import SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.domain.evaluation_engine import build_adaptive_report
from ai_workflow_service.domain.training_runtime import evaluate_points
from ai_workflow_service.skills.base import Skill

_STATUS_RANK = {"missed": 0, "miss": 0, "partial": 1, "hit": 2}


def _status_ratio(status: str, explicit: Any = None) -> float:
    normalized = str(status or "missed").strip().lower()
    if normalized == "hit":
        return 1.0
    if normalized in {"miss", "missed"}:
        return 0.0
    try:
        value = float(explicit if explicit is not None else 0.5)
    except (TypeError, ValueError):
        value = 0.5
    return max(0.25, min(0.85, value))


def _merge_point_reviews(rule_results: list[dict[str, Any]], ai_review: dict[str, Any]) -> list[dict[str, Any]]:
    """规则命中与 LLM 语义补判合并：取更高完成度，并保留证据。"""
    reviews = ai_review.get("point_reviews") if isinstance(ai_review, dict) else None
    if not isinstance(reviews, list) or not reviews:
        return rule_results

    by_id: dict[str, dict[str, Any]] = {}
    by_label: dict[str, dict[str, Any]] = {}
    for item in reviews:
        if not isinstance(item, dict):
            continue
        point_id = str(item.get("id") or item.get("point_id") or "").strip()
        label = str(item.get("label") or item.get("content") or "").strip()
        if point_id:
            by_id[point_id] = item
        if label:
            by_label[label[:40]] = item

    merged: list[dict[str, Any]] = []
    for point in rule_results:
        review = by_id.get(str(point.get("id") or "").strip()) or by_label.get(str(point.get("label") or "")[:40])
        if not review:
            merged.append(point)
            continue
        rule_status = str(point.get("status") or "missed")
        ai_status = str(review.get("status") or "").strip().lower()
        if ai_status not in _STATUS_RANK:
            merged.append(point)
            continue
        rule_rank = _STATUS_RANK.get(rule_status, 0)
        ai_rank = _STATUS_RANK.get(ai_status, 0)
        chosen_status = ai_status if ai_rank > rule_rank else rule_status
        rule_ratio = float(point.get("hit_ratio") or _status_ratio(rule_status))
        ai_ratio = _status_ratio(ai_status, review.get("completion_ratio") or review.get("hit_ratio"))
        chosen_ratio = max(rule_ratio, ai_ratio)
        evidence = list(dict.fromkeys([
            *(point.get("evidence") or []),
            *([str(item).strip() for item in (review.get("evidence") or []) if str(item).strip()]),
            *(["llm_semantic"] if ai_rank > rule_rank else []),
        ]))
        feedback = str(review.get("reason") or review.get("feedback") or point.get("feedback") or "").strip()
        merged.append({
            **point,
            "status": "hit" if chosen_ratio >= 0.5 else "partial" if chosen_ratio > 0 else "missed",
            "hit_ratio": round(min(chosen_ratio, 1.0), 4),
            "evidence": evidence,
            "feedback": feedback or point.get("feedback"),
            "scoring_source": "rule+llm" if review else "rule",
        })
    return merged


class EvaluationSkill(Skill):
    name = SkillName.evaluation
    next_stage = WorkflowStage.evaluated

    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def execute(self, request: WorkflowRequest) -> dict:
        transcript = list(request.payload.get("transcript") or [])
        assessment_points = list(request.payload.get("assessment_points") or [])
        expected_outcomes = [str(item).strip() for item in request.payload.get("expected_outcomes") or [] if str(item).strip()]
        if expected_outcomes and not assessment_points:
            assessment_points = [
                {
                    "id": f"eo_{index + 1}",
                    "label": text[:40],
                    "content": text,
                    "required": True,
                    "keywords": [],
                }
                for index, text in enumerate(expected_outcomes[:6])
            ]
        action_ids = [str(item.get("action_id") or item.get("id") or "") for item in request.payload.get("action_results") or [] if isinstance(item, dict)]
        completed = evaluate_points(assessment_points, transcript, action_ids)
        try:
            ai_review = self.llm.complete_json(
                system=(
                    "你是警务训练评估官。只依据结构化对话和本场景考察点给出审阅。"
                    "输出 JSON：summary、common_reviews、strengths、improvements、suggestions、point_reviews。"
                    "point_reviews 必须是数组，每项含 id（与考察点 id 一致）、status（hit/partial/missed）、"
                    "completion_ratio（0-1）、evidence（学员原话短摘录数组）、reason。"
                    "语义判定：学员用语不必与考察点原文一致，只要对话能合理证明完成该考察意图即可判 hit/partial。"
                    "不得自行计算最终总分。"
                ),
                user=json.dumps({
                    "transcript": transcript,
                    "expected_outcomes": expected_outcomes,
                    "assessment_points": completed,
                    "knowledge_refs": request.payload.get("knowledge_refs") or [],
                }, ensure_ascii=False),
                max_tokens=5000,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            ai_review = {}
        if not isinstance(ai_review, dict):
            ai_review = {}
        completed = _merge_point_reviews(completed, ai_review)
        report = build_adaptive_report(
            transcript=transcript, point_results=completed, action_results=list(request.payload.get("action_results") or []),
            ai_review=ai_review, scene_type=str(request.payload.get("scene_type") or "通用"),
            rule_checks=dict(request.payload.get("rule_checks") or {}), report_header=dict(request.payload.get("report_header") or {}),
            knowledge_refs=[str(item) for item in request.payload.get("knowledge_refs") or []],
        )
        return {"rule_results": completed, "ai_review": ai_review, "report": report}
