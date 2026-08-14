from __future__ import annotations

import json
import re
from typing import Any

from ai_workflow_service.domain.scene_blueprints import normalize_blueprint, select_necessary_scenes
from ai_workflow_service.domain.dialogue_scene_admission import (
    admission_prompt_block,
    filter_dialogue_admitted_scenes,
)
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.skills import CompleteStorySkill, FactAnalysisSkill, PersonMemorySkill
from ai_workflow_service.tools.audit_log import AuditLogTool


class CaseImportHarnessAgent:
    """The single source-to-training-world orchestration entry."""

    def __init__(self, llm: DeepSeekAdapter, audit_log: AuditLogTool):
        self.llm = llm
        self.audit_log = audit_log
        self.complete_story = CompleteStorySkill(llm)
        self.fact_analysis = FactAnalysisSkill(llm)
        self.person_memory = PersonMemorySkill(llm)

    def _record(self, trace_id: str, workflow_id: str, node: str, status: str, **details: Any) -> None:
        self.audit_log.write({"trace_id": trace_id, "workflow_id": workflow_id, "node": node, "status": status, **details})

    @staticmethod
    def _clean_source(source_text: str) -> dict[str, Any]:
        original = source_text.replace("\r", "").strip()
        paragraphs = [item.strip() for item in re.split(r"\n+", original) if item.strip()]
        excluded = [item for item in paragraphs if any(token in item for token in ("目录", "证据目录", "审判长", "如不服本判决"))]
        cleaned = "\n\n".join(item for item in paragraphs if item not in excluded).strip() or original
        if not cleaned:
            raise WorkflowServiceError("INVALID_CASE_SOURCE", "案件原文不能为空")
        return {"cleaned_text": cleaned, "excluded_appendix": excluded, "original_chars": len(original), "cleaned_chars": len(cleaned)}

    def _blueprints(self, world: Any, story: str, *, trace_id: str, workflow_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        try:
            result = self.llm.complete_json(
                system=("依据案件故事世界和训练目标生成必要训练场景，只输出 JSON：{scenes:[...]}。"
                        + admission_prompt_block()
                        + "学员固定为一线处置民警，禁止生成检察审查、法庭辩论、定罪量刑场景。场景必须完整、互不重复且"
                        "只能为可执行的警情处置训练目标服务，单场景足够时只生成 1 个，最多 4 个。每个场景必须使用不同且明确的"
                        "scene_name，并含 student_role、training_entry_phase、training_goal、dispatch_brief、"
                        "first_impression、expected_outcomes、scene_roles.initial_state(emotion/cooperation/risk/clarity)、"
                        "场景 fact_ids，以及 stages/assessment_points/action_catalog/completion_rules/end_conditions。"
                        "每个阶段也必须包含 fact_ids；roles 只放本场景需要对话的人物，不得把全部人物复制到每个场景。"
                        "所有人物和事实编号必须来自 case_world，不得超出人物和事实边界。"),
                user=json.dumps({"case_world": world.model_dump(mode="json"), "complete_story": story}, ensure_ascii=False),
                max_tokens=7000, max_attempts=1,
            )
            raw_scenes = result.get("scenes") if isinstance(result.get("scenes"), list) else []
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            raw_scenes = []
        if not raw_scenes:
            raw_scenes = [{}]
            self._record(trace_id, workflow_id, "scene_blueprint_agent", "rule_fallback", reason="model_unavailable_or_empty")
        normalized = [normalize_blueprint(
            raw, case_id=world.case_id, index=i, title=world.title, summary=world.summary,
            persons=world.persons, facts=world.facts, default_location=world.locations[0] if world.locations else "",
        ) for i, raw in enumerate(raw_scenes[:4])]
        selected = select_necessary_scenes(normalized)
        if not selected:
            raise WorkflowServiceError("INVALID_SCENE_BLUEPRINT", "未生成有效的必要训练场景")
        _admitted, rejected = filter_dialogue_admitted_scenes(normalized, allow_remap=False)
        scene_admission = {
            "rule_version": "dialogue_scene_admission_v1",
            "admitted_count": len(selected),
            "rejected_count": len(rejected),
            "rejected_scenes": [
                {
                    "scene_name": item.get("scene_name"),
                    "reasons": (item.get("dialogue_admission") or {}).get("reasons") or [],
                    "non_dialogue_markers": (item.get("dialogue_admission") or {}).get("non_dialogue_markers") or [],
                    "suggested_alternative": (item.get("dialogue_admission") or {}).get("suggested_alternative") or "",
                }
                for item in rejected
            ],
            "sufficient": all(isinstance(item.get("dialogue_admission"), dict) and item["dialogue_admission"].get("admitted") for item in selected),
        }
        if rejected:
            self._record(
                trace_id, workflow_id, "dialogue_scene_admission", "filtered",
                rejected_count=len(rejected),
                rejected_names=[item.get("scene_name") for item in rejected],
            )
        return selected, scene_admission

    def execute(self, *, workflow_id: str, case_id: str, source_text: str, trace_id: str) -> dict[str, Any]:
        self._record(trace_id, workflow_id, "import_case_source", "started")
        cleaned = self._clean_source(source_text)
        self._record(trace_id, workflow_id, "import_case_source", "succeeded", chars=cleaned["original_chars"])
        self._record(trace_id, workflow_id, "text_cleaning_agent", "succeeded", chars=cleaned["cleaned_chars"])
        story, story_audit = self.complete_story.execute(cleaned["cleaned_text"])
        self._record(trace_id, workflow_id, "complete_story_skill", "succeeded", **story_audit)
        world, fact_audit = self.fact_analysis.execute(case_id, story)
        self._record(trace_id, workflow_id, "fact_analysis_skill", "succeeded", **fact_audit)
        world, memories, memory_audit = self.person_memory.execute(world, story)
        self._record(trace_id, workflow_id, "person_memory_skill", "succeeded", **memory_audit)
        story_world = {"complete_story": story, "facts": [fact.model_dump(mode="json") for fact in world.facts], "roles": memories}
        self._record(trace_id, workflow_id, "case_story_world", "succeeded")
        scenes, scene_admission = self._blueprints(world, story, trace_id=trace_id, workflow_id=workflow_id)
        self._record(
            trace_id, workflow_id, "scene_blueprint_agent", "succeeded",
            candidate_count=len(scenes), bound_fact_count=sum(len(scene.get("fact_ids") or []) for scene in scenes),
        )
        self._record(trace_id, workflow_id, "necessary_scene_selector", "succeeded", scene_count=len(scenes))
        return {
            "cleaning": cleaned, "complete_story": story, "case_world": world.model_dump(mode="json"),
            "role_memories": memories, "story_world": story_world,
            "scene_blueprint": scenes[0], "scene_blueprints": scenes, "necessary_scenes": scenes,
            "case_import_quality": {
                "story": story_audit,
                "facts": fact_audit,
                "memories": memory_audit,
                "scene_admission": scene_admission,
            },
            "training_read_sources": {"role_memory": True, "role_information": True, "facts": True, "recent_context": True},
        }
