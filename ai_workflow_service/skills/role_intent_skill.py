from __future__ import annotations

import json
from typing import Any

from ai_workflow_service.contracts import Persona, RoleParticipation
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter


SPEAKING_INTENTS = {"answer", "react", "interrupt"}


class RoleIntentSkill:
    """Route one public turn to exactly one TinyTroupe role."""

    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    @staticmethod
    def _decision(
        persona: Persona,
        *,
        selected: bool,
        intent: str = "silent",
        confidence: float = 1.0,
        reason: str,
        addressed: bool = False,
        fallback: bool = False,
    ) -> dict[str, Any]:
        return {
            "person_id": persona.person_id,
            "intent": intent if selected else "silent",
            "confidence": confidence,
            "reason": reason,
            "addressed": addressed,
            "fallback": fallback,
        }

    @staticmethod
    def _explicit_target(
        personas: list[Persona], learner_input: str, target_role_name: str
    ) -> Persona | None:
        target = target_role_name.strip()
        if target:
            exact = next((persona for persona in personas if persona.name == target), None)
            if exact:
                return exact
        named = [persona for persona in personas if persona.name and persona.name in learner_input]
        return max(named, key=lambda persona: len(persona.name), default=None)

    @staticmethod
    def _fallback_persona(personas: list[Persona], participation: dict[str, RoleParticipation]) -> Persona:
        return next(
            (persona for persona in personas if persona.is_primary and participation[persona.person_id].can_initiate),
            next((persona for persona in personas if persona.is_primary), personas[0]),
        )

    def execute(
        self,
        *,
        personas: list[Persona],
        learner_input: str,
        input_kind: str,
        target_role_name: str,
        public_history: list[dict[str, Any]],
        fact_access: dict[str, list[dict[str, Any]]],
        participation: dict[str, RoleParticipation],
        max_actors: int,
    ) -> dict[str, Any]:
        del max_actors  # Ordinary training turns intentionally activate one TinyPerson.
        candidates = [persona for persona in personas if participation[persona.person_id].present]
        if not candidates:
            return {"decisions": [], "actor_ids": [], "routing_summary": "当前没有可参与对话的角色"}

        explicit = self._explicit_target(candidates, learner_input, target_role_name)
        if explicit:
            decisions = [
                self._decision(
                    persona,
                    selected=persona.person_id == explicit.person_id,
                    intent="answer",
                    confidence=1.0,
                    reason="学员明确点名该角色" if persona.person_id == explicit.person_id else "本轮问题已明确指向其他角色",
                    addressed=persona.person_id == explicit.person_id,
                )
                for persona in candidates
            ]
            return {
                "decisions": decisions,
                "actor_ids": [explicit.person_id],
                "routing_summary": f"已点名 {explicit.name}，本轮仅由该角色回应",
            }

        role_options = []
        for persona in candidates:
            policy = participation[persona.person_id]
            role_options.append({
                "person_id": persona.person_id,
                "name": persona.name,
                "identity": persona.role,
                "is_primary": persona.is_primary,
                "interaction_purpose": policy.interaction_purpose,
                "can_initiate": policy.can_initiate,
                "can_interrupt": policy.can_interrupt,
                "goals": persona.goals,
                "relationships": persona.relationships,
                "answerable_facts": fact_access.get(persona.person_id, []),
            })
        payload = {
            "learner_input": learner_input,
            "input_kind": input_kind,
            "roles": role_options,
            "recent_public_history": public_history[-12:],
        }
        selected: Persona | None = None
        intent = "answer" if input_kind == "dialogue" else "react"
        confidence = 0.0
        reason = ""
        fallback = False
        try:
            raw = self.llm.complete_json(
                system=(
                    "你是TinyTroupe警情世界的轮次路由器，不生成台词。必须从roles中选择且只选择一个"
                    "最适合回应当前学员输入的角色，避免所有角色同时发言。结合角色身份、可回答事实、"
                    "互动目的、最近公共对话和正常轮流秩序判断。输出JSON：selected_person_id、"
                    "intent(answer|react|interrupt)、confidence(0到1)、reason。"
                ),
                user=json.dumps(payload, ensure_ascii=False),
                temperature=0.0,
                max_tokens=350,
                max_attempts=1,
            )
            selected_id = str(raw.get("selected_person_id") or "")
            selected = next((persona for persona in candidates if persona.person_id == selected_id), None)
            proposed_intent = str(raw.get("intent") or intent).lower()
            if proposed_intent in SPEAKING_INTENTS:
                intent = proposed_intent
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0))))
            reason = str(raw.get("reason") or "").strip()
        except (WorkflowServiceError, TypeError, ValueError):
            fallback = True

        if selected is None:
            selected = self._fallback_persona(candidates, participation)
            confidence = 0.5
            reason = "路由结果不可用，回退到场景主角色"
            fallback = True
        if intent == "interrupt" and not participation[selected.person_id].can_interrupt:
            intent = "react" if input_kind == "action" else "answer"

        decisions = [
            self._decision(
                persona,
                selected=persona.person_id == selected.person_id,
                intent=intent,
                confidence=confidence if persona.person_id == selected.person_id else 1.0,
                reason=reason if persona.person_id == selected.person_id else "本轮由其他角色回应",
                fallback=fallback if persona.person_id == selected.person_id else False,
            )
            for persona in candidates
        ]
        return {
            "decisions": decisions,
            "actor_ids": [selected.person_id],
            "routing_summary": f"已路由至 {selected.name}，本轮仅由该角色回应",
        }
