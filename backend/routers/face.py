from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user, require_admin_user
from services.face_service import (
    create_liveness_challenge,
    count_session_failures,
    count_session_failures_total,
    count_session_monitor_failures,
    count_session_monitor_failures_total,
    engine_status,
    is_face_session_terminated_by_policy,
    read_upload,
    record_event,
    register_profile,
    serialize_profile,
    verify_frame,
    FACE_MAX_FAILURES,
    localize_face_reason,
)


router = APIRouter(prefix="/face", tags=["Face Verification"])


class VerifyFrameRequest(BaseModel):
    frame: str
    liveness_score: float | None = None
    challenge_id: str | None = None
    liveness_actions: list[dict[str, Any]] | None = None
    quality_metrics: dict[str, Any] | None = None


class FaceEventRequest(BaseModel):
    reason: str = "人脸离开画面"
    event_type: str = "offline"
    liveness_score: float | None = None


def _get_student(db: Session, student_id: int) -> models.User:
    student = db.query(models.User).filter(models.User.id == student_id, models.User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="学员不存在")
    return student


def _get_owned_session(db: Session, session_id: int, current_user: models.User) -> models.TrainingSession:
    query = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id)
    if current_user.role != "admin":
        query = query.filter(models.TrainingSession.user_id == current_user.id)
    session = query.first()
    if not session:
        raise HTTPException(status_code=404, detail="训练会话不存在或无权访问")
    return session


@router.get("/engine")
def get_engine_status(_: models.User = Depends(get_current_user)) -> dict[str, Any]:
    return engine_status()


@router.get("/students/{student_id}/profile")
def get_face_profile(
    student_id: int,
    db: Session = Depends(database.get_db),
    _: models.User = Depends(require_admin_user),
) -> dict[str, Any]:
    _get_student(db, student_id)
    profile = db.query(models.FaceProfile).filter(models.FaceProfile.student_id == student_id).first()
    return serialize_profile(profile)


@router.post("/students/{student_id}/register")
async def register_face_profile(
    student_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(database.get_db),
    _: models.User = Depends(require_admin_user),
) -> dict[str, Any]:
    student = _get_student(db, student_id)
    raw = await read_upload(file)
    profile = register_profile(db, student, raw)
    return serialize_profile(profile)


@router.get("/session/{session_id}/status")
def get_session_face_status(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, current_user)
    profile = db.query(models.FaceProfile).filter(models.FaceProfile.student_id == session.user_id).first()
    monitor_failure_count = count_session_monitor_failures(db, session.id)
    monitor_failure_total = count_session_monitor_failures_total(db, session.id)
    failure_total = count_session_failures_total(db, session.id)
    terminated_by_policy = is_face_session_terminated_by_policy(db, session.id)
    return {
        "registered": profile is not None,
        "failure_count": failure_total,
        "monitor_failure_count": monitor_failure_count,
        "monitor_failure_total": monitor_failure_total,
        "failure_total": failure_total,
        "max_failures": FACE_MAX_FAILURES,
        "terminated_by_policy": terminated_by_policy,
        "terminated": terminated_by_policy or session.status in {"evaluating", "finished"},
        "session_status": session.status,
    }


@router.get("/session/{session_id}/challenge")
def get_session_face_challenge(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, current_user)
    if session.status in {"evaluating", "finished"}:
        raise HTTPException(status_code=409, detail="训练会话已结束，无法发放活体挑战。")
    return create_liveness_challenge(session.id, session.user_id)


@router.post("/session/{session_id}/verify")
def verify_session_face(
    session_id: int,
    payload: VerifyFrameRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, current_user)
    if session.status in {"evaluating", "finished"}:
        return {
            "passed": False,
            "status": "ignored",
            "reason": "训练会话已结束，人脸验证请求已忽略。",
            "failure_count": count_session_failures(db, session.id),
            "max_failures": FACE_MAX_FAILURES,
            "terminated": True,
        }
    return verify_frame(
        db,
        session=session,
        frame_data_url=payload.frame,
        event_type="verify",
        liveness_score=payload.liveness_score,
        challenge_id=payload.challenge_id,
        liveness_actions=payload.liveness_actions,
        client_quality=payload.quality_metrics,
    )


@router.post("/session/{session_id}/heartbeat")
def heartbeat_session_face(
    session_id: int,
    payload: VerifyFrameRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, current_user)
    if session.status in {"evaluating", "finished"}:
        return {
            "passed": False,
            "status": "ignored",
            "reason": "训练会话已结束，人脸监控请求已忽略。",
            "failure_count": count_session_failures(db, session.id),
            "max_failures": FACE_MAX_FAILURES,
            "terminated": True,
        }
    return verify_frame(
        db,
        session=session,
        frame_data_url=payload.frame,
        event_type="heartbeat",
        liveness_score=payload.liveness_score,
        client_quality=payload.quality_metrics,
    )


@router.post("/session/{session_id}/event")
def record_session_face_event(
    session_id: int,
    payload: FaceEventRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    session = _get_owned_session(db, session_id, current_user)
    if session.status in {"evaluating", "finished"}:
        return {
            "passed": False,
            "status": "ignored",
            "reason": "训练会话已结束，人脸事件已忽略。",
            "failure_count": count_session_failures(db, session.id),
            "max_failures": FACE_MAX_FAILURES,
            "terminated": True,
        }
    event = record_event(
        db,
        session=session,
        event_type=payload.event_type,
        status="failed",
        reason=payload.reason,
        liveness_score=payload.liveness_score,
    )
    terminated = is_face_session_terminated_by_policy(db, session.id) or session.status in {"evaluating", "finished"}
    return {
        "passed": False,
        "status": "terminated" if terminated else "failed",
        "reason": localize_face_reason(event.reason),
        "failure_count": event.failure_count,
        "max_failures": FACE_MAX_FAILURES,
        "terminated": terminated,
        "event_id": event.id,
    }
