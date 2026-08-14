from __future__ import annotations

from ai_workflow_service.contracts import CaseWorld, Fact
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.domain.case_import_quality import fact_quality


def _source_refs(item: dict, complete_story: str, content: str) -> list[dict]:
    proposed = item.get("source_refs")
    if isinstance(proposed, list):
        valid = [ref for ref in proposed if isinstance(ref, dict)]
        if valid:
            return valid

    candidates = (
        item.get("source_quote"), item.get("quote"),
        item.get("source") if item.get("source") != "完整剧情" else "",
        content,
    )
    for candidate in candidates:
        quote = str(candidate or "").strip()
        if not quote:
            continue
        start = complete_story.find(quote)
        if start >= 0:
            return [{
                "source_id": "complete-story",
                "start": start,
                "end": start + len(quote),
                "summary": quote[:180],
            }]
    return [{
        "source_id": "complete-story",
        "start": 0,
        "end": len(complete_story),
        "summary": content[:180],
    }]


class FactAnalysisSkill:
    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    @staticmethod
    def _fallback_facts(complete_story: str) -> list[dict]:
        import re
        rows = []
        for sentence in re.split(r"(?<=[。！？；])|\n+", complete_story):
            content = sentence.strip().lstrip("# ")
            if 12 <= len(content) <= 500 and not content.startswith(("案件完整剧情", "证据如下")):
                rows.append({"content": content, "source_quote": content, "fact_type": "事实", "status": "source_supported"})
            if len(rows) >= 40:
                break
        return rows

    def execute(self, case_id: str, complete_story: str) -> tuple[CaseWorld, dict]:
        try:
            result = self.llm.complete_json(
                system=("根据完整案件剧情抽取原子事实、时间线、地点和人物关系，不得虚构。事实必须拆分到单一行为、"
                        "陈述、证据、伤情或处置，不得把整段案件概括成一条。覆盖主要人物、关键时间地点、各方陈述、"
                        "物证书证、鉴定、报警处置和结果。只输出 JSON：title,case_type,summary,facts,timeline,locations,relationships。"
                        "facts 含 fact_id、content、source_quote、source、fact_type、status、known_by、unknown_by、secret；"
                        "source_quote 必须逐字摘自完整剧情。"),
                user=complete_story, max_tokens=6000, max_attempts=1,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            result = {}
        raw_facts = result.get("facts") if isinstance(result.get("facts"), list) else []
        expected_minimum = 1 if len(complete_story) < 500 else min(12, max(4, len(complete_story) // 700))
        if len(raw_facts) < expected_minimum:
            raw_facts = [*raw_facts, *self._fallback_facts(complete_story)]
        facts = []
        used_fact_ids: set[str] = set()
        used_contents: set[str] = set()
        next_fact_number = 1
        for index, raw in enumerate(raw_facts):
            item = raw if isinstance(raw, dict) else {}
            content = str(item.get("content") or item.get("fact") or "").strip()
            if content and content not in used_contents:
                proposed_id = str(item.get("fact_id") or f"F{index + 1:03d}").strip()
                fact_id = proposed_id
                while not fact_id or fact_id in used_fact_ids:
                    fact_id = f"F{next_fact_number:03d}"
                    next_fact_number += 1
                used_fact_ids.add(fact_id)
                used_contents.add(content)
                facts.append(Fact(
                    fact_id=fact_id, content=content,
                    source=str(item.get("source") or "完整剧情"), known_by=[str(v) for v in item.get("known_by") or []],
                    unknown_by=[str(v) for v in item.get("unknown_by") or []], secret=bool(item.get("secret", False)),
                    source_refs=_source_refs(item, complete_story, content),
                    fact_type=str(item.get("fact_type") or "事实"), status=str(item.get("status") or "claimed"),
                ))
        if not facts:
            facts = [Fact(
                fact_id="F001", content=complete_story, source="完整剧情",
                source_refs=[{"source_id": "complete-story", "start": 0, "end": len(complete_story), "summary": complete_story[:180]}],
            )]
        world = CaseWorld(
            case_id=case_id, title=str(result.get("title") or "案件导入"),
            case_type=str(result.get("case_type") or "其他"), summary=str(result.get("summary") or complete_story[:500]), facts=facts,
            timeline=list(result.get("timeline") or []),
            locations=[
                str(value.get("name") or value.get("location") or value.get("address") or "").strip()
                if isinstance(value, dict) else str(value).strip()
                for value in result.get("locations") or []
                if (isinstance(value, dict) and str(value.get("name") or value.get("location") or value.get("address") or "").strip())
                or (not isinstance(value, dict) and str(value).strip())
            ],
            relationships=list(result.get("relationships") or []),
        )
        return world, fact_quality(world.facts, complete_story)
