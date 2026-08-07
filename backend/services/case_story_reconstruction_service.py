"""Reconstruct a complete case story and a source-grounded event document."""
from __future__ import annotations

import math
import os
import re
from typing import Any

from .llm_provider import (
    create_text_chat_completion,
    extract_message_text,
    get_story_generation_binding,
    get_story_generation_kwargs,
)


CASE_NARRATIVE_PROMPT = """你是一名擅长将公安、刑事和治安案件材料还原为纪实故事的资深案件叙事专家。请先在内部完整梳理时间线、空间变化、人物关系、主线、支线、冲突升级、人物心理动机与案件收束，再直接输出可阅读的 Markdown 正文，不要输出思考过程、JSON、代码块、字段说明或写作说明。

写作目标：
1. 写成类似纪实故事、案件还原或警情复盘的完整长文，而不是摘要、证据清单、判决书改写或机械事件拼接。
2. 参考这种叙事节奏：先写“案件背景：矛盾如何形成”，再写“风暴前夜/导火索/第一幕/第二幕/对峙升级/强制驱散/尾声”等与本案事实匹配的章节。章节名必须根据本案具体矛盾、人物和地点命名，禁止所有章节都叫“拉警戒维护现场”“现场处置”等模板化标题。
3. 每个重要阶段都要交代：何时开始、在哪里发生、在场和关联人物是谁、人物为何来到这里、他们看到了什么、听到了什么、心里怎样判断、动作如何变化、冲突怎样推进、警方或相关人员如何介入、阶段如何结束并转入下一阶段。
4. 主线和支线都允许充分拓写。可以补充符合现实常识的过渡动作、现场第一印象、人物犹豫、判断、心理变化、情绪、短对话、肢体动作、旁观者反应和环境感受，使故事丰富、连续、有画面；但所有拓写都必须服务于原有事实和训练理解。
5. 人物心理和对话可以依据其身份、经历、行为及前后事实合理还原，写法要像“他心里想的是……”“他其实担心……”“他嘴上不说，但动作已经说明……”；不得把推测写成新增证据，不得新增会改变责任、伤情、违法性质或结果的人物、行为和关系。
6. 生成内容应足够详尽。长材料不得只写开头几段，也不得只保留前半段；后半段的报警、赶赴现场、调查、调解、救治、控制、收尾、判决或处理结果如果与训练理解有关，都要写进正文。

事实边界：
1. 原文中明确的人物、时间、地点、行为、物品、伤情、证据、矛盾说法及最终结果均为硬事实，不得删除、调换主体、改变责任或制造相反结局。
2. 对相互冲突或尚未核实的说法，保留“某人称”“其认为”“另一方否认”等来源边界，不替警方或法院擅自下结论。
3. 材料未明确天气、光线或地形时，只能使用中性的现场描写，不得虚构具体天气并冒充事实。
4. 必须覆盖案件起因、发展、关键转折、主要人物行为、报警或介入、处置过程和最终结果，长材料后半部分同样不得遗漏。
5. 删除与剧情无关的文书标题、案号、审判人员、书记员、诉讼套话、证据目录、文档识别标记和重复材料。不得输出“块 49 / paragraph / body”“docx_xml_text”“（一）证据目录”“鉴定意见目录”等非正文标记。判决或处理结果仅在确有必要收束故事时简明保留。

输出要求：
- 第一行为“# 案件完整剧情”。
- 使用“##”组织有叙事意义的章节，正文采用完整自然段。
- 每个章节正文至少包含人物行动或心理描写，不能只有一句概括。
- 标题应具体，例如“牛裔岭的归属之争”“两村人马在山路对峙”“民警赶到后的隔离与劝阻”，不得使用重复空泛标题。
- 不单独输出人物参数表、时空导图、事实 ID、覆盖率或免责声明。
- 不得以“材料有限”“以原文为准”等兜底话术代替故事正文。
"""


CASE_STORY_REPAIR_PROMPT = """你上一版故事对部分来源事实覆盖不足。请保留原有叙事风格，将补充事实自然写回正确的时间、空间和人物阶段，输出一篇重新整合后的完整正文。不要增加“补遗”“遗漏事实”“修订说明”等章节，也不要解释修改过程。"""


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


def _source_start(item: dict[str, Any]) -> int:
    refs = item.get("source_refs") if isinstance(item, dict) else []
    starts = [ref.get("start") for ref in refs or [] if isinstance(ref, dict) and isinstance(ref.get("start"), int)]
    return min(starts) if starts else int(item.get("source_start") or 10**9)


def _clean_time_hint(value: Any) -> str:
    text = str(value or "").strip()
    if re.search(r"\d{1,4}(?:年|月|日|时|点|分)|凌晨|早晨|上午|中午|下午|傍晚|晚上|夜间|当天|次日|随后|不久", text):
        return text[:60]
    return "未明确"


def _clean_place_hint(value: Any) -> str:
    text = str(value or "").strip().lstrip("与于在到")
    if not text or len(text) > 48 or any(token in text for token in ("看见", "听说", "叫他", "他们", "开车", "送他", "之后")):
        return "未明确"
    if re.search(r"村|山|岭|山腰|山脚|冲口|路|桥|医院|派出所|看守所|政府|现场|家中|屋内|室内|门口|附近", text):
        return text
    return "未明确"


def _join_hints(values: list[str]) -> str:
    unique = list(dict.fromkeys(value for value in values if value and value != "未明确"))
    if not unique:
        return "未明确"
    return " → ".join(unique[:4]) + ("等" if len(unique) > 4 else "")


def _sentence_split(text: str) -> list[str]:
    parts = [item.strip() for item in re.split(r"(?<=[。！？；])", strip_document_artifacts(text)) if item.strip()]
    return parts or ([strip_document_artifacts(text)] if strip_document_artifacts(text) else [])


def _node_theme(node: dict[str, Any], index: int, total: int) -> str:
    text = strip_document_artifacts(node.get("story_segment") or "")
    time_hint = str(node.get("time") or "").strip()
    place_hint = str(node.get("place") or "").strip()
    people = [str(item).strip() for item in node.get("present_roles") or [] if str(item).strip()]
    prefix = ""
    if index == 0:
        prefix = "案件背景"
    elif index == total - 1:
        prefix = "尾声"
    elif any(token in text for token in ("报警", "接警", "派出所", "民警", "公安", "处警", "出警", "赶到", "到达现场")):
        prefix = "民警介入"
    elif any(token in text for token in ("殴打", "打伤", "砍", "冲突", "斗殴", "互殴", "围攻", "围殴")):
        prefix = "冲突升级"
    elif any(token in text for token in ("调解", "劝阻", "阻止", "劝说", "控制", "隔离", "驱散", "制止")):
        prefix = "现场处置"
    elif any(token in text for token in ("会议", "商量", "组织", "准备", "集合", "聚集")):
        prefix = "风暴前夜"
    else:
        prefix = f"第{index + 1}幕"

    cues: list[str] = []
    if place_hint and place_hint != "未明确":
        cues.append(place_hint[:18])
    if people:
        cues.append("、".join(people[:3]))
    if not cues:
        first_sentence = _sentence_split(text)[0] if text else ""
        words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", first_sentence)
        cues.extend(words[:2])
    cue_text = "与".join(cues[:2])
    if cue_text:
        return f"{prefix}：{cue_text}"
    if time_hint and time_hint != "未明确":
        return f"{prefix}：{time_hint[:18]}"
    return prefix


def _paragraphize_node(node: dict[str, Any]) -> list[str]:
    sentences = _sentence_split(node.get("story_segment") or "")
    if not sentences:
        return []
    paragraphs: list[str] = []
    buffer = ""
    for sentence in sentences:
        if buffer and len(buffer) + len(sentence) > 360:
            paragraphs.append(buffer)
            buffer = sentence
        else:
            buffer += sentence
    if buffer:
        paragraphs.append(buffer)
    return paragraphs


def build_story_nodes(reconstruction: dict[str, Any], persons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = [dict(item) for item in reconstruction.get("event_ledger") or [] if isinstance(item, dict)]
    events.sort(key=_source_start)
    known_names = [str(item.get("name") or "").strip() for item in persons if isinstance(item, dict) and str(item.get("name") or "").strip()]
    nodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    max_node_chars = max(1600, int(os.getenv("CASE_STORY_NODE_CHARS", "3600")))
    for event in events:
        statement = strip_document_artifacts(event.get("statement"))
        if not statement:
            continue
        time_hint = _clean_time_hint(event.get("time_hint"))
        place_hint = _clean_place_hint(event.get("place_hint"))
        participants = [name for name in known_names if name in statement]
        participants.extend(str(name).strip() for name in event.get("participants") or [] if str(name).strip() in known_names)
        participants = list(dict.fromkeys(participants))
        node_key = (time_hint, place_hint)
        current_chars = sum(len(item["statement"]) for item in (current or {}).get("events", []))
        if current is None or current["node_key"] != node_key or current_chars + len(statement) > max_node_chars:
            current = {
                "node_id": f"N{len(nodes) + 1}",
                "node_key": node_key,
                "start_condition": "承接上一剧情阶段" if nodes else "案件相关行为开始",
                "end_condition": "进入下一时间、空间或行为阶段",
                "time": time_hint,
                "place": place_hint,
                "present_roles": [],
                "mentioned_roles": [],
                "events": [],
                "source_start": _source_start(event),
            }
            nodes.append(current)
        current["events"].append({
            "event_id": event.get("event_id"),
            "fact_id": f"F{str(event.get('event_id') or '').lstrip('E')}" if str(event.get("event_id") or "").startswith("E") else "",
            "statement": statement,
            "participants": participants,
            "certainty": event.get("certainty") or "source_supported",
            "source_refs": event.get("source_refs") or [],
        })
        current["present_roles"] = list(dict.fromkeys([*current["present_roles"], *participants]))

    max_nodes = max(4, int(os.getenv("CASE_STORY_MAX_NODES", "24")))
    if len(nodes) > max_nodes:
        group_size = math.ceil(len(nodes) / max_nodes)
        grouped: list[dict[str, Any]] = []
        for start in range(0, len(nodes), group_size):
            batch = nodes[start:start + group_size]
            grouped.append({
                "node_id": f"N{len(grouped) + 1}",
                "node_key": (batch[0].get("time"), batch[0].get("place")),
                "start_condition": batch[0].get("start_condition"),
                "end_condition": batch[-1].get("end_condition"),
                "time": _join_hints([str(item.get("time") or "未明确") for item in batch]),
                "place": _join_hints([str(item.get("place") or "未明确") for item in batch]),
                "present_roles": list(dict.fromkeys(name for item in batch for name in item.get("present_roles") or [])),
                "mentioned_roles": [],
                "events": [event for item in batch for event in item.get("events") or []],
                "source_start": batch[0].get("source_start"),
                "sub_nodes": [{"time": item.get("time"), "place": item.get("place"), "event_count": len(item.get("events") or [])} for item in batch],
            })
        nodes = grouped

    for index, node in enumerate(nodes):
        node["story_segment"] = "".join(str(item.get("statement") or "") for item in node.get("events") or [])
        node["ending_state"] = node.get("end_condition")
        node["enrichment_source"] = "source_event_ledger"
        if index + 1 < len(nodes):
            next_node = nodes[index + 1]
            node["end_condition"] = f"转入{next_node.get('time') or '下一时段'}、{next_node.get('place') or '下一地点'}"
            node["ending_state"] = node["end_condition"]
    return nodes


def render_event_document(nodes: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    entries: list[dict[str, Any]] = []
    lines = ["# 案件完整剧情事件明细", ""]
    for node in nodes:
        for event in node.get("events") or []:
            participants = list(dict.fromkeys(str(name).strip() for name in event.get("participants") or [] if str(name).strip()))
            entry = {
                "index": len(entries) + 1,
                "event_id": event.get("event_id"),
                "time": node.get("time") or "未明确",
                "place": node.get("place") or "未明确",
                "participants": participants,
                "content": strip_document_artifacts(event.get("statement")),
                "certainty": event.get("certainty") or "source_supported",
                "source_refs": event.get("source_refs") or [],
            }
            entries.append(entry)
            role_text = "、".join(participants) or "相关人员"
            lines.append(f"{entry['index']}. 【{entry['time']}｜{entry['place']}｜{role_text}】{entry['content']}")
    return strip_document_artifacts("\n\n".join(lines)), entries


def _event_coverage(story: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    compact_story = re.sub(r"\s+", "", story)
    events = [event for node in nodes for event in node.get("events") or []]
    missing: list[dict[str, Any]] = []
    for event in events:
        statement = re.sub(r"\s+", "", str(event.get("statement") or ""))
        terms = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z0-9]{2,}", statement)
        anchors = list(dict.fromkeys([*event.get("participants", []), *terms]))
        anchors = [str(item) for item in anchors if len(str(item)) >= 2][:12]
        matches = sum(1 for anchor in anchors if anchor in compact_story)
        if anchors and matches / len(anchors) < 0.25:
            missing.append(event)
    total = len(events)
    return {
        "event_count": total,
        "covered_event_count": total - len(missing),
        "coverage_ratio": round((total - len(missing)) / total, 4) if total else 1.0,
        "missing_events": missing,
    }


def _fallback_story(nodes: list[dict[str, Any]]) -> str:
    lines = ["# 案件完整剧情"]
    total = len(nodes)
    for index, node in enumerate(nodes):
        paragraphs = _paragraphize_node(node)
        if not paragraphs:
            continue
        title = _node_theme(node, index, total)
        time_hint = node.get("time") or "时间未明确"
        place_hint = node.get("place") or "地点未明确"
        people = "、".join(str(item).strip() for item in node.get("present_roles") or [] if str(item).strip()) or "相关人员"
        lines.extend([
            "",
            f"## {title}",
            f"{time_hint}，{place_hint}，与本阶段有关的人物包括{people}。这一阶段承接前一段矛盾，人物的行动和现场反应开始把案件推向新的节点。",
        ])
        lines.extend(paragraphs)
    return strip_document_artifacts("\n".join(lines))


def _story_quality_issues(story: str) -> list[str]:
    issues: list[str] = []
    cleaned = strip_document_artifacts(story)
    if _ARTIFACT_RE.search(story) or re.search(r"块\s*\d+\s*/\s*(?:paragraph|body|段落|正文|docx_xml)", story, flags=re.IGNORECASE):
        issues.append("contains_document_artifacts")
    if len(cleaned) < max(900, int(os.getenv("CASE_STORY_MIN_CHARS", "1800"))):
        issues.append("too_short")
    headings = re.findall(r"(?m)^##\s*(.+)$", cleaned)
    normalized_headings = [re.sub(r"\s+", "", item) for item in headings]
    if len(normalized_headings) >= 3 and len(set(normalized_headings)) <= max(1, len(normalized_headings) // 2):
        issues.append("repeated_headings")
    weak_headings = [item for item in normalized_headings if item in {"拉警戒维护现场", "现场处置", "案件背景与发展", "时间未明确·地点未明确"}]
    if len(weak_headings) >= 2:
        issues.append("template_headings")
    if not re.search(r"心里|担心|害怕|犹豫|不服|着急|愤怒|紧张|慌|认为|觉得|意识到|看见|听见|冲|跑|拉|拦|劝|喊", cleaned):
        issues.append("missing_psychology_or_action")
    return issues


def _generate_narrative(source_text: str, nodes: list[dict[str, Any]], persons: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    llm_client, model, provider, _ = get_story_generation_binding()
    cast = [str(person.get("name") or "").strip() for person in persons if isinstance(person, dict) and str(person.get("name") or "").strip()]
    source = strip_document_artifacts(source_text) or "\n".join(str(node.get("story_segment") or "") for node in nodes)
    response, trace = create_text_chat_completion(
        messages=[
            {"role": "system", "content": CASE_NARRATIVE_PROMPT},
            {"role": "user", "content": f"【已识别人物】\n{'、'.join(cast)}\n\n【整理后的案件有效原文】\n{source}"},
        ],
        model=model,
        llm_client=llm_client,
        temperature=0.2,
        max_tokens=max(8000, int(os.getenv("CASE_STORY_MAX_TOKENS", "24000"))),
        return_trace=True,
        long_output=True,
        extra_kwargs=get_story_generation_kwargs(),
        allow_provider_fallback=os.getenv("CASE_STORY_ALLOW_PROVIDER_FALLBACK", "0").strip() == "1",
    )
    story = strip_document_artifacts(extract_message_text(response))
    if not story or len(story) < 600:
        raise ValueError("完整剧情模型输出为空或篇幅不足")
    if not story.startswith("# 案件完整剧情"):
        story = "# 案件完整剧情\n\n" + story.lstrip("# ")

    coverage = _event_coverage(story, nodes)
    quality_issues = _story_quality_issues(story)
    if coverage["coverage_ratio"] < float(os.getenv("CASE_STORY_MIN_COVERAGE", "0.68")) or quality_issues:
        missing_text = "\n".join(
            f"- {item.get('statement')}" for item in coverage["missing_events"][:40]
        )
        repair_context = f"【当前故事】\n{story}\n\n"
        if missing_text:
            repair_context += f"【必须补回的来源事实】\n{missing_text}\n\n"
        repair_context += (
            f"【需要修复的问题】\n{', '.join(quality_issues) or 'event_coverage_below_threshold'}\n\n"
            "【整理后的案件有效原文】\n"
            f"{source[: max(12000, int(os.getenv('CASE_STORY_REPAIR_SOURCE_CHARS', '28000')))]}"
        )
        repair_response, repair_trace = create_text_chat_completion(
            messages=[
                {"role": "system", "content": CASE_NARRATIVE_PROMPT + "\n\n" + CASE_STORY_REPAIR_PROMPT},
                {"role": "user", "content": repair_context},
            ],
            model=model,
            llm_client=llm_client,
            temperature=0.2,
            max_tokens=max(8000, int(os.getenv("CASE_STORY_MAX_TOKENS", "24000"))),
            return_trace=True,
            long_output=True,
            extra_kwargs=get_story_generation_kwargs(),
            allow_provider_fallback=os.getenv("CASE_STORY_ALLOW_PROVIDER_FALLBACK", "0").strip() == "1",
        )
        repaired = strip_document_artifacts(extract_message_text(repair_response))
        if len(repaired) >= len(story) * 0.75:
            story = repaired if repaired.startswith("# 案件完整剧情") else "# 案件完整剧情\n\n" + repaired.lstrip("# ")
            trace = {
                **repair_trace,
                "initial_attempts": trace.get("attempts") or [],
                "repair_reason": "event_coverage_or_quality",
                "quality_issues": quality_issues,
            }
    story = strip_document_artifacts(story)
    return story, {**trace, "provider": provider, "model": model}


def generate_case_narrative(source_text: str) -> tuple[str, dict[str, Any]]:
    """Start the expert story call without waiting for role-line extraction."""
    return _generate_narrative(source_text, [], [])


def reconstruct_story_document(
    reconstruction: dict[str, Any],
    persons: list[dict[str, Any]],
    *,
    source_text: str = "",
    use_model: bool = True,
    narrative_override: str = "",
    generation_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = build_story_nodes(reconstruction, persons)
    event_document, event_entries = render_event_document(nodes)
    trace: dict[str, Any] = generation_trace or {"attempts": []}
    generation_error = str(trace.get("error") or "")[:500]
    if strip_document_artifacts(narrative_override):
        narrative = strip_document_artifacts(narrative_override)
    elif use_model and nodes:
        try:
            narrative, trace = _generate_narrative(source_text, nodes, persons)
        except Exception as exc:
            generation_error = str(exc)[:500]
            narrative = _fallback_story(nodes)
    else:
        narrative = _fallback_story(nodes)
    if _story_quality_issues(narrative) and nodes:
        narrative = _fallback_story(nodes)
    coverage = _event_coverage(narrative, nodes)
    model_succeeded = any(item.get("status") == "success" for item in trace.get("attempts") or [])
    coverage.update({
        "node_count": len(nodes),
        "generation_mode": "deepseek_expert_story" if model_succeeded else "source_assembled",
        "generation_error": generation_error,
    })
    return {
        "nodes": nodes,
        "complete_story": narrative,
        "event_document": event_document,
        "event_entries": event_entries,
        "story_documents": {
            "narrative": {"title": "案件完整故事剧情", "format": "word", "content": narrative},
            "event_ledger": {"title": "案件完整剧情事件明细", "format": "word_event_ledger", "content": event_document, "entries": event_entries},
        },
        "coverage": coverage,
        "generation_trace": trace,
    }
