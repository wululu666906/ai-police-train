"""Compile generated scenes into bounded, finishable training lifecycles."""
from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def compile_scene_lifecycles(case_info: dict[str, Any], scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compiled = []
    for scene_index, source in enumerate(scenes, start=1):
        scene = dict(source)
        if scene.get("lifecycle_version") == "training_lifecycle_v2" and scene.get("entry_contract") and scene.get("exit_contract"):
            compiled.append(scene)
            continue
        phase = _text(scene.get("training_entry_phase")) or "post_incident_onsite"
        overall_completion = [
            _text(item) for item in scene.get("completion_criteria") or [] if _text(item)
        ]
        if not overall_completion:
            overall_completion = ["当前场景核心事实已经核实", "当前警务任务已经处置或明确移交", "已说明下一步程序"]
        scene["scene_purpose"] = _text(scene.get("scene_purpose")) or "围绕本案当前警务环节开展针对性训练。"
        scene["training_goal"] = _text(scene.get("training_goal")) or "完成当前场景的警务处置任务。"
        scene["start_state"] = _text(scene.get("start_state")) or "案件主要行为已经发生，民警进入当前处置阶段。"
        scene["completion_criteria"] = overall_completion
        scene["end_prompt"] = _text(scene.get("end_prompt")) or "本场景核心目标已完成，可结束训练或继续补充非必要询问。"
        impression_parts = [
            _text(scene.get("first_impression")),
            _text(scene.get("scene_description")),
        ]
        visible_roles = [str(item).strip() for item in (scene.get("roles") or []) if str(item).strip()]
        if visible_roles:
            impression_parts.append(f"当前可接触人员：{'、'.join(visible_roles)}。")
        time_place = "，".join(filter(None, [_text(scene.get("time")), _text(scene.get("place"))]))
        if time_place:
            impression_parts.insert(0, f"当前时空：{time_place}。")
        if phase == "intake":
            impression_parts.append("当前仅掌握接警或任务派发信息，民警需要先核实要素并形成出警判断。")
        elif phase == "post_incident_onsite":
            impression_parts.append("案件主要行为已经发生，民警应根据案发后可见状态判断残余风险，再开展处置和初查。")
        elif phase == "post_incident_inquiry":
            impression_parts.append("现场主要风险已处置，当前应围绕人物亲历范围、时间线和信息来源开展询问。")
        else:
            impression_parts.append("当前进入案发后跟进阶段，应围绕证据缺口、协同事项和风险闭环开展处置。")
        scene["first_impression"] = "\n".join(dict.fromkeys(item for item in impression_parts if item))
        stages = []
        raw_stages = scene.get("stages") if isinstance(scene.get("stages"), list) else []
        for stage_index, raw in enumerate(raw_stages, start=1):
            stage = dict(raw) if isinstance(raw, dict) else {}
            name = _text(stage.get("stage_name")) or f"阶段{stage_index}"
            goal = _text(stage.get("stage_goal")) or "完成当前处置任务"
            points = stage.get("assessment_points") if isinstance(stage.get("assessment_points"), list) else []
            observable = []
            for point in points:
                label = _text(point.get("label") if isinstance(point, dict) else point)
                if label and label not in observable:
                    observable.append(label)
            if not observable:
                observable = [goal]
            explicit_stage_completion = [
                _text(item) for item in stage.get("completion_criteria") or [] if _text(item)
            ]
            stage_completion = explicit_stage_completion or [f"已完成：{item}" for item in observable[:5]]
            if stage_index == len(raw_stages):
                stage_completion = list(dict.fromkeys([*stage_completion, *overall_completion]))
            stage.update(
                {
                    "stage_name": name,
                    "stage_goal": goal,
                    "observable_actions": observable[:8],
                    "entry_condition": "场景开始" if stage_index == 1 else f"完成上一阶段：{stages[-1]['stage_name']}",
                    "completion_criteria": stage_completion,
                    "exit_conditions": stage_completion,
                    "max_turns": max(4, min(10, len(observable) * 2 + 2)),
                    "stuck_recovery": "连续两轮无新信息时，角色回到学员当前问题并给出一项可核实细节；仍无进展则允许进入处置收尾。",
                    "role_response_policy": "优先回答当前问题；只披露当前时点本人知道的事实；有效安抚后逐步恢复配合。",
                    "transition_mode": "observable_actions",
                }
            )
            stages.append(stage)
        if not stages:
            stages = [{
                "stage_name": "现场核实",
                "stage_goal": "控制风险并核实警情基本事实",
                "observable_actions": ["确认人员安全", "核实时间地点和事件经过", "说明下一步处置"],
                "entry_condition": "场景开始",
                "exit_conditions": ["风险已经受控", "关键事实已经核实", "后续处置已经说明"],
                "max_turns": 8,
                "stuck_recovery": "连续两轮无进展时提供一项可核实细节并进入收尾。",
                "role_response_policy": "优先回答当前问题，安抚有效后逐步配合。",
                "transition_mode": "observable_actions",
            }]
        stages[-1]["completion_criteria"] = list(dict.fromkeys([
            *(stages[-1].get("completion_criteria") or stages[-1].get("exit_conditions") or []),
            *overall_completion,
        ]))
        stages[-1]["exit_conditions"] = stages[-1]["completion_criteria"]
        scene["stages"] = stages
        scene["entry_contract"] = {
            "student_role": "民警",
            "training_entry_phase": phase,
            "entry_time_policy": _text(scene.get("entry_time_policy")) or "after_canonical_event",
            "canonical_outcome_locked": True,
            "dispatch_brief": _text(scene.get("dispatch_brief")),
            "first_impression": _text(scene.get("first_impression")),
            "opening_rule": "角色先表现当前诉求或案发后的可观察状态，不向学员朗读人物设定，不把历史行为表演成正在发生。",
            "impact_boundary": "学员只影响处置质量、证据完整度和沟通效果，不得改变案件既定事实与结果。",
        }
        scene["exit_contract"] = {
            "required": overall_completion,
            "emotion_requirement": "不要求情绪归零；达到可沟通或现场可控即可结束。",
            "hard_turn_limit": sum(int(stage.get("max_turns") or 6) for stage in stages),
            "success_prompt": scene["end_prompt"],
            "stuck_prompt": "本场景已达到建议轮次上限。系统将列出尚未完成的训练目标，学员可结束训练或继续补充处置。",
        }
        scene["lifecycle_version"] = "training_lifecycle_v2"
        compiled.append(scene)
    return compiled
