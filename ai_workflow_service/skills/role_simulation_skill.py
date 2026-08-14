from __future__ import annotations

import json
import hashlib
from typing import Any

from ai_workflow_service.contracts import CaseWorld, Persona, SceneWorld, SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.domain.four_dimensional_state import infer_rule_delta, transition
from ai_workflow_service.domain.training_runtime import evaluate_training
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.simulation.police_training_world import PoliceTrainingWorld
from ai_workflow_service.simulation.role_validator import PoliceRoleValidator
from ai_workflow_service.simulation.tinytroupe_adapter import TinyTroupeAdapter
from ai_workflow_service.skills.base import Skill


STATE_KEYS = ("emotion", "cooperation", "risk", "clarity")


class RoleSimulationSkill(Skill):
    name = SkillName.role_simulation
    next_stage = WorkflowStage.training

    def __init__(self, llm: DeepSeekAdapter, simulation: TinyTroupeAdapter):
        self.llm = llm
        self.simulation = simulation
        self.validator = PoliceRoleValidator()

    @staticmethod
    def _bounded_model_delta(value: Any) -> dict[str, int]:
        raw = value if isinstance(value, dict) else {}
        delta: dict[str, int] = {}
        for key in STATE_KEYS:
            try:
                numeric = int(raw.get(key, 0) or 0)
            except (TypeError, ValueError):
                numeric = 0
            delta[key] = max(-4, min(4, numeric))
        return delta

    def _audit_turns(
        self,
        *,
        learner_input: str,
        turns: list[dict[str, Any]],
        personas: dict[str, Persona],
        fact_access: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        audit_payload = {
            "learner_input": learner_input,
            "roles": [
                {
                    "person_id": turn["person_id"],
                    "speaker_name": turn["speaker_name"],
                    "reply": turn["content"],
                    "cognitive_state": turn.get("cognitive_state") or {},
                    "allowed_facts": fact_access.get(turn["person_id"], []),
                }
                for turn in turns
            ],
        }
        raw = self.llm.complete_json(
            system=(
                "你是警情角色回复审计器，不得改写或补写任何台词。逐角色判断回复是否只使用 allowed_facts，"
                "是否捏造事实、泄露系统身份或替他人陈述。输出JSON：roles数组；每项必须包含person_id、"
                "valid、violations、revealed_fact_ids、state_delta。state_delta只表示该角色本轮情绪、配合度、"
                "风险、清晰度的轻量建议，每轴只能为-4到4。"
            ),
            user=json.dumps(audit_payload, ensure_ascii=False),
            temperature=0.0,
            max_tokens=1800,
            max_attempts=1,
        )
        rows = raw.get("roles") if isinstance(raw.get("roles"), list) else []
        rows_by_id = {
            str(row.get("person_id") or ""): row
            for row in rows
            if isinstance(row, dict) and str(row.get("person_id") or "")
        }
        invalid: list[str] = []
        normalized: dict[str, dict[str, Any]] = {}
        for turn in turns:
            person_id = str(turn["person_id"])
            persona = personas[person_id]
            row = rows_by_id.get(person_id)
            allowed_ids = {str(item.get("fact_id") or "") for item in fact_access.get(person_id, [])}
            if row is None:
                row = {"valid": False, "violations": ["missing_audit_result"], "revealed_fact_ids": [], "state_delta": {}}
            revealed = [str(item) for item in row.get("revealed_fact_ids") or []]
            issues = [str(item) for item in row.get("violations") or [] if str(item).strip()]
            if row.get("valid") is not True and not issues:
                issues.append("semantic_boundary_violation")
            validation = self.validator.validate(
                persona=persona,
                reply=str(turn.get("content") or ""),
                revealed_fact_ids=revealed,
                allowed_fact_ids=allowed_ids,
                audit_issues=issues,
            )
            if not validation.valid:
                invalid.append(person_id)
            normalized[person_id] = {
                "valid": validation.valid,
                "issues": validation.issues,
                "revealed_fact_ids": [item for item in revealed if item in allowed_ids],
                "discarded_revealed_fact_ids": [item for item in revealed if item not in allowed_ids],
                "state_delta": self._bounded_model_delta(row.get("state_delta")),
            }
        return {"invalid_person_ids": invalid, "roles": normalized, "model_calls": 1}

    def execute(self, request: WorkflowRequest) -> dict:
        learner_input = str(request.payload.get("learner_input") or "").strip()
        if not learner_input:
            raise WorkflowServiceError("INVALID_LEARNER_INPUT", "学员输入不能为空")
        case_world = CaseWorld.model_validate(request.payload.get("case_world") or {})
        scene = SceneWorld.model_validate(request.payload.get("scene_world") or {})
        raw_personas = request.payload.get("personas")
        if not isinstance(raw_personas, list) or not raw_personas:
            raw_personas = [request.payload.get("persona") or {}]
        personas = [Persona.model_validate(item) for item in raw_personas]
        personas_by_id = {item.person_id: item for item in personas}
        if len(personas_by_id) != len(personas):
            raise WorkflowServiceError("INVALID_PERSONAS", "场景人物 person_id 必须唯一")

        policy_world = PoliceTrainingWorld(scene.scene_id, current_stage=scene.current_stage, rules=scene.rules)
        revealed_before = {str(item) for item in request.payload.get("revealed_fact_ids") or []}
        fact_access: dict[str, list[dict[str, Any]]] = {}
        for persona in personas:
            allowed = policy_world.allowed_fact_ids(
                persona,
                case_world.facts,
                learner_input,
                revealed_fact_ids=revealed_before,
            )
            fact_access[persona.person_id] = [
                fact.model_dump(mode="json")
                for fact in case_world.facts
                if fact.fact_id in allowed
            ]

        audit_calls = 0

        def audit(turns: list[dict[str, Any]]) -> dict[str, Any]:
            nonlocal audit_calls
            audit_calls += 1
            return self._audit_turns(
                learner_input=learner_input,
                turns=turns,
                personas=personas_by_id,
                fact_access=fact_access,
            )

        simulation_turn = self.simulation.simulate_turn(
            workflow_id=request.workflow_id,
            idempotency_key=str(request.payload.get("_idempotency_key") or request.workflow_id),
            scene=scene,
            personas=personas,
            learner_input=learner_input,
            input_kind=str(request.payload.get("input_kind") or "dialogue"),
            target_role_name=str(request.payload.get("target_role_name") or ""),
            history=list(request.payload.get("public_history") or request.payload.get("recent_dialogue") or []),
            fact_access=fact_access,
            world_revision=hashlib.sha256(
                json.dumps(
                    [fact.model_dump(mode="json") for fact in case_world.facts],
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ).encode("utf-8")
            ).hexdigest(),
            validator=audit,
        )
        audit_rows = simulation_turn.audit.get("roles") if isinstance(simulation_turn.audit.get("roles"), dict) else {}
        active_ids = {item["person_id"] for item in simulation_turn.active_speakers}
        input_kind = str(request.payload.get("input_kind") or "dialogue")
        affected = personas if input_kind == "action" else [item for item in personas if item.person_id in active_ids]
        role_state_results: list[dict[str, Any]] = []
        any_crisis = False
        for persona in affected:
            rule_delta = infer_rule_delta(learner_input, input_kind=input_kind)
            model_delta = self._bounded_model_delta((audit_rows.get(persona.person_id) or {}).get("state_delta"))
            proposed = {key: rule_delta[key] + model_delta[key] for key in STATE_KEYS}
            state_transition = transition(
                persona.state.model_dump(mode="json"),
                proposed,
                previous_label=persona.state_label,
                thresholds=request.payload.get("state_thresholds"),
            )
            any_crisis = any_crisis or state_transition.crisis_blocked
            role_state_results.append({
                "person_id": persona.person_id,
                "platform_role_id": persona.platform_role_id,
                "name": persona.name,
                "state": state_transition.state,
                "state_delta": state_transition.delta,
                "role_state_label": state_transition.label,
            })

        reply_turns: list[dict[str, Any]] = []
        revealed_all: list[str] = []
        for turn in simulation_turn.reply_turns:
            audit_row = audit_rows.get(turn["person_id"]) or {}
            revealed = list(audit_row.get("revealed_fact_ids") or [])
            revealed_all.extend(revealed)
            reply_turns.append({
                "person_id": turn["person_id"],
                "speaker_role_id": turn.get("platform_role_id") or None,
                "speaker_name": turn["speaker_name"],
                "content": turn["content"],
                "revealed_fact_ids": revealed,
            })
        if not reply_turns:
            raise WorkflowServiceError("ROLE_VALIDATION_FAILED", "TinyTroupe 未产生有效 TALK", retryable=True)

        target_name = str(request.payload.get("target_role_name") or "")
        primary_turn = next((item for item in reply_turns if item["speaker_name"] == target_name), reply_turns[0])
        primary_state = next(
            (item for item in role_state_results if item["person_id"] == primary_turn["person_id"]),
            role_state_results[0] if role_state_results else None,
        )
        if primary_state is None:
            raise WorkflowServiceError("STATE_TRANSITION_FAILED", "本轮没有可持久化的角色状态")

        training = evaluate_training(request.payload, learner_input)
        if any_crisis:
            training["stage_advance_allowed"] = False
            training["training_finished"] = False
        simulation_meta = dict(simulation_turn.simulation_meta)
        simulation_meta["audit_model_calls"] = audit_calls or int(simulation_meta.get("audit_model_calls") or simulation_turn.audit.get("model_calls") or 0)
        simulation_meta["model_calls"] = int(simulation_meta.get("model_calls") or 0) + simulation_meta["audit_model_calls"]
        return {
            "reply": primary_turn["content"],
            "speaker": {"person_id": primary_turn["person_id"], "name": primary_turn["speaker_name"]},
            "reply_turns": reply_turns,
            "active_speakers": simulation_turn.active_speakers,
            "role_state_results": role_state_results,
            "revealed_fact_ids": list(dict.fromkeys(revealed_all)),
            "state": primary_state["state"],
            "state_delta": primary_state["state_delta"],
            "role_state_label": primary_state["role_state_label"],
            "simulation_meta": simulation_meta,
            **training,
        }
