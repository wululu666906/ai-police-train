from __future__ import annotations

import json
import hashlib
from typing import Any

from ai_workflow_service.contracts import CaseWorld, Persona, RoleParticipation, SceneWorld, SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.domain.four_dimensional_state import infer_rule_delta, transition
from ai_workflow_service.domain.training_runtime import evaluate_training
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.simulation.police_training_world import PoliceTrainingWorld
from ai_workflow_service.simulation.role_validator import PoliceRoleValidator
from ai_workflow_service.simulation.text_normalize import decode_literal_unicode_escapes
from ai_workflow_service.simulation.tinytroupe_adapter import TinyTroupeAdapter
from ai_workflow_service.skills.base import Skill
from ai_workflow_service.skills.role_intent_skill import RoleIntentSkill
from ai_workflow_service.skills.recommended_questions_skill import RecommendedQuestionsSkill


STATE_KEYS = ("emotion", "cooperation", "risk", "clarity")


class RoleSimulationSkill(Skill):
    name = SkillName.role_simulation
    next_stage = WorkflowStage.training

    def __init__(self, llm: DeepSeekAdapter, simulation: TinyTroupeAdapter):
        self.llm = llm
        self.simulation = simulation
        self.validator = PoliceRoleValidator()
        self.role_intent = RoleIntentSkill(llm)
        self.recommended_questions = RecommendedQuestionsSkill(llm)

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

        configured_participation = {item.person_id: item for item in scene.role_participation}
        participation = {}
        for persona in personas:
            configured = configured_participation.get(persona.person_id) or RoleParticipation(
                person_id=persona.person_id,
                present=True,
                interaction_purpose="承担本场景中与其身份和已知事实相关的互动",
                can_initiate=persona.is_primary,
                can_interrupt=False,
            )
            # 场景绑定角色一律可交互，避免历史 present=false 脏数据阻断训练。
            participation[persona.person_id] = configured.model_copy(update={"present": True})
        present_personas = list(personas)
        if not present_personas:
            raise WorkflowServiceError("NO_PRESENT_PERSONAS", "当前场景没有在场且可参与交互的角色")

        policy_world = PoliceTrainingWorld(scene.scene_id, current_stage=scene.current_stage, rules=scene.rules)
        revealed_before = {str(item) for item in request.payload.get("revealed_fact_ids") or []}
        fact_access: dict[str, list[dict[str, Any]]] = {}
        scene_fact_ids = set(scene.fact_ids) or {fact.fact_id for fact in case_world.facts}
        for persona in personas:
            allowed = policy_world.allowed_fact_ids(
                persona,
                case_world.facts,
                learner_input,
                revealed_fact_ids=revealed_before,
            )
            role_scope = set(participation[persona.person_id].relevant_fact_ids)
            allowed &= scene_fact_ids | revealed_before
            if role_scope:
                allowed &= role_scope | revealed_before
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

        public_history = list(request.payload.get("public_history") or request.payload.get("recent_dialogue") or [])
        input_kind = str(request.payload.get("input_kind") or "dialogue")
        target_role_name = str(request.payload.get("target_role_name") or "")
        intent_result = self.role_intent.execute(
            personas=present_personas,
            learner_input=learner_input,
            input_kind=input_kind,
            target_role_name=target_role_name,
            public_history=public_history,
            fact_access=fact_access,
            participation=participation,
            max_actors=self.simulation.settings.tinytroupe_max_actors,
        )
        simulation_turn = self.simulation.simulate_turn(
            workflow_id=request.workflow_id,
            idempotency_key=str(request.payload.get("_idempotency_key") or request.workflow_id),
            scene=scene,
            personas=present_personas,
            learner_input=learner_input,
            input_kind=input_kind,
            target_role_name=target_role_name,
            history=public_history,
            fact_access=fact_access,
            case_facts=case_world.facts,
            actor_ids=intent_result["actor_ids"],
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
        spoken_ids = {str(item.get("person_id") or "") for item in simulation_turn.reply_turns if str(item.get("content") or "").strip()}
        addressed_ids = {
            str(item.get("person_id") or "")
            for item in intent_result.get("decisions") or []
            if item.get("addressed")
        }
        role_intents = [
            {
                "person_id": persona.person_id,
                "intent": "answer" if persona.person_id in spoken_ids else "silent",
                "confidence": 1.0,
                "reason": "TinyTroupe 本轮实际发言" if persona.person_id in spoken_ids else "TinyTroupe 本轮选择沉默",
                "addressed": persona.person_id in addressed_ids,
                "fallback": False,
            }
            for persona in present_personas
        ]
        active_ids = {item["person_id"] for item in simulation_turn.active_speakers}
        affected = present_personas if input_kind == "action" else [item for item in present_personas if item.person_id in active_ids]
        role_state_results: list[dict[str, Any]] = []
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
            content = decode_literal_unicode_escapes(str(turn.get("content") or "").strip())
            if not content:
                continue
            audit_row = audit_rows.get(turn["person_id"]) or {}
            revealed = list(audit_row.get("revealed_fact_ids") or [])
            revealed_all.extend(revealed)
            reply_turns.append({
                "person_id": turn["person_id"],
                "speaker_role_id": turn.get("platform_role_id") or None,
                "speaker_name": turn["speaker_name"],
                "content": content,
                "revealed_fact_ids": revealed,
            })
        primary_turn = next(
            (item for item in reply_turns if item["speaker_name"] == target_role_name),
            reply_turns[0] if reply_turns else None,
        )
        primary_state = next(
            (item for item in role_state_results if primary_turn and item["person_id"] == primary_turn["person_id"]),
            role_state_results[0] if role_state_results else None,
        )

        training = evaluate_training(request.payload, learner_input)
        recommendation_payload = {
            **request.payload,
            "revealed_fact_ids": list(dict.fromkeys([
                *(request.payload.get("revealed_fact_ids") or []),
                *revealed_all,
            ])),
            "public_history": [
                *public_history,
                {"role": input_kind, "content": learner_input},
                *[
                    {"role": "assistant", "person_id": item["person_id"], "speaker_name": item["speaker_name"], "content": item["content"]}
                    for item in reply_turns
                ],
            ],
        }
        # 阶段已推进：建议提问必须按新阶段剧本节奏生成。
        next_stage_name = str(training.get("current_stage") or "").strip()
        if training.get("stage_advanced") and next_stage_name:
            scene_world = recommendation_payload.get("scene_world") if isinstance(recommendation_payload.get("scene_world"), dict) else {}
            stages = [item for item in (scene_world.get("stages") or []) if isinstance(item, dict)]
            script_stages = [
                item for item in (recommendation_payload.get("training_script_stages") or [])
                if isinstance(item, dict)
            ]
            next_stage = next(
                (item for item in (*script_stages, *stages) if str(item.get("stage_name") or "").strip() == next_stage_name),
                None,
            )
            if isinstance(next_stage, dict):
                recommendation_payload["current_stage"] = next_stage_name
                recommendation_payload["stage"] = next_stage
                recommendation_payload["current_stage_script"] = next_stage
                scene_world = dict(scene_world)
                scene_world["current_stage"] = next_stage_name
                recommendation_payload["scene_world"] = scene_world
        recommendation_items = self.recommended_questions.execute(
            payload=recommendation_payload,
            training_result=training,
            role_intents=role_intents,
        )
        training["recommended_question_items"] = recommendation_items
        training["recommended_questions"] = [item["text"] for item in recommendation_items]
        simulation_meta = dict(simulation_turn.simulation_meta)
        simulation_meta["audit_model_calls"] = audit_calls or int(simulation_meta.get("audit_model_calls") or simulation_turn.audit.get("model_calls") or 0)
        simulation_meta["model_calls"] = int(simulation_meta.get("model_calls") or 0) + simulation_meta["audit_model_calls"]
        return {
            "reply": primary_turn["content"] if primary_turn else "",
            "speaker": {"person_id": primary_turn["person_id"], "name": primary_turn["speaker_name"]} if primary_turn else {},
            "reply_turns": reply_turns,
            "active_speakers": simulation_turn.active_speakers,
            "role_state_results": role_state_results,
            "revealed_fact_ids": list(dict.fromkeys(revealed_all)),
            "state": primary_state["state"] if primary_state else {},
            "state_delta": primary_state["state_delta"] if primary_state else {},
            "role_state_label": primary_state["role_state_label"] if primary_state else "",
            "role_intents": role_intents,
            "routing_summary": intent_result["routing_summary"],
            "addressing_warning": "当前没有角色认为自己适合发言，请明确询问对象或调整问题。" if not reply_turns and input_kind != "action" else "",
            "simulation_meta": simulation_meta,
            **training,
        }
