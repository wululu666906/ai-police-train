from __future__ import annotations

from ai_workflow_service.contracts import CaseWorld, SceneWorld, SkillName, WorkflowRequest, WorkflowStage
from ai_workflow_service.skills.base import Skill


class SceneBuildSkill(Skill):
    name = SkillName.scene_build
    next_stage = WorkflowStage.ready

    def execute(self, request: WorkflowRequest) -> dict:
        world = CaseWorld.model_validate(request.payload.get("case_world") or {})
        scene = SceneWorld(
            scene_id=str(request.payload.get("scene_id") or f"{world.case_id}-scene-1"),
            case_id=world.case_id,
            name=str(request.payload.get("name") or world.title or "警情处置训练"),
            environment=dict(request.payload.get("environment") or {}),
            role_ids=[person.person_id for person in world.persons],
            rules=["角色不得突破知识边界", "不得创造影响案情的新事实", "训练状态由平台提交"],
        )
        return {"scene_world": scene.model_dump(mode="json")}
