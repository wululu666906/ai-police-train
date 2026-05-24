from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional

import database
import models
from routers.auth import require_admin_user
from services.rag_service import rag_service
from services.stage_config_service import normalize_stages
import pydantic
import schemas

router = APIRouter(prefix="/knowledge", tags=["Knowledge"], dependencies=[Depends(require_admin_user)])


def _build_reference_index(db) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    cases = db.query(models.Case).all()
    for case in cases:
        case_title = str(case.title or "未命名案件").strip()
        for scene in case.scenes or []:
            stages = normalize_stages(scene.stages, case_type=case.case_type or "", scene_name=scene.name or "")
            for stage in stages:
                stage_name = str(stage.get("stage_name") or "阶段").strip()
                for point in stage.get("assessment_points") or []:
                    point_label = str(point.get("label") or "考察点").strip()
                    reference_label = f"{case_title} / {scene.name or '场景'} / {stage_name} / {point_label}"
                    for knowledge_id in point.get("knowledge_refs") or []:
                        clean_id = str(knowledge_id or "").strip()
                        if not clean_id:
                            continue
                        index.setdefault(clean_id, [])
                        if reference_label not in index[clean_id]:
                            index[clean_id].append(reference_label)
    return index


@router.get("/list", response_model=List[schemas.KnowledgeItem])
def list_knowledge(limit: int = 50, offset: int = 0, db=Depends(database.get_db)):
    """获取本地向量库中的知识片段列表"""
    try:
        reference_index = _build_reference_index(db)
        items = []
        for item in rag_service.get_items(limit=limit, offset=offset):
            references = reference_index.get(item["id"], [])
            items.append(
                schemas.KnowledgeItem(
                    id=item["id"],
                    content=item["content"],
                    source=item["source"],
                    title=item["title"],
                    category=item["category"],
                    tags=item["tags"],
                    referenced_by_count=len(references),
                    referenced_by=references,
                )
            )
        return items

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
def upload_knowledge(payload: dict = Body(...)):
    """上传并索引新的知识文本"""
    text = payload.get("text")
    source = payload.get("source", "manual_upload")
    title = payload.get("title") or rag_service._default_title(text)
    category = payload.get("category") or "通用"
    tags = rag_service._normalize_tags(payload.get("tags"))
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    try:
        ids = rag_service.add_documents(
            [text],
            metadatas=[{"source": source, "title": title, "category": category, "tags": tags}],
        )
        return {"message": "Knowledge indexed successfully", "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{item_id}")
def delete_knowledge(item_id: str):
    """从向量库中删除指定知识片段"""
    try:
        rag_service.collection.delete(ids=[item_id])
        return {"message": "Item deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
