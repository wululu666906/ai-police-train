"""Import and auto-generate assessment points from files, text, or case templates."""

from __future__ import annotations

import json
import re
from typing import Any

from .llm_provider import create_json_chat_completion, extract_json_payload, get_chat_model
from .ai_roles import get_assessment_point_officer_prompts
from .scene_bucket_service import (
    BUCKET_LABELS,
    SCENE_BUCKETS,
    format_scenes_for_officer_prompt,
    normalize_scene_names,
    resolve_scene_bucket,
    suggest_standard_scene_name,
)
from .stage_config_service import (
    infer_assessment_point_content,
    infer_scene_behavior_mode,
    infer_scene_kind,
    normalize_case_template_key,
    normalize_stage,
)

_LINE_SPLIT_RE = re.compile(
    r"(?m)^(?:\d+[\.\、\)]\s*|[-*•]\s+|#{1,3}\s+|[一二三四五六七八九十]+[、\.]\s*)"
)
_LABEL_CONTENT_RE = re.compile(r"^(.{2,40}?)[：:]\s*(.+)$", re.DOTALL)


def _dedupe_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        output.append(clean)
    return output


def _slug_point_id(label: str, index: int) -> str:
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", str(label or "").strip().lower()).strip("_")
    return f"ap_{text or index}"


def _safe_weight(value: Any, default: int = 10) -> int:
    try:
        return max(1, min(30, int(value)))
    except (TypeError, ValueError):
        return default


def _normalize_raw_point(raw: dict[str, Any], index: int) -> dict[str, Any]:
    label = str(raw.get("label") or raw.get("name") or raw.get("title") or "").strip()
    content = str(raw.get("content") or raw.get("requirement") or raw.get("description") or "").strip()
    if not label and content:
        parts = content.split("：", 1)
        if len(parts) == 2 and len(parts[0]) <= 40:
            label, content = parts[0].strip(), parts[1].strip()
    if not label:
        label = f"考察点{index}"
    category = str(raw.get("category") or "procedure").strip() or "procedure"
    if not content:
        content = infer_assessment_point_content(label, category=category)
    keywords = raw.get("keywords")
    if isinstance(keywords, str):
        keywords = [item.strip() for item in re.split(r"[,，\n]", keywords) if item.strip()]
    return {
        "id": str(raw.get("id") or _slug_point_id(label, index)).strip(),
        "label": label,
        "content": content,
        "category": category,
        "required": raw.get("required") is not False,
        "weight": _safe_weight(raw.get("weight", 10)),
        "keywords": _dedupe_strings(keywords if isinstance(keywords, list) else []),
        "knowledge_refs": _dedupe_strings(raw.get("knowledge_refs") if isinstance(raw.get("knowledge_refs"), list) else []),
    }


def parse_text_to_assessment_points(text: str) -> list[dict[str, Any]]:
    """Rule-based split: numbered/bullet lines or label：content pairs."""
    raw_text = str(text or "").strip()
    if not raw_text:
        return []

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict) and isinstance(parsed.get("assessment_points"), list):
            return [_normalize_raw_point(item, idx) for idx, item in enumerate(parsed["assessment_points"], 1) if isinstance(item, dict)]
        if isinstance(parsed, list):
            return [_normalize_raw_point(item, idx) for idx, item in enumerate(parsed, 1) if isinstance(item, dict)]
    except Exception:
        pass

    chunks = [part.strip() for part in _LINE_SPLIT_RE.split(raw_text) if part.strip()]
    if len(chunks) <= 1:
        chunks = [line.strip() for line in raw_text.splitlines() if line.strip()]

    points: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        label = ""
        content = chunk
        match = _LABEL_CONTENT_RE.match(chunk.replace("\n", " "))
        if match:
            label = match.group(1).strip()
            content = match.group(2).strip()
        elif "：" in chunk:
            head, tail = chunk.split("：", 1)
            if len(head) <= 40:
                label, content = head.strip(), tail.strip()
        points.append(_normalize_raw_point({"label": label, "content": content}, index))
    return points


def list_builtin_templates() -> list[dict[str, Any]]:
    """Expose built-in stage templates for admin UI."""
    catalog: list[dict[str, Any]] = []
    presets = [
        ("通用", "现场初查", "初始接触", "核实身份、经过与现场风险。"),
        ("通用", "重点询问", "关键压实", "核实时间线、矛盾点与后续处置。"),
        ("酒驾醉驾", "现场酒驾查处", "现场处置", "规范告知并实施呼气酒精检测。"),
        ("交通事故", "事故现场处置", "现场处置", "保护现场、核实车辆人员并固定证据。"),
        ("邻里/家庭纠纷", "纠纷现场调解", "现场处置", "分离双方、核实关系与矛盾经过。"),
    ]
    for case_type, scene_name, stage_name, stage_goal in presets:
        stage = normalize_stage(
            {"stage_name": stage_name, "stage_goal": stage_goal, "assessment_points": []},
            1,
            case_type=case_type,
            scene_name=scene_name,
        )
        catalog.append(
            {
                "template_key": f"{case_type}|{scene_name}|{stage_name}",
                "case_type": case_type,
                "scene_name": scene_name,
                "stage_name": stage_name,
                "stage_goal": stage_goal,
                "behavior_mode": infer_scene_behavior_mode(scene_name, case_type, [stage]),
                "scene_kind": infer_scene_kind(scene_name, stage_name),
                "point_count": len(stage.get("assessment_points") or []),
                "action_count": len(stage.get("action_catalog") or []),
                "assessment_points": stage.get("assessment_points") or [],
                "action_catalog": stage.get("action_catalog") or [],
            }
        )
    return catalog


def apply_template_to_points(
    points: list[dict[str, Any]],
    *,
    case_type: str = "",
    scene_name: str = "",
    stage_name: str = "考察点",
    stage_goal: str = "",
) -> list[dict[str, Any]]:
    """Merge user/imported points with built-in template defaults (keywords, weight)."""
    stage = normalize_stage(
        {
            "stage_name": stage_name,
            "stage_goal": stage_goal or "围绕本场景关键事实展开问询和处置。",
            "assessment_points": points,
        },
        1,
        case_type=case_type,
        scene_name=scene_name,
    )
    return stage.get("assessment_points") or []


def _build_case_context(case_info: dict[str, Any], scene_info: dict[str, Any]) -> str:
    parts = [
        f"案件标题：{case_info.get('title') or case_info.get('case_name') or ''}",
        f"案件类型：{case_info.get('case_type') or ''}",
        f"案情摘要：{case_info.get('case_background') or case_info.get('background') or ''}",
        f"场景名称：{scene_info.get('name') or scene_info.get('scene_name') or ''}",
        f"场景说明：{scene_info.get('description') or ''}",
        f"接警简报：{scene_info.get('dispatch_brief') or ''}",
        f"现场印象：{scene_info.get('first_impression') or ''}",
    ]
    return "\n".join(part for part in parts if str(part).split("：", 1)[-1].strip())


ASSESSMENT_GEN_PROMPT = """你是警务训练「考察点设计」专家。根据案件与场景信息，输出可操作的考察点列表（用于对话训练与评分）。

要求：
1. 每条考察点必须可核查：学员在对话或动作中能否被观察到完成。
2. 输出 4-8 条，覆盖：身份/关系、时间地点、风险、证据、处置路径等（按场景取舍）。
3. 不要复述空泛口号；label 简短（≤20字），content 写清「学员应做到什么」。
4. keywords 提取 2-5 个对话中可能出现的核查词。
5. required：关键项 true，辅助项 false；weight：必考 12-15，选考 8-10。
6. 只输出 JSON：{{"assessment_points":[{{"label":"","content":"","category":"procedure|risk|evidence","required":true,"weight":10,"keywords":[]}}]}}"""


def generate_assessment_points_with_llm(
    case_info: dict[str, Any],
    scene_info: dict[str, Any],
    *,
    source_text: str = "",
    extra_hint: str = "",
) -> list[dict[str, Any]]:
    context = _build_case_context(case_info, scene_info)
    if source_text.strip():
        context += f"\n\n参考材料节选：\n{source_text.strip()[:6000]}"
    if extra_hint.strip():
        context += f"\n\n教官补充要求：{extra_hint.strip()}"

    prompt = f"{ASSESSMENT_GEN_PROMPT}\n\n{context}"
    response = create_json_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.35,
        model=get_chat_model(),
        max_tokens=1800,
    )
    payload = extract_json_payload(response) or {}
    raw_points = payload.get("assessment_points") if isinstance(payload, dict) else payload
    if not isinstance(raw_points, list):
        return []
    points = [_normalize_raw_point(item, idx) for idx, item in enumerate(raw_points, 1) if isinstance(item, dict)]
    case_type = str(case_info.get("case_type") or "").strip()
    scene_name = str(scene_info.get("name") or scene_info.get("scene_name") or "").strip()
    return apply_template_to_points(points, case_type=case_type, scene_name=scene_name)


def generate_assessment_points(
    case_info: dict[str, Any],
    scene_info: dict[str, Any],
    *,
    source_text: str = "",
    template_key: str = "",
    extra_hint: str = "",
    use_llm: bool = True,
) -> dict[str, Any]:
    case_type = normalize_case_template_key(str(case_info.get("case_type") or ""))
    scene_name = str(scene_info.get("name") or scene_info.get("scene_name") or "训练场景").strip()
    stage_goal = str(scene_info.get("stage_goal") or scene_info.get("description") or "").strip()

    if template_key:
        for item in list_builtin_templates():
            if item.get("template_key") == template_key:
                points = [dict(point) for point in item.get("assessment_points") or []]
                return {
                    "points": points,
                    "source": "template",
                    "template_key": template_key,
                    "message": f"已应用内置模板（{len(points)} 条）",
                }

    if source_text.strip():
        parsed = parse_text_to_assessment_points(source_text)
        if parsed:
            enriched = apply_template_to_points(parsed, case_type=case_type, scene_name=scene_name, stage_goal=stage_goal)
            return {
                "points": enriched,
                "source": "text_parse",
                "message": f"已从文本解析 {len(enriched)} 条考察点",
            }

    warning = ""
    if use_llm:
        try:
            llm_points = generate_assessment_points_with_llm(
                case_info,
                scene_info,
                source_text=source_text,
                extra_hint=extra_hint,
            )
            if llm_points:
                return {
                    "points": llm_points,
                    "source": "llm",
                    "message": f"已根据案件生成 {len(llm_points)} 条考察点",
                }
        except Exception as exc:
            warning = str(exc)

    stage = normalize_stage(
        {"stage_name": "考察点", "stage_goal": stage_goal, "assessment_points": []},
        1,
        case_type=case_type,
        scene_name=scene_name,
    )
    points = stage.get("assessment_points") or []
    result: dict[str, Any] = {
        "points": points,
        "source": "builtin_template",
        "message": f"已使用「{case_type}」类内置模板（{len(points)} 条）",
    }
    if warning:
        result["warning"] = warning
    return result


_SECTION_LINE_RE = re.compile(
    r"^\s*[【\[]?\s*(接警|现场|询问|讯问|信息初核|初查|笔录|intake|onsite|investigation)\s*[】\]]?\s*$",
    re.IGNORECASE,
)


def _bucket_from_section_header(header: str) -> str:
    text = str(header or "").strip().lower()
    if any(k in text for k in ("接警", "报警", "接处警", "信息初核", "intake")):
        return "intake"
    if any(k in text for k in ("询问", "讯问", "审讯", "笔录", "压实", "investigation")):
        return "investigation"
    return "onsite"


def parse_text_to_bucketed_points(text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse text with optional 【接警】【现场】【询问】 section headers."""
    raw = str(text or "").strip()
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in SCENE_BUCKETS}
    if not raw:
        return buckets

    current_bucket = "onsite"
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        chunk = "\n".join(buffer).strip()
        buffer.clear()
        if not chunk:
            return
        for point in parse_text_to_assessment_points(chunk):
            buckets[current_bucket].append(point)

    has_section = False
    for line in raw.splitlines():
        if _SECTION_LINE_RE.match(line.strip()):
            has_section = True
            flush_buffer()
            current_bucket = _bucket_from_section_header(line)
            continue
        buffer.append(line)
    flush_buffer()

    if not has_section:
        flat = parse_text_to_assessment_points(raw)
        if flat:
            buckets["onsite"] = flat
    return buckets


def build_officer_user_prompt(
    case_info: dict[str, Any],
    scenes: list[dict[str, Any]],
    *,
    source_text: str = "",
    extra_hint: str = "",
) -> str:
    """Build user prompt without str.format() — case text may contain `{`/`}`."""
    scenes_list = format_scenes_for_officer_prompt(scenes)
    excerpt = str(source_text or "").strip()[:6000] or "（无额外材料）"
    hint = str(extra_hint or "").strip() or "（无）"
    return (
        "请根据以下案件与场景列表，为 intake / onsite / investigation 三个场景桶分别生成考察点。\n\n"
        f"【案件信息】\n{_build_full_case_context(case_info)}\n\n"
        f"【当前场景列表（名称用于对齐，可建议改名）】\n{scenes_list}\n\n"
        f"【参考材料】\n{excerpt}\n\n"
        f"【补充要求】\n{hint}"
    )


def _looks_like_assessment_paste(text: str) -> bool:
    """Avoid treating full case narrative as a bullet list."""
    raw = str(text or "").strip()
    if not raw:
        return False
    if _SECTION_LINE_RE.search(raw):
        return True
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(lines) > 40:
        return False
    list_like = sum(1 for line in lines if re.match(r"^\d+[\.\、\)]\s+|^[-*•]\s+", line))
    return list_like >= 2 or (len(lines) <= 12 and list_like >= 1)


def _build_full_case_context(case_info: dict[str, Any]) -> str:
    parts = [
        f"案件标题：{case_info.get('title') or case_info.get('case_name') or ''}",
        f"案件类型：{case_info.get('case_type') or ''}",
        f"案情摘要：{case_info.get('case_background') or case_info.get('background') or ''}",
        f"全文材料：{(case_info.get('full_narrative') or case_info.get('original_content') or '')[:4000]}",
    ]
    return "\n".join(part for part in parts if str(part).split("：", 1)[-1].strip())


def generate_bucketed_assessment_points_with_officer(
    case_info: dict[str, Any],
    scenes: list[dict[str, Any]],
    *,
    source_text: str = "",
    extra_hint: str = "",
) -> dict[str, Any]:
    """LLM: dedicated assessment point officer → three scene buckets."""
    officer = get_assessment_point_officer_prompts()
    user_prompt = build_officer_user_prompt(
        case_info,
        scenes,
        source_text=source_text,
        extra_hint=extra_hint,
    )
    response = create_json_chat_completion(
        messages=[
            {"role": "system", "content": officer["system_prompt"]},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        model=get_chat_model(),
        max_tokens=3200,
    )
    payload = extract_json_payload(response) or {}
    if not isinstance(payload, dict):
        raise ValueError("考察点专员返回格式无效")
    return payload


def _extract_points_from_bucket_payload(bucket_data: Any) -> list[dict[str, Any]]:
    if isinstance(bucket_data, list):
        raw_list = bucket_data
    elif isinstance(bucket_data, dict):
        raw_list = bucket_data.get("assessment_points") or []
    else:
        raw_list = []
    if not isinstance(raw_list, list):
        return []
    return [_normalize_raw_point(item, idx) for idx, item in enumerate(raw_list, 1) if isinstance(item, dict)]


def _extend_warnings(warnings: list[str], raw_warnings: Any) -> None:
    if isinstance(raw_warnings, list):
        warnings.extend(str(item).strip() for item in raw_warnings if str(item or "").strip())
    elif raw_warnings not in (None, ""):
        warnings.append(str(raw_warnings).strip())


def _fill_builtin_bucket_points(
    bucket_points: dict[str, list[dict[str, Any]]],
    *,
    case_type: str,
    name_suggestions: dict[str, Any],
) -> None:
    """When AI/paste produced nothing, load built-in templates per intake/onsite/investigation."""
    for bucket in SCENE_BUCKETS:
        if bucket_points.get(bucket):
            continue
        scene_name = str(name_suggestions.get(bucket) or suggest_standard_scene_name(bucket)).strip()
        stage = normalize_stage(
            {"stage_name": "考察点", "assessment_points": []},
            1,
            case_type=case_type,
            scene_name=scene_name,
        )
        bucket_points[bucket] = stage.get("assessment_points") or []


def distribute_assessment_points_to_scenes(
    case_info: dict[str, Any],
    scenes: list[dict[str, Any]],
    *,
    source_text: str = "",
    reference_text: str = "",
    extra_hint: str = "",
    use_llm: bool = True,
    rename_scenes: bool = True,
) -> dict[str, Any]:
    """
    One-shot: generate points for intake/onsite/investigation and assign to all scenes by name rules.
    """
    case_type = normalize_case_template_key(str(case_info.get("case_type") or ""))
    working_scenes = [dict(s) for s in scenes if isinstance(s, dict)]
    if not working_scenes:
        return {"assignments": [], "message": "案件下没有场景", "total_points": 0}

    normalized_scenes = normalize_scene_names(working_scenes, rename=rename_scenes)
    bucket_points: dict[str, list[dict[str, Any]]] = {key: [] for key in SCENE_BUCKETS}
    source = "builtin"
    warnings: list[str] = []
    name_suggestions: dict[str, Any] = {}

    pasted = source_text.strip()
    if pasted and _looks_like_assessment_paste(pasted):
        parsed_buckets = parse_text_to_bucketed_points(pasted)
        if any(parsed_buckets.values()):
            bucket_points = parsed_buckets
            source = "text_sections"
        else:
            flat = parse_text_to_assessment_points(pasted)
            if flat and len(normalized_scenes) == 1:
                bucket = resolve_scene_bucket(
                    str(normalized_scenes[0].get("name") or ""),
                    scene_index=0,
                    scene_count=1,
                )
                bucket_points[bucket] = flat
                source = "text_parse"

    llm_reference = reference_text.strip() or _build_full_case_context(case_info)
    if pasted and not _looks_like_assessment_paste(pasted) and not reference_text.strip():
        llm_reference = pasted
    if use_llm and not any(bucket_points.values()):
        try:
            officer_payload = generate_bucketed_assessment_points_with_officer(
                case_info,
                normalized_scenes,
                source_text=llm_reference,
                extra_hint=extra_hint,
            )
            raw_buckets = officer_payload.get("buckets") if isinstance(officer_payload.get("buckets"), dict) else {}
            for bucket in SCENE_BUCKETS:
                bucket_points[bucket] = _extract_points_from_bucket_payload(raw_buckets.get(bucket))
            name_suggestions = officer_payload.get("scene_name_suggestions") if isinstance(
                officer_payload.get("scene_name_suggestions"), dict
            ) else {}
            _extend_warnings(warnings, officer_payload.get("warnings"))
            source = "officer_llm"
        except Exception as exc:
            warnings.append(f"AI 分场景失败，已用内置模板：{exc}")
            _fill_builtin_bucket_points(bucket_points, case_type=case_type, name_suggestions=name_suggestions)

    if not any(bucket_points.values()):
        warnings.append("未从 AI 或粘贴内容解析到考察点，已使用内置模板补全")
        _fill_builtin_bucket_points(bucket_points, case_type=case_type, name_suggestions=name_suggestions)
        if source == "builtin":
            source = "builtin_template"
        elif source == "officer_llm":
            source = "officer_llm+builtin_template"

    # Enrich each bucket's points once (template keywords/weight)
    for bucket in SCENE_BUCKETS:
        if not bucket_points[bucket]:
            continue
        scene_name = name_suggestions.get(bucket) or suggest_standard_scene_name(bucket)
        bucket_points[bucket] = apply_template_to_points(
            bucket_points[bucket],
            case_type=case_type,
            scene_name=scene_name,
        )

    assignments: list[dict[str, Any]] = []
    assigned_buckets: set[str] = set()
    for index, scene in enumerate(normalized_scenes):
        scene_id = scene.get("id")
        scene_name = str(scene.get("name") or "").strip()
        bucket = str(scene.get("_bucket") or resolve_scene_bucket(scene_name, scene_index=index, scene_count=len(normalized_scenes)))
        points = list(bucket_points.get(bucket) or [])
        suggested_name = str(name_suggestions.get(bucket) or suggest_standard_scene_name(bucket)).strip()

        if bucket in assigned_buckets:
            if points:
                warnings.append(f"多个场景归入「{BUCKET_LABELS.get(bucket, bucket)}」，仅首个场景写入考察点")
            points = []
        else:
            assigned_buckets.add(bucket)

        assignments.append(
            {
                "scene_id": scene_id,
                "scene_name": scene_name,
                "suggested_name": suggested_name,
                "bucket": bucket,
                "bucket_label": BUCKET_LABELS.get(bucket, bucket),
                "points": points,
                "point_count": len(points),
                "renamed_from": scene.get("_renamed_from"),
            }
        )

    total = sum(len(item.get("points") or []) for item in assignments)
    return {
        "assignments": assignments,
        "scene_name_suggestions": name_suggestions or {b: suggest_standard_scene_name(b) for b in SCENE_BUCKETS},
        "source": source,
        "warnings": warnings,
        "total_points": total,
        "message": f"已为 {len(assignments)} 个场景分配共 {total} 条考察点（{source}）",
    }


def merge_assessment_point_lists(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    mode: str = "append",
) -> list[dict[str, Any]]:
    if mode == "replace":
        base = []
    else:
        base = [dict(item) for item in existing if isinstance(item, dict)]
    seen_labels = {str(item.get("label") or "").strip() for item in base}
    for index, item in enumerate(incoming, start=len(base) + 1):
        if not isinstance(item, dict):
            continue
        normalized = _normalize_raw_point(item, index)
        label = normalized["label"]
        if label in seen_labels:
            continue
        seen_labels.add(label)
        base.append(normalized)
    return base
