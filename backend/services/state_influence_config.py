"""Load state influence tables with optional admin overrides from JSON."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from . import state_influence_tables as _base

_OVERRIDES_PATH = Path(__file__).resolve().parent.parent / "config" / "state_influence_overrides.json"
_cached_tables: dict[str, Any] | None = None


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    if isinstance(override, list) and isinstance(base, list):
        if override and all(isinstance(item, dict) and "id" in item for item in override):
            by_id = {str(item.get("id")): copy.deepcopy(item) for item in base if isinstance(item, dict)}
            for item in override:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id") or "")
                if item_id in by_id:
                    by_id[item_id] = _deep_merge(by_id[item_id], item)
                else:
                    by_id[item_id] = copy.deepcopy(item)
            return list(by_id.values())
        return copy.deepcopy(override)
    return copy.deepcopy(override)


def _load_overrides_file() -> dict[str, Any]:
    if not _OVERRIDES_PATH.exists():
        return {}
    try:
        payload = json.loads(_OVERRIDES_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _base_tables() -> dict[str, Any]:
    return {
        "BAND_THRESHOLDS": copy.deepcopy(_base.BAND_THRESHOLDS),
        "AXIS_EMOTION": copy.deepcopy(_base.AXIS_EMOTION),
        "AXIS_COOPERATION": copy.deepcopy(_base.AXIS_COOPERATION),
        "AXIS_RISK": copy.deepcopy(_base.AXIS_RISK),
        "AXIS_CLARITY": copy.deepcopy(_base.AXIS_CLARITY),
        "COMBINATION_RULES": copy.deepcopy(_base.COMBINATION_RULES),
        "TRIGGER_DELTAS": copy.deepcopy(_base.TRIGGER_DELTAS),
        "ACTION_DELTAS": copy.deepcopy(_base.ACTION_DELTAS),
        "MAX_DELTA_PER_TURN": _base.MAX_DELTA_PER_TURN,
        "MAX_DELTA_FROM_CURRENT": _base.MAX_DELTA_FROM_CURRENT,
    }


def get_tables(force_reload: bool = False) -> dict[str, Any]:
    global _cached_tables
    if _cached_tables is not None and not force_reload:
        return _cached_tables
    merged = _deep_merge(_base_tables(), _load_overrides_file())
    _cached_tables = merged
    return _cached_tables


def save_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    payload = overrides if isinstance(overrides, dict) else {}
    _OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OVERRIDES_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return get_tables(force_reload=True)


def export_tables_for_admin() -> dict[str, Any]:
    tables = get_tables()
    overrides = _load_overrides_file()
    return {
        "tables": tables,
        "overrides": overrides,
        "overrides_path": str(_OVERRIDES_PATH),
        "has_overrides": bool(overrides),
    }
