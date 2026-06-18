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
            "persons[].role_type",
            "persons[].status",
            "persons[].behavior_archetype",
            "persons[].opening_preset",
            "persons[].current_goal",
            "persons[].core_concern",
            "persons[].trigger_points",
            "persons[].calming_points",
            "persons[].cannot_answer",
            "persons[].boundary_primary",
            "persons[].boundary_secondary",
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
            "scenes[].assessment_points",
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
6. dispatch_brief_suggestion 只写接警时可知信息；first_impression_suggestion 只写到场第一眼可观察信息。
7. persons 中 name 只能是纯人名，不要带”称、表示、供述”等后缀。
8. 同一角色在不同场景中必须使用完全相同的 name 作为唯一标识，不得出现”张三”在场景A、”张三审讯”在场景B的情况。
9. 严格避免将地名（某某村、东风路）、抽象名词（证言、陈述、纠纷）、角色称谓（嫌疑人、报警人、邻居）等非人名词当作 name 输出。
8. 若【当前表单已有内容】某字段已有有效值且 mode=fill_gaps，不要覆盖，只在 field_evidence 标注 skipped；若 mode=full 则全部重新填写。
9. parse_engine 固定为 “ai”；completion_engine 固定为 “deepseek-case-officer”。
10. 各类要点（conflict_points / key_facts / hidden_info / evidence_points / inconsistencies）的区别：
    - conflict_points：当事人之间在核心事实上相互矛盾的陈述或版本分歧。
    - key_facts：办案决策最关键的客观事实，优先摘录时间、地点、人物、行为、结果五要素。
    - hidden_info：原文暗示但未明确交代、需要后续询问才能确认的信息缺口。
    - evidence_points：原文中出现的物证、书证、视听资料、目击线索等客观证据。
    - inconsistencies：同一人在不同时间或不同人之间在细节上的前后不一致，区别于 conflict_points 的”核心矛盾”。
11. fact_sheet 子字段：case_time（案发时间）、case_location（案发地点）、report_time（报案时间）、timeline（时间线列表）、relationships（人物关系说明列表）。
12. persons 中每个对象应包含 name、role_type（当事人/报警人/目击者/嫌疑人等）、status、behavior_archetype（行为原型）、opening_preset（开场白模板）、current_goal（当前诉求）、core_concern（核心顾虑）、trigger_points（情绪触发点列表）、calming_points（可安抚点列表）、cannot_answer（角色不能回答的问题列表）、boundary_primary（不可配合的行为底线）、boundary_secondary（次要边界）。
13. source_classification 一般写”普通案件文本”，如果是庭审记录则写”庭审记录”，如果是报警记录则写”报警记录”。
14. full_narrative 是完整叙事重述（按时间顺序）；criminal_process 是重点摘取违法/犯罪过程段落；transcript_summary 用”谁、何时、何地、发生了什么、当前争议点/风险点”格式概括。
15. mode=fill_gaps 时仅补缺、不覆盖已有值；mode=full 时全部重新生成。
16. case_background 必须是可直接展示给教官复核的案件背景，优先写 120-300 字，交代警情来源、时间、地点、人物、起因、已经发生的行为、后果、当前风险/争议；信息不足时也要基于原文客观概括，并把缺口写入 completion_warnings。
17. fact_sheet.timeline 至少尝试抽取 2-6 条时间线，按“时间/阶段 + 事件”短句输出；relationships 至少尝试提炼人物关系或“关系未明确但存在冲突/接触”的说明。
18. 若输出长度受限，优先保证 case_name、case_type、case_background、fact_sheet、persons、key_facts、transcript_summary 这些字段完整，再输出其他字段。

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
  "full_narrative": "",
  "criminal_process": "",
  "main_culprit": "",
  "source_classification": "普通案件文本",
  "dispatch_brief_suggestion": "",
  "first_impression_suggestion": "",
  "transcript_summary": "",
  "fact_sheet": {{
    "case_time": "",
    "case_location": "",
    "report_time": "",
    "timeline": [],
    "relationships": []
  }},
  "persons": [
    {{
      "name": "张某",
      "role_type": "当事人/报警人/目击者/嫌疑人",
      "status": "正常",
      "behavior_archetype": "行为原型名称",
      "opening_preset": "开场白模板文字",
      "current_goal": "当前核心诉求",
      "core_concern": "核心顾虑/不愿说的事",
      "trigger_points": ["可能刺激情绪的话"],
      "calming_points": ["能缓和情绪的方式"],
      "cannot_answer": ["此角色不会回答的问题"],
      "boundary_primary": "不可配合的行为底线",
      "boundary_secondary": "次要边界/可突破条件"
    }}
  ],
  "conflict_points": [],
  "key_facts": [],
  "hidden_info": [],
  "evidence_points": [],
  "inconsistencies": [],
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


def _looks_like_case_payload(payload: Any) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    for key in (
        "case_name",
        "case_type",
        "case_background",
        "full_narrative",
        "criminal_process",
        "main_culprit",
        "dispatch_brief_suggestion",
        "first_impression_suggestion",
        "transcript_summary",
    ):
        if not _is_empty_value(payload.get(key)):
            return True
    for key in ("persons", "conflict_points", "key_facts", "hidden_info", "evidence_points", "inconsistencies"):
        if isinstance(payload.get(key), list) and payload.get(key):
            return True
    fact_sheet = payload.get("fact_sheet")
    if isinstance(fact_sheet, dict):
        return any(not _is_empty_value(value) for value in fact_sheet.values())
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
        new_persons = workflow_service.standardize_person_records(new_persons)
        if mode == "fill_gaps" and isinstance(base.get("persons"), list) and base.get("persons"):
            existing_persons = workflow_service.standardize_person_records(base.get("persons"))
            by_name = {str(item.get("name") or "").strip(): item for item in existing_persons if isinstance(item, dict)}
            for person in new_persons:
                if not isinstance(person, dict):
                    continue
                name = workflow_service._normalize_person_name(person.get("name"))
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
    elif isinstance(base.get("persons"), list):
        base["persons"] = workflow_service.standardize_person_records(base.get("persons"))

    if isinstance(base.get("scenes"), list) and isinstance(base.get("persons"), list):
        for scene in base["scenes"]:
            if not isinstance(scene, dict):
                continue
            roles = scene.get("roles") or scene.get("role_names")
            canonical_roles = workflow_service.canonicalize_role_names(roles, base["persons"])
            if canonical_roles:
                scene["roles"] = canonical_roles

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
    # Extract character names from source text for accurate constraint
    extracted_names = workflow_service.extract_case_person_names(text)

    name_constraint = ""
    if extracted_names:
        name_constraint = (
            "\n\n【已在文本中识别到以下角色名】"
            + json.dumps(extracted_names, ensure_ascii=False)
            + "\npersons 中 name 必须严格从该名单选取，不得编造不在名单中的新名字。"
            + "name 只能是纯人名，不得追加“嫌疑人/证人/审讯阶段/现场阶段”等身份或场景后缀。"
            + "角色身份只能写入 role_type，场景状态只能写入场景或阶段字段，不得污染 name。"
            + "同一角色在不同场景中必须使用完全相同的 name。"
        )


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
        "output_quality_requirements": [
            "case_background 不得只写未明确或复制标题，至少概括案由、人物、时间地点、经过、后果/风险中的可得信息。",
            "fact_sheet.timeline 和 relationships 能抽则抽，不能抽取时在 completion_warnings 写明缺口。",
            "persons 不只列姓名，还要尽量补 role_type/status/current_goal/core_concern/trigger_points/calming_points。",
            "所有字段只能来自原文或合理归纳，推测必须以待核实语气呈现。",
        ],
    }
    if source_meta:
        user_payload["source_meta"] = source_meta

    enhanced_prompt = CASE_COMPLETION_PROMPT + name_constraint
    messages = [
        {"role": "system", "content": enhanced_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    ai_payload: dict[str, Any] = {}
    completion_engine = "heuristic"
    completion_warnings: list[str] = []
    try:
        response = create_case_completion_chat_completion(messages=messages, temperature=0.1, max_tokens=8000)
        raw = extract_message_text(response) or ""
        parsed = extract_json_payload(raw) or {}
        if _looks_like_case_payload(parsed):
            ai_payload = parsed
            completion_engine = "deepseek-case-officer"
        elif isinstance(parsed, dict) and parsed:
            completion_warnings.append("信息补全专员返回了 JSON，但缺少案件核心字段，已进入兜底解析。")
        else:
            completion_warnings.append("信息补全专员未返回可用 JSON，已进入兜底解析。")
    except Exception as exc:
        completion_warnings.append(f"信息补全专员调用失败：{exc}")

    if completion_engine != "deepseek-case-officer":
        parsed = workflow_service.parse_case_text(text, source_mode=source_mode, source_meta=source_meta)
        ai_payload = parsed
        ai_payload["completion_warnings"] = [
            *(ai_payload.get("completion_warnings") or []),
            *completion_warnings,
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

    merged_case["field_evidence"] = normalized.get("field_evidence") or {}
    merged_case["completion_engine"] = completion_engine
    merged_case["completion_agent"] = CASE_OFFICER_ROLE
    merged_case["completion_model"] = get_case_completion_model()
    merged_case["completion_provider"] = get_case_completion_provider()

    warnings = list(
        dict.fromkeys(
            [
                *(merged_case.get("completion_warnings") or []),
                *(normalized.get("completion_warnings") or []),
                *(normalized.get("parse_warnings") or []),
            ]
        )
    )
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
