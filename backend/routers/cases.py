import json
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

import database
import models
import schemas
from services.data_quality_service import build_data_quality_report
from services.role_resolver import is_role_speakable
from services.scene_role_service import audit_scene_roles, normalize_scene_roles
from services.workflow_service import workflow_service

router = APIRouter(prefix="/cases", tags=["Cases"])


def _safe_json_loads(value, default):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


@router.get("/", response_model=List[schemas.Case])
def read_cases(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.Case).offset(skip).limit(limit).all()


@router.get("/all/roles")
def read_all_roles(db: Session = Depends(database.get_db)):
    roles = (
        db.query(models.Role, models.Case.title.label("case_title"))
        .outerjoin(models.Case, models.Role.case_id == models.Case.id)
        .all()
    )

    result = []
    for role, case_title in roles:
        result.append(
            {
                "id": role.id,
                "name": role.name,
                "role_type": role.role_type,
                "personality": role.personality,
                "speaking_style": role.speaking_style,
                "init_emotion": role.init_emotion,
                "init_trust": role.init_trust,
                "case_title": case_title or "公共角色库",
            }
        )
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


@router.get("/scene-role-audit")
def get_scene_role_audit(case_id: int | None = None, db: Session = Depends(database.get_db)):
    return audit_scene_roles(db, case_id=case_id)


@router.get("/data-quality-report")
def get_data_quality_report(db: Session = Depends(database.get_db)):
    return build_data_quality_report(db)


@router.post("/scene-role-repair")
def repair_scene_roles(payload: dict = Body(default={}), db: Session = Depends(database.get_db)):
    case_id = payload.get("case_id")
    repair_result = normalize_scene_roles(db, case_id=case_id)
    audit_result = audit_scene_roles(db, case_id=case_id)
    return {
        **repair_result,
        "audit": audit_result,
    }


@router.post("/full-create", response_model=schemas.Case)
def full_create_case(payload: dict = Body(...), db: Session = Depends(database.get_db)):
    case_data = payload.get("case") or {}
    scenes_data = payload.get("scenes") or []

    try:
        case_title = case_data.get("title") or case_data.get("case_name") or "未命名案件"
        original_content = case_data.get("original_content") or case_data.get("rawText") or ""
        background = case_data.get("background") or case_data.get("case_background") or "暂无案件背景"
        normalized_case_type = workflow_service.normalize_case_type(
            text=original_content,
            ai_case_type=case_data.get("case_type") or ""
        )

        structured_data_to_save = {
            "fact_sheet": case_data.get("fact_sheet", {}),
            "full_narrative": case_data.get("full_narrative", ""),
            "criminal_process": case_data.get("criminal_process", ""),
            **case_data,
            "case_type": normalized_case_type,
        }

        db_case = models.Case(
            title=case_title,
            case_type=normalized_case_type or "其他",
            background=background,
            original_content=original_content,
            structured_data=json.dumps(structured_data_to_save, ensure_ascii=False),
        )
        db.add(db_case)
        db.flush()

        persons_data = case_data.get("persons") or []
        created_roles = {}

        for person in persons_data:
            role_name = person.get("name")
            if not role_name:
                continue

            db_role = models.Role(
                case_id=db_case.id,
                name=role_name,
                role_type=person.get("role_type") or "配合型",
                personality=person.get("personality") or "暂无详细性格描述",
                speaking_style=person.get("speaking_style") or "常规",
                init_emotion=person.get("init_emotion", 50),
                init_trust=person.get("init_trust", 30),
                status=person.get("status") or "正常",
                hidden_truths=json.dumps(person.get("hidden_truths", []), ensure_ascii=False),
                knows_facts=json.dumps(person.get("knows_facts", []), ensure_ascii=False),
                does_not_know=json.dumps(person.get("does_not_know", []), ensure_ascii=False),
                iq_level=person.get("iq_level", "中等"),
                eq_level=person.get("eq_level", "中等"),
                lying_ability=person.get("lying_ability", "一般"),
                weakness=person.get("weakness", ""),
            )
            db.add(db_role)
            db.flush()
            created_roles[role_name] = db_role

        for scene_data in scenes_data:
            db_scene = models.Scene(
                case_id=db_case.id,
                name=scene_data.get("scene_name") or "未命名场景",
                description=scene_data.get("scene_description") or "",
                difficulty=scene_data.get("difficulty") or "中等",
                dispatch_brief=scene_data.get("dispatch_brief") or "暂无接警信息",
                first_impression=scene_data.get("first_impression") or "暂无现场第一印象描述",
                stages=json.dumps(scene_data.get("stages") or [], ensure_ascii=False),
            )
            db.add(db_scene)
            db.flush()

            primary_assigned = False
            linked_role_ids = set()

            for role_name in scene_data.get("roles") or []:
                role = created_roles.get(role_name)
                if not role or role.id in linked_role_ids:
                    continue

                linked_role_ids.add(role.id)
                can_speak = is_role_speakable(role)
                is_primary = False
                if not primary_assigned and can_speak:
                    is_primary = True
                    primary_assigned = True

                db.add(models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=is_primary))
                role.scene_id = db_scene.id

            if not primary_assigned:
                for role in created_roles.values():
                    if not is_role_speakable(role):
                        continue
                    if role.id in linked_role_ids:
                        continue

                    db.add(models.SceneRole(scene_id=db_scene.id, role_id=role.id, is_primary=True))
                    linked_role_ids.add(role.id)
                    role.scene_id = db_scene.id
                    primary_assigned = True
                    break

        db.commit()
        db.refresh(db_case)
        return db_case
    except Exception as e:
        db.rollback()
        print(f"Full create failed: {e}")
        raise HTTPException(status_code=500, detail=f"保存案件失败: {str(e)}")


@router.put("/{case_id}", response_model=schemas.Case)
def update_case(case_id: int, payload: dict = Body(...), db: Session = Depends(database.get_db)):
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    case_data = payload.get("case") or {}
    scenes_data = payload.get("scenes") or []

    try:
        if "title" in case_data:
            db_case.title = case_data.get("title") or db_case.title
        if "case_type" in case_data:
            db_case.case_type = workflow_service.normalize_case_type(
                text=case_data.get("original_content") or db_case.original_content or "",
                ai_case_type=case_data.get("case_type") or db_case.case_type or ""
            )
        if "background" in case_data:
            db_case.background = case_data.get("background") or ""
        if "original_content" in case_data:
            db_case.original_content = case_data.get("original_content") or ""

        structured_data = _safe_json_loads(db_case.structured_data, {})
        if not isinstance(structured_data, dict):
            structured_data = {}

        if "title" in case_data:
            structured_data["case_name"] = db_case.title
        if "case_type" in case_data:
            structured_data["case_type"] = db_case.case_type
        if "background" in case_data:
            structured_data["case_background"] = db_case.background
        if "original_content" in case_data:
            structured_data["rawText"] = db_case.original_content

        incoming_structured_data = _safe_json_loads(case_data.get("structured_data"), None)
        if isinstance(incoming_structured_data, dict):
            structured_data.update(incoming_structured_data)

        db_case.structured_data = json.dumps(structured_data, ensure_ascii=False)

        scene_map = {scene.id: scene for scene in db_case.scenes}
        for scene_data in scenes_data:
            scene_id = scene_data.get("id")
            db_scene = scene_map.get(scene_id)
            if not db_scene:
                continue

            if "name" in scene_data:
                db_scene.name = scene_data.get("name") or db_scene.name
            if "description" in scene_data:
                db_scene.description = scene_data.get("description") or ""
            if "difficulty" in scene_data:
                db_scene.difficulty = scene_data.get("difficulty") or "中等"
            if "dispatch_brief" in scene_data:
                db_scene.dispatch_brief = scene_data.get("dispatch_brief") or ""
            if "first_impression" in scene_data:
                db_scene.first_impression = scene_data.get("first_impression") or ""
            if "stages" in scene_data:
                stages = scene_data.get("stages") or []
                if isinstance(stages, str):
                    stages = _safe_json_loads(stages, [])
                if not isinstance(stages, list):
                    raise HTTPException(status_code=400, detail=f"Scene {scene_id} stages must be a list")
                db_scene.stages = json.dumps(stages, ensure_ascii=False)

        db.commit()
        db.refresh(db_case)
        return db_case
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"Update case failed: {e}")
        raise HTTPException(status_code=500, detail=f"更新案件失败: {str(e)}")


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
