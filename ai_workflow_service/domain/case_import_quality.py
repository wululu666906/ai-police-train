from __future__ import annotations

import re
from typing import Any


EVIDENCE_MARKERS = (
    "证言", "供述", "陈述", "鉴定", "勘验", "辨认", "物证", "书证",
    "视频", "照片", "病历", "伤情", "报警", "到案", "现场",
)
POLICE_ACTION_MARKERS = (
    "接警", "出警", "核实", "询问", "处置", "控制", "疏散", "隔离",
    "救助", "取证", "记录", "告知", "移交", "增援", "风险",
)
NON_POLICE_GOAL_MARKERS = (
    "检察官", "公诉", "起诉意见", "辩护", "法庭", "定罪", "量刑",
    "构成要件", "主从犯", "审判", "裁判",
)


def text_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def story_quality(source_text: str, story: str) -> dict[str, Any]:
    source = str(source_text or "").strip()
    narrative = str(story or "").strip()
    ratio = round(len(narrative) / max(len(source), 1), 4)
    source_markers = [marker for marker in EVIDENCE_MARKERS if marker in source]
    covered_markers = [marker for marker in source_markers if marker in narrative]
    source_numbers = set(re.findall(r"\d{1,4}(?:年|月|日|时|分|名|人|次|号)?", source))
    covered_numbers = {value for value in source_numbers if value in narrative}
    minimum_chars = min(len(source), max(800, int(len(source) * 0.15))) if len(source) > 3000 else min(len(source), max(600, int(len(source) * 0.45)))
    has_chapters = narrative.count("## ") >= 2
    looks_like_source_paste = narrative.startswith("# 案件完整剧情") and "经审理查明" in narrative and narrative.count("## ") < 2
    fail_reasons: list[str] = []
    if not narrative:
        fail_reasons.append("empty_story")
    if narrative and not has_chapters:
        fail_reasons.append("missing_chapter_headings")
    if looks_like_source_paste:
        fail_reasons.append("looks_like_source_paste")
    if narrative and len(narrative) < minimum_chars:
        fail_reasons.append("too_short")
    if source_markers and len(covered_markers) / len(source_markers) < 0.55:
        fail_reasons.append("evidence_coverage_low")
    if source_numbers and len(covered_numbers) / len(source_numbers) < 0.45:
        fail_reasons.append("number_coverage_low")
    sufficient = bool(
        narrative
        and has_chapters
        and not looks_like_source_paste
        and len(narrative) >= minimum_chars
        and (not source_markers or len(covered_markers) / len(source_markers) >= 0.55)
        and (not source_numbers or len(covered_numbers) / len(source_numbers) >= 0.45)
    )
    return {
        "source_chars": len(source),
        "story_chars": len(narrative),
        "compression_ratio": ratio,
        "minimum_story_chars": minimum_chars,
        "source_evidence_markers": source_markers,
        "covered_evidence_markers": covered_markers,
        "missing_evidence_markers": [item for item in source_markers if item not in covered_markers],
        "number_coverage": round(len(covered_numbers) / len(source_numbers), 4) if source_numbers else 1.0,
        "sufficient": sufficient,
        "fail_reasons": fail_reasons,
        "chapter_count": narrative.count("## "),
    }


def fact_quality(facts: list[Any], story: str) -> dict[str, Any]:
    valid = [fact for fact in facts if str(getattr(fact, "content", "")).strip()]
    sourced = [fact for fact in valid if getattr(fact, "source_refs", None)]
    categories = sorted({str(getattr(fact, "fact_type", "") or "其他") for fact in valid})
    expected_minimum = 1 if len(story) < 500 else min(18, max(6, len(story) // 500))
    return {
        "fact_count": len(valid),
        "expected_minimum": expected_minimum,
        "source_coverage": round(len(sourced) / len(valid), 4) if valid else 0.0,
        "categories": categories,
        "sufficient": len(valid) >= expected_minimum and (not valid or len(sourced) / len(valid) >= 0.8),
    }


def memory_quality(persons: list[Any], memories: list[dict[str, Any]]) -> dict[str, Any]:
    memory_by_id = {str(item.get("person_id")): item for item in memories}
    counts = {
        str(getattr(person, "person_id", "")): len(memory_by_id.get(str(getattr(person, "person_id", "")), {}).get("role_memories") or [])
        for person in persons
    }
    interactive = [person for person in persons if bool(getattr(person, "speakable", True))]
    expected_counts = {
        str(getattr(person, "person_id", "")): min(3, max(1, len(getattr(person, "facts_known", None) or [])))
        for person in interactive
    }
    covered = [
        person for person in interactive
        if counts.get(str(getattr(person, "person_id", "")), 0)
        >= expected_counts.get(str(getattr(person, "person_id", "")), 1)
    ]
    return {
        "person_count": len(persons),
        "interactive_person_count": len(interactive),
        "memory_count": sum(counts.values()),
        "memory_counts": counts,
        "expected_memory_counts": expected_counts,
        "interactive_memory_coverage": round(len(covered) / len(interactive), 4) if interactive else 1.0,
        "sufficient": bool(interactive) and len(covered) == len(interactive),
    }


def is_police_training_goal(value: Any) -> bool:
    goal = str(value or "").strip()
    return bool(goal and any(marker in goal for marker in POLICE_ACTION_MARKERS) and not any(marker in goal for marker in NON_POLICE_GOAL_MARKERS))
