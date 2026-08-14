from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_workflow_service.contracts import Fact, Persona


@dataclass(frozen=True)
class RoleMemoryBundle:
    fixed: dict[str, Any]
    facts: dict[str, list[dict[str, Any]]]
    conversation: list[dict[str, Any]]
    dynamic_state: dict[str, float]


class MemoryManager:
    def build(self, persona: Persona, facts: list[Fact], recent_dialogue: list[dict[str, Any]]) -> RoleMemoryBundle:
        hidden = set(persona.hidden_fact_ids)
        known = [fact.model_dump(mode="json") for fact in facts if fact.fact_id in persona.known_fact_ids]
        return RoleMemoryBundle(
            fixed={
                "person_id": persona.person_id,
                "name": persona.name,
                "role": persona.role,
                "traits": persona.traits,
                "speaking_style": persona.speaking_style,
                "goals": persona.goals,
            },
            facts={
                "known": known,
                "hidden": [item for item in known if item["fact_id"] in hidden],
                "answerable": [item for item in known if item["fact_id"] not in hidden],
            },
            conversation=list(recent_dialogue)[-10:],
            dynamic_state=dict(persona.state),
        )
