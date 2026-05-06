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
    try:
        # 1. 查找场景
        scene = db.query(models.Scene).filter(models.Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="未找到该训练场景")
        
        # 2. 状态检查 (已按要求移除限制)
        role = db.query(models.Role).filter(models.Role.scene_id == scene_id).first()
        if not role:
            role = db.query(models.Role).filter(models.Role.case_id == scene.case_id).first()
            
        # 3. 阶段信息解析 (增加容错)
        stages = []
        if scene.stages:
            try:
                stages = json.loads(scene.stages) if isinstance(scene.stages, str) else scene.stages
            except:
                stages = []
        
        first_stage = stages[0].get("stage_name", "初始接触") if (stages and isinstance(stages, list) and len(stages) > 0) else "初始接触"
        
        # 4. 创建新会话
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
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        print(f"Error in start_training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"训练启动失败: {str(e)}")

@router.post("/chat/{session_id}")
def training_chat(session_id: int, message: schemas.MessageCreate, db: Session = Depends(database.get_db)):
    # 场景与角色状态校验
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 调用 AI 引擎 (已移除状态校验)

    # 调用 AI 引擎
    result = generate_dialogue(db, session_id, message.content)
    return result


@router.get("/session/{session_id}", response_model=schemas.SessionDetail)
def get_session(session_id: int, db: Session = Depends(database.get_db)):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    
    # 查找角色：通过 SceneRole 关联表找主对话角色
    primary_link = db.query(models.SceneRole).filter(
        models.SceneRole.scene_id == session.scene_id,
        models.SceneRole.is_primary == True
    ).first()
    
    if primary_link:
        role = db.query(models.Role).get(primary_link.role_id)
    else:
        # 兜底
        fallback_link = db.query(models.SceneRole).filter(models.SceneRole.scene_id == session.scene_id).first()
        if fallback_link:
            role = db.query(models.Role).get(fallback_link.role_id)
        else:
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
        evaluation_result=session.evaluation_result,
        status=session.status,
        case_title=case.title if case else "未知案例",
        case_type=case.case_type if case else "其他",
        case_background=case.background if case else "暂无背景描述",
        case_original_content=case.original_content if case else "暂无原文信息",
        role_name=role.name if role else "对话人员",
        role_status=role.status if role else "正常",
        scene_name=scene.name if scene else "训练场景",
        dispatch_brief=scene.dispatch_brief if scene else None,
        first_impression=scene.first_impression if scene else None,
        structured_data=case.structured_data if case else None,
        messages=messages
    )

@router.post("/finish/{session_id}")
def finish_training(session_id: int, db: Session = Depends(database.get_db)):
    # 触发 AI 评分
    report = evaluate_session(db, session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return report
