from __future__ import annotations

import json
from typing import Any

from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter


class RecommendedQuestionsSkill:
    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def execute(
        self,
        *,
        payload: dict[str, Any],
        training_result: dict[str, Any],
        role_intents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        missing = list(training_result.get("stage_completion_missing") or [])
        if not missing:
            return []
        personas = [item for item in payload.get("personas") or [] if isinstance(item, dict)]
        request_payload = {
            "scene": payload.get("scene_world") or {},
            "current_stage": payload.get("stage") or {},
            "missing_assessment_items": missing,
            "completed_point_ids": training_result.get("completed_point_ids") or [],
            "revealed_fact_ids": payload.get("revealed_fact_ids") or [],
            "public_history": (payload.get("public_history") or payload.get("recent_dialogue") or [])[-20:],
            "roles": [
                {"name": item.get("name"), "role": item.get("role"), "person_id": item.get("person_id")}
                for item in personas
            ],
            "role_intents": role_intents,
        }
        try:
            raw = self.llm.complete_json(
                system=(
                    "你是警情实训建议追问节点。依据完整公开对话和累计考核进度，生成3到5条学员下一步可直接说出的问句。"
                    "问题必须帮助完成尚缺考核项，指定合理的在场目标角色，不得泄露未披露事实、标准答案或角色私有记忆。"
                    "避免重复最近已经问过的问题。只输出JSON：questions数组，每项包含text、category、priority、"
                    "target_role_name、related_point_id。"
                ),
                user=json.dumps(request_payload, ensure_ascii=False),
                temperature=0.2,
                max_tokens=1000,
                max_attempts=1,
            )
            rows = raw.get("questions") if isinstance(raw.get("questions"), list) else []
        except WorkflowServiceError:
            rows = []
        role_names = {str(item.get("name") or "") for item in personas}
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw_item in enumerate(rows):
            if not isinstance(raw_item, dict):
                continue
            text = str(raw_item.get("text") or "").strip()
            if not text or text in seen:
                continue
            target = str(raw_item.get("target_role_name") or "").strip()
            results.append({
                "text": text,
                "category": str(raw_item.get("category") or "信息核实"),
                "priority": str(raw_item.get("priority") or "medium"),
                "target_role_name": target if target in role_names else None,
                "related_point_id": str(raw_item.get("related_point_id") or ""),
            })
            seen.add(text)
            if len(results) == 5:
                break
        if results:
            return results
        primary = next((item for item in personas if item.get("is_primary")), personas[0] if personas else {})
        target = str(primary.get("name") or "") or None
        return [
            {
                "text": f"请具体说明与“{item}”有关的情况？",
                "category": "缺失项",
                "priority": "high",
                "target_role_name": target,
                "related_point_id": "",
            }
            for item in missing[:3]
        ]
