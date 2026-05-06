import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import database
import models
import schemas
from routers.auth import get_current_user
from services.ai_service import generate_dialogue
from services.evaluation_service import evaluate_session
from services.role_resolver import resolve_scene_role
from services.text_repair import repair_payload, repair_text

router = APIRouter(prefix="/training", tags=["Training"])


def safe_json_loads(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


@router.post("/start/{scene_id}", response_model=schemas.Session)
def start_training(
    scene_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        scene = db.query(models.Scene).filter(models.Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="未找到该训练场景")

        latest_session = (
            db.query(models.TrainingSession)
            .filter(
                models.TrainingSession.user_id == current_user.id,
                models.TrainingSession.scene_id == scene_id,
            )
            .order_by(models.TrainingSession.created_at.desc())
            .first()
        )
        if latest_session and latest_session.status == "active":
            return latest_session

        role = resolve_scene_role(db, scene)
        stages = safe_json_loads(scene.stages, [])
        first_stage = (
            stages[0].get("stage_name", "初始接触")
            if isinstance(stages, list) and stages
            else "初始接触"
        )

        new_session = models.TrainingSession(
            user_id=current_user.id,
            scene_id=scene_id,
            current_stage=first_stage,
            current_emotion=role.init_emotion if role else 50,
            current_trust=role.init_trust if role else 30,
            revealed_info="[]",
        )
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in start_training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"训练启动失败: {str(e)}")


@router.post("/chat/{session_id}")
def training_chat(
    session_id: int,
    message: schemas.MessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该训练会话")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Training session has already been finished")
    if not message.content or not message.content.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    db.add(models.Message(session_id=session_id, role="user", content=message.content.strip()))
    db.commit()

    result = generate_dialogue(db, session_id, message.content.strip())
    return result


@router.get("/session/{session_id}", response_model=schemas.SessionDetail)
def get_session(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看该训练会话")

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    role = resolve_scene_role(db, scene, case)

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
            created_at=message.created_at,
        )
        for message in messages
    ]

    current_goal = None
    if scene:
        stages_list = safe_json_loads(scene.stages, [])
        for stage in stages_list:
            if stage.get("stage_name") == session.current_stage:
                current_goal = stage.get("stage_goal")
                break

    repaired_revealed_info = repair_payload(session.revealed_info)
    if isinstance(repaired_revealed_info, list):
        repaired_revealed_info = json.dumps(repaired_revealed_info, ensure_ascii=False)
    else:
        repaired_revealed_info = session.revealed_info

    repaired_evaluation_result = session.evaluation_result
    if repaired_evaluation_result:
        try:
            repaired_evaluation_result = json.dumps(
                repair_payload(json.loads(repaired_evaluation_result)),
                ensure_ascii=False,
            )
        except Exception:
            repaired_evaluation_result = repair_text(repaired_evaluation_result)

    return schemas.SessionDetail(
        id=session.id,
        scene_id=session.scene_id,
        user_id=session.user_id,
        current_stage=session.current_stage or "训练中",
        current_stage_goal=current_goal,
        current_emotion=session.current_emotion,
        current_trust=session.current_trust,
        revealed_info=repaired_revealed_info,
        evaluation_result=repaired_evaluation_result,
        status=session.status,
        case_title=repair_text(case.title) if case else "未知案例",
        case_type=repair_text(case.case_type) if case else "其他",
        case_background=repair_text(case.background) if case else "暂无背景描述",
        case_original_content=repair_text(case.original_content) if case else "暂无原文信息",
        role_name=repair_text(role.name) if role else "对话人员",
        role_status=repair_text(role.status) if role else "正常",
        scene_name=repair_text(scene.name) if scene else "训练场景",
        difficulty=repair_text(scene.difficulty) if scene else "中等",
        dispatch_brief=repair_text(scene.dispatch_brief) if scene else None,
        first_impression=repair_text(scene.first_impression) if scene else None,
        structured_data=(
            json.dumps(repair_payload(safe_json_loads(case.structured_data, {})), ensure_ascii=False)
            if case and case.structured_data
            else None
        ),
        messages=repaired_messages,
    )


@router.post("/finish/{session_id}")
def finish_training(
    session_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权结束该训练会话")

    user_message_count = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id, models.Message.role == "user")
        .count()
    )
    if user_message_count <= 0:
        raise HTTPException(status_code=400, detail="至少完成一轮有效对话后再结束训练")

    report = evaluate_session(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Session not found")

    return report
