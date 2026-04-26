import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import models
from .rag_service import rag_service

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
)

SYSTEM_PROMPT_TEMPLATE = """
# 你的身份
你是【{role_name}】，正在接受警察盘问。这是一场心理与事实的博弈。

# 🧱 核心规则 (必须遵守)
1. **禁止沉默与空场**：你必须对警察的每一句话做出实质性回应！就算完全不想配合，也必须用动作神态加冷漠的话语来表达。**绝对禁止返回空字符串或不符合 JSON 格式的内容**。
2. **知识边界**：你只知道【你的知识范围】里的内容。对于【你不知道的事】，你必须如实表示不知道（用符合人设的方式表达）。
3. **秘密保护**：对于【你的秘密】，你要根据当前的信任度和情绪决定是否透露。
4. **尊重客观**：对于【案件事实档案】中的公开客观信息（如你的报警时间、具体案发地点），你可以如实回答，**严禁自行编造时间/地点等硬事实**。
5. **输出格式**：你必须输出且仅输出一个合法的 JSON 对象，确保 `response` 字段的内容至少包含一段动作描写和一句台词。

# 📋 案件事实档案 (客观信息参考)
案发时间: {case_time}
案发地点: {case_location}
报警时间: {report_time}
事件时间线:
{timeline}

# 🧠 你的知识范围 (你确实知道的)
{knows_facts}

# 🚫 你不知道的 (被问到请坚决表示不知情)
{does_not_know}

# 🔒 你的秘密 (信任度达标后才可能说出)
{hidden_truths}

# 🎭 你的人设与状态
- 性格: {personality}
- 智商: {iq_level} (低=容易说漏嘴, 高=逻辑严密)
- 情商: {eq_level} (低=易被激怒, 高=善于控制)
- 撒谎能力: {lying_ability} (差=破绽百出, 强=面不改色)
- 软肋: {weakness}
- 当前指标：情绪 {emotion}/100，信任 {trust}/100

# 🎯 动态信息释放规则
- 信任度 < {release_threshold}: 严守秘密，被追问则转移话题、回避或表现对抗。
- 信任度 >= {release_threshold}: 可以开始"不小心"透露一条隐藏信息。
- 信任度 > 80 + 被触及软肋: 心理防线崩塌，主动坦白所有秘密。

# 🎯 当前训练阶段目标
{current_stage}

# 输出要求 (JSON 格式)
{{
  "response": "角色回复（包含动作描写和真实台词，绝不可为空）",
  "inner_thought": "角色当前的真实心理活动",
  "updated_emotion": 整数,
  "updated_trust": 整数,
  "new_fact_revealed": "新吐露的秘密事实关键词，无则null",
  "is_stage_completed": true/false
}}
"""

def generate_dialogue(db: Session, session_id: int, user_message: str):
    try:
        # 1. 获取上下文
        ts = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
        if not ts: return None
        
        scene = db.query(models.Scene).filter(models.Scene.id == ts.scene_id).first()
        case = db.query(models.Case).filter(models.Case.id == scene.case_id).first() if scene else None
        
        # ✅ 精准获取当前场景的主对话角色
        primary_link = db.query(models.SceneRole).filter(
            models.SceneRole.scene_id == scene.id,
            models.SceneRole.is_primary == True
        ).first()
        
        if primary_link:
            role = db.query(models.Role).get(primary_link.role_id)
        else:
            # 如果极端情况没有 is_primary 标记，取关联的第一个角色
            fallback_link = db.query(models.SceneRole).filter(models.SceneRole.scene_id == scene.id).first()
            if fallback_link:
                role = db.query(models.Role).get(fallback_link.role_id)
            else:
                # 最后的兜底
                role = models.Role(name="当事人", role_type="配合型", personality="普通人", iq_level="中等", eq_level="中等", lying_ability="一般")
        
        history = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.desc()).limit(12).all()
        history.reverse()
        
        # ✅ 从 structured_data 提取事实档案
        structured = json.loads(case.structured_data or "{}") if case and case.structured_data else {}
        fact_sheet = structured.get("fact_sheet", {})
        
        # 格式化时间线
        timeline_items = fact_sheet.get("timeline", [])
        if isinstance(timeline_items, list):
            timeline_text = "\n".join([f"  {t.get('time', '')} - {t.get('event', '')}" for t in timeline_items if isinstance(t, dict)])
        else:
            timeline_text = str(timeline_items)
            
        # 动态释放阈值
        thresholds = {"配合型": 40, "情绪型": 50, "隐瞒型": 60, "对抗型": 70}
        release_threshold = thresholds.get(role.role_type, 50)
        
        # 2. 填充 Prompt
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            role_name=role.name,
            case_time=fact_sheet.get("case_time", "未记录"),
            case_location=fact_sheet.get("case_location", "未记录"),
            report_time=fact_sheet.get("report_time", "未记录"),
            timeline=timeline_text or "未记录",
            knows_facts=role.knows_facts or "[]",
            does_not_know=role.does_not_know or "[]",
            hidden_truths=role.hidden_truths or "[]",
            personality=role.personality or "平民",
            iq_level=role.iq_level or "中等",
            eq_level=role.eq_level or "中等",
            lying_ability=role.lying_ability or "一般",
            weakness=role.weakness or "无明显弱点",
            current_stage=ts.current_stage or "初步接触",
            emotion=ts.current_emotion,
            trust=ts.current_trust,
            release_threshold=release_threshold
        )
        
        msgs = [{"role": "system", "content": system_prompt}]
        for m in history:
            msgs.append({"role": "assistant" if m.role in ["ai", "assistant"] else "user", "content": m.content})
        msgs.append({"role": "user", "content": user_message})
        
        # 3. API 调用与重试机制 (最多重试 2 次)
        max_retries = 2
        result = None
        
        for attempt in range(max_retries):
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=msgs,
                response_format={"type": "json_object"},
                temperature=0.7 + (attempt * 0.2) # 失败后稍微增加随机性
            )
            
            raw_content = response.choices[0].message.content or ""
            print(f"--- AI RAW (Attempt {attempt+1}) ---\n{raw_content}\n--------------")
            
            try:
                start_idx = raw_content.find('{')
                end_idx = raw_content.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    clean_json = raw_content[start_idx:end_idx+1]
                    result = json.loads(clean_json)
                else:
                    result = json.loads(raw_content)
                break # 成功则跳出循环
            except Exception as parse_e:
                print(f"!!! JSON Parsing Error on attempt {attempt+1}: {parse_e}")
                if attempt == max_retries - 1:
                    # 最后一次仍然失败，不保存到数据库，直接抛出提示
                    return {
                        "response": "（系统提示：角色当前状态异常，可能由于问题触发了安全限制或解析失败，请尝试换种问法）",
                        "inner_thought": "ERROR: LLM JSON Parse Failed after retries.",
                        "updated_emotion": ts.current_emotion,
                        "updated_trust": ts.current_trust,
                        "is_stage_completed": False
                    }
        
        # 5. 更新与持久化
        ts.current_emotion = result.get("updated_emotion", ts.current_emotion)
        ts.current_trust = result.get("updated_trust", ts.current_trust)
        
        ai_reply = result.get("response", "...")
        ai_thought = result.get("inner_thought", "...")
        
        db.add(models.Message(session_id=session_id, role="assistant", content=ai_reply, inner_thought=ai_thought))
        db.commit()
        
        return {
            "response": ai_reply,
            "inner_thought": ai_thought,
            "updated_emotion": ts.current_emotion,
            "updated_trust": ts.current_trust,
            "new_fact_revealed": result.get("new_fact_revealed"),
            "is_stage_completed": result.get("is_stage_completed", False)
        }

    except Exception as e:
        if db: db.rollback()
        print(f"!!! DIALOGUE ERROR: {e}")
        return {"response": f"(由于系统异常，对话暂时无法继续。错误详情: {str(e)})", "inner_thought": "ERROR"}
