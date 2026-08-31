from __future__ import annotations

import ast
from typing import Any

from services.agent_workflow_client import agent_workflow_client


def _location_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("location") or value.get("address") or "").strip()
    text = str(value or "").strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return _location_text(parsed)
    return text


def _parse_case_import_result(text: str, *, workflow_id: str, case_id: str, source_mode: str = "plain_case") -> dict[str, Any]:
    imported = agent_workflow_client.execute_case_import(
        workflow_id=workflow_id,
        case_id=case_id,
        source_text=text,
        idempotency_key=f"{workflow_id}-case-import",
    )["result"]
    parsed = imported["case_world"]
    memory_index = {item["person_id"]: item for item in imported.get("role_memories") or []}
    scene_blueprints = imported.get("scene_blueprints") or imported.get("necessary_scenes") or []
    persons = []
    for person in parsed.get("persons") or []:
        memory = memory_index.get(person.get("person_id"), {})
        initial_state = person.get("initial_state") or memory.get("initial_state") or {}
        persons.append({
            **person,
            "role_type": person.get("role"),
            "knows_facts": person.get("facts_known") or [],
            "hidden_truths": person.get("facts_hidden") or [],
            "role_memories": memory.get("role_memories") or [],
            "knowledge_ledger": memory.get("knowledge_ledger") or [],
            "persona_meta": memory,
            "personality": "，".join(str(item) for item in person.get("traits") or [] if str(item).strip()),
            "speaking_style": person.get("speaking_style") or "自然口语",
            "current_goal": next((str(item) for item in person.get("goals") or [] if str(item).strip()), "按本人立场自然回应"),
            "init_emotion": initial_state.get("emotion", 50),
            "init_trust": initial_state.get("cooperation", 35),
            "init_risk": initial_state.get("risk", 50),
            "init_expression_clarity": initial_state.get("clarity", 50),
        })
    locations = list(dict.fromkeys(_location_text(item) for item in parsed.get("locations") or [] if _location_text(item)))
    return {
        "case_id": parsed.get("case_id") or case_id,
        "case_name": parsed.get("title") or "未命名案件",
        "case_type": parsed.get("case_type") or "其他",
        "case_background": parsed.get("summary") or "",
        "persons": persons,
        "facts": parsed.get("facts") or [],
        "timeline": parsed.get("timeline") or [],
        "locations": locations,
        "relationships": parsed.get("relationships") or [],
        "fact_sheet": {
            "case_location": locations[0] if locations else "",
            "case_time": next((str(item.get("time") or item.get("date") or "") for item in parsed.get("timeline") or [] if isinstance(item, dict)), ""),
            "timeline": parsed.get("timeline") or [],
        },
        "key_facts": [str(item.get("content") or "") for item in parsed.get("facts") or [] if isinstance(item, dict) and str(item.get("content") or "").strip()],
        "case_world": parsed,
        "complete_story": imported.get("complete_story") or text,
        "story_world": imported.get("story_world") or {},
        "scene_blueprint": imported.get("scene_blueprint") or {},
        "scene_blueprints": imported.get("scene_blueprints") or imported.get("necessary_scenes") or [],
        "necessary_scenes": imported.get("necessary_scenes") or imported.get("scene_blueprints") or [],
        "training_scripts": imported.get("training_scripts") or [],
        "training_read_sources": imported.get("training_read_sources") or {},
        "case_import_quality": imported.get("case_import_quality") or {},
        "original_content": text,
        "rawText": text,
        "source_mode": source_mode,
        "ai_workflow": {"engine": "agent-workflow-v2-flowchart", "skills": ["case_import_harness"]},
    }


def parse_case_with_agent(text: str, *, workflow_id: str, case_id: str = "draft", source_mode: str = "plain_case") -> dict[str, Any]:
    return _parse_case_import_result(text, workflow_id=workflow_id, case_id=case_id, source_mode=source_mode)


def _scenes_from_training_scripts(case_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Compile script points 1-6 into scene JSON payloads when blueprints are absent."""
    scripts = case_info.get("training_scripts") or []
    case_id = str(case_info.get("case_id") or "draft")
    scenes: list[dict[str, Any]] = []
    for index, script in enumerate(scripts[:4]):
        if not isinstance(script, dict):
            continue
        scene_pack = script.get("scene_pack") if isinstance(script.get("scene_pack"), dict) else {}
        scene_name = str(script.get("scene_name") or "").strip()
        if not scene_name:
            continue
        scenes.append({
            "scene_id": f"{case_id}-scene-{index + 1}",
            "scene_name": scene_name,
            "scene_description": str(script.get("plot_arc") or case_info.get("case_background") or ""),
            "training_goal": str(script.get("training_goal") or ""),
            "student_role": str(scene_pack.get("student_role") or "民警"),
            "training_entry_phase": str(scene_pack.get("training_entry_phase") or "post_incident_onsite"),
            "dispatch_brief": str(scene_pack.get("dispatch_brief") or ""),
            "first_impression": str(scene_pack.get("first_impression") or ""),
            "expected_outcomes": list(script.get("expected_outcomes") or []),
            "plot_arc": str(script.get("plot_arc") or ""),
            "opening_lines": [item for item in script.get("opening_lines") or [] if isinstance(item, dict)],
            "opening_config": {
                "enabled": True,
                "mode": "preset" if script.get("opening_lines") else "dynamic",
                "preset_turns": [
                    {
                        "speaker_name": str(item.get("speaker_name") or "").strip(),
                        "content": str(item.get("content") or "").strip(),
                    }
                    for item in script.get("opening_lines") or []
                    if isinstance(item, dict) and str(item.get("content") or "").strip()
                ],
            },
            "stages": [item for item in script.get("stages") or [] if isinstance(item, dict)],
            "role_training_functions": [item for item in script.get("role_training_functions") or [] if isinstance(item, dict)],
            "completion_criteria": list(script.get("completion_criteria") or []),
            "failure_patterns": list(script.get("failure_patterns") or []),
            "roles": [
                str(item.get("role_name") or "").strip()
                for item in script.get("role_training_functions") or []
                if isinstance(item, dict) and str(item.get("role_name") or "").strip()
            ],
            "fact_ids": list(dict.fromkeys(
                str(fid)
                for stage in script.get("stages") or []
                if isinstance(stage, dict)
                for fid in stage.get("fact_ids") or []
                if str(fid).strip()
            )),
        })
    return scenes


def generate_scenes_with_agent(case_info: dict[str, Any], *, workflow_id: str) -> dict[str, Any]:
    blueprints = case_info.get("necessary_scenes") or case_info.get("scene_blueprints") or []
    if not blueprints and isinstance(case_info.get("scene_blueprint"), dict):
        blueprints = [case_info["scene_blueprint"]]
    blueprints = [item for item in blueprints if isinstance(item, dict) and item.get("scene_id")][:4]
    generation_mode = "agent-workflow-v2-flowchart"
    if not blueprints:
        blueprints = _scenes_from_training_scripts(case_info)
        if blueprints:
            generation_mode = "script-first-direct"
    if blueprints:
        blueprint = blueprints[0]
        return {
            "scenes": blueprints,
            "training_scripts": case_info.get("training_scripts") or [],
            "scene_world": {
                "scene_id": blueprint["scene_id"],
                "case_id": str(case_info.get("case_id") or "draft"),
                "name": blueprint.get("scene_name") or "训练场景",
                "environment": {"description": blueprint.get("scene_description") or blueprint.get("plot_arc") or ""},
                "role_ids": blueprint.get("role_ids") or [],
                "rules": [],
            },
            "scene_generation_mode": generation_mode,
            "ai_workflow": {"engine": "agent-workflow-v2-flowchart", "skills": ["case_import_harness", "scene_script_skill"]},
        }
    return {
        "scenes": [],
        "training_scripts": case_info.get("training_scripts") or [],
        "scene_world": {},
        "scene_generation_mode": "no-suitable-dialogue-scene",
        "scene_generation_issue": {
            "code": "NO_SUITABLE_DIALOGUE_SCENE",
            "message": "该案件未形成可通过多轮对话有效训练的场景，系统未使用通用模板补齐。",
        },
        "ai_workflow": {"engine": "agent-workflow-v2-flowchart", "skills": ["case_import_harness"]},
    }
