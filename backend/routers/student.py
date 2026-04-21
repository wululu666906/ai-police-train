from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

import models, schemas, database

router = APIRouter(prefix="/student", tags=["Student"])

@router.get("/cases")
def get_student_cases(
    case_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    """获取学员可训练的案件列表（含场景、角色信息）"""
    query = db.query(models.Case)
    
    if search:
        query = query.filter(models.Case.title.contains(search))
    if case_type:
        query = query.filter(models.Case.case_type == case_type)
    
    cases = query.all()
    
    result = []
    for case in cases:
        scenes = db.query(models.Scene).filter(models.Scene.case_id == case.id).all()
        
        # 按难度过滤
        if difficulty:
            scenes = [s for s in scenes if s.difficulty == difficulty]
            if not scenes:
                continue
        
        # 统计该案件的训练次数
        scene_ids = [s.id for s in db.query(models.Scene).filter(models.Scene.case_id == case.id).all()]
        train_count = db.query(models.TrainingSession).filter(
            models.TrainingSession.scene_id.in_(scene_ids)
        ).count() if scene_ids else 0
        
        result.append({
            "id": case.id,
            "title": case.title,
            "case_type": case.case_type,
            "background": case.background,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "scenes": [{
                "id": s.id,
                "name": s.name,
                "difficulty": s.difficulty,
                "description": s.description
            } for s in scenes],
            "train_count": train_count
        })
    
    return result

@router.get("/history")
def get_student_history(
    user_id: int = 1,
    db: Session = Depends(database.get_db)
):
    """获取学员历史训练记录"""
    sessions = db.query(models.TrainingSession).filter(
        models.TrainingSession.user_id == user_id
    ).order_by(models.TrainingSession.created_at.desc()).all()
    
    result = []
    for session in sessions:
        scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
        msg_count = db.query(models.Message).filter(models.Message.session_id == session.id).count()
        
        result.append({
            "id": session.id,
            "case_title": case.title if case else "未知案件",
            "case_type": case.case_type if case else "未分类",
            "scene_name": scene.name if scene else "未知场景",
            "difficulty": scene.difficulty if scene else "中等",
            "status": session.status,
            "message_count": msg_count,
            "final_emotion": session.current_emotion,
            "final_trust": session.current_trust,
            "created_at": session.created_at.isoformat() if session.created_at else None
        })
    
    return result

@router.get("/case-types")
def get_case_types(db: Session = Depends(database.get_db)):
    """获取所有案件类型（用于筛选器）"""
    types = db.query(models.Case.case_type).distinct().all()
    return [t[0] for t in types if t[0]]
