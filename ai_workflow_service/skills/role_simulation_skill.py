from __future__ import annotations

import json

from ai_workflow_service.contracts import CaseWorld, Persona, SceneWorld, SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.simulation.tinytroupe_adapter import TinyTroupeAdapter
from ai_workflow_service.skills.base import Skill


class RoleSimulationSkill(Skill):
    name = SkillName.role_simulation
    next_stage = WorkflowStage.training

    def __init__(self, llm: DeepSeekAdapter, simulation: TinyTroupeAdapter):
        self.llm = llm
        self.simulation = simulation

    def execute(self, request: WorkflowRequest) -> dict:
        learner_input = str(request.payload.get("learner_input") or "").strip()
        if not learner_input:
            raise WorkflowServiceError("INVALID_LEARNER_INPUT", "学员输入不能为空")
        case_world = CaseWorld.model_validate(request.payload.get("case_world") or {})
        scene = SceneWorld.model_validate(request.payload.get("scene_world") or {})
        persona = Persona.model_validate(request.payload.get("persona") or {})
        self.simulation.build_world(scene, [persona])
        snapshot = self.simulation.infer_tendency(persona, learner_input)
        known = [fact for fact in case_world.facts if fact.fact_id in persona.known_fact_ids]
        hidden_ids = set(persona.hidden_fact_ids)
        context = {
            "persona": persona.model_dump(mode="json"),
            "scene": scene.model_dump(mode="json"),
            "known_facts": [fact.model_dump(mode="json") for fact in known],
            "hidden_fact_ids": sorted(hidden_ids),
            "behavior_tendency": snapshot.behavior_tendency,
            "state": snapshot.state,
            "recent_dialogue": list(request.payload.get("recent_dialogue") or [])[-10:],
            "learner_input": learner_input,
        }
        result = self.llm.complete_json(
            system=(
                "你是警情训练中的案件人物。只按提供的本人已知事实回答；不得泄露隐藏事实、"
                "不得创造新案情、不得替其他人发言。输出 JSON：reply、revealed_fact_ids、state。"
            ),
            user=json.dumps(context, ensure_ascii=False),
            temperature=0.65,
            max_tokens=1200,
        )
        reply = str(result.get("reply") or "").strip()
        revealed = [str(item) for item in result.get("revealed_fact_ids") or []]
        allowed = set(persona.known_fact_ids) - hidden_ids
        if not reply or any(item not in allowed for item in revealed):
            raise WorkflowServiceError("ROLE_VALIDATION_FAILED", "角色回复未通过知识边界校验", retryable=True)
        return {
            "reply": reply,
            "speaker": {"person_id": persona.person_id, "name": persona.name},
            "revealed_fact_ids": revealed,
            "state": snapshot.state,
            "behavior_tendency": snapshot.behavior_tendency,
        }
