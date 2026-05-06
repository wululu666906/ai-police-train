from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import database
import models
from routers.auth import get_current_user
from services.text_repair import repair_payload, repair_text

router = APIRouter(prefix="/student", tags=["Student"])


def get_session_activity_map(db: Session, session_ids: list[int]) -> dict[int, dict]:
    if not session_ids:
        return {}

    rows = (
        db.query(
            models.Message.session_id.label("session_id"),
            func.sum(case((models.Message.role == "user", 1), else_=0)).label("user_message_count"),
            func.sum(case((models.Message.role.in_(("assistant", "ai")), 1), else_=0)).label("assistant_message_count"),
            func.count(models.Message.id).label("message_count"),
        )
        .filter(models.Message.session_id.in_(session_ids))
        .group_by(models.Message.session_id)
        .all()
    )

    activity_map = {
        session_id: {
            "message_count": 0,
            "user_message_count": 0,
            "assistant_message_count": 0,
            "turn_count": 0,
            "is_empty_session": True,
        }
        for session_id in session_ids
    }

    for row in rows:
        user_message_count = int(row.user_message_count or 0)
        assistant_message_count = int(row.assistant_message_count or 0)
        message_count = int(row.message_count or 0)
        activity_map[row.session_id] = {
            "message_count": message_count,
            "user_message_count": user_message_count,
            "assistant_message_count": assistant_message_count,
            "turn_count": user_message_count,
            "is_empty_session": user_message_count == 0 and assistant_message_count == 0,
        }

    return activity_map


def get_case_title(case: Optional[models.Case]) -> str:
    if not case:
        return "未知案件"
    title = repair_text(case.title)
    return title or "未知案件"


@router.get("/cases")
def get_student_cases(
    case_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Case)

    if search:
        query = query.filter(models.Case.title.contains(search))
    if case_type:
        query = query.filter(models.Case.case_type == case_type)

    cases = query.all()
    result = []

    for case in cases:
        scenes = db.query(models.Scene).filter(models.Scene.case_id == case.id).all()
        scene_ids = [scene.id for scene in scenes]
        case_sessions = (
            db.query(models.TrainingSession)
            .filter(
                models.TrainingSession.user_id == current_user.id,
                models.TrainingSession.scene_id.in_(scene_ids),
            )
            .order_by(models.TrainingSession.created_at.desc())
            .all()
            if scene_ids
            else []
        )
        session_ids = [session.id for session in case_sessions]
        activity_map = get_session_activity_map(db, session_ids)

        latest_session_map = {}
        valid_train_count = 0
        empty_session_count = 0
        for session in case_sessions:
            latest_session_map.setdefault(session.scene_id, session)
            if activity_map.get(session.id, {}).get("is_empty_session", True):
                empty_session_count += 1
            else:
                valid_train_count += 1

        if difficulty:
            scenes = [scene for scene in scenes if scene.difficulty == difficulty]
            if not scenes:
                continue

        result.append(
            {
                "id": case.id,
                "title": get_case_title(case),
                "case_type": repair_text(case.case_type) or "未分类",
                "background": repair_text(case.background),
                "created_at": case.created_at.isoformat() if case.created_at else None,
                "train_count": valid_train_count,
                "empty_session_count": empty_session_count,
                "scenes": [
                    {
                        "id": scene.id,
                        "name": repair_text(scene.name),
                        "difficulty": repair_text(scene.difficulty),
                        "description": repair_text(scene.description),
                        "has_active_session": (
                            latest_session_map.get(scene.id).status == "active"
                            if scene.id in latest_session_map
                            else False
                        ),
                        "active_session_id": (
                            latest_session_map.get(scene.id).id
                            if scene.id in latest_session_map and latest_session_map.get(scene.id).status == "active"
                            else None
                        ),
                        "active_session_is_empty": (
                            activity_map.get(latest_session_map.get(scene.id).id, {}).get("is_empty_session", True)
                            if scene.id in latest_session_map and latest_session_map.get(scene.id).status == "active"
                            else False
                        ),
                    }
                    for scene in scenes
                ],
            }
        )

    return result


@router.get("/history")
def get_student_history(
    page: int = 1,
    page_size: int = 10,
    include_empty: bool = False,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 50)

    sessions = (
        db.query(models.TrainingSession)
        .filter(models.TrainingSession.user_id == current_user.id)
        .order_by(models.TrainingSession.created_at.desc())
        .all()
    )
    session_ids = [session.id for session in sessions]
    activity_map = get_session_activity_map(db, session_ids)

    session_items = []
    empty_session_count = 0
    for session in sessions:
        scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
        activity = activity_map.get(
            session.id,
            {
                "message_count": 0,
                "user_message_count": 0,
                "assistant_message_count": 0,
                "turn_count": 0,
                "is_empty_session": True,
            },
        )
        if activity["is_empty_session"]:
            empty_session_count += 1
            if not include_empty:
                continue

        revealed_info = repair_payload(session.revealed_info)
        revealed_info_count = len(revealed_info) if isinstance(revealed_info, list) else 0
        session_items.append(
            {
                "id": session.id,
                "case_title": get_case_title(case),
                "case_type": repair_text(case.case_type) if case else "未分类",
                "scene_name": repair_text(scene.name) if scene else "未知场景",
                "difficulty": repair_text(scene.difficulty) if scene else "中等",
                "status": session.status,
                "message_count": activity["message_count"],
                "user_message_count": activity["user_message_count"],
                "assistant_message_count": activity["assistant_message_count"],
                "turn_count": activity["turn_count"],
                "is_empty_session": activity["is_empty_session"],
                "revealed_info_count": revealed_info_count,
                "final_emotion": session.current_emotion,
                "final_trust": session.current_trust,
                "created_at": session.created_at.isoformat() if session.created_at else None,
            }
        )

    total = len(session_items)
    page_items = session_items[(page - 1) * page_size : page * page_size]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < total,
        "include_empty": include_empty,
        "hidden_empty_count": 0 if include_empty else empty_session_count,
        "empty_session_count": empty_session_count,
    }


@router.get("/case-types")
def get_case_types(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    types = db.query(models.Case.case_type).distinct().all()
    return [repair_text(item[0]) for item in types if item[0]]
