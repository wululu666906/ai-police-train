import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional
from difflib import SequenceMatcher

import chromadb

from .llm_provider import create_embeddings, get_embedding_model, get_embedding_provider

SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SERVICES_DIR)
_chroma_raw = os.getenv("CHROMA_DB_PATH", "chroma_db")
CHROMA_DB_PATH = _chroma_raw if os.path.isabs(_chroma_raw) else os.path.join(BACKEND_DIR, _chroma_raw)
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "legal_knowledge_qwen")
FALLBACK_EMBEDDING_DIMENSIONS = int(os.getenv("FALLBACK_EMBEDDING_DIMENSIONS", "1024"))
DEFAULT_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))
DEFAULT_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
DEFAULT_CONTEXT_MAX_CHARS = int(os.getenv("RAG_CONTEXT_MAX_CHARS", "3600"))

CASE_LIBRARY = "case_library"
ROLE_LIBRARY = "role_library"
LAW_LIBRARY = "law_library"
SOP_LIBRARY = "sop_library"
TRAINING_LIBRARY = "training_library"
GENERAL_LIBRARY = "general"

RUNTIME_RETRIEVAL_LIBRARIES = [
    LAW_LIBRARY,
    SOP_LIBRARY,
    TRAINING_LIBRARY,
    GENERAL_LIBRARY,
]

VALID_LIBRARIES = {
    CASE_LIBRARY,
    ROLE_LIBRARY,
    LAW_LIBRARY,
    SOP_LIBRARY,
    TRAINING_LIBRARY,
    GENERAL_LIBRARY,
}


@dataclass(frozen=True)
class TextChunk:
    content: str
    index: int
    start: int
    end: int


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

    @staticmethod
    def normalize_library(value: Any, *, source: str = "", category: str = "", doc_type: str = "") -> str:
        raw = str(value or "").strip()
        if raw in VALID_LIBRARIES:
            return raw

        source_text = str(source or "").strip()
        category_text = str(category or "").strip()
        doc_type_text = str(doc_type or "").strip()
        haystack = f"{raw} {source_text} {category_text} {doc_type_text}".lower()

        if source_text == CASE_LIBRARY and doc_type_text == "role_script":
            return ROLE_LIBRARY
        if "role_script" in haystack or "角色剧本" in haystack:
            return ROLE_LIBRARY
        if source_text == CASE_LIBRARY:
            return CASE_LIBRARY
        if "case_info" in haystack or "案件知识" in haystack or "案件信息" in haystack:
            return CASE_LIBRARY
        if any(token in haystack for token in ["law", "legal", "法律", "法规", "法条", "司法解释", "执法规范"]):
            return LAW_LIBRARY
        if any(token in haystack for token in ["sop", "流程", "处置", "接警", "出警", "询问", "审讯", "风险处置"]):
            return SOP_LIBRARY
        if any(token in haystack for token in ["training", "教学", "培训", "案例分析", "警务知识", "学习"]):
            return TRAINING_LIBRARY
        return GENERAL_LIBRARY

    @staticmethod
    def build_retrieval_query(*parts: Any, history: list[str] | None = None) -> str:
        values: list[str] = []
        for part in parts:
            text = str(part or "").strip()
            if text:
                values.append(text)
        for item in history or []:
            text = str(item or "").strip()
            if text:
                values.append(text)
        return "\n".join(values[:12])

    @staticmethod
    def normalize_text(text: Any) -> str:
        clean = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        clean = re.sub(r"[ \t\u3000]+", " ", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean.strip()

    @classmethod
    def split_text(
        cls,
        text: str,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[TextChunk]:
        clean = cls.normalize_text(text)
        if not clean:
            return []

        chunk_size = max(200, int(chunk_size or DEFAULT_CHUNK_SIZE))
        overlap = max(0, min(int(overlap or 0), chunk_size // 2))
        if len(clean) <= chunk_size:
            return [TextChunk(content=clean, index=0, start=0, end=len(clean))]

        chunks: List[TextChunk] = []
        start = 0
        while start < len(clean):
            hard_end = min(start + chunk_size, len(clean))
            end = hard_end
            if hard_end < len(clean):
                window = clean[start:hard_end]
                boundary_candidates = [
                    window.rfind("\n\n"),
                    window.rfind("\n"),
                    window.rfind("。"),
                    window.rfind("；"),
                    window.rfind(";"),
                    window.rfind("！"),
                    window.rfind("？"),
                    window.rfind(". "),
                ]
                boundary = max(boundary_candidates)
                if boundary >= int(chunk_size * 0.55):
                    end = start + boundary + 1

            content = clean[start:end].strip()
            if content:
                chunks.append(TextChunk(content=content, index=len(chunks), start=start, end=end))
            if end >= len(clean):
                break
            start = max(end - overlap, start + 1)
        return chunks

    @classmethod
    def stable_source_id(cls, *, title: str = "", source: str = "", content: str = "") -> str:
        seed = f"{source}\n{title}\n{cls.normalize_text(content)[:4000]}"
        digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"kb:{digest}"

    @staticmethod
    def _metadata_value(value: Any) -> str | int | float | bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, dict):
            return str(value)
        return str(value or "")

    @classmethod
    def _normalize_metadata(cls, metadata: dict | None, content: str = "") -> dict:
        metadata = dict(metadata or {})
        source = str(metadata.get("source") or "manual_upload").strip()
        category = str(metadata.get("category") or "通用").strip()
        doc_type = str(metadata.get("doc_type") or "").strip()
        library = cls.normalize_library(metadata.get("library"), source=source, category=category, doc_type=doc_type)
        tags = cls._normalize_tags(metadata.get("tags"))

        normalized = {
            **metadata,
            "source": source,
            "category": category,
            "library": library,
            "tags": ",".join(tags),
            "title": str(metadata.get("title") or cls._default_title(content)).strip(),
        }
        return {key: cls._metadata_value(value) for key, value in normalized.items() if value is not None}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

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

    @staticmethod
    def _metadata_matches(metadata: dict, filters: dict | None = None) -> bool:
        if not filters:
            return True
        for key, expected in filters.items():
            if expected in (None, "", []):
                continue
            actual = metadata.get(key)
            if key == "library":
                actual = RAGService.normalize_library(
                    actual,
                    source=metadata.get("source", ""),
                    category=metadata.get("category", ""),
                    doc_type=metadata.get("doc_type", ""),
                )
            if isinstance(expected, (list, tuple, set)):
                if str(actual) not in {str(item) for item in expected}:
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    def _search_without_embeddings(self, query: str, limit: int, filters: dict | None = None) -> List[dict]:
        documents: List[tuple[str, dict, str]] = []
        try:
            for collection in self.search_collections:
                snapshot = collection.get(include=["documents", "metadatas"])
                ids = snapshot.get("ids") or []
                raw_documents = snapshot.get("documents") or []
                metadatas = snapshot.get("metadatas") or []
                for index, document in enumerate(raw_documents):
                    metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
                    if self._metadata_matches(metadata, filters):
                        documents.append((ids[index] if index < len(ids) else "", metadata, document))
        except Exception as exc:
            print(f"RAG lexical fallback failed: {exc}")
            return []

        query_terms = self._expand_query_terms(query)
        scored = []
        for item_id, metadata, document in documents:
            if not str(document or "").strip():
                continue
            best_score = max((self._score_text_match(term, document) for term in query_terms), default=0.0)
            scored.append((best_score, item_id, metadata, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        rows = [row for row in scored[:limit] if row[0] > 0] or scored[:limit]
        return [
            self._item_from_parts(item_id, document, metadata, distance=None, relevance=float(score), fallback=True)
            for score, item_id, metadata, document in rows
        ]

    def add_documents(self, texts: List[str], metadatas: List[dict] = None):
        if not texts:
            return

        embeddings = self._build_embeddings_or_fallback(texts)
        ids = [f"id_{i}_{os.urandom(4).hex()}" for i in range(len(texts))]
        raw_metadatas = list(metadatas) if metadatas is not None else [{"source": "system_seed"} for _ in texts]
        if len(raw_metadatas) < len(texts):
            raw_metadatas.extend({} for _ in range(len(texts) - len(raw_metadatas)))
        valid_metadatas = [
            self._normalize_metadata(metadata, text)
            for text, metadata in zip(texts, raw_metadatas)
        ]

        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=valid_metadatas,
            ids=ids,
        )
        print(f"Added {len(texts)} documents to ChromaDB.")
        return ids

    def ingest_text(
        self,
        text: str,
        *,
        title: str = "",
        source: str = "manual_upload",
        category: str = "通用",
        tags: list[str] | str | None = None,
        library: str = "",
        source_id: str = "",
        extra_metadata: dict | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> dict[str, Any]:
        clean = self.normalize_text(text)
        if not clean:
            return {"source_id": source_id, "ids": [], "chunks": 0}

        source_id = source_id or self.stable_source_id(title=title, source=source, content=clean)
        chunks = self.split_text(clean, chunk_size=chunk_size, overlap=overlap)
        ids = [f"{source_id}:chunk:{chunk.index}" for chunk in chunks]
        base_metadata = {
            "source": source,
            "source_id": source_id,
            "title": title or self._default_title(clean),
            "category": category or "通用",
            "tags": tags or [],
            "library": library,
            "chunk_count": len(chunks),
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
            **(extra_metadata or {}),
        }
        metadatas = []
        for chunk in chunks:
            metadatas.append(
                self._normalize_metadata(
                    {
                        **base_metadata,
                        "chunk_id": ids[chunk.index],
                        "chunk_index": chunk.index,
                        "chunk_start": chunk.start,
                        "chunk_end": chunk.end,
                    },
                    chunk.content,
                )
            )
        synced = self.upsert_documents(ids, [chunk.content for chunk in chunks], metadatas)
        return {
            "source_id": source_id,
            "ids": synced,
            "chunks": len(synced),
            "chunk_size": chunk_size,
            "overlap": overlap,
        }

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
        now = self._now_iso()
        clean_metadatas = []
        for row in clean_rows:
            metadata = dict(row[2] or {})
            metadata.setdefault("created_at", now)
            metadata["updated_at"] = now
            clean_metadatas.append(self._normalize_metadata(metadata, row[1]))
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

    def delete_by_source_id(self, source_id: str) -> dict[str, Any]:
        clean_source_id = str(source_id or "").strip()
        if not clean_source_id:
            return {"source_id": "", "deleted_ids": []}
        rows = self.get_documents_by_metadata({"source_id": clean_source_id})
        ids = [item["id"] for item in rows if item.get("id")]
        self.delete_by_ids(ids)
        return {"source_id": clean_source_id, "deleted_ids": ids, "deleted_count": len(ids)}

    def _rows_from_chroma_results(self, results: dict) -> List[dict]:
        items: List[dict] = []
        ids = results.get("ids") or []
        metadatas = results.get("metadatas") or []
        documents = results.get("documents") or []
        for index, item_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            content = documents[index] if index < len(documents) and documents[index] else ""
            items.append(
                {
                    "id": item_id,
                    "content": content,
                    "source": metadata.get("source", "unknown"),
                    "title": metadata.get("title") or self._default_title(content),
                    "category": metadata.get("category") or "通用",
                    "library": metadata.get("library") or self.normalize_library(
                        metadata.get("library"),
                        source=metadata.get("source", ""),
                        category=metadata.get("category", ""),
                        doc_type=metadata.get("doc_type", ""),
                    ),
                    "tags": self._normalize_tags(metadata.get("tags")),
                    "metadata": metadata,
                }
            )
        return items

    def get_documents_by_metadata(self, where: dict, limit: int | None = None) -> List[dict]:
        kwargs = {"where": where, "include": ["documents", "metadatas"]}
        if limit is not None:
            kwargs["limit"] = limit
        results = self.collection.get(**kwargs)
        return self._rows_from_chroma_results(results)

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
        return self._rows_from_chroma_results(results)

    def get_all_items(self, *, include_documents: bool = True) -> List[dict]:
        try:
            include = ["metadatas"]
            if include_documents:
                include.append("documents")
            results = self.collection.get(include=include)
        except Exception as exc:
            print(f"RAG list all failed: {exc}")
            return []
        return self._rows_from_chroma_results(results)

    @staticmethod
    def _latest_time(*values: Any) -> str:
        clean = [str(value or "").strip() for value in values if str(value or "").strip()]
        return max(clean) if clean else ""

    def get_library_stats(self) -> dict[str, Any]:
        items = self.get_all_items(include_documents=False)
        libraries = {
            key: {
                "library": key,
                "chunk_count": 0,
                "source_count": 0,
                "latest_updated_at": "",
                "ingest_status": "empty",
                "retrieval_status": "degraded" if self.embedding_error else "available",
            }
            for key in VALID_LIBRARIES
        }
        source_map: dict[str, set[str]] = {key: set() for key in VALID_LIBRARIES}
        for item in items:
            metadata = item.get("metadata") or {}
            library = self.normalize_library(
                item.get("library"),
                source=item.get("source", ""),
                category=item.get("category", ""),
                doc_type=metadata.get("doc_type", ""),
            )
            if library not in libraries:
                library = GENERAL_LIBRARY
            libraries[library]["chunk_count"] += 1
            source_id = str(metadata.get("source_id") or item.get("id") or "").strip()
            if source_id:
                source_map[library].add(source_id)
            libraries[library]["latest_updated_at"] = self._latest_time(
                libraries[library]["latest_updated_at"],
                metadata.get("updated_at"),
                metadata.get("created_at"),
            )

        for library, source_ids in source_map.items():
            libraries[library]["source_count"] = len(source_ids)
            libraries[library]["ingest_status"] = "ready" if libraries[library]["chunk_count"] else "empty"

        return {
            "total_chunks": len(items),
            "total_sources": len(
                {
                    str((item.get("metadata") or {}).get("source_id") or item.get("id") or "").strip()
                    for item in items
                    if str((item.get("metadata") or {}).get("source_id") or item.get("id") or "").strip()
                }
            ),
            "embedding_available": not bool(self.embedding_error),
            "embedding_error": self.embedding_error,
            "libraries": libraries,
        }

    def get_sources(
        self,
        library: str | None = None,
        *,
        source_id: str | None = None,
        include_chunks: bool = False,
    ) -> List[dict[str, Any]]:
        requested_library = self.normalize_library(library) if str(library or "").strip() else ""
        requested_source_id = str(source_id or "").strip()
        grouped: dict[str, dict[str, Any]] = {}
        for item in self.get_all_items(include_documents=include_chunks):
            metadata = item.get("metadata") or {}
            item_library = self.normalize_library(
                item.get("library"),
                source=item.get("source", ""),
                category=item.get("category", ""),
                doc_type=metadata.get("doc_type", ""),
            )
            if requested_library and item_library != requested_library:
                continue

            source_id = str(metadata.get("source_id") or item.get("id") or "").strip()
            if not source_id:
                continue
            if requested_source_id and source_id != requested_source_id:
                continue
            row = grouped.setdefault(
                source_id,
                {
                    "source_id": source_id,
                    "title": item.get("title") or source_id,
                    "source": item.get("source") or "unknown",
                    "category": item.get("category") or "通用",
                    "library": item_library,
                    "tags": item.get("tags") or [],
                    "chunk_count": 0,
                    "created_at": str(metadata.get("created_at") or ""),
                    "updated_at": str(metadata.get("updated_at") or metadata.get("created_at") or ""),
                    "filename": str(metadata.get("filename") or ""),
                    "file_type": str(metadata.get("file_type") or ""),
                    "extract_method": str(metadata.get("extract_method") or ""),
                    "extract_engine": str(metadata.get("extract_engine") or ""),
                    "status": "ready",
                    "chunks": [],
                },
            )
            row["chunk_count"] += 1
            row["updated_at"] = self._latest_time(row.get("updated_at"), metadata.get("updated_at"), metadata.get("created_at"))
            row["created_at"] = row.get("created_at") or str(metadata.get("created_at") or "")
            if not row.get("filename") and metadata.get("filename"):
                row["filename"] = str(metadata.get("filename"))
            if include_chunks:
                row["chunks"].append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "content": item.get("content"),
                        "category": item.get("category"),
                        "library": item_library,
                        "source": item.get("source"),
                        "tags": item.get("tags") or [],
                        "metadata": metadata,
                    }
                )

        return sorted(
            grouped.values(),
            key=lambda item: (str(item.get("updated_at") or ""), str(item.get("title") or "")),
            reverse=True,
        )

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
                    "library": metadata.get("library") or self.normalize_library(
                        metadata.get("library"),
                        source=metadata.get("source", ""),
                        category=metadata.get("category", ""),
                        doc_type=metadata.get("doc_type", ""),
                    ),
                    "tags": self._normalize_tags(metadata.get("tags")),
                    "metadata": metadata,
                }
            )
        return items

    def _build_filters(self, *, libraries: list[str] | None = None, where: dict | None = None) -> dict:
        filters = dict(where or {})
        clean_libraries = [
            self.normalize_library(item)
            for item in (libraries or [])
            if str(item or "").strip()
        ]
        if clean_libraries:
            filters["library"] = list(dict.fromkeys(clean_libraries))
        return filters

    def _item_from_parts(
        self,
        item_id: str,
        document: str,
        metadata: dict,
        *,
        distance: float | None,
        relevance: float | None = None,
        fallback: bool = False,
    ) -> dict:
        metadata = metadata or {}
        if relevance is None:
            relevance = 1.0 / (1.0 + float(distance)) if distance is not None else 0.0
        return {
            "id": item_id,
            "content": document or "",
            "source": metadata.get("source", "unknown"),
            "title": metadata.get("title") or self._default_title(document),
            "category": metadata.get("category") or "通用",
            "library": metadata.get("library") or self.normalize_library(
                metadata.get("library"),
                source=metadata.get("source", ""),
                category=metadata.get("category", ""),
                doc_type=metadata.get("doc_type", ""),
            ),
            "tags": self._normalize_tags(metadata.get("tags")),
            "metadata": metadata,
            "distance": distance,
            "relevance": relevance,
            "fallback": fallback,
        }

    def search_items(
        self,
        query: str,
        limit: int = DEFAULT_TOP_K,
        *,
        libraries: list[str] | None = None,
        where: dict | None = None,
    ) -> List[dict]:
        if not str(query or "").strip():
            return []

        filters = self._build_filters(libraries=libraries, where=where)
        try:
            query_embedding = self._build_embeddings([query])
        except Exception:
            print("RAG search downgraded to lexical fallback because embedding service is unavailable.")
            return self._search_without_embeddings(query, limit, filters)

        hits: List[dict] = []
        fetch_limit = max(limit, limit * 4 if filters else limit)
        for collection in self.search_collections:
            try:
                results = collection.query(
                    query_embeddings=query_embedding,
                    n_results=fetch_limit,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception as exc:
                print(f"RAG vector query failed: {exc}")
                continue

            ids = (results.get("ids") or [[]])[0] if results.get("ids") else []
            documents = (results.get("documents") or [[]])[0] if results.get("documents") else []
            metadatas = (results.get("metadatas") or [[]])[0] if results.get("metadatas") else []
            distances = (results.get("distances") or [[]])[0] if results.get("distances") else []
            for index, document in enumerate(documents):
                metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
                if not self._metadata_matches(metadata, filters):
                    continue
                hits.append(
                    self._item_from_parts(
                        ids[index] if index < len(ids) else "",
                        document,
                        metadata,
                        distance=distances[index] if index < len(distances) else None,
                    )
                )
                if len(hits) >= limit:
                    return hits[:limit]
        return hits[:limit]

    def search(self, query: str, limit: int = 2) -> List[str]:
        return [item["content"] for item in self.search_items(query, limit=limit)]

    def build_context_block(
        self,
        query: str,
        *,
        limit: int = DEFAULT_TOP_K,
        libraries: list[str] | None = None,
        where: dict | None = None,
        max_chars: int = DEFAULT_CONTEXT_MAX_CHARS,
    ) -> dict[str, Any]:
        try:
            hits = self.search_items(
                query,
                limit=limit,
                libraries=libraries,
                where=where,
            )
        except Exception as exc:
            print(f"RAG context retrieval disabled for this turn: {exc}")
            return {"hits": [], "context_block": "", "error": str(exc)}

        sections: List[str] = []
        used_chars = 0
        for index, item in enumerate(hits, start=1):
            title = str(item.get("title") or item.get("id") or f"知识片段{index}").strip()
            library = str(item.get("library") or "").strip()
            content = self.normalize_text(item.get("content") or "")
            if not content:
                continue
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            clipped = content[: max(0, remaining - 120)]
            if not clipped:
                break
            sections.append(f"[{index}] {title}（{library or 'knowledge'}）\n{clipped}")
            used_chars += len(clipped)

        return {
            "hits": hits,
            "context_block": "\n\n".join(sections),
            "error": None,
        }


rag_service = RAGService()
