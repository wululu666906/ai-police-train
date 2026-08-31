from __future__ import annotations

import re
from typing import Any

from ai_workflow_service.contracts import CaseWorld, Fact
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.domain.case_import_quality import fact_quality

COURT_NOISE_MARKERS = (
    "本院认为", "判决如下", "裁定如下", "经审理查明", "审理查明",
    "公诉机关", "公诉人", "辩护人", "辩护意见", "审判员", "书记员",
    "人民法院", "定罪", "量刑", "构成要件", "如不服本判决",
    "法院认为", "判决书", "刑事判决", "另案处理", "起诉书",
    "DOCX", "页眉页脚", "OCR", "文档识别结果", "图片 OCR",
)

STORY_EVENT_MARKERS = (
    "持", "拿", "携带", "组织", "召集", "通知", "纠集", "带领", "参与", "实施",
    "殴打", "击打", "追赶", "阻拦", "劝阻", "报警", "报案", "送医", "救助",
    "受伤", "损伤", "轻伤", "重伤", "被打", "被砍", "逃离", "离开", "到场",
    "赶到", "种植", "毁坏", "争吵", "冲突", "推搡", "砍", "砸", "拔",
    "挖", "堵", "损坏", "破坏", "威胁", "聚集",
)

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[，。！？、；：,.!?;:\"'“”‘’（）()【】\[\]《》<>·…—\-]+")

CHUNK_TARGET_CHARS = 1400
CHUNK_MAX_CHARS = 2200
MAX_CHUNKS = 12
MAX_FACTS = 64


def _is_court_noise(text: str) -> bool:
    return any(marker in text for marker in COURT_NOISE_MARKERS)


def _is_story_event(text: str) -> bool:
    return any(marker in text for marker in STORY_EVENT_MARKERS)


def _normalize_fact_key(text: str) -> str:
    value = _SPACE_RE.sub("", str(text or "").strip().lower())
    return _PUNCT_RE.sub("", value)


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
    def _normalize_relationships(value: Any) -> list[dict]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict] = []
        for item in rows:
            if isinstance(item, dict):
                person1 = str(item.get("person1") or item.get("from") or item.get("source") or item.get("left") or "").strip()
                person2 = str(item.get("person2") or item.get("to") or item.get("target") or item.get("right") or "").strip()
                relation = str(item.get("relation") or item.get("relationship") or item.get("type") or item.get("desc") or "").strip()
                if person1 or person2 or relation:
                    normalized.append({
                        "person1": person1,
                        "person2": person2,
                        "relation": relation or "相关",
                    })
                continue
        return normalized[:32]

    @staticmethod
    def _normalize_timeline(value: Any) -> list[dict]:
        rows = value if isinstance(value, list) else []
        normalized: list[dict] = []
        for item in rows:
            if isinstance(item, dict):
                event = str(item.get("event") or item.get("content") or item.get("description") or item.get("summary") or "").strip()
                time_text = str(item.get("time") or item.get("when") or item.get("date") or "").strip()
                if event or time_text:
                    normalized.append({"time": time_text, "event": event or time_text})
                continue
            text = str(item or "").strip()
            if text:
                normalized.append({"time": "", "event": text})
        return normalized[:48]

    @staticmethod
    def _split_story_chunks(complete_story: str) -> list[dict[str, Any]]:
        """Split complete story by ## sections, then pack into bounded chunks covering full text."""
        text = str(complete_story or "").strip()
        if not text:
            return []

        sections: list[tuple[str, str]] = []
        if re.search(r"(?m)^##\s+", text):
            parts = re.split(r"(?m)^##\s+", text)
            preamble = (parts[0] or "").strip()
            if preamble:
                clean_preamble = re.sub(r"^#\s*案件完整剧情\s*", "", preamble).strip()
                if clean_preamble and len(clean_preamble) >= 40:
                    sections.append(("开篇", clean_preamble))
            for part in parts[1:]:
                lines = part.splitlines()
                title = (lines[0].strip() if lines else "章节") or "章节"
                body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
                if body:
                    sections.append((title, body))
                elif title and len(title) >= 20:
                    sections.append(("段落", title))
        else:
            paragraphs = [
                paragraph.strip().lstrip("# ")
                for paragraph in re.split(r"\n{2,}", text)
                if paragraph.strip() and not paragraph.strip().startswith(("# 案件完整剧情", "说明：", "【文档"))
            ]
            if not paragraphs:
                paragraphs = [text]
            for index, paragraph in enumerate(paragraphs, start=1):
                sections.append((f"段{index}", paragraph))

        raw_chunks: list[dict[str, Any]] = []
        for title, body in sections:
            if _is_court_noise(body) and len(body) < 200:
                continue
            if len(body) <= CHUNK_MAX_CHARS:
                raw_chunks.append({"title": title, "text": body})
                continue
            # Oversized section: split by sentences while keeping order.
            sentences = [s.strip() for s in re.split(r"(?<=[。！？；])|\n+", body) if s.strip()]
            buf: list[str] = []
            buf_len = 0
            part_no = 1
            for sentence in sentences:
                if buf and buf_len + len(sentence) > CHUNK_TARGET_CHARS:
                    raw_chunks.append({"title": f"{title}-{part_no}", "text": "".join(buf)})
                    part_no += 1
                    buf = [sentence]
                    buf_len = len(sentence)
                else:
                    buf.append(sentence)
                    buf_len += len(sentence)
            if buf:
                raw_chunks.append({"title": f"{title}-{part_no}" if part_no > 1 else title, "text": "".join(buf)})

        if not raw_chunks:
            return [{"index": 1, "title": "全文", "text": text[:CHUNK_MAX_CHARS]}]

        packed = raw_chunks
        if len(packed) > MAX_CHUNKS:
            # Evenly merge into MAX_CHUNKS buckets to keep full coverage.
            bucket_size = (len(packed) + MAX_CHUNKS - 1) // MAX_CHUNKS
            merged: list[dict[str, Any]] = []
            for start in range(0, len(packed), bucket_size):
                group = packed[start:start + bucket_size]
                merged.append({
                    "title": "+".join(item["title"] for item in group)[:40],
                    "text": "\n".join(item["text"] for item in group),
                })
            packed = merged[:MAX_CHUNKS]

        return [
            {"index": index, "title": item["title"], "text": item["text"]}
            for index, item in enumerate(packed, start=1)
        ]

    @staticmethod
    def _fallback_facts_from_chunk(chunk_text: str) -> list[dict]:
        rows = []
        sentences = [
            sentence.strip().lstrip("# ")
            for sentence in re.split(r"(?<=[。！？；])|\n+", chunk_text)
            if sentence.strip()
        ]
        for content in sentences:
            if _is_court_noise(content) or content.startswith(("案件完整剧情", "证据如下", "说明：", "【文档")):
                continue
            if 12 <= len(content) <= 280 and (_is_story_event(content) or len(rows) < 4):
                rows.append({
                    "content": content,
                    "source_quote": content,
                    "fact_type": "行为" if _is_story_event(content) else "事实",
                    "status": "source_supported",
                })
            if len(rows) >= 8:
                break
        return rows

    def _extract_facts_from_chunk(self, chunk: dict[str, Any]) -> dict:
        title = str(chunk.get("title") or f"块{chunk.get('index')}")
        body = str(chunk.get("text") or "")
        try:
            return self.llm.complete_json(
                system=(
                    "你是案件事实账本编辑。输入是完整案件剧情的一个分块，请抽出本块内的原子事实。"
                    "每条事实必须是单一行为、陈述、证据、伤情或处置；不要把整块概括成一条。"
                    "只依据本块正文，不得虚构块外情节；人名、时间、地点必须来自本块。"
                    "禁止写入法院审理、辩护意见、定罪量刑、裁判说理、诉讼程序套话，以及文档识别/OCR 说明。"
                    "只输出 JSON：facts,timeline,locations,relationships。"
                    "facts 含 content、source_quote、fact_type、status、known_by、unknown_by、secret；"
                    "source_quote 必须尽量摘自本块原文；known_by 只能写本块真实出现的人名。"
                    "relationships 必须是对象数组，每项含 person1,person2,relation；禁止输出纯字符串名单。"
                    "timeline 必须是对象数组，每项含 time,event。"
                    "本块可输出 1-8 条事实；若本块几乎无可训练事实，可返回空 facts。"
                ),
                user=f"【分块标题】{title}\n【分块正文】\n{body}",
                max_tokens=3500,
                max_attempts=1,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            return {}

    def _build_case_summary(self, complete_story: str, facts: list[Fact]) -> dict:
        fact_lines = "；".join(fact.content for fact in facts[:18])
        # Keep prompt short: head + middle + tail samples + fact bullets.
        head = complete_story[:900]
        mid_start = max(0, len(complete_story) // 2 - 450)
        mid = complete_story[mid_start:mid_start + 900]
        tail = complete_story[-900:] if len(complete_story) > 900 else ""
        try:
            return self.llm.complete_json(
                system=(
                    "你是案件摘要编辑。根据完整剧情抽样与已抽事实，输出全案摘要。"
                    "只输出 JSON：title,case_type,summary。"
                    "summary 为 80-200 字，必须覆盖起因、冲突、伤情/损失、报警与结果，不得只写开头。"
                    "禁止法院裁判套话与 OCR 说明。"
                ),
                user=(
                    f"【剧情开头】\n{head}\n\n【剧情中段】\n{mid}\n\n【剧情结尾】\n{tail}\n\n"
                    f"【已抽事实要点】\n{fact_lines or '（无）'}"
                ),
                max_tokens=800,
                max_attempts=1,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            return {}

    def execute(self, case_id: str, complete_story: str) -> tuple[CaseWorld, dict]:
        chunks = self._split_story_chunks(complete_story)
        raw_facts: list[dict] = []
        timeline_rows: list[Any] = []
        location_rows: list[Any] = []
        relationship_rows: list[Any] = []
        chunk_stats: list[dict[str, Any]] = []

        for chunk in chunks:
            result = self._extract_facts_from_chunk(chunk)
            chunk_facts = result.get("facts") if isinstance(result.get("facts"), list) else []
            if len(chunk_facts) < 1:
                chunk_facts = self._fallback_facts_from_chunk(str(chunk.get("text") or ""))
            for item in chunk_facts:
                if isinstance(item, dict):
                    item = {**item, "chunk_index": chunk["index"], "chunk_title": chunk["title"]}
                    raw_facts.append(item)
            if isinstance(result.get("timeline"), list):
                timeline_rows.extend(result["timeline"])
            if isinstance(result.get("locations"), list):
                location_rows.extend(result["locations"])
            if isinstance(result.get("relationships"), list):
                relationship_rows.extend(result["relationships"])
            chunk_stats.append({
                "index": chunk["index"],
                "title": chunk["title"],
                "chars": len(str(chunk.get("text") or "")),
                "fact_count": len(chunk_facts),
            })

        expected_minimum = 1 if len(complete_story) < 500 else min(18, max(6, len(complete_story) // 800))
        if len(raw_facts) < expected_minimum:
            raw_facts = [*raw_facts, *self._fallback_facts_from_chunk(complete_story)]

        facts: list[Fact] = []
        used_fact_ids: set[str] = set()
        used_keys: set[str] = set()
        next_fact_number = 1
        for index, raw in enumerate(raw_facts):
            item = raw if isinstance(raw, dict) else {}
            content = str(item.get("content") or item.get("fact") or "").strip()
            key = _normalize_fact_key(content)
            if not content or not key or key in used_keys or _is_court_noise(content):
                continue
            if content.startswith(("说明：", "【文档", "--- 块")):
                continue
            # Near-duplicate: skip if an existing fact already contains this key or vice versa at high overlap.
            if any(key in existing or existing in key for existing in used_keys if min(len(key), len(existing)) >= 12):
                continue
            proposed_id = str(item.get("fact_id") or f"F{next_fact_number:03d}").strip()
            fact_id = proposed_id
            while not fact_id or fact_id in used_fact_ids:
                fact_id = f"F{next_fact_number:03d}"
                next_fact_number += 1
            used_fact_ids.add(fact_id)
            used_keys.add(key)
            known_by = [
                str(v).strip()
                for v in item.get("known_by") or []
                if str(v).strip()
                and not _is_court_noise(str(v))
                and len(str(v).strip()) <= 12
                and not any(marker in str(v) for marker in ("未明确", "证言", "辨认", "材料", "通过"))
            ]
            facts.append(Fact(
                fact_id=fact_id,
                content=content,
                source=str(item.get("source") or "完整剧情"),
                known_by=known_by,
                unknown_by=[str(v) for v in item.get("unknown_by") or []],
                secret=bool(item.get("secret", False)),
                source_refs=_source_refs(item, complete_story, content),
                fact_type=str(item.get("fact_type") or ("行为" if _is_story_event(content) else "事实")),
                status=str(item.get("status") or "claimed"),
            ))
            if len(facts) >= MAX_FACTS:
                break

        if not facts:
            preview = complete_story[:500].strip() or "案件事实待补充"
            facts = [Fact(
                fact_id="F001",
                content=preview,
                source="完整剧情",
                source_refs=[{
                    "source_id": "complete-story",
                    "start": 0,
                    "end": min(len(complete_story), 500),
                    "summary": preview[:180],
                }],
            )]

        meta = self._build_case_summary(complete_story, facts)
        summary = str(meta.get("summary") or "").strip()
        if not summary or len(summary) < 40:
            summary = "；".join(fact.content for fact in facts[:6])[:300]

        world = CaseWorld(
            case_id=case_id,
            title=str(meta.get("title") or "案件导入"),
            case_type=str(meta.get("case_type") or "其他"),
            summary=summary,
            facts=facts,
            timeline=self._normalize_timeline(timeline_rows),
            locations=[
                str(value.get("name") or value.get("location") or value.get("address") or "").strip()
                if isinstance(value, dict) else str(value).strip()
                for value in location_rows
                if (isinstance(value, dict) and str(value.get("name") or value.get("location") or value.get("address") or "").strip())
                or (not isinstance(value, dict) and str(value).strip())
            ],
            relationships=self._normalize_relationships(relationship_rows),
        )
        quality = fact_quality(world.facts, complete_story)
        quality["complete_story_chars"] = len(complete_story)
        quality["chunk_count"] = len(chunks)
        quality["chunks"] = chunk_stats
        quality["method"] = "section_chunk_extract_merge"
        return world, quality
