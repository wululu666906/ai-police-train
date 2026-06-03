"""Scene naming rules and bucket resolution (intake / onsite / investigation)."""

from __future__ import annotations

import re
from typing import Any

SCENE_BUCKETS = ("intake", "onsite", "investigation")

STANDARD_SCENE_NAMES: dict[str, str] = {
    "intake": "接警研判",
    "onsite": "现场处置",
    "investigation": "重点询问",
}

BUCKET_LABELS: dict[str, str] = {
    "intake": "接警",
    "onsite": "现场",
    "investigation": "询问",
}

_BUCKET_KEYWORDS: dict[str, list[str]] = {
    "intake": ["接警", "报警", "接处警", "信息初核", "110", "95519"],
    "onsite": ["现场", "初查", "勘查", "处置", "出警", "到场", "控制现场"],
    "investigation": ["询问", "讯问", "审讯", "核实", "笔录", "问询", "压实", "重点问"],
}


def resolve_scene_bucket(scene_name: str, *, scene_index: int = 0, scene_count: int = 1) -> str:
    """Map scene name to intake | onsite | investigation; fallback by index when 3 scenes."""
    text = str(scene_name or "").strip()
    if text:
        for bucket, keywords in _BUCKET_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return bucket

    if scene_count == 3 and 0 <= scene_index < 3:
        return SCENE_BUCKETS[scene_index]
    if scene_count == 2:
        return SCENE_BUCKETS[min(scene_index, 1)]
    return "onsite"


def scene_name_matches_bucket(scene_name: str, bucket: str) -> bool:
    return resolve_scene_bucket(scene_name) == bucket


def suggest_standard_scene_name(bucket: str) -> str:
    return STANDARD_SCENE_NAMES.get(bucket, "训练场景")


def normalize_scene_names(scenes: list[dict[str, Any]], *, rename: bool = True) -> list[dict[str, Any]]:
    """Optionally rename scenes to standard names when bucket is clear but name is vague."""
    output: list[dict[str, Any]] = []
    count = len(scenes)
    used_names: set[str] = set()
    for index, scene in enumerate(scenes):
        row = dict(scene)
        name = str(row.get("name") or row.get("scene_name") or "").strip()
        bucket = resolve_scene_bucket(name, scene_index=index, scene_count=count)
        standard = suggest_standard_scene_name(bucket)
        vague = not name or re.search(r"^(场景|训练|未命名|\d+)", name)
        if rename and (vague or not scene_name_matches_bucket(name, bucket)):
            candidate = standard
            suffix = 2
            while candidate in used_names:
                candidate = f"{standard}{suffix}"
                suffix += 1
            row["name"] = candidate
            row["_bucket"] = bucket
            row["_renamed_from"] = name or None
        else:
            row["name"] = name or standard
            row["_bucket"] = bucket
        used_names.add(str(row["name"]))
        output.append(row)
    return output


def format_scenes_for_officer_prompt(scenes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        name = str(scene.get("name") or scene.get("scene_name") or f"场景{index}").strip()
        bucket = resolve_scene_bucket(name, scene_index=index - 1, scene_count=len(scenes))
        lines.append(
            f"- 场景{index}：{name}（系统推断类型：{BUCKET_LABELS.get(bucket, bucket)} / {bucket}）\n"
            f"  描述：{str(scene.get('description') or '').strip()[:200]}\n"
            f"  简报：{str(scene.get('dispatch_brief') or '').strip()[:120]}"
        )
    return "\n".join(lines) if lines else "（无场景）"
