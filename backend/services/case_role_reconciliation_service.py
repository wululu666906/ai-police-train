"""Reconcile source-grounded people and role memories after story generation."""
from __future__ import annotations

import re
from typing import Any

from .role_information_management_service import compile_person_role_information
from .workflow_service import workflow_service


_NON_TRAINING_ROLES = (
    "审判员", "审判长", "人民陪审员", "书记员", "公诉人", "公诉机关",
    "辩护人", "代理审判员", "法院", "检察院",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_training_person(person: dict[str, Any], source_text: str) -> bool:
    name = _text(person.get("name"))
    role = _text(person.get("role_type") or person.get("role"))
    return bool(
        name
        and name in source_text
        and not any(token in role or token in name for token in _NON_TRAINING_ROLES)
    )


def _story_context(name: str, story: str) -> list[dict[str, Any]]:
    """Return non-factual narrative context for persona shaping only."""
    rows: list[dict[str, Any]] = []
    for paragraph in re.split(r"\n{2,}|(?<=[。！？])\s*\n", _text(story)):
        clean = paragraph.strip()
        if name not in clean or len(clean) < 8:
            continue
        rows.append({
            "content": clean[:800],
            "source": "complete_story",
            "is_scoring_fact": False,
            "usage": "persona_context_only",
        })
        if len(rows) >= 4:
            break
    return rows


def _seed_identity_memories(person: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep source-verified people even when event memory extraction is sparse."""
    name = _text(person.get("name"))
    role = _text(person.get("role_type") or person.get("role") or "相关人员")
    seeds: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in [*_items(person.get("knows_facts")), *_items(person.get("known_key_points"))]:
        statement = _text(raw)
        if not statement or statement in seen:
            continue
        seen.add(statement)
        seeds.append({
            "memory_id": f"{name}-ID{len(seeds) + 1}",
            "memory_type": "source_identity",
            "statement": statement[:500],
            "time_hint": "未明确",
            "place_hint": "未明确",
            "actors": [name] if name else [],
            "certainty": "source_supported",
            "quote": statement[:180],
        })
    if not seeds and name:
        seeds.append({
            "memory_id": f"{name}-ID1",
            "memory_type": "source_identity",
            "statement": f"{name}在原文中作为{role}出现，身份已核对，经历细节待结合原文补全。",
            "time_hint": "未明确",
            "place_hint": "未明确",
            "actors": [name],
            "certainty": "source_supported",
            "quote": name,
        })
    return seeds


def _merge_person(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in ("role", "role_type", "status", "role_basis", "source_verification", "persona_source"):
        if not _text(merged.get(key)) and _text(incoming.get(key)):
            merged[key] = incoming[key]
    memories = [dict(item) for item in _items(merged.get("role_memories")) if isinstance(item, dict)]
    memories.extend(dict(item) for item in _items(incoming.get("role_memories")) if isinstance(item, dict))
    merged["role_memories"] = memories
    for key in ("unresolved_claims", "response_constraints", "source_refs"):
        values = [item for item in _items(merged.get(key)) if item]
        values.extend(item for item in _items(incoming.get(key)) if item and item not in values)
        merged[key] = values
    for key in ("knows_facts", "known_key_points"):
        values = [_text(item) for item in _items(merged.get(key)) if _text(item)]
        values.extend(_text(item) for item in _items(incoming.get(key)) if _text(item) and _text(item) not in values)
        if values:
            merged[key] = values
    merged.setdefault("status", "正常")
    merged.setdefault("source_verification", "source_matched")
    merged.setdefault("persona_source", "source_role_reconciliation")
    merged["persona_autofill"] = False
    return compile_person_role_information(merged)


def reconcile_case_roles(
    case_info: dict[str, Any],
    *,
    source_text: str,
    complete_story: str,
) -> dict[str, Any]:
    """Recover source-verified people and attach event memories before personas."""
    source = _text(source_text)
    existing = [dict(item) for item in _items(case_info.get("persons")) if isinstance(item, dict)]
    source_people = workflow_service._programmatic_people(source)

    people_by_name: dict[str, dict[str, Any]] = {}
    for person in existing:
        if _is_training_person(person, source):
            people_by_name[_text(person.get("name"))] = person
    recovered_names: list[str] = []
    for person in source_people:
        if not _is_training_person(person, source):
            continue
        name = _text(person.get("name"))
        if name not in people_by_name:
            people_by_name[name] = person
            recovered_names.append(name)
        else:
            people_by_name[name] = _merge_person(people_by_name[name], person)

    candidates = list(people_by_name.values())
    cards = workflow_service._programmatic_claim_cards(source)
    source_sections = workflow_service._classify_source_sections(source)
    reconstruction = workflow_service._build_role_memories_and_case_flow(
        source, candidates, cards, source_sections
    )

    final_people: list[dict[str, Any]] = []
    excluded_unusable_names: list[str] = []
    identity_seeded_names: list[str] = []
    for person in candidates:
        name = _text(person.get("name"))
        source_memory_person = {
            "name": name,
            "role_memories": reconstruction.get("role_memories", {}).get(name, []),
            "response_constraints": ["只依据本人亲历、亲眼所见、本人陈述及本轮公开信息回答。"],
        }
        merged = _merge_person(person, source_memory_person)
        merged["narrative_context"] = _story_context(name, complete_story)
        if not _items(merged.get("role_memories")):
            seeded = _seed_identity_memories(merged)
            if seeded:
                merged["role_memories"] = seeded
                identity_seeded_names.append(name)
                merged = compile_person_role_information(merged)
        if not _items(merged.get("role_memories")) and not _items(merged.get("narrative_context")):
            excluded_unusable_names.append(name)
            continue
        final_people.append(merged)

    source_names = [_text(item.get("name")) for item in source_people if _is_training_person(item, source)]
    story_names = [name for name in source_names if name and name in complete_story]
    final_names = {_text(person.get("name")) for person in final_people}
    retained_recovered_names = [name for name in recovered_names if name in final_names]
    memory_count = sum(len(_items(person.get("role_memories"))) for person in final_people)
    zero_memory_names = [
        _text(person.get("name"))
        for person in final_people
        if not _items(person.get("role_memories"))
    ]
    stats = {
        "source_candidate_count": len(set(source_names)),
        "story_candidate_count": len(set(story_names)),
        "input_person_count": len(existing),
        "final_person_count": len(final_people),
        "memory_count": memory_count,
        "recovered_person_count": len(retained_recovered_names),
        "recovered_person_names": retained_recovered_names,
        "excluded_unusable_person_names": excluded_unusable_names,
        "identity_seeded_person_names": identity_seeded_names,
        "zero_memory_person_names": zero_memory_names,
        "status": "completed",
    }

    result = dict(case_info)
    result["persons"] = final_people
    result["role_reconciliation"] = stats
    warnings = [_text(item) for item in _items(result.get("parse_warnings")) if _text(item)]
    if len(set(source_names)) > 1 and len(final_people) <= 1:
        warnings.append("人物对账未覆盖原文中的多名训练相关人员，请人工复核来源材料。")
        stats["status"] = "coverage_warning"
    if final_people and memory_count == 0:
        warnings.append("人物对账后仍未形成来源事件记忆，请人工复核原文结构。")
        stats["status"] = "memory_warning"
    elif identity_seeded_names:
        warnings.append("部分人物仅保留来源身份记忆，建议复核补齐亲历经历：" + "、".join(identity_seeded_names[:12]))
    elif zero_memory_names:
        warnings.append("部分人物仅有来源身份、暂无可核对经历：" + "、".join(zero_memory_names[:12]))
    result["parse_warnings"] = list(dict.fromkeys(warnings))
    return result
