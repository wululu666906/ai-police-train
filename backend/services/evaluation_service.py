import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

import models
from .dialogue_sanitize_service import filter_internal_prompt_messages, is_internal_prompt_message
from .llm_provider import create_json_chat_completion, extract_json_payload, extract_message_text, get_chat_model
from .persona_engine import build_persona_profile
from .rag_service import rag_service
from .role_resolver import resolve_scene_role
from .stage_config_service import normalize_stages
from .training_runtime_service import collect_stage_progress, load_runtime_state

SCORING_VERSION = "adaptive_v1"
CURRENT_EVALUATION_POLICY_VERSION = "adaptive_v1_llm_cap_audit_v2"

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


def _parse_report_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except ValueError:
            for pattern in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(normalized, pattern)
                except ValueError:
                    continue
    return None


def _report_header_from_payload(report: Dict[str, Any]) -> Dict[str, Any]:
    meta = report.get("evaluation_meta") if isinstance(report, dict) else {}
    header = meta.get("report_header") if isinstance(meta, dict) else {}
    return header if isinstance(header, dict) else {}


def _format_report_datetime(value: Any) -> str | None:
    parsed = _parse_report_datetime(value)
    if not parsed:
        return None
    if parsed.tzinfo:
        return parsed.isoformat()
    return f"{parsed.isoformat()}+00:00"

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

本系统使用 adaptive_v1 评分制度：你必须依据下方“评分模板”对所有指标逐项打分。后端只负责校验范围、去重、证据有效性和落库，不会替你完成主要评分。

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

评分模板（必须逐项打分，score 不得只机械给半分或整档分）：
{scoring_template}

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
1. common_reviews 必须覆盖 4 个通用能力，每项包含 dimension、full_score、score、level、reason、evidence。level 只能为 excellent/good/fair/weak。
2. assessment_check_results 必须与“考察点要求表”逐条对应，不得遗漏 id，每项包含 id、label、full_score、score、status、evidence、reason。status 只能为 hit/partial/missed。
3. evidence 必须引用具体学员发言/动作，以及学员提问后紧邻的 AI 回答。考察点命中需要同时看到学员主动触发和 AI 反馈结果；不得把 AI 主动长篇交代或学员简单应答直接算作命中。
4. strengths 是学员表现亮点（2-4 条），improvements 是具体不足（2-4 条），suggestions 给出下一轮训练建议。
5. 只输出合法 JSON。

严格输出 JSON：
{{
  "common_reviews": [
    {{"dimension": "沟通表达与执法语言", "full_score": 12, "score": 9, "level": "good", "reason": "学员语气总体克制。", "evidence": ["学员: 请您先说明情况"]}},
    {{"dimension": "主动询问与逻辑推进", "full_score": 12, "score": 7, "level": "fair", "reason": "追问不足。", "evidence": []}},
    {{"dimension": "关键信息整理能力", "full_score": 12, "score": 6, "level": "fair", "reason": "未形成完整事实归纳。", "evidence": []}},
    {{"dimension": "处置闭环意识", "full_score": 12, "score": 4, "level": "weak", "reason": "未说明下一步处置。", "evidence": []}}
  ],
  "assessment_check_results": [
    {{"id": "ap_001", "label": "核实报警人身份", "content": "学员应主动询问报警人姓名、身份及与事件的关系", "full_score": 8, "score": 6, "status": "partial", "evidence": ["学员: 请问您怎么称呼？"], "reason": "学员主动核实身份，但未确认联系方式。"}}
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
    text = re.sub(r"^(学员应|学员应当|应当|需要|需|要求|目标)[:：\s]*", "", text)
    return text


ASSESSMENT_KEY_TERMS = [
    "报警人", "身份", "姓名", "联系方式", "电话", "关系",
    "时间", "地点", "地址", "位置", "几号楼", "房间",
    "人员", "在场", "对方", "嫌疑人", "当事人",
    "经过", "原因", "诉求", "矛盾", "冲突",
    "伤情", "受伤", "危险", "风险", "安全", "救助", "120",
    "证据", "监控", "录像", "记录", "物证", "现场",
    "处置", "派警", "控制", "分离", "告知", "闭环",
]

ASSESSMENT_TERM_ALIASES = {
    "电话": "联系方式",
    "位置": "地点",
    "地址": "地点",
    "几号楼": "地点",
    "房间": "地点",
    "人员": "在场",
    "对方": "当事人",
    "嫌疑人": "当事人",
    "冲突": "矛盾",
    "受伤": "伤情",
    "救助": "伤情",
    "120": "伤情",
    "录像": "监控",
    "记录": "证据",
    "物证": "证据",
}


def _assessment_term_set(point: dict) -> set[str]:
    text = _normalize_assessment_identity_text(
        " ".join(
            str(point.get(key) or "")
            for key in ("label", "content", "requirement", "description", "target", "assessment_target", "goal")
        )
    )
    terms = {term for term in ASSESSMENT_KEY_TERMS if _normalize_assessment_identity_text(term) in text}
    return {ASSESSMENT_TERM_ALIASES.get(term, term) for term in terms}


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
    left_content = _normalize_assessment_identity_text(_assessment_core_content(left.get("content") or left.get("requirement") or left.get("description")))
    right_content = _normalize_assessment_identity_text(_assessment_core_content(right.get("content") or right.get("requirement") or right.get("description")))

    left_terms = _assessment_term_set(left)
    right_terms = _assessment_term_set(right)
    term_union = left_terms | right_terms
    term_overlap = (len(left_terms & right_terms) / len(term_union)) if term_union else 0.0
    label_similarity = SequenceMatcher(None, left_label, right_label).ratio() if left_label and right_label else 0.0
    content_similarity = SequenceMatcher(None, left_content, right_content).ratio() if left_content and right_content else 0.0

    if left_label and right_label and left_label == right_label:
        if not left_content or not right_content:
            return True
        if left_content in right_content or right_content in left_content:
            return True
        return content_similarity >= 0.62 or term_overlap >= 0.75

    if term_overlap >= 0.85 and (label_similarity >= 0.5 or content_similarity >= 0.5):
        return True
    if term_overlap >= 0.6 and (label_similarity >= 0.72 or content_similarity >= 0.62):
        return True
    if label_similarity >= 0.88 and content_similarity >= 0.58:
        return True
    if content_similarity >= 0.82 and term_overlap >= 0.5:
        return True
    if not left_label or not right_label:
        return bool(left_content and right_content and content_similarity >= 0.86)
    if left_content in right_content or right_content in left_content:
        return term_overlap >= 0.5 or min(len(left_content), len(right_content)) >= 8
    return False


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


def _clamp_ratio(value: Any, default: float = 0.0) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        ratio = default
    return max(0.0, min(1.0, ratio))


def _point_completion_ratio(point: dict) -> float:
    status = str(point.get("status") or "").strip()
    if status == "hit":
        return 1.0
    if status in {"missed", "miss"}:
        return 0.0
    explicit = point.get("completion_ratio")
    if explicit is not None:
        return max(0.25, min(0.85, _clamp_ratio(explicit, 0.5)))

    keywords = _dedupe_strings(point.get("keywords") or [])
    matched = _dedupe_strings(point.get("keyword_matches") or [])
    evidence_count = len(_valid_student_or_action_evidence(point.get("evidence") or []))
    linked_actions = point.get("linked_actions_completed") or []
    keyword_target = min(len(keywords), 2) if keywords else 1
    keyword_ratio = (len(matched) / keyword_target) if keyword_target else 0.0
    evidence_bonus = min(0.18, evidence_count * 0.06)
    action_bonus = 0.18 if linked_actions else 0.0
    ratio = 0.3 + min(0.32, keyword_ratio * 0.28) + evidence_bonus + action_bonus
    return max(0.25, min(0.85, ratio))


def _score_from_point(point: dict, weight: int) -> int:
    return max(0, min(max(1, int(weight or 10)), int(round(max(1, int(weight or 10)) * _point_completion_ratio(point)))))


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
    merged["keywords"] = _dedupe_strings((current.get("keywords") or []) + (incoming.get("keywords") or []))
    merged["keyword_matches"] = _dedupe_strings((current.get("keyword_matches") or []) + (incoming.get("keyword_matches") or []))
    merged["linked_actions_completed"] = _dedupe_strings((current.get("linked_actions_completed") or []) + (incoming.get("linked_actions_completed") or []))
    merged["evidence"] = _dedupe_strings((current.get("evidence") or []) + (incoming.get("evidence") or []))[:3]
    merged["completion_ratio"] = max(_point_completion_ratio(current), _point_completion_ratio(incoming))
    merged["score"] = _score_from_point(merged, merged["weight"])
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
        if is_internal_prompt_message(msg):
            continue
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
        "excellent": 0.92,
        "good": 0.78,
        "fair": 0.58,
        "weak": 0.34,
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


def _score_items_total(report: Dict[str, Any]) -> int:
    scores = report.get("scores") if isinstance(report, dict) else []
    if not isinstance(scores, list):
        return 0
    return sum(int(item.get("score") or 0) for item in scores if isinstance(item, dict))


def _extract_cap_sources(report: Dict[str, Any]) -> List[dict]:
    meta = report.get("evaluation_meta") if isinstance(report, dict) else {}
    score_caps = meta.get("score_caps") if isinstance(meta, dict) else {}
    caps: List[dict] = []
    raw_caps = score_caps.get("caps") if isinstance(score_caps, dict) else []
    if isinstance(raw_caps, list):
        for item in raw_caps:
            if not isinstance(item, dict):
                continue
            try:
                cap = int(item.get("cap"))
            except (TypeError, ValueError):
                continue
            caps.append(
                {
                    "type": str(item.get("type") or "unknown"),
                    "cap": max(0, min(100, cap)),
                    "reason": str(item.get("reason") or "").strip(),
                }
            )
    if isinstance(score_caps, dict):
        try:
            final_cap = int(score_caps.get("final_cap"))
        except (TypeError, ValueError):
            final_cap = None
        if final_cap is not None and not any(item["type"] == "reported_final_cap" for item in caps):
            caps.append({"type": "reported_final_cap", "cap": max(0, min(100, final_cap)), "reason": "报告已有最终上限"})
    return caps


def enforce_final_score_policy(report: Dict[str, Any], *, policy_source: str = "unknown") -> Dict[str, Any]:
    if not isinstance(report, dict):
        return report
    if "evaluation_meta" not in report or not isinstance(report.get("evaluation_meta"), dict):
        report["evaluation_meta"] = {}
    meta = report["evaluation_meta"]
    if "score_caps" not in meta or not isinstance(meta.get("score_caps"), dict):
        meta["score_caps"] = {"caps": [], "final_cap": 100}

    cap_sources = _extract_cap_sources(report)
    if not cap_sources:
        cap_sources = [{"type": "no_cap", "cap": 100, "reason": "未触发上限规则"}]
    applied_cap = min(int(item["cap"]) for item in cap_sources)

    try:
        before_score = int(round(float(report.get("total_score"))))
    except (TypeError, ValueError):
        before_score = _score_items_total(report)
    before_score = max(0, min(100, before_score))
    if report.get("uncapped_total_score") is None:
        report["uncapped_total_score"] = before_score

    after_score = min(before_score, applied_cap)
    if after_score != before_score and isinstance(report.get("scores"), list):
        adjusted = reconcile_dimension_scores({"scores": report.get("scores") or [], "total_score": after_score})
        report["scores"] = adjusted.get("scores") or report.get("scores")
        after_score = int(adjusted.get("total_score") or after_score)

    report["total_score"] = max(0, min(100, after_score))
    report["grade_level"] = compute_grade_level(report["total_score"])
    meta["scoring_version"] = SCORING_VERSION
    meta["policy_version"] = CURRENT_EVALUATION_POLICY_VERSION
    meta["score_caps"]["caps"] = [item for item in cap_sources if item["type"] != "reported_final_cap"]
    meta["score_caps"]["final_cap"] = applied_cap
    meta["cap_audit"] = {
        "policy_version": CURRENT_EVALUATION_POLICY_VERSION,
        "policy_source": policy_source,
        "cap_sources": cap_sources,
        "applied_cap": applied_cap,
        "before_cap_score": before_score,
        "after_cap_score": report["total_score"],
        "score_items_total": _score_items_total(report),
        "valid": report["total_score"] <= applied_cap,
        "enforced_at": datetime.utcnow().isoformat(timespec="microseconds"),
    }
    return report


def is_current_evaluation_report(report: Any) -> bool:
    if not isinstance(report, dict):
        return False
    meta = report.get("evaluation_meta")
    if not isinstance(meta, dict):
        return False
    audit = meta.get("cap_audit")
    try:
        total_score = int(round(float(report.get("total_score"))))
        applied_cap = int(audit.get("applied_cap")) if isinstance(audit, dict) else -1
        after_cap_score = int(audit.get("after_cap_score")) if isinstance(audit, dict) else -1
    except (TypeError, ValueError):
        return False
    return (
        meta.get("scoring_version") == SCORING_VERSION
        and meta.get("policy_version") == CURRENT_EVALUATION_POLICY_VERSION
        and isinstance(audit, dict)
        and audit.get("valid") is True
        and 0 <= total_score <= applied_cap <= 100
        and after_cap_score == total_score
    )


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


def _render_scoring_template(weighting: Dict[str, Any], requirement_rows: List[dict], scene_type: str) -> str:
    common_full = _round_score(float(weighting.get("common_full_score") or 0))
    common_each_full = _round_score(common_full / max(1, len(COMMON_DIMENSIONS))) if COMMON_DIMENSIONS else 0
    lines = [
        f"总分：100 分；场景类型：{scene_type}",
        f"通用指标总分：{common_full} 分；考察点总分：{_round_score(float(weighting.get('assessment_full_score') or 0))} 分。",
        "通用指标：",
    ]
    for dimension, focus in COMMON_DIMENSIONS:
        lines.append(f"- {dimension}：满分 {common_each_full} 分。评分依据：{focus}")

    point_weight_map = {str(item.get("id") or "").strip(): item for item in weighting.get("point_weights") or []}
    lines.append("场景考察点：")
    if not requirement_rows:
        lines.append("- 当前场景未配置考察点，考察点总分为 0。")
    for row in requirement_rows:
        point_id = str(row.get("id") or "").strip()
        weight = point_weight_map.get(point_id) or {}
        full_score = int(weight.get("full_score") or 0)
        required_label = "必考" if row.get("required", True) else "选考"
        content = str(row.get("content") or "").strip() or "无补充说明"
        lines.append(
            f"- id={point_id or '未配置'}；{row.get('label') or '未命名考察点'}：满分 {full_score} 分；{required_label}；要求：{content}"
        )
    lines.extend(
        [
            "命中状态换算原则：hit 通常应接近满分；missed 必须为 0 分；partial 需要按完成比例给 25%-85% 区间内的具体分值，不能固定给一半。",
            "证据原则：学员主动提问/动作与 AI 紧邻反馈需要成对判断；AI 角色反馈可作为命中证据的一部分，但 AI 单独主动透露不能作为学员得分。",
        ]
    )
    return "\n".join(lines)


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


def _student_fact_category_count(joined: str) -> int:
    categories = [
        ["姓名", "身份", "你是谁", "叫什么", "关系", "联系方式", "电话"],
        ["什么时候", "几点", "时间", "何时", "刚刚"],
        ["哪里", "地址", "地点", "位置", "几号楼", "房间"],
        ["谁在场", "还有谁", "哪些人", "对方是谁", "人物"],
        ["怎么回事", "什么情况", "经过", "发生了什么", "具体"],
        ["受伤", "危险", "安全", "120", "风险", "还在现场"],
        ["证据", "现场", "监控", "录像", "记录", "物证"],
    ]
    return sum(1 for keywords in categories if contains_any(joined, keywords))


def _required_point_rate(point_results: List[dict]) -> float:
    required_points = [point for point in point_results if point.get("required", True)]
    if not required_points:
        return 1.0
    return sum(_point_completion_ratio(point) for point in required_points) / len(required_points)


def _common_ratio_cap_by_points(dimension: str, point_results: List[dict]) -> float:
    required_rate = _required_point_rate(point_results)
    if dimension == COMMUNICATION_DIMENSION:
        return 0.9 if required_rate >= 0.35 else 0.75
    if required_rate <= 0:
        return 0.5
    if required_rate < 0.35:
        return 0.62
    if required_rate < 0.55:
        return 0.72
    if required_rate < 0.75:
        return 0.82
    return 1.0


def _common_dimension_reviews(
    llm_report: Dict[str, Any],
    student_lines: List[str],
    msgs: List[models.Message],
    rule_checks: Dict[str, Any],
    point_results: List[dict] | None = None,
) -> List[dict]:
    joined = "\n".join(student_lines)
    user_evidence = [f"学员: {line[:120]}" for line in student_lines if str(line).strip()]
    adjacent_ai_evidence = _assistant_after_user_evidence(msgs)
    point_results = point_results or []
    fact_category_count = _student_fact_category_count(joined)
    question_turns = sum(1 for line in student_lines if contains_any(line, ["?", "？", "吗", "什么", "哪里", "几", "是否", "有没有", "谁", "怎么", "为何", "为什么"]))
    total_turns = len([line for line in student_lines if str(line).strip()])
    polite_hits = sum(1 for line in student_lines if contains_any(line, ["请", "麻烦", "您", "你好", "配合", "说明"]))
    red_language_hits = sum(1 for line in student_lines if contains_any(line, RED_FLAG_RULES["coercive_language"]["keywords"]))
    closure_hits = sum(1 for line in student_lines if contains_any(line, ["下一步", "后续", "处理", "结束", "带回", "笔录", "移交", "我们会", "请等待"]))
    required_rate = _required_point_rate(point_results)
    llm_reviews = {
        str(item.get("dimension") or "").strip(): item
        for item in (llm_report.get("common_reviews") or [])
        if isinstance(item, dict)
    }
    deductions = rule_checks.get("deductions") or {}

    seed = {
        COMMUNICATION_DIMENSION: {
            "ratio": min(0.93, 0.58 + polite_hits * 0.055 + min(total_turns, 6) * 0.018 - red_language_hits * 0.22),
            "reason": "学员表达总体可控，未见明显激化表达。" if student_lines else "缺少有效学员表达，无法体现规范沟通。",
            "evidence": _sample_evidence(user_evidence),
        },
        INQUIRY_DIMENSION: {
            "ratio": min(0.9, 0.32 + question_turns * 0.075 + min(fact_category_count, 6) * 0.052 + required_rate * 0.08),
            "reason": "学员能够围绕关键信息持续发问推进对话。" if question_turns >= 4 and fact_category_count >= 3 else "学员追问轮次或关键要素覆盖不足。",
            "evidence": _sample_evidence(user_evidence),
        },
        SUMMARY_DIMENSION: {
            "ratio": min(0.88, 0.30 + fact_category_count * 0.072 + required_rate * 0.16),
            "reason": "学员主动覆盖了多类关键事实要素。" if fact_category_count >= 4 else "学员主动触发的关键信息类别不足。",
            "evidence": _sample_evidence(user_evidence + adjacent_ai_evidence),
        },
        CLOSURE_DIMENSION: {
            "ratio": min(0.86, 0.42 + closure_hits * 0.12 + required_rate * 0.12 + min(total_turns, 5) * 0.015),
            "reason": "学员体现了后续处置或收尾安排。" if contains_any(joined, ["下一步", "后续", "处理", "结束", "带回", "笔录", "移交"]) else "未充分说明下一步安排或阶段收尾。",
            "evidence": _sample_evidence(user_evidence),
        },
    }

    reviews = []
    for dimension, focus in COMMON_DIMENSIONS:
        llm_item = llm_reviews.get(dimension) or {}
        base_ratio = seed[dimension]["ratio"]
        if llm_item:
            llm_full = float(llm_item.get("full_score") or 0)
            llm_score = float(llm_item.get("score") or -1)
            if llm_full > 0 and llm_score >= 0:
                ratio = max(0.0, min(1.0, llm_score / llm_full))
            else:
                llm_ratio = _level_ratio(llm_item.get("level"))
                ratio = base_ratio * 0.35 + llm_ratio * 0.65
        else:
            ratio = base_ratio
        ratio = min(ratio, _common_ratio_cap_by_points(dimension, point_results))
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
                "llm_score": llm_item.get("score") if llm_item else None,
                "llm_full_score": llm_item.get("full_score") if llm_item else None,
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
    required_rate = (sum(_point_completion_ratio(point) for point in required_points) / len(required_points)) if required_points else 1.0
    if required_rate < 0.35:
        caps.append({"type": "required_completion", "cap": 58, "reason": "必考点完成度低于 35%"})
    elif required_rate < 0.55:
        caps.append({"type": "required_completion", "cap": 70, "reason": "必考点完成度低于 55%"})
    elif required_rate < 0.75:
        caps.append({"type": "required_completion", "cap": 82, "reason": "必考点完成度低于 75%"})

    for flag in red_flags:
        caps.append({"type": "red_flag", "cap": int(flag.get("cap") or 100), "reason": flag.get("label")})

    final_cap = min([int(item["cap"]) for item in caps], default=100)
    return {
        "turn_count": turn_count,
        "required_total": len(required_points),
        "required_hit": len(required_hit),
        "required_rate": required_rate,
        "required_completion_rate": required_rate,
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
    common_reviews = _common_dimension_reviews(llm_report, student_lines, msgs, rule_checks, point_results)
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
        llm_score = point.get("llm_score")
        llm_full_score = int(point.get("llm_full_score") or full_score or 0)
        if isinstance(llm_score, (int, float)) and llm_full_score > 0:
            score = max(0, min(llm_full_score, _round_score(float(llm_score))))
            ratio = score / llm_full_score
            full_score = llm_full_score
        else:
            ratio = _point_completion_ratio(point)
            score = _round_score(full_score * ratio)
        running_total += score
        enriched = {
            **point,
            "difficulty_level": point_weight.get("difficulty_level") or _infer_point_difficulty(point)[0],
            "difficulty_factor": point_weight.get("difficulty_factor") or _infer_point_difficulty(point)[1],
            "score_share": share,
            "weighted_score": score,
            "full_score": full_score,
            "completion_ratio": ratio,
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
                "score_ratio": ratio,
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

    report = {
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
                "required_rate": (sum(_point_completion_ratio(point) for point in required_points) / len(required_points)) if required_points else 1.0,
                "overall_total": len(enriched_points),
                "overall_hit": len(all_hit),
                "overall_rate": (sum(_point_completion_ratio(point) for point in enriched_points) / len(enriched_points)) if enriched_points else 1.0,
                "total_weight": total_weight,
                "earned_weight": earned_weight,
                "weight_rate": (earned_weight / total_weight) if total_weight else 1.0,
            },
        },
    }
    return enforce_final_score_policy(report, policy_source="build_adaptive_report")


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


def _valid_student_or_action_evidence(values: List[Any]) -> List[str]:
    weak_replies = {"是", "是的", "不是", "好的", "好", "嗯", "哦", "没有", "对", "不对", "知道", "明白"}
    result: List[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if not text:
            continue
        if text.startswith(("AI角色:", "AI角色：", "AI:", "AI：", "助手:", "助手：")):
            continue
        is_prefixed_signal = text.startswith(("学员:", "学员：", "用户:", "用户：", "user:", "user：", "动作:", "动作："))
        clean = re.sub(r"^(学员|用户|user|动作)[:：]\s*", "", text, flags=re.I).strip()
        if clean in weak_replies or len(clean) < 3:
            continue
        if is_prefixed_signal:
            result.append(text)
    return _dedupe_strings(result)


def _is_ai_evidence(text: Any) -> bool:
    value = str(text or "").strip()
    return value.startswith(("AI角色:", "AI角色：", "AI:", "AI：", "助手:", "助手：", "assistant:", "assistant："))


def _valid_paired_scoring_evidence(values: List[Any]) -> List[str]:
    items = [str(value or "").strip() for value in values or [] if str(value or "").strip()]
    student_or_action = _valid_student_or_action_evidence(items)
    ai_items = _dedupe_strings([item for item in items if _is_ai_evidence(item)])
    if not student_or_action:
        return []
    return _dedupe_strings(student_or_action + ai_items)


def _has_paired_ai_feedback(values: List[Any]) -> bool:
    paired = _valid_paired_scoring_evidence(values)
    return bool(paired) and any(_is_ai_evidence(item) for item in paired)


def _resolve_point_status(runtime_point: dict, llm_point: dict) -> str:
    runtime_status = str(runtime_point.get("status") or "").strip()
    llm_status = str(llm_point.get("status") or "").strip()
    runtime_rank = _STATUS_RANK.get(runtime_status, 0)
    llm_rank = _STATUS_RANK.get(llm_status, 0)

    runtime_evidence = (runtime_point.get("evidence") or []) + (runtime_point.get("context_evidence") or [])
    llm_evidence = (llm_point.get("evidence") or []) + (llm_point.get("context_evidence") or [])
    runtime_has_action = bool(runtime_point.get("linked_actions_completed"))
    runtime_has_pair = _has_paired_ai_feedback(runtime_evidence)
    llm_has_pair = _has_paired_ai_feedback(llm_evidence)

    if runtime_rank >= 3 and (runtime_has_pair or runtime_has_action):
        return "hit"
    if runtime_rank == 2:
        return "partial"

    llm_valid_evidence = _valid_paired_scoring_evidence(llm_evidence)
    if llm_rank >= 3 and llm_has_pair:
        return "hit"
    if llm_rank == 2 and llm_valid_evidence:
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


def _strip_requirement_prefix(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = re.sub(r"^(学员应|应当|需要|需|具体要求|怎样算完成|完成标准|考察点)[:：\s]*", "", value)
    value = re.sub(r"^(学员应完成|具体要求|怎样算完成)[:：\s]*", "", value)
    value = re.sub(r"^(目标|要求)[:：\s]*", "", value)
    return value.strip(" 　\t\r\n，。；;：:")


def _compact_text(text: Any, *, limit: int = 48, keep_sentences: int = 1) -> str:
    value = _strip_requirement_prefix(text)
    if not value:
        return ""
    parts = [part.strip() for part in re.split(r"[。！？；;\n]+", value) if part.strip()]
    if parts:
        value = "。".join(parts[:keep_sentences])
    value = re.sub(r"\s+", "", value)
    if len(value) <= limit:
        return value
    return f"{value[: max(1, limit - 1)]}…"


def _split_bullets(text: Any, *, limit: int = 3) -> List[str]:
    value = str(text or "").strip()
    if not value:
        return []
    parts = [part.strip(" \t\r\n，。；;:：") for part in re.split(r"[。！？；;\n]+", value) if part.strip()]
    if not parts:
        parts = [value]
    normalized: List[str] = []
    seen = set()
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        normalized.append(part)
        if len(normalized) >= limit:
            break
    return normalized


def _classify_evidence_item(text: Any) -> dict:
    value = str(text or "").strip()
    prefix = value[:16]
    if prefix.startswith(("学员:", "学员：", "用户:", "用户：", "user:", "user：")):
        kind = "student_utterance"
    elif prefix.startswith(("AI:", "AI：", "助手:", "助手：", "assistant:", "assistant：")):
        kind = "assistant_reply"
    elif "动作" in prefix or value.startswith(("动作:", "动作：", "日志:", "日志：")):
        kind = "action_log"
    elif prefix.startswith(("上下文:", "上下文：")):
        kind = "context"
    else:
        kind = "text"
    return {"kind": kind, "text": value}


def _normalize_media_refs(point: dict) -> List[dict]:
    refs: List[dict] = []
    for key in ("media_refs", "media_evidence", "artifacts"):
        items = point.get(key)
        if not items:
            continue
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                refs.append({k: item.get(k) for k in ("id", "artifact_type", "file_url", "mime_type", "duration_seconds", "label") if item.get(k) is not None})
            else:
                refs.append({"label": str(item).strip()})
    return refs


def _build_assessment_point_display(point: dict) -> dict:
    full_text = str(
        point.get("content")
        or point.get("requirement")
        or point.get("description")
        or point.get("target")
        or point.get("assessment_target")
        or point.get("goal")
        or "",
    ).strip()
    feedback = str(point.get("feedback") or "").strip()
    summary_source = feedback or full_text
    short_label = _compact_text(point.get("label") or full_text, limit=20) or str(point.get("label") or "未命名考察点").strip()
    summary = _compact_text(summary_source, limit=48, keep_sentences=2) or short_label
    evidence = [_classify_evidence_item(item) for item in _dedupe_strings(point.get("evidence") or [])]
    context_evidence = [_classify_evidence_item(item) for item in _dedupe_strings(point.get("context_evidence") or [])]
    return {
        "short_label": short_label,
        "summary": summary,
        "full_text": full_text,
        "evidence_items": evidence,
        "context_evidence_items": context_evidence,
        "media_refs": _normalize_media_refs(point),
        "feedback_items": _split_bullets(feedback, limit=3),
    }


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
        status = _resolve_point_status(runtime_point, llm_point)
        runtime_scoring_source = (runtime_point.get("evidence") or []) + (runtime_point.get("context_evidence") or [])
        llm_scoring_source = (llm_point.get("evidence") or []) + (llm_point.get("context_evidence") or [])
        runtime_evidence = _valid_paired_scoring_evidence(runtime_scoring_source)
        llm_evidence = _valid_paired_scoring_evidence(llm_scoring_source)
        evidence = _dedupe_strings(runtime_evidence + llm_evidence)[:4]
        context_evidence = _dedupe_strings(
            [
                item
                for item in (runtime_point.get("context_evidence") or []) + (llm_point.get("context_evidence") or [])
                if item not in evidence
            ]
        )[:3]
        feedback = str(llm_point.get("reason") or llm_point.get("feedback") or runtime_point.get("feedback") or "").strip()
        if not feedback:
            feedback = _default_point_feedback({"status": status, "evidence": evidence})
        if status == "missed":
            feedback = runtime_point.get("feedback") or "未发现学员主动完成该考察点的有效发言或动作。"
        llm_full_score = int(llm_point.get("full_score") or 0)
        llm_score = int(llm_point.get("score") or -1)
        llm_ratio = llm_point.get("score_ratio")
        if llm_full_score > 0 and llm_score >= 0:
            llm_score = max(0, min(llm_full_score, llm_score))
            completion_ratio = max(0.0, min(1.0, llm_score / llm_full_score))
        else:
            completion_ratio = _point_completion_ratio({**runtime_point, **llm_point, "status": status, "evidence": evidence})
            llm_score = _score_from_point({**runtime_point, **llm_point, "status": status, "evidence": evidence}, weight)
        if llm_ratio is not None:
            try:
                completion_ratio = max(0.0, min(1.0, float(llm_ratio)))
            except (TypeError, ValueError):
                pass
        display = _build_assessment_point_display(
            {
                **req_row,
                **runtime_point,
                **llm_point,
                "label": label,
                "content": str(req_row.get("content") or llm_point.get("content") or "").strip(),
                "feedback": feedback,
                "evidence": evidence,
                "context_evidence": context_evidence,
            }
        )
        score = llm_score if llm_full_score > 0 and llm_score >= 0 else _score_from_point({**runtime_point, **llm_point, "status": status, "evidence": evidence, "completion_ratio": completion_ratio}, weight)
        if llm_full_score > 0:
            score = min(score, llm_full_score)
        if status == "missed":
            score = 0
            completion_ratio = 0.0
        elif status == "partial" and llm_full_score > 0:
            score = min(score, int(round(llm_full_score * 0.85)))
            completion_ratio = min(completion_ratio, score / llm_full_score if llm_full_score else completion_ratio)
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
                "score": score,
                "llm_score": llm_score if llm_full_score > 0 else None,
                "llm_full_score": llm_full_score or None,
                "completion_ratio": completion_ratio,
                "evidence": evidence,
                "context_evidence": context_evidence,
                "feedback": feedback,
                "knowledge_refs": _dedupe_strings(runtime_point.get("knowledge_refs") or req_row.get("knowledge_refs") or []),
                **display,
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
    existing_header = _report_header_from_payload(report)
    created_at = getattr(session, "created_at", None)
    started_at = (
        getattr(session, "training_started_at", None)
        or _parse_report_datetime(existing_header.get("training_started_at"))
        or _parse_report_datetime(existing_header.get("created_at"))
        or created_at
    )
    finished_at = (
        getattr(session, "training_finished_at", None)
        or _parse_report_datetime(existing_header.get("training_finished_at"))
        or _parse_report_datetime(existing_header.get("finished_at"))
        or _parse_report_datetime(report.get("evaluated_at"))
        or started_at
        or datetime.utcnow()
    )
    duration_seconds = None
    if started_at:
        try:
            duration_seconds = max(0, int((finished_at - started_at).total_seconds()))
        except Exception:
            duration_seconds = None
    if duration_seconds is None:
        duration_seconds = existing_header.get("duration_seconds")
    report["grade_level"] = compute_grade_level(total_score)
    report["total_score"] = total_score
    report["evaluated_at"] = _format_report_datetime(finished_at)

    if "evaluation_meta" not in report:
        report["evaluation_meta"] = {}
    report["evaluation_meta"]["report_header"] = {
        "session_id": session.id,
        "case_title": str(getattr(case, "title", "") or "未知案件").strip() or "未知案件",
        "case_type": str(getattr(case, "case_type", "") or "").strip() or "其他",
        "scene_name": str(getattr(scene, "name", "") or "训练场景").strip() or "训练场景",
        "scene_type": report["evaluation_meta"].get("scene_type") or infer_scene_type(scene) if scene else "通用",
        "dialogue_turns": len(student_lines),
        "created_at": _format_report_datetime(created_at),
        "training_started_at": _format_report_datetime(started_at),
        "finished_at": _format_report_datetime(finished_at),
        "training_finished_at": _format_report_datetime(finished_at),
        "duration_seconds": duration_seconds,
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
        cached_report = json.loads(session.evaluation_result)
        if not is_current_evaluation_report(cached_report):
            force_recompute = True
        else:
            return cached_report

    if not force_recompute and session.status == "finished" and session.evaluation_result:
        cached_report = json.loads(session.evaluation_result)
        scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
        msgs = filter_internal_prompt_messages(
            db.query(models.Message)
            .filter(models.Message.session_id == session_id)
            .order_by(models.Message.created_at.asc(), models.Message.id.asc())
            .all()
        )
        _, student_lines = format_dialogue(msgs)
        header = cached_report.get("evaluation_meta", {}).get("report_header", {}) if isinstance(cached_report, dict) else {}
        if (
            not isinstance(header, dict)
            or not header.get("finished_at")
            or "duration_seconds" not in header
            or "training_started_at" not in header
            or "training_finished_at" not in header
        ):
            cached_report = finalize_evaluation_report(cached_report, session, scene, case, student_lines)
        next_report_json = json.dumps(cached_report, ensure_ascii=False)
        if next_report_json != session.evaluation_result:
            session.evaluation_result = next_report_json
            db.commit()
        return cached_report

    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
    msgs = filter_internal_prompt_messages(
        db.query(models.Message)
        .filter(models.Message.session_id == session_id)
        .order_by(models.Message.created_at.asc(), models.Message.id.asc())
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
    scoring_template = _render_scoring_template(calculate_adaptive_weighting(runtime_point_results), requirement_rows, scene_type)

    full_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        scene_info=scene_info,
        scene_rubric=scene_rubric,
        rule_check_summary=rule_check_summary,
        case_info=case_info,
        dialogue_history=dialogue_history or "暂无对话内容",
        assessment_requirements=assessment_requirements,
        knowledge_base=knowledge_base,
        scoring_template=scoring_template,
    )

    try:
        response = create_json_chat_completion(
            model=get_chat_model(),
            messages=[
                {"role": "system", "content": "你是一名公正、严格、专业的警务训练教官，必须输出合法 JSON。"},
                {"role": "user", "content": full_prompt},
            ],
            max_tokens=4200,
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
        report["evaluation_meta"]["scoring_source"] = "llm_structured_scoring"
        report["evaluation_meta"]["evaluation_run_id"] = f"{session_id}-{datetime.utcnow().isoformat(timespec='microseconds')}"
        report["evaluation_meta"]["force_recompute"] = bool(force_recompute)
        if isinstance(llm_report.get("evaluation_meta"), dict):
            report["evaluation_meta"]["llm_fallback"] = bool(llm_report["evaluation_meta"].get("llm_fallback", False))
            if llm_report["evaluation_meta"].get("raw_summary"):
                report["evaluation_meta"]["raw_summary"] = llm_report["evaluation_meta"]["raw_summary"]
        report = enforce_final_score_policy(report, policy_source="evaluate_session_success")
        report = finalize_evaluation_report(report, session, scene, case, student_lines)
        report_json = json.dumps(report, ensure_ascii=False)
        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()

        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        llm_report = {
            "common_reviews": [],
            "assessment_check_results": [],
            "strengths": [],
            "improvements": [],
            "suggestions": "模型评估暂不可用，系统已依据运行时考察点、动作记录和规则校验生成兜底报告。",
            "evaluation_meta": {"llm_fallback": True, "raw_summary": str(e)[:220]},
        }
        knowledge_docs = _knowledge_index(structured_assessment["knowledge_ref_ids"])
        merged_points = merge_assessment_point_results(runtime_point_results, [], requirement_rows)
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
        report["evaluation_meta"]["scoring_source"] = "fallback_rule_scoring_after_llm_error"
        report["evaluation_meta"]["evaluation_run_id"] = f"{session_id}-{datetime.utcnow().isoformat(timespec='microseconds')}"
        report["evaluation_meta"]["force_recompute"] = bool(force_recompute)
        report["evaluation_meta"]["llm_fallback"] = True
        report["evaluation_meta"]["raw_summary"] = str(e)[:220]
        report = enforce_final_score_policy(report, policy_source="evaluate_session_fallback")
        report = finalize_evaluation_report(report, session, scene, case, student_lines)
        report_json = json.dumps(report, ensure_ascii=False)
        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()
        return report
