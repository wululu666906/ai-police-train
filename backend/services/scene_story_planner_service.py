"""Post-process scene blueprints against story time/space nodes."""
from __future__ import annotations

import os
import re
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _terms(value: Any) -> set[str]:
    text = re.sub(r"\s+", "", _text(value))
    terms = set(re.findall(r"[A-Za-z0-9]+", text))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    terms.update(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    return {term for term in terms if term}


def build_scene_portfolio_plan(case_info: dict[str, Any], story_graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Build candidate training dimensions before asking the model for scene prose.

    These are references, not mandatory slots. Scene generation applies the
    necessity principle: one scene is correct when it covers the practical
    training goal, and extra scenes require distinct operational value.
    """
    fact_cards = [item for item in story_graph.get("fact_cards") or [] if isinstance(item, dict)]
    persons = [item for item in case_info.get("persons") or [] if isinstance(item, dict)]
    context = " ".join([
        _text(case_info.get("case_type")),
        _text(case_info.get("case_background")),
        _text(case_info.get("full_narrative")),
        _text(story_graph.get("complete_story")),
        " ".join(_text(item.get("content")) for item in fact_cards),
    ])
    has_alarm_context = any(term in context for term in ("报警", "报案", "接警", "求助", "110"))
    intake_name = "接警研判" if has_alarm_context else "任务研判与出警准备"
    intake_purpose = (
        "训练学员从报警人的有限陈述中核实警情要素、识别风险并形成派警判断。"
        if has_alarm_context
        else "训练学员在出警前从已有材料中提炼任务、风险和需要到场核实的问题。"
    )
    plan = [
        {
            "portfolio_role": "intake",
            "is_primary": False,
            "scene_name": intake_name,
            "scene_kind": "接警" if has_alarm_context else "任务研判",
            "training_entry_phase": "intake",
            "entry_time_policy": "dispatch_intake",
            "scene_purpose": intake_purpose,
            "necessity_note": "仅当接警阶段存在独立的要素核实、风险研判或出警准备训练价值时生成；不得作为单纯信息复述场景。",
            "training_goal": "准确形成警情基本判断、出警重点和安全预案。",
            "start_state": "民警只掌握报警或任务派发阶段的有限信息，案件完整经过尚待核实。",
            "stages": [
                {"stage_name": "警情要素核实", "stage_goal": "核实时间、地点、人员、事由和当前状态。"},
                {"stage_name": "风险研判与出警准备", "stage_goal": "判断伤情、持续危险、增援救助需求和到场核查重点。"},
            ],
            "completion_criteria": ["警情基本要素已经核实", "主要风险及增援救助需求已经判断", "已形成明确出警重点"],
            "end_prompt": "接警研判目标已完成，可结束本场训练并进入案发后现场处置。",
        },
        {
            "portfolio_role": "primary",
            "is_primary": True,
            "scene_name": "案发后主现场处置",
            "scene_kind": "案发后现场处置",
            "training_entry_phase": "post_incident_onsite",
            "entry_time_policy": "after_canonical_event",
            "scene_purpose": "作为本案核心训练场景，还原案发后的空间、人员、遗留状态和现实风险，训练民警完成首次现场处置。",
            "necessity_note": "优先作为单场景承载矛盾调处、现场控制、人员接触、信息核实和线索摸排等综合训练目标。",
            "training_goal": "完成安全确认、人员接触、现场控制、初步核实和证据保护。",
            "start_state": "案件主要行为已经发生，民警到达相关现场；既定案件事实和结果不可改变。",
            "stages": [
                {"stage_name": "到场观察与安全确认", "stage_goal": "识别现场人员状态、伤情、危险物和残余风险。"},
                {"stage_name": "人员分流与初步核实", "stage_goal": "稳定现场并分别核实各方身份、诉求和第一手情况。"},
                {"stage_name": "证据保护与处置闭环", "stage_goal": "固定现场线索，完成救助、移交和后续程序告知。"},
            ],
            "completion_criteria": ["现实风险已经受控或明确移交", "关键人员和基本经过已经初核", "现场证据与后续处置已经安排"],
            "end_prompt": "主现场核心处置目标已完成，可结束本场训练或继续补充非必要询问。",
        },
        {
            "portfolio_role": "investigation",
            "is_primary": False,
            "scene_name": "案发后信息核实与线索摸排",
            "scene_kind": "案发后信息核实",
            "training_entry_phase": "post_incident_inquiry",
            "entry_time_policy": "after_canonical_event",
            "scene_purpose": "训练学员在案件发生后按人物认知边界开展信息核实、线索摸排并核对陈述矛盾。",
            "necessity_note": "仅当主现场处置无法充分覆盖线索摸排或陈述核实时生成；不得设计为审问、讯问或纯笔录制作。",
            "training_goal": "形成时间线清晰、信息来源明确、矛盾点可继续核查的处置记录。",
            "start_state": "现场主要风险已处置，相关人员可分别沟通，仍存在需要核实的信息缺口或线索断点。",
            "stages": [
                {"stage_name": "自由陈述与时间线建立", "stage_goal": "让被询问人按亲历顺序说明其所知经过。"},
                {"stage_name": "关键细节与信息来源核实", "stage_goal": "区分亲历、目击、听闻和事后得知的信息。"},
                {"stage_name": "矛盾核对与线索闭合", "stage_goal": "核对重要差异、遗漏和待查事项，明确下一步核查方向。"},
            ],
            "completion_criteria": ["人物陈述时间线已经建立", "关键行为及信息来源已经核实", "矛盾点和待查事项已经记录", "下一步核查方向已经说明"],
            "end_prompt": "信息核实与线索摸排目标已完成，可结束本场训练。",
        },
    ]
    return plan


def _portfolio_role(blueprint: dict[str, Any]) -> str:
    explicit = _text(blueprint.get("portfolio_role"))
    if explicit in {"intake", "primary", "investigation", "followup"}:
        return explicit
    phase = _text(blueprint.get("training_entry_phase"))
    context = " ".join([_text(blueprint.get("scene_name")), _text(blueprint.get("scene_kind")), _text(blueprint.get("training_goal"))])
    if phase == "intake" or any(term in context for term in ("接警", "报警", "出警准备", "任务研判")):
        return "intake"
    if phase == "post_incident_followup" or any(term in context for term in ("回访", "复盘", "协同", "流转")):
        return "followup"
    if phase == "post_incident_inquiry" or any(term in context for term in ("询问", "调查", "笔录", "讯问")):
        return "investigation"
    return "primary"


def _fact_ids_for_portfolio(role: str, facts: list[dict[str, Any]]) -> list[str]:
    keywords = {
        "intake": ("报警", "报案", "接警", "求助", "发现", "时间", "地点"),
        "primary": ("现场", "发生", "冲突", "伤", "损失", "行为", "持有", "到场", "人员"),
        "investigation": ("陈述", "证言", "供述", "询问", "辨认", "目击", "听见", "矛盾", "证据"),
        "followup": ("鉴定", "监控", "转账", "赔偿", "移交", "后续", "回访", "风险", "证据"),
    }.get(role, ())
    matched = [
        _text(fact.get("id"))
        for fact in facts
        if any(keyword in _text(fact.get("content")) for keyword in keywords)
    ]
    all_ids = [_text(fact.get("id")) for fact in facts]
    selected = list(dict.fromkeys([*matched, *all_ids[:4]]))
    return selected[:24]


def complete_scene_blueprint_portfolio(
    blueprints: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    story_graph: dict[str, Any],
    persons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize necessary blueprints without forcing optional slots.

    The model decides the number of scenes under the necessity principle. This
    function fills missing fields on returned blueprints and only synthesizes a
    single primary scene when no usable blueprint exists.
    """
    facts = [item for item in story_graph.get("fact_cards") or [] if isinstance(item, dict) and _text(item.get("id"))]
    person_rows = [item for item in persons if isinstance(item, dict) and _text(item.get("name"))]
    slot_by_role = {
        _text(slot.get("portfolio_role")): slot
        for slot in plan
        if isinstance(slot, dict) and _text(slot.get("portfolio_role"))
    }
    primary_slot = slot_by_role.get("primary") or (plan[0] if plan else {})
    source_blueprints = [dict(item) for item in blueprints if isinstance(item, dict)]
    if not source_blueprints and primary_slot:
        source_blueprints = [dict(primary_slot)]

    output: list[dict[str, Any]] = []
    for index, source in enumerate(source_blueprints[:4], start=1):
        role = _portfolio_role(source)
        if role == "followup":
            context = " ".join([
                _text(source.get("scene_name")),
                _text(source.get("scene_kind")),
                _text(source.get("scene_purpose")),
                _text(source.get("training_goal")),
            ])
            if not any(term in context for term in ("线索", "矛盾", "风险", "处置", "核实", "调处", "证据")):
                continue
        slot = slot_by_role.get(role) or primary_slot or {}
        item = dict(source)
        item["scene_id"] = _text(item.get("scene_id")) or f"S{index}"
        item["portfolio_role"] = role
        item["is_primary"] = bool(item.get("is_primary")) or role == "primary" or (index == 1 and not output)
        for key in (
            "scene_name", "scene_kind", "training_entry_phase", "entry_time_policy",
            "scene_purpose", "training_goal", "start_state", "completion_criteria", "end_prompt",
        ):
            if not item.get(key):
                item[key] = slot.get(key)
        if not item.get("stages"):
            item["stages"] = [dict(stage) for stage in slot.get("stages") or []]
        item["canonical_outcome_locked"] = True
        item["student_role"] = "民警"
        if not item.get("fact_ids"):
            item["fact_ids"] = _fact_ids_for_portfolio(role, facts)
        if not item.get("roles"):
            fact_text = " ".join(
                _text(fact.get("content")) for fact in facts if _text(fact.get("id")) in set(item.get("fact_ids") or [])
            )
            grounded = [_text(person.get("name")) for person in person_rows if _text(person.get("name")) in fact_text]
            item["roles"] = grounded or [_text(person.get("name")) for person in person_rows]
        output.append(item)
    if output and not any(item.get("is_primary") for item in output):
        output[0]["is_primary"] = True
        output[0]["portfolio_role"] = output[0].get("portfolio_role") or "primary"
    return output[:4]


def missing_scene_portfolio_slots(blueprints: list[dict[str, Any]], plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    present = {_portfolio_role(item) for item in blueprints}
    return [dict(slot) for slot in plan if _text(slot.get("portfolio_role")) not in present]


def _similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_portfolio_role = _text(left.get("portfolio_role"))
    right_portfolio_role = _text(right.get("portfolio_role"))
    if left_portfolio_role and right_portfolio_role and left_portfolio_role != right_portfolio_role:
        return 0.0
    left_phase = _text(left.get("training_entry_phase"))
    right_phase = _text(right.get("training_entry_phase"))
    if left_phase and right_phase and left_phase != right_phase:
        return 0.0
    left_kind = _text(left.get("scene_kind"))
    right_kind = _text(right.get("scene_kind"))
    if left_kind and right_kind and left_kind != right_kind:
        return 0.0
    left_facts = {str(item) for item in left.get("fact_ids") or []}
    right_facts = {str(item) for item in right.get("fact_ids") or []}
    fact_union = left_facts | right_facts
    fact_score = len(left_facts & right_facts) / len(fact_union) if fact_union else 0.0
    left_terms = _terms(" ".join([_text(left.get("scene_name")), _text(left.get("training_goal"))]))
    right_terms = _terms(" ".join([_text(right.get("scene_name")), _text(right.get("training_goal"))]))
    term_union = left_terms | right_terms
    term_score = len(left_terms & right_terms) / len(term_union) if term_union else 0.0
    same_space = bool(_text(left.get("place")) and _text(left.get("place")) == _text(right.get("place")))
    same_time = bool(_text(left.get("time")) and _text(left.get("time")) == _text(right.get("time")))
    combined = fact_score * 0.5 + term_score * 0.3 + (0.1 if same_space else 0) + (0.1 if same_time else 0)
    if fact_score >= 0.8 and term_score >= 0.35:
        combined = max(combined, 0.72)
    if same_space and same_time and term_score >= 0.35:
        combined = max(combined, 0.65)
    return combined


def merge_duplicate_blueprints(blueprints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for source in blueprints:
        current = dict(source)
        duplicate = next((item for item in merged if _similarity(item, current) >= 0.68), None)
        if duplicate is None:
            merged.append(current)
            continue
        duplicate["fact_ids"] = list(dict.fromkeys([*(duplicate.get("fact_ids") or []), *(current.get("fact_ids") or [])]))[:max(24, int(os.getenv("CASE_SCENE_FACT_LIMIT", "80")))]
        duplicate["story_node_ids"] = list(dict.fromkeys([*(duplicate.get("story_node_ids") or []), *(current.get("story_node_ids") or [])]))
        duplicate["roles"] = list(dict.fromkeys([*(duplicate.get("roles") or []), *(current.get("roles") or [])]))
        duplicate["present_roles"] = list(dict.fromkeys([*(duplicate.get("present_roles") or []), *(current.get("present_roles") or [])]))
        duplicate["mentioned_roles"] = list(dict.fromkeys([*(duplicate.get("mentioned_roles") or []), *(current.get("mentioned_roles") or [])]))
        duplicate["primary_roles"] = list(dict.fromkeys([*(duplicate.get("primary_roles") or []), *(current.get("primary_roles") or [])]))[:3]
        duplicate["time"] = " → ".join(dict.fromkeys(filter(None, [_text(duplicate.get("time")), _text(current.get("time"))])))
        duplicate["place"] = " → ".join(dict.fromkeys(filter(None, [_text(duplicate.get("place")), _text(current.get("place"))])))
        stage_rows = [*(duplicate.get("stages") or []), *(current.get("stages") or [])]
        unique_stages: list[dict[str, Any]] = []
        seen_stages: set[tuple[str, str]] = set()
        for stage in stage_rows:
            if not isinstance(stage, dict):
                continue
            marker = (_text(stage.get("stage_name")), _text(stage.get("stage_goal")))
            if marker in seen_stages:
                continue
            seen_stages.add(marker)
            unique_stages.append(stage)
        duplicate["stages"] = unique_stages
        duplicate["training_goal"] = "；".join(dict.fromkeys(filter(None, [_text(duplicate.get("training_goal")), _text(current.get("training_goal"))])))
    return merged


def _entry_phase(blueprint: dict[str, Any], index: int) -> str:
    explicit = _text(blueprint.get("training_entry_phase"))
    allowed = {
        "intake",
        "post_incident_onsite",
        "post_incident_inquiry",
        "post_incident_followup",
    }
    if explicit in allowed:
        return explicit
    context = " ".join(
        [_text(blueprint.get("scene_name")), _text(blueprint.get("scene_kind")), _text(blueprint.get("training_goal"))]
    )
    if index == 0 and any(term in context for term in ("接警", "报警", "指挥中心")):
        return "intake"
    if any(term in context for term in ("询问", "调查", "笔录", "核查", "讯问")):
        return "post_incident_inquiry"
    if any(term in context for term in ("回访", "复盘", "协同", "移交", "化解")):
        return "post_incident_followup"
    return "post_incident_onsite" if index <= 1 else "post_incident_inquiry"


def _entry_time_label(phase: str) -> str:
    return {
        "intake": "接到报警时（案件事实尚待民警核实）",
        "post_incident_onsite": "案件主要行为发生后，民警到场处置时",
        "post_incident_inquiry": "案件发生后的调查询问阶段",
        "post_incident_followup": "案件发生后的复盘回访或协同处置阶段",
    }[phase]


def bind_blueprints_to_story(
    blueprints: list[dict[str, Any]],
    story_graph: dict[str, Any],
    persons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    nodes = [node for node in story_graph.get("nodes") or [] if isinstance(node, dict)]
    valid_people = {
        _text(person.get("name")): person
        for person in persons
        if isinstance(person, dict) and _text(person.get("name"))
    }
    fact_to_node: dict[str, dict[str, Any]] = {}
    for node in nodes:
        for event in node.get("events") or []:
            fact_id = _text(event.get("fact_id"))
            if fact_id:
                fact_to_node[fact_id] = node

    bound: list[dict[str, Any]] = []
    for blueprint_index, blueprint in enumerate(blueprints):
        requested_nodes = {_text(value) for value in blueprint.get("story_node_ids") or [] if _text(value)}
        matched_nodes = [node for node in nodes if _text(node.get("node_id")) in requested_nodes]
        if not matched_nodes:
            matched_nodes = []
            seen_node_ids: set[str] = set()
            for fact_id in (_text(value) for value in blueprint.get("fact_ids") or []):
                node = fact_to_node.get(fact_id)
                node_id = _text((node or {}).get("node_id"))
                if node and node_id not in seen_node_ids:
                    matched_nodes.append(node)
                    seen_node_ids.add(node_id)
        if not matched_nodes and nodes:
            index = min(len(bound), len(nodes) - 1)
            matched_nodes = [nodes[index]]
        historical_present_roles = list(dict.fromkeys(
            name
            for node in matched_nodes
            for name in node.get("present_roles") or []
            if name in valid_people
        ))
        requested_roles = [name for name in blueprint.get("roles") or [] if name in valid_people]
        scene_roles = requested_roles
        primary_roles = scene_roles[:3]
        mentioned_roles = list(dict.fromkeys(
            name
            for node in matched_nodes
            for name in node.get("mentioned_roles") or []
            if name in valid_people and name not in historical_present_roles
        ))
        item = dict(blueprint)
        phase = _entry_phase(item, blueprint_index)
        item["story_node_ids"] = [_text(node.get("node_id")) for node in matched_nodes]
        item["canonical_time"] = " → ".join(dict.fromkeys(_text(node.get("time")) for node in matched_nodes if _text(node.get("time"))))
        item["canonical_place"] = " → ".join(dict.fromkeys(_text(node.get("place")) for node in matched_nodes if _text(node.get("place"))))
        item["training_entry_phase"] = phase
        item["entry_time_policy"] = "after_canonical_event" if phase != "intake" else "dispatch_intake"
        item["canonical_outcome_locked"] = True
        item["student_role"] = "民警"
        item["time"] = _entry_time_label(phase)
        item["place"] = _text(item.get("place")) or item["canonical_place"]
        item["historical_present_roles"] = historical_present_roles
        item["present_roles"] = list(dict.fromkeys([*historical_present_roles, *requested_roles]))
        item["primary_roles"] = primary_roles
        item["mentioned_roles"] = mentioned_roles
        item["roles"] = scene_roles
        bound.append(item)
    return merge_duplicate_blueprints(bound)


def bind_scenes_to_story(
    scenes: list[dict[str, Any]],
    blueprints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        blueprint = blueprints[min(index, len(blueprints) - 1)] if blueprints else {}
        item = dict(scene)
        for key in (
            "story_node_ids", "time", "place", "canonical_time", "canonical_place",
            "present_roles", "historical_present_roles", "primary_roles", "mentioned_roles",
            "training_entry_phase", "entry_time_policy", "canonical_outcome_locked", "student_role",
            "portfolio_role", "is_primary", "scene_purpose", "training_goal", "start_state",
            "completion_criteria", "end_prompt", "scene_kind",
        ):
            if key in {"canonical_outcome_locked", "is_primary"}:
                item[key] = bool(blueprint.get(key, item.get(key, False)))
            else:
                item[key] = blueprint.get(key) or item.get(key) or (
                    [] if key.endswith("roles") or key in {"story_node_ids", "completion_criteria"} else ""
                )
        item["roles"] = list(dict.fromkeys(blueprint.get("roles") or []))
        item["fact_ids"] = list(dict.fromkeys(blueprint.get("fact_ids") or []))
        item["supplement_ids"] = list(dict.fromkeys(blueprint.get("supplement_ids") or []))
        allowed_facts = set(item["fact_ids"])
        item["stages"] = [
            {
                **stage,
                "fact_ids": [fact_id for fact_id in stage.get("fact_ids") or [] if fact_id in allowed_facts]
                or list(item["fact_ids"]),
            }
            for stage in item.get("stages") or []
            if isinstance(stage, dict)
        ]
        output.append(item)
    return output
