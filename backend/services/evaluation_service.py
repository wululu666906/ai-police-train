import json
from openai import OpenAI
from sqlalchemy.orm import Session
import os
import models

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
)

EVALUATION_PROMPT_TEMPLATE = """
你是公安实战训练考核专家。请对以下接处警模拟训练对话进行全维度评估。

【训练基本信息】
- 案件背景：{background}
- 扮演角色：{role_name}
- 最终角色状态：情绪{emotion}/100, 信任{trust}/100

【对话历史】
{history_text}

【评估任务】
请基于对话内容，从以下五个维度（0-100分）进行评分，并给出专业化的评语。
1. 执法规范性 (Professionalism): 用语是否文明、程序是否合规。
2. 沟通说服力 (Communication): 是否有安抚技巧、缓解矛盾的能力。
3. 信息采集度 (Information): 是否问清了核心事实要素。
4. 情绪调控力 (EmotionControl): 对角色情绪的掌控和引导情况。
5. 处置果断性 (DecisionMaking): 处理方案是否明确得当。

【输出要求】
你必须且只能输出如下格式的 JSON：
{{
  "overall_score": 整数,
  "grade": "S/A/B/C/D",
  "dimensions": {{
    "professionalism": 整数,
    "communication": 整数,
    "information": 整数,
    "emotion_control": 整数,
    "decision_making": 整数
  }},
  "highlights": ["优点1", "优点2"],
  "shortcomings": ["缺点1", "缺点2"],
  "suggestion": "专业改进建议..."
}}
"""

def evaluate_session(db: Session, session_id: int):
    # 1. 加载数据
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
         return None
    
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
    role = db.query(models.Role).filter(models.Role.scene_id == scene.id).first()
    msgs = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.asc()).all()
    
    # 格式化对话
    history_text = "\n".join([f"{m.role}: {m.content}" for m in msgs])
    
    # 2. 调用 LLM 评估
    full_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        background=case.background,
        role_name=role.name,
        emotion=session.current_emotion,
        trust=session.current_trust,
        history_text=history_text
    )
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "你是一名公正专业的警察学院教官。"},
                      {"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"}
        )
        
        report = json.loads(response.choices[0].message.content)
        
        # 3. 持久化报告（MVP 简单处理：更新 session 状态或预留字段）
        # 这里建议以后在 TrainingSession 增加 evaluation_json 字段
        # 目前返回给前端即可
        session.status = "finished"
        db.commit()
        
        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {"error": str(e)}
