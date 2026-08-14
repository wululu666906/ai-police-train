"""Dialogue-adapted scene admission rules for AI multi-role conversation training."""

from __future__ import annotations

from typing import Any


ADMISSION_RULE_VERSION = "dialogue_scene_admission_v1"

# Scenes whose core competency cannot be exercised through text dialogue simulation.
NON_DIALOGUE_MARKERS = (
    "追捕", "追逃", "抓捕行动", "围捕", "设卡", "堵截", "武装突袭", "武装抓捕",
    "战术配合", "班组协同", "编队", "队形", "火力", "狙击手", "特警攻坚",
    "无人机", "警犬", "追踪犬", "体能追捕", "奔跑追击", "徒步追捕",
    "现场调度", "指挥调度", "电台调度", "警力部署", "封控圈", "包围圈",
    "武装押解", "押送途中", "解铐", "搜身控制", "强制带离",
    "车辆追击", "追车", "路检", "查缉", "突击检查",
    "审讯突破", "讯问突破", "审讯室突破", "攻心战术",
    "实弹", "射击", "枪械", "破拆", "破门",
)

# Strong dialogue-fit markers: language, interaction, verbal handling.
DIALOGUE_CORE_MARKERS = (
    "询问", "问询", "核实", "调解", "沟通", "安抚", "劝导", "告知", "解释",
    "劝阻", "答疑", "对话", "交流", "陈述", "核对", "澄清", "倾听", "话术",
    "情绪", "矛盾", "纠纷", "协商", "接待", "接待群众", "现场稳控",
    "风险筛查", "身份核实", "要素核实", "线索核实", "信息核实", "到场接触", "人员接触",
    "政策", "法规", "释法", "舆情", "围观", "投诉",
    "报警", "接警", "求助", "举报",
)

# Preferred high-value dialogue scene archetypes for generation guidance.
PREFERRED_DIALOGUE_ARCHETYPES = (
    "现场应急处置",
    "群众纠纷调解",
    "政策沟通答疑",
    "舆情劝导化解",
    "接警要素核实",
    "到场人员接触",
    "陈述矛盾核对",
    "风险稳控沟通",
    "预警劝阻沟通",
    "线索摸排询问",
)

# Remap hints when rejecting a non-dialogue scene name/goal.
REJECTION_ALTERNATIVES = {
    "追捕": "到案后身份核实与现场稳控沟通",
    "追逃": "报警线索核实与到场人员接触",
    "抓捕": "到案后控制与身份核实对话",
    "审讯": "案发后信息核实与陈述矛盾核对",
    "讯问": "关键人员陈述核实与矛盾核对",
    "突破": "陈述时间线建立与信息来源核实",
    "战术": "现场风险稳控与多方沟通",
    "调度": "到场人员接触与情况核实",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _scene_text_parts(scene: dict[str, Any]) -> list[str]:
    parts = [
        scene.get("scene_name"),
        scene.get("scene_description"),
        scene.get("scene_purpose"),
        scene.get("training_goal"),
        scene.get("start_state"),
        scene.get("dispatch_brief"),
        scene.get("first_impression"),
        scene.get("scene_kind"),
    ]
    for item in scene.get("expected_outcomes") or []:
        parts.append(item)
    for item in scene.get("completion_criteria") or []:
        parts.append(item)
    for stage in scene.get("stages") or []:
        if isinstance(stage, dict):
            parts.extend((stage.get("stage_name"), stage.get("stage_goal")))
            for point in stage.get("assessment_points") or []:
                if isinstance(point, dict):
                    parts.append(point.get("label"))
    return [_text(item) for item in parts if _text(item)]


def _matched_markers(text: str, markers: tuple[str, ...]) -> list[str]:
    return [marker for marker in markers if marker in text]


def _interactive_role_count(scene: dict[str, Any]) -> int:
    roles = scene.get("roles") or scene.get("role_names") or []
    role_ids = scene.get("role_ids") or []
    scene_roles = scene.get("scene_roles") or []
    count = len([item for item in roles if _text(item)])
    count = max(count, len([item for item in role_ids if _text(item)]))
    count = max(count, len([item for item in scene_roles if isinstance(item, dict)]))
    return count


def suggest_dialogue_alternative(scene: dict[str, Any]) -> str:
    blob = " ".join(_scene_text_parts(scene))
    for token, alternative in REJECTION_ALTERNATIVES.items():
        if token in blob:
            return alternative
    return "现场人员接触与关键信息核实对话"


def evaluate_dialogue_admission(scene: dict[str, Any]) -> dict[str, Any]:
    """Return admission verdict for a single scene blueprint."""
    if not isinstance(scene, dict):
        return {
            "admitted": False,
            "rule_version": ADMISSION_RULE_VERSION,
            "reasons": ["invalid_scene_payload"],
            "non_dialogue_markers": [],
            "dialogue_markers": [],
            "dialogue_fit_score": 0.0,
            "suggested_alternative": PREFERRED_DIALOGUE_ARCHETYPES[0],
        }

    blob = " ".join(_scene_text_parts(scene))
    non_dialogue = _matched_markers(blob, NON_DIALOGUE_MARKERS)
    dialogue = _matched_markers(blob, DIALOGUE_CORE_MARKERS)
    interactive_roles = _interactive_role_count(scene)

    reasons: list[str] = []
    if non_dialogue:
        reasons.append("non_dialogue_core_competency")
    if interactive_roles < 1:
        reasons.append("missing_interactive_roles")
    if not dialogue and not non_dialogue:
        # Ambiguous goal with no clear dialogue anchor — warn-level reject for generation.
        reasons.append("missing_dialogue_core_markers")

    # Non-dialogue markers dominate when present without sufficient dialogue anchors.
    if non_dialogue and len(dialogue) < 2:
        reasons.append("insufficient_dialogue_coverage")

    # Pure physical/tactical goals even if phrased as police work.
    tactical_only = any(token in blob for token in ("追捕", "追逃", "抓捕行动", "战术", "调度", "审讯突破"))
    if tactical_only and len(dialogue) < 2:
        reasons.append("tactical_goal_not_dialogue_trainable")

    dialogue_score = round(len(dialogue) / max(len(dialogue) + len(non_dialogue), 1), 4)
    admitted = not reasons

    return {
        "admitted": admitted,
        "rule_version": ADMISSION_RULE_VERSION,
        "reasons": reasons,
        "non_dialogue_markers": non_dialogue,
        "dialogue_markers": dialogue,
        "interactive_role_count": interactive_roles,
        "dialogue_fit_score": dialogue_score,
        "suggested_alternative": suggest_dialogue_alternative(scene) if not admitted else "",
    }


def is_dialogue_adapted_scene(scene: dict[str, Any]) -> bool:
    return bool(evaluate_dialogue_admission(scene).get("admitted"))


def remap_scene_for_dialogue_admission(scene: dict[str, Any]) -> dict[str, Any]:
    alternative = suggest_dialogue_alternative(scene)
    remapped = dict(scene)
    remapped["scene_name"] = alternative
    remapped["training_goal"] = (
        f"通过多轮对话完成{alternative}，核实关键信息、稳控现场风险并形成规范处置记录。"
    )
    remapped["scene_purpose"] = f"训练学员在{alternative}环节中的沟通处置与逻辑应对能力。"
    remapped["expected_outcomes"] = [
        "通过对话核实关键信息",
        "稳控现场风险并完成规范告知",
        "形成可复盘的多轮交互记录",
    ]
    remapped["completion_criteria"] = [
        "已完成关键信息核实对话",
        "已稳控现场风险或明确移交",
    ]
    remapped["stages"] = [{
        "stage_name": "沟通核实",
        "stage_goal": remapped["training_goal"],
        "assessment_points": [
            {"id": "dialogue_facts", "label": "核实关键事实", "required": True, "keywords": ["核实", "询问", "确认"]},
            {"id": "dialogue_risk", "label": "稳控现场风险", "required": True, "keywords": ["安全", "风险", "安抚"]},
        ],
        "fact_ids": list(remapped.get("fact_ids") or []),
    }]
    remapped["dialogue_admission_remapped"] = True
    remapped["dialogue_admission"] = evaluate_dialogue_admission(remapped)
    return remapped


def filter_dialogue_admitted_scenes(
    candidates: list[dict[str, Any]],
    *,
    allow_remap: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    admitted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in candidates:
        verdict = evaluate_dialogue_admission(item)
        enriched = {**item, "dialogue_admission": verdict}
        if verdict.get("admitted"):
            admitted.append(enriched)
        else:
            rejected.append(enriched)

    if not admitted and rejected and allow_remap:
        best = max(rejected, key=lambda row: float((row.get("dialogue_admission") or {}).get("dialogue_fit_score") or 0))
        remapped = remap_scene_for_dialogue_admission(best)
        if remapped.get("dialogue_admission", {}).get("admitted"):
            admitted = [remapped]
    return admitted, rejected


def admission_prompt_block() -> str:
    preferred = "、".join(PREFERRED_DIALOGUE_ARCHETYPES)
    blocked = "、".join(NON_DIALOGUE_MARKERS[:18])
    return (
        "平台仅生成对话适配型实训场景：核心考核点必须是语言沟通、多轮交互、话术处置、逻辑应对。"
        f"优先生成{preferred}等强对话、高交互场景。"
        f"禁止生成以{blocked}等为核心、无法通过纯文本多角色对话完整还原的非适配场景。"
        "若原案包含追捕、武装抓捕、团队战术、现场指挥调度、线下体能控制等非对话环节，"
        "必须改写为到场后的人员接触、身份核实、风险稳控、陈述核对、调解沟通等可对话训练节点，"
        "不得保留追捕行动、战术配合、审讯突破等场景名称或训练目标。"
        "每个场景至少绑定 1 名可交流角色，训练目标须明确学员需要通过对话完成的处置动作。"
    )
