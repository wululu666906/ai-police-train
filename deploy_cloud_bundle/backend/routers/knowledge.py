from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from services.rag_service import rag_service
import pydantic
import schemas

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

@router.get("/list", response_model=List[schemas.KnowledgeItem])
def list_knowledge(limit: int = 50, offset: int = 0):
    """获取本地向量库中的知识片段列表"""
    try:
        # ChromaDB get() method
        results = rag_service.collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"]
        )
        
        items = []
        for i in range(len(results['ids'])):
            items.append(schemas.KnowledgeItem(
                id=results['ids'][i],
                content=results['documents'][i],
                source=results['metadatas'][i].get("source", "unknown")
            ))
        return items

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
def upload_knowledge(payload: dict = Body(...)):
    """上传并索引新的知识文本"""
    text = payload.get("text")
    source = payload.get("source", "manual_upload")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    try:
        rag_service.add_documents([text], metadatas=[{"source": source}])
        return {"message": "Knowledge indexed successfully"}
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
