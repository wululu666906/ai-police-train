from __future__ import annotations

import re
from typing import Any

from ai_workflow_service.domain.four_dimensional_state import normalize_state
from ai_workflow_service.domain.case_import_quality import is_police_training_goal
from ai_workflow_service.domain.dialogue_scene_admission import filter_dialogue_admitted_scenes


# Versioned template contract consumed by the existing case-import Harness.
SCENE_TEMPLATE_VERSION = "police_training_scene_v1"
DEFAULT_GOAL = "核实警情要素、控制现场风险并完成规范处置"
DEFAULT_SCENE_NAMES = ("接警信息核实", "现场风险处置", "关键人员询问", "处置闭环回访")


def default_assessment_points() -> list[dict[str, Any]]:
    return [
        {"id": "safety", "label": "确认现场安全与风险", "required": True, "keywords": ["安全", "危险", "受伤"], "related_actions": ["request_backup", "isolate_scene"]},
        {"id": "facts", "label": "核实关键事实", "required": True, "keywords": ["时间", "地点", "经过"], "related_actions": []},
        {"id": "closure", "label": "完成处置闭环", "required": False, "keywords": ["后续", "记录", "告知"], "related_actions": ["record_evidence"]},
    ]


def _fact_ids(value: Any, valid_ids: set[str]) -> list[str]:
    values = value if isinstance(value, list) else []
    return list(dict.fromkeys(str(item) for item in values if str(item) in valid_ids))


def _relevance_terms(value: Any) -> set[str]:
    text = str(value or "").casefold()
    terms = set(re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]{2,}", text))
    for term in tuple(terms):
        if re.fullmatch(r"[\u4e00-\u9fff]+", term):
            terms.update(term[pos:pos + 2] for pos in range(len(term) - 1))
    return terms


def _bind_facts(item: dict[str, Any], facts: list[Any], roles: list[dict[str, Any]]) -> list[str]:
    valid_ids = {str(getattr(fact, "fact_id", "")) for fact in facts if str(getattr(fact, "fact_id", ""))}
    proposed = _fact_ids(item.get("fact_ids"), valid_ids)
    if proposed:
        return proposed

    context_parts = [
        item.get("scene_name"), item.get("scene_description"), item.get("training_goal"),
        item.get("dispatch_brief"), item.get("first_impression"),
        " ".join(str(value) for value in item.get("expected_outcomes") or []),
        " ".join(role["name"] for role in roles),
    ]
    for stage in item.get("stages") or []:
        if isinstance(stage, dict):
            context_parts.extend((stage.get("stage_name"), stage.get("stage_goal")))
    context_terms = _relevance_terms(" ".join(str(value or "") for value in context_parts))
    scored = []
    for order, fact in enumerate(facts):
        fact_id = str(getattr(fact, "fact_id", ""))
        fact_terms = _relevance_terms(getattr(fact, "content", ""))
        known_by = {str(value) for value in getattr(fact, "known_by", [])}
        role_names = {role["name"] for role in roles}
        score = len(context_terms & fact_terms) + 3 * len(known_by & role_names)
        scored.append((-score, order, fact_id))
    scored.sort()
    relevant = [fact_id for negative_score, _, fact_id in scored if negative_score < 0][:6]
    return relevant or [fact_id for _, _, fact_id in scored[:1]]


def _select_roles(item: dict[str, Any], persons: list[Any]) -> list[dict[str, Any]]:
    by_id = {str(getattr(person, "person_id", "")): person for person in persons}
    by_name = {str(getattr(person, "name", "")): person for person in persons}
    proposed_states = [value for value in item.get("scene_roles") or [] if isinstance(value, dict)]
    requested_ids = [str(value) for value in item.get("role_ids") or []]
    requested_names = [str(value) for value in item.get("roles") or item.get("role_names") or []]
    selected = []
    for person in [*(by_id.get(value) for value in requested_ids), *(by_name.get(value) for value in requested_names)]:
        if person is None or not bool(getattr(person, "speakable", True)) or person in selected:
            continue
        selected.append(person)
    if not selected:
        selected = [person for person in persons if bool(getattr(person, "speakable", True))][:4]
    roles = []
    for person in selected[:6]:
        person_id = str(getattr(person, "person_id", ""))
        name = str(getattr(person, "name", ""))
        proposed = next((value for value in proposed_states if str(value.get("person_id")) == person_id or str(value.get("name")) == name), {})
        roles.append({"person_id": person_id, "name": name, "initial_state": normalize_state(proposed.get("initial_state"))})
    return roles


def normalize_blueprint(raw: Any, *, case_id: str, index: int, title: str, summary: str, persons: list[Any], facts: list[Any], default_location: str = "") -> dict[str, Any]:
    item = raw if isinstance(raw, dict) else {}
    roles = _select_roles(item, persons)
    scene_fact_ids = _bind_facts(item, facts, roles)
    valid_scene_fact_ids = set(scene_fact_ids)
    proposed_goal = str(item.get("training_goal") or "").strip()
    goal_repaired = not is_police_training_goal(proposed_goal)
    goal = proposed_goal if not goal_repaired else DEFAULT_GOAL
    phase = str(item.get("training_entry_phase") or ("intake" if index == 0 else "post_incident_onsite" if index == 1 else "post_incident_inquiry" if index == 2 else "post_incident_followup"))
    proposed_name = str(item.get("scene_name") or "").strip()
    scene_name = proposed_name if proposed_name and proposed_name != title else DEFAULT_SCENE_NAMES[min(index, len(DEFAULT_SCENE_NAMES) - 1)]
    stages = [stage for stage in item.get("stages") or [] if isinstance(stage, dict)] if isinstance(item.get("stages"), list) else []
    if not stages:
        stages = [{
            "stage_name": "现场处置", "stage_goal": goal,
            "assessment_points": default_assessment_points(),
            "action_catalog": [
                {"id": "request_backup", "label": "请求增援"},
                {"id": "isolate_scene", "label": "隔离现场"},
                {"id": "record_evidence", "label": "固定证据"},
            ],
            "prerequisites": ["safety"],
            "completion_rules": [{"required_point_ids": ["safety", "facts"]}],
            "end_conditions": [{"type": "required_points_complete"}],
        }]
    normalized_stages = []
    for stage_index, stage in enumerate(stages):
        points = [value for value in stage.get("assessment_points") or [] if isinstance(value, dict)]
        if goal_repaired or not points:
            points = default_assessment_points()
        actions = [] if goal_repaired else [value for value in stage.get("action_catalog") or stage.get("available_actions") or [] if isinstance(value, dict)]
        required_ids = [str(value.get("id")) for value in points if value.get("required", value.get("is_required", True)) and value.get("id")]
        proposed_stage_goal = str(stage.get("stage_goal") or "").strip()
        stage_goal = proposed_stage_goal if is_police_training_goal(proposed_stage_goal) else goal
        normalized_stages.append({
            **stage,
            "stage_name": str(stage.get("stage_name") or f"训练阶段{stage_index + 1}"),
            "stage_goal": stage_goal,
            "assessment_points": points,
            "fact_ids": _fact_ids(stage.get("fact_ids"), valid_scene_fact_ids) or list(scene_fact_ids),
            "action_catalog": actions or [
                {"id": "request_backup", "label": "请求增援"},
                {"id": "isolate_scene", "label": "隔离现场"},
                {"id": "record_evidence", "label": "固定证据"},
            ],
            "completion_rules": list(([] if goal_repaired else stage.get("completion_rules")) or [{"required_point_ids": required_ids}]),
            "end_conditions": list(([] if goal_repaired else stage.get("end_conditions")) or ([{"type": "required_points_complete"}] if stage_index == len(stages) - 1 else [])),
        })
    stages = normalized_stages
    scene_thresholds = item.get("state_thresholds") if isinstance(item.get("state_thresholds"), dict) else {}
    if scene_thresholds:
        stages = [{**stage, "state_thresholds": stage.get("state_thresholds") or scene_thresholds} for stage in stages if isinstance(stage, dict)]
    return {
        "scene_id": str(item.get("scene_id") or f"{case_id}-scene-{index + 1}"),
        "scene_name": scene_name,
        "scene_description": str(item.get("scene_description") or summary),
        "location": str(item.get("location") or item.get("place") or default_location),
        "training_goal": goal,
        "training_goal_repaired": goal_repaired,
        "student_role": "民警",
        "training_entry_phase": phase,
        "dispatch_brief": str(item.get("dispatch_brief") or summary[:240]),
        "first_impression": str(item.get("first_impression") or summary[:240]),
        "expected_outcomes": [str(value) for value in item.get("expected_outcomes") if str(value).strip()]
        if isinstance(item.get("expected_outcomes"), list) and not goal_repaired else ["识别并控制现场风险", "核实并记录关键事实", "完成告知、移交或处置闭环"],
        "roles": [role["name"] for role in roles], "role_ids": [role["person_id"] for role in roles],
        "scene_roles": roles, "fact_ids": scene_fact_ids, "stages": stages,
        "state_thresholds": scene_thresholds,
        "harness_contract": {
            "template_version": SCENE_TEMPLATE_VERSION,
            "fact_boundary": "case_world.fact_ids", "role_boundary": "case_world.person_ids",
            "max_scenes": 4, "training_validated": True, "student_role": "民警",
        },
    }


def _similarity(left: Any, right: Any) -> float:
    left_terms = _relevance_terms(left)
    right_terms = _relevance_terms(right)
    return len(left_terms & right_terms) / max(len(left_terms | right_terms), 1)


def _merge_scene(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    target["fact_ids"] = list(dict.fromkeys([*(target.get("fact_ids") or []), *(incoming.get("fact_ids") or [])]))
    target["expected_outcomes"] = list(dict.fromkeys([*(target.get("expected_outcomes") or []), *(incoming.get("expected_outcomes") or [])]))
    stages = [*(target.get("stages") or []), *(incoming.get("stages") or [])]
    deduped_stages = []
    seen_stages = set()
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        key = (str(stage.get("stage_name") or ""), str(stage.get("stage_goal") or ""))
        if key in seen_stages:
            continue
        seen_stages.add(key)
        deduped_stages.append(stage)
    target["stages"] = deduped_stages[:6]
    valid_ids = set(target["fact_ids"])
    for stage in target["stages"]:
        if isinstance(stage, dict):
            stage["fact_ids"] = _fact_ids(stage.get("fact_ids"), valid_ids) or list(target["fact_ids"])


def select_necessary_scenes(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    for item in candidates:
        if not item.get("training_goal") or not item.get("stages") or not item.get("fact_ids") or not item.get("role_ids"):
            continue
        duplicate = next((existing for existing in selected if (
            str(existing.get("scene_name")) == str(item.get("scene_name"))
            or (
                set(existing.get("fact_ids") or []) == set(item.get("fact_ids") or [])
                and set(existing.get("role_ids") or []) == set(item.get("role_ids") or [])
                and _similarity(existing.get("training_goal"), item.get("training_goal")) >= 0.55
            )
            or _similarity(
                " ".join(map(str, [existing.get("training_goal"), existing.get("scene_description")])),
                " ".join(map(str, [item.get("training_goal"), item.get("scene_description")])),
            ) >= 0.78
        )), None)
        if duplicate:
            _merge_scene(duplicate, item)
            continue
        selected.append(item)
        if len(selected) == 4:
            break
    admitted, rejected = filter_dialogue_admitted_scenes(selected, allow_remap=True)
    return admitted if admitted else selected[:1] if selected else []
