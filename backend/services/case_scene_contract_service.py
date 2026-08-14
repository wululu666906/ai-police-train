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


SCENE_CONTRACT_SCHEMA_VERSION = "2026.08.case-scene-contract-v4"
DERIVED_ARTIFACT_VERSION = "scene-derived-v2"
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


def _normalize_first_impression(value: Any) -> tuple[str, bool]:
    text = re.sub(r"\s+", " ", _text(value))
    banned = (
        "接警信息", "报警信息", "接到报警", "当前可接触人员", "可接触人员", "当前时空", "→",
        "训练目标", "训练任务", "民警任务", "需要先", "开展询问", "开展处置", "案件结论", "裁判结论",
    )
    valid = (
        40 <= len(text) <= 220
        and "\n" not in text
        and not any(word in text for word in banned)
        and not re.search(r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}时\d{1,2}分|F\d+", text)
    )
    return text, not valid


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
        first_impression, impression_repaired = _normalize_first_impression(scene.get("first_impression"))
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
            "first_impression_autofixed": impression_repaired,
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
            "stages": stages,
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
    return {
        "scenes": compiled_scenes,
        "scene_blueprints": blueprints,
        "scene_scripts": scripts,
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
        add(blocking, "TOO_MANY_SCENES", "必要训练场景数量超过 4 个")

    import_quality = case_info.get("case_import_quality") if isinstance(case_info.get("case_import_quality"), dict) else {}
    story_audit = import_quality.get("story") if isinstance(import_quality.get("story"), dict) else {}
    fact_audit = import_quality.get("facts") if isinstance(import_quality.get("facts"), dict) else {}
    memory_audit = import_quality.get("memories") if isinstance(import_quality.get("memories"), dict) else {}
    scene_admission_audit = import_quality.get("scene_admission") if isinstance(import_quality.get("scene_admission"), dict) else {}
    if story_audit and not story_audit.get("sufficient"):
        add(blocking, "INCOMPLETE_COMPLETE_STORY", "完整案件剧情覆盖不足，无法支撑事实与角色对话")
    if fact_audit and not fact_audit.get("sufficient"):
        add(blocking, "INSUFFICIENT_FACT_EXTRACTION", "事实抽取数量或来源覆盖不足")
    if memory_audit and not memory_audit.get("sufficient"):
        add(blocking, "INSUFFICIENT_ROLE_MEMORY", "可对话角色的来源记忆覆盖不足")
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
        if scene.get("first_impression_autofixed"):
            add(blocking, "INVALID_FIRST_IMPRESSION", f"{name} 的现场第一印象不符合可观察、无剧透要求", ref)
        admission = evaluate_dialogue_admission(scene)
        if not admission.get("admitted"):
            markers = "、".join(admission.get("non_dialogue_markers") or []) or "非对话核心能力"
            alternative = _text(admission.get("suggested_alternative")) or "对话适配型现场处置场景"
            add(
                blocking,
                "NON_DIALOGUE_SCENE",
                f"{name} 不属于 AI 对话训练适配场景（命中：{markers}），建议改写为：{alternative}",
                ref,
            )
        roles = _roles(scene.get("roles") if scene.get("roles") is not None else scene.get("role_names"))
        unknown = [role for role in roles if role not in persons]
        if unknown:
            add(blocking, "SCENE_ROLE_OUTSIDE_CASE", f"{name} 包含案件人物名册外角色：{'、'.join(unknown)}", ref)
        non_speakable = [role for role in roles if role in persons and not person_is_speakable(persons[role])]
        if non_speakable:
            add(blocking, "NON_SPEAKABLE_INTERACTIVE_ROLE", f"{name} 将不可交流人员设为交互角色：{'、'.join(non_speakable)}", ref)
        if not roles:
            add(blocking, "MISSING_INTERACTIVE_ROLE", f"{name} 没有可交互角色", ref)
        primary = _text(scene.get("primary_role_name"))
        if roles and (not primary or primary not in roles):
            add(blocking, "INVALID_PRIMARY_ROLE", f"{name} 缺少有效主对话角色", ref)
        elif primary in persons and not person_is_speakable(persons[primary]):
            add(blocking, "NON_SPEAKABLE_PRIMARY_ROLE", f"{name} 的主对话角色不可交流", ref)

        facts = set(_fact_ids(scene.get("fact_ids")))
        scene_fact_sets.append(facts)
        referenced_facts.update(facts)
        invalid_facts = sorted(fact for fact in facts if valid_facts and fact not in valid_facts)
        if invalid_facts:
            add(blocking, "SCENE_FACT_OUTSIDE_CASE", f"{name} 引用了案件事实范围外编号：{'、'.join(invalid_facts)}", ref)
        if valid_facts and not facts:
            missing_fact_scene_names.append(name)
        for fact_id in facts:
            card = valid_facts.get(fact_id) or {}
            if valid_facts and not _items(card.get("source_refs")):
                add(blocking, "FACT_WITHOUT_SOURCE", f"{name} 的事实 {fact_id} 缺少来源定位", ref)
        stages = [item for item in _items(scene.get("stages")) if isinstance(item, dict)]
        if not stages:
            add(blocking, "SCENE_WITHOUT_STAGES", f"{name} 没有训练阶段", ref)
        for stage in stages:
            stage_facts = set(_fact_ids(stage.get("fact_ids")))
            if facts and not stage_facts:
                add(blocking, "STAGE_WITHOUT_FACTS", f"{name} 存在未绑定事实的训练阶段", ref)
            if stage_facts and not stage_facts.issubset(facts):
                add(blocking, "STAGE_FACT_OUTSIDE_SCENE", f"{name} 的阶段引用了场景范围外事实", ref)
        goal = _text(scene.get("training_goal"))
        if not goal or not any(marker in goal for marker in POLICE_GOAL_MARKERS) or any(marker in goal for marker in NON_POLICE_GOAL_MARKERS):
            add(blocking, "INVALID_POLICE_TRAINING_GOAL", f"{name} 的训练目标不是民警可执行的警情处置任务", ref)
        outcomes = [_text(item) for item in _items(scene.get("expected_outcomes")) if _text(item)]
        if not outcomes:
            add(blocking, "MISSING_EXPECTED_OUTCOMES", f"{name} 缺少预期达到效果", ref)
        if scene.get("canonical_outcome_locked") is False:
            add(blocking, "CANONICAL_OUTCOME_UNLOCKED", f"{name} 未锁定案件既定结果", ref)
        phase = _text(scene.get("training_entry_phase"))
        if phase in PHASE_ORDER:
            current_phase = PHASE_ORDER[phase]
            if current_phase < previous_phase:
                add(blocking, "SCENE_TIME_ORDER_CONFLICT", f"{name} 的训练时间阶段早于前一场景", ref)
            previous_phase = max(previous_phase, current_phase)

    if missing_fact_scene_names:
        add(blocking, "SCENE_WITHOUT_FACTS", "以下场景未绑定案件事实：" + "、".join(dict.fromkeys(missing_fact_scene_names)))
    duplicate_names = sorted({name for name in scene_names if scene_names.count(name) > 1})
    if duplicate_names:
        add(blocking, "DUPLICATED_SCENE_NAMES", "存在重复场景名称：" + "、".join(duplicate_names))

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
