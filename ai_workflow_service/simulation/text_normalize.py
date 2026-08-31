"""Shared text normalization for dialogue and role speech."""

from __future__ import annotations

import codecs
import re


_LITERAL_UNICODE_CHUNK = re.compile(r"(?:\\u|\\U|/u|/U|[Uu])([0-9a-fA-F]{4})")
_LITERAL_UNICODE_RUN = re.compile(
    r"(?:(?:\\u|\\U|/u|/U|[Uu])[0-9a-fA-F]{4}){2,}"
)


def _count_cjk(value: str) -> int:
    return sum(1 for char in value if "\u4e00" <= char <= "\u9fff")


def decode_literal_unicode_escapes(value: str) -> str:
    """Decode malformed unicode dumps like `U884cU6211` back to readable CJK."""
    if not value or not isinstance(value, str):
        return value
    if not _LITERAL_UNICODE_RUN.search(value):
        if "\\u" in value or "\\U" in value:
            try:
                escaped = value.encode("utf-8", errors="surrogatepass").decode("unicode_escape")
                if _count_cjk(escaped) > _count_cjk(value):
                    return escaped
            except Exception:
                pass
            try:
                escaped = codecs.decode(value, "unicode_escape")
                if isinstance(escaped, str) and _count_cjk(escaped) > _count_cjk(value):
                    return escaped
            except Exception:
                pass
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
    return repaired if _count_cjk(repaired) > _count_cjk(value) else value
