from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import models, database
from pymilvus import MilvusClient
import os

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats")
def get_stats(db: Session = Depends(database.get_db)):
    # 基础统计数据
    case_count = db.query(models.Case).count()
    role_count = db.query(models.Role).count()
    session_count = db.query(models.TrainingSession).count()
    
    # 针对 RAG 知识库片段的统计 (如果是 ChromaDB)
    rag_count = 0
    try:
        # 尝试检查 chromadb 目录是否存在
        if os.path.exists("./chroma_db"):
            import chromadb
            client = chromadb.PersistentClient(path="./chroma_db")
            collection = client.get_or_create_collection(name="legal_knowledge")
            rag_count = collection.count()
    except Exception as e:
        print(f"RAG stats error: {e}")
        
    return {
        "cases": case_count,
        "roles": role_count,
        "sessions": session_count,
        "rag": rag_count
    }
