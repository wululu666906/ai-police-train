"""Case-scoped canonical knowledge nodes with content-hash deduplication."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import database
import models


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def upsert_node(namespace: str, node_id: str, node_type: str, value: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    content_hash = _hash(content)
    db = database.SessionLocal()
    try:
        node = db.query(models.CaseKnowledgeNode).filter_by(namespace=namespace, node_id=node_id).first()
        status = "reused" if node and node.content_hash == content_hash else "updated" if node else "created"
        if not node:
            node = models.CaseKnowledgeNode(namespace=namespace, node_id=node_id)
            db.add(node)
        node.node_type = node_type
        node.content_hash = content_hash
        node.content = content
        node.metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        db.commit()
        return {"node_id": node_id, "node_type": node_type, "content_hash": content_hash, "status": status}
    finally:
        db.close()


def store_case_knowledge(namespace: str, case_info: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = [upsert_node(namespace, "story", "complete_story", case_info.get("complete_story") or "")]
    story_documents = case_info.get("story_documents") if isinstance(case_info.get("story_documents"), dict) else {}
    event_document = story_documents.get("event_ledger") if isinstance(story_documents.get("event_ledger"), dict) else {}
    manifest.append(upsert_node(namespace, "story:event-ledger", "complete_story_event_ledger", event_document))
    manifest.append(upsert_node(namespace, "intelligence", "case_intelligence", case_info.get("case_intelligence") or {}))
    for node in (case_info.get("story_world") or {}).get("nodes") or []:
        if not isinstance(node, dict) or not str(node.get("node_id") or "").strip():
            continue
        node_id = str(node["node_id"]).strip()
        manifest.append(upsert_node(
            namespace,
            f"story-node:{node_id}",
            "story_node",
            node,
            metadata={"time": node.get("time"), "place": node.get("place"), "present_roles": node.get("present_roles") or []},
        ))
    for person in case_info.get("persons") or []:
        if not isinstance(person, dict) or not str(person.get("name") or "").strip():
            continue
        name = str(person["name"]).strip()
        manifest.append(upsert_node(namespace, f"role:{name}", "role_memory", {
            "name": name,
            "role_type": person.get("role_type") or person.get("role"),
            "role_memories": person.get("role_memories") or [],
            "knowledge_ledger": person.get("knowledge_ledger") or [],
            "role_event_ledger": person.get("role_event_ledger") or [],
            "role_information_version": person.get("role_information_version") or "",
            "soul_profile": person.get("soul_profile") or {},
        }))
    return manifest


def bind_namespace(source_namespace: str, case_id: int) -> str:
    target = f"case:{int(case_id)}"
    if not source_namespace or source_namespace == target:
        return target
    db = database.SessionLocal()
    try:
        rows = db.query(models.CaseKnowledgeNode).filter_by(namespace=source_namespace).all()
        for row in rows:
            existing = db.query(models.CaseKnowledgeNode).filter_by(namespace=target, node_id=row.node_id).first()
            if existing:
                existing.node_type = row.node_type
                existing.content_hash = row.content_hash
                existing.content = row.content
                existing.metadata_json = row.metadata_json
                db.delete(row)
            else:
                row.namespace = target
        db.commit()
        return target
    finally:
        db.close()
