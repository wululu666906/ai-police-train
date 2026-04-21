from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json

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
    
    if role and role.status in ["死亡", "重伤", "昏迷"]:
        raise HTTPException(
            status_code=403, 
            detail=f"该角色当前状态为【{role.status}】，无法接受审问或进行对话训练。"
        )
    
    # 获取场景的阶段信息
    stages = json.loads(scene.stages) if scene.stages else []
    first_stage = stages[0]["stage_name"] if stages else "初始接触"
    
    # 创建新会话
    new_session = models.TrainingSession(
        user_id=user_id,
        scene_id=scene_id,
        current_stage=first_stage,
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


@router.get("/session/{session_id}", response_model=schemas.SessionDetail)
def get_session(session_id: int, db: Session = Depends(database.get_db)):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    
    # 查找角色：优先用场景 ID 找，找不到用案例 ID 兜底
    role = db.query(models.Role).filter(models.Role.scene_id == session.scene_id).first() if scene else None
    if not role and scene:
         role = db.query(models.Role).filter(models.Role.case_id == scene.case_id).first()

    # 获取消息记录
    messages = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.asc()).all()
    
    # 查找当前阶段的目标
    current_goal = None
    if scene:
        stages_list = json.loads(scene.stages or "[]")
        for s in stages_list:
            if s.get("stage_name") == session.current_stage:
                current_goal = s.get("stage_goal")
                break
    
    return schemas.SessionDetail(
        id=session.id,
        scene_id=session.scene_id,
        user_id=session.user_id,
        current_stage=session.current_stage or "训练中",
        current_stage_goal=current_goal,
        current_emotion=session.current_emotion,
        current_trust=session.current_trust,
        revealed_info=session.revealed_info,
        status=session.status,
        case_title=case.title if case else "未知案例",
        case_background=case.background if case else "暂无背景描述",
        role_name=role.name if role else "对话人员",
        scene_name=scene.name if scene else "训练场景",
        messages=messages
    )

@router.post("/finish/{session_id}")
def finish_training(session_id: int, db: Session = Depends(database.get_db)):
    # 触发 AI 评分
    report = evaluate_session(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return report
