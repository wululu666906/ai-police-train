import json
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import database
import models
import schemas
from routers.auth import get_current_user
from services.ai_service import (
    _build_available_actions,
    _build_feedback,
    _build_recommended_questions,
    _evaluate_stage_coverage,
    _get_case_type,
    _get_stage_config,
    _get_stage_goal,
    _infer_truth_stage,
    _role_state_label,
    apply_training_action,
    generate_dialogue,
)
from services.evaluation_service import evaluate_session, is_current_evaluation_report
from services.classroom_service import (
    get_session_assignment_context,
    link_session_to_assignment,
    sync_assignment_submission_for_session,
    validate_assignment_training_access,
)
from services.case_knowledge_service import try_sync_case_to_knowledge
from services.persona_engine import build_persona_profile
from services.recommended_questions_service import (
    build_recommended_question_items,
    filter_stale_missing_requirements_for_history,
    serialize_message_history,
)
from services.multi_role_service import serialize_scene_roles
from services.role_resolver import resolve_scene_role
from services.text_repair import repair_payload, repair_text
from services.dialogue_sequence_service import build_intake_sequence_feedback, merge_sequence_feedback
from services.opening_turn_service import (
    ensure_opening_turn,
    infer_session_scene_kind,
    redact_dispatch_brief_for_student,
    redact_first_impression_for_student,
    resolve_dialogue_mode,
)
from services.training_runtime_service import dump_runtime_state, load_runtime_state

router = APIRouter(prefix="/training", tags=["Training"])

SESSION_MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "session_media")
ALLOWED_ARTIFACT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "audio/webm": ".webm",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "video/webm": ".webm",
    "video/mp4": ".mp4",
}


def safe_json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _redact_internal_role_fields(result: dict[str, Any]) -> dict[str, Any]:
    """Remove model-only reasoning from learner-facing training responses."""
    result.pop("inner_thought", None)
    result.pop("persona_hint", None)
    for turn in result.get("reply_turns") or []:
        if isinstance(turn, dict):
            turn.pop("inner_thought", None)
    return result


def _artifact_url(file_path: str | None) -> str | None:
    if not file_path:
        return None
    return f"/static/session_media/{file_path.replace(os.sep, '/')}"


def _serialize_artifact(artifact: models.TrainingSessionArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "session_id": artifact.session_id,
        "artifact_type": artifact.artifact_type,
        "file_url": _artifact_url(artifact.file_path),
        "mime_type": artifact.mime_type,
        "file_size": artifact.file_size,
        "duration_seconds": artifact.duration_seconds,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


def _get_accessible_training_session(db: Session, session_id: int, current_user: models.User) -> models.TrainingSession:
    session = (
        db.query(models.TrainingSession)
        .filter(
            models.TrainingSession.id == session_id,
            models.TrainingSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or not accessible")
    return session


def _clamp_score(value, fallback):
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0, min(100, numeric))


def _session_emotion(session: models.TrainingSession, *, fallback: int = 50) -> int:
    return _clamp_score(session.current_emotion, fallback)


def _session_trust(session: models.TrainingSession, *, fallback: int = 30) -> int:
    return _clamp_score(session.current_trust, fallback)


def _as_utc_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)


def _default_state_snapshot(role: models.Role | None, case: models.Case | None, scene: models.Scene | None):
    snapshot = {
        "cooperation": _clamp_score(getattr(role, "init_trust", 30), 30),
        "risk": 50,
        "clarity": 50,
    }
    if role is None:
        return snapshot
    try:
        persona_profile = build_persona_profile(role, case, scene)
    except Exception:
        persona_profile = {}
    snapshot["cooperation"] = _clamp_score(persona_profile.get("init_cooperation"), snapshot["cooperation"])
    snapshot["risk"] = _clamp_score(persona_profile.get("init_risk"), snapshot["risk"])
    snapshot["clarity"] = _clamp_score(persona_profile.get("init_expression_clarity"), snapshot["clarity"])
    return snapshot


def _resolve_state_snapshot(
    runtime_state: dict | None,
    role: models.Role | None,
    case: models.Case | None,
    scene: models.Scene | None,
    *,
    current_trust: int | None = None,
):
    snapshot = _default_state_snapshot(role, case, scene)
    raw_snapshot = (runtime_state or {}).get("state_snapshot") if isinstance(runtime_state, dict) else {}
    if isinstance(raw_snapshot, dict):
        snapshot["cooperation"] = _clamp_score(raw_snapshot.get("cooperation"), snapshot["cooperation"])
        snapshot["risk"] = _clamp_score(raw_snapshot.get("risk"), snapshot["risk"])
        snapshot["clarity"] = _clamp_score(raw_snapshot.get("clarity"), snapshot["clarity"])
    if current_trust is not None:
        snapshot["cooperation"] = _clamp_score(current_trust, snapshot["cooperation"])
    return snapshot


def _serialize_session_response(
    session: models.TrainingSession,
    role: models.Role | None,
    case: models.Case | None,
    scene: models.Scene | None,
):
    runtime_state = load_runtime_state(session.revealed_info)
    state_snapshot = _resolve_state_snapshot(
        runtime_state,
        role,
        case,
        scene,
        current_trust=session.current_trust,
    )
    return schemas.Session(
        id=session.id,
        scene_id=session.scene_id,
        user_id=session.user_id,
        created_at=_as_utc_datetime(session.created_at),
        training_started_at=_as_utc_datetime(session.training_started_at),
        training_finished_at=_as_utc_datetime(session.training_finished_at),
        current_stage=session.current_stage or "",
        current_emotion=_session_emotion(session),
        current_trust=state_snapshot["cooperation"],
        current_cooperation=state_snapshot["cooperation"],
        current_risk=state_snapshot["risk"],
        current_clarity=state_snapshot["clarity"],
        revealed_info=session.revealed_info or dump_runtime_state(runtime_state),
        status=session.status,
        messages=[],
    )


def get_owned_session(db: Session, session_id: int, user_id: int) -> models.TrainingSession:
    session = (
        db.query(models.TrainingSession)
        .filter(
            models.TrainingSession.id == session_id,
            models.TrainingSession.user_id == user_id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or not accessible")
    return session


def _mark_session_training_finished(session: models.TrainingSession, finished_at: datetime | None = None) -> None:
    end_time = finished_at or datetime.utcnow()
    if session.training_started_at is None:
        session.training_started_at = session.created_at or end_time
    session.training_finished_at = session.training_finished_at or end_time


def _build_session_guidance(
    db: Session,
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    role: models.Role | None,
    messages: list[models.Message],
    current_stage_goal: str | None,
):
    runtime_state = load_runtime_state(session.revealed_info)
    state_snapshot = _resolve_state_snapshot(
        runtime_state,
        role,
        case,
        scene,
        current_trust=session.current_trust,
    )
    session_emotion = _session_emotion(session)
    revealed_info = [repair_text(str(item)) for item in runtime_state.get("revealed_info", []) if str(item).strip()]
    case_type = _get_case_type(case)
    stage_goal = current_stage_goal or ""
    stage_coverage = _evaluate_stage_coverage(
        messages,
        "",
        revealed_info,
        None,
        session.current_stage or "",
        stage_goal,
        scene,
        case_type=case_type,
    )
    truth_stage = _infer_truth_stage(state_snapshot["cooperation"], session_emotion)
    last_user_message = next(
        (repair_text(message.content) for message in reversed(messages) if message.role == "user"),
        "",
    )
    recent_message_payload = serialize_message_history(messages)
    stage_config = _get_stage_config(scene, session.current_stage or "", case_type=case_type)
    custom_prompts = list(stage_config.get("recommended_prompts") or []) if stage_config else []
    scene_kind = infer_session_scene_kind(scene, session)
    effective_missing_requirements = filter_stale_missing_requirements_for_history(
        stage_coverage.get("missing") or [],
        recent_messages=recent_message_payload,
        revealed_info=revealed_info,
        last_user_message=last_user_message,
        use_intake_flow=scene_kind == "intake",
    )
    recommended_question_items = build_recommended_question_items(
        current_stage=session.current_stage or "",
        current_stage_goal=stage_goal,
        case_type=case_type,
        case_title=case.title if case else "",
        scene_name=scene.name if scene else "",
        scene_kind=scene_kind,
        role_name=role.name if role else "",
        role_type=role.role_type if role else "",
        scene_roles=[
            {"name": item.get("name"), "speakable": item.get("speakable", True), "role_type": item.get("role_type")}
            for item in serialize_scene_roles(db, scene, case, runtime_state=runtime_state)
        ]
        if scene
        else [],
        revealed_info=revealed_info,
        missing_requirements=effective_missing_requirements,
        truth_stage=truth_stage,
        emotion=session_emotion,
        cooperation=state_snapshot["cooperation"],
        last_user_message=last_user_message,
        recent_messages=recent_message_payload,
        custom_prompts=custom_prompts,
        use_llm=bool(last_user_message or any(message.role == "assistant" for message in messages)),
    )
    recommended_questions = [item["text"] for item in recommended_question_items]
    communication_feedback = _build_feedback(
        last_user_message,
        state_snapshot["cooperation"],
        session_emotion,
        truth_stage,
        risk=state_snapshot["risk"],
        clarity=state_snapshot["clarity"],
    )
    if effective_missing_requirements:
        missing_preview = "、".join(effective_missing_requirements[:3])
        if last_user_message.strip():
            communication_feedback["message"] = f"继续补齐这些关键项会更稳：{missing_preview}。"
        else:
            communication_feedback["message"] = f"当前阶段建议先补齐：{missing_preview}。"
        communication_feedback["all_messages"] = list(
            dict.fromkeys([communication_feedback["message"], *communication_feedback.get("all_messages", [])])
        )
        communication_feedback["tags"] = list(dict.fromkeys(["stage_gap", *communication_feedback.get("tags", [])]))
    elif not last_user_message.strip():
        if scene_kind == "intake" and any(message.role == "assistant" for message in messages):
            bootstrap_message = "报警人已说明情况，建议先确认其安全与事件性质，再核实地点、时间和身份。"
        elif scene_kind == "intake":
            bootstrap_message = "110 已接通，等待报警人先说明情况；随后再按顺序核实安全、地点、时间和身份。"
        else:
            bootstrap_message = "训练已恢复，建议先从时间、地点、人物或风险情况打开第一轮问询。"
        communication_feedback = {
            "level": "info",
            "tags": ["session_resume"],
            "message": bootstrap_message,
            "all_messages": [bootstrap_message],
        }

    if scene_kind == "intake":
        sequence_feedback = build_intake_sequence_feedback(messages, last_user_message, revealed_info)
        communication_feedback = merge_sequence_feedback(communication_feedback, sequence_feedback)

    stage_config = _get_stage_config(scene, session.current_stage or "", case_type=case_type)
    available_actions = _build_available_actions(
        stage_config,
        runtime_state.get("completed_action_ids") or [],
    )

    return {
        "stage_completion_requirements": stage_coverage["requirements"],
        "stage_completion_satisfied": stage_coverage["satisfied"],
        "stage_completion_missing": stage_coverage["missing"],
        "recommended_questions": recommended_questions,
        "recommended_question_items": recommended_question_items,
        "communication_feedback": communication_feedback,
        "role_state_label": _role_state_label(
            state_snapshot["cooperation"],
            session_emotion,
            state_snapshot["risk"],
            state_snapshot["clarity"],
        ),
        "truth_stage": truth_stage,
        "available_actions": available_actions,
        "assessment_progress": runtime_state.get("assessment_progress") or stage_coverage.get("assessment_progress"),
        "completed_point_ids": runtime_state.get("completed_point_ids") or [],
        "completed_action_ids": runtime_state.get("completed_action_ids") or [],
        "auto_finish_ready": bool(runtime_state.get("auto_finish_ready", False)),
        "closure_summary": runtime_state.get("closure_summary") or {},
        "state_snapshot": state_snapshot,
    }


def _trigger_auto_evaluation_if_needed(
    db: Session,
    session_id: int,
    user_id: int,
    result: dict,
):
    if result.get("auto_finished"):
        session = get_owned_session(db, session_id, user_id)
        _mark_session_training_finished(session)
        session.status = "evaluating"
        db.commit()
        report = evaluate_session(db, session_id, user_id)
        if report and "error" not in report:
            session.status = "finished"
            if not session.evaluation_result:
                session.evaluation_result = json.dumps(report, ensure_ascii=False)
            db.commit()
            try:
                sync_assignment_submission_for_session(db, session_id, user_id, report)
            except Exception as error:
                print(f"Assignment submission sync failed: {error}")
            result["evaluation_ready"] = True
        else:
            result["evaluation_ready"] = False
    return result


@router.post("/start/{scene_id}", response_model=schemas.Session)
def start_training(
    scene_id: int,
    assignment_id: int | None = Query(default=None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        scene = db.query(models.Scene).filter(models.Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="Training scene not found")
        if assignment_id is not None:
            validate_assignment_training_access(db, assignment_id, current_user, scene_id)

        if assignment_id is not None:
            latest_session = (
                db.query(models.TrainingSession)
                .join(
                    models.AssignmentSubmission,
                    models.AssignmentSubmission.training_session_id == models.TrainingSession.id,
                )
                .filter(
                    models.TrainingSession.user_id == current_user.id,
                    models.TrainingSession.scene_id == scene_id,
                    models.AssignmentSubmission.assignment_id == assignment_id,
                )
                .order_by(models.TrainingSession.created_at.desc())
                .first()
            )
        else:
            assigned_session_ids = db.query(models.AssignmentSubmission.training_session_id).filter(
                models.AssignmentSubmission.training_session_id.isnot(None)
            )
            latest_session = (
                db.query(models.TrainingSession)
                .filter(
                    models.TrainingSession.user_id == current_user.id,
                    models.TrainingSession.scene_id == scene_id,
                    ~models.TrainingSession.id.in_(assigned_session_ids),
                )
                .order_by(models.TrainingSession.created_at.desc())
                .first()
            )
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
        if case:
            try_sync_case_to_knowledge(case)
        role = resolve_scene_role(db, scene, case)
        if latest_session and latest_session.status == "active":
            if latest_session.training_started_at is None:
                latest_session.training_started_at = latest_session.created_at or datetime.utcnow()
            ensure_opening_turn(db, latest_session, scene, case, role)
            if assignment_id is not None:
                link_session_to_assignment(db, assignment_id, current_user, latest_session, scene)
            db.commit()
            return _serialize_session_response(latest_session, role, case, scene)
        latest_evaluation = safe_json_loads(latest_session.evaluation_result, {}) if latest_session else {}
        latest_has_final_report = (
            isinstance(latest_evaluation, dict)
            and bool(latest_evaluation)
            and isinstance(latest_evaluation.get("total_score"), (int, float))
        )
        if latest_session and latest_session.status == "evaluating" and not latest_has_final_report:
            if latest_session.training_started_at is None:
                latest_session.training_started_at = latest_session.created_at or datetime.utcnow()
            if assignment_id is not None:
                link_session_to_assignment(db, assignment_id, current_user, latest_session, scene)
            db.commit()
            return _serialize_session_response(latest_session, role, case, scene)
        stage_config = _get_stage_config(scene, "", case_type=_get_case_type(case))
        initial_runtime_state = load_runtime_state([])
        initial_state_snapshot = _default_state_snapshot(role, case, scene)
        initial_runtime_state["state_snapshot"] = initial_state_snapshot
        first_stage = str(stage_config.get("stage_name") or "初始接触")

        new_session = models.TrainingSession(
            user_id=current_user.id,
            scene_id=scene_id,
            current_stage=first_stage,
            current_emotion=role.init_emotion if role else 50,
            current_trust=initial_state_snapshot["cooperation"],
            revealed_info=dump_runtime_state(initial_runtime_state),
            training_started_at=datetime.utcnow(),
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        ensure_opening_turn(db, new_session, scene, case, role)
        if assignment_id is not None:
            link_session_to_assignment(db, assignment_id, current_user, new_session, scene)
        db.commit()
        db.refresh(new_session)
        return _serialize_session_response(new_session, role, case, scene)
    except HTTPException:
        raise
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to start training: {error}") from error


@router.post("/chat/{session_id}")
def training_chat(
    session_id: int,
    message: schemas.MessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Training session has already been finished")
    if not message.content or not message.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    result = generate_dialogue(
        db,
        session_id,
        message.content.strip(),
        current_user.id,
        target_role_name=message.target_role_name,
    )
    if not result:
        raise HTTPException(status_code=502, detail="训练环境暂时无法响应，请稍后重试")
    if result.get("inner_thought") == "ACCESS_DENIED":
        raise HTTPException(status_code=403, detail="当前账号无权访问这条训练会话")
    if result.get("inner_thought") == "ERROR":
        detail = result.get("communication_feedback", {}).get("message") or "训练环境暂时无法响应，请稍后重试"
        raise HTTPException(status_code=502, detail=detail)

    result.pop("state_contract", None)
    result.pop("last_postcheck", None)
    result.pop("state_influence_metrics", None)
    # Internal reasoning and persona summaries are never part of the learner API.
    _redact_internal_role_fields(result)

    return _trigger_auto_evaluation_if_needed(db, session_id, current_user.id, result)


@router.post("/chat-stream/{session_id}")
def training_chat_stream(
    session_id: int,
    message: schemas.MessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Training session has already been finished")
    if not message.content or not message.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    result = generate_dialogue(
        db,
        session_id,
        message.content.strip(),
        current_user.id,
        target_role_name=message.target_role_name,
    )
    if not result:
        raise HTTPException(status_code=502, detail="训练环境暂时无法响应，请稍后重试")
    if result.get("inner_thought") == "ACCESS_DENIED":
        raise HTTPException(status_code=403, detail="当前账号无权访问这条训练会话")
    if result.get("inner_thought") == "ERROR":
        detail = result.get("communication_feedback", {}).get("message") or "训练环境暂时无法响应，请稍后重试"
        raise HTTPException(status_code=502, detail=detail)

    result.pop("state_contract", None)
    result.pop("last_postcheck", None)
    result.pop("state_influence_metrics", None)
    _redact_internal_role_fields(result)

    def _event(name: str, payload: dict[str, Any]) -> str:
        return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _stream():
        yield _event("meta", {
            "session_id": session_id,
            "status": session.status,
            "auto_finished": bool(result.get("auto_finished")),
            "reply_turns": len(result.get("reply_turns") or []),
        })
        reply_turns = result.get("reply_turns") or []
        for index, turn in enumerate(reply_turns):
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            chunk_payload = {
                "index": index,
                "speaker_name": turn.get("speaker_name") or "",
                "speaker_role_id": turn.get("speaker_role_id"),
                "content": content,
                "is_last": index == len(reply_turns) - 1,
            }
            yield _event("chunk", chunk_payload)
            time.sleep(0.03)
        yield _event("done", {
            "response": result.get("response"),
            "reply_sequence": result.get("reply_sequence"),
            "reply_turns": result.get("reply_turns"),
            "active_speakers": result.get("active_speakers"),
            "scene_roles": result.get("scene_roles"),
            "routing_summary": result.get("routing_summary"),
            "addressing_warning": result.get("addressing_warning"),
            "recognized_actions": result.get("recognized_actions"),
            "available_actions": result.get("available_actions"),
            "assessment_progress": result.get("assessment_progress"),
            "completed_point_ids": result.get("completed_point_ids"),
            "completed_action_ids": result.get("completed_action_ids"),
            "auto_finish_ready": result.get("auto_finish_ready"),
            "auto_finished": result.get("auto_finished"),
            "redirect_to_evaluation": result.get("redirect_to_evaluation"),
            "closure_summary": result.get("closure_summary"),
            "updated_emotion": result.get("updated_emotion"),
            "updated_trust": result.get("updated_trust"),
            "updated_cooperation": result.get("updated_cooperation"),
            "updated_risk": result.get("updated_risk"),
            "updated_clarity": result.get("updated_clarity"),
            "new_fact_revealed": result.get("new_fact_revealed"),
            "is_stage_completed": result.get("is_stage_completed"),
            "current_stage": result.get("current_stage"),
            "current_stage_goal": result.get("current_stage_goal"),
            "stage_transition_message": result.get("stage_transition_message"),
            "stage_completion_requirements": result.get("stage_completion_requirements"),
            "stage_completion_satisfied": result.get("stage_completion_satisfied"),
            "stage_completion_missing": result.get("stage_completion_missing"),
            "recommended_questions": result.get("recommended_questions"),
            "recommended_question_items": result.get("recommended_question_items"),
            "communication_feedback": result.get("communication_feedback"),
            "role_state_label": result.get("role_state_label"),
            "truth_stage": result.get("truth_stage"),
        })

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/action/{session_id}")
def training_action(
    session_id: int,
    payload: schemas.ActionTrigger,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Training session has already been finished")
    if not payload.action_id or not payload.action_id.strip():
        raise HTTPException(status_code=400, detail="Action id cannot be empty")

    result = apply_training_action(
        db,
        session_id,
        payload.action_id.strip(),
        payload.note or "",
        current_user.id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    if result.get("inner_thought") == "ACCESS_DENIED":
        raise HTTPException(status_code=403, detail="当前账号无权访问这条训练会话")
    if result.get("inner_thought") == "INVALID_ACTION":
        detail = result.get("communication_feedback", {}).get("message") or "该动作与当前阶段不匹配"
        raise HTTPException(status_code=400, detail=detail)
    if result.get("inner_thought") == "ERROR":
        detail = result.get("communication_feedback", {}).get("message") or "动作处理失败，请稍后重试"
        raise HTTPException(status_code=502, detail=detail)

    return _trigger_auto_evaluation_if_needed(db, session_id, current_user.id, result)


@router.get("/session/{session_id}", response_model=schemas.SessionDetail)
def get_session(
    session_id: int,
    for_report: bool = Query(False, description="报告页轻量读取：跳过训练中推荐问法和自动补全逻辑"),
    assignment_id: int | None = Query(default=None, description="作业报告校验：确保会话属于指定作业"),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    if assignment_id is not None:
        linked_submission = (
            db.query(models.AssignmentSubmission)
            .filter(
                models.AssignmentSubmission.assignment_id == assignment_id,
                models.AssignmentSubmission.training_session_id == session.id,
                models.AssignmentSubmission.user_id == current_user.id,
            )
            .first()
        )
        if not linked_submission:
            raise HTTPException(status_code=404, detail="该报告不属于当前班级作业")

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    role = resolve_scene_role(db, scene, case)

    if not for_report:
        ensure_opening_turn(db, session, scene, case, role)
        db.commit()

    messages = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    repaired_messages = [
        schemas.Message(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=repair_text(message.content),
            speaker_role_id=getattr(message, "speaker_role_id", None),
            speaker_name=repair_text(getattr(message, "speaker_name", None)) if getattr(message, "speaker_name", None) else None,
            created_at=_as_utc_datetime(message.created_at),
        )
        for message in messages
    ]

    current_goal = _get_stage_goal(scene, session.current_stage or "", case_type=_get_case_type(case))
    runtime_state = load_runtime_state(session.revealed_info)
    state_snapshot = _resolve_state_snapshot(
        runtime_state,
        role,
        case,
        scene,
        current_trust=session.current_trust,
    )
    repaired_revealed_info = json.dumps(runtime_state.get("revealed_info") or [], ensure_ascii=False)

    if not for_report and session.status == "finished" and session.evaluation_result:
        refreshed_report = evaluate_session(db, session.id, current_user.id)
        if isinstance(refreshed_report, dict) and not refreshed_report.get("error"):
            session.evaluation_result = json.dumps(refreshed_report, ensure_ascii=False)
            db.commit()

    repaired_evaluation_result = session.evaluation_result
    if repaired_evaluation_result:
        try:
            repaired_payload = repair_payload(json.loads(repaired_evaluation_result))
            if for_report and not is_current_evaluation_report(repaired_payload):
                refreshed_report = evaluate_session(db, session.id, current_user.id, force_recompute=True)
                if isinstance(refreshed_report, dict) and not refreshed_report.get("error"):
                    repaired_payload = refreshed_report
                    session.evaluation_result = json.dumps(refreshed_report, ensure_ascii=False)
                    db.commit()
            repaired_evaluation_result = json.dumps(repaired_payload, ensure_ascii=False)
        except Exception:
            repaired_evaluation_result = repair_text(repaired_evaluation_result)

    if for_report:
        guidance_payload = {
            "stage_completion_requirements": [],
            "stage_completion_satisfied": [],
            "stage_completion_missing": [],
            "recommended_questions": [],
            "recommended_question_items": [],
            "communication_feedback": None,
            "persona_hint": None,
            "role_state_label": None,
            "truth_stage": None,
            "available_actions": [],
            "assessment_progress": None,
            "completed_point_ids": [],
            "completed_action_ids": [],
            "auto_finish_ready": False,
            "closure_summary": None,
        }
    else:
        guidance_payload = _build_session_guidance(
            db,
            session=session,
            scene=scene,
            case=case,
            role=role,
            messages=messages,
            current_stage_goal=current_goal,
        )

    return schemas.SessionDetail(
        id=session.id,
        scene_id=session.scene_id,
        user_id=session.user_id,
        created_at=_as_utc_datetime(session.created_at),
        training_started_at=_as_utc_datetime(session.training_started_at),
        training_finished_at=_as_utc_datetime(session.training_finished_at),
        current_stage=session.current_stage or "训练中",
        current_stage_goal=current_goal,
        current_emotion=_session_emotion(session),
        current_trust=state_snapshot["cooperation"],
        current_cooperation=state_snapshot["cooperation"],
        current_risk=state_snapshot["risk"],
        current_clarity=state_snapshot["clarity"],
        revealed_info=repaired_revealed_info or dump_runtime_state(runtime_state),
        evaluation_result=repaired_evaluation_result,
        status=session.status,
        case_title=repair_text(case.title) if case else "未知案例",
        case_type=repair_text(case.case_type) if case else "其他",
        case_background=repair_text(case.background) if case else "暂无背景描述",
        case_original_content=repair_text(case.original_content) if case else "暂无原文信息",
        role_name=repair_text(role.name) if role else "对话对象",
        role_status=repair_text(role.status) if role else "正常",
        scene_roles=[
            schemas.SceneRoleBrief(**item)
            for item in serialize_scene_roles(db, scene, case, runtime_state=runtime_state)
        ],
        scene_name=repair_text(scene.name) if scene else "训练场景",
        scene_kind=infer_session_scene_kind(scene, session),
        dialogue_mode=resolve_dialogue_mode(scene, session),
        difficulty=repair_text(scene.difficulty) if scene else "中等",
        dispatch_brief=redact_dispatch_brief_for_student(scene, session),
        first_impression=redact_first_impression_for_student(scene, session),
        structured_data=(
            json.dumps(repair_payload(safe_json_loads(case.structured_data, {})), ensure_ascii=False)
            if case and case.structured_data
            else None
        ),
        stage_completion_requirements=guidance_payload["stage_completion_requirements"],
        stage_completion_satisfied=guidance_payload["stage_completion_satisfied"],
        stage_completion_missing=guidance_payload["stage_completion_missing"],
        recommended_questions=guidance_payload["recommended_questions"],
        recommended_question_items=[
            schemas.RecommendedQuestionItem(**item) for item in guidance_payload.get("recommended_question_items") or []
        ],
        communication_feedback=guidance_payload["communication_feedback"],
        role_state_label=guidance_payload["role_state_label"],
        truth_stage=guidance_payload["truth_stage"],
        available_actions=guidance_payload["available_actions"],
        assessment_progress=guidance_payload["assessment_progress"],
        completed_point_ids=guidance_payload["completed_point_ids"],
        completed_action_ids=guidance_payload["completed_action_ids"],
        auto_finish_ready=guidance_payload["auto_finish_ready"],
        closure_summary=guidance_payload["closure_summary"],
        assignment_context=get_session_assignment_context(db, session.id, current_user.id),
        artifacts=[_serialize_artifact(item) for item in (session.artifacts or [])],
        messages=repaired_messages,
    )


@router.get("/session/{session_id}/artifacts")
def get_session_artifacts(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = _get_accessible_training_session(db, session_id, current_user)
    return {
        "items": [_serialize_artifact(item) for item in (session.artifacts or [])],
    }


@router.post("/session/{session_id}/artifacts/upload")
async def upload_session_artifact(
    session_id: int,
    artifact_file: UploadFile = File(...),
    artifact_type: str = Form("screenshot"),
    duration_seconds: int | None = Form(default=None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = _get_accessible_training_session(db, session_id, current_user)
    content_type = (artifact_file.content_type or "").strip().lower()
    if content_type not in ALLOWED_ARTIFACT_TYPES:
        raise HTTPException(status_code=400, detail="不支持的附件格式")

    data = await artifact_file.read()
    if not data:
        raise HTTPException(status_code=400, detail="附件为空")

    os.makedirs(SESSION_MEDIA_DIR, exist_ok=True)
    safe_type = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in artifact_type).strip("_") or "screenshot"
    relative_dir = os.path.join(str(session.user_id), str(session.id))
    abs_dir = os.path.join(SESSION_MEDIA_DIR, relative_dir)
    os.makedirs(abs_dir, exist_ok=True)
    ext = ALLOWED_ARTIFACT_TYPES[content_type]
    filename = f"{safe_type}_{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join(relative_dir, filename)
    abs_path = os.path.join(SESSION_MEDIA_DIR, rel_path)
    with open(abs_path, "wb") as file_handle:
        file_handle.write(data)

    artifact = models.TrainingSessionArtifact(
        session_id=session.id,
        artifact_type=safe_type,
        file_path=rel_path,
        mime_type=content_type,
        file_size=len(data),
        duration_seconds=duration_seconds if duration_seconds and duration_seconds > 0 else None,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return _serialize_artifact(artifact)


@router.post("/finish/{session_id}")
def finish_training(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)

    user_message_count = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id, models.Message.role == "user")
        .count()
    )
    if user_message_count <= 0:
        raise HTTPException(status_code=400, detail="At least one valid round of dialogue is required before finishing")

    if session.status == "active":
        _mark_session_training_finished(session)
        session.status = "evaluating"
        db.commit()
    elif session.training_finished_at is None:
        _mark_session_training_finished(session)
        db.commit()

    report = evaluate_session(db, session_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Session not found")
    if report.get("error"):
        session.status = "active"
        session.training_finished_at = None
        db.commit()
        raise HTTPException(status_code=502, detail=report["error"])
    try:
        sync_assignment_submission_for_session(db, session_id, current_user.id, report)
    except Exception as error:
        print(f"Assignment submission sync failed: {error}")
    return report


@router.post("/re-evaluate/{session_id}")
def re_evaluate_training(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)

    user_message_count = (
        db.query(models.Message)
        .filter(models.Message.session_id == session.id, models.Message.role == "user")
        .count()
    )
    if user_message_count <= 0:
        raise HTTPException(status_code=400, detail="At least one valid round of dialogue is required before evaluation")

    if session.training_started_at is None or session.training_finished_at is None:
        _mark_session_training_finished(session)
        db.commit()

    session.status = "evaluating"
    session.evaluation_result = None
    db.commit()

    report = evaluate_session(db, session.id, current_user.id, force_recompute=True)
    if not report:
        raise HTTPException(status_code=404, detail="Session not found")
    if report.get("error"):
        raise HTTPException(status_code=502, detail=report["error"])
    try:
        sync_assignment_submission_for_session(db, session.id, current_user.id, report)
    except Exception as error:
        print(f"Assignment submission sync failed: {error}")
    return report


@router.delete("/session/{session_id}")
def delete_training_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    linked_submission = (
        db.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.training_session_id == session.id,
            models.AssignmentSubmission.user_id == current_user.id,
        )
        .first()
    )
    if linked_submission:
        raise HTTPException(status_code=400, detail="班级作业训练记录请在班级作业中查看，不能从普通训练历史删除")

    db.query(models.Message).filter(models.Message.session_id == session.id).delete(synchronize_session=False)
    db.delete(session)
    db.commit()

    return {"message": "训练记录已删除", "session_id": session_id}


@router.delete("/sessions/active")
def delete_active_training_sessions(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    assigned_session_ids = db.query(models.AssignmentSubmission.training_session_id).filter(
        models.AssignmentSubmission.training_session_id.isnot(None)
    )
    active_sessions = (
        db.query(models.TrainingSession)
        .filter(
            models.TrainingSession.user_id == current_user.id,
            models.TrainingSession.status == "active",
            ~models.TrainingSession.id.in_(assigned_session_ids),
        )
        .all()
    )
    session_ids = [session.id for session in active_sessions]

    if session_ids:
        db.query(models.Message).filter(models.Message.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(session_ids)).delete(synchronize_session=False)
        db.commit()

    return {
        "message": "进行中的训练记录已删除",
        "deleted_count": len(session_ids),
        "session_ids": session_ids,
    }
