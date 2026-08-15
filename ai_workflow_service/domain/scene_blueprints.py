from __future__ import annotations

import re
from typing import Any

from ai_workflow_service.domain.four_dimensional_state import normalize_state
from ai_workflow_service.domain.case_import_quality import is_police_training_goal
from ai_workflow_service.domain.dialogue_scene_admission import filter_dialogue_admitted_scenes


# Versioned template contract consumed by the existing case-import Harness.
SCENE_TEMPLATE_VERSION = "police_training_scene_v1"
FIRST_IMPRESSION_MIN_LENGTH = 80
FIRST_IMPRESSION_MAX_LENGTH = 160
FIRST_IMPRESSION_BANNED_MARKERS = (
    "接警信息", "报警信息", "接到报警", "报警人称", "110指令",
    "当前可接触人员", "可接触人员", "当前时空", "→",
    "训练目标", "训练任务", "民警任务", "开展询问", "开展处置",
    "案件结论", "裁判结论", "隐藏证据", "定罪", "量刑",
)


def _normalize_first_impression(value: Any, _phase: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if (
        not text
        or any(marker in text for marker in FIRST_IMPRESSION_BANNED_MARKERS)
        or re.search(r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}时\d{1,2}分|F\d+", text)
    ):
        return ""
    if len(text) <= FIRST_IMPRESSION_MAX_LENGTH:
        return text
    sentences = [part for part in re.split(r"(?<=[。！？；])", text) if part]
    shortened = ""
    for sentence in sentences:
        if len(shortened + sentence) > FIRST_IMPRESSION_MAX_LENGTH:
            break
        shortened += sentence
    if len(shortened) >= FIRST_IMPRESSION_MIN_LENGTH:
        return shortened
    return text[:FIRST_IMPRESSION_MAX_LENGTH - 1].rstrip("，；： ") + "。"


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
    requested_ids = [
        *[str(value) for value in item.get("role_ids") or []],
        *[str(value.get("person_id") or "") for value in proposed_states],
    ]
    requested_names = [
        *[str(value) for value in item.get("roles") or item.get("role_names") or []],
        *[str(value.get("name") or "") for value in proposed_states],
    ]
    selected = []
    for person in [*(by_id.get(value) for value in requested_ids), *(by_name.get(value) for value in requested_names)]:
        if person is None or not bool(getattr(person, "speakable", True)) or person in selected:
            continue
        selected.append(person)
    roles = []
    for person in selected[:6]:
        person_id = str(getattr(person, "person_id", ""))
        name = str(getattr(person, "name", ""))
        proposed = next((value for value in proposed_states if str(value.get("person_id")) == person_id or str(value.get("name")) == name), {})
        if proposed.get("present") is False:
            continue
        role_state = getattr(person, "initial_state", None)
        if hasattr(role_state, "model_dump"):
            role_state = role_state.model_dump(mode="json")
        roles.append({
            "person_id": person_id,
            "name": name,
            "initial_state": normalize_state(role_state),
            "present": proposed.get("present") is not False,
            "interaction_purpose": str(proposed.get("interaction_purpose") or "").strip(),
            "can_initiate": bool(proposed.get("can_initiate", False)),
            "can_interrupt": bool(proposed.get("can_interrupt", False)),
            "relevant_fact_ids": list(dict.fromkeys(
                str(value) for value in proposed.get("relevant_fact_ids") or [] if str(value).strip()
            )),
        })
    return roles


def normalize_blueprint(raw: Any, *, case_id: str, index: int, title: str, summary: str, persons: list[Any], facts: list[Any], default_location: str = "") -> dict[str, Any]:
    item = raw if isinstance(raw, dict) else {}
    roles = _select_roles(item, persons)
    scene_fact_ids = _bind_facts(item, facts, roles)
    valid_scene_fact_ids = set(scene_fact_ids)
    for role in roles:
        role["relevant_fact_ids"] = _fact_ids(role.get("relevant_fact_ids"), valid_scene_fact_ids)
    proposed_goal = str(item.get("training_goal") or "").strip()
    goal_repaired = not is_police_training_goal(proposed_goal)
    goal = proposed_goal if not goal_repaired else ""
    phase = str(item.get("training_entry_phase") or ("intake" if index == 0 else "post_incident_onsite" if index == 1 else "post_incident_inquiry" if index == 2 else "post_incident_followup"))
    proposed_name = str(item.get("scene_name") or "").strip()
    scene_name = proposed_name if proposed_name and proposed_name != title else ""
    stages = [stage for stage in item.get("stages") or [] if isinstance(stage, dict)] if isinstance(item.get("stages"), list) else []
    normalized_stages = []
    for stage_index, stage in enumerate(stages):
        points = [value for value in stage.get("assessment_points") or [] if isinstance(value, dict)]
        actions = [value for value in stage.get("action_catalog") or stage.get("available_actions") or [] if isinstance(value, dict)]
        proposed_stage_goal = str(stage.get("stage_goal") or "").strip()
        stage_goal = proposed_stage_goal if is_police_training_goal(proposed_stage_goal) else goal
        normalized_stages.append({
            **stage,
            "stage_name": str(stage.get("stage_name") or f"训练阶段{stage_index + 1}"),
            "stage_goal": stage_goal if is_police_training_goal(stage_goal) else "",
            "assessment_points": points,
            "fact_ids": _fact_ids(stage.get("fact_ids"), valid_scene_fact_ids) or list(scene_fact_ids),
            "action_catalog": actions,
            "completion_rules": list(stage.get("completion_rules") or []),
            "end_conditions": list(stage.get("end_conditions") or []),
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
        "first_impression": _normalize_first_impression(item.get("first_impression"), phase),
        "expected_outcomes": [str(value) for value in item.get("expected_outcomes") if str(value).strip()]
        if isinstance(item.get("expected_outcomes"), list) and not goal_repaired else [],
        "roles": [role["name"] for role in roles], "role_ids": [role["person_id"] for role in roles],
        "scene_roles": roles, "fact_ids": scene_fact_ids, "stages": stages,
        "state_thresholds": scene_thresholds,
        "harness_contract": {
            "template_version": SCENE_TEMPLATE_VERSION,
            "fact_boundary": "case_world.fact_ids", "role_boundary": "case_world.person_ids",
            "max_scenes": 4, "training_validated": True, "student_role": "民警",
            "first_impression_contract": "80-160_chars_single_paragraph_observable_only",
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
        if (
            not item.get("scene_name") or not item.get("training_goal") or not item.get("first_impression") or not item.get("stages")
            or not item.get("fact_ids") or not item.get("role_ids") or not item.get("expected_outcomes")
        ):
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
    admitted, _ = filter_dialogue_admitted_scenes(selected, allow_remap=False)
    return admitted
