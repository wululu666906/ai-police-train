from __future__ import annotations

import re

from ai_workflow_service.config import settings
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.domain.case_import_quality import story_quality
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.prompts.complete_story import COMPLETE_STORY_REPAIR_PROMPT, COMPLETE_STORY_SYSTEM_PROMPT


class CompleteStorySkill:
    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def _story_completion_kwargs(self) -> dict:
        mode = settings.complete_story_reasoning_mode
        model = settings.deepseek_model.lower()
        # deepseek-v4-flash 在 json_object + thinking 模式下 content 为空，会误触原文兜底。
        if "flash" in model or mode in {"disabled", "off", "false", "0"}:
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        effort = settings.complete_story_reasoning_effort
        if effort not in {"high", "max"}:
            effort = "max"
        return {
            "reasoning_effort": effort,
            "extra_body": {"thinking": {"type": "enabled"}},
        }

    @staticmethod
    def _normalize_story_output(raw: str) -> str:
        story = str(raw or "").strip()
        if story.startswith("```"):
            story = re.sub(r"^```(?:markdown|md|text)?\s*", "", story)
            story = re.sub(r"\s*```$", "", story).strip()
        if story and not story.startswith("#"):
            story = "# 案件完整剧情\n\n" + story.lstrip("# ")
        return story

    def _generate(self, system: str, user: str, *, max_tokens: int) -> str:
        try:
            result = self.llm.complete_message(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=max_tokens,
                max_attempts=1,
                extra_kwargs=self._story_completion_kwargs(),
            )
            return self._normalize_story_output(str(result.get("content") or ""))
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            return ""

    def execute(self, cleaned_text: str) -> tuple[str, dict]:
        max_tokens = settings.complete_story_max_tokens
        story = self._generate(
            system=COMPLETE_STORY_SYSTEM_PROMPT,
            user=cleaned_text,
            max_tokens=max_tokens,
        )
        refusal_markers = ("无法整理", "原始案件文本未提供", "字符编码损坏", "不能构成完整", "无法构成完整")
        if any(marker in story for marker in refusal_markers):
            story = ""
        audit = story_quality(cleaned_text, story)
        repaired = False
        if story and not audit["sufficient"]:
            repaired_story = self._generate(
                system=COMPLETE_STORY_REPAIR_PROMPT,
                user=(
                    f"原文：\n{cleaned_text}\n\n当前不合格剧情：\n{story}\n\n"
                    f"缺失证据类别：{audit['missing_evidence_markers']}；最低建议长度：{audit['minimum_story_chars']}字。"
                ),
                max_tokens=max(max_tokens, 12000),
            )
            repaired_audit = story_quality(cleaned_text, repaired_story)
            if repaired_audit["sufficient"]:
                story, audit, repaired = repaired_story, repaired_audit, True
        if not audit["sufficient"]:
            story = "# 案件完整剧情\n\n" + cleaned_text
            audit = story_quality(cleaned_text, story)
            audit["fallback"] = "source_preserving"
        audit["repaired"] = repaired
        return story, audit
