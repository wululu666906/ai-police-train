"""Compile case intelligence into observable training tasks and state nodes."""
from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_training_tasks(case_info: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Produce a stable, executable task contract without asking an LLM again."""
    intelligence = case_info.get("case_intelligence") if isinstance(case_info.get("case_intelligence"), dict) else {}
    claim_ids = [str(item.get("claim_id") or "") for item in _list(intelligence.get("claims")) if isinstance(item, dict)]
    tasks = []
    for scene_index, scene in enumerate(scenes, start=1):
        scene_fact_ids = [str(item) for item in _list(scene.get("fact_ids")) if str(item).strip()]
        stages = _list(scene.get("stages"))
        if not stages:
            stages = [{"stage_name": "信息核实", "stage_goal": scene.get("training_goal") or scene.get("scene_description") or "完成现场信息核实"}]
        for stage_index, stage in enumerate(stages, start=1):
            goal = _text(stage.get("stage_goal") if isinstance(stage, dict) else "") or "完成当前训练目标"
            name = _text(stage.get("stage_name") if isinstance(stage, dict) else "") or f"阶段{stage_index}"
            observable_actions = [
                _text(item)
                for item in _list(stage.get("observable_actions") if isinstance(stage, dict) else [])
                if _text(item)
            ] or [goal]
            exit_conditions = [
                _text(item)
                for item in _list(stage.get("exit_conditions") if isinstance(stage, dict) else [])
                if _text(item)
            ] or [f"已完成：{item}" for item in observable_actions]
            tasks.append({
                "task_id": f"T{scene_index}-{stage_index}",
                "scene_index": scene_index,
                "title": name,
                "competency": "警情处置与事实核实",
                "objective": goal,
                "expected_actions": observable_actions,
                "prohibited_actions": [],
                "observable_evidence": observable_actions,
                "entry_condition": _text(stage.get("entry_condition") if isinstance(stage, dict) else ""),
                "exit_conditions": exit_conditions,
                "max_turns": max(2, min(20, int(stage.get("max_turns", 8) or 8))) if isinstance(stage, dict) else 8,
                "stuck_recovery": _text(stage.get("stuck_recovery") if isinstance(stage, dict) else ""),
                # A task may only be assessed against facts assigned to its own
                # scene. Falling back to case-wide claims made every scene look
                # like a copy of the whole case when stage references were absent.
                "source_claim_ids": [item for item in _list(stage.get("fact_ids") if isinstance(stage, dict) else []) if item] or scene_fact_ids or claim_ids[:1],
                "critical": stage_index == 1,
            })
    return tasks


def compile_state_machine(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    states = []
    for index, task in enumerate(tasks, start=1):
        states.append({
            "state_id": f"S{index}",
            "task_id": task["task_id"],
            "phase": task["title"],
            "entry_conditions": [task["entry_condition"]] if task.get("entry_condition") else ([] if index == 1 else [f"S{index - 1}:objectives_complete"]),
            "exit_conditions": task.get("exit_conditions") or ["objectives_complete"],
            "max_turns": task.get("max_turns") or 8,
            "stuck_recovery": task.get("stuck_recovery") or "连续两轮无新进展时提供可核实信息并允许收尾。",
            "on_events": {
                "evidence_presented": "increase_clarity",
                "risk_control": "decrease_risk",
                "contradiction_challenged": "allow_partial_disclosure",
            },
        })
    return {"schema_version": 1, "initial_state": states[0]["state_id"] if states else None, "states": states}


def build_observable_scoring_rules(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn training objectives into deterministic, inspectable score rules."""
    rules = []
    for task in tasks:
        rules.append({
            "rule_id": f"R-{task['task_id']}",
            "task_id": task["task_id"],
            "label": task["title"],
            "observable_actions": task.get("observable_evidence") or task.get("expected_actions") or [],
            "source_claim_ids": task.get("source_claim_ids") or [],
            "weight": 20 if task.get("critical") else 10,
            "critical": bool(task.get("critical")),
            "pass_condition": "至少命中一项可观察行为",
            "failure_condition": "阶段结束前未命中可观察行为",
        })
    return rules
