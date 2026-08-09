import hashlib
import json
import threading
from typing import Any

import database
import models
from .rag_service import rag_service
from .case_intelligence_service import build_role_knowledge_view, format_role_knowledge_view
from .case_knowledge_repository import upsert_node


CASE_SOURCE = "case_library"
CASE_DOC_TYPE = "case_info"
ROLE_DOC_TYPE = "role_script"
CANONICAL_DOC_TYPE = "case_knowledge_node"
_SYNC_LOCK = threading.Lock()
_SYNC_FINGERPRINTS: dict[int, str] = {}


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()


def _safe_json_loads(value: Any, fallback: Any):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
        return parsed if parsed is not None else fallback
    except Exception:
        return fallback


def _to_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    parsed = _safe_json_loads(value, None)
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def _text(value: Any, fallback: str = "") -> str:
    clean = str(value or "").strip()
    return clean or fallback


def _list_block(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    return [f"{title}：", *[f"- {item}" for item in values]]


def case_info_id(case_id: int) -> str:
    return f"case:{case_id}:info"


def role_script_id(case_id: int, role_id: int) -> str:
    return f"case:{case_id}:role:{role_id}:script"


def canonical_node_id(case_id: int, node_id: str) -> str:
    return f"case:{case_id}:node:{node_id}"


def _canonical_nodes(case_id: int) -> list[models.CaseKnowledgeNode]:
    db = database.SessionLocal()
    try:
        return list(
            db.query(models.CaseKnowledgeNode)
            .filter_by(namespace=f"case:{int(case_id)}")
            .order_by(models.CaseKnowledgeNode.id.asc())
            .all()
        )
    finally:
        db.close()


def _canonical_documents(case: models.Case) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for node in _canonical_nodes(int(case.id)):
        if node.node_type == "source_appendix" or not str(node.content or "").strip():
            continue
        metadata = _safe_json_loads(node.metadata_json, {})
        role_name = str(metadata.get("role_name") or "").strip()
        if node.node_type == "role_memory" and not role_name:
            payload = _safe_json_loads(node.content, {})
            role_name = str(payload.get("name") or "").strip() if isinstance(payload, dict) else ""
        title = role_name or {
            "complete_story": "完整案件剧情",
            "case_intelligence": "案件事实索引",
            "role_memory": "角色记忆",
        }.get(node.node_type, node.node_id)
        docs.append(
            {
                "id": canonical_node_id(int(case.id), node.node_id),
                "content": node.content,
                "metadata": {
                    "source": CASE_SOURCE,
                    "doc_type": CANONICAL_DOC_TYPE,
                    "node_type": node.node_type,
                    "node_id": node.node_id,
                    "content_hash": node.content_hash,
                    "case_id": str(case.id),
                    "role_name": role_name,
                    "library": rag_service.normalize_library(
                        CASE_SOURCE,
                        source=CASE_SOURCE,
                        doc_type=CANONICAL_DOC_TYPE,
                    ),
                    "title": title,
                    "category": "案件知识节点",
                    "tags": f"案件库,{node.node_type}",
                },
            }
        )
    return docs


def _structured_complete_story(case: models.Case) -> str:
    structured = _safe_json_loads(getattr(case, "structured_data", None), {})
    if not isinstance(structured, dict):
        structured = {}
    story_world = structured.get("story_world") if isinstance(structured.get("story_world"), dict) else {}
    narrative_document = structured.get("narrative_document") if isinstance(structured.get("narrative_document"), dict) else {}
    candidates = (
        structured.get("complete_story"),
        structured.get("full_narrative"),
        story_world.get("complete_story"),
        narrative_document.get("content"),
        getattr(case, "background", None),
        getattr(case, "original_content", None),
    )
    return next((str(item).strip() for item in candidates if str(item or "").strip()), "")


def load_complete_story_source(
    case: models.Case | None,
    *,
    canonical_docs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Load the full case story for every actor turn, with legacy fallbacks."""
    if not case or not getattr(case, "id", None):
        return {"content": "", "content_hash": "", "source": "missing", "node_id": "story"}

    docs = canonical_docs if canonical_docs is not None else _canonical_documents(case)
    story_doc = next(
        (
            item for item in docs
            if (item.get("metadata") or {}).get("node_type") == "complete_story"
            or (item.get("metadata") or {}).get("node_id") == "story"
        ),
        None,
    )
    content = str((story_doc or {}).get("content") or "").strip()
    metadata = (story_doc or {}).get("metadata") or {}
    if content:
        return {
            "content": content,
            "content_hash": str(metadata.get("content_hash") or _content_hash(content)),
            "source": "case_knowledge_node",
            "node_id": str(metadata.get("node_id") or "story"),
        }

    content = _structured_complete_story(case)
    return {
        "content": content,
        "content_hash": _content_hash(content) if content else "",
        "source": "structured_data_fallback" if content else "missing",
        "node_id": "story",
    }


def sync_complete_story_source(case: models.Case | None) -> dict[str, Any]:
    """Keep the case-scoped canonical story node aligned after case edits."""
    if not case or not getattr(case, "id", None):
        return {"status": "skipped", "reason": "case_not_persisted"}
    content = _structured_complete_story(case)
    if not content:
        return {"status": "skipped", "reason": "complete_story_missing"}
    return upsert_node(
        f"case:{int(case.id)}",
        "story",
        "complete_story",
        content,
        metadata={"case_id": int(case.id), "role": "actor_global_story_baseline"},
    )


def _case_fact_lines(case: models.Case, structured: dict[str, Any]) -> list[str]:
    fact_sheet = structured.get("fact_sheet") if isinstance(structured.get("fact_sheet"), dict) else {}
    lines = [
        f"案件名称：{_text(case.title, '未命名案件')}",
        f"案件类型：{_text(case.case_type, '其他')}",
        f"案件背景：{_text(case.background, '暂无')}",
    ]
    for label, key in [
        ("案发时间", "case_time"),
        ("案发地点", "case_location"),
        ("报警时间", "report_time"),
        ("报警人", "reporter"),
    ]:
        if _text(fact_sheet.get(key)):
            lines.append(f"{label}：{_text(fact_sheet.get(key))}")

    full_narrative = _text(structured.get("full_narrative") or structured.get("criminal_process"))
    if full_narrative:
        lines.append(f"案件经过：{full_narrative}")
    elif _text(case.original_content):
        lines.append(f"原始案情：{_text(case.original_content)[:1600]}")

    for field, label in [
        ("evidence_points", "证据材料"),
        ("key_clues", "关键线索"),
        ("risk_points", "风险点"),
        ("inconsistencies", "矛盾点"),
    ]:
        values = _to_list(structured.get(field))
        lines.extend(_list_block(label, values))
    return lines


def _scene_lines(case: models.Case) -> list[str]:
    lines: list[str] = []
    scenes = sorted(case.scenes or [], key=lambda item: item.id or 0)
    if not scenes:
        return lines
    lines.append("训练场景：")
    for scene in scenes:
        lines.append(f"- {scene.name or '未命名场景'}：{scene.description or '暂无描述'}")
        if scene.dispatch_brief:
            lines.append(f"  接警/派警摘要：{scene.dispatch_brief}")
        if scene.first_impression:
            lines.append(f"  第一印象：{scene.first_impression}")
    return lines


def _role_script_lines(role: models.Role, case: models.Case) -> list[str]:
    persona_meta = _safe_json_loads(role.persona_meta, {})
    lines = [
        f"案件：{_text(case.title, '未命名案件')}",
        f"角色名称：{_text(role.name, '未命名角色')}",
        f"身份类型：{_text(role.role_type, '相关人员')}",
        f"身份信息：{_text(persona_meta.get('identity') or persona_meta.get('role') or role.role_type, '暂无')}",
        f"性格设定：{_text(role.personality, '普通人')}",
        f"情绪状态：初始情绪 {role.init_emotion if role.init_emotion is not None else 50}/100，初始信任 {role.init_trust if role.init_trust is not None else 30}/100，当前状态 {_text(role.status, '正常')}",
        f"回答逻辑：{_text(persona_meta.get('answer_logic') or persona_meta.get('pressure_response') or persona_meta.get('stress_response'), '按本人掌握事实作答；未被问到敏感内容时不主动完整展开。')}",
        f"行为倾向：{_text(persona_meta.get('behavior_tendency') or persona_meta.get('interaction_style') or role.interaction_style, '根据警方态度调整配合程度。')}",
        f"可透露内容：{'; '.join(_to_list(role.knows_facts)) or '暂无明确配置'}",
        f"不可主动透露内容：{'; '.join(_to_list(role.hidden_truths)) or '暂无明确配置'}",
        f"不知道/无法确认：{'; '.join(_to_list(role.does_not_know)) or '暂无明确配置'}",
    ]
    optional_fields = [
        ("掌握信息", "known_information"),
        ("隐藏信息", "hidden_information"),
        ("核心顾虑", "core_concern"),
        ("触发点", "trigger_points"),
        ("安抚点", "calming_points"),
        ("弱点", "weakness"),
    ]
    for label, key in optional_fields:
        raw_value = persona_meta.get(key) if isinstance(persona_meta, dict) else None
        values = _to_list(raw_value)
        if values:
            lines.extend(_list_block(label, values))
        elif key == "weakness" and role.weakness:
            lines.append(f"{label}：{role.weakness}")
    return lines


def build_case_knowledge_documents(case: models.Case) -> list[dict[str, Any]]:
    canonical_docs = _canonical_documents(case)
    if canonical_docs:
        return canonical_docs

    # Compatibility path for cases created before canonical knowledge nodes existed.
    structured = _safe_json_loads(case.structured_data, {})
    docs = [
        {
            "id": case_info_id(case.id),
            "content": "\n".join(_case_fact_lines(case, structured) + _scene_lines(case)),
            "metadata": {
                "source": CASE_SOURCE,
                "doc_type": CASE_DOC_TYPE,
                "case_id": str(case.id),
                "library": rag_service.normalize_library(CASE_SOURCE, source=CASE_SOURCE, doc_type=CASE_DOC_TYPE),
                "title": f"案件信息：{case.title or case.id}",
                "category": "案件信息",
                "tags": f"案件库,{case.case_type or '其他'}",
            },
        }
    ]
    for role in sorted(case.roles or [], key=lambda item: item.id or 0):
        if not role.id:
            continue
        docs.append(
            {
                "id": role_script_id(case.id, role.id),
                "content": "\n".join(_role_script_lines(role, case)),
                "metadata": {
                    "source": CASE_SOURCE,
                    "doc_type": ROLE_DOC_TYPE,
                    "case_id": str(case.id),
                    "role_id": str(role.id),
                    "role_name": role.name or "",
                    "library": rag_service.normalize_library(CASE_SOURCE, source=CASE_SOURCE, doc_type=ROLE_DOC_TYPE),
                    "title": f"角色剧本：{case.title or case.id} / {role.name or role.id}",
                    "category": "角色剧本",
                    "tags": f"角色剧本,{role.role_type or '相关人员'}",
                },
            }
        )
    return docs


def _documents_fingerprint(docs: list[dict[str, Any]]) -> str:
    payload = [
        {
            "id": doc.get("id"),
            "content": doc.get("content"),
            "metadata": doc.get("metadata") or {},
        }
        for doc in docs
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def sync_case_to_knowledge(case: models.Case) -> dict[str, Any]:
    docs = build_case_knowledge_documents(case)
    fingerprint = _documents_fingerprint(docs)
    case_id = int(case.id or 0)
    with _SYNC_LOCK:
        if case_id and _SYNC_FINGERPRINTS.get(case_id) == fingerprint:
            return {
                "ok": True,
                "sync_status": "skipped",
                "case_id": case.id,
                "synced_ids": [],
                "deleted_ids": [],
                "embedding_error": rag_service.embedding_error,
            }

        expected_ids = [doc["id"] for doc in docs]
        existing = rag_service.get_documents_by_metadata({"case_id": str(case.id)})
        stale_ids = [item["id"] for item in existing if item["id"] not in expected_ids]
        if stale_ids:
            rag_service.delete_by_ids(stale_ids)
        synced_ids = rag_service.upsert_documents(
            expected_ids,
            [doc["content"] for doc in docs],
            [doc["metadata"] for doc in docs],
        )
        if case_id:
            _SYNC_FINGERPRINTS[case_id] = fingerprint
        return {
            "ok": True,
            "sync_status": "ok",
            "case_id": case.id,
            "synced_ids": synced_ids,
            "deleted_ids": stale_ids,
            "embedding_error": rag_service.embedding_error,
        }


def try_sync_case_to_knowledge(case: models.Case) -> dict[str, Any]:
    try:
        story_sync = sync_complete_story_source(case)
        # The canonical node is authoritative for actor turns; RAG remains a
        # secondary index and is refreshed only after the story node is current.
        result = sync_case_to_knowledge(case)
        result["complete_story_sync"] = story_sync
        return result
    except Exception as exc:
        print(f"Case knowledge sync failed for case {getattr(case, 'id', None)}: {exc}")
        return {
            "ok": False,
            "sync_status": "failed",
            "case_id": getattr(case, "id", None),
            "error": str(exc),
        }


def delete_case_from_knowledge(case_id: int) -> dict[str, Any]:
    existing = rag_service.get_documents_by_metadata({"case_id": str(case_id)})
    ids = [item["id"] for item in existing]
    rag_service.delete_by_ids(ids)
    return {"case_id": case_id, "deleted_ids": ids}


def load_case_knowledge_bundle(case: models.Case | None, role: models.Role | None = None) -> dict[str, Any]:
    if not case or not getattr(case, "id", None):
        return {"documents": [], "knowledge_block": "暂无案件知识库内容"}

    # Actor models must not receive the full case document.  It contains facts
    # that a witness, suspect or caller may not know.  The full case remains
    # available to validators and admin tools; roleplay receives a scoped view.
    canonical_docs = _canonical_documents(case)
    complete_story_source = load_complete_story_source(case, canonical_docs=canonical_docs)
    ids = [] if role else [
        item["id"]
        for item in canonical_docs
        if (item.get("metadata") or {}).get("node_type") != "role_memory"
    ]
    if not role and not ids:
        ids = [case_info_id(case.id)]
    if role and getattr(role, "id", None):
        ids.append(role_script_id(case.id, role.id))

    if role:
        structured = _safe_json_loads(getattr(case, "structured_data", None), {})
        persona_meta = _safe_json_loads(getattr(role, "persona_meta", None), {})
        canonical_role = next(
            (
                node
                for node in _canonical_nodes(int(case.id))
                if node.node_id == f"role:{str(getattr(role, 'name', '') or '').strip()}"
            ),
            None,
        )
        canonical_payload = _safe_json_loads(canonical_role.content, {}) if canonical_role else {}
        canonical_payload = canonical_payload if isinstance(canonical_payload, dict) else {}
        role_payload = {
            **persona_meta,
            **canonical_payload,
            "knows_facts": _to_list(getattr(role, "knows_facts", None)) or _to_list(canonical_payload.get("knows_facts")),
            "hidden_truths": _to_list(getattr(role, "hidden_truths", None)) or _to_list(canonical_payload.get("hidden_truths")),
            "does_not_know": _to_list(getattr(role, "does_not_know", None)) or _to_list(canonical_payload.get("does_not_know")),
        }
        role_view = build_role_knowledge_view(
            structured,
            role_name=str(getattr(role, "name", "") or "相关人员"),
            role_payload=role_payload,
        )
        source_docs = canonical_docs or build_case_knowledge_documents(case)
        role_docs = [
            item for item in source_docs
            if (item.get("metadata") or {}).get("role_name") == getattr(role, "name", None)
            or item.get("id") == role_script_id(case.id, role.id)
        ]
        role_block = format_role_knowledge_view(role_view)
        return {
            "documents": role_docs,
            "knowledge_block": f"案件：{getattr(case, 'title', '') or case.id}\n{role_block}",
            "role_knowledge_view": role_view,
            "complete_story_source": complete_story_source,
        }

    docs = rag_service.get_documents_by_ids(ids)
    if len(docs) < len(ids):
        fallback_docs = canonical_docs or build_case_knowledge_documents(case)
        fallback_by_id = {doc["id"]: doc for doc in fallback_docs}
        existing_ids = {doc["id"] for doc in docs}
        for item_id in ids:
            if item_id not in existing_ids and item_id in fallback_by_id:
                item = fallback_by_id[item_id]
                docs.append(
                    {
                        "id": item["id"],
                        "content": item["content"],
                        "title": item["metadata"].get("title"),
                        "category": item["metadata"].get("category"),
                        "source": item["metadata"].get("source"),
                        "metadata": item["metadata"],
                    }
                )

    ordered = sorted(docs, key=lambda item: ids.index(item["id"]) if item["id"] in ids else 999)
    sections = []
    for doc in ordered:
        title = doc.get("title") or (doc.get("metadata") or {}).get("title") or doc["id"]
        content = str(doc.get("content") or "").strip()
        if content:
            sections.append(f"【{title}】\n{content[:2400]}")
    return {
        "documents": ordered,
        "knowledge_block": "\n\n".join(sections) or "暂无案件知识库内容",
        "complete_story_source": complete_story_source,
    }
