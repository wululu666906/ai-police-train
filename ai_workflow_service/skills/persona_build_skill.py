from __future__ import annotations

from ai_workflow_service.contracts import CaseWorld, Persona, SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.skills.base import Skill


class PersonaBuildSkill(Skill):
    name = SkillName.persona_build
    next_stage = WorkflowStage.personas_ready

    def execute(self, request: WorkflowRequest) -> dict:
        world = CaseWorld.model_validate(request.payload.get("case_world") or {})
        personas = []
        for person in world.persons:
            personas.append(
                Persona(
                    person_id=person.person_id,
                    name=person.name,
                    role=person.role,
                    traits=["符合案件材料", "保持知识边界"],
                    goals=["按本人立场自然回应"],
                    known_fact_ids=person.facts_known,
                    hidden_fact_ids=person.facts_hidden,
                    state={"trust": 0.4, "pressure": 0.3, "anger": 0.2, "fear": 0.3},
                )
            )
        return {"personas": [item.model_dump(mode="json") for item in personas]}
