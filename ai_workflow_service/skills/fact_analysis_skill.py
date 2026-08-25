from __future__ import annotations

import re

from ai_workflow_service.contracts import CaseWorld, Fact
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.domain.case_import_quality import fact_quality

COURT_NOISE_MARKERS = (
    "本院认为", "判决如下", "裁定如下", "经审理查明", "审理查明",
    "公诉机关", "公诉人", "辩护人", "辩护意见", "审判员", "书记员",
    "人民法院", "定罪", "量刑", "构成要件", "如不服本判决",
)

STORY_EVENT_MARKERS = (
    "持", "拿", "携带", "组织", "召集", "通知", "纠集", "带领", "参与", "实施",
    "殴打", "击打", "追赶", "阻拦", "劝阻", "报警", "报案", "送医", "救助",
    "受伤", "损伤", "轻伤", "重伤", "被打", "被砍", "逃离", "离开", "到场",
    "赶到", "种植", "毁坏", "争吵", "冲突", "推搡", "砍", "砸", "拔",
)


def _is_court_noise(text: str) -> bool:
    return any(marker in text for marker in COURT_NOISE_MARKERS)


def _is_story_event(text: str) -> bool:
    return any(marker in text for marker in STORY_EVENT_MARKERS)


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
        rows = []
        for sentence in re.split(r"(?<=[。！？；])|\n+", complete_story):
            content = sentence.strip().lstrip("# ")
            if _is_court_noise(content):
                continue
            if 10 <= len(content) <= 500 and not content.startswith(("案件完整剧情", "证据如下")):
                if _is_story_event(content) or len(rows) < 8:
                    rows.append({
                        "content": content,
                        "source_quote": content,
                        "fact_type": "行为" if _is_story_event(content) else "事实",
                        "status": "source_supported",
                    })
            if len(rows) >= 80:
                break
        return rows

    def execute(self, case_id: str, complete_story: str) -> tuple[CaseWorld, dict]:
        try:
            result = self.llm.complete_json(
                system=("根据完整案件剧情抽取原子事实、时间线、地点和人物关系，不得虚构。"
                        "聚焦案发经过中的人物行为与重要事件，尽量多拆分行为事实；"
                        "覆盖主要人物、关键时间地点、各方陈述、物证书证、伤情、报警处置和结果。"
                        "禁止写入法院审理、辩护意见、定罪量刑、裁判说理或诉讼程序套话。"
                        "事实必须拆分到单一行为、陈述、证据、伤情或处置，不得把整段案件概括成一条。"
                        "只输出 JSON：title,case_type,summary,facts,timeline,locations,relationships。"
                        "facts 含 fact_id、content、source_quote、source、fact_type、status、known_by、unknown_by、secret；"
                        "source_quote 必须逐字摘自完整剧情。"),
                user=complete_story, max_tokens=7000, max_attempts=1,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            result = {}
        raw_facts = result.get("facts") if isinstance(result.get("facts"), list) else []
        expected_minimum = 1 if len(complete_story) < 500 else min(18, max(6, len(complete_story) // 500))
        if len(raw_facts) < expected_minimum:
            raw_facts = [*raw_facts, *self._fallback_facts(complete_story)]
        facts = []
        used_fact_ids: set[str] = set()
        used_contents: set[str] = set()
        next_fact_number = 1
        for index, raw in enumerate(raw_facts):
            item = raw if isinstance(raw, dict) else {}
            content = str(item.get("content") or item.get("fact") or "").strip()
            if not content or content in used_contents or _is_court_noise(content):
                continue
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
                fact_type=str(item.get("fact_type") or ("行为" if _is_story_event(content) else "事实")),
                status=str(item.get("status") or "claimed"),
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
