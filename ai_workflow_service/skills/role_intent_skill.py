from __future__ import annotations

from typing import Any

from ai_workflow_service.contracts import Persona, RoleParticipation
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter


class RoleIntentSkill:
    """Admit present TinyTroupe actors. The world decides who actually talks."""

    def __init__(self, llm: DeepSeekAdapter):
        del llm

    @staticmethod
    def _decision(
        persona: Persona,
        *,
        intent: str,
        reason: str,
        addressed: bool = False,
    ) -> dict[str, Any]:
        return {
            "person_id": persona.person_id,
            "intent": intent,
            "confidence": 1.0,
            "reason": reason,
            "addressed": addressed,
            "fallback": False,
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
        del input_kind, public_history, fact_access
        candidates = [persona for persona in personas if participation[persona.person_id].present]
        if not candidates:
            return {"decisions": [], "actor_ids": [], "routing_summary": "当前没有可参与对话的角色"}

        explicit = self._explicit_target(candidates, learner_input, target_role_name)
        ordered: list[Persona] = []
        if explicit:
            ordered.append(explicit)
        for persona in candidates:
            if persona not in ordered and (
                persona.is_primary or participation[persona.person_id].can_initiate
            ):
                ordered.append(persona)
        for persona in candidates:
            if persona not in ordered:
                ordered.append(persona)

        cap = max(1, min(6, max_actors))
        actors = ordered[:cap]
        actor_ids = {item.person_id for item in actors}
        decisions = [
            self._decision(
                persona,
                intent="world_act" if persona.person_id in actor_ids else "observe",
                reason=(
                    "进入 TinyTroupe 世界，由人物自己决定发言或沉默"
                    if persona.person_id in actor_ids
                    else "本轮仅作为在场观察者接收公开事件"
                ),
                addressed=bool(explicit and persona.person_id == explicit.person_id),
            )
            for persona in candidates
        ]
        names = "、".join(item.name for item in actors)
        return {
            "decisions": decisions,
            "actor_ids": [item.person_id for item in actors],
            "routing_summary": f"TinyTroupe 世界推演，在场行动角色：{names}",
        }
