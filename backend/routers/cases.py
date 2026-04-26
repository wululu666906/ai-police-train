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
        case_title = case_data.get("title") or case_data.get("case_name") or "未命名案件"
        
        # 优先级：顶层 original_content > structured_data 内的 rawText > 默认
        orig_content = case_data.get("original_content") or case_data.get("rawText") or ""
        
        # 优先级：顶层 background > case_background > 默认
        bg_info = case_data.get("background") or case_data.get("case_background") or "暂无背景描述"
        
        # 提取或重组 structured_data
        structured_data_to_save = {
            "fact_sheet": case_data.get("fact_sheet", {}),
            "full_narrative": case_data.get("full_narrative", ""),
            "criminal_process": case_data.get("criminal_process", ""),
            **case_data
        }

        db_case = models.Case(
            title=case_title,
            case_type=case_data.get("case_type") or "未分类",
            background=bg_info,
            original_content=orig_content, 
            structured_data=json.dumps(structured_data_to_save, ensure_ascii=False)
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
                hidden_truths=json.dumps(p.get("hidden_truths", []), ensure_ascii=False),
                knows_facts=json.dumps(p.get("knows_facts", []), ensure_ascii=False),
                does_not_know=json.dumps(p.get("does_not_know", []), ensure_ascii=False),
                iq_level=p.get("iq_level", "中等"),
                eq_level=p.get("eq_level", "中等"),
                lying_ability=p.get("lying_ability", "一般"),
                weakness=p.get("weakness", "")
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
                dispatch_brief=sc.get("dispatch_brief") or "暂无接警信息",
                first_impression=sc.get("first_impression") or "暂无现场景象描述",
                stages=json.dumps(sc.get("stages") or [], ensure_ascii=False)
            )
            db.add(db_scene)
            db.flush()
            
            # 角色关联：使用 SceneRole 中间表
            primary_assigned = False
            for role_name in (sc.get("roles") or []):
                if role_name in created_roles:
                    r_obj = created_roles[role_name]
                    # 只有当角色没有被分配为主角色，且状态不是死亡/重伤/昏迷时，才可能被分配为对话主角色
                    can_speak = r_obj.status not in ["死亡", "重伤", "昏迷"]
                    
                    is_primary = False
                    if not primary_assigned and can_speak:
                        is_primary = True
                        primary_assigned = True
                        
                    db.add(models.SceneRole(
                        scene_id=db_scene.id,
                        role_id=r_obj.id,
                        is_primary=is_primary
                    ))
                    # 兼容保留原有的 scene_id
                    r_obj.scene_id = db_scene.id
            
            # 如果循环完都没有找到能说话的主角色（比如只关联了死者），兜底找本案中第一个活人强制作为主角色关联
            if not primary_assigned:
                for r_obj in created_roles.values():
                    if r_obj.status not in ["死亡", "重伤", "昏迷"]:
                        db.add(models.SceneRole(
                            scene_id=db_scene.id,
                            role_id=r_obj.id,
                            is_primary=True
                        ))
                        break
        
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
