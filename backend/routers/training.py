from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas, database
from services.ai_service import generate_dialogue
from services.evaluation_service import evaluate_session

router = APIRouter(prefix="/training", tags=["Training"])

@router.post("/start/{scene_id}", response_model=schemas.Session)
def start_training(scene_id: int, user_id: int = 1, db: Session = Depends(database.get_db)):
    # 查找场景与角色
    scene = db.query(models.Scene).filter(models.Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    role = db.query(models.Role).filter(models.Role.scene_id == scene_id).first()
    
    # 创建新会话
    new_session = models.TrainingSession(
        user_id=user_id,
        scene_id=scene_id,
        current_emotion=role.init_emotion if role else 50,
        current_trust=role.init_trust if role else 30,
        revealed_info="[]"
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return new_session

@router.post("/chat/{session_id}")
def training_chat(session_id: int, message: schemas.MessageCreate, db: Session = Depends(database.get_db)):
    # 调用 AI 引擎
    result = generate_dialogue(db, session_id, message.content)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return result

@router.get("/session/{session_id}", response_model=schemas.Session)
def get_session(session_id: int, db: Session = Depends(database.get_db)):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/finish/{session_id}")
def finish_training(session_id: int, db: Session = Depends(database.get_db)):
    # 触发 AI 评分
    report = evaluate_session(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return report
