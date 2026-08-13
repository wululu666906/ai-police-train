from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Generator

from sqlalchemy.orm import Session

import models
from services.agent_workflow_client import AgentWorkflowUnavailable, agent_workflow_client
from services.role_resolver import resolve_scene_role
from services.text_repair import repair_text


def _json(value: Any, default: Any):
    if isinstance(value, type(default)):
        return value
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(default)) else default
    except (TypeError, ValueError):
        return default


def _get_case_type(case: models.Case | None) -> str:
    return repair_text(case.case_type) if case and case.case_type else "其他"


def _get_stage_config(scene: models.Scene | None, stage_name: str, *, case_type: str = "") -> dict[str, Any]:
    stages = _json(getattr(scene, "stages", None), [])
    for stage in stages:
        if isinstance(stage, dict) and stage.get("stage_name") == stage_name:
            return stage
    return stages[0] if stages and isinstance(stages[0], dict) else {"stage_name": stage_name or "初始接触"}


def _get_stage_goal(scene: models.Scene | None, stage_name: str, *, case_type: str = "") -> str:
    return str(_get_stage_config(scene, stage_name, case_type=case_type).get("stage_goal") or "")


def _infer_truth_stage(cooperation: int, emotion: int) -> str:
    return "配合" if cooperation >= 60 and emotion >= 50 else "抵触" if cooperation <= 30 or emotion <= 25 else "犹豫"


def _role_state_label(cooperation: int, emotion: int, risk: int, clarity: int) -> str:
    return _infer_truth_stage(cooperation, emotion)


def _evaluate_stage_coverage(*args, **kwargs) -> dict[str, Any]:
    return {"requirements": [], "satisfied": [], "missing": [], "assessment_progress": None}


def _build_feedback(*args, **kwargs) -> dict[str, Any]:
    return {"level": "info", "tags": [], "message": "", "all_messages": []}


def _build_available_actions(stage_config: dict | None, completed_ids: list) -> list:
    actions = (stage_config or {}).get("available_actions") or (stage_config or {}).get("action_catalog") or []
    return [item for item in actions if item.get("id") not in set(completed_ids or [])]


def _context(db: Session, session_id: int, user_id: int):
    session = db.query(models.TrainingSession).filter(
        models.TrainingSession.id == session_id,
        models.TrainingSession.user_id == user_id,
    ).first()
    if not session:
        return None
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    role = resolve_scene_role(db, scene, case) if scene else None
    messages = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.id.asc()).all()
    return session, scene, case, role, messages


def _build_payload(session, scene, case, role, messages, user_text: str) -> dict[str, Any]:
    structured = _json(getattr(case, "structured_data", None), {})
    facts = structured.get("facts") or structured.get("fact_cards") or []
    normalized_facts = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        normalized_facts.append({
            "fact_id": str(fact.get("fact_id") or fact.get("id") or f"F{index + 1:03d}"),
            "content": str(fact.get("content") or fact.get("fact") or ""),
            "source": str(fact.get("source") or ""),
            "known_by": list(fact.get("known_by") or []),
            "unknown_by": list(fact.get("unknown_by") or []),
            "secret": bool(fact.get("secret")),
        })
    role_id = str(getattr(role, "person_id", None) or getattr(role, "id", "role"))
    known = [str(item) for item in _json(getattr(role, "knows_facts", None), [])]
    hidden = [str(item) for item in _json(getattr(role, "hidden_truths", None), [])]
    return {
        "learner_input": user_text,
        "case_world": {
            "case_id": str(case.id),
            "title": repair_text(case.title or ""),
            "summary": repair_text(case.background or ""),
            "persons": [{"person_id": role_id, "name": repair_text(role.name), "role": role.role_type or "相关人员", "facts_known": known, "facts_hidden": hidden}],
            "facts": normalized_facts,
            "timeline": list(structured.get("timeline") or []),
            "locations": list(structured.get("locations") or []),
            "relationships": list(structured.get("relationships") or []),
        },
        "scene_world": {
            "scene_id": str(scene.id),
            "case_id": str(case.id),
            "name": repair_text(scene.name or "训练场景"),
            "environment": {"description": repair_text(scene.description or "")},
            "role_ids": [role_id],
            "rules": ["不得突破知识边界", "不得创造影响案情的新事实"],
        },
        "persona": {
            "person_id": role_id,
            "name": repair_text(role.name),
            "role": role.role_type or "相关人员",
            "traits": [repair_text(role.personality or "")],
            "speaking_style": repair_text(role.speaking_style or "自然口语"),
            "goals": ["按本人立场自然回应"],
            "known_fact_ids": known,
            "hidden_fact_ids": hidden,
            "state": {"trust": (session.current_trust or role.init_trust or 40) / 100, "pressure": 0.3, "anger": 0.2, "fear": 0.3},
        },
        "recent_dialogue": [{"role": item.role, "content": repair_text(item.content or ""), "speaker_name": item.speaker_name} for item in messages[-10:]],
    }


def generate_dialogue(db: Session, session_id: int, user_text: str, user_id: int, *, target_role_name: str | None = None) -> dict[str, Any]:
    context = _context(db, session_id, user_id)
    if not context:
        return {"inner_thought": "ACCESS_DENIED", "response": "", "communication_feedback": {"message": "无权访问"}}
    session, scene, case, role, messages = context
    if not all((scene, case, role)):
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": "训练上下文不完整"}}
    try:
        response = agent_workflow_client.execute(
            workflow_id=f"training-{session.id}",
            stage="TRAINING",
            skill="role_simulation",
            case_id=str(case.id),
            training_id=str(session.id),
            payload=_build_payload(session, scene, case, role, messages, user_text),
            idempotency_key=f"training-{session.id}-turn-{len(messages) + 1}",
        )
    except AgentWorkflowUnavailable as exc:
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": str(exc)}}
    result = response.get("result") or {}
    reply = str(result.get("reply") or "").strip()
    if not reply:
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": "Agent 未返回有效回复"}}
    db.add(models.Message(session_id=session.id, role="user", content=user_text))
    db.add(models.Message(session_id=session.id, role="assistant", content=reply, speaker_role_id=role.id, speaker_name=repair_text(role.name)))
    state = result.get("state") or {}
    session.current_trust = max(0, min(100, round(float(state.get("trust", 0.4)) * 100)))
    db.commit()
    return {
        "response": reply,
        "reply_turns": [{"speaker_name": repair_text(role.name), "speaker_role_id": role.id, "content": reply}],
        "updated_emotion": session.current_emotion or role.init_emotion or 50,
        "updated_trust": session.current_trust,
        "updated_cooperation": session.current_trust,
        "updated_risk": 50,
        "updated_clarity": 50,
        "new_fact_revealed": (result.get("revealed_fact_ids") or [None])[0],
        "is_stage_completed": False,
        "current_stage": session.current_stage,
    }


def iter_dialogue_stream_events(*args, **kwargs) -> Generator[dict[str, Any], None, None]:
    result = generate_dialogue(*args, **kwargs)
    yield {"event": "_result", "data": result}


def apply_training_action(db: Session, session_id: int, action_id: str, note: str, user_id: int) -> dict[str, Any]:
    context = _context(db, session_id, user_id)
    if not context:
        return {"inner_thought": "ACCESS_DENIED", "response": ""}
    session, _, _, _, _ = context
    if note.strip():
        db.add(models.Message(session_id=session.id, role="action", content=f"[{action_id}] {note.strip()}"))
        db.commit()
    return {"response": f"已执行: {action_id}", "inner_thought": "ACTION_OK", "recognized_actions": [action_id]}


def is_current_evaluation_report(report: Any) -> bool:
    return isinstance(report, dict) and report.get("engine") == "agent-workflow-v1"


def evaluate_session(db: Session, session_id: int, user_id: int | None = None, force_recompute: bool = False):
    query = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id)
    if user_id is not None:
        query = query.filter(models.TrainingSession.user_id == user_id)
    session = query.first()
    if not session:
        return None
    if session.evaluation_result and not force_recompute:
        existing = _json(session.evaluation_result, {})
        if is_current_evaluation_report(existing):
            return existing
    messages = db.query(models.Message).filter(models.Message.session_id == session.id).order_by(models.Message.id.asc()).all()
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    try:
        response = agent_workflow_client.execute(
            workflow_id=f"evaluation-{session.id}",
            stage="COMPLETED",
            skill="evaluation",
            training_id=str(session.id),
            case_id=str(scene.case_id) if scene else None,
            payload={"transcript": [{"role": item.role, "content": repair_text(item.content or "")} for item in messages], "assessment_points": []},
            idempotency_key=f"evaluation-{session.id}-{len(messages)}-{int(force_recompute)}",
        )
    except AgentWorkflowUnavailable as exc:
        raise RuntimeError(str(exc)) from exc
    evaluation = response.get("result") or {}
    review = evaluation.get("ai_review") or {}
    report = {
        "engine": "agent-workflow-v1",
        "generated_at": datetime.utcnow().isoformat(),
        "summary": review.get("summary", ""),
        "dimensions": review.get("dimensions", []),
        "deductions": review.get("deductions", []),
        "suggestions": review.get("suggestions", []),
        "assessment_point_results": evaluation.get("rule_results", []),
        "total_score": int(review.get("total_score") or 0),
    }
    session.evaluation_result = json.dumps(report, ensure_ascii=False)
    db.commit()
    return report
