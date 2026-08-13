from __future__ import annotations

from typing import Any

from services.agent_workflow_client import agent_workflow_client


def _case_world_from_legacy(case_info: dict[str, Any]) -> dict[str, Any]:
    persons = []
    for index, person in enumerate(case_info.get("persons") or []):
        if not isinstance(person, dict):
            continue
        persons.append({
            "person_id": str(person.get("person_id") or f"P{index + 1:03d}"),
            "name": str(person.get("name") or "未知人物"),
            "role": str(person.get("role_type") or person.get("role") or "相关人员"),
            "facts_known": [str(item) for item in person.get("knows_facts") or person.get("facts_known") or []],
            "facts_hidden": [str(item) for item in person.get("hidden_truths") or person.get("facts_hidden") or []],
        })
    facts = []
    for index, fact in enumerate(case_info.get("facts") or case_info.get("fact_cards") or []):
        if not isinstance(fact, dict):
            continue
        facts.append({
            "fact_id": str(fact.get("fact_id") or fact.get("id") or f"F{index + 1:03d}"),
            "content": str(fact.get("content") or fact.get("fact") or ""),
            "source": str(fact.get("source") or ""),
            "known_by": list(fact.get("known_by") or []),
            "unknown_by": list(fact.get("unknown_by") or []),
            "secret": bool(fact.get("secret")),
        })
    return {
        "case_id": str(case_info.get("case_id") or case_info.get("id") or "draft"),
        "title": str(case_info.get("case_name") or case_info.get("title") or ""),
        "summary": str(case_info.get("case_background") or case_info.get("summary") or ""),
        "persons": persons,
        "facts": facts,
        "timeline": list(case_info.get("timeline") or []),
        "locations": list(case_info.get("locations") or []),
        "relationships": list(case_info.get("relationships") or []),
    }


def parse_case_with_agent(text: str, *, workflow_id: str, case_id: str = "draft") -> dict[str, Any]:
    parsed = agent_workflow_client.execute(
        workflow_id=workflow_id,
        stage="CASE_UPLOADED",
        skill="case_parse",
        case_id=case_id,
        payload={"source_text": text},
        idempotency_key=f"{workflow_id}-parse",
    )["result"]["case_world"]
    personas = agent_workflow_client.execute(
        workflow_id=f"{workflow_id}-personas",
        stage="CASE_PARSED",
        skill="persona_build",
        case_id=case_id,
        payload={"case_world": parsed},
        idempotency_key=f"{workflow_id}-personas",
    )["result"]["personas"]
    persona_index = {item["person_id"]: item for item in personas}
    persons = []
    for person in parsed.get("persons") or []:
        persona = persona_index.get(person.get("person_id"), {})
        persons.append({
            **person,
            "role_type": person.get("role"),
            "knows_facts": person.get("facts_known") or [],
            "hidden_truths": person.get("facts_hidden") or [],
            "personality": "、".join(persona.get("traits") or []),
            "speaking_style": persona.get("speaking_style") or "自然口语",
            "persona_meta": persona,
        })
    return {
        "case_name": parsed.get("title") or "未命名案件",
        "case_type": "其他",
        "case_background": parsed.get("summary") or "",
        "persons": persons,
        "facts": parsed.get("facts") or [],
        "timeline": parsed.get("timeline") or [],
        "locations": parsed.get("locations") or [],
        "relationships": parsed.get("relationships") or [],
        "case_world": parsed,
        "personas": personas,
        "original_content": text,
        "rawText": text,
        "ai_workflow": {"engine": "agent-workflow-v1", "skills": ["case_parse", "persona_build"]},
    }


def generate_scenes_with_agent(case_info: dict[str, Any], *, workflow_id: str) -> dict[str, Any]:
    case_world = case_info.get("case_world") or _case_world_from_legacy(case_info)
    result = agent_workflow_client.execute(
        workflow_id=workflow_id,
        stage="PERSONAS_READY",
        skill="scene_build",
        case_id=str(case_world.get("case_id") or "draft"),
        payload={"case_world": case_world, "name": case_info.get("case_name") or case_info.get("title")},
        idempotency_key=f"{workflow_id}-scene",
    )["result"]["scene_world"]
    return {
        "scenes": [{
            "scene_id": result["scene_id"],
            "scene_name": result["name"],
            "name": result["name"],
            "description": str(result.get("environment", {}).get("description") or case_world.get("summary") or ""),
            "roles": result.get("role_ids") or [],
            "stages": [],
        }],
        "scene_world": result,
        "scene_generation_mode": "agent-workflow-v1",
        "ai_workflow": {"engine": "agent-workflow-v1", "skills": ["scene_build"]},
    }
