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

    def _generate(self, system: str, user: str, *, max_tokens: int) -> tuple[str, dict]:
        meta = {"partial": False, "partial_reason": "", "error": ""}
        try:
            result = self.llm.complete_message(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=max_tokens,
                max_attempts=1,
                extra_kwargs=self._story_completion_kwargs(),
                allow_partial_on_timeout=True,
            )
            meta["partial"] = bool(result.get("partial"))
            meta["partial_reason"] = str(result.get("partial_reason") or "")
            meta["error"] = str(result.get("error") or "")
            return self._normalize_story_output(str(result.get("content") or "")), meta
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            meta["error"] = str(exc.message or exc)
            return "", meta

    def execute(self, cleaned_text: str) -> tuple[str, dict]:
        max_tokens = settings.complete_story_max_tokens
        story, gen_meta = self._generate(
            system=COMPLETE_STORY_SYSTEM_PROMPT,
            user=cleaned_text,
            max_tokens=max_tokens,
        )
        refusal_markers = ("无法整理", "原始案件文本未提供", "字符编码损坏", "不能构成完整", "无法构成完整")
        refused = bool(story and any(marker in story for marker in refusal_markers))
        if refused:
            story = ""
        audit = story_quality(cleaned_text, story)
        audit["generation"] = gen_meta
        audit["refused"] = refused
        repaired = False
        # Empty / timeout-partial / insufficient: always attempt one repair when possible.
        need_repair = (not story) or (not audit["sufficient"])
        if need_repair:
            repair_user = (
                f"原文：\n{cleaned_text}\n\n"
                f"当前不合格或中断的剧情：\n{story or '（空，可能因超时中断，请根据原文完整重写）'}\n\n"
                f"失败原因：{audit.get('fail_reasons') or ['empty_or_insufficient']}；"
                f"缺失证据类别：{audit['missing_evidence_markers']}；最低建议长度：{audit['minimum_story_chars']}字。"
            )
            repaired_story, repair_meta = self._generate(
                system=COMPLETE_STORY_REPAIR_PROMPT,
                user=repair_user,
                max_tokens=max(max_tokens, 12000),
            )
            audit["repair_generation"] = repair_meta
            repaired_audit = story_quality(cleaned_text, repaired_story)
            # Prefer repaired full pass; otherwise keep the longer usable draft (including timeout partial).
            if repaired_audit["sufficient"]:
                story, audit, repaired = repaired_story, repaired_audit, True
                audit["generation"] = gen_meta
                audit["repair_generation"] = repair_meta
            elif repaired_story and len(repaired_story) > len(story or ""):
                story = repaired_story
                audit = repaired_audit
                audit["generation"] = gen_meta
                audit["repair_generation"] = repair_meta
                repaired = True
        if not audit.get("sufficient"):
            # Last resort: if we still hold a chaptered partial draft, keep it instead of OCR paste
            # when it already looks like a narrative with chapters.
            keep_partial = bool(story) and story.count("## ") >= 1 and len(story) >= max(600, audit.get("minimum_story_chars", 600) // 2)
            if keep_partial:
                audit["fallback"] = "partial_draft_kept"
                audit["sufficient"] = False
            else:
                story = "# 案件完整剧情\n\n" + cleaned_text
                audit = story_quality(cleaned_text, story)
                audit["fallback"] = "source_preserving"
                audit["generation"] = gen_meta
        audit["repaired"] = repaired
        return story, audit
