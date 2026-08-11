"""Prepare source-grounded training text and compact role memories."""
from __future__ import annotations

import re
from typing import Any

from .case_text_utils import strip_document_artifacts
from .role_information_management_service import compile_person_role_information


_JUDICIAL_NOISE = re.compile(
    r"^(?:审判长|审判员|人民陪审员|书记员|公诉机关|上诉人|原审被告人|关联文书|公告|如不服本判决|刑期从判决执行之日起|"
    r"本判决为终审判决|审判委员会|代理审判员|二〇|附录|目录|证据目录)"
)

_EVIDENCE_HEADING_RE = re.compile(
    r"^\s*(?:（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)|[一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十]+组)\s*"
    r"(?:证据|书证|物证|证人证言|被害人供述|被告人供述|鉴定意见|勘验|检查|辨认|视听资料|电子数据|到案经过|户籍证明|前科材料|判决书|裁定书)\s*$"
)


def compact_case_source(source_text: str) -> dict[str, Any]:
    original = str(source_text or "").replace("\r", "").strip()
    cleaned_source = strip_document_artifacts(original)
    judicial = any(token in cleaned_source for token in ("人民法院", "刑事判决书", "刑事裁定书", "经审理查明"))
    working = cleaned_source
    excluded: list[str] = []
    if judicial and "经审理查明" in working:
        prefix, body = working.split("经审理查明", 1)
        if prefix.strip():
            excluded.append(prefix.strip())
        working = "经审理查明" + body
    if judicial and "本院认为" in working:
        body, suffix = working.split("本院认为", 1)
        if suffix.strip():
            excluded.append("本院认为" + suffix.strip())
        working = body

    kept: list[str] = []
    for paragraph in re.split(r"\n+", working):
        clean = strip_document_artifacts(paragraph)
        if not clean:
            continue
        if (
            _JUDICIAL_NOISE.search(clean)
            or _EVIDENCE_HEADING_RE.search(clean)
            or re.search(r"男，?\d{4}年\d{1,2}月\d{1,2}日出生", clean)
        ):
            excluded.append(clean)
            continue
        clean = re.sub(r"(?:审判长|审判员|人民陪审员|书记员)[^。\n]{0,80}", "", clean)
        clean = re.sub(r"如不服本判决[^。\n]*。?", "", clean)
        clean = re.sub(r"(?:---\s*)?块\s*\d+\s*/\s*(?:paragraph|body|段落|正文|docx_xml_text|docx_xml)[^\n。；]*(?:---)?", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
        if not clean:
            continue
        kept.append(clean)
    training_text = strip_document_artifacts("\n\n".join(kept)).strip() or cleaned_source
    return {
        "training_text": training_text,
        "excluded_appendix": excluded,
        "is_judicial_document": judicial,
        "original_chars": len(original),
        "training_chars": len(training_text),
    }


def compact_role_memories(persons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in persons:
        person = dict(source)
        compacted: list[dict[str, Any]] = []
        for memory_index, raw in enumerate(person.get("role_memories") or [], start=1):
            if not isinstance(raw, dict):
                continue
            statement = strip_document_artifacts(raw.get("statement") or raw.get("content"))
            # A source block boundary means the extractor accidentally joined
            # the next judicial section into this person's statement.
            statement = re.split(r"\n\s*---\s*块\s*\d+", statement, maxsplit=1)[0].strip()
            if not statement:
                continue
            sentences = [item.strip() for item in re.split(r"(?<=[。！？；])", statement) if item.strip()]
            chunks: list[str] = []
            buffer = ""
            for sentence in sentences or [statement]:
                if buffer and len(buffer) + len(sentence) > 460:
                    chunks.append(buffer)
                    buffer = sentence
                else:
                    buffer += sentence
            if buffer:
                chunks.append(buffer)
            for chunk_index, chunk in enumerate(chunks, start=1):
                item = dict(raw)
                item["memory_id"] = str(raw.get("memory_id") or f"{person.get('name')}-M{memory_index}") + f"-{chunk_index}"
                item["statement"] = chunk
                item["content"] = chunk
                compacted.append(item)
        # Preserve all semantically distinct source memories. Long documents
        # are bounded by per-memory chunk size, not by discarding the tail.
        unique_memories: list[dict[str, Any]] = []
        seen_statements: set[str] = set()
        for item in compacted:
            normalized = re.sub(r"\s+", "", str(item.get("statement") or ""))
            if not normalized or normalized in seen_statements:
                continue
            seen_statements.add(normalized)
            unique_memories.append(item)
        person["role_memories"] = unique_memories
        output.append(compile_person_role_information(person))
    return output
