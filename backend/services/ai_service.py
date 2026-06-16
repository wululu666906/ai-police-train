import json
from typing import Any

from sqlalchemy.orm import Session

import models
from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
from .case_knowledge_service import load_case_knowledge_bundle
from .persona_engine import (
    analyze_dialogue_momentum,
    build_persona_profile,
    build_personalized_questions,
    build_recent_memory,
    build_role_script,
    derive_stage_dynamic_adjustment,
    evaluate_truth_stage,
    format_memory_block,
    format_persona_block,
    summarize_session_memory,
)
from .multi_role_service import (
    generate_multi_role_turn,
    serialize_scene_roles,
    should_use_scene_conversation,
)
from .role_resolver import is_role_speakable, resolve_scene_role, resolve_scene_roles
from .dialogue_sequence_service import build_intake_sequence_feedback, merge_sequence_feedback
from .dialogue_sanitize_service import sanitize_spoken_line
from .opening_turn_service import infer_session_scene_kind
from .stage_config_service import find_stage_config, infer_scene_kind, normalize_stages
from .prompts.training_voice_layers import TRAINING_VOICE_LAYER_PROMPT
from .state_contract_postcheck import apply_contract_postcheck, postcheck_reply_turns, validate_response_against_contract
from .state_influence_metrics import build_session_metrics, record_turn_metrics
from .state_influence_engine import (
    blend_four_axis_state,
    build_state_contract,
    cap_new_fact_for_contract,
    enrich_momentum_with_axis_deltas,
    format_state_contract_block,
    generation_temperature_for_contract,
)
from .training_runtime_service import (
    build_closure_message,
    build_follow_up_reply,
    collect_stage_progress,
    detect_actions_from_text,
    dump_runtime_state,
    evaluate_end_conditions,
    evaluate_stage_completion,
    load_runtime_state,
)

SYSTEM_PROMPT_TEMPLATE = """
你正在扮演“{role_name}”，不是助手，不是旁白，而是案件中的真实角色本人。

你必须遵守以下规则：
1. 只能依据案件事实、角色设定、当前训练阶段、警方已掌握信息和本轮输入作答。
2. 不要凭空补全案件，不要主动把整条案情一次性说完。
3. 回答要像真实人类：允许犹豫、改口、情绪化、打断、补半句，但不能机械重复。
4. 优先按照“当前场景行为模式 + 场景边界”决定说什么、保留什么、被问到什么才会松口，不要机械套用固定三栏。
5. 不知道的就说不知道；不愿主动说的可以保留，但保留方式要自然。
6. 如果警方问得笼统，就给有限且口语化的回答；如果问得具体、击中软肋或动作触发了你，才逐步多说一点。
7. 只输出一个合法 JSON 对象，不要输出解释和 markdown。

案件信息：
- 案发时间：{case_time}
- 案发地点：{case_location}
- 报警时间：{report_time}
- 时间线：
{timeline}

案件库与角色剧本库：
{case_knowledge_block}

角色画像：
- 角色类型：{role_type}
- 行为原型：{behavior_archetype}
- 互动风格：{interaction_style}
- 当前状态：{status}
- 性格特点：{personality}
- 说话风格：{speaking_style}
- 对警方基本态度：{police_attitude}
- 当前诉求：{current_goal}
- 核心顾虑：{core_concern}
- 关系压力：{relationship_pressure}
- 对外口径：{surface_stance}
- 受压反应：{pressure_response}
- 情绪触发点：{trigger_points}
- 可安抚点：{calming_points}
- 当前情绪：{emotion}/100
- 当前信任：{trust}/100
- 当前配合：{cooperation}/100
- 当前风险：{risk}/100
- 当前表达清晰度：{clarity}/100
（注：信任度是角色对警方的信任水平，配合度是表面愿意配合的程度——两者数值可能接近但概念不同，需分别判断。输出的 updated_trust 和 updated_cooperation 分别对应这两个维度。）

当前场景行为模式：
- 模式：{scene_behavior_mode}
- 当前场景边界：
{scene_boundary_block}

兼容旧事实边界：
你确实知道的事实：
{knows_facts}

你确实不知道或无法确认的事实：
{does_not_know}

你可能不愿主动说出的事实：
{hidden_truths}

当前训练阶段：
- 阶段名称：{current_stage}
- 阶段目标：{current_stage_goal}
- 本阶段已累计学员发言轮次：{stage_turn_count}
- 本阶段建议最低轮次：{stage_turn_target}
- 本阶段考察点：
{stage_assessment_points}
- 本阶段可触发动作：
{stage_action_catalog}
- 警方已掌握的信息：
{revealed_info}

深层人物建模：
{persona_block}

角色约束：
{role_archetype_block}

场景约束：
{scene_mode_block}

近期记忆：
{memory_block}

本轮表现契约（必须严格遵守，优先级高于自由发挥）：
{state_contract_block}

输出要求：
1. response 只写角色本轮主要回答。
2. follow_up_response 是 response 的即时追加，表现为打断自己、改口或补充，不是新的一轮对话。只有在以下情况才允许出现，否则必须为 null：
   - 情绪过高出现打断或补半句
   - 被动作触发后产生即时反应
   - 被问到关键软肋后出现改口或补充
3. inner_thought 写角色真实心理活动，不要重复 response。可以反映角色当下的判断（"他是不是已经知道了？"）、应对策略（"先岔开这个话题"）或真实的情绪波动（"被说到痛处了"），一般15字以内短句即可。
4. new_fact_revealed 只有在本轮确实新增关键事实时填写，否则填 null。
5. updated_risk 和 updated_clarity 要结合本轮问法、动作触发和角色状态做小幅变化；没有明显变化时可沿用原值。
6. is_stage_completed 只有在本阶段信息与动作确实已足够时才可为 true。
7. updated_cooperation 对应配合度变化（表面配合意愿），与 updated_trust（信任感变化）在概念上不同，需结合本轮互动独立判断。没有明显变化时可沿用原值。

注意：以下JSON模板中的数字值为示例，请根据角色实际状态和本轮互动动态调整，不要照搬。

严格输出 JSON：
{{
  "response": "角色本轮主要回复",
  "follow_up_response": null,
  "inner_thought": "角色真实心理活动",
  "updated_emotion": 55,
  "updated_trust": 35,
  "updated_cooperation": 35,
  "updated_risk": 48,
  "updated_clarity": 62,
  "new_fact_revealed": null,
  "is_stage_completed": false
}}
""" + TRAINING_VOICE_LAYER_PROMPT


def _parse_json_list(raw_value: Any) -> list[str]:
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, dict):
        return [str(item).strip() for item in raw_value.get("revealed_info", []) if str(item).strip()]
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, dict):
            return [str(item).strip() for item in parsed.get("revealed_info", []) if str(item).strip()]
    except Exception:
        pass
    return [line.strip() for line in str(raw_value).splitlines() if line.strip()]


def _format_list_block(raw_value: Any) -> str:
    values = _parse_json_list(raw_value)
    if not values:
        return "[]"
    return "\n".join(f"- {item}" for item in values)


def _build_timeline_text(structured: dict[str, Any]) -> str:
    fact_sheet = structured.get("fact_sheet", {}) if isinstance(structured, dict) else {}
    timeline_items = fact_sheet.get("timeline") or structured.get("timeline") or []
    if isinstance(timeline_items, list):
        rows = []
        for item in timeline_items:
            if isinstance(item, dict):
                time_text = str(item.get("time", "") or "").strip()
                event_text = str(item.get("event", "") or "").strip()
                if time_text or event_text:
                    rows.append(f"- {time_text or '时间待核实'}：{event_text or '事件待核实'}")
            elif str(item).strip():
                rows.append(f"- {str(item).strip()}")
        return "\n".join(rows) if rows else "未记录"
    if isinstance(timeline_items, str) and timeline_items.strip():
        return timeline_items.strip()
    return "未记录"


def _get_case_type(case: Any) -> str:
    return str(getattr(case, "case_type", "") or "").strip()


def _get_stage_config(scene: Any, current_stage: str, case_type: str = "") -> dict[str, Any]:
    return find_stage_config(
        getattr(scene, "stages", []),
        current_stage,
        case_type=case_type,
        scene_name=str(getattr(scene, "name", "") or ""),
    )


def _format_stage_assessment_points(stage_config: dict[str, Any]) -> str:
    points = stage_config.get("assessment_points") or []
    if not points:
        return "[]"
    rows = []
    for point in points:
        label = str(point.get("label") or "考察点").strip()
        keywords = "、".join(point.get("keywords") or [])
        rows.append(f"- {label}（关键词：{keywords or '无'}）")
    return "\n".join(rows)


def _format_stage_action_catalog(stage_config: dict[str, Any]) -> str:
    actions = stage_config.get("action_catalog") or []
    if not actions:
        return "[]"
    rows = []
    for action in actions:
        label = str(action.get("label") or "动作").strip()
        aliases = "、".join(action.get("aliases") or [])
        rows.append(f"- {label}（可识别表达：{aliases or label}）")
    return "\n".join(rows)


def _get_stage_goal(scene: Any, current_stage: str, case_type: str = "") -> str:
    default_goal = "继续围绕时间、地点、人物、经过和关键矛盾点展开问询。"
    if not scene:
        return default_goal
    stage = _get_stage_config(scene, current_stage, case_type=case_type)
    if stage:
        return str(stage.get("stage_goal") or default_goal)
    return default_goal


def _advance_stage(scene: Any, current_stage: str, case_type: str = "") -> dict[str, str]:
    current_goal = _get_stage_goal(scene, current_stage, case_type=case_type)
    if not scene:
        return {"current_stage": current_stage, "current_stage_goal": current_goal}
    stages = normalize_stages(
        getattr(scene, "stages", []),
        case_type=case_type,
        scene_name=str(getattr(scene, "name", "") or ""),
    )

    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        if stage.get("stage_name") == current_stage:
            if index + 1 < len(stages) and isinstance(stages[index + 1], dict):
                next_stage = str(stages[index + 1].get("stage_name") or current_stage)
                return {
                    "current_stage": next_stage,
                    "current_stage_goal": _get_stage_goal(scene, next_stage, case_type=case_type),
                }
            break

    return {"current_stage": current_stage, "current_stage_goal": current_goal}


def _clamp_score(value: Any, default: int) -> int:
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        numeric_value = default
    return max(0, min(100, numeric_value))


def _infer_truth_stage(trust: int, emotion: int) -> str:
    if trust >= 78:
        return "mostly_open"
    if trust >= 62:
        return "meaningful_disclosure"
    if trust >= 48:
        return "partial_release"
    if emotion >= 76:
        return "emotional_leak"
    return "guarded_denial"


def _format_scene_boundary_block(persona_profile: dict[str, Any]) -> str:
    boundary = persona_profile.get("scene_boundary") if isinstance(persona_profile, dict) else {}
    if not isinstance(boundary, dict):
        boundary = {}
    labels = {
        "known_key_points": "可直接说出的关键点",
        "withheld_key_points": "不会主动交代的关键点",
        "conflict_core": "冲突核心",
        "acceptable_outcomes": "可接受结果",
        "no_go_topics": "绝对不愿碰的话题",
        "trigger_sources": "容易被什么刺激",
        "concerned_targets": "最在意的人或对象",
        "taboo_actions": "最反感的警方做法",
        "escalation_actions": "什么动作会让其更失控",
        "deescalation_conditions": "什么条件下更容易缓和",
    }
    lines: list[str] = []
    for key, label in labels.items():
        values = [str(item).strip() for item in (boundary.get(key) or []) if str(item).strip()]
        if values:
            lines.append(f"- {label}：{'；'.join(values[:4])}")
    return "\n".join(lines) if lines else "- 当前还没有补充专属边界信息，先以角色诉求、顾虑和旧事实边界自然作答。"


def _role_state_label(cooperation: int, emotion: int, risk: int | None = None, clarity: int | None = None) -> str:
    risk = _clamp_score(risk, 50) if risk is not None else 50
    clarity = _clamp_score(clarity, 50) if clarity is not None else 50
    if risk >= 78 or emotion >= 82:
        return "接近失控边缘"
    if clarity <= 32 and emotion >= 70:
        return "表达混乱且波动大"
    if cooperation >= 68 and risk <= 45:
        return "愿意沟通"
    if cooperation <= 30 and risk >= 60:
        return "强烈对抗"
    if clarity >= 68 and cooperation >= 55:
        return "信息逐渐清晰"
    return "谨慎应对"


def _build_persona_hint(role: Any) -> str:
    weakness = str(getattr(role, "weakness", "") or "").strip()
    personality = str(getattr(role, "personality", "") or "").strip()
    if weakness:
        return f"当前角色弱点：{weakness}"
    if personality:
        return f"当前角色性格重点：{personality}"
    return ""


def _build_role_archetype_block(role: Any, scene: Any, persona_profile: dict[str, Any] | None = None) -> str:
    persona_profile = persona_profile or {}
    role_type = str(getattr(role, "role_type", "") or "").strip()
    interaction_style = str(persona_profile.get("interaction_style") or getattr(role, "interaction_style", "") or "").strip()
    behavior_archetype = str(persona_profile.get("behavior_archetype") or "").strip()
    police_attitude = str(persona_profile.get("police_attitude") or persona_profile.get("authority_attitude") or "").strip()
    current_goal = str(persona_profile.get("current_goal") or persona_profile.get("current_need") or "").strip()
    core_concern = str(persona_profile.get("core_concern") or getattr(role, "weakness", "") or "").strip()
    trigger_points = [str(item).strip() for item in (persona_profile.get("trigger_points") or []) if str(item).strip()]
    calming_points = [str(item).strip() for item in (persona_profile.get("calming_points") or []) if str(item).strip()]
    scene_name = str(getattr(scene, "name", "") or "").strip()

    rules: list[str] = []
    if "报警" in role_type or "接警" in scene_name:
        rules.append("更像报警人或目击者，只掌握局部信息，不会主动整理成完整笔录。")
    if role_type in {"受害人", "被害人"}:
        rules.append("更在意伤害、损失和责任，表达可带情绪，但事实不一定完整。")
    if role_type == "嫌疑人":
        rules.append("默认会淡化责任、切割主观故意，只有被持续压实时才会明显松口。")
    if interaction_style == "对抗型":
        rules.append("会顶嘴、反问、切话题，但不要每轮无意义硬顶。")
    elif interaction_style == "情绪型":
        rules.append("更容易抱怨、激动、跑题，稳定情绪后信息质量才会提升。")
    elif interaction_style == "观察型":
        rules.append("会先观察警方掌握了多少，再决定说多少。")
    else:
        rules.append("会在被具体提问后持续补充，而不是一口气说完。")

    if behavior_archetype == "防御切责型":
        rules.append("会优先淡化主动责任、切割关键行为，尽量不让最重后果先落到自己头上。")
    elif behavior_archetype == "强硬对抗型":
        rules.append("如果被命令式压问或当众定性，更容易抢话、反问和顶撞。")
    elif behavior_archetype == "谨慎回避型":
        rules.append("会先给保守、局部的信息，确认安全后才可能逐步补细节。")
    elif behavior_archetype == "委屈宣泄型":
        rules.append("会反复强调自己吃亏、委屈和损失，事实表达可能夹杂情绪。")
    elif behavior_archetype == "醉酒失控型":
        rules.append("在刺激和约束下反应会更跳、更冲，表达顺序和逻辑容易失控。")
    elif behavior_archetype == "绝望封闭型":
        rules.append("对空泛说教和硬性逼问更容易关闭自己，可能沉默、拒答或突然失控。")
    elif behavior_archetype == "围观起哄型":
        rules.append("容易借着围观气氛壮胆，若觉得被针对会继续起哄或煽动旁人。")
    elif behavior_archetype == "创伤受害型":
        rules.append("最先需要安全感和被相信；若被暗示有错或被逼完整复述，会退缩、断续或情绪崩溃。")
    elif behavior_archetype == "精神危机型":
        rules.append("现实感和情绪稳定性波动大；遇到多人逼问、突然靠近或否定感受时，可能激动、拒答或失控。")
    elif behavior_archetype == "利益算计型":
        rules.append("会清楚表达对自己有利的信息，但对责任、赔偿和关键不利事实保持选择性配合。")
    elif behavior_archetype == "权威敏感型":
        rules.append("核心反应不是单纯不配合，而是对被命令、当众羞辱、扣帽子极敏感；给台阶后才可能有限配合。")
    elif behavior_archetype == "沉默恐惧型":
        rules.append("害怕报复或牵连，可能只给边缘信息；即使情绪下降，也需要保护承诺才会逐步补关键事实。")
    elif behavior_archetype == "过度依赖型":
        rules.append("愿意靠近警方但焦虑反复，需要明确下一步、责任人和联系渠道，否则会不断重复诉求。")
    elif behavior_archetype == "求助配合型":
        rules.append("如果确认警方在认真处理，配合度会明显提升。")

    if police_attitude == "主动求助":
        rules.append("会关注警方是否真的在解决问题，如果感到被敷衍会重复诉求。")
    elif police_attitude == "试探观望":
        rules.append("不会一次性把话说满，会先看警方态度和掌握程度再决定补多少。")
    elif police_attitude == "防备排斥":
        rules.append("对可能被定性、被压责任的话题会本能防守，先切责任再谈细节。")
    elif police_attitude == "敌对抵触":
        rules.append("面对强压和先入为主的判断时更容易直接对着干，但并非每轮都要硬顶。")

    if current_goal and core_concern:
        rules.append(
            f"内部动机会围绕“{current_goal}”，内心顾虑会影响语气和是否愿意多说，但不要在台词里直接复述配置字段或说「我最怕/最担心的是……」。"
        )
    elif current_goal:
        rules.append(f"眼下优先想保住或达成的是“{current_goal}”。")

    if trigger_points:
        rules.append(f"被问到“{trigger_points[0]}”这类点时，更可能出现回避、改口或情绪波动。")
    if calming_points:
        rules.append(f"如果警方先做到“{calming_points[0]}”，更容易让其继续交流。")
    return "\n".join(f"- {item}" for item in rules)


def _build_scene_mode_block(scene: Any, current_stage: str, current_stage_goal: str) -> str:
    scene_name = str(getattr(scene, "name", "") or "").strip()
    rules: list[str] = []
    if infer_scene_kind(scene_name, current_stage) == "intake" or "接警" in scene_name or "接警" in current_stage:
        rules.append("这是110接警电话场景：若你已主动说过出了什么事，而接警员跳过事件性质直接问时间、地点或联系方式，可以口语化提醒对方先听你说清情况。")
        rules.append("接警阶段优先弄清事件性质与是否仍需救助，再逐步补充地点、时间和身份。")
    if "现场" in scene_name or "现场" in current_stage:
        rules.append("现场阶段更贴近目击视角和即时反应，不要把表达变成书面总结。")
    if any(token in current_stage for token in ["调查", "问询", "矛盾", "压实", "审讯", "讯问"]):
        rules.append("调查压实阶段突出时间线、矛盾点、证据和关系压力。")
    if current_stage_goal:
        rules.append(f"本轮始终围绕“{current_stage_goal[:40]}”相关内容作出回应。")
    return "\n".join(f"- {item}" for item in rules)


def _count_user_turns(messages: list[Any]) -> int:
    return sum(1 for message in messages if getattr(message, "role", "") == "user")


def _stage_turn_target(current_stage: str) -> int:
    stage_text = str(current_stage or "")
    if any(token in stage_text for token in ["接警", "初始", "初查", "信息初核"]):
        return 3
    if any(token in stage_text for token in ["现场", "情况摸排", "关键要素确认"]):
        return 4
    if any(token in stage_text for token in ["调查", "问询", "矛盾", "压实", "时间线"]):
        return 4
    return 3


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _build_stage_requirements(current_stage: str, current_stage_goal: str, scene: Any) -> list[dict[str, Any]]:
    stage_text = str(current_stage or "")
    goal_text = str(current_stage_goal or "")
    scene_name = str(getattr(scene, "name", "") or "")

    requirement_sets = {
        "identity": {"label": "身份/关系", "keywords": ["姓名", "身份", "你是谁", "叫什么", "关系", "什么关系"]},
        "time": {"label": "时间", "keywords": ["什么时候", "几点", "时间", "何时", "先后", "时间线"]},
        "location": {"label": "地点", "keywords": ["哪里", "地点", "位置", "几号楼", "哪个房间", "现场在哪"]},
        "people": {"label": "人物", "keywords": ["谁在场", "还有谁", "哪些人", "对方是谁", "都有哪些人"]},
        "process": {"label": "什么事/经过", "keywords": ["什么事", "怎么回事", "发生了什么", "什么情况", "经过", "具体怎么发生", "谁先"]},
        "risk": {"label": "风险/伤情", "keywords": ["受伤", "危险", "安全", "120", "刀", "还在现场", "风险"]},
        "evidence": {"label": "证据/现场", "keywords": ["监控", "证据", "录像", "聊天记录", "血迹", "现场", "物证"]},
        "contradiction": {"label": "矛盾点", "keywords": ["前后不一致", "对不上", "矛盾", "为什么不一样", "改口"]},
        "motive": {"label": "动机/利益", "keywords": ["为什么", "动机", "原因", "图什么", "利益", "冲突"]},
    }

    if infer_scene_kind(scene_name, stage_text) == "intake" or "接警" in scene_name or any(
        token in stage_text for token in ["接警", "信息初核"]
    ):
        keys = ["process", "risk", "location", "time", "identity"]
    elif any(token in scene_name for token in ["现场", "初查", "勘查"]) or any(token in stage_text for token in ["现场", "情况摸排", "关键要素确认"]):
        keys = ["identity", "people", "process", "risk"]
    elif any(token in scene_name for token in ["重点询问", "矛盾"]) or any(token in stage_text for token in ["矛盾", "压实", "关键压实"]):
        keys = ["time", "process", "contradiction", "motive"]
    elif any(token in scene_name for token in ["审讯", "讯问", "嫌疑人"]) or any(token in stage_text for token in ["审讯", "讯问", "时间线压实"]):
        keys = ["time", "process", "contradiction", "evidence"]
    else:
        keys = ["time", "location", "people", "process"]

    if "关系" in goal_text and "identity" not in keys:
        keys.append("identity")
    if "证据" in goal_text and "evidence" not in keys:
        keys.append("evidence")
    if "风险" in goal_text and "risk" not in keys:
        keys.append("risk")

    return [requirement_sets[key] for key in keys if key in requirement_sets]


def _evaluate_stage_coverage(
    history: list[Any],
    user_message: str,
    revealed_info: list[str],
    new_fact: Any,
    current_stage: str,
    current_stage_goal: str,
    scene: Any,
    *,
    recognized_actions: list[dict[str, Any]] | None = None,
    case_type: str = "",
) -> dict[str, Any]:
    stage_config = _get_stage_config(scene, current_stage, case_type=case_type)
    if stage_config and stage_config.get("assessment_points"):
        progress = collect_stage_progress(
            stage_config,
            history,
            revealed_info + ([str(new_fact).strip()] if str(new_fact or "").strip() and str(new_fact).strip().lower() != "null" else []),
            extra_texts=[str(user_message or "").strip()],
            recognized_actions=recognized_actions or [],
        )
        return {
            "requirements": progress["summary"]["requirements"],
            "satisfied": progress["summary"]["satisfied"],
            "missing": progress["summary"]["missing"],
            "minimum_required": len(progress["summary"]["requirements"]),
            "coverage_count": len(progress["summary"]["satisfied"]),
            "enough_coverage": not progress["summary"]["missing"],
            "assessment_progress": progress,
        }

    user_turns = [str(getattr(message, "content", "") or "").strip() for message in history if getattr(message, "role", "") == "user"]
    corpus = "\n".join([item for item in user_turns[-6:] if item] + [str(user_message or "").strip()])
    reveal_corpus_parts = list(revealed_info)
    if str(new_fact or "").strip() and str(new_fact).strip().lower() != "null":
        reveal_corpus_parts.append(str(new_fact).strip())
    reveal_corpus = "\n".join(reveal_corpus_parts)

    requirements = _build_stage_requirements(current_stage, current_stage_goal, scene)
    satisfied = []
    missing = []
    for requirement in requirements:
        label = requirement["label"]
        keywords = requirement["keywords"]
        hit = _contains_any(corpus, keywords) or _contains_any(reveal_corpus, keywords)
        if hit:
            satisfied.append(label)
        else:
            missing.append(label)

    minimum_required = 3 if len(requirements) >= 4 else max(1, len(requirements))
    return {
        "requirements": [item["label"] for item in requirements],
        "satisfied": satisfied,
        "missing": missing,
        "minimum_required": minimum_required,
        "coverage_count": len(satisfied),
        "enough_coverage": len(satisfied) >= minimum_required,
        "assessment_progress": {
            "points": [],
            "actions": [],
            "summary": {
                "requirements": [item["label"] for item in requirements],
                "satisfied": satisfied,
                "missing": missing,
                "completed_point_ids": [],
                "completed_action_ids": [],
                "total_weight": len(requirements),
                "earned_weight": len(satisfied),
            },
        },
    }


def _should_allow_stage_completion(
    stage_completed: bool,
    history: list[Any],
    user_message: str,
    current_stage: str,
    current_stage_goal: str,
    stage_turn_count: int,
    trust: int,
    emotion: int,
    new_fact: Any,
    revealed_info: list[str],
    scene: Any,
    *,
    recognized_actions: list[dict[str, Any]] | None = None,
    case_type: str = "",
) -> bool:
    coverage = _evaluate_stage_coverage(
        history,
        user_message,
        revealed_info,
        new_fact,
        current_stage,
        current_stage_goal,
        scene,
        recognized_actions=recognized_actions,
        case_type=case_type,
    )
    stage_config = _get_stage_config(scene, current_stage, case_type=case_type)
    if stage_config and coverage.get("assessment_progress"):
        return evaluate_stage_completion(
            stage_config,
            coverage["assessment_progress"],
            stage_turn_count,
            llm_completed=stage_completed,
        )

    if not stage_completed:
        return False

    required_turns = _stage_turn_target(current_stage)
    has_new_fact = bool(str(new_fact or "").strip()) and str(new_fact).strip().lower() != "null"
    enough_progress = has_new_fact or len(revealed_info) >= 2 or trust >= 72 or coverage["coverage_count"] >= coverage["minimum_required"] + 1
    if stage_turn_count < required_turns:
        return False
    if not coverage["enough_coverage"]:
        return False
    if not enough_progress and emotion < 82:
        return False
    return True


def _build_recommended_questions(
    current_stage_goal: str,
    revealed_info: list[str],
    truth_stage: str,
    *,
    current_stage: str = "",
    case_type: str = "",
    scene_name: str = "",
    role_name: str = "",
    role_type: str = "",
    missing_requirements: list[str] | None = None,
    emotion: int = 50,
    cooperation: int = 50,
) -> list[str]:
    from .recommended_questions_service import build_recommended_questions

    return build_recommended_questions(
        current_stage=current_stage,
        current_stage_goal=current_stage_goal,
        case_type=case_type,
        scene_name=scene_name,
        role_name=role_name,
        role_type=role_type,
        revealed_info=revealed_info,
        missing_requirements=missing_requirements,
        truth_stage=truth_stage,
        emotion=emotion,
        cooperation=cooperation,
    )


def _build_feedback(user_message: str, trust: int, emotion: int, truth_stage: str) -> dict[str, Any]:
    notes: list[str] = []
    tags: list[str] = []

    if len(user_message.strip()) < 12:
        notes.append("这一轮问法偏短，建议补上时间、地点或人物锚点。")
        tags.append("question_too_short")
    if any(token in user_message for token in ["为什么", "怎么回事", "具体", "谁", "几点", "哪里"]):
        notes.append("这一轮问法已经开始逼近关键事实。")
        tags.append("fact_probe")
    if any(token in user_message for token in ["冷静", "别激动", "慢慢说", "不用着急"]):
        notes.append("你在尝试稳住对方情绪，这有助于后续继续深问。")
        tags.append("rapport")
    if truth_stage == "guarded_denial":
        notes.append("当前角色仍偏防御，建议先缩小问题范围，不要一次问太散。")
        tags.append("guarded")
    elif truth_stage == "mostly_open":
        notes.append("对方已经开始松口，适合顺着时间线追细节和矛盾点。")
        tags.append("disclosure")

    if not notes:
        notes.append("问询节奏正常，可以继续围绕已知线索逐步压实。")
        tags.append("steady")

    level = "warning" if emotion >= 75 else "good" if trust >= 65 else "info"
    return {
        "level": level,
        "tags": tags,
        "message": notes[0],
        "all_messages": notes,
    }


def _build_plain_text_result(raw_content: str, ts: Any, current_stage_goal: str, role: Any) -> dict[str, Any]:
    truth_stage = _infer_truth_stage(current_state_snapshot["cooperation"], ts.current_emotion)
    revealed_info = _parse_json_list(ts.revealed_info)
    salvage_message = "模型返回了非 JSON 文本，系统已自动转换为可继续训练的结构化回复。"
    return {
        "response": raw_content[:420].rstrip(),
        "inner_thought": f"先按当前口径回答，暂时不把最在意的部分完全说透。当前真相阶段：{truth_stage}",
        "updated_emotion": ts.current_emotion,
        "updated_trust": ts.current_trust,
        "new_fact_revealed": None,
        "is_stage_completed": False,
        "current_stage": ts.current_stage,
        "current_stage_goal": current_stage_goal,
        "recommended_questions": _build_recommended_questions(current_stage_goal, revealed_info, truth_stage),
        "communication_feedback": {
            "level": "info",
            "tags": ["plain_text_salvaged"],
            "message": salvage_message,
            "all_messages": [salvage_message],
        },
        "persona_hint": _build_persona_hint(role),
        "role_state_label": _role_state_label(
            current_state_snapshot["cooperation"],
            ts.current_emotion,
            current_state_snapshot["risk"],
            current_state_snapshot["clarity"],
        ),
        "truth_stage": truth_stage,
    }


class _TransientMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


def _default_role() -> models.Role:
    return models.Role(
        name="当事人",
        role_type="相关人员",
        interaction_style="配合型",
        personality="普通人，临场状态会受情绪、利益和关系影响。",
        speaking_style="口语化、谨慎",
        iq_level="中等",
        eq_level="中等",
        lying_ability="一般",
        status="正常",
        knows_facts="[]",
        does_not_know="[]",
        hidden_truths="[]",
        weakness="暂无明显弱点",
    )


def _extract_response_text(response: Any) -> str:
    text = extract_message_text(response)
    if text:
        return text
    if isinstance(response, dict):
        try:
            return str(response["choices"][0]["message"]["content"] or "")
        except Exception:
            return ""
    return ""


def _parse_result_payload(raw_content: str, ts: Any, current_stage_goal: str, role: Any) -> dict[str, Any]:
    try:
        start_idx = raw_content.find("{")
        end_idx = raw_content.rfind("}")
        payload = raw_content[start_idx : end_idx + 1] if start_idx != -1 and end_idx != -1 else raw_content
        result = json.loads(payload)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return _build_plain_text_result(raw_content, ts, current_stage_goal, role)


def _is_meaningful_fact(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() != "null"


def _stage_turn_target_for_config(stage_config: dict[str, Any], current_stage: str) -> int:
    completion_rules = stage_config.get("completion_rules") or {}
    min_turns = completion_rules.get("min_user_turns")
    if min_turns is not None:
        try:
            return max(1, int(min_turns))
        except (TypeError, ValueError):
            pass
    return _stage_turn_target(current_stage)


def _build_prompt_history(history: list[Any]) -> list[dict[str, str]]:
    prompt_messages: list[dict[str, str]] = []
    for message in history[-12:]:
        role = str(getattr(message, "role", "") or "")
        content = str(getattr(message, "content", "") or "").strip()
        if not content:
            continue
        if role in {"assistant", "ai"}:
            speaker = str(getattr(message, "speaker_name", "") or "").strip()
            labeled = f"[{speaker}]：{content}" if speaker else content
            prompt_messages.append({"role": "assistant", "content": labeled})
        elif role == "action":
            prompt_messages.append({"role": "user", "content": f"[动作] {content}"})
        elif role == "user":
            prompt_messages.append({"role": "user", "content": content})
    return prompt_messages


def _build_available_actions(stage_config: dict[str, Any], completed_action_ids: list[str]) -> list[dict[str, Any]]:
    completed_set = {str(item).strip() for item in completed_action_ids if str(item).strip()}
    actions: list[dict[str, Any]] = []
    for action in stage_config.get("action_catalog") or []:
        action_id = str(action.get("id") or "").strip()
        if not action_id:
            continue
        actions.append(
            {
                "id": action_id,
                "label": str(action.get("label") or action_id).strip(),
                "type": str(action.get("type") or "physical").strip(),
                "aliases": action.get("aliases") or [],
                "counts_for": action.get("counts_for") or [],
                "completed": action_id in completed_set,
            }
        )
    return actions


def _list_stage_names(scene: Any, case_type: str = "") -> list[str]:
    stages = normalize_stages(
        getattr(scene, "stages", []),
        case_type=case_type,
        scene_name=str(getattr(scene, "name", "") or ""),
    )
    return [
        str(stage.get("stage_name") or "").strip()
        for stage in stages
        if isinstance(stage, dict) and str(stage.get("stage_name") or "").strip()
    ]


def _should_add_follow_up(
    result: dict[str, Any],
    recognized_actions: list[dict[str, Any]],
    momentum: dict[str, Any],
    emotion: int,
) -> tuple[bool, str]:
    if recognized_actions:
        return True, "action"
    if emotion >= 70:
        return True, "emotion"
    if momentum.get("trigger_hits") or momentum.get("pressure_point_hits") or "soft_spot_probe" in (momentum.get("strategy_tags") or []):
        return True, "trigger"
    if _is_meaningful_fact(result.get("follow_up_response")):
        return True, "trigger"
    return False, ""


def _append_unique(items: list[str], value: str) -> list[str]:
    clean = str(value or "").strip()
    if clean and clean not in items:
        items.append(clean)
    return items


def _build_runtime_summary(end_result: dict[str, Any], current_stage: str) -> dict[str, Any]:
    return {
        "current_stage": current_stage,
        "ready": bool(end_result.get("ready")),
        "closure_hit": bool(end_result.get("closure_hit")),
        "missing_point_ids": end_result.get("missing_point_ids") or [],
        "missing_action_ids": end_result.get("missing_action_ids") or [],
        "closing_script": str(end_result.get("closing_script") or "").strip(),
    }


def _normalize_state_snapshot(ts: Any, runtime_state: dict[str, Any], persona_profile: dict[str, Any]) -> dict[str, int]:
    raw_snapshot = runtime_state.get("state_snapshot") if isinstance(runtime_state, dict) else {}
    raw_snapshot = raw_snapshot if isinstance(raw_snapshot, dict) else {}
    return {
        "cooperation": _clamp_score(raw_snapshot.get("cooperation"), persona_profile.get("init_cooperation") or ts.current_trust or 30),
        "risk": _clamp_score(raw_snapshot.get("risk"), persona_profile.get("init_risk") or 50),
        "clarity": _clamp_score(raw_snapshot.get("clarity"), persona_profile.get("init_expression_clarity") or 50),
    }


def _pick_result_score(result: dict[str, Any], fallback: int, *keys: str) -> int:
    for key in keys:
        if key in result and result.get(key) not in (None, ""):
            return _clamp_score(result.get(key), fallback)
    return _clamp_score(fallback, fallback)


def _format_scene_boundary_block(persona_profile: dict[str, Any]) -> str:
    boundary = persona_profile.get("scene_boundary") if isinstance(persona_profile, dict) else {}
    if not isinstance(boundary, dict):
        boundary = {}
    labels = {
        "known_key_points": "֪���Ĺؼ���",
        "withheld_key_points": "����������",
        "conflict_core": "��ͻ����",
        "acceptable_outcomes": "�ɽ��ܵĽ��",
        "no_go_topics": "������Ļ���",
        "trigger_sources": "����Դ",
        "concerned_targets": "�ر����ĵ���",
        "taboo_actions": "�������Ĵ���",
        "escalation_actions": "�������⵼��ʧ�ص���Ϊ",
        "deescalation_conditions": "�пɽ����Ĺ���",
    }
    lines: list[str] = []
    for key, label in labels.items():
        values = [str(item).strip() for item in (boundary.get(key) or []) if str(item).strip()]
        if values:
            lines.append(f"- {label}��{'��'.join(values[:4])}")
    return "\n".join(lines) if lines else "- ��ǰδ���ö�̬��Ϣ�߽磬����ԭʼ��֪/δ֪/�������ݡ�"


def _role_state_label(cooperation: int, emotion: int, risk: int | None = None, clarity: int | None = None) -> str:
    risk = _clamp_score(risk, 50) if risk is not None else 50
    clarity = _clamp_score(clarity, 50) if clarity is not None else 50
    if risk >= 78 or emotion >= 82:
        return "����ʧ�ر�Ե"
    if clarity <= 32 and emotion >= 70:
        return "������������"
    if cooperation >= 68 and risk <= 45:
        return "���ȶ���ͨ"
    if cooperation <= 30 and risk >= 60:
        return "ǿ�������"
    if clarity >= 68 and cooperation >= 55:
        return "��Ϣ���𽥹���"
    return "����Ӧ��"


def _build_feedback(
    user_message: str,
    cooperation: int,
    emotion: int,
    truth_stage: str,
    *,
    risk: int | None = None,
    clarity: int | None = None,
) -> dict[str, Any]:
    notes: list[str] = []
    tags: list[str] = []
    risk = _clamp_score(risk, 50) if risk is not None else 50
    clarity = _clamp_score(clarity, 50) if clarity is not None else 50

    if len(user_message.strip()) < 12:
        notes.append("��һ���ʷ�ƫ�̣����鲹��ʱ�䡢�ص������ê�㡣")
        tags.append("question_too_short")
    if any(token in user_message for token in ["Ϊʲô", "��ô����", "����", "˭", "����", "����"]):
        notes.append("��һ���ʷ��Ѿ���ʼ�ƽ��ؼ���ʵ��")
        tags.append("fact_probe")
    if any(token in user_message for token in ["�侲", "�𼤶�", "����˵", "�����ż�"]):
        notes.append("���ڳ�����ס�Է��������������ں����������ʡ�")
        tags.append("rapport")
    if risk >= 72:
        notes.append("��ǰ��ɫʧ�ط���ƫ�ߣ����ȿ����ȶ�������Χ�ۻ��ڶԿ���")
        tags.append("high_risk")
    if clarity <= 35:
        notes.append("�Է���ǰ�������Ƚϵͣ������ö̾䡢�����Ⱥ�˳������")
        tags.append("low_clarity")
    if truth_stage == "guarded_denial":
        notes.append("��ǰ��ɫ��ƫ��������������С���ⷶΧ����Ҫһ����̫ɢ��")
        tags.append("guarded")
    elif truth_stage == "mostly_open":
        notes.append("�Է��Ѿ���ʼ�ɿڣ��ʺ�˳��ʱ����׷ϸ�ں�ì�ܵ㡣")
        tags.append("disclosure")

    if not notes:
        notes.append("��ѯ�������������Լ���Χ����֪������ѹʵ��")
        tags.append("steady")

    level = "warning" if emotion >= 75 or risk >= 72 else "good" if cooperation >= 65 and clarity >= 50 else "info"
    return {
        "level": level,
        "tags": tags,
        "message": notes[0],
        "all_messages": notes,
    }


def _build_plain_text_result(
    raw_content: str,
    ts: Any,
    current_stage_goal: str,
    role: Any,
    state_snapshot: dict[str, int] | None = None,
) -> dict[str, Any]:
    state_snapshot = state_snapshot or {"cooperation": ts.current_trust, "risk": 50, "clarity": 50}
    truth_stage = _infer_truth_stage(state_snapshot["cooperation"], ts.current_emotion)
    runtime_state = load_runtime_state(ts.revealed_info)
    revealed_info = runtime_state.get("revealed_info") or []
    salvage_message = "ģ�ͷ����˷� JSON �ı���ϵͳ���Զ�ת��Ϊ�ɼ���ѵ���Ľṹ���ظ���"
    return {
        "response": raw_content[:420].rstrip(),
        "inner_thought": f"�Ȱ���ǰ�ھ��ش���ʱ����������Ĳ�����ȫ˵͸����ǰ����׶Σ�{truth_stage}",
        "updated_emotion": ts.current_emotion,
        "updated_cooperation": state_snapshot["cooperation"],
        "updated_risk": state_snapshot["risk"],
        "updated_clarity": state_snapshot["clarity"],
        "updated_trust": state_snapshot["cooperation"],
        "new_fact_revealed": None,
        "is_stage_completed": False,
        "current_stage": ts.current_stage,
        "current_stage_goal": current_stage_goal,
        "recommended_questions": _build_recommended_questions(current_stage_goal, revealed_info, truth_stage),
        "communication_feedback": {
            "level": "info",
            "tags": ["plain_text_salvaged"],
            "message": salvage_message,
            "all_messages": [salvage_message],
        },
        "persona_hint": _build_persona_hint(role),
        "role_state_label": _role_state_label(
            state_snapshot["cooperation"],
            ts.current_emotion,
            state_snapshot["risk"],
            state_snapshot["clarity"],
        ),
        "truth_stage": truth_stage,
    }


def _parse_result_payload(
    raw_content: str,
    ts: Any,
    current_stage_goal: str,
    role: Any,
    state_snapshot: dict[str, int] | None = None,
) -> dict[str, Any]:
    try:
        start_idx = raw_content.find("{")
        end_idx = raw_content.rfind("}")
        payload = raw_content[start_idx : end_idx + 1] if start_idx != -1 and end_idx != -1 else raw_content
        result = json.loads(payload)
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    return _build_plain_text_result(raw_content, ts, current_stage_goal, role, state_snapshot)


def _run_training_turn(
    db: Session,
    session_id: int,
    user_text: str,
    *,
    user_id: int | None = None,
    turn_role: str = "user",
    explicit_actions: list[dict[str, Any]] | None = None,
    target_role_name: str | None = None,
) -> dict[str, Any] | None:
    ts = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not ts:
        return None
    if user_id is not None and ts.user_id != user_id:
        return {
            "response": "当前账号无权访问这条训练会话。",
            "inner_thought": "ACCESS_DENIED",
            "updated_emotion": ts.current_emotion,
            "updated_trust": ts.current_trust,
            "is_stage_completed": False,
            "recommended_questions": [],
            "communication_feedback": {
                "level": "warning",
                "tags": ["access_denied"],
                "message": "当前会话不属于本账号，无法继续训练。",
                "all_messages": ["当前会话不属于本账号，无法继续训练。"],
            },
        }

    scene = db.query(models.Scene).filter(models.Scene.id == ts.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    scene_roles = resolve_scene_roles(db, scene, case) if scene else []
    speakable_scene_roles = [item for item in scene_roles if is_role_speakable(item)]
    role = (
        speakable_scene_roles[0]
        if speakable_scene_roles
        else (resolve_scene_role(db, scene, case) if scene else None)
    )
    if not role:
        role = _default_role()

    history = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )

    case_type = _get_case_type(case)
    current_stage = str(ts.current_stage or "初始接触")
    stage_config = _get_stage_config(scene, current_stage, case_type=case_type)
    runtime_state = load_runtime_state(ts.revealed_info)
    revealed_info = list(runtime_state.get("revealed_info") or [])
    current_stage_goal = _get_stage_goal(scene, current_stage, case_type=case_type)
    stage_turn_count = _count_user_turns(history) + (1 if turn_role == "user" else 0)
    stage_turn_target = _stage_turn_target_for_config(stage_config, current_stage)

    recognized_actions = explicit_actions or detect_actions_from_text(stage_config, user_text)
    structured = json.loads(case.structured_data or "{}") if case and case.structured_data else {}
    fact_sheet = structured.get("fact_sheet", {}) if isinstance(structured, dict) else {}

    prompt_text = user_text if turn_role == "user" else f"警方执行动作：{user_text}"
    persona_profile = build_persona_profile(role, case, scene)
    current_state_snapshot = _normalize_state_snapshot(ts, runtime_state, persona_profile)
    runtime_state["state_snapshot"] = current_state_snapshot
    recent_memory = build_recent_memory(history[-12:])
    momentum = analyze_dialogue_momentum(
        prompt_text,
        persona_profile,
        current_stage_goal,
        ts.current_trust,
        ts.current_emotion,
    )
    momentum = enrich_momentum_with_axis_deltas(momentum, prompt_text, recognized_actions, persona_profile)
    current_axis_scores = {
        "emotion": ts.current_emotion,
        "cooperation": current_state_snapshot["cooperation"],
        "risk": current_state_snapshot["risk"],
        "clarity": current_state_snapshot["clarity"],
    }
    state_contract = build_state_contract(current_axis_scores, momentum, persona_profile)
    runtime_state["state_contract"] = state_contract
    state_contract_block = format_state_contract_block(state_contract)
    truth_state = evaluate_truth_stage(
        persona_profile,
        momentum,
        ts.current_trust,
        ts.current_emotion,
        revealed_info,
    )
    dynamic_adjustment = derive_stage_dynamic_adjustment(
        persona_profile,
        momentum,
        truth_state,
        current_stage,
        stage_turn_count,
    )
    runtime_state["dynamic_adjustment"] = dynamic_adjustment
    knowledge_bundle = load_case_knowledge_bundle(case, role)
    runtime_state["case_knowledge_doc_ids"] = [
        item.get("id") for item in knowledge_bundle.get("documents", []) if item.get("id")
    ]
    role_script = build_role_script(role, case, scene, persona_profile)
    session_memory = summarize_session_memory(history[-12:], revealed_info, current_stage_goal)
    persona_block = format_persona_block(persona_profile, role_script, recent_memory, momentum, dynamic_adjustment)
    memory_block = format_memory_block(session_memory, truth_state)

    multi_turn_payload: dict[str, Any] | None = None
    conversation_roles = speakable_scene_roles or scene_roles
    if (
        turn_role in {"user", "action"}
        and scene
        and should_use_scene_conversation(conversation_roles, scene)
    ):
        multi_turn_payload = generate_multi_role_turn(
            db,
            scene=scene,
            case=case,
            roles=conversation_roles,
            history=history,
            user_text=prompt_text,
            current_stage=current_stage,
            current_stage_goal=current_stage_goal,
            target_role_name=target_role_name,
            runtime_state=runtime_state,
        )

    if multi_turn_payload:
        role = multi_turn_payload.get("primary_role") or role
        persona_profile = build_persona_profile(role, case, scene)
        runtime_state["role_state_snapshots"] = multi_turn_payload.get("role_state_snapshots") or runtime_state.get(
            "role_state_snapshots", {}
        )
        runtime_state["role_state_deltas"] = multi_turn_payload.get("role_state_deltas") or {}
        runtime_state["role_contracts"] = multi_turn_payload.get("role_contracts") or {}
        if multi_turn_payload.get("state_contract"):
            state_contract = multi_turn_payload.get("state_contract")
            runtime_state["state_contract"] = state_contract
        runtime_state["last_active_role_ids"] = multi_turn_payload.get("active_role_ids") or []
        scene_snapshot = multi_turn_payload.get("scene_state_snapshot") or {}
        current_state_snapshot = {
            "cooperation": int(scene_snapshot.get("cooperation", current_state_snapshot["cooperation"])),
            "risk": int(scene_snapshot.get("risk", current_state_snapshot["risk"])),
            "clarity": int(scene_snapshot.get("clarity", current_state_snapshot["clarity"])),
        }
        result = {
            "response": multi_turn_payload.get("response") or "……",
            "follow_up_response": multi_turn_payload.get("follow_up_response"),
            "inner_thought": multi_turn_payload.get("inner_thought") or "保持谨慎，继续观察警方问法。",
            "updated_emotion": multi_turn_payload.get("updated_emotion"),
            "updated_trust": multi_turn_payload.get("updated_trust"),
            "updated_cooperation": multi_turn_payload.get("updated_cooperation"),
            "updated_risk": multi_turn_payload.get("updated_risk"),
            "updated_clarity": multi_turn_payload.get("updated_clarity"),
            "new_fact_revealed": multi_turn_payload.get("new_fact_revealed"),
            "is_stage_completed": multi_turn_payload.get("is_stage_completed"),
        }
        planned_reply_turns = multi_turn_payload.get("reply_turns") or multi_turn_payload.get("reply_sequence") or []
    else:
        planned_reply_turns = []
        result = None

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        role_name=role.name or "相关人员",
        case_time=fact_sheet.get("case_time", "未记录"),
        case_location=fact_sheet.get("case_location", "未记录"),
        report_time=fact_sheet.get("report_time", "未记录"),
        timeline=_build_timeline_text(structured),
        case_knowledge_block=knowledge_bundle.get("knowledge_block") or "暂无案件知识库内容",
        knows_facts=_format_list_block(getattr(role, "knows_facts", [])),
        does_not_know=_format_list_block(getattr(role, "does_not_know", [])),
        hidden_truths=_format_list_block(getattr(role, "hidden_truths", [])),
        role_type=role.role_type or "相关人员",
        behavior_archetype=persona_profile.get("behavior_archetype") or "求助配合型",
        interaction_style=getattr(role, "interaction_style", "") or "配合型",
        status=role.status or "正常",
        personality=role.personality or "普通人",
        speaking_style=getattr(role, "speaking_style", "") or "口语化、谨慎",
        police_attitude=persona_profile.get("police_attitude") or persona_profile.get("authority_attitude") or "暂无明确对警方态度",
        current_goal=persona_profile.get("current_goal") or "暂无明确当前诉求",
        core_concern=persona_profile.get("core_concern") or role.weakness or "暂无明确核心顾虑",
        relationship_pressure="、".join(persona_profile.get("relationship_pressure") or []) or "暂无明显关系压力",
        surface_stance=persona_profile.get("surface_stance") or "暂无明确对外口径",
        pressure_response=persona_profile.get("pressure_response") or "暂无明确承压反应",
        trigger_points="、".join(persona_profile.get("trigger_points") or []) or "暂无明确触发点",
        calming_points="、".join(persona_profile.get("calming_points") or []) or "暂无明确安抚点",
        current_stage=current_stage,
        current_stage_goal=current_stage_goal,
        stage_turn_count=stage_turn_count,
        stage_turn_target=stage_turn_target,
        stage_assessment_points=_format_stage_assessment_points(stage_config),
        stage_action_catalog=_format_stage_action_catalog(stage_config),
        revealed_info="\n".join(f"- {item}" for item in revealed_info) if revealed_info else "[]",
        persona_block=persona_block,
        role_archetype_block=_build_role_archetype_block(role, scene, persona_profile),
        scene_mode_block=_build_scene_mode_block(scene, current_stage, current_stage_goal),
        memory_block=memory_block,
        emotion=ts.current_emotion,
        trust=current_state_snapshot["cooperation"],
        cooperation=current_state_snapshot["cooperation"],
        risk=current_state_snapshot["risk"],
        clarity=current_state_snapshot["clarity"],
        scene_behavior_mode=persona_profile.get("scene_behavior_mode") or "核查取证型",
        scene_boundary_block=_format_scene_boundary_block(persona_profile),
        state_contract_block=state_contract_block,
    )

    if result is None:
        messages = [{"role": "system", "content": system_prompt}, *_build_prompt_history(history)]
        if turn_role == "action":
            messages.append(
                {
                    "role": "user",
                    "content": f"[动作执行] {user_text}\n请根据这次执法动作给出角色的即时反应，可表现为紧张、配合、打断或补充。",
                }
            )
        else:
            messages.append({"role": "user", "content": user_text})

        response = create_json_chat_completion(
            messages=messages,
            temperature=generation_temperature_for_contract(state_contract),
            model=get_chat_model(),
            max_tokens=2200,
        )
        raw_content = _extract_response_text(response) or ""
        result = _parse_result_payload(raw_content, ts, current_stage_goal, role, current_state_snapshot)
        planned_reply_turns = []

    blended_state = blend_four_axis_state(current_axis_scores, result, momentum)
    ts.current_emotion = blended_state["emotion"]
    ts.current_trust = blended_state["cooperation"]
    current_state_snapshot = {
        "cooperation": blended_state["cooperation"],
        "risk": blended_state["risk"],
        "clarity": blended_state["clarity"],
    }
    if not multi_turn_payload and role and getattr(role, "id", None):
        role_key = str(role.id)
        previous_role_snapshot = (runtime_state.get("role_state_snapshots") or {}).get(role_key) or {
            "emotion": current_axis_scores["emotion"],
            "cooperation": current_axis_scores["cooperation"],
            "risk": current_axis_scores["risk"],
            "clarity": current_axis_scores["clarity"],
        }
        next_role_snapshot = {
            "emotion": blended_state["emotion"],
            "cooperation": blended_state["cooperation"],
            "risk": blended_state["risk"],
            "clarity": blended_state["clarity"],
        }
        runtime_state.setdefault("role_state_snapshots", {})[role_key] = next_role_snapshot
        runtime_state["role_state_deltas"] = {
            role_key: {
                axis: int(next_role_snapshot[axis]) - int(previous_role_snapshot.get(axis, next_role_snapshot[axis]))
                for axis in ("emotion", "cooperation", "risk", "clarity")
            }
        }
        runtime_state["last_active_role_ids"] = [int(role.id)]
    runtime_state["state_snapshot"] = current_state_snapshot
    state_contract = build_state_contract(blended_state, momentum, persona_profile)
    runtime_state["state_contract"] = state_contract

    ai_reply = sanitize_spoken_line(str(result.get("response") or "……").strip() or "……")
    if not planned_reply_turns:
        postcheck = apply_contract_postcheck(
            ai_reply,
            state_contract,
            role_name=getattr(role, "name", "") or "",
            user_text=prompt_text,
            use_llm=True,
        )
        ai_reply = postcheck.get("text") or ai_reply
        if postcheck.get("follow_up") and not str(result.get("follow_up_response") or "").strip():
            result["follow_up_response"] = postcheck["follow_up"]
        runtime_state["last_postcheck"] = {
            "adjusted": postcheck.get("adjusted"),
            "validation": postcheck.get("validation"),
        }
    ai_thought = str(result.get("inner_thought") or "保持谨慎，继续观察警方问法。").strip()
    new_fact = cap_new_fact_for_contract(result.get("new_fact_revealed"), state_contract)
    result["new_fact_revealed"] = new_fact
    if _is_meaningful_fact(new_fact):
        _append_unique(revealed_info, str(new_fact).strip())

    transient_history = [*history, _TransientMessage(turn_role, user_text)]
    stage_coverage = _evaluate_stage_coverage(
        transient_history,
        user_text,
        revealed_info,
        new_fact,
        current_stage,
        current_stage_goal,
        scene,
        recognized_actions=recognized_actions,
        case_type=case_type,
    )
    stage_completed = _should_allow_stage_completion(
        bool(result.get("is_stage_completed", False)),
        transient_history,
        user_text,
        current_stage,
        current_stage_goal,
        stage_turn_count,
        ts.current_trust,
        ts.current_emotion,
        new_fact,
        revealed_info,
        scene,
        recognized_actions=recognized_actions,
        case_type=case_type,
    )

    stage_names = _list_stage_names(scene, case_type=case_type)
    is_last_stage = not stage_names or current_stage == stage_names[-1]
    end_result = evaluate_end_conditions(
        stage_config,
        stage_coverage.get("assessment_progress") or {},
        stage_completed,
        is_last_stage,
        message_text=user_text,
        recognized_actions=recognized_actions,
    )
    auto_finished = bool(end_result.get("ready"))

    if planned_reply_turns:
        normalized_turns = [
            {
                "speaker_name": item.get("speaker_name") or getattr(role, "name", ""),
                "speaker_role_id": item.get("speaker_role_id") or getattr(role, "id", None),
                "content": item.get("content") or "",
                "inner_thought": item.get("inner_thought"),
            }
            for item in planned_reply_turns
            if isinstance(item, dict) and str(item.get("content") or "").strip()
        ]
        normalized_turns = postcheck_reply_turns(
            normalized_turns,
            runtime_state.get("role_contracts") or {},
            fallback_contract=state_contract,
            user_text=prompt_text,
            use_llm=True,
        )
        reply_turns = normalized_turns
        reply_sequence = [item["content"] for item in reply_turns]
    else:
        reply_turns = []
        reply_sequence = [ai_reply]
        if auto_finished:
            closure_message = build_closure_message(stage_config, current_stage, getattr(role, "name", ""), ts.current_emotion)
            if closure_message and closure_message != ai_reply:
                reply_sequence.append(closure_message)
        else:
            should_follow_up, follow_up_reason = _should_add_follow_up(result, recognized_actions, momentum, ts.current_emotion)
            if should_follow_up:
                follow_up_text = str(result.get("follow_up_response") or "").strip()
                if not follow_up_text:
                    follow_up_text = build_follow_up_reply(getattr(role, "name", ""), ts.current_emotion, follow_up_reason, recognized_actions)
                if follow_up_text and follow_up_text != ai_reply:
                    reply_sequence.append(follow_up_text)
        reply_turns = [
            {
                "speaker_name": getattr(role, "name", "") or "相关人员",
                "speaker_role_id": getattr(role, "id", None),
                "content": content,
                "inner_thought": ai_thought if index == 0 else None,
            }
            for index, content in enumerate(reply_sequence)
        ]

    stage_transition_message = None
    active_stage_goal = current_stage_goal
    if stage_completed and not auto_finished:
        previous_stage = current_stage
        stage_state = _advance_stage(scene, current_stage, case_type=case_type)
        ts.current_stage = stage_state["current_stage"]
        active_stage_goal = stage_state["current_stage_goal"]
        if previous_stage != ts.current_stage:
            stage_transition_message = f"【阶段切换】已由“{previous_stage or '上一阶段'}”进入“{ts.current_stage}”阶段。"
    else:
        ts.current_stage = current_stage
        active_stage_goal = _get_stage_goal(scene, current_stage, case_type=case_type)

    runtime_state["revealed_info"] = revealed_info
    runtime_state["assessment_progress"] = stage_coverage.get("assessment_progress") or runtime_state.get("assessment_progress") or {}
    runtime_state["completed_point_ids"] = runtime_state["assessment_progress"].get("summary", {}).get("completed_point_ids", []) or []
    runtime_state["completed_action_ids"] = runtime_state["assessment_progress"].get("summary", {}).get("completed_action_ids", []) or []
    runtime_state["auto_finish_ready"] = auto_finished
    runtime_state["closure_summary"] = _build_runtime_summary(end_result, current_stage)
    runtime_state["state_snapshot"] = current_state_snapshot
    if planned_reply_turns and not runtime_state.get("last_postcheck"):
        runtime_state["last_postcheck"] = {
            "adjusted": False,
            "validation": validate_response_against_contract(ai_reply, state_contract or {}),
        }
    record_turn_metrics(
        runtime_state,
        contract=state_contract,
        ai_reply=ai_reply,
        postcheck=runtime_state.get("last_postcheck") if isinstance(runtime_state.get("last_postcheck"), dict) else None,
        stage_missing=stage_coverage.get("missing"),
        stage_satisfied=stage_coverage.get("satisfied"),
    )
    ts.revealed_info = dump_runtime_state(runtime_state)

    active_stage_config = _get_stage_config(scene, ts.current_stage or current_stage, case_type=case_type)
    active_coverage = stage_coverage
    if (ts.current_stage or current_stage) != current_stage and not auto_finished:
        active_coverage = _evaluate_stage_coverage(
            transient_history,
            "",
            revealed_info,
            None,
            ts.current_stage or current_stage,
            active_stage_goal,
            scene,
            recognized_actions=[],
            case_type=case_type,
        )

    truth_stage = _infer_truth_stage(current_state_snapshot["cooperation"], ts.current_emotion)
    from .recommended_questions_service import (
        apply_stage_hit_rate_correction,
        build_recommended_question_items,
        filter_stale_missing_requirements_for_history,
        serialize_message_history,
    )

    recent_messages = serialize_message_history(history[-10:])
    custom_prompts = list(active_stage_config.get("recommended_prompts") or []) if active_stage_config else []
    scene_kind = infer_session_scene_kind(scene, ts)
    effective_missing_requirements = filter_stale_missing_requirements_for_history(
        active_coverage.get("missing") or [],
        recent_messages=recent_messages,
        revealed_info=revealed_info,
        last_user_message=user_text if turn_role == "user" else "",
        use_intake_flow=scene_kind == "intake",
    )
    recommended_question_items = build_recommended_question_items(
        current_stage=ts.current_stage or current_stage,
        current_stage_goal=active_stage_goal,
        case_type=case_type,
        case_title=getattr(case, "title", "") or "",
        scene_name=getattr(scene, "name", "") or "",
        scene_kind=scene_kind,
        role_name=getattr(role, "name", "") or "",
        role_type=getattr(role, "role_type", "") or "",
        target_role_name=target_role_name or "",
        scene_roles=[
            {"name": item.name, "speakable": True, "role_type": item.role_type}
            for item in scene_roles
        ],
        revealed_info=revealed_info,
        missing_requirements=effective_missing_requirements,
        truth_stage=truth_stage,
        emotion=ts.current_emotion,
        cooperation=current_state_snapshot["cooperation"],
        persona_profile=persona_profile,
        momentum=momentum,
        last_user_message=user_text if turn_role == "user" else "",
        recent_messages=recent_messages,
        custom_prompts=custom_prompts,
        use_llm=True,
    )
    recommended_question_items = apply_stage_hit_rate_correction(
        recommended_question_items,
        satisfied=active_coverage.get("satisfied") or [],
        missing=effective_missing_requirements,
        addressee=getattr(role, "name", "") or target_role_name or "",
    )
    recommended_questions = [item["text"] for item in recommended_question_items]

    communication_feedback = _build_feedback(
        prompt_text,
        current_state_snapshot["cooperation"],
        ts.current_emotion,
        truth_stage,
        risk=current_state_snapshot["risk"],
        clarity=current_state_snapshot["clarity"],
    )
    if not auto_finished and effective_missing_requirements:
        coverage_msg = f"当前阶段仍缺少：{'、'.join(effective_missing_requirements[:3])}。"
        communication_feedback["message"] = coverage_msg
        communication_feedback["all_messages"] = [coverage_msg, *communication_feedback.get("all_messages", [])]
        communication_feedback["tags"] = ["stage_gap", *communication_feedback.get("tags", [])]
    if momentum.get("notes"):
        communication_feedback["all_messages"] = list(dict.fromkeys([*momentum["notes"], *communication_feedback.get("all_messages", [])]))
        if not auto_finished:
            communication_feedback["message"] = momentum["notes"][0]
    communication_feedback["tags"] = list(dict.fromkeys([*(momentum.get("strategy_tags") or []), *communication_feedback.get("tags", [])]))
    if auto_finished:
        communication_feedback["level"] = "good"
        communication_feedback["message"] = "训练满足收尾条件，系统将自动结束并进入评估。"
        communication_feedback["all_messages"] = ["训练满足收尾条件，系统将自动结束并进入评估。"]

    if infer_session_scene_kind(scene, ts) == "intake" and turn_role == "user":
        sequence_feedback = build_intake_sequence_feedback(history, user_text, revealed_info)
        communication_feedback = merge_sequence_feedback(communication_feedback, sequence_feedback)

    persisted_input = user_text.strip()
    if persisted_input:
        db.add(models.Message(session_id=session_id, role=turn_role, content=persisted_input))
    for index, turn in enumerate(reply_turns):
        db.add(
            models.Message(
                session_id=session_id,
                role="assistant",
                content=turn.get("content") or "",
                speaker_role_id=turn.get("speaker_role_id"),
                speaker_name=turn.get("speaker_name"),
                inner_thought=turn.get("inner_thought") if index == 0 else None,
            )
        )
    db.commit()

    active_speakers = [
        {
            "id": turn.get("speaker_role_id"),
            "name": turn.get("speaker_name"),
        }
        for turn in reply_turns
        if turn.get("speaker_name")
    ]

    return {
        "response": reply_sequence[0] if reply_sequence else ai_reply,
        "reply_sequence": reply_sequence,
        "reply_turns": reply_turns,
        "active_speakers": active_speakers,
        "scene_roles": serialize_scene_roles(
            db,
            scene,
            case,
            runtime_state=runtime_state,
            target_role_name=target_role_name or "",
            active_role_ids=runtime_state.get("last_active_role_ids") or [],
        ),
        "interaction_mode": multi_turn_payload.get("interaction_mode") if multi_turn_payload else None,
        "scene_mood": multi_turn_payload.get("scene_mood") if multi_turn_payload else None,
        "scene_mood_shift": multi_turn_payload.get("scene_mood_shift") if multi_turn_payload else None,
        "routing_summary": multi_turn_payload.get("routing_summary") if multi_turn_payload else None,
        "addressing_warning": multi_turn_payload.get("addressing_warning") if multi_turn_payload else None,
        "recognized_actions": recognized_actions,
        "available_actions": _build_available_actions(active_stage_config, runtime_state["completed_action_ids"]),
        "assessment_progress": runtime_state["assessment_progress"],
        "completed_point_ids": runtime_state["completed_point_ids"],
        "completed_action_ids": runtime_state["completed_action_ids"],
        "auto_finish_ready": runtime_state["auto_finish_ready"],
        "auto_finished": auto_finished,
        "redirect_to_evaluation": auto_finished,
        "closure_summary": runtime_state["closure_summary"],
        "inner_thought": ai_thought,
        "updated_emotion": ts.current_emotion,
        "updated_trust": ts.current_trust,
        "updated_cooperation": current_state_snapshot["cooperation"],
        "updated_risk": current_state_snapshot["risk"],
        "updated_clarity": current_state_snapshot["clarity"],
        "new_fact_revealed": new_fact if _is_meaningful_fact(new_fact) else None,
        "is_stage_completed": stage_completed,
        "current_stage": ts.current_stage,
        "current_stage_goal": active_stage_goal,
        "stage_transition_message": stage_transition_message,
        "stage_completion_requirements": active_coverage["requirements"],
        "stage_completion_satisfied": active_coverage["satisfied"],
        "stage_completion_missing": active_coverage["missing"],
        "recommended_questions": recommended_questions,
        "recommended_question_items": recommended_question_items,
        "communication_feedback": communication_feedback,
        "persona_hint": "；".join((persona_profile.get("core_motives") or persona_profile.get("soft_spots") or [])[:2]) or _build_persona_hint(role),
        "role_state_label": _role_state_label(
            current_state_snapshot["cooperation"],
            ts.current_emotion,
            current_state_snapshot["risk"],
            current_state_snapshot["clarity"],
        ),
        "truth_stage": truth_stage,
        "state_contract": state_contract,
        "state_influence_metrics": build_session_metrics(runtime_state),
        "last_postcheck": runtime_state.get("last_postcheck"),
    }


def generate_dialogue(
    db: Session,
    session_id: int,
    user_message: str,
    user_id: int | None = None,
    target_role_name: str | None = None,
):
    try:
        return _run_training_turn(
            db,
            session_id,
            user_message.strip(),
            user_id=user_id,
            turn_role="user",
            target_role_name=target_role_name,
        )
    except Exception as error:
        if db:
            db.rollback()
        print(f"!!! DIALOGUE ERROR: {error}")
        return {
            "response": f"(由于系统异常，对话暂时无法继续。错误详情：{error})",
            "inner_thought": "ERROR",
            "recommended_questions": [],
            "communication_feedback": {
                "level": "warning",
                "tags": ["system_error"],
                "message": "当前系统响应异常，请稍后重试。",
                "all_messages": ["当前系统响应异常，请稍后重试。"],
            },
        }


def apply_training_action(
    db: Session,
    session_id: int,
    action_id: str,
    note: str = "",
    user_id: int | None = None,
):
    try:
        ts = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
        if not ts:
            return None
        scene = db.query(models.Scene).filter(models.Scene.id == ts.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
        stage_config = _get_stage_config(scene, ts.current_stage or "", case_type=_get_case_type(case))
        matched_action = next(
            (
                action
                for action in (stage_config.get("action_catalog") or [])
                if str(action.get("id") or "").strip() == str(action_id or "").strip()
            ),
            None,
        )
        if not matched_action:
            return {
                "response": "当前阶段没有这个可执行动作。",
                "inner_thought": "INVALID_ACTION",
                "communication_feedback": {
                    "level": "warning",
                    "tags": ["invalid_action"],
                    "message": "该动作与当前训练阶段不匹配，请重新选择。",
                    "all_messages": ["该动作与当前训练阶段不匹配，请重新选择。"],
                },
            }

        action_label = str(matched_action.get("label") or action_id).strip()
        note_text = str(note or "").strip()
        action_text = action_label if not note_text else f"{action_label}，备注：{note_text}"
        explicit_action = {
            "action_id": str(matched_action.get("id") or "").strip(),
            "label": action_label,
            "type": str(matched_action.get("type") or "physical").strip(),
            "source": "card",
            "note": note_text or action_label,
        }
        return _run_training_turn(
            db,
            session_id,
            action_text,
            user_id=user_id,
            turn_role="action",
            explicit_actions=[explicit_action],
        )
    except Exception as error:
        if db:
            db.rollback()
        print(f"!!! ACTION ERROR: {error}")
        return {
            "response": f"(动作执行失败：{error})",
            "inner_thought": "ERROR",
            "recommended_questions": [],
            "communication_feedback": {
                "level": "warning",
                "tags": ["system_error"],
                "message": "当前动作处理异常，请稍后重试。",
                "all_messages": ["当前动作处理异常，请稍后重试。"],
            },
        }
