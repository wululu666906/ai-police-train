import json
import logging
import os
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

import database
import models
import schemas
from routers.auth import get_current_user, require_admin_user
from services.agent_training_service import (
    _build_available_actions,
    _build_feedback,
    _evaluate_stage_coverage,
    _get_case_type,
    _get_stage_config,
    _get_stage_goal,
    _infer_truth_stage,
    _role_state_label,
    apply_training_action,
    generate_dialogue,
    generate_opening_dialogue,
    resolve_revealed_fact_texts,
)
from services.agent_training_service import evaluate_session, is_current_evaluation_report
from services.classroom_service import (
    get_session_assignment_context,
    link_session_to_assignment,
    sync_assignment_submission_for_session,
    validate_assignment_training_access,
)
from services.face_service import (
    apply_face_termination_report_metadata,
    build_adaptive_fallback_report,
    has_successful_session_verification,
)
from services.training_view_service import (
    filter_internal_prompt_messages,
    resolve_role_initial_state,
    build_recommended_question_items,
    filter_stale_missing_requirements_for_history,
    serialize_message_history,
    serialize_scene_roles,
    build_intake_sequence_feedback,
    merge_sequence_feedback,
    ensure_opening_turn,
    infer_session_scene_kind,
    redact_dispatch_brief_for_student,
    redact_first_impression_for_student,
    _compose_plot_opening_turns,
    _opening_prompts_from_scene,
    _stage_prompts_from_scene,
    resolve_dialogue_mode,
)
from services.role_resolver import resolve_scene_role
from services.text_repair import repair_payload, repair_text
from services.training_runtime_service import dump_runtime_state, load_runtime_state
from services.object_storage_service import MEDIA_BUCKET, build_object_key, delete_media_assets, get_media_asset, guess_content_type, object_storage, upsert_media_asset

router = APIRouter(prefix="/training", tags=["Training"])
logger = logging.getLogger(__name__)

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
    result.pop("role_intents", None)
    for turn in result.get("reply_turns") or []:
        if isinstance(turn, dict):
            turn.pop("inner_thought", None)
    return result


def _sse_event(name: str, payload: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"


def _serialize_opening_message(item: models.Message) -> dict[str, Any]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "role": item.role,
        "content": repair_text(item.content),
        "speaker_role_id": item.speaker_role_id,
        "speaker_name": repair_text(item.speaker_name) if item.speaker_name else None,
        "created_at": _as_utc_datetime(item.created_at),
    }


def _opening_payload(db: Session, session: models.TrainingSession, scene=None, case=None) -> dict[str, Any]:
    runtime_state = load_runtime_state(session.revealed_info)
    opening_ids = [int(item) for item in runtime_state.get("opening_message_ids") or [] if str(item).isdigit()]
    query = db.query(models.Message).filter(models.Message.session_id == session.id)
    if opening_ids:
        query = query.filter(models.Message.id.in_(opening_ids))
    elif runtime_state.get("opening_delivered"):
        query = query.filter(models.Message.role == "assistant")
    else:
        return {
            "opening_delivered": False,
            "messages": [],
            "recommended_questions": [],
            "recommended_question_items": [],
            "scene_roles": serialize_scene_roles(db, scene, case, runtime_state=runtime_state) if scene else [],
        }
    messages = filter_internal_prompt_messages(
        query.order_by(models.Message.created_at.asc(), models.Message.id.asc()).all()
    )
    recommended_question_items = build_recommended_question_items(
        stored_items=runtime_state.get("recommended_question_items") or [],
    )
    scene_roles = serialize_scene_roles(db, scene, case, runtime_state=runtime_state) if scene else []
    roles_by_name = {str(item.get("name") or ""): item for item in scene_roles}
    serialized_messages = []
    for item in messages:
        payload = _serialize_opening_message(item)
        role_meta = roles_by_name.get(str(payload.get("speaker_name") or ""))
        if role_meta:
            payload["avatar_id"] = role_meta.get("avatar_id")
            payload["avatar_url"] = role_meta.get("avatar_url")
        serialized_messages.append(payload)
    return {
        "opening_delivered": bool(runtime_state.get("opening_delivered")),
        "messages": serialized_messages,
        "recommended_questions": [item["text"] for item in recommended_question_items],
        "recommended_question_items": recommended_question_items,
        "scene_roles": scene_roles,
    }


def _persist_plot_opening(db: Session, session, scene, case, role, extra_prompts: list | None = None) -> None:
    state = load_runtime_state(session.revealed_info)
    if state.get("opening_delivered"):
        return
    message_ids = []
    for item in _compose_plot_opening_turns(scene, case, role):
        message = models.Message(
            session_id=session.id,
            role="assistant",
            content=item.get("content") or "",
            speaker_role_id=item.get("speaker_role_id"),
            speaker_name=item.get("speaker_name"),
        )
        db.add(message)
        db.flush()
        message_ids.append(message.id)
    prompts = [item for item in (extra_prompts or []) if isinstance(item, dict) and str(item.get("text") or "").strip()]
    prompts = prompts or list(state.get("recommended_question_items") or []) or _opening_prompts_from_scene(scene, case)
    state.update({
        "opening_delivered": True,
        "opening_message_ids": message_ids,
        "recommended_question_items": prompts,
    })
    session.revealed_info = dump_runtime_state(state)


def _ensure_opening_payload(
    db: Session,
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    role: models.Role | None,
    current_user: models.User | None = None,
) -> dict[str, Any]:
    delivered = ensure_opening_turn(db, session, scene, case, role)
    if not delivered and current_user is not None:
        result = generate_opening_dialogue(db, session.id, current_user.id)
        if result.get("inner_thought") in {"ERROR", "ACCESS_DENIED"} or not result.get("reply_turns"):
            _persist_plot_opening(
                db,
                session,
                scene,
                case,
                role,
                extra_prompts=result.get("recommended_question_items") or [],
            )
    elif not delivered:
        _persist_plot_opening(db, session, scene, case, role)
    db.commit()
    db.refresh(session)
    return _opening_payload(db, session, scene=scene, case=case)


def _artifact_url(db: Session, artifact: models.TrainingSessionArtifact) -> str | None:
    asset = get_media_asset(db, "training_session_artifact", artifact.id, "file")
    if asset:
        return object_storage.url_for(asset)
    file_path = artifact.file_path
    if not file_path:
        return None
    return f"/static/session_media/{file_path.replace(os.sep, '/')}"


def _serialize_artifact(db: Session, artifact: models.TrainingSessionArtifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "session_id": artifact.session_id,
        "artifact_type": artifact.artifact_type,
        "file_url": _artifact_url(db, artifact),
        "mime_type": artifact.mime_type,
        "file_size": artifact.file_size,
        "duration_seconds": artifact.duration_seconds,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


def _get_accessible_training_session(db: Session, session_id: int, current_user: models.User) -> models.TrainingSession:
    return _get_readable_training_session(db, session_id, current_user)


def _managed_student_ids_subquery(db: Session, admin_id: int):
    """Return student accounts whose training records an admin may review.

    Platform admins are not scoped to self-created classes here; that matches
    video-training admin listings and the student directory, which are also global.
    """
    del admin_id
    return db.query(models.User.id).filter(models.User.role == "student")


def _is_managed_student(db: Session, admin_id: int, student_id: int) -> bool:
    del admin_id
    return (
        db.query(models.User.id)
        .filter(models.User.id == student_id, models.User.role == "student")
        .first()
        is not None
    )


def _format_utc_datetime(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    if getattr(value, "tzinfo", None):
        return value.isoformat()
    return f"{value.isoformat()}+00:00"


def _get_readable_training_session(db: Session, session_id: int, current_user: models.User) -> models.TrainingSession:
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or not accessible")
    if session.user_id == current_user.id:
        return session
    if current_user.role == "admin" and _is_managed_student(db, current_user.id, session.user_id):
        return session
    raise HTTPException(status_code=404, detail="Session not found or not accessible")


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
    return resolve_role_initial_state(role, case, scene)


def _resolve_state_snapshot(
    runtime_state: dict | None,
    role: models.Role | None,
    case: models.Case | None,
    scene: models.Scene | None,
    *,
    current_trust: int | None = None,
    current_emotion: int | None = None,
):
    snapshot = _default_state_snapshot(role, case, scene)
    raw_snapshot = (runtime_state or {}).get("state_snapshot") if isinstance(runtime_state, dict) else {}
    if isinstance(raw_snapshot, dict):
        snapshot["emotion"] = _clamp_score(raw_snapshot.get("emotion"), snapshot["emotion"])
        snapshot["cooperation"] = _clamp_score(raw_snapshot.get("cooperation"), snapshot["cooperation"])
        snapshot["risk"] = _clamp_score(raw_snapshot.get("risk"), snapshot["risk"])
        snapshot["clarity"] = _clamp_score(raw_snapshot.get("clarity"), snapshot["clarity"])
    has_runtime_snapshot = (runtime_state or {}).get("state_contract") == "four_dimensional_v1"
    if current_trust is not None and not has_runtime_snapshot:
        snapshot["cooperation"] = _clamp_score(current_trust, snapshot["cooperation"])
    if current_emotion is not None and not has_runtime_snapshot:
        snapshot["emotion"] = _clamp_score(current_emotion, snapshot["emotion"])
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
        current_emotion=session.current_emotion,
    )
    return schemas.Session(
        id=session.id,
        scene_id=session.scene_id,
        user_id=session.user_id,
        created_at=_as_utc_datetime(session.created_at),
        training_started_at=_as_utc_datetime(session.training_started_at),
        training_finished_at=_as_utc_datetime(session.training_finished_at),
        current_stage=session.current_stage or "",
        current_emotion=state_snapshot["emotion"],
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


def _sync_session_finished_from_report(session: models.TrainingSession) -> bool:
    """Promote sessions that already have a valid report but are stuck in active/evaluating."""
    if session.status == "finished" or not session.evaluation_result:
        return False
    try:
        report = json.loads(session.evaluation_result)
    except (TypeError, ValueError):
        return False
    if not isinstance(report, dict) or not is_current_evaluation_report(report):
        return False
    _mark_session_training_finished(session)
    session.status = "finished"
    return True


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
        current_emotion=session.current_emotion,
    )
    session_emotion = state_snapshot["emotion"]
    revealed_info = resolve_revealed_fact_texts(case, list(runtime_state.get("revealed_info") or []))
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
        stored_items=runtime_state.get("recommended_question_items") or [],
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
        # Session reads must remain deterministic and fast. Model-backed
        # recommendations are generated only as part of an explicit chat turn.
        use_llm=False,
    )
    if not recommended_question_items:
        # 只读会话：按当前阶段取方向种子；中后期禁止回退首阶段模板冒充新题。
        recommended_question_items = _stage_prompts_from_scene(
            scene,
            case,
            current_stage=session.current_stage or "",
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
        "role_state_label": runtime_state.get("role_state_label") or _role_state_label(
            state_snapshot["cooperation"], session_emotion, state_snapshot["risk"], state_snapshot["clarity"]
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


def _peek_face_termination_pending(session: models.TrainingSession) -> dict[str, Any] | None:
    runtime = load_runtime_state(session.revealed_info)
    pending = runtime.get("face_termination_pending")
    return pending if isinstance(pending, dict) else None


def _pop_face_termination_pending(session: models.TrainingSession) -> dict[str, Any] | None:
    runtime = load_runtime_state(session.revealed_info)
    pending = runtime.pop("face_termination_pending", None)
    if pending:
        session.revealed_info = dump_runtime_state(runtime)
    return pending if isinstance(pending, dict) else None


def _ensure_training_session_writable(session: models.TrainingSession) -> None:
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Training session has already been finished")
    if _peek_face_termination_pending(session):
        raise HTTPException(status_code=409, detail="训练已因人脸验证异常终止，正在进入评估")


def _face_termination_fallback_report(
    session: models.TrainingSession,
    face_pending: dict[str, Any],
    *,
    error: str,
) -> dict[str, Any]:
    failure_count = int(face_pending.get("failure_count") or 0)
    reason = str(face_pending.get("reason") or "")
    report = build_adaptive_fallback_report(
        session=session,
        failure_count=failure_count,
        reason=reason,
        error=error or "未知评估错误",
    )
    return apply_face_termination_report_metadata(
        report,
        failure_count=failure_count,
        reason=reason,
        evaluation_type="auto_terminated_fallback",
        policy_source="face_termination_fallback",
    )


def _persist_finished_report(
    db: Session,
    session: models.TrainingSession,
    report: dict[str, Any],
    *,
    user_id: int,
) -> dict[str, Any]:
    session.evaluation_result = json.dumps(report, ensure_ascii=False)
    _mark_session_training_finished(session)
    session.status = "finished"
    db.commit()
    try:
        sync_assignment_submission_for_session(db, session.id, user_id, report)
    except Exception as error:
        print(f"Assignment submission sync failed: {error}")
    return report


def _repair_stuck_face_evaluating_session(
    db: Session,
    session: models.TrainingSession,
    user_id: int,
) -> bool:
    """Repair sessions left in evaluating without a report after face auto-termination."""
    if session.evaluation_result:
        return False
    if session.status not in {"evaluating", "active"}:
        return False
    runtime = load_runtime_state(session.revealed_info)
    if runtime.get("face_eval_repair_done"):
        return False

    face_pending = _peek_face_termination_pending(session)
    if not isinstance(face_pending, dict):
        face_msg = (
            db.query(models.Message)
            .filter(
                models.Message.session_id == session.id,
                models.Message.role == "system",
                models.Message.content.like("%人脸验证连续异常%"),
            )
            .order_by(models.Message.id.desc())
            .first()
        )
        if not face_msg:
            return False
        face_pending = {"failure_count": 0, "reason": "人脸验证异常"}

    runtime["face_eval_repair_done"] = True
    session.revealed_info = dump_runtime_state(runtime)
    popped = _pop_face_termination_pending(session)
    if popped:
        face_pending = popped
    db.commit()

    user_messages = (
        db.query(models.Message)
        .filter(models.Message.session_id == session.id, models.Message.role == "user")
        .all()
    )
    user_message_count = len(filter_internal_prompt_messages(user_messages))
    if user_message_count <= 0:
        report = _face_termination_fallback_report(
            session,
            face_pending,
            error="训练尚未形成有效对话轮次",
        )
        _persist_finished_report(db, session, report, user_id=user_id)
        return True

    _mark_session_training_finished(session)
    session.status = "evaluating"
    db.commit()
    try:
        report = evaluate_session(db, session.id, user_id, force_recompute=True)
        if not report:
            raise RuntimeError("评估结果为空")
        if report.get("error"):
            raise RuntimeError(str(report.get("error")))
        report = apply_face_termination_report_metadata(
            report,
            failure_count=int(face_pending.get("failure_count") or 0),
            reason=str(face_pending.get("reason") or ""),
        )
    except Exception as exc:
        report = _face_termination_fallback_report(session, face_pending, error=str(exc))
    _persist_finished_report(db, session, report, user_id=user_id)
    return True


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
        role = resolve_scene_role(db, scene, case)
        if latest_session and latest_session.status == "active":
            if latest_session.training_started_at is None:
                latest_session.training_started_at = latest_session.created_at or datetime.utcnow()
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
        scene_role_link = (
            db.query(models.SceneRole)
            .filter(models.SceneRole.scene_id == scene.id, models.SceneRole.role_id == role.id)
            .first()
            if role else None
        )
        initial_state_snapshot = resolve_role_initial_state(role, case, scene, scene_role_link)
        initial_runtime_state["state_snapshot"] = initial_state_snapshot
        first_stage = str(stage_config.get("stage_name") or "初始接触")

        new_session = models.TrainingSession(
            user_id=current_user.id,
            scene_id=scene_id,
            current_stage=first_stage,
            current_emotion=initial_state_snapshot["emotion"],
            current_trust=initial_state_snapshot["cooperation"],
            revealed_info=dump_runtime_state(initial_runtime_state),
            training_started_at=datetime.utcnow(),
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
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


@router.post("/session/{session_id}/opening")
def start_session_opening(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="训练会话已结束，不能生成开场对话")
    if _peek_face_termination_pending(session):
        raise HTTPException(status_code=409, detail="训练已因人脸验证异常终止，正在进入评估")
    if not has_successful_session_verification(db, session.id):
        raise HTTPException(status_code=409, detail="请先完成人脸身份验证")

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    role = resolve_scene_role(db, scene, case) if scene else None
    return _ensure_opening_payload(db, session, scene, case, role, current_user)


def _opening_stream_response(
    db: Session,
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    role: models.Role | None,
    current_user: models.User,
    *,
    phase: str,
    log_context: str,
):
    def _stream():
        yield _sse_event("meta", {"session_id": session.id, "phase": phase})
        try:
            payload = _ensure_opening_payload(db, session, scene, case, role, current_user)
            messages = payload.get("messages") or []
            for index, message in enumerate(messages):
                yield _sse_event("thinking", {
                    "index": index,
                    "speaker_name": message.get("speaker_name") or "",
                    "speaker_role_id": message.get("speaker_role_id"),
                    "avatar_id": message.get("avatar_id"),
                    "avatar_url": message.get("avatar_url"),
                })
                yield _sse_event("chunk", {
                    "index": index,
                    "message_id": message.get("id"),
                    "speaker_name": message.get("speaker_name") or "",
                    "speaker_role_id": message.get("speaker_role_id"),
                    "avatar_id": message.get("avatar_id"),
                    "avatar_url": message.get("avatar_url"),
                    "content": message.get("content") or "",
                    "is_last": index == len(messages) - 1,
                })
                time.sleep(0.03)
            yield _sse_event("done", payload)
        except Exception:
            db.rollback()
            logger.exception("Failed to generate %s for session %s", log_context, session.id)
            yield _sse_event("error", {"message": "\u5f00\u573a\u5bf9\u8bdd\u751f\u6210\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"})

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/session/{session_id}/opening-stream")
def stream_session_opening(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="训练会话已结束，不能生成开场对话")
    if _peek_face_termination_pending(session):
        raise HTTPException(status_code=409, detail="训练已因人脸验证异常终止，正在进入评估")
    if not has_successful_session_verification(db, session.id):
        raise HTTPException(status_code=409, detail="请先完成人脸身份验证")

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    role = resolve_scene_role(db, scene, case) if scene else None
    return _opening_stream_response(
        db,
        session,
        scene,
        case,
        role,
        current_user,
        phase="generating",
        log_context="opening stream",
    )


@router.post("/chat/{session_id}")
def training_chat(
    session_id: int,
    message: schemas.MessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    _ensure_training_session_writable(session)
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
    # Internal reasoning and persona summaries are never part of the learner API.
    _redact_internal_role_fields(result)

    return result


@router.post("/chat-stream/{session_id}")
def training_chat_stream(
    session_id: int,
    message: schemas.MessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    _ensure_training_session_writable(session)
    if not message.content or not message.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    user_text = message.content.strip()
    target_role_name = message.target_role_name

    def _stream():
        def _generate_in_isolated_session():
            worker_db = database.SessionLocal()
            try:
                return generate_dialogue(
                    worker_db,
                    session_id,
                    user_text,
                    current_user.id,
                    target_role_name=target_role_name,
                )
            finally:
                worker_db.close()

        try:
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="training-chat") as executor:
                future = executor.submit(_generate_in_isolated_session)
                yield _sse_event("heartbeat", {"phase": "routing"})
                while not future.done():
                    time.sleep(0.75)
                    yield _sse_event("heartbeat", {"phase": "simulating"})
                result = future.result()
        except Exception as exc:
            logger.exception("Failed to stream training chat for session %s", session_id)
            yield _sse_event("error", {"message": str(exc) or "训练环境暂时无法响应，请稍后重试"})
            return

        if not result:
            yield _sse_event("error", {"message": "训练环境暂时无法响应，请稍后重试"})
            return
        if result.get("inner_thought") == "ACCESS_DENIED":
            yield _sse_event("error", {"message": "当前账号无权访问这条训练会话"})
            return
        if result.get("inner_thought") == "ERROR":
            detail = result.get("communication_feedback", {}).get("message") or "训练环境暂时无法响应，请稍后重试"
            yield _sse_event("error", {"message": detail})
            return

        result.pop("state_contract", None)
        result.pop("last_postcheck", None)
        _redact_internal_role_fields(result)
        reply_turns = result.get("reply_turns") or []
        for index, turn in enumerate(reply_turns):
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            yield _sse_event("chunk", {
                "index": index,
                "speaker_name": turn.get("speaker_name") or "",
                "speaker_role_id": turn.get("speaker_role_id"),
                "content": content,
                "is_last": index == len(reply_turns) - 1,
            })

        yield _sse_event("done", {
            "response": result.get("response"),
            "reply_sequence": result.get("reply_sequence"),
            "reply_turns": result.get("reply_turns"),
            "active_speakers": result.get("active_speakers"),
            "role_state_results": result.get("role_state_results"),
            "simulation_meta": result.get("simulation_meta"),
            "scene_roles": result.get("scene_roles"),
            "routing_summary": result.get("routing_summary"),
            "addressing_warning": result.get("addressing_warning"),
            "recognized_actions": result.get("recognized_actions"),
            "available_actions": result.get("available_actions"),
            "assessment_progress": result.get("assessment_progress"),
            "completed_point_ids": result.get("completed_point_ids"),
            "completed_action_ids": result.get("completed_action_ids"),
            "auto_finish_ready": result.get("auto_finish_ready"),
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

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/action/{session_id}")
def training_action(
    session_id: int,
    payload: schemas.ActionTrigger,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)
    _ensure_training_session_writable(session)
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

    return result


@router.get("/session/{session_id}", response_model=schemas.SessionDetail)
def get_session(
    session_id: int,
    for_report: bool = Query(False, description="报告页轻量读取：跳过训练中推荐问法和自动补全逻辑"),
    assignment_id: int | None = Query(default=None, description="作业报告校验：确保会话属于指定作业"),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = _get_readable_training_session(db, session_id, current_user)
    if for_report:
        try:
            _repair_stuck_face_evaluating_session(db, session, current_user.id)
            db.refresh(session)
        except Exception as error:
            print(f"Face termination report repair failed for session {session_id}: {error}")
    if _sync_session_finished_from_report(session):
        db.commit()
        try:
            report = json.loads(session.evaluation_result or "{}")
            if isinstance(report, dict):
                sync_assignment_submission_for_session(db, session.id, session.user_id, report)
        except Exception as error:
            print(f"Assignment submission sync failed: {error}")
    if assignment_id is not None:
        linked_submission = (
            db.query(models.AssignmentSubmission)
            .filter(
                models.AssignmentSubmission.assignment_id == assignment_id,
                models.AssignmentSubmission.training_session_id == session.id,
                models.AssignmentSubmission.user_id == session.user_id,
            )
            .first()
        )
        if not linked_submission:
            raise HTTPException(status_code=404, detail="该报告不属于当前班级作业")
        if current_user.role != "admin" and linked_submission.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="该报告不属于当前班级作业")

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    role = resolve_scene_role(db, scene, case)

    messages = filter_internal_prompt_messages(
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
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
        current_emotion=session.current_emotion,
    )
    repaired_revealed_info = json.dumps(
        resolve_revealed_fact_texts(case, list(runtime_state.get("revealed_info") or [])),
        ensure_ascii=False,
    )

    if not for_report and session.status == "finished" and session.evaluation_result:
        refreshed_report = evaluate_session(db, session.id, session.user_id)
        if isinstance(refreshed_report, dict) and not refreshed_report.get("error"):
            session.evaluation_result = json.dumps(refreshed_report, ensure_ascii=False)
            db.commit()

    repaired_evaluation_result = session.evaluation_result
    if repaired_evaluation_result:
        try:
            repaired_payload = repair_payload(json.loads(repaired_evaluation_result))
            if for_report and not is_current_evaluation_report(repaired_payload):
                refreshed_report = evaluate_session(db, session.id, session.user_id, force_recompute=True)
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
        opening_delivered=bool(runtime_state.get("opening_delivered")) or bool(messages),
        assignment_context=get_session_assignment_context(db, session.id, current_user.id),
        artifacts=[_serialize_artifact(db, item) for item in (session.artifacts or [])],
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
        "items": [_serialize_artifact(db, item) for item in (session.artifacts or [])],
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

    safe_type = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in artifact_type).strip("_") or "screenshot"
    ext = ALLOWED_ARTIFACT_TYPES[content_type]
    filename = f"{safe_type}_{uuid.uuid4().hex}{ext}"
    stored = object_storage.put_bytes(
        bucket=MEDIA_BUCKET,
        object_key=build_object_key(f"training-sessions/{session.user_id}/{session.id}", filename),
        data=data,
        content_type=guess_content_type(filename, content_type),
    )

    artifact = models.TrainingSessionArtifact(
        session_id=session.id,
        artifact_type=safe_type,
        file_path=stored.object_key,
        mime_type=content_type,
        file_size=len(data),
        duration_seconds=duration_seconds if duration_seconds and duration_seconds > 0 else None,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    upsert_media_asset(
        db,
        owner_type="training_session_artifact",
        owner_key=artifact.id,
        asset_kind="file",
        stored=stored,
        original_filename=artifact_file.filename or filename,
        content_type=content_type,
    )
    db.commit()
    return _serialize_artifact(db, artifact)


@router.post("/finish/{session_id}")
def finish_training(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)

    face_pending_peek = _peek_face_termination_pending(session)
    user_messages = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id, models.Message.role == "user")
        .all()
    )
    user_message_count = len(filter_internal_prompt_messages(user_messages))
    if user_message_count <= 0 and not face_pending_peek:
        raise HTTPException(status_code=400, detail="At least one valid round of dialogue is required before finishing")

    face_pending = _pop_face_termination_pending(session)
    if face_pending:
        db.commit()

    if session.status == "active" or (face_pending and session.status == "evaluating"):
        _mark_session_training_finished(session)
        session.status = "evaluating"
        db.commit()
    elif session.training_finished_at is None:
        _mark_session_training_finished(session)
        db.commit()

    if session.evaluation_result and not face_pending:
        try:
            existing = json.loads(session.evaluation_result)
        except (TypeError, ValueError):
            existing = None
        if isinstance(existing, dict) and is_current_evaluation_report(existing):
            if _sync_session_finished_from_report(session):
                db.commit()
                try:
                    sync_assignment_submission_for_session(db, session_id, current_user.id, existing)
                except Exception as error:
                    print(f"Assignment submission sync failed: {error}")
            return existing

    if face_pending and user_message_count <= 0:
        report = _face_termination_fallback_report(
            session,
            face_pending,
            error="训练尚未形成有效对话轮次",
        )
        return _persist_finished_report(db, session, report, user_id=current_user.id)

    try:
        report = evaluate_session(db, session_id, current_user.id, force_recompute=bool(face_pending))
    except Exception as exc:
        if not face_pending:
            if session.status == "evaluating":
                session.status = "active"
                session.training_finished_at = None
                db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        report = _face_termination_fallback_report(session, face_pending, error=str(exc))
        return _persist_finished_report(db, session, report, user_id=current_user.id)

    if not report:
        raise HTTPException(status_code=404, detail="Session not found")
    if report.get("error"):
        if face_pending:
            report = _face_termination_fallback_report(
                session,
                face_pending,
                error=str(report.get("error") or "未知评估错误"),
            )
            return _persist_finished_report(db, session, report, user_id=current_user.id)
        session.status = "active"
        session.training_finished_at = None
        db.commit()
        raise HTTPException(status_code=502, detail=report["error"])

    if face_pending:
        report = apply_face_termination_report_metadata(
            report,
            failure_count=int(face_pending.get("failure_count") or 0),
            reason=str(face_pending.get("reason") or ""),
        )

    return _persist_finished_report(db, session, report, user_id=current_user.id)


@router.post("/re-evaluate/{session_id}")
def re_evaluate_training(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = get_owned_session(db, session_id, current_user.id)

    user_messages = (
        db.query(models.Message)
        .filter(models.Message.session_id == session.id, models.Message.role == "user")
        .all()
    )
    user_message_count = len(filter_internal_prompt_messages(user_messages))
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
    _mark_session_training_finished(session)
    session.status = "finished"
    db.commit()
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
    artifact_ids = [
        item[0]
        for item in db.query(models.TrainingSessionArtifact.id)
        .filter(models.TrainingSessionArtifact.session_id == session.id)
        .all()
    ]
    for artifact_id in artifact_ids:
        delete_media_assets(db, owner_type="training_session_artifact", owner_key=artifact_id)
    db.query(models.TrainingSessionArtifact).filter(models.TrainingSessionArtifact.session_id == session.id).delete(
        synchronize_session=False
    )
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
        artifact_ids = [
            item[0]
            for item in db.query(models.TrainingSessionArtifact.id)
            .filter(models.TrainingSessionArtifact.session_id.in_(session_ids))
            .all()
        ]
        for artifact_id in artifact_ids:
            delete_media_assets(db, owner_type="training_session_artifact", owner_key=artifact_id)
        db.query(models.TrainingSessionArtifact).filter(models.TrainingSessionArtifact.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
        db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(session_ids)).delete(synchronize_session=False)
        db.commit()

    return {
        "message": "进行中的训练记录已删除",
        "deleted_count": len(session_ids),
        "session_ids": session_ids,
    }


@router.get("/admin/sessions")
def admin_list_text_sessions(
    username: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(require_admin_user),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)
    offset = (page - 1) * page_size
    normalized_status = (status or "").strip().lower()
    if normalized_status and normalized_status not in {"active", "evaluating", "finished"}:
        raise HTTPException(status_code=400, detail="Unsupported status filter")

    managed_student_ids = [row[0] for row in _managed_student_ids_subquery(db, current_user.id).all()]
    if not managed_student_ids:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "active_count": 0,
            "evaluating_count": 0,
            "finished_count": 0,
        }

    activity_subquery = (
        db.query(
            models.Message.session_id.label("session_id"),
            func.sum(case((models.Message.role == "user", 1), else_=0)).label("user_message_count"),
            func.count(models.Message.id).label("message_count"),
        )
        .group_by(models.Message.session_id)
        .subquery()
    )

    base_query = (
        db.query(
            models.TrainingSession.id.label("id"),
            models.TrainingSession.user_id.label("user_id"),
            models.User.username.label("username"),
            models.TrainingSession.status.label("status"),
            models.TrainingSession.evaluation_result.label("evaluation_result"),
            models.TrainingSession.created_at.label("created_at"),
            models.TrainingSession.training_started_at.label("training_started_at"),
            models.TrainingSession.training_finished_at.label("training_finished_at"),
            models.Scene.name.label("scene_name"),
            models.Scene.difficulty.label("difficulty"),
            models.Case.title.label("case_title"),
            models.Case.case_type.label("case_type"),
            func.coalesce(activity_subquery.c.message_count, 0).label("message_count"),
            func.coalesce(activity_subquery.c.user_message_count, 0).label("user_message_count"),
        )
        .join(models.User, models.User.id == models.TrainingSession.user_id)
        .outerjoin(activity_subquery, activity_subquery.c.session_id == models.TrainingSession.id)
        .outerjoin(models.Scene, models.Scene.id == models.TrainingSession.scene_id)
        .outerjoin(models.Case, models.Case.id == models.Scene.case_id)
        .filter(models.TrainingSession.user_id.in_(managed_student_ids))
    )

    if username:
        username_keyword = username.strip()
        if username_keyword:
            base_query = base_query.filter(models.User.username.contains(username_keyword))

    if keyword:
        content_keyword = keyword.strip()
        if content_keyword:
            base_query = base_query.filter(
                or_(
                    models.Case.title.contains(content_keyword),
                    models.Scene.name.contains(content_keyword),
                    models.Case.case_type.contains(content_keyword),
                )
            )

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid start_date") from exc
    if end_date:
        try:
            end_dt = datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid end_date") from exc
    if start_dt is not None:
        base_query = base_query.filter(models.TrainingSession.created_at >= start_dt)
    if end_dt is not None:
        base_query = base_query.filter(models.TrainingSession.created_at <= end_dt)

    status_counts = {
        "active": base_query.filter(models.TrainingSession.status == "active").count(),
        "evaluating": base_query.filter(models.TrainingSession.status == "evaluating").count(),
        "finished": base_query.filter(models.TrainingSession.status == "finished").count(),
    }

    filtered_query = base_query
    if normalized_status:
        filtered_query = base_query.filter(models.TrainingSession.status == normalized_status)

    total = filtered_query.count()
    rows = (
        filtered_query
        .order_by(models.TrainingSession.created_at.desc(), models.TrainingSession.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = []
    for row in rows:
        evaluation_result = safe_json_loads(row.evaluation_result, {})
        total_score = evaluation_result.get("total_score") if isinstance(evaluation_result, dict) else None
        display_time = (
            row.training_finished_at
            if row.status == "finished" and row.training_finished_at
            else row.training_started_at or row.created_at
        )
        items.append(
            {
                "id": row.id,
                "user_id": row.user_id,
                "username": row.username or "",
                "case_title": repair_text(row.case_title) if row.case_title else "未知案件",
                "case_type": repair_text(row.case_type) if row.case_type else "未分类",
                "scene_name": repair_text(row.scene_name) if row.scene_name else "未知场景",
                "difficulty": repair_text(row.difficulty) if row.difficulty else "中等",
                "status": row.status,
                "message_count": int(row.message_count or 0),
                "user_message_count": int(row.user_message_count or 0),
                "total_score": total_score,
                "created_at": _format_utc_datetime(row.created_at),
                "training_started_at": _format_utc_datetime(row.training_started_at),
                "training_finished_at": _format_utc_datetime(row.training_finished_at),
                "display_time": _format_utc_datetime(display_time),
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "active_count": status_counts["active"],
        "evaluating_count": status_counts["evaluating"],
        "finished_count": status_counts["finished"],
    }
