from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user
from services.multimodal_service import build_scene_performance_report, record_frame, record_voice_event


router = APIRouter(prefix="/multimodal", tags=["Multimodal"])


class FrameAnalysisRequest(BaseModel):
    frame: str


class VoiceEventRequest(BaseModel):
    event_type: str
    transcript: str = ""
    duration_ms: int | None = None
    audio_level: float | None = None
    repeated: bool = False


@router.post("/session/{session_id}/frame")
def analyze_session_frame(
    session_id: int,
    payload: FrameAnalysisRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    return record_frame(db, session_id=session_id, user=current_user, frame_data_url=payload.frame)


@router.post("/session/{session_id}/voice-event")
def create_session_voice_event(
    session_id: int,
    payload: VoiceEventRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    return record_voice_event(
        db,
        session_id=session_id,
        user=current_user,
        event_type=payload.event_type,
        transcript=payload.transcript,
        duration_ms=payload.duration_ms,
        audio_level=payload.audio_level,
        repeated=payload.repeated,
    )


@router.get("/session/{session_id}/summary")
def get_session_summary(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    query = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id)
    if current_user.role != "admin":
        query = query.filter(models.TrainingSession.user_id == current_user.id)
    if not query.first():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Training session not found")
    return build_scene_performance_report(db, session_id)
