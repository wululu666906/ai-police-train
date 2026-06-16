import hashlib
import os
from typing import List, Optional
from difflib import SequenceMatcher

import chromadb

from .llm_provider import create_embeddings, get_embedding_model, get_embedding_provider

SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICES_DIR)
_chroma_raw = os.getenv("CHROMA_DB_PATH", "chroma_db")
CHROMA_DB_PATH = _chroma_raw if os.path.isabs(_chroma_raw) else os.path.join(BACKEND_DIR, _chroma_raw)
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "legal_knowledge_qwen")
FALLBACK_EMBEDDING_DIMENSIONS = int(os.getenv("FALLBACK_EMBEDDING_DIMENSIONS", "1024"))


class RAGService:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.collection = self.client.get_or_create_collection(name=COLLECTION_NAME)
        self.search_collections = [self.collection]
        if COLLECTION_NAME != "legal_knowledge":
            try:
                legacy_collection = self.client.get_collection("legal_knowledge")
                if self.collection.count() == 0 and legacy_collection.count() > 0:
                    self.search_collections.append(legacy_collection)
                    print(
                        f"RAG using legacy collection fallback: legal_knowledge -> {COLLECTION_NAME}"
                    )
            except Exception:
                pass
        self.embedding_error: Optional[str] = None

    def is_available(self) -> bool:
        return not self.embedding_error

    def _build_embeddings(self, texts: List[str]) -> List[List[float]]:
        try:
            return create_embeddings(texts)
        except Exception as exc:
            self.embedding_error = str(exc)
            print(
                f"Embedding unavailable for provider {get_embedding_provider()} "
                f"model {get_embedding_model()}: {exc}"
            )
            raise

    @staticmethod
    def _fallback_embedding(text: str, dimensions: int = FALLBACK_EMBEDDING_DIMENSIONS) -> List[float]:
        vector = [0.0] * dimensions
        clean = str(text or "").strip()
        if not clean:
            vector[0] = 1.0
            return vector

        for token in clean.split():
            digest = hashlib.sha256(token.encode("utf-8", errors="ignore")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        if not any(vector):
            for offset in range(0, min(len(clean), 256), 2):
                digest = hashlib.sha256(clean[offset : offset + 2].encode("utf-8", errors="ignore")).digest()
                index = int.from_bytes(digest[:4], "big") % dimensions
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign

        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def _build_embeddings_or_fallback(self, texts: List[str]) -> List[List[float]]:
        try:
            return self._build_embeddings(texts)
        except Exception as exc:
            self.embedding_error = str(exc)
            print(
                "RAG upsert downgraded to deterministic fallback embeddings "
                f"({FALLBACK_EMBEDDING_DIMENSIONS} dimensions)."
            )
            return [self._fallback_embedding(text) for text in texts]

    @staticmethod
    def _score_text_match(query: str, document: str) -> float:
        query = str(query or "").strip()
        document = str(document or "").strip()
        if not query or not document:
            return 0.0

        query_chars = {char for char in query if not char.isspace()}
        doc_chars = {char for char in document if not char.isspace()}
        overlap = len(query_chars & doc_chars) / max(len(query_chars), 1)
        ratio = SequenceMatcher(None, query[:80], document[:200]).ratio()
        substring_bonus = 0.35 if query and query in document else 0.0
        return overlap + ratio + substring_bonus

    @staticmethod
    def _expand_query_terms(query: str) -> List[str]:
        query = str(query or "").strip()
        if not query:
            return []

        expansions = [query]
        synonym_map = {
            "接警": ["报警", "处警", "报警人", "执法"],
            "现场": ["现场处置", "询问", "证据", "风险"],
            "纠纷": ["打架", "口角", "调解"],
            "伤害": ["受伤", "殴打", "故意伤害"],
        }
        for token, aliases in synonym_map.items():
            if token in query:
                expansions.extend(aliases)
        return list(dict.fromkeys([item for item in expansions if item]))

    def _search_without_embeddings(self, query: str, limit: int) -> List[str]:
        documents: List[str] = []
        try:
            for collection in self.search_collections:
                snapshot = collection.get(include=["documents"])
                documents.extend(snapshot.get("documents") or [])
        except Exception as exc:
            print(f"RAG lexical fallback failed: {exc}")
            return []

        query_terms = self._expand_query_terms(query)
        scored = []
        for document in documents:
            if not str(document or "").strip():
                continue
            best_score = max((self._score_text_match(term, document) for term in query_terms), default=0.0)
            scored.append((best_score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [document for score, document in scored[:limit] if score > 0]
        if matches:
            return matches
        return [document for _, document in scored[:limit]]

    def add_documents(self, texts: List[str], metadatas: List[dict] = None):
        if not texts:
            return

        embeddings = self._build_embeddings(texts)
        ids = [f"id_{i}_{os.urandom(4).hex()}" for i in range(len(texts))]
        valid_metadatas = (
            metadatas if metadatas else [{"source": "system_seed"} for _ in range(len(texts))]
        )

        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=valid_metadatas,
            ids=ids,
        )
        print(f"Added {len(texts)} documents to ChromaDB.")
        return ids

    def upsert_documents(self, ids: List[str], texts: List[str], metadatas: List[dict] = None):
        clean_rows = [
            (str(item_id or "").strip(), str(text or "").strip(), metadata or {})
            for item_id, text, metadata in zip(ids or [], texts or [], metadatas or [])
            if str(item_id or "").strip() and str(text or "").strip()
        ]
        if not clean_rows:
            return []

        clean_ids = [row[0] for row in clean_rows]
        clean_texts = [row[1] for row in clean_rows]
        clean_metadatas = [row[2] for row in clean_rows]
        embeddings = self._build_embeddings_or_fallback(clean_texts)
        self.collection.upsert(
            ids=clean_ids,
            embeddings=embeddings,
            documents=clean_texts,
            metadatas=clean_metadatas,
        )
        print(f"Upserted {len(clean_texts)} documents to ChromaDB.")
        return clean_ids

    def delete_by_ids(self, ids: List[str]):
        clean_ids = [str(item).strip() for item in ids or [] if str(item).strip()]
        if clean_ids:
            self.collection.delete(ids=clean_ids)

    def get_documents_by_metadata(self, where: dict, limit: int | None = None) -> List[dict]:
        kwargs = {"where": where, "include": ["documents", "metadatas"]}
        if limit is not None:
            kwargs["limit"] = limit
        results = self.collection.get(**kwargs)
        items: List[dict] = []
        for index, item_id in enumerate(results.get("ids") or []):
            metadata = (results.get("metadatas") or [{}])[index] or {}
            content = (results.get("documents") or [""])[index] or ""
            items.append(
                {
                    "id": item_id,
                    "content": content,
                    "source": metadata.get("source", "unknown"),
                    "title": metadata.get("title") or self._default_title(content),
                    "category": metadata.get("category") or "閫氱敤",
                    "tags": self._normalize_tags(metadata.get("tags")),
                    "metadata": metadata,
                }
            )
        return items

    @staticmethod
    def _default_title(document: str) -> str:
        text = str(document or "").strip()
        if not text:
            return "未命名知识"
        compact = text.replace("\n", " ")
        return compact[:30] + ("..." if len(compact) > 30 else "")

    @staticmethod
    def _normalize_tags(raw_tags) -> List[str]:
        if isinstance(raw_tags, list):
            return [str(item).strip() for item in raw_tags if str(item).strip()]
        if isinstance(raw_tags, str):
            separators = [",", "，", ";", "；", "\n"]
            text = raw_tags
            for sep in separators[1:]:
                text = text.replace(sep, separators[0])
            return [item.strip() for item in text.split(separators[0]) if item.strip()]
        return []

    def get_items(self, limit: int = 50, offset: int = 0) -> List[dict]:
        results = self.collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"],
        )
        items: List[dict] = []
        for index, item_id in enumerate(results.get("ids") or []):
            metadata = (results.get("metadatas") or [{}])[index] or {}
            content = (results.get("documents") or [""])[index] or ""
            items.append(
                {
                    "id": item_id,
                    "content": content,
                    "source": metadata.get("source", "unknown"),
                    "title": metadata.get("title") or self._default_title(content),
                    "category": metadata.get("category") or "通用",
                    "tags": self._normalize_tags(metadata.get("tags")),
                }
            )
        return items

    def get_documents_by_ids(self, ids: List[str]) -> List[dict]:
        clean_ids = [str(item).strip() for item in ids if str(item).strip()]
        if not clean_ids:
            return []
        results = self.collection.get(ids=clean_ids, include=["documents", "metadatas"])
        items: List[dict] = []
        for index, item_id in enumerate(results.get("ids") or []):
            metadata = (results.get("metadatas") or [{}])[index] or {}
            content = (results.get("documents") or [""])[index] or ""
            items.append(
                {
                    "id": item_id,
                    "content": content,
                    "source": metadata.get("source", "unknown"),
                    "title": metadata.get("title") or self._default_title(content),
                    "category": metadata.get("category") or "通用",
                    "tags": self._normalize_tags(metadata.get("tags")),
                }
            )
        return items

    def search(self, query: str, limit: int = 2) -> List[str]:
        if not query:
            return []

        try:
            query_embedding = self._build_embeddings([query])
        except Exception:
            print("RAG search downgraded to lexical fallback because embedding service is unavailable.")
            return self._search_without_embeddings(query, limit)

        for collection in self.search_collections:
            results = collection.query(query_embeddings=query_embedding, n_results=limit)
            if results.get("documents") and len(results["documents"][0]) > 0:
                return results["documents"][0]
        return []


rag_service = RAGService()
