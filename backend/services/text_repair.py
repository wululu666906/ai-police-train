from __future__ import annotations

from typing import Any


MOJIBAKE_MARKERS = ("å", "æ", "ç", "é", "è", "ä", "â", "ï", "ô", "€", "™", "�")


def _count_cjk(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def _looks_better(original: str, repaired: str) -> bool:
    if not repaired or repaired == original:
        return False
    original_cjk = _count_cjk(original)
    repaired_cjk = _count_cjk(repaired)
    if repaired_cjk > original_cjk:
        return True
    if repaired_cjk == original_cjk:
        original_markers = sum(original.count(marker) for marker in MOJIBAKE_MARKERS)
        repaired_markers = sum(repaired.count(marker) for marker in MOJIBAKE_MARKERS)
        return repaired_markers < original_markers
    return False


def repair_text(value: str) -> str:
    if not value or not isinstance(value, str):
        return value
    if not any(marker in value for marker in MOJIBAKE_MARKERS):
        return value

    try:
        repaired = value.encode("latin1").decode("utf-8")
        if _looks_better(value, repaired):
            return repaired
    except Exception:
        return value
    return value


def repair_payload(value: Any) -> Any:
    if isinstance(value, str):
        return repair_text(value)
    if isinstance(value, list):
        return [repair_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_payload(item) for key, item in value.items()}
    return value
