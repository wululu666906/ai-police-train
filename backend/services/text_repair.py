from __future__ import annotations

import codecs
import re
from typing import Any


MOJIBAKE_MARKERS = ("å", "æ", "ç", "é", "è", "ä", "â", "ï", "ô", "€", "™", "�")
_LITERAL_UNICODE_CHUNK = re.compile(r"(?:\\u|\\U|/u|/U|[Uu])([0-9a-fA-F]{4})")
_LITERAL_UNICODE_RUN = re.compile(
    r"(?:(?:\\u|\\U|/u|/U|[Uu])[0-9a-fA-F]{4}){2,}"
)


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


def _decode_literal_unicode_escapes(value: str) -> str:
    """Decode malformed unicode dumps like `U884cU6211` / `\\u884c\\u6211` back to CJK."""
    if not value or not _LITERAL_UNICODE_RUN.search(value):
        return value

    def replace_run(match: re.Match[str]) -> str:
        chunk = match.group(0)
        codes = _LITERAL_UNICODE_CHUNK.findall(chunk)
        if len(codes) < 2:
            return chunk
        try:
            decoded = "".join(chr(int(code, 16)) for code in codes)
        except ValueError:
            return chunk
        if _count_cjk(decoded) >= max(1, len(codes) // 3) or any(
            "\u3000" <= char <= "\u303f" or "\uff00" <= char <= "\uffef" for char in decoded
        ):
            return decoded
        return chunk

    repaired = _LITERAL_UNICODE_RUN.sub(replace_run, value)
    if repaired != value and _looks_better(value, repaired):
        return repaired
    if "\\u" in value or "\\U" in value:
        try:
            escaped = value.encode("utf-8", errors="surrogatepass").decode("unicode_escape")
            if _looks_better(value, escaped):
                return escaped
        except Exception:
            pass
        try:
            escaped = codecs.decode(value, "unicode_escape")
            if isinstance(escaped, str) and _looks_better(value, escaped):
                return escaped
        except Exception:
            pass
    return repaired if _count_cjk(repaired) > _count_cjk(value) else value


def repair_text(value: str) -> str:
    if not value or not isinstance(value, str):
        return value
    value = _decode_literal_unicode_escapes(value)
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
