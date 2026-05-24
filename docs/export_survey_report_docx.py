# -*- coding: utf-8 -*-
"""从 01-调研报告.md 导出 Word（无 Markdown 锚点链接，可直接交付）。"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

_DIR = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(_DIR, "01-调研报告.md")
OUT = os.path.join(_DIR, "AI虚拟警情处置模拟训练平台-调研报告.docx")


def clean_markdown_for_word(text: str) -> str:
    """去掉目录锚点、水平线，规范化空白。"""
    lines: list[str] = []
    for line in text.splitlines():
        # [引言](#一引言) -> 引言
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        if line.strip() in ("---", "***", "___"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"


def main() -> None:
    if not os.path.isfile(MD_PATH):
        raise FileNotFoundError(MD_PATH)
    raw = open(MD_PATH, encoding="utf-8").read()
    clean = clean_markdown_for_word(raw)
    out_path = OUT
    if os.path.isfile(OUT):
        try:
            os.remove(OUT)
        except PermissionError:
            from datetime import datetime

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = OUT.replace(".docx", f"-{stamp}.docx")
            print(f"WARN: 原文件被占用，将写入: {out_path}")
    export_with_pandoc_to(clean, out_path)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"OK: {out_path}")
    print(f"Source: {MD_PATH}")
    print(f"Size: {size_kb:.1f} KB")


def export_with_pandoc_to(clean_md: str, destination: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(clean_md)
        tmp_path = tmp.name
    try:
        cmd = [
            "pandoc",
            tmp_path,
            "-o",
            destination,
            "--from",
            "markdown",
            "--to",
            "docx",
            "--standalone",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
