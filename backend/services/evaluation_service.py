import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

import models
from .llm_provider import create_json_chat_completion, extract_json_payload, extract_message_text, get_chat_model
from .multimodal_service import append_scene_performance_report
from .persona_engine import build_persona_profile
from .rag_service import rag_service
from .role_resolver import resolve_scene_role
from .stage_config_service import normalize_stages
from .training_runtime_service import collect_stage_progress, load_runtime_state

SCORING_VERSION = "adaptive_v1"

COMMUNICATION_DIMENSION = "沟通表达与执法语言"
INQUIRY_DIMENSION = "主动询问与逻辑推进"
SUMMARY_DIMENSION = "关键信息整理能力"
CLOSURE_DIMENSION = "处置闭环意识"

COMMON_DIMENSIONS = [
    (COMMUNICATION_DIMENSION, "礼貌克制、身份立场清晰，避免压迫、诱导或激化。"),
    (INQUIRY_DIMENSION, "主动提问、追问连贯，信息流由学员推动。"),
    (SUMMARY_DIMENSION, "归纳时间、地点、人物、经过、诉求、矛盾点等已获信息。"),
    (CLOSURE_DIMENSION, "阶段总结、下一步安排、确认反馈，避免草率结束。"),
]

DIMENSIONS = [(name, 25) for name, _ in COMMON_DIMENSIONS]

GRADE_LEVELS: List[Tuple[int, str]] = [
    (90, "卓越"),
    (80, "优秀"),
    (70, "良好"),
    (60, "合格"),
    (0, "需改进"),
]

COMMON_DIMENSION_FOCUS = {name: focus for name, focus in COMMON_DIMENSIONS}

POINT_DIFFICULTY_FACTORS = {
    "低": 0.75,
    "简单": 0.75,
    "中": 1.0,
    "中等": 1.0,
    "普通": 1.0,
    "高": 1.25,
    "困难": 1.25,
}

RED_FLAG_RULES = {
    "coercive_language": {
        "cap": 59,
        "label": "明显威胁/侮辱/诱供",
        "keywords": ["闭嘴", "老实点", "快说", "少废话", "废话", "给我老实交代", "别装了", "不说就", "收拾你", "铐起来"],
    },
    "ignored_emergency_risk": {
        "cap": 59,
        "label": "忽视紧急人身风险",
        "keywords": ["流血", "昏迷", "刀", "持刀", "火", "煤气", "跳楼", "自杀", "爆炸", "重伤"],
    },
    "rights_violation": {
        "cap": 69,
        "label": "明显错误法律处置或侵犯权利",
        "keywords": ["不用手续", "随便搜", "直接关起来", "必须认罪", "不让你联系", "不许请律师", "我说了算"],
    },
}

_STATUS_RANK = {"hit": 3, "partial": 2, "missed": 1}

SCENE_RUBRICS = {
    "接警": [
        "优先确认地点、身份、伤情、风险和是否仍在持续。",
        "接警阶段要体现快速定位关键事实的能力，而不是泛泛安抚。",
        "如果未核实时间、地点、伤情或现场风险，应在通用能力和对应考察点中体现不足。",
    ],
    "现场": [
        "要体现身份核实、现场保护、风险控制和基础证据意识。",
        "如果只聊天不处置，或忽略现场动作，应在通用闭环意识和对应考察点中体现不足。",
        "若能兼顾情绪稳定、现场控制和事实摸排，可明显加分。",
    ],
    "审讯": [
        "要围绕时间线、矛盾点、动机和证据线索逐步推进。",
        "不能只提宽泛问题，必须体现连续追问和压实能力。",
        "若存在诱供、威胁或激化冲突，应在语言规范性和情绪控制上重扣。",
    ],
    "通用": [
        "评分必须紧扣场景目标和训练推进质量。",
        "必须结合学员具体轮次的发言与动作，不得泛泛而谈。",
    ],
}

EVALUATION_PROMPT_TEMPLATE = """
你是一名严格、公正、专业的警务训练评估官，需要根据完整对话、动作执行和“考察点要求表”逐条核查结果给出结构化评估。

本系统使用 adaptive_v1 评分制度：总分由后端按“通用能力 + 动态考察点”确定性计算。你不要输出旧版固定维度评分。

通用能力只评价以下 4 项：
1. 沟通表达与执法语言：礼貌克制、身份立场清晰，避免压迫、诱导或激化。
2. 主动询问与逻辑推进：主动提问、追问连贯，信息流由学员推动。
3. 关键信息整理能力：归纳时间、地点、人物、经过、诉求、矛盾点等已获信息。
4. 处置闭环意识：阶段总结、下一步安排、确认反馈，避免草率结束。

场景专属能力全部通过考察点评价。例如接警场景不强制评价“证据固定”，除非考察点中明确配置了相关要求。

场景信息（评估时应关注学员是否识别了人物的身份、诉求、顾虑和情绪触发点）：
{scene_info}

专项评分标准：
{scene_rubric}

规则校验结果：
{rule_check_summary}

案件信息：
{case_info}

完整对话历史：
{dialogue_history}

考察点要求表（你必须逐条核查“是否满足”，并在输出中给出 evidence 引用）：
{assessment_requirements}

参考知识：
{knowledge_base}

动态权重规则（由后端计算，你只需按事实评价）：
- 通用能力固定 4 个评分单位。
- 每个考察点按难度和 required 属性形成动态评分单位。
- 学员有效发言轮次、必考点命中率和严重红线会触发总分上限。

动作执行评估：
- 训练日志中的"动作"行（以"动作："开头）代表学员完成的现场操作（如开启执法记录仪、拍照取证、分离双方等）。
- 动作只在相关考察点或通用闭环意识中作为证据引用，不作为旧固定维度评分。

参考知识引用要求：
- 评分时必须尽量引用"参考知识"中的条款作为法律依据，并在 reason 中明示（如"根据参考知识第X条…"）。
- 如果知识库中的内容与学员的行为直接相关，必须在 assessment_check_results 的 evidence 或 reason 中引用。

学员主动性判断（不要被 AI 角色牵着走）：
- 区分"学员主动追问获知的信息"和"AI 角色主动告知的信息"。如果信息是 AI 角色主动交代而非学员问出的，不应作为学员的信息获取加分。
- 学员的每个追问轮次应带来新增信息；如果多轮反复询问同一件事而无新进展，应在“主动询问与逻辑推进”中体现不足。
- 判断依据：观察对话中谁在主导信息流动——学员提问→AI角色回答→学员追问问细节，这是主动；AI角色长篇陈述→学员仅应答，这是被动。

输出要求：
1. common_reviews 必须覆盖 4 个通用能力，每项包含 dimension、level、reason、evidence。level 只能为 excellent/good/fair/weak。
2. assessment_check_results 必须与“考察点要求表”逐条对应，不得遗漏 id。status 只能为 hit/partial/missed。
3. evidence 必须引用具体学员发言、动作日志或“学员提问后紧邻 AI 回答”；不得把 AI 主动长篇交代直接算作学员主动得分。
4. strengths 是学员表现亮点（2-4 条），improvements 是具体不足（2-4 条），suggestions 给出下一轮训练建议。
5. 只输出合法 JSON。

严格输出 JSON：
{{
  "common_reviews": [
    {{"dimension": "沟通表达与执法语言", "level": "good", "reason": "学员语气总体克制。", "evidence": ["学员: 请您先说明情况"]}},
    {{"dimension": "主动询问与逻辑推进", "level": "fair", "reason": "追问不足。", "evidence": []}},
    {{"dimension": "关键信息整理能力", "level": "fair", "reason": "未形成完整事实归纳。", "evidence": []}},
    {{"dimension": "处置闭环意识", "level": "weak", "reason": "未说明下一步处置。", "evidence": []}}
  ],
  "assessment_check_results": [
    {{"id": "ap_001", "label": "核实报警人身份", "content": "学员应主动询问报警人姓名、身份及与事件的关系", "status": "hit", "evidence": ["学员: 请问您怎么称呼？"], "reason": "学员主动核实身份。"}}
  ],
  "strengths": ["表达较克制"],
  "improvements": ["需要补齐关键事实追问"],
  "suggestions": "建议按通用能力和本场景考察点逐项复训。"
}}
"""


def _dedupe_strings(values: List[Any]) -> List[str]:
    seen = set()
    items: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _normalize_assessment_identity_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"[\s，。！？、；：“”‘’（）()《》【】\[\]{}<>.,!?;:'\"`~@#$%^&*\-_=+|\\/]+", "", text)


def _assessment_core_content(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"（.*?）|\(.*?\)", "", text)
    text = re.split(r"怎样算完成|具体要求|回放时|回放训练", text, maxsplit=1)[0]
    return text


def _assessment_semantic_key(point: dict) -> str:
    label = _normalize_assessment_identity_text(point.get("label"))
    content = _normalize_assessment_identity_text(_assessment_core_content(point.get("content") or point.get("requirement") or point.get("description")))
    if label and content:
        return f"{label}__{content}"
    return label or content


def _assessment_identity_keys(point: dict) -> List[str]:
    keys: List[str] = []
    point_id = str(point.get("id") or "").strip()
    semantic_key = _assessment_semantic_key(point)
    if point_id:
        keys.append(f"id:{point_id}")
    if semantic_key:
        keys.append(f"semantic:{semantic_key}")
    return keys


def _assessment_points_equivalent(left: dict, right: dict) -> bool:
    left_id = str(left.get("id") or "").strip()
    right_id = str(right.get("id") or "").strip()
    if left_id and right_id and left_id == right_id:
        return True

    left_label = _normalize_assessment_identity_text(left.get("label"))
    right_label = _normalize_assessment_identity_text(right.get("label"))
    if not left_label or left_label != right_label:
        return False

    left_content = _normalize_assessment_identity_text(_assessment_core_content(left.get("content") or left.get("requirement") or left.get("description")))
    right_content = _normalize_assessment_identity_text(_assessment_core_content(right.get("content") or right.get("requirement") or right.get("description")))
    if not left_content or not right_content:
        return True
    if left_content in right_content or right_content in left_content:
        return True
    return SequenceMatcher(None, left_content, right_content).ratio() >= 0.72


def _assessment_point_quality(point: dict) -> int:
    score = 0
    if str(point.get("content") or point.get("requirement") or point.get("description") or "").strip():
        score += 4
    if point.get("keywords"):
        score += 2
    if str(point.get("id") or "").strip():
        score += 1
    if point.get("weight") is not None:
        score += 1
    if point.get("required") is not None:
        score += 1
    if point.get("knowledge_refs"):
        score += 1
    return score


def _best_point_status(*statuses: Any) -> str:
    rank = {"miss": 1, "missed": 1, "partial": 2, "hit": 3}
    best = "missed"
    for status in statuses:
        value = str(status or "").strip()
        if rank.get(value, 0) > rank.get(best, 0):
            best = "missed" if value == "miss" else value
    return best


def _merge_duplicate_assessment_points(current: dict, incoming: dict) -> dict:
    preferred, other = (incoming, current) if _assessment_point_quality(incoming) > _assessment_point_quality(current) else (current, incoming)
    merged = {**other, **preferred}
    merged["id"] = str(preferred.get("id") or other.get("id") or "").strip()
    merged["label"] = str(preferred.get("label") or other.get("label") or "未命名考察点").strip()
    merged["content"] = str(preferred.get("content") or other.get("content") or "").strip()
    merged["stage_name"] = str(preferred.get("stage_name") or other.get("stage_name") or "").strip()
    merged["category"] = str(preferred.get("category") or other.get("category") or "procedure").strip() or "procedure"
    merged["required"] = bool(preferred.get("required", other.get("required", True)))
    merged["weight"] = max(1, int(preferred.get("weight") or other.get("weight") or 10))
    merged["status"] = _best_point_status(current.get("status"), incoming.get("status"))
    merged["score"] = _score_from_point_status(merged["status"], merged["weight"])
    merged["evidence"] = _dedupe_strings((current.get("evidence") or []) + (incoming.get("evidence") or []))[:3]
    merged["feedback"] = "；".join(_dedupe_strings([current.get("feedback"), incoming.get("feedback")]))
    merged["knowledge_refs"] = _dedupe_strings((current.get("knowledge_refs") or []) + (incoming.get("knowledge_refs") or []))
    return merged


def dedupe_assessment_result_points(points: List[dict]) -> List[dict]:
    deduped: List[dict] = []
    key_to_index: Dict[str, int] = {}
    for point in points or []:
        if not isinstance(point, dict):
            continue
        keys = _assessment_identity_keys(point)
        if not keys:
            continue
        matched_index = next((key_to_index[key] for key in keys if key in key_to_index), None)
        if matched_index is None:
            for index, existing in enumerate(deduped):
                if _assessment_points_equivalent(existing, point):
                    matched_index = index
                    break
        if matched_index is None:
            key_to_index.update({key: len(deduped) for key in keys})
            deduped.append(dict(point))
            continue
        deduped[matched_index] = _merge_duplicate_assessment_points(deduped[matched_index], point)
        for key in _assessment_identity_keys(deduped[matched_index]):
            key_to_index[key] = matched_index
    return deduped


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


def infer_scene_type(scene: models.Scene) -> str:
    scene_name = str(scene.name or "")
    if "接警" in scene_name:
        return "接警"
    if any(keyword in scene_name for keyword in ("审讯", "讯问", "嫌疑人")):
        return "审讯"
    if any(keyword in scene_name for keyword in ("现场", "勘查", "调查", "询问")):
        return "现场"
    return "通用"


def format_dialogue(msgs: List[models.Message]) -> Tuple[str, List[str]]:
    history_lines = []
    student_lines = []
    for msg in msgs:
        role = str(msg.role or "")
        if role == "user":
            speaker = "学员"
        elif role == "action":
            speaker = "动作"
        elif role == "system":
            speaker = "系统"
        else:
            speaker = "AI角色"
        content = (msg.content or "").strip()
        history_lines.append(f"{speaker}: {content}")
        if role == "user":
            student_lines.append(content)
    return "\n".join(history_lines), student_lines


def _build_scene_info(scene: models.Scene | None, scene_type: str, role: Any, case: models.Case | None = None) -> str:
    lines = [
        f"场景名称：{scene.name if scene else '未知'}",
        f"场景类型：{scene_type}",
        f"主对话对象：{getattr(role, 'name', '未知')}",
    ]
    if not role:
        return "\n".join(lines)

    persona_profile = build_persona_profile(role, case, scene)
    lines.extend(
        [
            f"角色身份：{getattr(role, 'role_type', '') or '相关人员'}",
            f"行为原型：{persona_profile.get('behavior_archetype') or '求助配合型'}",
            f"对警方基本态度：{persona_profile.get('police_attitude') or persona_profile.get('authority_attitude') or '暂无'}",
            f"当前诉求：{persona_profile.get('current_goal') or persona_profile.get('current_need') or '暂无'}",
            f"核心顾虑：{persona_profile.get('core_concern') or getattr(role, 'weakness', '') or '暂无'}",
            f"关系压力：{'、'.join(persona_profile.get('relationship_pressure') or []) or '暂无'}",
            f"情绪触发点：{'、'.join(persona_profile.get('trigger_points') or []) or '暂无'}",
            f"可安抚点：{'、'.join(persona_profile.get('calming_points') or []) or '暂无'}",
        ]
    )
    return "\n".join(lines)


def contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def build_rule_checks(scene: models.Scene, student_lines: List[str], role: Any) -> Dict[str, Any]:
    scene_type = infer_scene_type(scene)
    joined = "\n".join(student_lines)
    findings: List[Dict[str, Any]] = []
    deductions = {
        COMMUNICATION_DIMENSION: 0,
        INQUIRY_DIMENSION: 0,
        SUMMARY_DIMENSION: 0,
        CLOSURE_DIMENSION: 0,
    }

    if len(student_lines) < 2:
        findings.append(
            {
                "level": "major",
                "dimension": INQUIRY_DIMENSION,
                "message": "学员有效发言轮次过少，难以完成完整处置与信息收集。",
            }
        )
        deductions[INQUIRY_DIMENSION] += 4
        deductions[CLOSURE_DIMENSION] += 3

    bad_phrases = ["闭嘴", "老实点", "快说", "少废话", "废话", "给我老实交代", "别装了"]
    if contains_any(joined, bad_phrases):
        findings.append(
            {
                "level": "major",
                "dimension": COMMUNICATION_DIMENSION,
                "message": "出现疑似不规范、带压迫性或激化冲突的表达。",
            }
        )
        deductions[COMMUNICATION_DIMENSION] += 8

    if scene_type == "接警":
        if not contains_any(joined, ["哪里", "地址", "地点", "具体位置", "几号楼", "房间", "案发地点"]):
            findings.append(
                {
                    "level": "major",
                    "dimension": SUMMARY_DIMENSION,
                    "message": "接警阶段未明确确认案发地点。",
                }
            )
            deductions[SUMMARY_DIMENSION] += 4
            deductions[INQUIRY_DIMENSION] += 2
        if not contains_any(joined, ["什么时候", "几点", "刚刚", "时间"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": SUMMARY_DIMENSION,
                    "message": "接警阶段未及时确认事件发生时间。",
                }
            )
            deductions[SUMMARY_DIMENSION] += 2
        if not contains_any(joined, ["受伤", "危险", "还在现场", "120", "是否安全"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": INQUIRY_DIMENSION,
                    "message": "接警阶段未充分确认现场风险和救助需求。",
                }
            )
            deductions[INQUIRY_DIMENSION] += 2

    if scene_type == "现场":
        if not contains_any(joined, ["姓名", "你是谁", "和对方什么关系", "身份", "叫什么"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": SUMMARY_DIMENSION,
                    "message": "现场问询阶段未充分核实身份和人物关系。",
                }
            )
            deductions[SUMMARY_DIMENSION] += 2
        if not contains_any(joined, ["现场", "不要破坏", "保持原状", "先别动", "证据"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": CLOSURE_DIMENSION,
                    "message": "现场处置中未体现明显的现场保护或证据意识。",
                }
            )
            deductions[CLOSURE_DIMENSION] += 2

    if scene_type == "审讯":
        if not contains_any(joined, ["什么时候", "几点", "当时", "时间线", "案发时"]):
            findings.append(
                {
                    "level": "major",
                    "dimension": INQUIRY_DIMENSION,
                    "message": "审讯或讯问中未围绕案发时间线有效展开。",
                }
            )
            deductions[INQUIRY_DIMENSION] += 4
        if not contains_any(joined, ["为什么", "动机", "关系", "证据", "监控", "不在场"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": INQUIRY_DIMENSION,
                    "message": "审讯中对动机、证据或矛盾点追问不足。",
                }
            )
            deductions[INQUIRY_DIMENSION] += 3

    if role and not getattr(role, "name", ""):
        findings.append(
            {
                "level": "minor",
                "dimension": CLOSURE_DIMENSION,
                "message": "当前场景主对话角色信息异常，评估可能受限。",
            }
        )

    return {
        "scene_type": scene_type,
        "findings": findings,
        "deductions": deductions,
    }


def build_stage_gap_summary(scene: models.Scene | None, student_lines: List[str]) -> Dict[str, Any]:
    scene_type = infer_scene_type(scene) if scene else "通用"
    joined = "\n".join(student_lines)

    requirements_map = {
        "接警": [
            ("身份/关系", ["姓名", "身份", "你是谁", "叫什么", "和谁什么关系", "关系"]),
            ("地点", ["哪里", "地址", "地点", "具体位置", "几号楼", "房间", "案发地点"]),
            ("时间", ["什么时候", "几点", "时间", "刚刚", "何时"]),
            ("风险/伤情", ["受伤", "危险", "120", "是否安全", "还在现场", "风险"]),
        ],
        "现场": [
            ("身份/关系", ["姓名", "身份", "你是谁", "叫什么", "和对方什么关系", "关系"]),
            ("人物", ["谁在场", "还有谁", "哪些人", "对方是谁", "都有哪些人"]),
            ("经过", ["经过", "怎么回事", "发生了什么", "具体怎么发生", "谁先"]),
            ("风险/伤情", ["受伤", "危险", "120", "是否安全", "风险"]),
            ("证据/现场", ["现场", "证据", "监控", "保持原状", "先别动", "录像"]),
        ],
        "审讯": [
            ("时间", ["什么时候", "几点", "时间线", "案发时", "何时"]),
            ("经过", ["经过", "怎么回事", "发生了什么", "谁先", "具体怎么发生"]),
            ("矛盾点", ["矛盾", "对不上", "不一致", "改口", "前后"]),
            ("证据/现场", ["证据", "监控", "录像", "聊天记录", "物证", "不在场"]),
            ("动机/利益", ["为什么", "动机", "原因", "图什么", "利益"]),
        ],
        "通用": [
            ("时间", ["什么时候", "几点", "时间"]),
            ("地点", ["哪里", "地点", "位置"]),
            ("人物", ["谁在场", "哪些人", "对方是谁"]),
            ("经过", ["经过", "怎么回事", "发生了什么"]),
        ],
    }

    requirements = requirements_map.get(scene_type, requirements_map["通用"])
    satisfied = [label for label, keywords in requirements if contains_any(joined, keywords)]
    missing = [label for label, _ in requirements if label not in satisfied]
    return {
        "scene_type": scene_type,
        "requirements": [label for label, _ in requirements],
        "satisfied": satisfied,
        "missing": missing,
    }


def render_rule_summary(rule_checks: Dict[str, Any]) -> str:
    findings = rule_checks["findings"]
    if not findings:
        return "未发现明显的规则性硬伤，可重点依据对话质量和场景表现评分。"
    lines = [f"- [{item['level']}] {item['dimension']}：{item['message']}" for item in findings]
    return "\n".join(lines)


def _level_ratio(level: Any) -> float:
    return {
        "excellent": 1.0,
        "good": 0.85,
        "fair": 0.65,
        "weak": 0.4,
    }.get(str(level or "").strip(), 0.65)


def _ratio_level(ratio: float) -> str:
    if ratio >= 0.9:
        return "excellent"
    if ratio >= 0.75:
        return "good"
    if ratio >= 0.55:
        return "fair"
    return "weak"


def _round_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _infer_point_difficulty(point: dict) -> Tuple[str, float]:
    raw = str(point.get("difficulty") or point.get("difficulty_level") or "").strip()
    if raw in POINT_DIFFICULTY_FACTORS:
        return raw, POINT_DIFFICULTY_FACTORS[raw]
    weight = max(1, int(point.get("weight") or 10))
    if weight <= 10:
        return "低", POINT_DIFFICULTY_FACTORS["低"]
    if weight >= 14:
        return "高", POINT_DIFFICULTY_FACTORS["高"]
    return "中等", POINT_DIFFICULTY_FACTORS["中等"]


def _point_unit(point: dict) -> float:
    _, factor = _infer_point_difficulty(point)
    required_factor = 1.15 if point.get("required", True) else 1.0
    return round(factor * required_factor, 4)


def calculate_adaptive_weighting(point_results: List[dict]) -> Dict[str, Any]:
    points = dedupe_assessment_result_points([point for point in point_results if str(point.get("label") or "").strip()])
    common_units = float(len(COMMON_DIMENSIONS))
    point_units = sum(_infer_point_difficulty(point)[1] for point in points)
    point_distribution_units = sum(_point_unit(point) for point in points)
    if not points or point_units <= 0:
        common_share = 1.0
        assessment_share = 0.0
    else:
        raw_common_share = common_units / (common_units + point_units)
        common_share = max(0.35, min(0.60, raw_common_share))
        assessment_share = 1.0 - common_share

    point_details = []
    for point in points:
        difficulty_level, difficulty_factor = _infer_point_difficulty(point)
        unit = _point_unit(point)
        share = (assessment_share * unit / point_distribution_units) if point_distribution_units > 0 else 0.0
        point_details.append(
            {
                "id": str(point.get("id") or "").strip(),
                "label": str(point.get("label") or "").strip(),
                "difficulty_level": difficulty_level,
                "difficulty_factor": difficulty_factor,
                "required": bool(point.get("required", True)),
                "unit": unit,
                "score_share": share,
                "full_score": _round_score(share * 100),
            }
        )

    return {
        "scoring_version": SCORING_VERSION,
        "common_units": common_units,
        "assessment_units": round(point_units, 4),
        "assessment_distribution_units": round(point_distribution_units, 4),
        "common_share": common_share,
        "assessment_share": assessment_share,
        "common_full_score": _round_score(common_share * 100),
        "assessment_full_score": _round_score(assessment_share * 100),
        "assessment_point_count": len(points),
        "point_weights": point_details,
    }


def _assistant_after_user_evidence(msgs: List[models.Message]) -> List[str]:
    evidence = []
    previous_was_user = False
    for msg in msgs:
        role = str(getattr(msg, "role", "") or "")
        content = str(getattr(msg, "content", "") or "").strip()
        if role == "assistant" and previous_was_user and content:
            evidence.append(f"AI角色: {content[:120]}")
        previous_was_user = role == "user"
    return evidence


def _sample_evidence(items: List[str], limit: int = 2) -> List[str]:
    return _dedupe_strings(items)[:limit]


def _common_dimension_reviews(
    llm_report: Dict[str, Any],
    student_lines: List[str],
    msgs: List[models.Message],
    rule_checks: Dict[str, Any],
) -> List[dict]:
    joined = "\n".join(student_lines)
    user_evidence = [f"学员: {line[:120]}" for line in student_lines if str(line).strip()]
    adjacent_ai_evidence = _assistant_after_user_evidence(msgs)
    llm_reviews = {
        str(item.get("dimension") or "").strip(): item
        for item in (llm_report.get("common_reviews") or [])
        if isinstance(item, dict)
    }
    deductions = rule_checks.get("deductions") or {}

    seed = {
        COMMUNICATION_DIMENSION: {
            "ratio": 0.82 if contains_any(joined, ["请", "麻烦", "您", "说明", "是否", "你好"]) else 0.68,
            "reason": "学员表达总体可控，未见明显激化表达。" if student_lines else "缺少有效学员表达，无法体现规范沟通。",
            "evidence": _sample_evidence(user_evidence),
        },
        INQUIRY_DIMENSION: {
            "ratio": min(0.9, 0.45 + len(student_lines) * 0.08),
            "reason": "学员能够持续发问推进对话。" if len(student_lines) >= 4 else "学员追问轮次偏少，逻辑推进不足。",
            "evidence": _sample_evidence(user_evidence),
        },
        SUMMARY_DIMENSION: {
            "ratio": 0.78 if len(adjacent_ai_evidence) >= 2 else 0.6,
            "reason": "学员通过提问获得了部分关键事实。" if adjacent_ai_evidence else "缺少由学员主动触发的关键信息证据。",
            "evidence": _sample_evidence(user_evidence + adjacent_ai_evidence),
        },
        CLOSURE_DIMENSION: {
            "ratio": 0.75 if contains_any(joined, ["下一步", "后续", "处理", "结束", "带回", "笔录", "移交"]) else 0.55,
            "reason": "学员体现了后续处置或收尾安排。" if contains_any(joined, ["下一步", "后续", "处理", "结束", "带回", "笔录", "移交"]) else "未充分说明下一步安排或阶段收尾。",
            "evidence": _sample_evidence(user_evidence),
        },
    }

    reviews = []
    for dimension, focus in COMMON_DIMENSIONS:
        llm_item = llm_reviews.get(dimension) or {}
        ratio = _level_ratio(llm_item.get("level")) if llm_item else seed[dimension]["ratio"]
        deduct_ratio = min(0.35, float(deductions.get(dimension) or 0) / 25.0)
        ratio = max(0.0, min(1.0, ratio - deduct_ratio))
        reason = str(llm_item.get("reason") or seed[dimension]["reason"]).strip()
        if deductions.get(dimension):
            reason = f"{reason} 规则校验扣减 {deductions.get(dimension)} 分。"
        evidence = _dedupe_strings((llm_item.get("evidence") or []) + seed[dimension]["evidence"])[:3]
        reviews.append(
            {
                "dimension": dimension,
                "focus": focus,
                "level": _ratio_level(ratio),
                "ratio": ratio,
                "reason": reason,
                "evidence": evidence,
            }
        )
    return reviews


def _detect_red_flags(student_lines: List[str]) -> List[dict]:
    joined = "\n".join(student_lines)
    flags = []
    for key, rule in RED_FLAG_RULES.items():
        hits = [keyword for keyword in rule["keywords"] if keyword in joined]
        if hits:
            flags.append(
                {
                    "key": key,
                    "label": rule["label"],
                    "cap": rule["cap"],
                    "evidence": hits[:3],
                }
            )
    return flags


def _score_cap_summary(student_lines: List[str], point_results: List[dict], red_flags: List[dict]) -> Dict[str, Any]:
    caps = []
    turn_count = len(student_lines)
    if turn_count <= 1:
        caps.append({"type": "turn_count", "cap": 55, "reason": "有效学员发言不超过 1 轮"})
    elif turn_count == 2:
        caps.append({"type": "turn_count", "cap": 68, "reason": "有效学员发言不超过 2 轮"})
    elif turn_count == 3:
        caps.append({"type": "turn_count", "cap": 78, "reason": "有效学员发言不超过 3 轮"})

    required_points = [point for point in point_results if point.get("required", True)]
    required_hit = [point for point in required_points if point.get("status") == "hit"]
    required_rate = (len(required_hit) / len(required_points)) if required_points else 1.0
    if required_rate < 0.35:
        caps.append({"type": "required_rate", "cap": 58, "reason": "必考点 hit 率低于 35%"})
    elif required_rate < 0.55:
        caps.append({"type": "required_rate", "cap": 70, "reason": "必考点 hit 率低于 55%"})
    elif required_rate < 0.75:
        caps.append({"type": "required_rate", "cap": 82, "reason": "必考点 hit 率低于 75%"})

    for flag in red_flags:
        caps.append({"type": "red_flag", "cap": int(flag.get("cap") or 100), "reason": flag.get("label")})

    final_cap = min([int(item["cap"]) for item in caps], default=100)
    return {
        "turn_count": turn_count,
        "required_total": len(required_points),
        "required_hit": len(required_hit),
        "required_rate": required_rate,
        "caps": caps,
        "final_cap": final_cap,
    }


def build_adaptive_report(
    llm_report: Dict[str, Any],
    point_results: List[dict],
    action_results: List[dict],
    student_lines: List[str],
    msgs: List[models.Message],
    rule_checks: Dict[str, Any],
    scene_type: str,
) -> Dict[str, Any]:
    point_results = dedupe_assessment_result_points(point_results)
    weighting = calculate_adaptive_weighting(point_results)
    common_reviews = _common_dimension_reviews(llm_report, student_lines, msgs, rule_checks)
    common_full = weighting["common_full_score"]
    common_each_full = common_full / max(1, len(common_reviews))

    scores: List[dict] = []
    running_total = 0
    for review in common_reviews:
        full_score = _round_score(common_each_full)
        score = _round_score(full_score * float(review.get("ratio") or 0))
        running_total += score
        scores.append(
            {
                "dimension": review["dimension"],
                "group": "common",
                "score": score,
                "full_score": full_score,
                "reason": review["reason"],
                "evidence": review["evidence"],
                "level": review["level"],
                "status": review["level"],
            }
        )

    point_weight_map = {item["id"]: item for item in weighting.get("point_weights") or []}
    enriched_points = []
    for point in point_results:
        point_id = str(point.get("id") or "").strip()
        point_weight = point_weight_map.get(point_id) or {}
        share = float(point_weight.get("score_share") or 0)
        full_score = _round_score(share * 100)
        status = str(point.get("status") or "missed")
        ratio = 1.0 if status == "hit" else 0.5 if status == "partial" else 0.0
        score = _round_score(full_score * ratio)
        running_total += score
        enriched = {
            **point,
            "difficulty_level": point_weight.get("difficulty_level") or _infer_point_difficulty(point)[0],
            "difficulty_factor": point_weight.get("difficulty_factor") or _infer_point_difficulty(point)[1],
            "score_share": share,
            "weighted_score": score,
            "full_score": full_score,
        }
        enriched_points.append(enriched)
        scores.append(
            {
                "dimension": f"考察点：{point.get('label') or '未命名考察点'}",
                "group": "assessment",
                "score": score,
                "full_score": full_score,
                "reason": point.get("feedback") or _default_point_feedback(point),
                "evidence": point.get("evidence") or [],
                "level": status,
                "status": status,
                "assessment_point_id": point_id,
                "difficulty_level": enriched["difficulty_level"],
                "required": bool(point.get("required", True)),
            }
        )

    red_flags = _detect_red_flags(student_lines)
    cap_summary = _score_cap_summary(student_lines, enriched_points, red_flags)
    uncapped_total = max(0, min(100, running_total))
    total_score = min(uncapped_total, int(cap_summary["final_cap"]))
    if total_score != uncapped_total:
        scores = reconcile_dimension_scores({"scores": scores, "total_score": total_score}).get("scores") or scores

    required_points = [point for point in enriched_points if point.get("required", True)]
    all_hit = [point for point in enriched_points if point.get("status") == "hit"]
    required_hit = [point for point in required_points if point.get("status") == "hit"]
    total_weight = sum(max(1, int(point.get("weight") or 10)) for point in enriched_points)
    earned_weight = sum(int(point.get("score") or 0) for point in enriched_points)

    strengths = list(llm_report.get("strengths") or [])
    improvements = list(llm_report.get("improvements") or [])
    for point in enriched_points:
        label = str(point.get("label") or "").strip()
        if point.get("status") == "hit":
            strengths.append(f"已覆盖考察点：{label}")
        elif point.get("status") == "missed" and point.get("required", True):
            improvements.append(f"必考点未完成：{label}")
    for finding in rule_checks.get("findings") or []:
        improvements.append(str(finding.get("message") or "").strip())

    suggestions = str(llm_report.get("suggestions") or "").strip()
    if len(suggestions) < 12:
        suggestions = "建议按通用能力和本场景考察点逐项复训，先补齐必考点，再提升追问质量与收尾表达。"

    return {
        "scores": scores,
        "total_score": total_score,
        "uncapped_total_score": uncapped_total,
        "grade_level": compute_grade_level(total_score),
        "assessment_point_results": enriched_points,
        "action_results": action_results,
        "strengths": list(dict.fromkeys([item for item in strengths if str(item).strip()]))[:6],
        "improvements": list(dict.fromkeys([item for item in improvements if str(item).strip()]))[:8],
        "suggestions": suggestions,
        "evaluation_meta": {
            "scoring_version": SCORING_VERSION,
            "scene_type": scene_type,
            "weighting": weighting,
            "score_caps": cap_summary,
            "red_flags": red_flags,
            "rule_findings": rule_checks.get("findings") or [],
            "hybrid_mode": True,
            "model": get_chat_model(),
            "technique": ["RAG", "rule-based checks", "LLM structured review", "adaptive deterministic scoring"],
            "assessment_completion": {
                "required_total": len(required_points),
                "required_hit": len(required_hit),
                "required_rate": (len(required_hit) / len(required_points)) if required_points else 1.0,
                "overall_total": len(enriched_points),
                "overall_hit": len(all_hit),
                "overall_rate": (len(all_hit) / len(enriched_points)) if enriched_points else 1.0,
                "total_weight": total_weight,
                "earned_weight": earned_weight,
                "weight_rate": (earned_weight / total_weight) if total_weight else 1.0,
            },
        },
    }


def build_knowledge_hits(case: Any, scene: Any, scene_type: str, limit: int = 5, knowledge_refs: List[str] | None = None) -> List[str]:
    hits: List[str] = []
    if knowledge_refs:
        for item in rag_service.get_documents_by_ids(knowledge_refs):
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            snippet = title or content[:60]
            if snippet and snippet not in hits:
                hits.append(snippet)
            if len(hits) >= limit:
                return hits[:limit]

    queries: List[str] = []
    if case:
        queries.extend(
            [
                str(getattr(case, "case_type", "") or "").strip(),
                str(getattr(case, "title", "") or "").strip(),
                str(getattr(case, "background", "") or "").strip()[:80],
            ]
        )
    if scene:
        queries.append(str(getattr(scene, "name", "") or "").strip())
    queries.append(str(scene_type or "").strip())

    for query in queries:
        if not query:
            continue
        for item in rag_service.search(query, limit=limit):
            if item and item not in hits:
                hits.append(item)
            if len(hits) >= limit:
                return hits[:limit]
    return hits[:limit]


def compute_grade_level(total_score: int) -> str:
    score = max(0, min(100, int(total_score or 0)))
    for threshold, label in GRADE_LEVELS:
        if score >= threshold:
            return label
    return "需改进"


def _resolve_point_status(runtime_status: str | None, llm_status: str | None) -> str:
    runtime_rank = _STATUS_RANK.get(str(runtime_status or "").strip(), 0)
    llm_rank = _STATUS_RANK.get(str(llm_status or "").strip(), 0)
    best = max(runtime_rank, llm_rank)
    if best >= 3:
        return "hit"
    if best == 2:
        return "partial"
    return "missed"


def _score_from_point_status(status: str, weight: int) -> int:
    weight = max(1, int(weight or 10))
    if status == "hit":
        return weight
    if status == "partial":
        return max(1, weight // 2)
    return 0


def _default_point_feedback(point: dict) -> str:
    status = str(point.get("status") or "missed")
    evidence = point.get("evidence") or []
    evidence_text = "；".join(_dedupe_strings(evidence)[:2])
    if status == "hit":
        return f"已达考察要求。{('依据：' + evidence_text) if evidence_text else ''}".strip()
    if status == "partial":
        return f"部分达成，仍需补全关键环节。{('已出现：' + evidence_text) if evidence_text else ''}".strip()
    return "未在对话或动作中发现有效完成痕迹，建议按阶段要求补做。"


def merge_assessment_point_results(
    runtime_points: List[dict],
    llm_points: List[dict],
    requirement_rows: List[dict],
) -> List[dict]:
    def merge_by_id(points: List[dict]) -> Dict[str, dict]:
        output: Dict[str, dict] = {}
        for point in points or []:
            if not isinstance(point, dict):
                continue
            point_id = str(point.get("id") or "").strip()
            if not point_id:
                continue
            output[point_id] = _merge_duplicate_assessment_points(output[point_id], point) if point_id in output else dict(point)
        return output

    req_map = merge_by_id(requirement_rows)
    runtime_map = merge_by_id(runtime_points)
    llm_map = merge_by_id(llm_points)
    ordered_ids = [str(row.get("id") or "").strip() for row in requirement_rows if str(row.get("id") or "").strip()]
    for point_id in runtime_map:
        if point_id not in ordered_ids:
            ordered_ids.append(point_id)
    for point_id in llm_map:
        if point_id not in ordered_ids:
            ordered_ids.append(point_id)

    merged: List[dict] = []
    for point_id in ordered_ids:
        runtime_point = runtime_map.get(point_id) or {}
        llm_point = llm_map.get(point_id) or {}
        req_row = req_map.get(point_id) or {}
        label = str(runtime_point.get("label") or llm_point.get("label") or req_row.get("label") or "未命名考察点").strip()
        weight = max(1, int(req_row.get("weight") or runtime_point.get("weight") or 10))
        status = _resolve_point_status(runtime_point.get("status"), llm_point.get("status"))
        evidence = _dedupe_strings((runtime_point.get("evidence") or []) + (llm_point.get("evidence") or []))[:3]
        feedback = str(llm_point.get("reason") or llm_point.get("feedback") or runtime_point.get("feedback") or "").strip()
        if not feedback:
            feedback = _default_point_feedback({"status": status, "evidence": evidence})
        merged.append(
            {
                "id": point_id,
                "label": label,
                "content": str(req_row.get("content") or llm_point.get("content") or "").strip(),
                "stage_name": str(runtime_point.get("stage_name") or req_row.get("stage_name") or llm_point.get("stage_name") or "").strip(),
                "category": str(req_row.get("category") or runtime_point.get("category") or "procedure").strip() or "procedure",
                "required": bool(req_row.get("required", runtime_point.get("required", True))),
                "weight": weight,
                "status": status,
                "score": _score_from_point_status(status, weight),
                "evidence": evidence,
                "feedback": feedback,
                "knowledge_refs": _dedupe_strings(runtime_point.get("knowledge_refs") or req_row.get("knowledge_refs") or []),
            }
        )
    return dedupe_assessment_result_points(merged)


def reconcile_dimension_scores(report: Dict[str, Any]) -> Dict[str, Any]:
    scores = report.get("scores") or []
    if not scores:
        return report

    target_total = max(0, min(100, int(report.get("total_score") or 0)))
    dim_sum = sum(int(item.get("score") or 0) for item in scores)
    if dim_sum == target_total:
        report["total_score"] = dim_sum
        return report

    if dim_sum <= 0:
        report["total_score"] = 0
        return report

    ratio = target_total / dim_sum
    adjusted: List[dict] = []
    running = 0
    for index, item in enumerate(scores):
        full_score = int(item.get("full_score") or 0)
        raw = int(round(int(item.get("score") or 0) * ratio))
        if index == len(scores) - 1:
            score = max(0, min(full_score, target_total - running))
        else:
            score = max(0, min(full_score, raw))
        running += score
        adjusted.append({**item, "score": score})

    report["scores"] = adjusted
    report["total_score"] = sum(int(item.get("score") or 0) for item in adjusted)
    return report


def finalize_evaluation_report(
    report: Dict[str, Any],
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    student_lines: List[str],
) -> Dict[str, Any]:
    total_score = int(report.get("total_score") or 0)
    report["grade_level"] = compute_grade_level(total_score)
    report["total_score"] = total_score

    if "evaluation_meta" not in report:
        report["evaluation_meta"] = {}
    report["evaluation_meta"]["report_header"] = {
        "session_id": session.id,
        "case_title": str(getattr(case, "title", "") or "未知案件").strip() or "未知案件",
        "case_type": str(getattr(case, "case_type", "") or "").strip() or "其他",
        "scene_name": str(getattr(scene, "name", "") or "训练场景").strip() or "训练场景",
        "scene_type": report["evaluation_meta"].get("scene_type") or infer_scene_type(scene) if scene else "通用",
        "dialogue_turns": len(student_lines),
        "grade_level": report["grade_level"],
        "total_score": total_score,
    }
    report["evaluation_meta"]["prompt_version"] = "formal_report_v3"
    report["evaluation_meta"]["scene_template_version"] = "formal_report_v3"
    return report


def _collect_structured_assessment(
    session: models.TrainingSession,
    scene: models.Scene | None,
    case: models.Case | None,
    msgs: List[models.Message],
) -> Dict[str, Any]:
    runtime_state = load_runtime_state(session.revealed_info)
    revealed_info = runtime_state.get("revealed_info") or []
    case_type = str(getattr(case, "case_type", "") or "").strip()
    stages = normalize_stages(
        getattr(scene, "stages", []),
        case_type=case_type,
        scene_name=str(getattr(scene, "name", "") or ""),
    ) if scene else []

    requirement_rows: List[dict] = []
    knowledge_ref_ids: List[str] = []
    point_results: List[dict] = []
    action_results: List[dict] = []
    satisfied: List[str] = []
    missing: List[str] = []
    total_weight = 0
    earned_weight = 0

    for stage in stages:
        stage_name = str(stage.get("stage_name") or "").strip()
        for point in stage.get("assessment_points") or []:
            if not isinstance(point, dict):
                continue
            label = str(point.get("label") or "").strip()
            content = str(point.get("content") or "").strip()
            if not label and not content:
                continue
            requirement_rows.append(
                {
                    "id": str(point.get("id") or "").strip() or "",
                    "label": label or content[:18] or "未命名考察点",
                    "content": content,
                    "stage_name": stage_name or "",
                    "category": str(point.get("category") or "procedure").strip() or "procedure",
                    "weight": max(1, int(point.get("weight", 10) or 10)),
                    "required": bool(point.get("required", True)),
                    "keywords": point.get("keywords") or [],
                    "knowledge_refs": point.get("knowledge_refs") or [],
                }
            )
            knowledge_ref_ids.extend(point.get("knowledge_refs") or [])

        progress = collect_stage_progress(stage, msgs, revealed_info)
        for point in progress.get("points") or []:
            if not isinstance(point, dict):
                continue
            enriched = {
                **point,
                "stage_name": stage_name or str(point.get("stage_name") or "").strip(),
                "feedback": str(point.get("feedback") or "").strip() or _default_point_feedback(point),
            }
            point_results.append(enriched)
            total_weight += max(1, int(enriched.get("weight") or 10))
            earned_weight += int(enriched.get("score") or 0)
            label = str(enriched.get("label") or "").strip()
            if not label:
                continue
            if enriched.get("status") == "hit":
                satisfied.append(label)
            elif enriched.get("status") != "partial":
                missing.append(label)

        for action in progress.get("actions") or []:
            if isinstance(action, dict):
                action_results.append({**action, "stage_name": stage_name or ""})

    requirement_rows = dedupe_assessment_result_points(requirement_rows)
    point_results = dedupe_assessment_result_points(point_results)
    total_weight = sum(max(1, int(point.get("weight") or 10)) for point in point_results)
    earned_weight = sum(int(point.get("score") or 0) for point in point_results)
    satisfied = []
    missing = []
    for point in point_results:
        label = str(point.get("label") or "").strip()
        if not label:
            continue
        if point.get("status") == "hit":
            satisfied.append(label)
        elif point.get("status") != "partial":
            missing.append(label)

    stored_progress = runtime_state.get("assessment_progress") or {}
    if not point_results and isinstance(stored_progress, dict):
        stored_summary = stored_progress.get("summary") if isinstance(stored_progress.get("summary"), dict) else {}
        total_weight = max(total_weight, int(stored_summary.get("total_weight") or 0))
        earned_weight = max(earned_weight, int(stored_summary.get("earned_weight") or 0))

    summary = {
        "scene_type": infer_scene_type(scene) if scene else "通用",
        "requirements": [row.get("label") for row in requirement_rows if row.get("label")],
        "satisfied": _dedupe_strings(satisfied),
        "missing": _dedupe_strings(missing),
        "total_weight": total_weight,
        "earned_weight": earned_weight,
    }
    return {
        "assessment_requirements": requirement_rows,
        "point_results": point_results,
        "action_results": action_results,
        "knowledge_ref_ids": _dedupe_strings(knowledge_ref_ids),
        "stage_gap_summary": summary,
        "closure_summary": runtime_state.get("closure_summary") or {},
    }


def _render_assessment_requirements(requirement_rows: List[dict]) -> str:
    if not requirement_rows:
        return "暂无考察点要求表。"
    lines: List[str] = ["考察点要求："]
    for idx, row in enumerate(requirement_rows[:30], start=1):
        label = str(row.get("label") or "").strip()
        content = str(row.get("content") or "").strip()
        stage_name = str(row.get("stage_name") or "").strip()
        header = f"{idx}. {label}"
        if stage_name:
            header += f"（场景/阶段：{stage_name}）"
        lines.append(f"- {header}")
        if content:
            lines.append(f"  要求：{content}")
    return "\n".join(lines)


def _knowledge_index(knowledge_ref_ids: List[str]) -> Dict[str, dict]:
    return {item["id"]: item for item in rag_service.get_documents_by_ids(knowledge_ref_ids)}


def _attach_knowledge_titles(point_results: List[dict], knowledge_docs: Dict[str, dict]) -> List[dict]:
    enriched: List[dict] = []
    for point in point_results:
        titles = []
        for ref_id in point.get("knowledge_refs") or []:
            title = str((knowledge_docs.get(ref_id) or {}).get("title") or "").strip()
            if title:
                titles.append(title)
        enriched.append({**point, "knowledge_titles": _dedupe_strings(titles)})
    return enriched


def _render_assessment_evidence(point_results: List[dict], action_results: List[dict]) -> str:
    lines = []
    if point_results:
        lines.append("考察点：")
        for point in point_results[:18]:
            evidence = "；".join(point.get("evidence") or []) or "无明确证据"
            lines.append(
                f"- [{point.get('status')}] {point.get('label')} / 阶段={point.get('stage_name')} / 证据={evidence}"
            )
    if action_results:
        lines.append("动作：")
        for action in action_results[:18]:
            evidence = "；".join(action.get("evidence") or []) or "无明确动作证据"
            lines.append(
                f"- [{action.get('status')}] {action.get('label')} / 阶段={action.get('stage_name')} / 证据={evidence}"
            )
    return "\n".join(lines) if lines else "暂无结构化考察点或动作证据。"


def _enrich_report_from_structured_evidence(report: Dict[str, Any], point_results: List[dict], action_results: List[dict]) -> Dict[str, Any]:
    strengths = list(report.get("strengths") or [])
    improvements = list(report.get("improvements") or [])

    for point in point_results:
        label = str(point.get("label") or "").strip()
        if point.get("status") == "hit":
            strengths.append(f"已覆盖考察点：{label}")
        elif point.get("status") == "missed" and point.get("required", True):
            improvements.append(f"必考点未完成：{label}")

    for action in action_results:
        label = str(action.get("label") or "").strip()
        if action.get("status") == "missed":
            improvements.append(f"关键动作缺失：{label}")

    report["strengths"] = list(dict.fromkeys(strengths))[:6]
    report["improvements"] = list(dict.fromkeys(improvements))[:8]
    return report


def evaluate_session(db: Session, session_id: int, user_id: int | None = None, force_recompute: bool = False):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        return None
    if user_id is not None and session.user_id != user_id:
        return None

    if not force_recompute and session.status == "finished" and session.evaluation_result:
        return json.loads(session.evaluation_result)

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    msgs = (
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    role = resolve_scene_role(db, scene, case) if scene else None

    dialogue_history, student_lines = format_dialogue(msgs)
    scene_type = infer_scene_type(scene) if scene else "通用"
    rule_checks = build_rule_checks(scene, student_lines, role) if scene else {"findings": [], "deductions": {}, "scene_type": "通用"}
    rule_check_summary = render_rule_summary(rule_checks)
    structured_assessment = _collect_structured_assessment(session, scene, case, msgs)
    requirement_rows = structured_assessment.get("assessment_requirements") or []
    runtime_point_results = structured_assessment.get("point_results") or []
    action_results = structured_assessment.get("action_results") or []
    knowledge = build_knowledge_hits(
        case,
        scene,
        scene_type,
        limit=5,
        knowledge_refs=structured_assessment["knowledge_ref_ids"],
    )
    knowledge_base = "\n".join([f"- {item}" for item in knowledge]) if knowledge else "暂无相关法律标准参考。"
    assessment_requirements = _render_assessment_requirements(requirement_rows)

    scene_rubric = "\n".join([f"- {item}" for item in SCENE_RUBRICS.get(scene_type, SCENE_RUBRICS["通用"])])
    case_info = "暂无案件信息"
    if case:
        case_info = f"案件标题：{case.title}\n案件类型：{case.case_type}\n案件背景：{case.background}"
    scene_info = _build_scene_info(scene, scene_type, role, case)

    full_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        scene_info=scene_info,
        scene_rubric=scene_rubric,
        rule_check_summary=rule_check_summary,
        case_info=case_info,
        dialogue_history=dialogue_history or "暂无对话内容",
        assessment_requirements=assessment_requirements,
        knowledge_base=knowledge_base,
    )

    try:
        response = create_json_chat_completion(
            model=get_chat_model(),
            messages=[
                {"role": "system", "content": "你是一名公正、严格、专业的警务训练教官，必须输出合法 JSON。"},
                {"role": "user", "content": full_prompt},
            ],
            max_tokens=2600,
        )

        raw_content = _extract_response_text(response)
        llm_report = extract_json_payload(raw_content)
        if not isinstance(llm_report, dict):
            llm_report = {
                "common_reviews": [],
                "assessment_check_results": [],
                "strengths": [],
                "improvements": [],
                "suggestions": str(raw_content or "").strip()[:220],
                "evaluation_meta": {"llm_fallback": True, "raw_summary": str(raw_content or "").strip()[:220]},
            }

        check_results = llm_report.get("assessment_check_results") if isinstance(llm_report.get("assessment_check_results"), list) else []
        knowledge_docs = _knowledge_index(structured_assessment["knowledge_ref_ids"])
        merged_points = merge_assessment_point_results(runtime_point_results, check_results, requirement_rows)
        merged_points = _attach_knowledge_titles(merged_points, knowledge_docs)
        report = build_adaptive_report(
            llm_report,
            merged_points,
            action_results,
            student_lines,
            msgs,
            rule_checks,
            scene_type,
        )
        report["closure_summary"] = structured_assessment["closure_summary"]

        if "evaluation_meta" not in report:
            report["evaluation_meta"] = {}
        report["evaluation_meta"]["scene_type"] = scene_type
        report["evaluation_meta"]["knowledge_hits"] = knowledge
        report["evaluation_meta"]["stage_gap_summary"] = structured_assessment["stage_gap_summary"] or build_stage_gap_summary(scene, student_lines)
        if isinstance(llm_report.get("evaluation_meta"), dict):
            report["evaluation_meta"]["llm_fallback"] = bool(llm_report["evaluation_meta"].get("llm_fallback", False))
            if llm_report["evaluation_meta"].get("raw_summary"):
                report["evaluation_meta"]["raw_summary"] = llm_report["evaluation_meta"]["raw_summary"]
        report = finalize_evaluation_report(report, session, scene, case, student_lines)
        report = append_scene_performance_report(db, session.id, report)

        report_json = json.dumps(report, ensure_ascii=False)
        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()

        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {"error": str(e)}
