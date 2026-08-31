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


def _split_role_names(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_split_role_names(item))
        return list(dict.fromkeys(name for name in result if name))
    text = str(value or "").strip()
    if not text:
        return []
    parts = re.split(r"[、，,；;/\s]+|(?:以及)|(?:及)|(?:和)|(?:与)", text)
    return list(dict.fromkeys(part.strip() for part in parts if part.strip()))


def _normalize_assessment_points(value: Any, learner_actions: list[str]) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    points: list[dict[str, Any]] = []
    for index, item in enumerate(rows, start=1):
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("assessment_item") or item.get("name") or f"考核点{index}").strip()
            content = str(item.get("content") or item.get("standard") or item.get("description") or label).strip()
            keywords = [str(word).strip() for word in item.get("keywords") or [] if str(word).strip()]
            related_actions = [
                str(action).strip()
                for action in item.get("related_actions") or item.get("actions") or []
                if str(action).strip()
            ]
            points.append({
                "label": label,
                "content": content,
                "keywords": keywords or ([label] if label else []),
                "related_actions": related_actions or learner_actions[:3],
            })
            continue
        text = str(item or "").strip()
        if text:
            points.append({
                "label": f"考核点{index}",
                "content": text,
                "keywords": [text],
                "related_actions": learner_actions[:3],
            })
    return points


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
    # Soft ceiling only — scene role count follows script/binding, not a hard 6-person cap.
    for person in selected[:32]:
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
        learner_actions = [str(value) for value in stage.get("learner_actions") or [] if str(value).strip()]
        points = _normalize_assessment_points(stage.get("assessment_points"), learner_actions)
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
            "learner_actions": learner_actions,
        })
    stages = normalized_stages
    scene_thresholds = item.get("state_thresholds") if isinstance(item.get("state_thresholds"), dict) else {}
    if scene_thresholds:
        stages = [{**stage, "state_thresholds": stage.get("state_thresholds") or scene_thresholds} for stage in stages if isinstance(stage, dict)]
    outcomes = [str(value) for value in item.get("expected_outcomes") or [] if str(value).strip()] if isinstance(item.get("expected_outcomes"), list) else []
    student_role = str(item.get("student_role") or "民警").strip() or "民警"
    if "民警" in student_role:
        student_role = "民警"
    return {
        "scene_id": str(item.get("scene_id") or f"{case_id}-scene-{index + 1}"),
        "scene_name": scene_name,
        "scene_description": str(item.get("scene_description") or summary),
        "location": str(item.get("location") or item.get("place") or default_location),
        "training_goal": goal or proposed_goal,
        "training_goal_repaired": goal_repaired,
        "student_role": student_role,
        "training_entry_phase": phase,
        "dispatch_brief": str(item.get("dispatch_brief") or summary[:240]),
        "first_impression": _normalize_first_impression(item.get("first_impression"), phase) or str(item.get("first_impression") or "").strip()[:160],
        "expected_outcomes": outcomes if outcomes else ([proposed_goal] if proposed_goal else []),
        "roles": [role["name"] for role in roles], "role_ids": [role["person_id"] for role in roles],
        "scene_roles": roles, "fact_ids": scene_fact_ids, "stages": stages,
        "state_thresholds": scene_thresholds,
        "harness_contract": {
            "template_version": SCENE_TEMPLATE_VERSION,
            "fact_boundary": "case_world.fact_ids", "role_boundary": "case_world.person_ids",
            "max_scenes": 4, "training_validated": True, "student_role": student_role,
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


def training_scripts_to_scene_candidates(
    training_scripts: list[dict[str, Any]],
    *,
    case_id: str,
    title: str,
    summary: str,
    persons: list[Any],
    facts: list[Any],
    default_location: str = "",
) -> list[dict[str, Any]]:
    """Compile script-first payload into normalized scene blueprint candidates."""
    candidates: list[dict[str, Any]] = []
    for index, script in enumerate(training_scripts[:4]):
        if not isinstance(script, dict):
            continue
        scene_pack = script.get("scene_pack") if isinstance(script.get("scene_pack"), dict) else {}
        stages = script.get("stages") if isinstance(script.get("stages"), list) else []
        compiled_stages: list[dict[str, Any]] = []
        for stage_idx, stage in enumerate(stages):
            if not isinstance(stage, dict):
                continue
            learner_actions = [str(item) for item in stage.get("learner_actions") or [] if str(item).strip()]
            points = _normalize_assessment_points(stage.get("assessment_points"), learner_actions)
            compiled_stages.append(
                {
                    "stage_name": str(stage.get("stage_name") or f"训练阶段{stage_idx + 1}"),
                    "stage_goal": str(stage.get("stage_goal") or script.get("training_goal") or "").strip(),
                    "assessment_points": points,
                    "fact_ids": [str(item) for item in stage.get("fact_ids") or [] if str(item).strip()],
                    "action_catalog": [],
                    "completion_rules": [],
                    "end_conditions": [],
                    "learner_actions": learner_actions,
                    "role_pressure_points": [str(item) for item in stage.get("role_pressure_points") or [] if str(item).strip()],
                    "expected_stage_effects": [str(item) for item in stage.get("expected_stage_effects") or [] if str(item).strip()],
                    "recommended_prompts": [
                        str(item) for item in (stage.get("recommended_prompts") or learner_actions)[:4]
                        if str(item).strip()
                    ],
                }
            )
        role_rows = [item for item in script.get("role_training_functions") or [] if isinstance(item, dict)]
        role_names = _split_role_names([item.get("role_name") for item in role_rows if isinstance(item, dict)])
        role_ids = []
        for name in role_names:
            for person in persons:
                if str(getattr(person, "name", "")).strip() == name:
                    role_ids.append(str(getattr(person, "person_id", "")))
        role_ids = list(dict.fromkeys([item for item in role_ids if item]))
        scene_candidate = {
            "scene_id": f"{case_id}-scene-{index + 1}",
            "scene_name": str(script.get("scene_name") or "").strip(),
            "scene_description": str(script.get("plot_arc") or summary),
            "training_goal": str(script.get("training_goal") or "").strip(),
            "student_role": str(scene_pack.get("student_role") or "民警"),
            "training_entry_phase": str(scene_pack.get("training_entry_phase") or "post_incident_onsite"),
            "dispatch_brief": str(scene_pack.get("dispatch_brief") or ""),
            "first_impression": str(scene_pack.get("first_impression") or ""),
            "expected_outcomes": [str(item) for item in script.get("expected_outcomes") or [] if str(item).strip()],
            "fact_ids": list(
                dict.fromkeys(
                    [
                        str(item)
                        for stage in compiled_stages
                        for item in stage.get("fact_ids") or []
                        if str(item).strip()
                    ]
                )
            ),
            "roles": role_names,
            "role_ids": role_ids,
            "stages": compiled_stages,
            "plot_arc": str(script.get("plot_arc") or "").strip(),
            "role_training_functions": role_rows,
            "completion_criteria": [str(item) for item in script.get("completion_criteria") or [] if str(item).strip()],
            "failure_patterns": [str(item) for item in script.get("failure_patterns") or [] if str(item).strip()],
            "opening_lines": [item for item in script.get("opening_lines") or [] if isinstance(item, dict)],
        }
        candidates.append(
            normalize_blueprint(
                scene_candidate,
                case_id=case_id,
                index=index,
                title=title,
                summary=summary,
                persons=persons,
                facts=facts,
                default_location=default_location,
            )
            | {
                "plot_arc": scene_candidate["plot_arc"],
                "role_training_functions": scene_candidate["role_training_functions"],
                "completion_criteria": scene_candidate["completion_criteria"],
                "failure_patterns": scene_candidate["failure_patterns"],
                "opening_lines": scene_candidate["opening_lines"],
            }
        )
    return candidates
