"""DeepSeek case information completion officer — field-targeted fill from source text."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Optional

from .llm_provider import (
    create_case_completion_chat_completion,
    extract_json_payload,
    extract_message_text,
    get_case_completion_model,
    get_case_completion_provider,
)
from .workflow_service import CASE_TYPE_OPTIONS, workflow_service

CASE_OFFICER_ROLE = "案件信息补全专员（DeepSeek）"

FIELD_CATALOG = {
    "case_basic": {
        "label": "案件基础信息",
        "fields": [
            "case_name",
            "case_type",
            "case_background",
            "full_narrative",
            "criminal_process",
            "main_culprit",
            "source_classification",
            "dispatch_brief_suggestion",
            "first_impression_suggestion",
            "transcript_summary",
        ],
    },
    "fact_sheet": {
        "label": "事实要素",
        "fields": ["fact_sheet.case_time", "fact_sheet.case_location", "fact_sheet.report_time", "fact_sheet.timeline", "fact_sheet.relationships"],
    },
    "lists": {
        "label": "案情要点列表",
        "fields": ["conflict_points", "key_facts", "hidden_info", "evidence_points", "inconsistencies"],
    },
    "persons": {
        "label": "人物与训练人设",
        "fields": [
            "persons[].name",
            "persons[].role",
            "persons[].role_type",
            "persons[].status",
            "persons[].behavior_archetype",
            "persons[].police_attitude",
            "persons[].current_goal",
            "persons[].core_concern",
            "persons[].trigger_points",
            "persons[].calming_points",
            "persons[].init_emotion",
            "persons[].init_trust",
            "persons[].knows_facts",
            "persons[].does_not_know",
            "persons[].hidden_truths",
            "persons[].interaction_style",
            "persons[].personality",
            "persons[].speaking_style",
        ],
    },
    "scenes": {
        "label": "训练场景",
        "fields": [
            "scenes[].scene_name",
            "scenes[].scene_description",
            "scenes[].difficulty",
            "scenes[].dispatch_brief",
            "scenes[].first_impression",
            "scenes[].roles",
            "scenes[].stages[].stage_name",
            "scenes[].stages[].stage_goal",
            "scenes[].stages[].assessment_points",
            "scenes[].stages[].action_catalog",
        ],
    },
}

CASE_COMPLETION_PROMPT = f"""你是公安警情训练平台的「{CASE_OFFICER_ROLE}」。

你的唯一任务：根据【案件原文】为【待补全题目】在原文中查找依据并填写，输出训练平台可用的结构化 JSON。

工作方法（必须遵守）：
1. 先阅读【案件原文】，再对照【当前表单已有内容】和【待补全题目清单】，逐题到原文里找依据。
2. 只能使用原文中明确出现或可合理归纳的信息；找不到依据时，该题写“未明确”、空数组或空字符串，并在 completion_warnings 说明。
3. 不得编造新人物、新地点、新证据、新动机；不得把推测写成事实。
4. 案件类型只能从以下列表选择最接近的一项：{json.dumps(CASE_TYPE_OPTIONS, ensure_ascii=False)}
5. person status 只能是：正常、受伤可交流、昏迷、重伤无法交流、死亡。
6. dispatch_brief_suggestion / dispatch_brief 只写接警时可知信息；first_impression 只写到场第一眼可观察信息。
7. persons 中 name 只能是纯人名，不要带“称、表示、供述”等后缀。
8. 若【当前表单已有内容】某字段已有有效值且 mode=fill_gaps，不要覆盖，只在 field_evidence 标注 skipped。
9. parse_engine 固定为 "ai"；completion_engine 固定为 "deepseek-case-officer"。

输出 JSON 结构（与案件解析一致，并增加补全追踪字段）：
{{
  "completion_engine": "deepseek-case-officer",
  "completion_agent": "{CASE_OFFICER_ROLE}",
  "completion_model": "",
  "filled_field_paths": ["case_background", "persons[0].behavior_archetype"],
  "field_evidence": {{"case_background": "原文摘录或段落说明"}},
  "completion_warnings": ["哪些题在原文中找不到依据"],
  "parse_engine": "ai",
  "case_name": "",
  "case_type": "",
  "case_background": "",
  "fact_sheet": {{}},
  "persons": [],
  "conflict_points": [],
  "key_facts": [],
  "hidden_info": [],
  "evidence_points": [],
  "inconsistencies": [],
  "dispatch_brief_suggestion": "",
  "first_impression_suggestion": "",
  "transcript_summary": "",
  "parse_warnings": []
}}

只输出一个合法 JSON 对象，不要 markdown。"""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        clean = value.strip()
        return not clean or clean in {"未明确", "未提取到案件背景", "解析失败", "待核实", "暂无"}
    if isinstance(value, list):
        return len(value) == 0
    if isinstance(value, dict):
        return len(value) == 0
    return False


def _list_field_paths(groups: Optional[list[str]]) -> list[str]:
    if not groups:
        paths: list[str] = []
        for group in FIELD_CATALOG.values():
            paths.extend(group["fields"])
        return paths
    paths: list[str] = []
    for group_name in groups:
        entry = FIELD_CATALOG.get(group_name)
        if entry:
            paths.extend(entry["fields"])
    return paths


def _build_target_field_specs(target_groups: Optional[list[str]], mode: str) -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for path in _list_field_paths(target_groups):
        specs.append({"path": path, "instruction": "到原文查找依据后填写；无依据则留空或写未明确"})
    if mode == "fill_gaps":
        for item in specs:
            item["instruction"] += "；若当前表单该题已有有效值则不要覆盖"
    return specs


def _merge_case_info(
    existing: Optional[dict[str, Any]],
    completed: dict[str, Any],
    *,
    mode: str,
) -> tuple[dict[str, Any], list[str]]:
    base = deepcopy(existing) if isinstance(existing, dict) else {}
    filled: list[str] = []

    def merge_scalar(key: str):
        new_value = completed.get(key)
        if _is_empty_value(new_value):
            return
        if mode == "fill_gaps" and not _is_empty_value(base.get(key)):
            return
        if base.get(key) != new_value:
            filled.append(key)
        base[key] = new_value

    for key in (
        "case_name",
        "case_type",
        "case_background",
        "full_narrative",
        "criminal_process",
        "main_culprit",
        "source_classification",
        "dispatch_brief_suggestion",
        "first_impression_suggestion",
        "transcript_summary",
    ):
        merge_scalar(key)

    for key in ("conflict_points", "key_facts", "hidden_info", "evidence_points", "inconsistencies", "parse_warnings"):
        new_value = completed.get(key)
        if not isinstance(new_value, list) or not new_value:
            continue
        if mode == "fill_gaps" and isinstance(base.get(key), list) and base.get(key):
            continue
        base[key] = new_value
        filled.append(key)

    new_fact_sheet = completed.get("fact_sheet")
    if isinstance(new_fact_sheet, dict) and new_fact_sheet:
        current_sheet = base.get("fact_sheet") if isinstance(base.get("fact_sheet"), dict) else {}
        merged_sheet = dict(current_sheet)
        for sheet_key, sheet_value in new_fact_sheet.items():
            if _is_empty_value(sheet_value):
                continue
            if mode == "fill_gaps" and not _is_empty_value(merged_sheet.get(sheet_key)):
                continue
            merged_sheet[sheet_key] = sheet_value
            filled.append(f"fact_sheet.{sheet_key}")
        base["fact_sheet"] = merged_sheet

    new_persons = completed.get("persons")
    if isinstance(new_persons, list) and new_persons:
        if mode == "fill_gaps" and isinstance(base.get("persons"), list) and base.get("persons"):
            by_name = {str(item.get("name") or "").strip(): item for item in base["persons"] if isinstance(item, dict)}
            for person in new_persons:
                if not isinstance(person, dict):
                    continue
                name = str(person.get("name") or "").strip()
                if not name:
                    continue
                if name not in by_name:
                    by_name[name] = person
                    filled.append(f"persons[+].{name}")
                    continue
                target = by_name[name]
                for key, value in person.items():
                    if _is_empty_value(value):
                        continue
                    if not _is_empty_value(target.get(key)):
                        continue
                    target[key] = value
                    filled.append(f"persons[{name}].{key}")
            base["persons"] = list(by_name.values())
        else:
            base["persons"] = new_persons
            filled.append("persons")

    return base, filled


def complete_case_information(
    *,
    source_text: str,
    source_mode: str = "plain_case",
    existing_case: Optional[dict[str, Any]] = None,
    mode: str = "fill_gaps",
    target_groups: Optional[list[str]] = None,
    include_scenes: bool = True,
    source_meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    text = _text(source_text)
    if not text:
        raise ValueError("案件原文不能为空")

    target_groups = target_groups or list(FIELD_CATALOG.keys())
    if include_scenes and "scenes" not in target_groups:
        target_groups = [*target_groups, "scenes"]

    existing_snapshot = existing_case if isinstance(existing_case, dict) else {}
    target_specs = _build_target_field_specs(target_groups, mode)

    user_payload = {
        "mode": mode,
        "source_mode": source_mode,
        "target_field_specs": target_specs,
        "current_form": existing_snapshot,
        "source_text": text[:12000],
    }
    if source_meta:
        user_payload["source_meta"] = source_meta

    messages = [
        {"role": "system", "content": CASE_COMPLETION_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    ai_payload: dict[str, Any] = {}
    completion_engine = "heuristic"
    try:
        response = create_case_completion_chat_completion(messages=messages, temperature=0.2, max_tokens=8000)
        raw = extract_message_text(response) or ""
        parsed = extract_json_payload(raw) or {}
        if isinstance(parsed, dict) and parsed:
            ai_payload = parsed
            completion_engine = "deepseek-case-officer"
    except Exception as exc:
        ai_payload = {"completion_warnings": [f"信息补全专员调用失败：{exc}"]}

    if completion_engine != "deepseek-case-officer":
        parsed = workflow_service.parse_case_text(text, source_mode=source_mode, source_meta=source_meta)
        ai_payload = parsed
        ai_payload["completion_warnings"] = [
            *(ai_payload.get("completion_warnings") or []),
            "未使用 DeepSeek 信息补全专员，已切换为规则/通用解析兜底，请人工复核。",
        ]

    normalized = workflow_service._normalize_parsed_case(text, ai_payload, source_mode, source_meta)
    normalized["completion_engine"] = completion_engine
    normalized["completion_agent"] = CASE_OFFICER_ROLE
    normalized["completion_model"] = get_case_completion_model()
    normalized["completion_provider"] = get_case_completion_provider()
    normalized["filled_field_paths"] = ai_payload.get("filled_field_paths") or []
    normalized["field_evidence"] = ai_payload.get("field_evidence") if isinstance(ai_payload.get("field_evidence"), dict) else {}

    merged_case, merge_filled = _merge_case_info(existing_snapshot, normalized, mode=mode)
    if merge_filled:
        merged_paths = list(dict.fromkeys([*normalized.get("filled_field_paths", []), *merge_filled]))
        merged_case["filled_field_paths"] = merged_paths
    else:
        merged_case["filled_field_paths"] = normalized.get("filled_field_paths") or []

    warnings = list(dict.fromkeys([*(merged_case.get("completion_warnings") or []), *(normalized.get("parse_warnings") or [])]))
    merged_case["completion_warnings"] = warnings
    merged_case["parse_warnings"] = warnings
    merged_case["parse_engine"] = normalized.get("parse_engine") or "ai"
    merged_case["rawText"] = text
    merged_case["original_content"] = text

    scenes_payload: dict[str, Any] = {}
    if include_scenes and (mode == "full" or "scenes" in (target_groups or [])):
        scenes_payload = workflow_service.generate_scenes(merged_case, use_case_completion_officer=True)

    return {
        "case_info": merged_case,
        "scenes": scenes_payload.get("scenes") or [],
        "scene_generation_mode": scenes_payload.get("scene_generation_mode") or "",
        "scene_generation_warning": scenes_payload.get("scene_generation_warning") or "",
        "completion_engine": completion_engine,
        "completion_agent": CASE_OFFICER_ROLE,
        "completion_model": get_case_completion_model(),
        "completion_provider": get_case_completion_provider(),
        "filled_field_paths": merged_case.get("filled_field_paths") or [],
        "field_evidence": merged_case.get("field_evidence") or {},
        "completion_warnings": merged_case.get("completion_warnings") or [],
        "field_catalog": FIELD_CATALOG,
        "target_groups": target_groups,
    }


def list_field_catalog() -> dict[str, Any]:
    return {
        "agent": CASE_OFFICER_ROLE,
        "provider": get_case_completion_provider(),
        "model": get_case_completion_model(),
        "groups": FIELD_CATALOG,
    }
