import json
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List

import models, schemas, database
from services.workflow_service import workflow_service

router = APIRouter(prefix="/cases", tags=["Cases"])

@router.get("/", response_model=List[schemas.Case])
def read_cases(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    cases = db.query(models.Case).offset(skip).limit(limit).all()
    return cases

@router.get("/all/roles")
def read_all_roles(db: Session = Depends(database.get_db)):
    # 联表查询获取角色及其所属案件名称，用于前端分组展示
    roles = db.query(
        models.Role,
        models.Case.title.label("case_title")
    ).outerjoin(models.Case, models.Role.case_id == models.Case.id).all()
    
    result = []
    for role, case_title in roles:
        role_dict = {
            "id": role.id,
            "name": role.name,
            "role_type": role.role_type,
            "personality": role.personality,
            "speaking_style": role.speaking_style,
            "init_emotion": role.init_emotion,
            "init_trust": role.init_trust,
            "case_title": case_title or "公共角色库"
        }
        result.append(role_dict)
    return result

@router.post("/parse")
def parse_case(payload: dict = Body(...)):
    text = payload.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    result = workflow_service.parse_case_text(text)
    if not result:
        raise HTTPException(status_code=500, detail="AI Parsing failed")
    return result

@router.post("/generate-scenes")
def generate_scenes(payload: dict = Body(...)):
    case_info = payload.get("case_info")
    if not case_info:
        raise HTTPException(status_code=400, detail="Case info is required")
    result = workflow_service.generate_scenes(case_info)
    if not result:
        raise HTTPException(status_code=500, detail="AI Scene generation failed")
    return result

@router.post("/full-create", response_model=schemas.Case)
def full_create_case(payload: dict = Body(...), db: Session = Depends(database.get_db)):
    case_data = payload.get("case") or {}
    scenes_data = payload.get("scenes") or []
    
    try:
        # 1. 创建案件
        # 优先使用前端传入的 title，如果没有则使用 AI 解析出的 case_name
        case_title = case_data.get("title") or case_data.get("case_name") or "未命名案件"
        db_case = models.Case(
            title=case_title,
            case_type=case_data.get("case_type") or "未分类",
            background=case_data.get("case_background") or case_data.get("background") or "暂无背景描述",
            structured_data=json.dumps(case_data, ensure_ascii=False)
        )
        db.add(db_case)
        db.flush() # 获取 ID 但不提交
        
        # 2. 创建场景与角色
        persons_data = case_data.get("persons") or []
        created_roles = {}
        
        for p in persons_data:
            role_name = p.get("name")
            if not role_name: continue
            
            db_role = models.Role(
                case_id=db_case.id,
                name=role_name,
                role_type=p.get("role_type") or "配合型",
                personality=p.get("personality") or "暂无详细性格描述",
                speaking_style=p.get("speaking_style") or "常规",
                init_emotion=p.get("init_emotion", 50),
                init_trust=p.get("init_trust", 30),
                status=p.get("status") or "正常",
                hidden_truths=json.dumps(case_data.get("key_facts", []), ensure_ascii=False)
            )
            db.add(db_role)
            db.flush()
            created_roles[role_name] = db_role
            
        for sc in scenes_data:
            db_scene = models.Scene(
                case_id=db_case.id,
                name=sc.get("scene_name") or "未命名场景",
                description=sc.get("scene_description") or "",
                difficulty=sc.get("difficulty") or "中等",
                stages=json.dumps(sc.get("stages") or [], ensure_ascii=False)
            )
            db.add(db_scene)
            db.flush()
            
            # 角色关联：将场景指定的角色关联到该场景记录
            for role_name in (sc.get("roles") or []):
                if role_name in created_roles:
                    created_roles[role_name].scene_id = db_scene.id
        
        db.commit()
        db.refresh(db_case)
        return db_case
    except Exception as e:
        db.rollback()
        print(f"Full create failed: {e}")
        raise HTTPException(status_code=500, detail=f"保存案件由于服务器内部错误失败: {str(e)}")


@router.get("/{case_id}", response_model=schemas.Case)
def read_case(case_id: int, db: Session = Depends(database.get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@router.delete("/{case_id}")
def delete_case(case_id: int, db: Session = Depends(database.get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.delete(case)
    db.commit()
    return {"message": "Case deleted"}
