from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional

import database
import models
from routers.auth import require_admin_user
from services.rag_service import rag_service
from services.case_knowledge_service import (
    build_case_knowledge_documents,
    delete_case_from_knowledge,
    sync_case_to_knowledge,
    try_sync_case_to_knowledge,
)
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


@router.get("/cases")
def list_case_knowledge(case_id: Optional[int] = None, db=Depends(database.get_db)):
    """List case-library knowledge documents and role scripts.

    The response includes persisted Chroma documents when present, and generated
    database snapshots for cases that have not been synced yet. This keeps the
    admin view useful during migration and after restoring a database backup.
    """
    try:
        if case_id is not None:
            cases = db.query(models.Case).filter(models.Case.id == case_id).all()
            persisted = rag_service.get_documents_by_metadata({"case_id": str(case_id)})
        else:
            cases = db.query(models.Case).order_by(models.Case.id.asc()).all()
            persisted = rag_service.get_documents_by_metadata({"source": "case_library"})

        persisted_by_id = {item["id"]: item for item in persisted}
        rows = []
        seen_ids = set()
        for case in cases:
            for doc in build_case_knowledge_documents(case):
                item = persisted_by_id.get(doc["id"])
                metadata = (item or {}).get("metadata") or doc["metadata"]
                rows.append(
                    {
                        "id": doc["id"],
                        "content": (item or {}).get("content") or doc["content"],
                        "source": metadata.get("source", "case_library"),
                        "title": metadata.get("title") or doc["id"],
                        "category": metadata.get("category") or "",
                        "tags": rag_service._normalize_tags(metadata.get("tags")),
                        "metadata": metadata,
                        "case_id": str(case.id),
                        "case_title": case.title or f"Case {case.id}",
                        "doc_type": metadata.get("doc_type") or doc["metadata"].get("doc_type"),
                        "role_id": metadata.get("role_id"),
                        "role_name": metadata.get("role_name"),
                        "in_knowledge": bool(item),
                    }
                )
                seen_ids.add(doc["id"])

        for item in persisted:
            if item["id"] not in seen_ids:
                metadata = item.get("metadata") or {}
                rows.append(
                    {
                        **item,
                        "case_id": metadata.get("case_id"),
                        "case_title": metadata.get("case_title") or metadata.get("title"),
                        "doc_type": metadata.get("doc_type"),
                        "role_id": metadata.get("role_id"),
                        "role_name": metadata.get("role_name"),
                        "in_knowledge": True,
                    }
                )

        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/sync-all")
def sync_all_case_knowledge(db=Depends(database.get_db)):
    """Rebuild knowledge documents for every database case after migration/restore."""
    cases = db.query(models.Case).order_by(models.Case.id.asc()).all()
    results = []
    for case in cases:
        results.append(try_sync_case_to_knowledge(case))
    return {
        "total": len(results),
        "succeeded": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "results": results,
    }


@router.post("/cases/{case_id}/sync")
def sync_case_knowledge(case_id: int, db=Depends(database.get_db)):
    """Rebuild one case's case-info and role-script knowledge documents."""
    case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    try:
        return sync_case_to_knowledge(case)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cases/{case_id}")
def delete_case_knowledge(case_id: int):
    """Delete only the knowledge documents for a case; the database case stays intact."""
    try:
        return delete_case_from_knowledge(case_id)
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
