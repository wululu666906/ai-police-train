from __future__ import annotations

import json
import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

import models
from services.agent_workflow_client import AgentWorkflowUnavailable, agent_workflow_client
from services.role_resolver import resolve_scene_roles
from services.text_repair import repair_text
from services.training_runtime_service import dump_runtime_state, load_runtime_state
from services.training_view_service import serialize_scene_roles


SCORING_VERSION = "adaptive_v1"
CURRENT_EVALUATION_POLICY_VERSION = "adaptive_v1_llm_cap_audit_v2"


def _json(value: Any, default: Any):
    if isinstance(value, type(default)):
        return value
    try:
        parsed = json.loads(value or "")
        return parsed if isinstance(parsed, type(default)) else default
    except (TypeError, ValueError):
        return default


def _get_case_type(case: models.Case | None) -> str:
    return repair_text(case.case_type) if case and case.case_type else "其他"


def _get_stage_config(scene: models.Scene | None, stage_name: str, *, case_type: str = "") -> dict[str, Any]:
    stages = _json(getattr(scene, "stages", None), [])
    for stage in stages:
        if isinstance(stage, dict) and stage.get("stage_name") == stage_name:
            return stage
    return stages[0] if stages and isinstance(stages[0], dict) else {"stage_name": stage_name or "初始接触"}


def _get_stage_goal(scene: models.Scene | None, stage_name: str, *, case_type: str = "") -> str:
    return str(_get_stage_config(scene, stage_name, case_type=case_type).get("stage_goal") or "")


def _infer_truth_stage(cooperation: int, emotion: int) -> str:
    return "配合" if cooperation >= 60 else "抵触" if cooperation <= 30 else "犹豫"


def _role_state_label(cooperation: int, emotion: int, risk: int, clarity: int) -> str:
    if risk >= 80:
        return "crisis"
    if clarity <= 30:
        return "confused"
    if cooperation <= 30:
        return "resistant"
    if emotion >= 70:
        return "agitated"
    if cooperation >= 65 and clarity >= 60 and risk <= 60:
        return "engaged"
    return "guarded"


def _evaluate_stage_coverage(*args, **kwargs) -> dict[str, Any]:
    return {"requirements": [], "satisfied": [], "missing": [], "assessment_progress": None}


def _build_feedback(*args, **kwargs) -> dict[str, Any]:
    return {"level": "info", "tags": [], "message": "", "all_messages": []}


def _build_available_actions(stage_config: dict | None, completed_ids: list) -> list:
    actions = (stage_config or {}).get("available_actions") or (stage_config or {}).get("action_catalog") or []
    return [item for item in actions if item.get("id") not in set(completed_ids or [])]


def _scene_assessment_points(scene: models.Scene | None) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    seen: set[str] = set()
    for stage in _json(getattr(scene, "stages", None), []):
        if not isinstance(stage, dict):
            continue
        for point in stage.get("assessment_points") or []:
            if not isinstance(point, dict):
                continue
            key = str(point.get("id") or point.get("label") or point.get("content") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            points.append(point)
    return points


def _scene_knowledge_refs(scene: models.Scene | None) -> list[str]:
    refs = []
    for point in _scene_assessment_points(scene):
        refs.extend(str(item) for item in point.get("knowledge_refs") or [] if str(item).strip())
    return list(dict.fromkeys(refs))


def _context(db: Session, session_id: int, user_id: int):
    session = db.query(models.TrainingSession).filter(
        models.TrainingSession.id == session_id,
        models.TrainingSession.user_id == user_id,
    ).first()
    if not session:
        return None
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    roles = resolve_scene_roles(db, scene, case) if scene else []
    messages = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.id.asc()).all()
    return session, scene, case, roles, messages


def _idempotency_key(session, operation: str, value: str, sequence: int) -> str:
    identity = f"{session.id}|{getattr(session, 'created_at', '')}|{operation}|{sequence}|{value}"
    return f"training-{session.id}-{operation}-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:20]}"


def _build_payload(db: Session, session, scene, case, roles, messages, user_text: str, *, target_role_name: str | None = None) -> dict[str, Any]:
    structured = _json(getattr(case, "structured_data", None), {})
    facts = structured.get("facts") or structured.get("fact_cards") or []
    normalized_facts = []
    for index, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        normalized_facts.append({
            "fact_id": str(fact.get("fact_id") or fact.get("id") or f"F{index + 1:03d}"),
            "content": str(fact.get("content") or fact.get("fact") or ""),
            "source": str(fact.get("source") or ""),
            "known_by": list(fact.get("known_by") or []),
            "unknown_by": list(fact.get("unknown_by") or []),
            "secret": bool(fact.get("secret")),
            "disclosure_policy": fact.get("disclosure_policy") if isinstance(fact.get("disclosure_policy"), dict) else {},
        })
    valid_fact_ids = {item["fact_id"] for item in normalized_facts}
    runtime = load_runtime_state(session.revealed_info)
    links = db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).all()
    links_by_role = {link.role_id: link for link in links}
    structured_people = {
        repair_text(item.get("name") or ""): item
        for item in structured.get("persons") or []
        if isinstance(item, dict) and repair_text(item.get("name") or "")
    }

    def fact_id(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("fact_id") or value.get("id") or value.get("knowledge_id") or "")
        return str(value or "")

    personas = []
    case_people = []
    role_states = []
    role_participation = []
    role_id_by_db_id: dict[int, str] = {}
    for index, role in enumerate(roles):
        person_id = str(getattr(role, "person_id", None) or getattr(role, "id", f"role-{index + 1}"))
        role_id_by_db_id[role.id] = person_id
        role_name = repair_text(role.name or "")
        persona_meta = _json(getattr(role, "persona_meta", None), {})
        structured_person = structured_people.get(role_name, {})
        raw_role_memories = persona_meta.get("role_memories") if isinstance(persona_meta.get("role_memories"), list) else structured_person.get("role_memories") or []
        knowledge_ledger = persona_meta.get("knowledge_ledger") if isinstance(persona_meta.get("knowledge_ledger"), list) else structured_person.get("knowledge_ledger") or []

        role_memories = []
        for memory_index, raw_memory in enumerate(raw_role_memories if isinstance(raw_role_memories, list) else []):
            if not isinstance(raw_memory, dict):
                continue
            memory = dict(raw_memory)
            content = repair_text(memory.get("statement") or memory.get("content") or memory.get("quote") or "").strip()
            memory_fact_id = fact_id(memory)
            if content and memory_fact_id not in valid_fact_ids:
                memory_fact_id = memory_fact_id or (
                    "RM-" + hashlib.sha256(
                        f"{role.id}|{memory.get('memory_id') or memory_index}|{content}".encode("utf-8")
                    ).hexdigest()[:16]
                )
                normalized_facts.append({
                    "fact_id": memory_fact_id,
                    "content": content,
                    "source": "role_memory",
                    "known_by": [role_name],
                    "unknown_by": [],
                    "secret": False,
                    "disclosure_policy": {},
                })
                valid_fact_ids.add(memory_fact_id)
            if memory_fact_id:
                memory["fact_id"] = memory_fact_id
            role_memories.append(memory)
        known_candidates = [
            *_json(getattr(role, "knows_facts", None), []),
            *(structured_person.get("knows_facts") or structured_person.get("facts_known") or []),
            *knowledge_ledger,
        ]
        known_candidates.extend(item["fact_id"] for item in normalized_facts if role_name in item.get("known_by", []))
        raw_hidden_candidates = [
            *_json(getattr(role, "hidden_truths", None), []),
            *(structured_person.get("hidden_truths") or structured_person.get("facts_hidden") or []),
        ]
        hidden_candidates = []
        for hidden_index, hidden_item in enumerate(raw_hidden_candidates):
            hidden_id = fact_id(hidden_item)
            hidden_content = repair_text(
                hidden_item.get("content") or hidden_item.get("statement") or ""
                if isinstance(hidden_item, dict)
                else hidden_item
            ).strip()
            if hidden_content and hidden_id not in valid_fact_ids:
                hidden_id = hidden_id or (
                    "RH-" + hashlib.sha256(
                        f"{role.id}|{hidden_index}|{hidden_content}".encode("utf-8")
                    ).hexdigest()[:16]
                )
                normalized_facts.append({
                    "fact_id": hidden_id,
                    "content": hidden_content,
                    "source": "role_hidden_memory",
                    "known_by": [role_name],
                    "unknown_by": [],
                    "secret": False,
                    "disclosure_policy": {},
                })
                valid_fact_ids.add(hidden_id)
            if hidden_id:
                hidden_candidates.append(hidden_id)
        known = list(dict.fromkeys(item_id for item in known_candidates if (item_id := fact_id(item)) in valid_fact_ids))
        hidden = list(dict.fromkeys(item_id for item in hidden_candidates if (item_id := fact_id(item)) in valid_fact_ids))
        link = links_by_role.get(role.id)
        link_state = _json(getattr(link, "initial_state", None), {}) if link else {}
        initial_state = {
            "emotion": int(link_state.get("emotion", getattr(role, "init_emotion", None) or 50)),
            "cooperation": int(link_state.get("cooperation", getattr(role, "init_trust", None) or 35)),
            "risk": int(link_state.get("risk", getattr(role, "init_risk", None) or 50)),
            "clarity": int(link_state.get("clarity", getattr(role, "init_expression_clarity", None) or 50)),
        }
        state = runtime.get("role_state_snapshots", {}).get(str(role.id)) or initial_state
        relationships = [
            item for item in structured.get("relationships") or []
            if isinstance(item, dict) and role_name in json.dumps(item, ensure_ascii=False)
        ]
        response_constraints = structured_person.get("response_constraints") or persona_meta.get("response_constraints") or []
        if not isinstance(response_constraints, list):
            response_constraints = [response_constraints]
        is_primary = bool(link and link.is_primary) or (not any(bool(item.is_primary) for item in links) and index == 0)
        case_people.append({
            "person_id": person_id,
            "name": role_name,
            "role": role.role_type or "相关人员",
            "facts_known": known,
            "facts_hidden": hidden,
            "initial_state": initial_state,
        })
        role_states.append({"person_id": person_id, "name": role_name, "initial_state": state})
        participation_config = _json(getattr(link, "participation_config", None), {}) if link else {}
        role_participation.append({
            "person_id": person_id,
            "present": participation_config.get("present") is not False,
            "interaction_purpose": str(participation_config.get("interaction_purpose") or ""),
            "can_initiate": bool(participation_config.get("can_initiate", is_primary)),
            "can_interrupt": bool(participation_config.get("can_interrupt", False)),
            "relevant_fact_ids": [str(item) for item in participation_config.get("relevant_fact_ids") or []],
        })
        personas.append({
            "person_id": person_id,
            "platform_role_id": str(role.id),
            "name": role_name,
            "role": role.role_type or "相关人员",
            "traits": [repair_text(role.personality or "")],
            "speaking_style": repair_text(role.speaking_style or "自然口语"),
            "goals": [str(structured_person.get("current_goal") or persona_meta.get("current_goal") or "按本人立场自然回应")],
            "known_fact_ids": known,
            "hidden_fact_ids": hidden,
            "state": state,
            "state_label": str((runtime.get("role_state_labels") or {}).get(str(role.id)) or ""),
            "is_primary": is_primary,
            "role_memories": role_memories if isinstance(role_memories, list) else [],
            "knowledge_ledger": knowledge_ledger if isinstance(knowledge_ledger, list) else [],
            "relationships": relationships,
            "response_constraints": [str(item) for item in response_constraints if str(item).strip()],
        })

    stage_config = _get_stage_config(scene, session.current_stage or "", case_type=_get_case_type(case))
    scene_stages = _json(getattr(scene, "stages", None), [])
    scene_fact_ids = list(dict.fromkeys(
        str(fact_id)
        for stage_item in scene_stages if isinstance(stage_item, dict)
        for fact_id in stage_item.get("fact_ids") or []
        if str(fact_id)
    ))
    return {
        "learner_input": user_text,
        "target_role_name": str(target_role_name or ""),
        "case_world": {
            "case_id": str(case.id),
            "title": repair_text(case.title or ""),
            "summary": repair_text(case.background or ""),
            "case_type": _get_case_type(case),
            "persons": case_people,
            "facts": normalized_facts,
            "timeline": list(structured.get("timeline") or []),
            "locations": [str(item) for item in structured.get("locations") or []],
            "relationships": list(structured.get("relationships") or []),
        },
        "scene_world": {
            "scene_id": str(scene.id),
            "case_id": str(case.id),
            "name": repair_text(scene.name or "训练场景"),
            "environment": {"description": repair_text(scene.description or "")},
            "role_ids": [item["person_id"] for item in personas],
            "rules": ["不得突破知识边界", "不得创造影响案情的新事实"],
            "current_stage": session.current_stage or "",
            "stages": scene_stages,
            "role_states": role_states,
            "role_participation": role_participation,
            "fact_ids": scene_fact_ids,
        },
        "personas": personas,
        "current_stage": session.current_stage or "",
        "stage": stage_config,
        "completed_point_ids": runtime.get("completed_point_ids") or [],
        "completed_action_ids": runtime.get("completed_action_ids") or [],
        "state_thresholds": stage_config.get("state_thresholds") or {},
        "revealed_fact_ids": list(runtime.get("revealed_info") or []),
        "public_history": [
            {
                "role": item.role,
                "content": repair_text(item.content or ""),
                "speaker_name": item.speaker_name,
                "person_id": role_id_by_db_id.get(item.speaker_role_id) if item.speaker_role_id else "",
            }
            for item in messages
        ],
    }


def _persist_workflow_result(session, roles, result: dict[str, Any]) -> dict[str, int]:
    required = ("emotion", "cooperation", "risk", "clarity")
    roles_by_person = {str(getattr(role, "person_id", None) or role.id): role for role in roles}
    roles_by_db_id = {str(role.id): role for role in roles}
    runtime = load_runtime_state(session.revealed_info)
    runtime["state_contract"] = "four_dimensional_v1"
    primary_state: dict[str, int] | None = None
    primary_person_id = str((result.get("speaker") or {}).get("person_id") or "")
    for item in result.get("role_state_results") or []:
        if not isinstance(item, dict):
            continue
        role = roles_by_person.get(str(item.get("person_id") or "")) or roles_by_db_id.get(str(item.get("platform_role_id") or ""))
        state = item.get("state") if isinstance(item.get("state"), dict) else {}
        if not role or any(key not in state for key in required):
            raise RuntimeError("Agent 返回的多角色四维状态契约不完整")
        normalized = {key: max(0, min(100, round(float(state[key])))) for key in required}
        role_key = str(role.id)
        runtime.setdefault("role_state_snapshots", {})[role_key] = normalized
        runtime.setdefault("role_state_deltas", {})[role_key] = dict(item.get("state_delta") or {})
        label = str(item.get("role_state_label") or "guarded")
        runtime.setdefault("role_state_labels", {})[role_key] = label
        if str(item.get("person_id") or "") == primary_person_id or primary_state is None:
            primary_state = normalized
            runtime["role_state_label"] = label
    if primary_state is None:
        primary_state = dict(runtime.get("state_snapshot") or {"emotion": 50, "cooperation": 30, "risk": 50, "clarity": 50})
    runtime["state_snapshot"] = primary_state
    runtime["last_active_role_ids"] = [
        str(item.get("platform_role_id") or item.get("person_id") or "")
        for item in result.get("active_speakers") or []
        if isinstance(item, dict)
    ]
    runtime["last_target_role_name"] = str((result.get("speaker") or {}).get("name") or "")
    runtime["revealed_info"] = list(dict.fromkeys([*(runtime.get("revealed_info") or []), *(result.get("revealed_fact_ids") or [])]))
    runtime["assessment_progress"] = result.get("assessment_progress") or runtime.get("assessment_progress")
    runtime["assessment_results"] = result.get("assessment_results") or runtime.get("assessment_results") or []
    runtime["completed_point_ids"] = list(result.get("completed_point_ids") or runtime.get("completed_point_ids") or [])
    runtime["completed_action_ids"] = list(result.get("completed_action_ids") or runtime.get("completed_action_ids") or [])
    runtime["auto_finish_ready"] = bool(result.get("training_finished", False))
    runtime["stage_advance_allowed"] = bool(result.get("stage_advance_allowed", False))
    runtime["action_effective"] = bool(result.get("action_effective", False))
    runtime["recommended_question_items"] = list(result.get("recommended_question_items") or [])
    session.revealed_info = dump_runtime_state(runtime)
    session.current_emotion = primary_state["emotion"]
    session.current_trust = primary_state["cooperation"]
    if result.get("stage_advanced") and result.get("current_stage"):
        session.current_stage = str(result["current_stage"])
    return primary_state


def generate_dialogue(db: Session, session_id: int, user_text: str, user_id: int, *, target_role_name: str | None = None) -> dict[str, Any]:
    context = _context(db, session_id, user_id)
    if not context:
        return {"inner_thought": "ACCESS_DENIED", "response": "", "communication_feedback": {"message": "无权访问"}}
    session, scene, case, roles, messages = context
    if not scene or not case or not roles:
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": "训练上下文不完整"}}
    try:
        response = agent_workflow_client.execute(
            workflow_id=f"training-{session.id}",
            stage="TRAINING",
            skill="role_simulation",
            case_id=str(case.id),
            training_id=str(session.id),
            payload=_build_payload(db, session, scene, case, roles, messages, user_text, target_role_name=target_role_name),
            idempotency_key=_idempotency_key(session, "turn", user_text, len(messages) + 1),
        )
    except AgentWorkflowUnavailable as exc:
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": str(exc)}}
    result = response.get("result") or {}
    reply = str(result.get("reply") or "").strip()
    state = _persist_workflow_result(session, roles, result)
    roles_by_person = {str(getattr(role, "person_id", None) or role.id): role for role in roles}
    roles_by_db_id = {str(role.id): role for role in roles}
    reply_turns = []
    db.add(models.Message(session_id=session.id, role="user", content=user_text))
    for turn in result.get("reply_turns") or []:
        if not isinstance(turn, dict):
            continue
        content = str(turn.get("content") or "").strip()
        role = roles_by_person.get(str(turn.get("person_id") or "")) or roles_by_db_id.get(str(turn.get("speaker_role_id") or ""))
        if not content or role is None:
            continue
        speaker_name = repair_text(role.name or "")
        db.add(models.Message(session_id=session.id, role="assistant", content=content, speaker_role_id=role.id, speaker_name=speaker_name))
        reply_turns.append({"person_id": str(getattr(role, "person_id", None) or role.id), "speaker_name": speaker_name, "speaker_role_id": role.id, "content": content})
    db.commit()
    latest_runtime = load_runtime_state(session.revealed_info)
    return {
        "response": reply,
        "reply_turns": reply_turns,
        "active_speakers": result.get("active_speakers") or [],
        "role_state_results": result.get("role_state_results") or [],
        "simulation_meta": result.get("simulation_meta") or {},
        "role_intents": result.get("role_intents") or [],
        "routing_summary": result.get("routing_summary") or "",
        "addressing_warning": result.get("addressing_warning") or "",
        "scene_roles": serialize_scene_roles(db, scene, case, runtime_state=latest_runtime),
        "updated_emotion": state["emotion"],
        "updated_trust": state["cooperation"],
        "updated_cooperation": state["cooperation"],
        "updated_risk": state["risk"],
        "updated_clarity": state["clarity"],
        "new_fact_revealed": (result.get("revealed_fact_ids") or [None])[0],
        "is_stage_completed": bool(result.get("stage_advance_allowed")),
        "current_stage": result.get("current_stage") or session.current_stage,
        "assessment_progress": result.get("assessment_progress"),
        "completed_point_ids": result.get("completed_point_ids") or [],
        "completed_action_ids": result.get("completed_action_ids") or [],
        "auto_finish_ready": bool(result.get("training_finished")),
        "role_state_label": result.get("role_state_label"),
        "current_stage_goal": _get_stage_goal(scene, session.current_stage or "", case_type=_get_case_type(case)),
        "stage_completion_requirements": result.get("stage_completion_requirements") or [],
        "stage_completion_satisfied": result.get("stage_completion_satisfied") or [],
        "stage_completion_missing": result.get("stage_completion_missing") or [],
        "recommended_questions": result.get("recommended_questions") or [],
        "recommended_question_items": result.get("recommended_question_items") or [],
        "communication_feedback": result.get("communication_feedback") or {},
    }


def apply_training_action(db: Session, session_id: int, action_id: str, note: str, user_id: int) -> dict[str, Any]:
    context = _context(db, session_id, user_id)
    if not context:
        return {"inner_thought": "ACCESS_DENIED", "response": ""}
    session, scene, case, roles, messages = context
    if not scene or not case or not roles:
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": "训练上下文不完整"}}
    action_text = f"[{action_id}] {note.strip()}".strip()
    payload = _build_payload(db, session, scene, case, roles, messages, action_text)
    payload.update({"input_kind": "action", "action_id": action_id})
    try:
        response = agent_workflow_client.execute(
            workflow_id=f"training-{session.id}", stage="TRAINING", skill="role_simulation",
            case_id=str(case.id), training_id=str(session.id), payload=payload,
            idempotency_key=_idempotency_key(session, "action", action_text, len(messages) + 1),
        )
    except AgentWorkflowUnavailable as exc:
        return {"inner_thought": "ERROR", "response": "", "communication_feedback": {"message": str(exc)}}
    result = response.get("result") or {}
    state = _persist_workflow_result(session, roles, result)
    db.add(models.Message(session_id=session.id, role="action", content=action_text))
    roles_by_person = {str(getattr(role, "person_id", None) or role.id): role for role in roles}
    for turn in result.get("reply_turns") or []:
        if not isinstance(turn, dict):
            continue
        role = roles_by_person.get(str(turn.get("person_id") or ""))
        content = str(turn.get("content") or "").strip()
        if role and content:
            db.add(models.Message(session_id=session.id, role="assistant", content=content, speaker_role_id=role.id, speaker_name=repair_text(role.name or "")))
    db.commit()
    return {"response": f"已执行: {action_id}", "inner_thought": "ACTION_OK", "recognized_actions": [action_id],
            "reply_turns": result.get("reply_turns") or [], "active_speakers": result.get("active_speakers") or [],
            "role_state_results": result.get("role_state_results") or [], "simulation_meta": result.get("simulation_meta") or {},
            "action_effective": bool(result.get("action_effective")), "assessment_progress": result.get("assessment_progress"),
            "completed_point_ids": result.get("completed_point_ids") or [], "completed_action_ids": result.get("completed_action_ids") or [],
            "updated_emotion": state["emotion"], "updated_cooperation": state["cooperation"], "updated_trust": state["cooperation"],
            "updated_risk": state["risk"], "updated_clarity": state["clarity"], "role_state_label": result.get("role_state_label")}


def is_current_evaluation_report(report: Any) -> bool:
    if not isinstance(report, dict) or not isinstance(report.get("evaluation_meta"), dict):
        return False
    meta = report["evaluation_meta"]
    audit = meta.get("cap_audit")
    try:
        score = round(float(report.get("total_score")))
        cap = int(audit.get("applied_cap"))
        after = int(audit.get("after_cap_score"))
    except (AttributeError, TypeError, ValueError):
        return False
    return meta.get("scoring_version") == SCORING_VERSION and meta.get("policy_version") == CURRENT_EVALUATION_POLICY_VERSION and audit.get("valid") is True and 0 <= score <= cap <= 100 and after == score


def evaluate_session(db: Session, session_id: int, user_id: int | None = None, force_recompute: bool = False):
    query = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id)
    if user_id is not None:
        query = query.filter(models.TrainingSession.user_id == user_id)
    session = query.first()
    if not session:
        return None
    if session.evaluation_result and not force_recompute:
        existing = _json(session.evaluation_result, {})
        if is_current_evaluation_report(existing):
            return existing
    messages = db.query(models.Message).filter(models.Message.session_id == session.id).order_by(models.Message.id.asc()).all()
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    runtime = load_runtime_state(session.revealed_info)
    try:
        response = agent_workflow_client.execute(
            workflow_id=f"evaluation-{session.id}",
            stage="COMPLETED",
            skill="evaluation",
            training_id=str(session.id),
            case_id=str(scene.case_id) if scene else None,
            payload={
                "transcript": [{"role": item.role, "content": repair_text(item.content or "")} for item in messages],
                "assessment_points": _scene_assessment_points(scene),
                "action_results": [{"action_id": item, "status": "completed", "evidence": [f"动作:{item}"]} for item in runtime.get("completed_action_ids") or []],
                "scene_type": "接警" if scene and "接警" in (scene.name or "") else "现场" if scene and any(token in (scene.name or "") for token in ("现场", "勘查", "调查")) else "通用",
                "knowledge_refs": list(dict.fromkeys([*(runtime.get("knowledge_refs") or []), *_scene_knowledge_refs(scene)])),
                "report_header": {
                    "session_id": session.id,
                    "case_title": repair_text(case.title or "") if case else "未知案件",
                    "case_type": repair_text(case.case_type or "") if case else "其他",
                    "scene_name": repair_text(scene.name or "") if scene else "训练场景",
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "training_started_at": session.training_started_at.isoformat() if session.training_started_at else None,
                    "training_finished_at": session.training_finished_at.isoformat() if session.training_finished_at else None,
                    "dialogue_turns": sum(item.role == "user" for item in messages),
                },
                "rule_checks": {"closure_summary": runtime.get("closure_summary") or {}, "findings": []},
            },
            idempotency_key=_idempotency_key(session, "evaluation", str(int(force_recompute)), len(messages)),
        )
    except AgentWorkflowUnavailable as exc:
        raise RuntimeError(str(exc)) from exc
    evaluation = response.get("result") or {}
    report_response = agent_workflow_client.execute(
        workflow_id=f"report-{session.id}",
        stage="EVALUATED",
        skill="report",
        training_id=str(session.id),
        case_id=str(scene.case_id) if scene else None,
        payload={"evaluation": evaluation},
        idempotency_key=_idempotency_key(session, "report", str(int(force_recompute)), len(messages)),
    )
    generated = report_response.get("result", {}).get("report") or {}
    report = {"engine": "agent-workflow-v2-flowchart", **generated}
    if not is_current_evaluation_report(report):
        raise RuntimeError("Agent 返回的评估报告版本或封顶审计无效")
    session.evaluation_result = json.dumps(report, ensure_ascii=False)
    db.commit()
    return report
