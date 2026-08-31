from __future__ import annotations

import json
import re
from typing import Any

from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter


class SceneScriptSkill:
    """Generate script-first scene packages for police training."""

    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    @staticmethod
    def _list_of_text(value: Any) -> list[str]:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            # Guard against string mistakenly iterated into single characters.
            if items and all(len(item) == 1 for item in items) and len(items) >= 8:
                rejoined = "".join(items).strip()
                return [rejoined] if rejoined else []
            return items
        text = str(value or "").strip()
        if not text:
            return []
        if any(token in text for token in ("\n", "；", ";")):
            parts = re.split(r"[\n；;]+", text)
            return [part.strip("  -0123456789.、)") for part in parts if part.strip("  -0123456789.、)")]
        return [text]

    @staticmethod
    def _phase(value: Any) -> str:
        text = str(value or "").strip()
        if text in {"intake", "post_incident_onsite", "post_incident_inquiry", "post_incident_followup"}:
            return text
        if any(token in text for token in ("接警", "派警", "报警", "指令")):
            return "intake"
        if any(token in text for token in ("到场", "现场", "稳控", "初处")):
            return "post_incident_onsite"
        if any(token in text for token in ("询问", "调查", "核实", "取证")):
            return "post_incident_inquiry"
        if any(token in text for token in ("收尾", "移交", "善后", "总结")):
            return "post_incident_followup"
        return "post_incident_onsite"

    @staticmethod
    def _assessment_points(value: Any, learner_actions: list[str]) -> list[dict[str, Any]]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(rows, start=1):
            if isinstance(item, dict):
                label = str(item.get("label") or item.get("assessment_item") or item.get("name") or f"考核点{index}").strip()
                content = str(item.get("content") or item.get("standard") or item.get("description") or label).strip()
                keywords = [str(word).strip() for word in item.get("keywords") or [] if str(word).strip()]
                related_actions = [str(action).strip() for action in item.get("related_actions") or item.get("actions") or [] if str(action).strip()]
                if not related_actions:
                    related_actions = learner_actions[:3]
                if not keywords and label:
                    keywords = [label]
                normalized.append({
                    "label": label,
                    "content": content,
                    "keywords": keywords,
                    "related_actions": related_actions,
                })
            else:
                text = str(item or "").strip()
                if text:
                    normalized.append({
                        "label": f"考核点{index}",
                        "content": text,
                        "keywords": [text],
                        "related_actions": learner_actions[:3],
                    })
        return normalized

    @classmethod
    def _normalize_stage(cls, stage: Any, index: int, training_goal: str) -> dict[str, Any]:
        data = stage if isinstance(stage, dict) else {}
        learner_actions = cls._list_of_text(data.get("learner_actions"))
        return {
            "stage_name": str(data.get("stage_name") or f"训练阶段{index + 1}").strip(),
            "stage_goal": str(data.get("stage_goal") or training_goal).strip(),
            "learner_actions": learner_actions,
            "role_pressure_points": cls._list_of_text(data.get("role_pressure_points")),
            "expected_stage_effects": cls._list_of_text(data.get("expected_stage_effects")),
            "assessment_points": cls._assessment_points(data.get("assessment_points"), learner_actions),
            "fact_ids": [str(item).strip() for item in data.get("fact_ids") or [] if str(item).strip()],
            "recommended_prompts": cls._list_of_text(data.get("recommended_prompts")) or learner_actions[:4],
        }

    @staticmethod
    def _normalize_script(item: Any, index: int) -> dict[str, Any]:
        data = item if isinstance(item, dict) else {}
        scene_pack = data.get("scene_pack") if isinstance(data.get("scene_pack"), dict) else {}
        stage_list = data.get("stages") if isinstance(data.get("stages"), list) else []
        role_funcs = data.get("role_training_functions") if isinstance(data.get("role_training_functions"), list) else []
        training_goal = str(data.get("training_goal") or "").strip()
        opening_lines = []
        for line in data.get("opening_lines") or []:
            if not isinstance(line, dict):
                continue
            content = str(line.get("content") or line.get("line") or "").strip()
            speaker = str(line.get("speaker_name") or line.get("role_name") or "").strip()
            if content:
                opening_lines.append({"speaker_name": speaker, "content": content[:240]})
        stages = [SceneScriptSkill._normalize_stage(stage, i, training_goal) for i, stage in enumerate(stage_list) if isinstance(stage, dict)]
        if not opening_lines and role_funcs:
            first_role = str(role_funcs[0].get("role_name") or "").strip()
            pressure = ""
            if stages:
                pressures = stages[0].get("role_pressure_points") or []
                pressure = str(pressures[0] if pressures else "")
            plot = str(data.get("plot_arc") or "").strip()
            snippet = pressure or plot[:80]
            if snippet:
                opening_lines.append({
                    "speaker_name": first_role,
                    "content": f"警察来了就好……{snippet}。你们先听我说清楚。"[:240],
                })
        return {
            "script_id": str(data.get("script_id") or f"script-{index + 1}"),
            "scene_name": str(data.get("scene_name") or "").strip(),
            "scene_pack": {
                "dispatch_brief": str(scene_pack.get("dispatch_brief") or data.get("dispatch_brief") or "").strip(),
                "first_impression": str(scene_pack.get("first_impression") or data.get("first_impression") or "").strip(),
                "training_entry_phase": SceneScriptSkill._phase(scene_pack.get("training_entry_phase") or data.get("training_entry_phase")),
                "student_role": "民警" if "民警" in str(scene_pack.get("student_role") or data.get("student_role") or "民警") else str(scene_pack.get("student_role") or data.get("student_role") or "民警").strip(),
            },
            "training_goal": training_goal,
            "expected_outcomes": SceneScriptSkill._list_of_text(data.get("expected_outcomes"))[:6],
            "plot_arc": str(data.get("plot_arc") or "").strip(),
            "opening_lines": opening_lines[:3],
            "stages": stages,
            "role_training_functions": [row for row in role_funcs if isinstance(row, dict)],
            "completion_criteria": SceneScriptSkill._list_of_text(data.get("completion_criteria")),
            "failure_patterns": SceneScriptSkill._list_of_text(data.get("failure_patterns")),
        }

    def execute(self, case_world: dict[str, Any], complete_story: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        system_prompt = (
            "你是公安实战训练剧本策划。基于案件事实生成 1-4 个必要训练剧本，单场景足够时必须只输出 1 个。"
            "禁止检察、法庭、定罪量刑、复盘汇报场景。"
            "输出 JSON：{training_scripts:[...]}。每个 training_script 必须包含："
            "script_id,scene_name,scene_pack,training_goal,expected_outcomes,plot_arc,opening_lines,stages,"
            "role_training_functions,completion_criteria,failure_patterns。"
            "scene_pack 必须包含 dispatch_brief,first_impression,training_entry_phase,student_role。"
            "expected_outcomes 为本场景考察点，必须输出 1-6 条可观察短句（如“能够安全控制现场，避免冲突升级”），"
            "这是考察配置的唯一剧本真源；禁止写成旧式考察点大题干。"
            "opening_lines 为 1-3 条角色开场口语，每项含 speaker_name,content，必须贴合 plot_arc 和第一阶段压力点，禁止固定套话如“喂，110吗？”或“警察同志，你们来了。”"
            "stages 必须覆盖开端/发展/收尾，且每阶段包含 stage_name,stage_goal,learner_actions,role_pressure_points,"
            "expected_stage_effects,fact_ids,recommended_prompts。"
            "recommended_prompts 为学员可直接说出的问句。"
            "role_training_functions 每项包含 role_name,training_function,expected_interaction_effect。"
            "只用输入中的人物与事实，不得新增案外角色和案外事实。"
        )
        request_payload = {"case_world": case_world, "complete_story": complete_story}
        try:
            result = self.llm.complete_json(
                system=system_prompt,
                user=json.dumps(request_payload, ensure_ascii=False),
                max_tokens=7000,
                max_attempts=1,
            )
            scripts = result.get("training_scripts") if isinstance(result.get("training_scripts"), list) else []
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            scripts = []
        normalized = [self._normalize_script(item, i) for i, item in enumerate(scripts[:4])]
        sufficient = bool(normalized and normalized[0].get("scene_name") and normalized[0].get("training_goal"))
        return normalized, {"count": len(normalized), "sufficient": sufficient}
