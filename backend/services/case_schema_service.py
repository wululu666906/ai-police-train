from __future__ import annotations

import copy
from typing import Any

from .role_compact_service import expand_role_compact_to_person, person_to_role_compact_view

SCHEMA_VERSION = "2026.06.compact-v1"

PERSON_COMPACT_V1_FIELDS: tuple[str, ...] = (
    "person_id",
    "name",
    "aliases",
    "role_type",
    "status",
    "behavior_archetype",
    "opening_preset",
    "current_goal",
    "core_concern",
    "relationship_pressure",
    "surface_stance",
    "pressure_response",
    "trigger_points",
    "calming_points",
    "cannot_answer",
    "boundary_primary",
    "boundary_secondary",
    "impairment_state",
)

PERSON_CANONICAL_FIELDS: tuple[str, ...] = (
    "behavior_archetype",
    "opening_preset",
    "police_attitude",
    "scene_behavior_mode",
    "current_goal",
    "core_concern",
    "relationship_pressure",
    "surface_stance",
    "pressure_response",
    "trigger_points",
    "calming_points",
    "emotion_level",
    "cooperation_level",
    "risk_level",
    "clarity_level",
    "known_key_points",
    "withheld_key_points",
    "conflict_core",
    "acceptable_outcomes",
    "no_go_topics",
    "trigger_sources",
    "concerned_targets",
    "taboo_actions",
    "escalation_actions",
    "deescalation_conditions",
    "impairment_state",
    "cannot_answer",
)

PERSON_ALIAS_TO_CANONICAL: dict[str, str] = {
    "authority_attitude": "police_attitude",
    "current_need": "current_goal",
    "private_drive": "current_goal",
    "weakness": "core_concern",
    "stress_response": "pressure_response",
    "public_mask": "surface_stance",
    "trigger_topics": "trigger_points",
    "knows_facts": "known_key_points",
    "hidden_truths": "withheld_key_points",
    "does_not_know": "cannot_answer",
}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        seen = set()
        for item in value:
            text = _as_text(item)
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        lines = [item.strip() for item in raw.splitlines() if item.strip()]
        if lines:
            return _as_text_list(lines)
    return []


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return ""


_ALIAS_LIST_FIELDS = frozenset({"trigger_topics", "knows_facts", "hidden_truths", "does_not_know"})

PERSON_PROFILE_PRESERVE_TEXT_FIELDS: tuple[str, ...] = (
    "self_image",
    "current_need",
    "authority_attitude",
    "stress_response",
    "public_mask",
    "private_drive",
    "persona_template_version",
)

PERSON_PROFILE_PRESERVE_LIST_FIELDS: tuple[str, ...] = (
    "protected_targets",
    "feared_people",
    "conflict_targets",
    "feared_consequences",
    "trigger_topics",
    "coping_patterns",
)


def sync_person_alias_fields(person: dict[str, Any]) -> dict[str, Any]:
    """Mirror canonical fields onto legacy alias keys so persisted JSON stays consistent."""
    synced = copy.deepcopy(person or {})
    for alias, target in PERSON_ALIAS_TO_CANONICAL.items():
        if alias in _ALIAS_LIST_FIELDS:
            canonical_list = _as_text_list(synced.get(target))
            if canonical_list:
                synced[alias] = copy.deepcopy(canonical_list)
            continue
        canonical_text = _as_text(synced.get(target))
        if canonical_text:
            synced[alias] = canonical_text
    return synced


def canonicalize_person_payload(
    person: dict[str, Any] | None,
    *,
    scene_behavior_mode: str = "",
) -> tuple[dict[str, Any], list[str]]:
    source = dict(person or {})
    warnings: list[str] = []

    mode = _as_text(scene_behavior_mode) or _as_text(source.get("scene_behavior_mode")) or "核查取证型"
    expanded = expand_role_compact_to_person(source, scene_behavior_mode=mode)
    canonical = copy.deepcopy(expanded)
    if _as_text(source.get("person_id")):
        canonical["person_id"] = _as_text(source.get("person_id"))
    aliases = _as_text_list(source.get("aliases"))
    if aliases:
        canonical["aliases"] = aliases
    if _as_text(source.get("interaction_style")):
        canonical["interaction_style"] = _as_text(source.get("interaction_style"))
    if _as_text(source.get("personality")):
        canonical["personality"] = _as_text(source.get("personality"))
    if _as_text(source.get("speaking_style")):
        canonical["speaking_style"] = _as_text(source.get("speaking_style"))
    for alias, target in PERSON_ALIAS_TO_CANONICAL.items():
        if target in canonical and canonical.get(target) not in (None, "", []):
            continue
        if alias in source and source.get(alias) not in (None, "", []):
            canonical[target] = copy.deepcopy(source.get(alias))
            warnings.append(f"alias:{alias}->{target}")

    # Canonical text fields
    for key in (
        "behavior_archetype",
        "police_attitude",
        "scene_behavior_mode",
        "current_goal",
        "core_concern",
        "surface_stance",
        "pressure_response",
        "emotion_level",
        "cooperation_level",
        "risk_level",
        "clarity_level",
        "impairment_state",
    ):
        canonical[key] = _as_text(canonical.get(key))

    # Canonical list fields
    for key in (
        "relationship_pressure",
        "trigger_points",
        "calming_points",
        "known_key_points",
        "withheld_key_points",
        "conflict_core",
        "acceptable_outcomes",
        "no_go_topics",
        "trigger_sources",
        "concerned_targets",
        "taboo_actions",
        "escalation_actions",
        "deescalation_conditions",
    ):
        canonical[key] = _as_text_list(canonical.get(key))

    # Fill missing canonical values from legacy aliases before mirroring back.
    if not _as_text(canonical.get("current_goal")):
        canonical["current_goal"] = _first_non_empty(source.get("current_need"), source.get("private_drive"))
    if not _as_text(canonical.get("core_concern")):
        canonical["core_concern"] = _first_non_empty(source.get("weakness"))
    if not _as_text(canonical.get("police_attitude")):
        canonical["police_attitude"] = _first_non_empty(source.get("authority_attitude"))
    if not _as_text(canonical.get("pressure_response")):
        canonical["pressure_response"] = _first_non_empty(source.get("stress_response"))
    if not _as_text(canonical.get("surface_stance")):
        canonical["surface_stance"] = _first_non_empty(source.get("public_mask"))
    if not _as_text_list(canonical.get("trigger_points")):
        canonical["trigger_points"] = _as_text_list(source.get("trigger_topics"))
    if not _as_text_list(canonical.get("known_key_points")):
        canonical["known_key_points"] = _as_text_list(source.get("knows_facts"))
    if not _as_text_list(canonical.get("withheld_key_points")):
        canonical["withheld_key_points"] = _as_text_list(source.get("hidden_truths"))
    if not _as_text_list(canonical.get("cannot_answer")):
        canonical["cannot_answer"] = _as_text_list(source.get("does_not_know"))

    for key in PERSON_PROFILE_PRESERVE_TEXT_FIELDS:
        value = _first_non_empty(source.get(key), canonical.get(key))
        if value:
            canonical[key] = value
    for key in PERSON_PROFILE_PRESERVE_LIST_FIELDS:
        values = _as_text_list(source.get(key) or canonical.get(key))
        if values:
            canonical[key] = values

    canonical = sync_person_alias_fields(canonical)
    canonical["compact_v1"] = True
    return canonical, warnings


def person_compact_view(
    person: dict[str, Any] | None,
    *,
    scene_behavior_mode: str = "",
) -> dict[str, Any]:
    mode = _as_text(scene_behavior_mode) or _as_text((person or {}).get("scene_behavior_mode")) or "核查取证型"
    return person_to_role_compact_view(person, scene_behavior_mode=mode)


def migrate_structured_data_payload(structured_data: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    payload = copy.deepcopy(structured_data or {})
    warnings: list[str] = []

    persons = payload.get("persons")
    if isinstance(persons, list):
        migrated_persons = []
        for person in persons:
            canonical_person, person_warnings = canonicalize_person_payload(person if isinstance(person, dict) else {})
            migrated_persons.append(canonical_person)
            warnings.extend(person_warnings)
        payload["persons"] = migrated_persons

    payload["schema_version"] = SCHEMA_VERSION
    payload["canonical_person_fields"] = list(PERSON_CANONICAL_FIELDS)
    payload["compact_person_fields"] = list(PERSON_COMPACT_V1_FIELDS)
    payload["canonical_alias_map"] = dict(PERSON_ALIAS_TO_CANONICAL)

    if warnings:
        payload["consistency_warnings"] = sorted(set(warnings))
    else:
        payload.setdefault("consistency_warnings", [])
    return payload, sorted(set(warnings))
