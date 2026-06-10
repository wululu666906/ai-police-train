"""Role compact V1: minimal admin fields with derived persona runtime fields."""

from __future__ import annotations

import copy
from typing import Any

from .opening_preset import apply_opening_preset, infer_opening_preset
from .persona_engine import get_behavior_archetype_defaults

ROLE_COMPACT_V1_FIELDS: tuple[str, ...] = (
    "name",
    "role_type",
    "status",
    "behavior_archetype",
    "opening_preset",
    "current_goal",
    "core_concern",
    "trigger_points",
    "calming_points",
    "cannot_answer",
    "boundary_primary",
    "boundary_secondary",
    "impairment_state",
)

BOUNDARY_MODE_FIELDS: dict[str, tuple[str, str]] = {
    "核查取证型": ("known_key_points", "withheld_key_points"),
    "调解型": ("conflict_core", "acceptable_outcomes"),
    "危机干预型": ("trigger_sources", "concerned_targets"),
    "管控型": ("escalation_actions", "deescalation_conditions"),
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_text_list(value: Any, *, limit: int = 0) -> list[str]:
    if isinstance(value, list):
        items = [_as_text(item) for item in value if _as_text(item)]
    elif isinstance(value, str):
        items = [_as_text(line) for line in value.splitlines() if _as_text(line)]
    else:
        items = []
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
        if limit and len(output) >= limit:
            break
    return output


def _map_boundary_lists(
    person: dict[str, Any],
    *,
    scene_behavior_mode: str,
) -> dict[str, list[str]]:
    mode = scene_behavior_mode if scene_behavior_mode in BOUNDARY_MODE_FIELDS else "核查取证型"
    primary_key, secondary_key = BOUNDARY_MODE_FIELDS[mode]
    fields = {field: [] for field in BOUNDARY_MODE_FIELDS[mode]}
    fields.update({field: [] for field in sum(BOUNDARY_MODE_FIELDS.values(), ())})

    primary = _as_text_list(person.get("boundary_primary"))
    secondary = _as_text_list(person.get("boundary_secondary"))
    if not primary or not secondary:
        legacy_primary, legacy_secondary = BOUNDARY_MODE_FIELDS[mode]
        if not primary:
            primary = _as_text_list(person.get(legacy_primary)) or _as_text_list(person.get("knows_facts"))
        if not secondary:
            secondary = _as_text_list(person.get(legacy_secondary)) or _as_text_list(person.get("hidden_truths"))

    fields[primary_key] = primary[:6]
    fields[secondary_key] = secondary[:6]
    return fields


def person_to_role_compact_view(
    person: dict[str, Any] | None,
    *,
    scene_behavior_mode: str = "核查取证型",
) -> dict[str, Any]:
    person = copy.deepcopy(person or {})
    mode = scene_behavior_mode if scene_behavior_mode in BOUNDARY_MODE_FIELDS else "核查取证型"
    primary_key, secondary_key = BOUNDARY_MODE_FIELDS[mode]
    boundary = _map_boundary_lists(person, scene_behavior_mode=mode)

    return {
        "name": _as_text(person.get("name")),
        "role_type": _as_text(person.get("role_type") or person.get("role")) or "相关人员",
        "status": _as_text(person.get("status")) or "正常",
        "behavior_archetype": _as_text(person.get("behavior_archetype")) or "求助配合型",
        "opening_preset": infer_opening_preset(person),
        "current_goal": _as_text(person.get("current_goal") or person.get("current_need")),
        "core_concern": _as_text(person.get("core_concern") or person.get("weakness")),
        "trigger_points": _as_text_list(person.get("trigger_points"), limit=3),
        "calming_points": _as_text_list(person.get("calming_points"), limit=3),
        "cannot_answer": _as_text_list(person.get("cannot_answer") or person.get("does_not_know"), limit=6),
        "boundary_primary": boundary.get(primary_key, []),
        "boundary_secondary": boundary.get(secondary_key, []),
        "impairment_state": _as_text(person.get("impairment_state")),
        "relationship_pressure": _as_text_list(person.get("relationship_pressure"), limit=2),
        "surface_stance": _as_text(person.get("surface_stance") or person.get("public_mask")),
        "pressure_response": _as_text(person.get("pressure_response") or person.get("stress_response")),
    }


def expand_role_compact_to_person(
    compact: dict[str, Any] | None,
    *,
    scene_behavior_mode: str = "核查取证型",
) -> dict[str, Any]:
    compact = copy.deepcopy(compact or {})
    mode = scene_behavior_mode if scene_behavior_mode in BOUNDARY_MODE_FIELDS else "核查取证型"
    archetype = _as_text(compact.get("behavior_archetype")) or "求助配合型"
    defaults = get_behavior_archetype_defaults(archetype)
    preset_scores = apply_opening_preset(compact, compact.get("opening_preset"))

    primary_key, secondary_key = BOUNDARY_MODE_FIELDS[mode]
    boundary_primary = _as_text_list(compact.get("boundary_primary"), limit=6)
    boundary_secondary = _as_text_list(compact.get("boundary_secondary"), limit=6)

    person: dict[str, Any] = {
        "name": _as_text(compact.get("name")),
        "role_type": _as_text(compact.get("role_type")) or "相关人员",
        "status": _as_text(compact.get("status")) or "正常",
        "behavior_archetype": archetype,
        "opening_preset": infer_opening_preset(compact),
        "current_goal": _as_text(compact.get("current_goal")),
        "core_concern": _as_text(compact.get("core_concern")),
        "trigger_points": _as_text_list(compact.get("trigger_points"), limit=3),
        "calming_points": _as_text_list(compact.get("calming_points"), limit=3),
        "cannot_answer": _as_text_list(compact.get("cannot_answer"), limit=6),
        "does_not_know": _as_text_list(compact.get("cannot_answer"), limit=6),
        "scene_behavior_mode": mode,
        "impairment_state": _as_text(compact.get("impairment_state")),
        "relationship_pressure": _as_text_list(compact.get("relationship_pressure"), limit=2),
        "surface_stance": _as_text(compact.get("surface_stance")),
        "pressure_response": _as_text(compact.get("pressure_response")),
        "interaction_style": defaults.get("interaction_style", "配合型"),
        "police_attitude": defaults.get("police_attitude", "主动求助"),
        "personality": defaults.get("personality", ""),
        "speaking_style": defaults.get("speaking_style", ""),
        **preset_scores,
        primary_key: boundary_primary,
        secondary_key: boundary_secondary,
    }

    if not person["trigger_points"]:
        person["trigger_points"] = _as_text_list(defaults.get("trigger_points"), limit=3)
    if not person["calming_points"]:
        person["calming_points"] = _as_text_list(defaults.get("calming_points"), limit=3)
    if not person["surface_stance"]:
        person["surface_stance"] = _as_text(defaults.get("surface_stance"))
    if not person["pressure_response"]:
        person["pressure_response"] = _as_text(defaults.get("pressure_response"))

    if mode == "核查取证型":
        person["knows_facts"] = boundary_primary
        person["hidden_truths"] = boundary_secondary
    elif mode == "调解型":
        person["conflict_core"] = boundary_primary
        person["acceptable_outcomes"] = boundary_secondary
    elif mode == "危机干预型":
        person["trigger_sources"] = boundary_primary
        person["concerned_targets"] = boundary_secondary
    elif mode == "管控型":
        person["escalation_actions"] = boundary_primary
        person["deescalation_conditions"] = boundary_secondary

    from .persona_engine import infer_persona_template

    template = infer_persona_template(person)
    person.setdefault("personality", template.get("personality") or defaults.get("personality", ""))
    person.setdefault("speaking_style", template.get("speaking_style") or defaults.get("speaking_style", ""))
    person["compact_v1"] = True
    return person
