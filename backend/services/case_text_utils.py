"""Text cleaning helpers for case source material."""

from __future__ import annotations

import re
from typing import Any

_ARTIFACT_RE = re.compile(
    r"(?:---\s*)?块\s*\d+\s*/\s*(?:docx_xml_text|docx_xml|image_ocr|ocr|table|paragraph|body|段落|正文|图片OCR|表格)[^\n。；]*(?:---)?|"
    r"(?:---\s*)?\d+\s*/\s*(?:docx_xml_text|docx_xml|image_ocr|ocr|table|paragraph|body|段落|正文)[^\n。；]*(?:---)?|"
    r"(?:---\s*)?(?:docx_xml_text|docx_xml|paragraph|body|段落|正文)\s*/\s*(?:docx_xml|body|正文)[^\n。；]*(?:---)?|"
    r"```(?:json|markdown|text)?|```",
    flags=re.IGNORECASE,
)

_DOCUMENT_SECTION_NOISE_RE = re.compile(
    r"^\s*(?:（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)|[一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十]+组)[\s　]*"
    r"(?:证据|书证|物证|证人证言|被害人供述|被告人供述|鉴定意见|勘验|检查|辨认|视听资料|电子数据|到案经过|户籍证明|前科材料|判决书|裁定书)"
    r"[\s\S]{0,24}$"
)

_INLINE_SECTION_NOISE_RE = re.compile(
    r"(?:^|[。；\n])\s*(?:（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)|[一二三四五六七八九十]+[、.．])\s*"
    r"(?:证据|书证|物证|证人证言|被害人供述|被告人供述|鉴定意见|勘验|检查|辨认|视听资料|电子数据|到案经过|户籍证明|前科材料)"
    r"(?:[。；：:，,、\s]|$)"
)


def strip_document_artifacts(value: Any) -> str:
    text = str(value or "").replace("\r", "")
    text = _ARTIFACT_RE.sub("", text)
    text = re.sub(r"【文档识别结果】", "", text)
    text = re.sub(r"说明：以下内容按\s*(?:DOCX|PDF|OCR)[^\n]*", "", text, flags=re.IGNORECASE)
    text = _INLINE_SECTION_NOISE_RE.sub(lambda match: match.group(0)[0] if match.group(0)[:1] in "。；\n" else "", text)
    cleaned_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if _DOCUMENT_SECTION_NOISE_RE.match(line):
            continue
        line = re.sub(r"\s*---\s*$", "", line).strip()
        if re.fullmatch(r"(?:块\s*)?\d+|[一二三四五六七八九十]+|[（(][一二三四五六七八九十]+[）)]", line):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"([。！？；])\s*[。！？；]+", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
