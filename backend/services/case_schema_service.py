from __future__ import annotations

import copy
from typing import Any

SCHEMA_VERSION = "2026.05.canonical-v1"

PERSON_CANONICAL_FIELDS: tuple[str, ...] = (
    "behavior_archetype",
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


def canonicalize_person_payload(person: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    source = dict(person or {})
    warnings: list[str] = []

    canonical = copy.deepcopy(source)
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

    # Legacy compatibility fields are read-compatible but canonical wins on write.
    canonical["current_need"] = _first_non_empty(source.get("current_need"), canonical.get("current_goal"))
    canonical["private_drive"] = _first_non_empty(source.get("private_drive"), canonical.get("current_goal"))
    canonical["weakness"] = _first_non_empty(source.get("weakness"), canonical.get("core_concern"))
    canonical["authority_attitude"] = _first_non_empty(source.get("authority_attitude"), canonical.get("police_attitude"))
    canonical["stress_response"] = _first_non_empty(source.get("stress_response"), canonical.get("pressure_response"))
    canonical["public_mask"] = _first_non_empty(source.get("public_mask"), canonical.get("surface_stance"))
    canonical["trigger_topics"] = _as_text_list(source.get("trigger_topics") or canonical.get("trigger_points"))

    # Boundary compatibility mirrors.
    canonical["knows_facts"] = _as_text_list(source.get("knows_facts") or canonical.get("known_key_points"))
    canonical["hidden_truths"] = _as_text_list(source.get("hidden_truths") or canonical.get("withheld_key_points"))

    return canonical, warnings


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
    payload["canonical_alias_map"] = dict(PERSON_ALIAS_TO_CANONICAL)

    if warnings:
        payload["consistency_warnings"] = sorted(set(warnings))
    else:
        payload.setdefault("consistency_warnings", [])
    return payload, sorted(set(warnings))
