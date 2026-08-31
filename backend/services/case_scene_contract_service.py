"""Deterministic scene contracts, derived artifacts and publication quality gates."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .training_compiler_service import (
    build_observable_scoring_rules,
    build_training_tasks,
    compile_state_machine,
)
from .dialogue_scene_admission_service import evaluate_dialogue_admission


SCENE_CONTRACT_SCHEMA_VERSION = "2026.08.case-scene-contract-v5"
DERIVED_ARTIFACT_VERSION = "scene-derived-v3"
FIRST_IMPRESSION_MIN_LENGTH = 80
FIRST_IMPRESSION_MAX_LENGTH = 160
NON_SPEAKABLE_STATUS_KEYWORDS = (
    "死亡", "死者", "昏迷", "无意识", "重伤无法交流", "无法交流",
    "无法接受审问", "无法接受询问", "无法问询",
)
PHASE_ORDER = {
    "intake": 0,
    "post_incident_onsite": 1,
    "post_incident_inquiry": 2,
    "post_incident_followup": 3,
}
POLICE_GOAL_MARKERS = ("接警", "出警", "核实", "询问", "处置", "控制", "疏散", "隔离", "救助", "取证", "记录", "告知", "移交", "增援", "风险")
NON_POLICE_GOAL_MARKERS = ("检察官", "公诉", "起诉意见", "辩护", "法庭", "定罪", "量刑", "构成要件", "主从犯", "审判", "裁判")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def person_is_speakable(person: dict[str, Any] | None) -> bool:
    status = _text((person or {}).get("status"))
    return not any(keyword in status for keyword in NON_SPEAKABLE_STATUS_KEYWORDS)


def _scene_name(scene: dict[str, Any], index: int) -> str:
    return _text(scene.get("scene_name") or scene.get("name")) or f"场景 {index}"


def _scene_ref(scene: dict[str, Any], index: int) -> str:
    explicit = _text(scene.get("scene_ref") or scene.get("scene_id"))
    if explicit:
        return explicit
    try:
        database_id = int(scene.get("id"))
    except (TypeError, ValueError):
        database_id = 0
    return f"db:{database_id}" if database_id > 0 else f"S{index}"


def _fact_ids(value: Any) -> list[str]:
    return list(dict.fromkeys(_text(item) for item in _items(value) if _text(item)))


def _roles(value: Any) -> list[str]:
    return list(dict.fromkeys(_text(item) for item in _items(value) if _text(item)))


def _validate_first_impression(value: Any) -> tuple[str, list[dict[str, str]]]:
    raw = _text(value)
    text = re.sub(r"\s+", " ", raw)
    issues: list[dict[str, str]] = []
    if not text:
        issues.append({"severity": "warning", "code": "MISSING_FIRST_IMPRESSION", "reason": "现场第一印象为空，建议补充入场可观察描述"})
        return text, issues
    if len(text) < FIRST_IMPRESSION_MIN_LENGTH:
        issues.append({
            "severity": "warning", "code": "FIRST_IMPRESSION_TOO_SHORT",
            "reason": f"现场第一印象仅 {len(text)} 字，建议补充至 {FIRST_IMPRESSION_MIN_LENGTH}-{FIRST_IMPRESSION_MAX_LENGTH} 字",
        })
    if len(text) > FIRST_IMPRESSION_MAX_LENGTH:
        issues.append({
            "severity": "warning", "code": "FIRST_IMPRESSION_TOO_LONG",
            "reason": f"现场第一印象共 {len(text)} 字，超过 {FIRST_IMPRESSION_MAX_LENGTH} 字建议上限",
        })
    if "\n" in raw or "\r" in raw:
        issues.append({"severity": "warning", "code": "FIRST_IMPRESSION_MULTILINE", "reason": "现场第一印象建议为单段文本"})

    marker_groups = (
        (("接警信息", "报警信息", "接报警", "接到报警", "报警人称", "110指令"),
         "FIRST_IMPRESSION_DISPATCH_CONTENT", "现场第一印象包含接警或报警转述，建议改为入场时可直接观察的内容"),
        (("当前可接触人员", "可接触人员", "当前时空", "→"),
         "FIRST_IMPRESSION_CONTEXT_METADATA", "现场第一印象包含人员清单、时空链路或系统元数据"),
        (("训练目标", "训练任务", "民警任务", "需要先", "开展询问", "开展处置"),
         "FIRST_IMPRESSION_TASK_CONTENT", "现场第一印象包含训练或处置任务说明"),
        (("案件结论", "裁判结论", "隐藏证据", "定罪", "量刑"),
         "FIRST_IMPRESSION_SPOILER_CONTENT", "现场第一印象包含案件结论、隐藏证据或裁判信息"),
    )
    for markers, code, reason in marker_groups:
        if any(marker in text for marker in markers):
            issues.append({"severity": "warning", "code": code, "reason": reason})
    if re.search(r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}时\d{1,2}分|F\d+", text):
        issues.append({
            "severity": "warning", "code": "FIRST_IMPRESSION_TIMELINE_CONTENT",
            "reason": "现场第一印象包含案件时间线或事实编号",
        })
    return text, issues


def _existing_scene_index(case_info: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_ref: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for collection_name in ("scene_blueprints", "scene_scripts"):
        for item in _items(case_info.get(collection_name)):
            if not isinstance(item, dict):
                continue
            ref = _text(item.get("scene_ref") or item.get("scene_id"))
            name = _text(item.get("scene_name") or item.get("name"))
            if ref:
                by_ref.setdefault(ref, {}).update(item)
            if name:
                by_name.setdefault(name, {}).update(item)
    return by_ref, by_name


def compile_case_scene_artifacts(case_info: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
    """Rebuild all scene-derived artifacts without invoking a model."""
    by_ref, by_name = _existing_scene_index(case_info)
    compiled_scenes: list[dict[str, Any]] = []
    blueprints: list[dict[str, Any]] = []
    scripts: list[dict[str, Any]] = []
    role_map: dict[str, dict[str, Any]] = {}

    for index, raw_scene in enumerate(scenes or [], start=1):
        if not isinstance(raw_scene, dict):
            continue
        initial_scene = dict(raw_scene)
        name = _scene_name(initial_scene, index)
        ref = _scene_ref(initial_scene, index)
        previous = by_ref.get(ref) or by_name.get(name) or {}
        scene = {**previous, **initial_scene}
        roles = _roles(scene.get("roles") if scene.get("roles") is not None else scene.get("role_names"))
        if not roles:
            roles = _roles(previous.get("roles"))
        fact_ids = _fact_ids(scene.get("fact_ids")) or _fact_ids(previous.get("fact_ids"))
        supplement_ids = _fact_ids(scene.get("supplement_ids")) or _fact_ids(previous.get("supplement_ids"))
        primary = _text(scene.get("primary_role_name") or previous.get("primary_role_name"))
        if primary not in roles:
            primary = roles[0] if roles else ""
        stages = [dict(item) for item in _items(scene.get("stages")) if isinstance(item, dict)]
        if not stages:
            stages = [dict(item) for item in _items(previous.get("stages")) if isinstance(item, dict)]
        for stage in stages:
            stage["fact_ids"] = _fact_ids(stage.get("fact_ids")) or list(fact_ids)

        previous_roles = _roles(previous.get("roles"))
        manual_override = bool(previous and roles != previous_roles)
        first_impression, impression_issues = _validate_first_impression(scene.get("first_impression"))
        scene.update({
            "scene_ref": ref,
            "scene_name": name,
            "roles": roles,
            "role_names": roles,
            "primary_role_name": primary,
            "fact_ids": fact_ids,
            "supplement_ids": supplement_ids,
            "stages": stages,
            "canonical_outcome_locked": scene.get("canonical_outcome_locked", previous.get("canonical_outcome_locked", True)) is not False,
            "first_impression": first_impression,
            "first_impression_quality_issues": impression_issues,
            "plot_arc": _text(scene.get("plot_arc") or previous.get("plot_arc")),
            "opening_lines": [item for item in _items(scene.get("opening_lines") or previous.get("opening_lines")) if isinstance(item, dict)],
            "training_goal": _text(scene.get("training_goal") or previous.get("training_goal")),
            "expected_outcomes": [_text(item) for item in _items(scene.get("expected_outcomes") or previous.get("expected_outcomes")) if _text(item)],
            "completion_criteria": [_text(item) for item in _items(scene.get("completion_criteria") or previous.get("completion_criteria")) if _text(item)],
            "failure_patterns": [_text(item) for item in _items(scene.get("failure_patterns") or previous.get("failure_patterns")) if _text(item)],
            "role_training_functions": [item for item in _items(scene.get("role_training_functions") or previous.get("role_training_functions")) if isinstance(item, dict)],
        })
        compiled_scenes.append(scene)

        blueprint = {
            **previous,
            "scene_id": ref,
            "scene_ref": ref,
            "scene_name": name,
            "roles": roles,
            "present_roles": _roles(scene.get("present_roles")) or _roles(previous.get("present_roles")) or roles,
            "mentioned_roles": _roles(scene.get("mentioned_roles")) or _roles(previous.get("mentioned_roles")),
            "primary_role_name": primary,
            "fact_ids": fact_ids,
            "supplement_ids": supplement_ids,
            "stages": stages,
            "training_entry_phase": _text(scene.get("training_entry_phase") or previous.get("training_entry_phase")),
            "training_goal": scene.get("training_goal"),
            "expected_outcomes": scene.get("expected_outcomes"),
            "plot_arc": scene.get("plot_arc"),
            "opening_lines": scene.get("opening_lines") or previous.get("opening_lines") or [],
            "completion_criteria": scene.get("completion_criteria"),
            "failure_patterns": scene.get("failure_patterns"),
            "role_training_functions": scene.get("role_training_functions"),
            "canonical_outcome_locked": scene["canonical_outcome_locked"],
            "manual_override": manual_override or bool(previous.get("manual_override")),
        }
        blueprints.append(blueprint)
        scripts.append({
            "scene_ref": ref,
            "scene_name": name,
            "roles": roles,
            "primary_role_name": primary,
            "fact_ids": fact_ids,
            "supplement_ids": supplement_ids,
            "dispatch_brief": _text(scene.get("dispatch_brief")),
            "first_impression": _text(scene.get("first_impression")),
            "training_goal": _text(scene.get("training_goal")),
            "expected_outcomes": [_text(item) for item in _items(scene.get("expected_outcomes")) if _text(item)],
            "plot_arc": _text(scene.get("plot_arc")),
            "opening_lines": [item for item in _items(scene.get("opening_lines")) if isinstance(item, dict)],
            "stages": stages,
            "role_training_functions": [item for item in _items(scene.get("role_training_functions")) if isinstance(item, dict)],
            "completion_criteria": [_text(item) for item in _items(scene.get("completion_criteria")) if _text(item)],
            "failure_patterns": [_text(item) for item in _items(scene.get("failure_patterns")) if _text(item)],
            "script_markdown": _text(scene.get("script_markdown") or previous.get("script_markdown")),
            "manual_override": blueprint["manual_override"],
        })
        role_map[name] = {
            "scene_ref": ref,
            "role_names": roles,
            "primary_role_name": primary,
            "manual_override": blueprint["manual_override"],
        }

    training_tasks = build_training_tasks(case_info, compiled_scenes)
    state_machine = compile_state_machine(training_tasks)
    scoring_rules = build_observable_scoring_rules(training_tasks)
    revision_source = json.dumps(
        {"blueprints": blueprints, "scripts": scripts, "tasks": training_tasks},
        ensure_ascii=False,
        sort_keys=True,
    )
    derived_revision = hashlib.sha256(revision_source.encode("utf-8")).hexdigest()[:16]

    # Keep training_scripts.expected_outcomes in sync with compiled scene truth.
    training_scripts = [
        dict(item) for item in _items(case_info.get("training_scripts")) if isinstance(item, dict)
    ]
    by_name = {
        _text(item.get("scene_name") or item.get("name")): item
        for item in compiled_scenes
        if _text(item.get("scene_name") or item.get("name"))
    }
    for script in training_scripts:
        name = _text(script.get("scene_name") or script.get("name"))
        match = by_name.get(name)
        if match is not None:
            script["expected_outcomes"] = list(match.get("expected_outcomes") or [])
            script["training_goal"] = _text(match.get("training_goal") or script.get("training_goal"))

    return {
        "scenes": compiled_scenes,
        "scene_blueprints": blueprints,
        "scene_scripts": scripts,
        "training_scripts": training_scripts or case_info.get("training_scripts") or [],
        "scene_role_map": role_map,
        "training_tasks": training_tasks,
        "state_machine": state_machine,
        "observable_scoring_rules": scoring_rules,
        "derived_artifact_version": DERIVED_ARTIFACT_VERSION,
        "derived_revision": derived_revision,
        "scene_contract_schema_version": SCENE_CONTRACT_SCHEMA_VERSION,
    }


def build_case_quality_report(case_info: dict[str, Any], scenes: list[dict[str, Any]]) -> dict[str, Any]:
    persons = {
        _text(item.get("name")): item
        for item in _items(case_info.get("persons"))
        if isinstance(item, dict) and _text(item.get("name"))
    }
    story_world = case_info.get("story_world") if isinstance(case_info.get("story_world"), dict) else {}
    fact_cards = [item for item in _items(story_world.get("fact_cards")) if isinstance(item, dict)]
    valid_facts = {
        _text(item.get("id") or item.get("claim_id")): item
        for item in fact_cards
        if _text(item.get("id") or item.get("claim_id"))
    }
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def add(target: list[dict[str, Any]], code: str, message: str, scene_ref: str = "") -> None:
        issue_id = f"{code}:{scene_ref or 'case'}"
        if not any(item["id"] == issue_id for item in target):
            target.append({"id": issue_id, "code": code, "message": message, "scene_ref": scene_ref})

    if not [scene for scene in scenes or [] if isinstance(scene, dict)]:
        add(blocking, "CASE_WITHOUT_SCENES", "案件没有可发布的训练场景")
    if len([scene for scene in scenes or [] if isinstance(scene, dict)]) > 4:
        add(warnings, "TOO_MANY_SCENES", "必要训练场景数量超过 4 个，建议精简")

    import_quality = case_info.get("case_import_quality") if isinstance(case_info.get("case_import_quality"), dict) else {}
    story_audit = import_quality.get("story") if isinstance(import_quality.get("story"), dict) else {}
    fact_audit = import_quality.get("facts") if isinstance(import_quality.get("facts"), dict) else {}
    memory_audit = import_quality.get("memories") if isinstance(import_quality.get("memories"), dict) else {}
    scene_admission_audit = import_quality.get("scene_admission") if isinstance(import_quality.get("scene_admission"), dict) else {}
    if story_audit and not story_audit.get("sufficient"):
        add(warnings, "INCOMPLETE_COMPLETE_STORY", "完整案件剧情覆盖不足，建议复核事实与角色对话支撑")
    if fact_audit and not fact_audit.get("sufficient"):
        add(warnings, "INSUFFICIENT_FACT_EXTRACTION", "事实抽取数量或来源覆盖不足，建议补充")
    if memory_audit and not memory_audit.get("sufficient"):
        add(warnings, "INSUFFICIENT_ROLE_MEMORY", "可对话角色的来源记忆覆盖不足，建议补充")
    if scene_admission_audit and scene_admission_audit.get("rejected_count", 0) > 0 and not scene_admission_audit.get("sufficient"):
        rejected_names = [
            _text(item.get("scene_name"))
            for item in _items(scene_admission_audit.get("rejected_scenes"))
            if _text(item.get("scene_name"))
        ]
        detail = "、".join(dict.fromkeys(rejected_names)) or "非对话适配场景"
        add(warnings, "NON_DIALOGUE_SCENES_FILTERED", f"导入阶段已过滤非对话适配场景：{detail}")

    previous_phase = -1
    referenced_facts: set[str] = set()
    scene_fact_sets: list[set[str]] = []
    source_people = [person for person in persons.values() if _text(person.get("source_kind")) != "synthetic"]
    memory_people = 0
    scene_names: list[str] = []
    missing_fact_scene_names: list[str] = []
    for person in source_people:
        if _items(person.get("role_memories")):
            memory_people += 1

    for index, scene in enumerate(scenes or [], start=1):
        if not isinstance(scene, dict):
            continue
        ref = _scene_ref(scene, index)
        name = _scene_name(scene, index)
        scene_names.append(name)
        _, impression_issues = _validate_first_impression(scene.get("first_impression"))
        for issue in impression_issues:
            add(warnings, issue["code"], f"{name} 的{issue['reason']}", ref)
        admission = evaluate_dialogue_admission(scene)
        if not admission.get("admitted"):
            markers = "、".join(admission.get("non_dialogue_markers") or [])
            reasons = "、".join(admission.get("reasons") or []) or "对话适配度不足"
            detail = markers or reasons
            alternative = _text(admission.get("suggested_alternative")) or "现场人员接触与关键信息核实对话"
            add(
                warnings,
                "NON_DIALOGUE_SCENE",
                f"{name} 对话训练适配提示（{detail}），建议改写为：{alternative}",
                ref,
            )
        roles = _roles(scene.get("roles") if scene.get("roles") is not None else scene.get("role_names"))
        unknown = [role for role in roles if role not in persons]
        if unknown:
            add(warnings, "SCENE_ROLE_OUTSIDE_CASE", f"{name} 包含案件人物名册外角色：{'、'.join(unknown)}", ref)
        non_speakable = [role for role in roles if role in persons and not person_is_speakable(persons[role])]
        if non_speakable:
            add(warnings, "NON_SPEAKABLE_INTERACTIVE_ROLE", f"{name} 将不可交流人员设为交互角色：{'、'.join(non_speakable)}", ref)
        if not roles:
            add(blocking, "MISSING_INTERACTIVE_ROLE", f"{name} 没有可交互角色", ref)
        primary = _text(scene.get("primary_role_name"))
        if roles and (not primary or primary not in roles):
            add(warnings, "INVALID_PRIMARY_ROLE", f"{name} 缺少有效主对话角色，建议指定", ref)
        elif primary in persons and not person_is_speakable(persons[primary]):
            add(warnings, "NON_SPEAKABLE_PRIMARY_ROLE", f"{name} 的主对话角色不可交流", ref)

        facts = set(_fact_ids(scene.get("fact_ids")))
        scene_fact_sets.append(facts)
        referenced_facts.update(facts)
        invalid_facts = sorted(fact for fact in facts if valid_facts and fact not in valid_facts)
        if invalid_facts:
            add(warnings, "SCENE_FACT_OUTSIDE_CASE", f"{name} 引用了案件事实范围外编号：{'、'.join(invalid_facts)}", ref)
        if valid_facts and not facts:
            missing_fact_scene_names.append(name)
        for fact_id in facts:
            card = valid_facts.get(fact_id) or {}
            if valid_facts and not _items(card.get("source_refs")):
                add(warnings, "FACT_WITHOUT_SOURCE", f"{name} 的事实 {fact_id} 缺少来源定位", ref)
        stages = [item for item in _items(scene.get("stages")) if isinstance(item, dict)]
        if not stages:
            add(warnings, "SCENE_WITHOUT_STAGES", f"{name} 没有训练阶段，建议补充", ref)
        for stage in stages:
            stage_facts = set(_fact_ids(stage.get("fact_ids")))
            if facts and not stage_facts:
                add(warnings, "STAGE_WITHOUT_FACTS", f"{name} 存在未绑定事实的训练阶段", ref)
            if stage_facts and not stage_facts.issubset(facts):
                add(warnings, "STAGE_FACT_OUTSIDE_SCENE", f"{name} 的阶段引用了场景范围外事实", ref)
        goal = _text(scene.get("training_goal"))
        if not goal or not any(marker in goal for marker in POLICE_GOAL_MARKERS) or any(marker in goal for marker in NON_POLICE_GOAL_MARKERS):
            add(warnings, "INVALID_POLICE_TRAINING_GOAL", f"{name} 的训练目标建议明确为民警可执行的警情处置任务", ref)
        outcomes = [_text(item) for item in _items(scene.get("expected_outcomes")) if _text(item)]
        if not outcomes:
            add(warnings, "MISSING_EXPECTED_OUTCOMES", f"{name} 缺少预期达到效果，建议补充", ref)
        if scene.get("canonical_outcome_locked") is False:
            add(warnings, "CANONICAL_OUTCOME_UNLOCKED", f"{name} 未锁定案件既定结果", ref)
        phase = _text(scene.get("training_entry_phase"))
        if phase in PHASE_ORDER:
            current_phase = PHASE_ORDER[phase]
            if current_phase < previous_phase:
                add(warnings, "SCENE_TIME_ORDER_CONFLICT", f"{name} 的训练时间阶段早于前一场景", ref)
            previous_phase = max(previous_phase, current_phase)

    if missing_fact_scene_names:
        add(warnings, "SCENE_WITHOUT_FACTS", "以下场景未绑定案件事实：" + "、".join(dict.fromkeys(missing_fact_scene_names)))
    duplicate_names = sorted({name for name in scene_names if scene_names.count(name) > 1})
    if duplicate_names:
        add(warnings, "DUPLICATED_SCENE_NAMES", "存在重复场景名称：" + "、".join(duplicate_names))

    for left, right in zip(scene_fact_sets, scene_fact_sets[1:]):
        if left and right and left == right:
            add(warnings, "DUPLICATED_SCENE_FACT_SCOPE", "相邻场景使用了完全相同的事实范围")
            break

    parse_engine = _text(case_info.get("parse_engine"))
    scene_mode = _text(case_info.get("scene_generation_mode"))
    if parse_engine in {"heuristic", "rule_text_first"} or bool((case_info.get("ai_workflow") or {}).get("used_rule_fallback")):
        add(warnings, "PARSE_FALLBACK_USED", "案件解析使用了规则兜底")
    if scene_mode.startswith("fallback") or scene_mode == "ai_text_template":
        add(warnings, "SCENE_FALLBACK_USED", "场景生成使用了降级路径")
    source_quality = case_info.get("source_quality") if isinstance(case_info.get("source_quality"), dict) else {}
    if _text(source_quality.get("grade")) == "low":
        add(warnings, "LOW_SOURCE_QUALITY", "案件来源材料质量较低")
    if source_people and memory_people < len(source_people):
        add(warnings, "INCOMPLETE_ROLE_MEMORY", "部分人物缺少可核对的来源记忆")
    synthetic_names = [name for name, person in persons.items() if _text(person.get("source_kind")) == "synthetic"]
    if synthetic_names:
        add(warnings, "SYNTHETIC_ROLE_PRESENT", "案件包含显式模拟角色：" + "、".join(synthetic_names))

    fact_coverage = round(len(referenced_facts & set(valid_facts)) / len(valid_facts), 4) if valid_facts else 1.0
    memory_coverage = round(memory_people / len(source_people), 4) if source_people else 1.0
    if valid_facts and fact_coverage < 0.5:
        add(warnings, "LOW_SCENE_FACT_COVERAGE", f"场景仅覆盖 {round(fact_coverage * 100)}% 的案件事实，请复核训练范围")
    return {
        "schema_version": SCENE_CONTRACT_SCHEMA_VERSION,
        "blocking_issues": blocking,
        "warning_issues": warnings,
        "fact_coverage": fact_coverage,
        "role_memory_coverage": memory_coverage,
        "publishable": not blocking,
        "required_acknowledgements": [item["id"] for item in warnings],
    }


def unacknowledged_warnings(report: dict[str, Any], acknowledgements: Any) -> list[dict[str, Any]]:
    accepted = {_text(item) for item in _items(acknowledgements) if _text(item)}
    return [item for item in _items(report.get("warning_issues")) if item.get("id") not in accepted]
