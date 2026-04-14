from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas, database

router = APIRouter(prefix="/cases", tags=["Cases"])

@router.get("/", response_model=List[schemas.Case])
def read_cases(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    cases = db.query(models.Case).offset(skip).limit(limit).all()
    return cases

@router.post("/", response_model=schemas.Case)
def create_case(case: schemas.CaseCreate, db: Session = Depends(database.get_db)):
    db_case = models.Case(
        title=case.title,
        case_type=case.case_type,
        background=case.background
    )
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    
    # 也一起创建附带的场景和角色
    for sc_data in case.scenes:
        db_scene = models.Scene(
            case_id=db_case.id,
            name=sc_data.name,
            difficulty=sc_data.difficulty
        )
        db.add(db_scene)
        db.commit()
        db.refresh(db_scene)
        
        for r_data in sc_data.roles:
            db_role = models.Role(
                scene_id=db_scene.id,
                name=r_data.name,
                personality=r_data.personality,
                init_emotion=r_data.init_emotion,
                init_trust=r_data.init_trust,
                hidden_truths=r_data.hidden_truths
            )
            db.add(db_role)
            db.commit()
            
    db.refresh(db_case)
    return db_case

@router.get("/{case_id}", response_model=schemas.Case)
def read_case(case_id: int, db: Session = Depends(database.get_db)):
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@router.get("/all/roles", response_model=List[schemas.Role])
def read_all_roles(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.Role).offset(skip).limit(limit).all()
