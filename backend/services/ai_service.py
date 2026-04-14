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
你是AI虚拟警情模拟演练引擎。
你现在扮演的是一名：{role_name}。
性格特征：{personality}。
当前案件背景：{background}
当前对话阶段：{scene_name}

【法律与话术参考】
{knowledge_context}

【当前状态变量】
- 情绪值 (emotion): {current_emotion} (0-100, 100为极其愤怒/崩溃，0为冷静)
- 信任度 (trust): {current_trust} (0-100, 100为完全配合，0为极度对抗/隐瞒)
- 已吐露信息: {revealed_info}
- 尚未吐露的关键事实: {hidden_truths}

【演练规则】
1. 你必须严格遵循角色的性格。如果信任度低，你应该回避问题、撒谎或表现出对抗情绪。
2. 随着对话深入，如果学员安抚得当或提问精准，你应该适当增加信任度（trust）。
3. 如果学员言语粗鲁或违反执法规范，你应该增加愤怒值（emotion）并降低信任度。
4. 只有当持续安抚或信任度达到一定阈值（建议>70）时，你才可以在“回答内容”中自然地透露一条“尚未吐露的关键事实”。

【输出要求】
你必须且只能以 JSON 格式输出，不得包含任何其他解释文字。格式如下：
{{
  "response": "你扮演角色说的话...",
  "updated_emotion": 整数,
  "updated_trust": 整数,
  "new_fact_revealed": "如果本轮吐露了新事实则记录，否则为null"
}}
"""

def generate_dialogue(db: Session, session_id: int, user_message: str):
    # 1. 获取会话与上下文
    training_session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not training_session:
        return None
    
    scene = db.query(models.Scene).filter(models.Scene.id == training_session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
    role = db.query(models.Role).filter(models.Role.scene_id == scene.id).first()
    
    # 获取历史记录(最近10条)
    history = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.desc()).limit(10).all()
    history.reverse()
    
    # 2. RAG 检索
    knowledge = rag_service.search(user_message, limit=2)
    knowledge_context = "\n".join([f"- {k}" for k in knowledge]) if knowledge else "暂无相关法律参考。"

    # 3. 构建 Prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        role_name=role.name,
        personality=role.personality,
        background=case.background,
        scene_name=scene.name,
        knowledge_context=knowledge_context,
        current_emotion=training_session.current_emotion,
        current_trust=training_session.current_trust,
        revealed_info=training_session.revealed_info,
        hidden_truths=role.hidden_truths
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    
    # 3. 调用 DeepSeek
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # 4. 更新数据库状态
        training_session.current_emotion = result.get("updated_emotion", training_session.current_emotion)
        training_session.current_trust = result.get("updated_trust", training_session.current_trust)
        
        new_fact = result.get("new_fact_revealed")
        if new_fact:
            current_revealed = json.loads(training_session.revealed_info)
            if new_fact not in current_revealed:
                current_revealed.append(new_fact)
                training_session.revealed_info = json.dumps(current_revealed)
        
        # 保存对话记录
        user_msg_db = models.Message(session_id=session_id, role="user", content=user_message)
        ai_msg_db = models.Message(session_id=session_id, role="assistant", content=result.get("response"))
        
        db.add(user_msg_db)
        db.add(ai_msg_db)
        db.commit()
        
        return result
    except Exception as e:
        print(f"Error in generate_dialogue: {e}")
        return {"error": str(e)}
