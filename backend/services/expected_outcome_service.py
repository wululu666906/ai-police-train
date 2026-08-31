"""本场景考察点条目：剧本单一数据源 + AI 追加/刷新。"""

from __future__ import annotations

import re
from typing import Any

from .llm_provider import create_json_chat_completion, extract_json_payload, get_chat_model

EXPECTED_OUTCOMES_MAX_PER_SCENE = 6
EXPECTED_OUTCOMES_MIN_PER_GENERATE = 1

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[，。！？、；：,.!?;:\"'“”‘’（）()【】\[\]《》<>·…—\-]+")
_OUTCOME_STOPWORDS = {
    "能够", "可以", "应当", "应该", "需要", "要求", "迅速", "及时", "正确", "有效", "充分",
    "进行", "完成", "做到", "实现", "确保", "注意", "避免", "防止", "学员", "民警", "处置",
    "情况", "相关", "有关", "以及", "并且", "同时", "之后", "之前", "然后", "从而",
}
# 可观察短词：出现在考察点文本中则优先作为命中关键词
_OUTCOME_KEY_TERMS = (
    "报警人", "报警", "身份", "姓名", "联系方式", "电话", "时间", "地点", "地址", "在场",
    "经过", "原因", "诉求", "矛盾", "伤情", "伤员", "受伤", "流血", "危险", "风险", "安全",
    "证据", "监控", "现场", "隔离", "疏散", "控制", "警告", "告知", "劝离", "制止",
    "救护", "救护车", "急救", "派警", "增援", "武器", "刀具", "持刀", "斗殴", "冲突",
    "情绪", "安抚", "询问", "核实", "确认", "记录", "闭环", "收尾", "总结", "反馈",
    "暴力", "规模", "人数", "人员", "嫌疑人", "证人", "当事人", "被害人", "受害者",
)


def normalize_outcome_key(value: Any) -> str:
    text = _SPACE_RE.sub("", str(value or "").strip().lower())
    return _PUNCT_RE.sub("", text)


def dedupe_expected_outcomes(items: list[Any] | None) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            text = str(item.get("content") or item.get("text") or item.get("label") or "").strip()
        else:
            text = str(item or "").strip()
        key = normalize_outcome_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def cap_expected_outcomes(
    items: list[str] | None,
    limit: int = EXPECTED_OUTCOMES_MAX_PER_SCENE,
) -> tuple[list[str], bool]:
    rows = list(items or [])
    if len(rows) <= limit:
        return rows, False
    return rows[:limit], True


def finalize_expected_outcomes(
    items: list[Any] | None,
    *,
    limit: int = EXPECTED_OUTCOMES_MAX_PER_SCENE,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    deduped = dedupe_expected_outcomes(items)
    if len(deduped) < len([item for item in (items or []) if str(item or "").strip()]):
        warnings.append("已去除重复考察点")
    capped, truncated = cap_expected_outcomes(deduped, limit=limit)
    if truncated:
        warnings.append(f"考察点已截断为每场景最多 {limit} 条")
    return capped, warnings


def extract_outcome_keywords(text: str, *, limit: int = 8) -> list[str]:
    """从考察点短句抽取可观察短关键词，避免整句字面匹配导致终评全零。"""
    clean = str(text or "").strip()
    if not clean:
        return []
    compact = _SPACE_RE.sub("", clean)
    keywords: list[str] = []

    def _push(token: str) -> None:
        token = str(token or "").strip()
        if not token or token in keywords:
            return
        if token in _OUTCOME_STOPWORDS:
            return
        if len(token) < 2 or len(token) > 8:
            return
        keywords.append(token)

    # 1) 优先命中领域短词（按长度降序，减少短词抢先）
    for term in sorted(_OUTCOME_KEY_TERMS, key=len, reverse=True):
        if term in compact:
            _push(term)
        if len(keywords) >= limit:
            return keywords[:limit]

    # 2) 按标点切分后取短片段，去掉口语前缀（可连续剥离）
    parts = [part.strip() for part in re.split(r"[，。；、,/；]", clean) if part.strip()]
    prefix_re = re.compile(r"^(能够|可以|应当|应该|需要|要求|迅速|及时|正确|有效|充分|进行)")
    for part in parts:
        token = _SPACE_RE.sub("", part)
        for _ in range(4):
            nxt = prefix_re.sub("", token)
            if nxt == token:
                break
            token = nxt
        if 2 <= len(token) <= 6:
            _push(token)
        # 长片段仅依赖步骤 1 的领域短词，避免再塞入难命中的 6-8 字半句
        if len(keywords) >= limit:
            break

    if not keywords and 2 <= len(compact) <= 12:
        _push(compact[:8] if len(compact) > 8 else compact)
    return keywords[:limit]


def outcomes_to_eval_points(outcomes: list[str] | None) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, raw in enumerate(finalize_expected_outcomes(outcomes)[0], start=1):
        keywords = extract_outcome_keywords(raw)
        points.append({
            "id": f"eo_{index}",
            "label": raw[:40],
            "content": raw,
            "category": "procedure",
            "required": True,
            "weight": 12,
            "keywords": keywords,
            "knowledge_refs": [],
            "source": "expected_outcomes",
        })
    return points


def _build_script_context(scene_info: dict[str, Any], case_info: dict[str, Any]) -> str:
    stages = scene_info.get("stages") if isinstance(scene_info.get("stages"), list) else []
    stage_bits = []
    for stage in stages[:4]:
        if not isinstance(stage, dict):
            continue
        name = str(stage.get("stage_name") or "").strip()
        goal = str(stage.get("stage_goal") or "").strip()
        if name or goal:
            stage_bits.append(f"{name}:{goal}" if name and goal else (name or goal))
    existing = finalize_expected_outcomes(scene_info.get("expected_outcomes") or scene_info.get("existing_outcomes"))[0]
    return "\n".join([
        f"案件标题：{case_info.get('title') or case_info.get('case_name') or ''}",
        f"案件类型：{case_info.get('case_type') or ''}",
        f"场景名称：{scene_info.get('name') or scene_info.get('scene_name') or ''}",
        f"训练目标：{scene_info.get('training_goal') or scene_info.get('stage_goal') or ''}",
        f"剧情走向：{scene_info.get('plot_arc') or scene_info.get('description') or ''}",
        f"学员角色：{scene_info.get('student_role') or '民警'}",
        f"阶段摘要：{'；'.join(stage_bits) if stage_bits else '（无）'}",
        f"已有考察点：{'；'.join(existing) if existing else '（无）'}",
    ])


EXPECTED_OUTCOME_PROMPT = """你是公安教官。根据【本场景剧本信息】生成可观察的「本场景考察点」条目。

硬性约束：
1. 只输出 JSON：{"expected_outcomes":["..."]}
2. 条目数量必须在 1-6 之间；本轮按请求数量生成。
3. 每条是一句可判断的考察点短句（如“能够安全控制现场，避免冲突升级”），不要写成冗长题干或评分细则。
4. 必须紧扣训练目标与剧情，禁止虚构案外能力要求。
5. 禁止与「已有考察点」重复或近义复述。
6. 不要输出 label/content/category/weight 等旧结构字段。
"""


def generate_expected_outcomes_with_llm(
    case_info: dict[str, Any],
    scene_info: dict[str, Any],
    *,
    count: int,
    mode: str,
) -> list[str]:
    target = max(EXPECTED_OUTCOMES_MIN_PER_GENERATE, min(EXPECTED_OUTCOMES_MAX_PER_SCENE, int(count or 1)))
    context = _build_script_context(scene_info, case_info)
    prompt = (
        f"{EXPECTED_OUTCOME_PROMPT}\n\n"
        f"请求模式：{mode}\n"
        f"本轮需要生成条目数：{target}\n\n"
        f"【本场景剧本信息】\n{context}"
    )
    response = create_json_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        model=get_chat_model(),
        max_tokens=1800,
    )
    payload = extract_json_payload(response) or {}
    raw = payload.get("expected_outcomes") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []
    return finalize_expected_outcomes(raw)[0][:target]


def generate_expected_outcomes(
    case_info: dict[str, Any],
    scene_info: dict[str, Any],
    *,
    existing_outcomes: list[Any] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    existing, _ = finalize_expected_outcomes(
        existing_outcomes if existing_outcomes is not None else scene_info.get("expected_outcomes")
    )
    scene_payload = {
        **scene_info,
        "expected_outcomes": existing,
        "existing_outcomes": existing,
    }
    remaining = EXPECTED_OUTCOMES_MAX_PER_SCENE - len(existing)
    if remaining <= 0:
        mode = "refresh"
        request_count = EXPECTED_OUTCOMES_MAX_PER_SCENE
    else:
        mode = "append"
        request_count = remaining

    warnings: list[str] = []
    generated: list[str] = []
    if use_llm:
        try:
            generated = generate_expected_outcomes_with_llm(
                case_info,
                scene_payload,
                count=request_count,
                mode=mode,
            )
        except Exception as exc:
            warnings.append(str(exc))

    if mode == "append":
        merged, merge_warnings = finalize_expected_outcomes([*existing, *generated])
        warnings.extend(merge_warnings)
        message = f"已追加考察点（现 {len(merged)} / {EXPECTED_OUTCOMES_MAX_PER_SCENE} 条）"
    else:
        # Full: only refresh/replace content, keep count at cap.
        refreshed = generated[:EXPECTED_OUTCOMES_MAX_PER_SCENE]
        if len(refreshed) < EXPECTED_OUTCOMES_MAX_PER_SCENE and existing:
            # Keep untouched slots if model returned fewer items.
            refreshed = (refreshed + existing)[:EXPECTED_OUTCOMES_MAX_PER_SCENE]
            refreshed, refresh_warnings = finalize_expected_outcomes(refreshed)
            warnings.extend(refresh_warnings)
        else:
            refreshed, refresh_warnings = finalize_expected_outcomes(refreshed)
            warnings.extend(refresh_warnings)
        merged = refreshed
        message = f"已刷新本场景考察点（{len(merged)} 条，未新增）"

    if not merged and existing:
        merged = existing
        message = "未生成新内容，已保留现有考察点"
        warnings.append("模型未返回有效条目")

    result: dict[str, Any] = {
        "outcomes": merged,
        "expected_outcomes": merged,
        "points": outcomes_to_eval_points(merged),  # compat for old callers
        "source": "script_expected_outcomes",
        "mode": mode,
        "message": message,
        "max_per_scene": EXPECTED_OUTCOMES_MAX_PER_SCENE,
        "count": len(merged),
    }
    if warnings:
        result["warnings"] = warnings
    return result
