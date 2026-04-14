import chromadb
from sentence_transformers import SentenceTransformer
from typing import List
import os

# 配置
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "legal_knowledge"
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

class RAGService:
    def __init__(self):
        # 初始化本地持久化客户端
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)

    def add_documents(self, texts: List[str], metadatas: List[dict] = None):
        """将文本列表索引进向量库"""
        if not texts:
            return
        
        # ChromaDB 默认支持自动 Embedding，但为了统一控制，我们手动计算
        embeddings = self.model.encode(texts).tolist()
        ids = [f"id_{i}_{os.urandom(4).hex()}" for i in range(len(texts))]
        
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas if metadatas else [{}] * len(texts),
            ids=ids
        )
        print(f"Added {len(texts)} documents to ChromaDB.")

    def search(self, query: str, limit: int = 2) -> List[str]:
        """搜索最相关的知识片段"""
        query_embedding = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=limit
        )
        
        # 结果处理 (Chroma 返回的是嵌套列表)
        if results['documents'] and len(results['documents'][0]) > 0:
            return results['documents'][0]
        return []

# 全局单例
rag_service = RAGService()
