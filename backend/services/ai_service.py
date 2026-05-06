import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

import models
from .role_resolver import resolve_scene_role

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
)

SYSTEM_PROMPT_TEMPLATE = """
# 你的身份
你是“{role_name}”，正在接受民警问询。你必须严格按照案件事实、你的已知信息和你的角色身份作答。

# 核心规则
1. 你必须始终回应，不允许空白回复。
2. 你只能回答你“知道”的内容；对不知道的内容必须明确表示不知道。
3. 你可以对“hidden_truths”中的内容有所保留，但不能捏造客观事实。
4. 对时间、地点、人物关系、现场状态等硬事实，严禁编造。
5. 只输出一个合法 JSON 对象，不要输出任何额外解释。

# 案件事实档案
案发时间: {case_time}
案发地点: {case_location}
报警时间: {report_time}
时间线:
{timeline}

# 你的知识边界
你知道的事实:
{knows_facts}

你不知道的事实:
{does_not_know}

你想隐瞒的事实:
{hidden_truths}

# 你的人设与状态
- 性格: {personality}
- 智商: {iq_level}
- 情商: {eq_level}
- 撒谎能力: {lying_ability}
- 软肋: {weakness}
- 当前情绪: {emotion}/100
- 当前信任: {trust}/100

# 信息释放规则
- 当前信任低于 {release_threshold} 时，优先回避、克制、谨慎。
- 当前信任达到 {release_threshold} 及以上时，可以逐步透露少量隐藏信息。
- 当前信任很高且被问到软肋时，可以明显松动。

# 当前训练阶段
{current_stage}

# 输出格式
{{
  "response": "包含动作描写和口语化台词的角色回复",
  "inner_thought": "角色当前真实心理活动",
  "updated_emotion": 50,
  "updated_trust": 30,
  "new_fact_revealed": null,
  "is_stage_completed": false
}}
"""


def _parse_json_list(raw_value):
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return raw_value
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _advance_stage(scene, current_stage: str):
    if not scene or not scene.stages:
        return current_stage
    try:
        stages = json.loads(scene.stages) if isinstance(scene.stages, str) else scene.stages
    except Exception:
        return current_stage
    if not isinstance(stages, list):
        return current_stage

    for index, stage in enumerate(stages):
        if stage.get("stage_name") == current_stage:
            if index + 1 < len(stages):
                return stages[index + 1].get("stage_name", current_stage)
            return current_stage
    return current_stage


def _clamp_score(value, default: int) -> int:
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        numeric_value = default
    return max(0, min(100, numeric_value))


def generate_dialogue(db: Session, session_id: int, user_message: str):
    try:
        ts = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
        if not ts:
            return None

        scene = db.query(models.Scene).filter(models.Scene.id == ts.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None

        role = resolve_scene_role(db, scene, case)
        if not role:
            role = models.Role(
                name="当事人",
                role_type="配合型",
                personality="普通人",
                iq_level="中等",
                eq_level="中等",
                lying_ability="一般",
                status="正常",
                knows_facts="[]",
                does_not_know="[]",
                hidden_truths="[]",
                weakness="无明显弱点",
            )

        history = (
            db.query(models.Message)
            .filter(models.Message.session_id == session_id)
            .order_by(models.Message.created_at.desc())
            .limit(12)
            .all()
        )
        history.reverse()

        structured = json.loads(case.structured_data or "{}") if case and case.structured_data else {}
        fact_sheet = structured.get("fact_sheet", {})

        timeline_items = fact_sheet.get("timeline", [])
        if isinstance(timeline_items, list):
            timeline_text = "\n".join(
                [
                    f"  {item.get('time', '')} - {item.get('event', '')}"
                    for item in timeline_items
                    if isinstance(item, dict)
                ]
            )
        else:
            timeline_text = str(timeline_items)

        thresholds = {
            "配合型": 40,
            "情绪型": 50,
            "隐瞒型": 60,
            "对抗型": 70,
        }
        release_threshold = thresholds.get(role.role_type, 50)

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            role_name=role.name,
            case_time=fact_sheet.get("case_time", "未记录"),
            case_location=fact_sheet.get("case_location", "未记录"),
            report_time=fact_sheet.get("report_time", "未记录"),
            timeline=timeline_text or "未记录",
            knows_facts=role.knows_facts or "[]",
            does_not_know=role.does_not_know or "[]",
            hidden_truths=role.hidden_truths or "[]",
            personality=role.personality or "普通人",
            iq_level=role.iq_level or "中等",
            eq_level=role.eq_level or "中等",
            lying_ability=role.lying_ability or "一般",
            weakness=role.weakness or "无明显弱点",
            current_stage=ts.current_stage or "初始接触",
            emotion=ts.current_emotion,
            trust=ts.current_trust,
            release_threshold=release_threshold,
        )

        msgs = [{"role": "system", "content": system_prompt}]
        for message in history:
            msgs.append(
                {
                    "role": "assistant" if message.role in ["ai", "assistant"] else "user",
                    "content": message.content,
                }
            )
        msgs.append({"role": "user", "content": user_message})

        max_retries = 2
        result = None

        for attempt in range(max_retries):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=msgs,
                response_format={"type": "json_object"},
                temperature=0.7 + (attempt * 0.2),
            )

            raw_content = response.choices[0].message.content or ""
            print(f"--- AI RAW (Attempt {attempt + 1}) ---\n{raw_content}\n--------------")

            try:
                start_idx = raw_content.find("{")
                end_idx = raw_content.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    result = json.loads(raw_content[start_idx : end_idx + 1])
                else:
                    result = json.loads(raw_content)
                break
            except Exception as parse_e:
                print(f"!!! JSON Parsing Error on attempt {attempt + 1}: {parse_e}")
                if attempt == max_retries - 1:
                    return {
                        "response": "（系统提示：当前角色响应解析失败，请换一种问法再试。）",
                        "inner_thought": "ERROR: LLM JSON Parse Failed after retries.",
                        "updated_emotion": ts.current_emotion,
                        "updated_trust": ts.current_trust,
                        "is_stage_completed": False,
                    }

        ts.current_emotion = _clamp_score(result.get("updated_emotion"), ts.current_emotion)
        ts.current_trust = _clamp_score(result.get("updated_trust"), ts.current_trust)

        ai_reply = result.get("response", "...")
        ai_thought = result.get("inner_thought", "...")
        new_fact = result.get("new_fact_revealed")
        stage_completed = bool(result.get("is_stage_completed", False))

        revealed_info = _parse_json_list(ts.revealed_info)
        if new_fact and str(new_fact).lower() != "null":
            if new_fact not in revealed_info:
                revealed_info.append(new_fact)
                ts.revealed_info = json.dumps(revealed_info, ensure_ascii=False)

        if stage_completed:
            ts.current_stage = _advance_stage(scene, ts.current_stage)

        db.add(models.Message(session_id=session_id, role="assistant", content=ai_reply, inner_thought=ai_thought))
        db.commit()

        return {
            "response": ai_reply,
            "inner_thought": ai_thought,
            "updated_emotion": ts.current_emotion,
            "updated_trust": ts.current_trust,
            "new_fact_revealed": new_fact,
            "is_stage_completed": stage_completed,
            "current_stage": ts.current_stage,
        }

    except Exception as e:
        if db:
            db.rollback()
        print(f"!!! DIALOGUE ERROR: {e}")
        return {
            "response": f"(由于系统异常，对话暂时无法继续。错误详情: {str(e)})",
            "inner_thought": "ERROR",
        }
