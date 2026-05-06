import json
import os
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

import models
from .rag_service import rag_service
from .role_resolver import resolve_scene_role

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)

DIMENSIONS = [
    ("执法语言规范性", 25),
    ("执法流程完整性", 25),
    ("法律依据正确性", 20),
    ("情绪控制能力", 15),
    ("信息获取效率", 15),
]

SCENE_RUBRICS = {
    "接警": [
        "优先确认案发地点、报警人身份、事件类型、人员受伤情况和现场危险程度。",
        "需要体现安抚报警人、快速提取时间地点人物等关键信息的能力。",
        "如果未询问地点、时间、伤情、风险或是否仍在持续，应在流程完整性和信息获取效率维度扣分。",
    ],
    "现场": [
        "需要体现现场保护、人员分离、伤情判断、初步问询与证据意识。",
        "如果没有围绕目击经过、现场状态、人员关系展开，应在流程完整性维度扣分。",
        "如果忽视救助、风险控制或证据保护，应在法律依据正确性和流程完整性维度扣分。",
    ],
    "审讯": [
        "需要围绕身份核实、时间线、动机、矛盾点、证据线索逐步推进。",
        "如果问题杂乱、缺少追问、未利用前文信息形成突破，应在信息获取效率和流程完整性维度扣分。",
        "如果出现诱供、威胁、侮辱性表达，应在执法语言规范性维度重扣。",
    ],
    "通用": [
        "评分必须紧扣当前训练场景，而不是泛泛而谈。",
        "必须结合学员发言内容与推进顺序，指出做得好和做得不足的具体位置。",
    ],
}

EVALUATION_PROMPT_TEMPLATE = """
# 你的角色
你是一名严格、公正、专业的警务训练评分官，负责评估学员在模拟警情训练中的表现。

# 评分维度（总分 100）
1. 执法语言规范性（25分）：语言是否规范、克制、符合执法场景要求，是否存在侮辱、威胁、激化冲突等表达。
2. 执法流程完整性（25分）：是否按合理流程推进，是否遗漏身份、时间、地点、人物关系、风险处置等关键信息。
3. 法律依据正确性（20分）：处置思路是否符合执法常识与程序要求，是否具备现场保护、风险控制、证据意识。
4. 情绪控制能力（15分）：面对情绪激动对象时，能否保持冷静、克制和专业。
5. 信息获取效率（15分）：提问是否聚焦，追问是否有效，能否较快获取关键事实。

# 当前场景
{scene_info}

# 当前场景专项评分标准
{scene_rubric}

# 规则校验结果（必须纳入评分）
{rule_check_summary}

# 输入信息
- 案件信息：{case_info}
- 完整对话历史：{dialogue_history}
- 参考知识库：{knowledge_base}

# 评分要求
1. 每个维度都必须给出分数和具体理由。
2. 理由必须引用学员在对话中的实际表现，不能空泛。
3. 必须综合规则校验结果与场景专项标准，不能只看语气。
4. 如果出现明显违法违规、侮辱威胁、严重程序缺失，要明确扣分。
5. strengths / improvements 必须具体、可执行。

# 输出格式
严格输出 JSON：
{{
  "scores": [
    {{
      "dimension": "执法语言规范性",
      "score": 20,
      "full_score": 25,
      "reason": "整体表达较规范，但在某处措辞偏强硬。"
    }}
  ],
  "total_score": 85,
  "strengths": ["优点1"],
  "improvements": ["问题1"],
  "suggestions": "综合建议"
}}
"""


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
        speaker = "学员" if msg.role == "user" else "AI角色"
        content = (msg.content or "").strip()
        history_lines.append(f"{speaker}: {content}")
        if msg.role == "user":
            student_lines.append(content)
    return "\n".join(history_lines), student_lines


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
        findings.append({
            "level": "major",
            "dimension": "信息获取效率",
            "message": "学员有效发言轮次过少，难以完成完整处置与信息收集。"
        })
        deductions["信息获取效率"] += 4
        deductions["执法流程完整性"] += 3

    bad_phrases = ["闭嘴", "老实点", "快说", "少废话", "废话", "给我老实交代", "别装了"]
    if contains_any(joined, bad_phrases):
        findings.append({
            "level": "major",
            "dimension": "执法语言规范性",
            "message": "出现疑似不规范、带压迫性或激化冲突的表达。"
        })
        deductions["执法语言规范性"] += 8
        deductions["情绪控制能力"] += 3

    if scene_type == "接警":
        if not contains_any(joined, ["哪里", "地址", "地点", "具体位置", "几号楼", "房间", "案发地点"]):
            findings.append({
                "level": "major",
                "dimension": "执法流程完整性",
                "message": "接警阶段未明确确认案发地点。"
            })
            deductions["执法流程完整性"] += 6
            deductions["信息获取效率"] += 3
        if not contains_any(joined, ["什么时候", "几点", "刚刚", "时间"]):
            findings.append({
                "level": "minor",
                "dimension": "信息获取效率",
                "message": "接警阶段未及时确认事件发生时间。"
            })
            deductions["信息获取效率"] += 2
        if not contains_any(joined, ["受伤", "危险", "还在现场", "120", "是否安全"]):
            findings.append({
                "level": "minor",
                "dimension": "法律依据正确性",
                "message": "接警阶段未充分确认现场风险和救助需求。"
            })
            deductions["法律依据正确性"] += 3

    if scene_type == "现场":
        if not contains_any(joined, ["姓名", "你是谁", "和对方什么关系", "身份", "叫什么"]):
            findings.append({
                "level": "minor",
                "dimension": "执法流程完整性",
                "message": "现场问询阶段未充分核实身份和人物关系。"
            })
            deductions["执法流程完整性"] += 3
        if not contains_any(joined, ["现场", "不要破坏", "保持原状", "先别动", "证据"]):
            findings.append({
                "level": "minor",
                "dimension": "法律依据正确性",
                "message": "现场处置中未体现明显的现场保护或证据意识。"
            })
            deductions["法律依据正确性"] += 4

    if scene_type == "审讯":
        if not contains_any(joined, ["什么时候", "几点", "当时", "时间线", "案发时"]):
            findings.append({
                "level": "major",
                "dimension": "执法流程完整性",
                "message": "审讯或讯问中未围绕案发时间线有效展开。"
            })
            deductions["执法流程完整性"] += 5
        if not contains_any(joined, ["为什么", "动机", "关系", "证据", "监控", "不在场"]):
            findings.append({
                "level": "minor",
                "dimension": "信息获取效率",
                "message": "审讯中对动机、证据或矛盾点追问不足。"
            })
            deductions["信息获取效率"] += 3

    if role and not getattr(role, "name", ""):
        findings.append({
            "level": "minor",
            "dimension": "执法流程完整性",
            "message": "当前场景主对话角色信息异常，评估可能受限。"
        })

    return {
        "scene_type": scene_type,
        "findings": findings,
        "deductions": deductions,
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
    report["evaluation_meta"]["model"] = "deepseek-chat"
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
        if contains_any(joined, ["请", "麻烦", "先", "说明", "有没有", "是否"]):
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


def evaluate_session(db: Session, session_id: int):
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
        return None

    if session.status == "finished" and session.evaluation_result:
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
    knowledge = rag_service.search(case.case_type, limit=5) if case else []
    knowledge_base = "\n".join([f"- {item}" for item in knowledge]) if knowledge else "暂无相关法律标准参考。"

    scene_type = infer_scene_type(scene) if scene else "通用"
    scene_rubric = "\n".join([f"- {item}" for item in SCENE_RUBRICS.get(scene_type, SCENE_RUBRICS["通用"])])
    rule_checks = build_rule_checks(scene, student_lines, role) if scene else {"findings": [], "deductions": {}, "scene_type": "通用"}
    rule_check_summary = render_rule_summary(rule_checks)

    case_info = "暂无案件信息"
    if case:
        case_info = f"案件标题：{case.title}\n案件类型：{case.case_type}\n案件背景：{case.background}"
    scene_info = f"场景名称：{scene.name if scene else '未知'}\n场景类型：{scene_type}\n主对话对象：{getattr(role, 'name', '未知')}"

    full_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        scene_info=scene_info,
        scene_rubric=scene_rubric,
        rule_check_summary=rule_check_summary,
        case_info=case_info,
        dialogue_history=dialogue_history or "暂无对话内容",
        knowledge_base=knowledge_base,
    )

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一名公正、严格、专业的警务训练教官，必须输出合法 JSON。"},
                {"role": "user", "content": full_prompt},
            ],
            response_format={"type": "json_object"},
        )

        report = json.loads(response.choices[0].message.content)
        report = normalize_llm_report(report)
        report = apply_rule_adjustments(report, rule_checks)
        report = calibrate_report(report, student_lines, scene_type)
        report["evaluation_meta"]["scene_type"] = scene_type
        report["evaluation_meta"]["knowledge_hits"] = knowledge
        report["evaluation_meta"]["prompt_version"] = "hybrid_scene_v3"

        report_json = json.dumps(report, ensure_ascii=False)
        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()

        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {"error": str(e)}
