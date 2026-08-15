from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_workflow_service.contracts import Fact, Persona


@dataclass(frozen=True)
class RoleMemoryBundle:
    identity: dict[str, Any]
    private_memories: list[dict[str, Any]]
    answerable_facts: list[dict[str, Any]]
    public_history: list[dict[str, Any]]
    dynamic_state: dict[str, int]


class MemoryManager:
    def build(
        self,
        persona: Persona,
        facts: list[Fact],
        recent_dialogue: list[dict[str, Any]],
        *,
        allowed_fact_ids: set[str] | None = None,
    ) -> RoleMemoryBundle:
        allowed = allowed_fact_ids if allowed_fact_ids is not None else set(persona.known_fact_ids) - set(persona.hidden_fact_ids)
        answerable = [fact.model_dump(mode="json") for fact in facts if fact.fact_id in allowed]
        safe_memories = [
            memory for memory in persona.role_memories
            if isinstance(memory, dict) and str(memory.get("fact_id") or "") in allowed
        ]
        return RoleMemoryBundle(
            identity={
                "person_id": persona.person_id,
                "name": persona.name,
                "role": persona.role,
                "traits": persona.traits,
                "speaking_style": persona.speaking_style,
                "goals": persona.goals,
            },
            private_memories=safe_memories[:12],
            answerable_facts=answerable,
            public_history=list(recent_dialogue)[-20:],
            dynamic_state=persona.state.model_dump(mode="json"),
        )
