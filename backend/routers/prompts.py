from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models, schemas, database

router = APIRouter(prefix="/prompts", tags=["Prompts"])

@router.get("/", response_model=List[schemas.PromptTemplate])
def read_prompts(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return db.query(models.PromptTemplate).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.PromptTemplate)
def create_prompt(prompt: schemas.PromptTemplateCreate, db: Session = Depends(database.get_db)):
    db_prompt = models.PromptTemplate(name=prompt.name, content=prompt.content)
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt
