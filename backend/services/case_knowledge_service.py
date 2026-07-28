import hashlib
import json
import threading
from typing import Any

import models
from .rag_service import rag_service
from .case_intelligence_service import build_role_knowledge_view, format_role_knowledge_view


CASE_SOURCE = "case_library"
CASE_DOC_TYPE = "case_info"
ROLE_DOC_TYPE = "role_script"
_SYNC_LOCK = threading.Lock()
_SYNC_FINGERPRINTS: dict[int, str] = {}


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
        return sync_case_to_knowledge(case)
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
    ids = [] if role else [case_info_id(case.id)]
    if role and getattr(role, "id", None):
        ids.append(role_script_id(case.id, role.id))

    if role:
        structured = _safe_json_loads(getattr(case, "structured_data", None), {})
        persona_meta = _safe_json_loads(getattr(role, "persona_meta", None), {})
        role_payload = {
            **persona_meta,
            "knows_facts": _to_list(getattr(role, "knows_facts", None)),
            "hidden_truths": _to_list(getattr(role, "hidden_truths", None)),
            "does_not_know": _to_list(getattr(role, "does_not_know", None)),
        }
        role_view = build_role_knowledge_view(
            structured,
            role_name=str(getattr(role, "name", "") or "相关人员"),
            role_payload=role_payload,
        )
        return {
            "documents": [],
            "knowledge_block": format_role_knowledge_view(role_view),
            "role_knowledge_view": role_view,
        }

    docs = rag_service.get_documents_by_ids(ids)
    if len(docs) < len(ids):
        fallback_docs = build_case_knowledge_documents(case)
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
    return {"documents": ordered, "knowledge_block": "\n\n".join(sections) or "暂无案件知识库内容"}
