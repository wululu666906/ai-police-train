import json
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

import models
from .llm_provider import create_json_chat_completion, extract_json_payload, extract_message_text, get_chat_model
from .persona_engine import build_persona_profile
from .rag_service import rag_service
from .role_resolver import resolve_scene_role
from .stage_config_service import normalize_stages
from .training_runtime_service import collect_stage_progress, load_runtime_state

DIMENSIONS = [
    ("执法语言规范性", 25),
    ("执法流程完整性", 25),
    ("法律依据正确性", 20),
    ("情绪控制能力", 15),
    ("信息获取效率", 15),
]

GRADE_LEVELS: List[Tuple[int, str]] = [
    (90, "卓越"),
    (80, "优秀"),
    (70, "良好"),
    (60, "合格"),
    (0, "需改进"),
]

ASSESSMENT_WEIGHTED_DIMENSIONS = {
    "执法流程完整性": 0.55,
    "信息获取效率": 0.45,
}

_STATUS_RANK = {"hit": 3, "partial": 2, "missed": 1}

SCENE_RUBRICS = {
    "接警": [
        "优先确认地点、身份、伤情、风险和是否仍在持续。",
        "接警阶段要体现快速定位关键事实的能力，而不是泛泛安抚。",
        "如果未核实时间、地点、伤情或现场风险，应在流程完整性和信息获取效率上扣分。",
    ],
    "现场": [
        "要体现身份核实、现场保护、风险控制和基础证据意识。",
        "如果只聊天不处置，或忽略现场动作，应在流程完整性和法律依据正确性上扣分。",
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
你是一名严格、公正、专业的警务训练评估官，需要根据完整对话、动作执行和“考察点要求表”逐条核查结果给出结构化评分。

评分维度（总分 100）：
1. 执法语言规范性（25）
2. 执法流程完整性（25）
3. 法律依据正确性（20）
4. 情绪控制能力（15）
5. 信息获取效率（15）

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

评分锚点（必须遵守，不得随意给高分）：
- 90-100：关键流程完整、追问连续、无明显规范问题，且大部分必考点已覆盖。
- 75-89：主体流程到位，但存在 1-2 项明显遗漏或表述不够规范。
- 60-74：能维持基本沟通，但流程缺口较多，或必考点完成不足一半。
- 40-59：仅完成少量基础动作，关键事实、风险或身份核实明显不足。
- 0-39：有效轮次过少、对话偏离目标，或出现明显不规范/激化冲突表达。

评分校准规则：
- 考察点命中率与总分强相关：必考点命中率 < 35% 时总分上限不超过 58；命中率 < 55% 时不超过 70；命中率 < 75% 时不超过 82。
- "执法流程完整性"和"信息获取效率"两个维度的得分受考察点完成率校准：完成率越低，这两个维度的得分上限越低。
- 学员有效发言轮次 ≤ 1 轮时总分上限为 55；≤ 2 轮时上限为 68；≤ 3 轮时上限为 78。

动作执行评估：
- 训练日志中的"动作"行（以"动作："开头）代表学员完成的现场操作（如开启执法记录仪、拍照取证、分离双方等）。
- 动作完成情况应纳入"执法流程完整性"评分：动作执行充分的学员应在该维度获得加分；关键动作未做的应扣分。
- 如果对话历史中有明确的动作检查/验证动作完成的表述，应在 reason 中引用。

参考知识引用要求：
- 评分时必须尽量引用"参考知识"中的条款作为法律依据，并在 reason 中明示（如"根据参考知识第X条…"）。
- 如果知识库中的内容与学员的行为直接相关，必须在 assessment_check_results 的 evidence 或 reason 中引用。

学员主动性判断（不要被 AI 角色牵着走）：
- 区分"学员主动追问获知的信息"和"AI 角色主动告知的信息"。如果信息是 AI 角色主动交代而非学员问出的，不应作为学员的信息获取加分。
- 学员的每个追问轮次应带来新增信息；如果多轮反复询问同一件事而无新进展，应在"信息获取效率"上扣分。
- 判断依据：观察对话中谁在主导信息流动——学员提问→AI角色回答→学员追问问细节，这是主动；AI角色长篇陈述→学员仅应答，这是被动。

输出要求：
1. 每个维度都必须给出 score、full_score、reason；各维度 score 之和必须等于 total_score。
2. reason 必须引用具体轮次、具体发言或具体动作，并说明扣分依据（如”学员第3轮未核实地点，扣 X 分”）。引用格式参考：「学员第N轮」或「动作：XXX」。
3. assessment_check_results 必须与”考察点要求表”逐条对应，不得遗漏 id。判定 hit/partial/missed 时须结合对话原文和动作日志给出明确依据。
4. strengths 是学员表现中的亮点（各 2-4 条），improvements 是具体存在不足的维度或动作（各 2-4 条），improvements 应直接指出缺了什么、哪一步没做到，而不是笼统建议。
5. 不要因为 AI 角色说得多就高分，要看学员是否通过连续追问和动作推进拿到信息。
6. 只输出合法 JSON。

注意：以下输出模板中的 score、total_score、strengths、improvements、suggestions 均为占位示例，数值 20、80 等都是随意写的例子，可能与实际评分差异很大，请完全基于对话评分，不要被示例数值带偏。status 只能取 “hit”、”partial”、”missed” 三者之一，不得使用其他值。

【重要】输出模板使用的是合法 JSON 格式，请使用英文双引号（”），不要使用中文引号（“ ”），否则解析会失败。

严格输出 JSON：
{{
  “scores”: [
    {{
      “dimension”: “执法语言规范性”,
      “score”: 20,
      “full_score”: 25,
      “reason”: “学员第 2 轮使用了规范化告知话术，但第 5 轮出现轻微不当用语，扣 2 分”
    }},
    {{
      “dimension”: “执法流程完整性”,
      “score”: 18,
      “full_score”: 25,
      “reason”: “学员完成了身份核实和现场询问，但未落实现场保护措施，扣 5 分”
    }},
    {{
      “dimension”: “法律依据正确性”,
      “score”: 16,
      “full_score”: 20,
      “reason”: “学员引用了相关法律条款，但适用场景不完全匹配，扣 2 分”
    }},
    {{
      “dimension”: “情绪控制能力”,
      “score”: 13,
      “full_score”: 15,
      “reason”: “面对当事人激动情绪，学员保持了克制，未出现对抗性表达”
    }},
    {{
      “dimension”: “信息获取效率”,
      “score”: 11,
      “full_score”: 15,
      “reason”: “学员获取了地点和人员信息，但对关键时间线的追问不足，扣 2 分”
    }}
  ],
  “total_score”: 78,
  “assessment_check_results”: [
    {{
      “id”: “ap_001”,
      “label”: “核实报警人身份”,
      “content”: “学员应主动询问报警人姓名、身份及与事件的关系”,
      “status”: “hit”,
      “evidence”: [“学员: 请问您怎么称呼？”, “学员: 您和当事人是什么关系？”],
      “reason”: “学员在第 1 轮和第 3 轮分别核实了身份和关系，符合要求”
    }},
    {{
      “id”: “ap_002”,
      “label”: “确认现场风险”,
      “content”: “学员应询问是否存在伤人、危险物品或需紧急救助的情况”,
      “status”: “missed”,
      “evidence”: [],
      “reason”: “整段对话未涉及现场风险询问，判定未命中”
    }}
  ],
  “strengths”: [“学员在第 1 轮即主动表明身份并出示证件”, “整体提问语气规范、克制”],
  “improvements”: [“学员未询问现场风险情况，存在安全隐患”, “对当事人前后陈述的矛盾缺乏追问”],
  “suggestions”: “建议在后续训练中：(1) 每次处置前先系统梳理需要覆盖的必查要素清单；(2) 使用 SPORTS 框架（场景-人员-目标-风险-策略-收尾）组织问询顺序；(3) 对当事人陈述中的时间或逻辑矛盾及时追问压实。”
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
        "执法语言规范性": 0,
        "执法流程完整性": 0,
        "法律依据正确性": 0,
        "情绪控制能力": 0,
        "信息获取效率": 0,
    }

    if len(student_lines) < 2:
        findings.append(
            {
                "level": "major",
                "dimension": "信息获取效率",
                "message": "学员有效发言轮次过少，难以完成完整处置与信息收集。",
            }
        )
        deductions["信息获取效率"] += 4
        deductions["执法流程完整性"] += 3

    bad_phrases = ["闭嘴", "老实点", "快说", "少废话", "废话", "给我老实交代", "别装了"]
    if contains_any(joined, bad_phrases):
        findings.append(
            {
                "level": "major",
                "dimension": "执法语言规范性",
                "message": "出现疑似不规范、带压迫性或激化冲突的表达。",
            }
        )
        deductions["执法语言规范性"] += 8
        deductions["情绪控制能力"] += 3

    if scene_type == "接警":
        if not contains_any(joined, ["哪里", "地址", "地点", "具体位置", "几号楼", "房间", "案发地点"]):
            findings.append(
                {
                    "level": "major",
                    "dimension": "执法流程完整性",
                    "message": "接警阶段未明确确认案发地点。",
                }
            )
            deductions["执法流程完整性"] += 6
            deductions["信息获取效率"] += 3
        if not contains_any(joined, ["什么时候", "几点", "刚刚", "时间"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": "信息获取效率",
                    "message": "接警阶段未及时确认事件发生时间。",
                }
            )
            deductions["信息获取效率"] += 2
        if not contains_any(joined, ["受伤", "危险", "还在现场", "120", "是否安全"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": "法律依据正确性",
                    "message": "接警阶段未充分确认现场风险和救助需求。",
                }
            )
            deductions["法律依据正确性"] += 3

    if scene_type == "现场":
        if not contains_any(joined, ["姓名", "你是谁", "和对方什么关系", "身份", "叫什么"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": "执法流程完整性",
                    "message": "现场问询阶段未充分核实身份和人物关系。",
                }
            )
            deductions["执法流程完整性"] += 3
        if not contains_any(joined, ["现场", "不要破坏", "保持原状", "先别动", "证据"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": "法律依据正确性",
                    "message": "现场处置中未体现明显的现场保护或证据意识。",
                }
            )
            deductions["法律依据正确性"] += 4

    if scene_type == "审讯":
        if not contains_any(joined, ["什么时候", "几点", "当时", "时间线", "案发时"]):
            findings.append(
                {
                    "level": "major",
                    "dimension": "执法流程完整性",
                    "message": "审讯或讯问中未围绕案发时间线有效展开。",
                }
            )
            deductions["执法流程完整性"] += 5
        if not contains_any(joined, ["为什么", "动机", "关系", "证据", "监控", "不在场"]):
            findings.append(
                {
                    "level": "minor",
                    "dimension": "信息获取效率",
                    "message": "审讯中对动机、证据或矛盾点追问不足。",
                }
            )
            deductions["信息获取效率"] += 3

    if role and not getattr(role, "name", ""):
        findings.append(
            {
                "level": "minor",
                "dimension": "执法流程完整性",
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


def normalize_llm_report(report: Dict[str, Any]) -> Dict[str, Any]:
    score_map = {item["dimension"]: item for item in report.get("scores", []) if "dimension" in item}
    normalized_scores = []
    total = 0

    for dimension, full_score in DIMENSIONS:
        item = score_map.get(dimension, {})
        score = item.get("score", full_score)
        reason = item.get("reason", "未提供明确理由。")
        score = max(0, min(full_score, int(score)))
        normalized_scores.append(
            {
                "dimension": dimension,
                "score": score,
                "full_score": full_score,
                "reason": reason,
            }
        )
        total += score

    report["scores"] = normalized_scores
    report["total_score"] = total
    report["strengths"] = report.get("strengths") or []
    report["improvements"] = report.get("improvements") or []
    report["suggestions"] = report.get("suggestions") or "建议继续结合规范话术、场景流程和追问技巧反复训练。"
    return report


def apply_rule_adjustments(report: Dict[str, Any], rule_checks: Dict[str, Any]) -> Dict[str, Any]:
    deductions = rule_checks["deductions"]
    for item in report["scores"]:
        deduct = deductions.get(item["dimension"], 0)
        if deduct > 0:
            item["score"] = max(0, item["score"] - deduct)
            item["reason"] = f"{item['reason']} 规则校验补充：额外扣减 {deduct} 分。"

    report["total_score"] = sum(item["score"] for item in report["scores"])

    if rule_checks["findings"]:
        extra_improvements = [finding["message"] for finding in rule_checks["findings"]]
        report["improvements"] = list(dict.fromkeys((report.get("improvements") or []) + extra_improvements))

    if "evaluation_meta" not in report:
        report["evaluation_meta"] = {}
    report["evaluation_meta"]["rule_findings"] = rule_checks["findings"]
    report["evaluation_meta"]["hybrid_mode"] = True
    report["evaluation_meta"]["model"] = get_chat_model()
    report["evaluation_meta"]["technique"] = ["RAG", "rule-based checks", "LLM structured scoring"]
    return report


def calibrate_report(report: Dict[str, Any], student_lines: List[str], scene_type: str) -> Dict[str, Any]:
    turn_count = len(student_lines)
    joined = "\n".join(student_lines)

    total_cap = 100
    if turn_count <= 1:
        total_cap = 55
    elif turn_count == 2:
        total_cap = 68
    elif turn_count == 3:
        total_cap = 78

    if report["total_score"] > total_cap:
        overflow = report["total_score"] - total_cap
        for item in sorted(report["scores"], key=lambda x: x["score"], reverse=True):
            if overflow <= 0:
                break
            reducible = min(max(item["score"] - max(0, item["full_score"] // 3), 0), overflow)
            if reducible <= 0:
                continue
            item["score"] -= reducible
            item["reason"] = f"{item['reason']} 训练轮次较少，综合评分已做上限校准。"
            overflow -= reducible
        report["total_score"] = sum(item["score"] for item in report["scores"])

    if len(report.get("strengths") or []) < 2:
        strengths = report.get("strengths") or []
        if contains_any(joined, ["请", "麻烦", "您", "说明", "有没有", "是否"]):
            strengths.append("提问语气总体保持克制，具备基础执法沟通意识。")
        if turn_count >= 2:
            strengths.append("能够围绕现场情况继续追问，而不是完全停留在单句试探。")
        report["strengths"] = list(dict.fromkeys(strengths))[:3]

    if len(report.get("improvements") or []) < 2:
        improvements = report.get("improvements") or []
        if scene_type == "接警":
            improvements.append("接警阶段应优先锁定地点、时间、伤情和风险，再展开后续追问。")
        elif scene_type == "现场":
            improvements.append("现场问询时要同步兼顾身份核实、风险控制和证据保护。")
        else:
            improvements.append("后续问询应进一步围绕时间线、人物关系和矛盾点持续追问。")
        if turn_count <= 2:
            improvements.append("当前有效对话轮次偏少，建议至少完成数轮问答后再结束训练。")
        report["improvements"] = list(dict.fromkeys(improvements))[:4]

    if not report.get("suggestions") or len(str(report.get("suggestions")).strip()) < 12:
        report["suggestions"] = "建议先按场景目标完成身份核实、关键事实确认和风险判断，再逐步扩大追问范围，减少无效发问。"

    if "evaluation_meta" not in report:
        report["evaluation_meta"] = {}
    report["evaluation_meta"]["turn_count"] = turn_count
    report["evaluation_meta"]["score_cap"] = total_cap
    return report


def build_fallback_report(raw_content: str, student_lines: List[str], scene_type: str) -> Dict[str, Any]:
    report = normalize_llm_report(
        {
            "scores": [],
            "strengths": [],
            "improvements": [],
            "suggestions": str(raw_content or "").strip()[:220] or "建议继续围绕时间线、身份核实和关键事实确认展开训练。",
            "evaluation_meta": {
                "llm_fallback": True,
                "scene_type": scene_type,
            },
        }
    )
    report = calibrate_report(report, student_lines, scene_type)
    report["evaluation_meta"]["llm_fallback"] = True
    if str(raw_content or "").strip():
        report["evaluation_meta"]["raw_summary"] = str(raw_content).strip()[:220]
    return report


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
    req_map = {str(row.get("id") or "").strip(): row for row in requirement_rows if str(row.get("id") or "").strip()}
    runtime_map = {str(point.get("id") or "").strip(): point for point in runtime_points if str(point.get("id") or "").strip()}
    llm_map = {str(point.get("id") or "").strip(): point for point in llm_points if str(point.get("id") or "").strip()}
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
        weight = max(1, int(runtime_point.get("weight") or req_row.get("weight") or 10))
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
                "category": str(runtime_point.get("category") or "procedure").strip() or "procedure",
                "required": bool(runtime_point.get("required", req_row.get("required", True))),
                "weight": weight,
                "status": status,
                "score": _score_from_point_status(status, weight),
                "evidence": evidence,
                "feedback": feedback,
                "knowledge_refs": _dedupe_strings(runtime_point.get("knowledge_refs") or req_row.get("knowledge_refs") or []),
            }
        )
    return merged


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


def apply_assessment_driven_scoring(report: Dict[str, Any], point_results: List[dict], action_results: List[dict]) -> Dict[str, Any]:
    required_points = [p for p in point_results if str(p.get("label") or "").strip()]
    required_hit = [p for p in required_points if p.get("status") == "hit"]
    all_points = [p for p in point_results if str(p.get("label") or "").strip()]
    all_hit = [p for p in all_points if p.get("status") == "hit"]

    required_rate = (len(required_hit) / len(required_points)) if required_points else 1.0
    overall_rate = (len(all_hit) / len(all_points)) if all_points else 1.0
    total_weight = sum(max(1, int(p.get("weight") or 10)) for p in all_points)
    earned_weight = sum(int(p.get("score") or 0) for p in all_points)
    weight_rate = (earned_weight / total_weight) if total_weight else 1.0

    cap = 100
    bonus = 0
    if required_rate < 0.35:
        cap = 58
    elif required_rate < 0.55:
        cap = 70
    elif required_rate < 0.75:
        cap = 82

    if required_rate >= 0.85 and overall_rate >= 0.75 and len(action_results) > 0:
        bonus = 3
    if required_rate >= 0.95 and overall_rate >= 0.85:
        bonus = 5

    for item in report.get("scores") or []:
        dimension = item.get("dimension")
        if dimension not in ASSESSMENT_WEIGHTED_DIMENSIONS:
            continue
        full_score = int(item.get("full_score") or 0)
        ceiling = int(full_score * (0.25 + 0.75 * weight_rate) * (0.55 + 0.45 * required_rate))
        ceiling = max(0, min(full_score, ceiling))
        if int(item.get("score") or 0) > ceiling:
            gap = int(item.get("score") or 0) - ceiling
            item["score"] = ceiling
            item["reason"] = (
                f"{item.get('reason', '')} 考察点加权完成率 {weight_rate:.0%}，"
                f"必考命中率 {required_rate:.0%}，本项上限校准扣减 {gap} 分。"
            ).strip()

    report["total_score"] = max(0, min(100, min(sum(int(item.get("score") or 0) for item in report.get("scores") or []), cap) + bonus))
    report = reconcile_dimension_scores(report)

    if "evaluation_meta" not in report:
        report["evaluation_meta"] = {}
    report["evaluation_meta"]["assessment_completion"] = {
        "required_total": len(required_points),
        "required_hit": len(required_hit),
        "required_rate": required_rate,
        "overall_total": len(all_points),
        "overall_hit": len(all_hit),
        "overall_rate": overall_rate,
        "total_weight": total_weight,
        "earned_weight": earned_weight,
        "weight_rate": weight_rate,
        "score_cap": cap,
        "score_bonus": bonus,
    }
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
                    "weight": max(1, int(point.get("weight", 10) or 10)),
                    "required": bool(point.get("required", True)),
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

    stored_progress = runtime_state.get("assessment_progress") or {}
    if isinstance(stored_progress, dict):
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
        report = extract_json_payload(raw_content)
        if not isinstance(report, dict):
            report = build_fallback_report(raw_content, student_lines, scene_type)

        report = normalize_llm_report(report)
        report = apply_rule_adjustments(report, rule_checks)
        report = calibrate_report(report, student_lines, scene_type)
        check_results = report.get("assessment_check_results") if isinstance(report.get("assessment_check_results"), list) else []
        knowledge_docs = _knowledge_index(structured_assessment["knowledge_ref_ids"])
        merged_points = merge_assessment_point_results(runtime_point_results, check_results, requirement_rows)
        merged_points = _attach_knowledge_titles(merged_points, knowledge_docs)
        report["assessment_point_results"] = merged_points
        report = _enrich_report_from_structured_evidence(report, merged_points, action_results)
        report = apply_assessment_driven_scoring(report, merged_points, action_results)
        report["action_results"] = action_results
        report["closure_summary"] = structured_assessment["closure_summary"]

        if "evaluation_meta" not in report:
            report["evaluation_meta"] = {}
        report["evaluation_meta"]["scene_type"] = scene_type
        report["evaluation_meta"]["knowledge_hits"] = knowledge
        report["evaluation_meta"]["stage_gap_summary"] = structured_assessment["stage_gap_summary"] or build_stage_gap_summary(scene, student_lines)
        report = finalize_evaluation_report(report, session, scene, case, student_lines)

        report_json = json.dumps(report, ensure_ascii=False)
        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()

        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {"error": str(e)}
