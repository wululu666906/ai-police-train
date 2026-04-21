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
你是一名{role_name}，正在接受警察的询问/正在和警察对话。

# 案件背景
{case_description}

# 训练进度与目标
你现在处于：【{current_stage}】阶段。
本次实战的完整阶段规划为：
{stages_info}
你的任务是根据对话进展，引导学员完成这些阶段。

# 你的角色设定
- 性格：{personality}
- 类型：{role_type}
- 当前情绪：{emotion} (0=完全冷静，100=情绪失控)
- 信任度：{trust} (0=完全不信任，100=完全信任)
- 说话风格：{speaking_style}

# ⚠️ 核心交互规则 (重要)
1. **绝不冷场（No-Silence Rule）**：即使学员问得不专业、或者你对他的信任度极低，你也**绝对禁止**完全拒绝释放信息或说“我不知道/我不告诉你”。
2. **渐进式释放**：
   - 信任度低时：你可以表现得抗拒，给出**极简、模糊、甚至带点情绪**的简短回复，但必须包含一点点事实碎片。
   - 信任度高时：给出详细、准确、配合的回答。
   - 目的：通过这种方式延长对话轮数，诱导学员运用更好的谈话技巧（如共情、法律震慑）来获取更多信息。
3. **阶段管理**：
   - 只有当你认为学员在本阶段的表现已经达到了目标（stage_goal），你才可以在 JSON 中将 `is_stage_completed` 设为 true。
   - 完成后，你应在回答中通过言语巧妙地向下一阶段过渡（例如：由“谈论案发经过”过渡到“谈论赔偿意愿”）。

# 信息控制
- 掌握信息：{all_info}
- 已说：{revealed_info}
- 未说：{hidden_info}

# 执法知识参考
{rag_knowledge}

# 输出要求
必须且只能输出 JSON 格式。
{{
  "response": "你扮演角色说的话...",
  "updated_emotion": 整数(0-100),
  "updated_trust": 整数(0-100),
  "new_fact_revealed": "本轮吐露的新事实关键词，无则null",
  "is_stage_completed": 布尔值 (本阶段目标是否已达成),
  "stage_transition_msg": "如果你认为阶段已完成，给出下一步建议（仅供系统参考，不展示给学员）"
}}
"""
def generate_dialogue(db: Session, session_id: int, user_message: str):
    # 1. 获取会话与上下文 (增加多级容错)
    training_session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not training_session:
        return None
    
    scene = db.query(models.Scene).filter(models.Scene.id == training_session.scene_id).first()
    if not scene:
        return None
        
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
    
    # 获取该场景下的所有角色设定
    scene_roles = db.query(models.Role).filter(models.Role.scene_id == scene.id).all()
    if not scene_roles:
        scene_roles = db.query(models.Role).filter(models.Role.case_id == case.id).all()
    
    # 确定当前主视角角色 (优先取第一个，或根据逻辑动态切换)
    role = scene_roles[0] if scene_roles else models.Role(name="当事人", personality="普通群众", role_type="配合型", speaking_style="平实", hidden_truths="[]")
    
    # 汇总所有角色设定作为上下文
    roles_context = ""
    for r in scene_roles:
        roles_context += f"- 姓名：{r.name}, 身份：{r.role_type}, 性格：{r.personality}, 风格：{r.speaking_style}\n"
    
    # 获取历史记录(最近10条)
    history = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.desc()).limit(10).all()
    history.reverse()
    
    # 2. RAG 检索
    knowledge = rag_service.search(user_message, limit=2)
    rag_knowledge = "\n".join([f"- {k}" for k in knowledge]) if knowledge else "暂无相关法律参考。"

    # 汇总所有阶段信息作为上下文
    stages_raw = json.loads(scene.stages or "[]")
    stages_info = ""
    for idx, s in enumerate(stages_raw):
        stages_info += f"{idx+1}. {s.get('stage_name')}: {s.get('stage_goal')}\n"

    # 3. 信息控制逻辑
    all_info_list = json.loads(role.hidden_truths or "[]")
    revealed_info_list = json.loads(training_session.revealed_info or "[]")
    hidden_info_list = [i for i in all_info_list if i not in revealed_info_list]

    # 4. 构建更加直接的 Prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        role_name=role.name,
        case_description=case.background,
        current_stage=training_session.current_stage or "训练开始",
        stages_info=stages_info,
        personality=f"{role.personality} (当前场景中所有人角色设定: {roles_context})",
        role_type=role.role_type,
        emotion=training_session.current_emotion,
        trust=training_session.current_trust,
        speaking_style=role.speaking_style,
        all_info=json.dumps(all_info_list, ensure_ascii=False),
        revealed_info=json.dumps(revealed_info_list, ensure_ascii=False),
        hidden_info=json.dumps(hidden_info_list, ensure_ascii=False),
        rag_knowledge=rag_knowledge,
        user_input=user_message
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role if msg.role != "ai" else "assistant", "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    
    # 5. 调用 OpenAI/DeepSeek
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # 6. 更新数据库状态
        training_session.current_emotion = result.get("updated_emotion", training_session.current_emotion)
        training_session.current_trust = result.get("updated_trust", training_session.current_trust)
        
        # 处理阶段流转
        if result.get("is_stage_completed"):
            stages_list = json.loads(scene.stages or "[]")
            current_idx = -1
            for idx, s in enumerate(stages_list):
                if s.get("stage_name") == training_session.current_stage:
                    current_idx = idx
                    break
            
            # 如果还有下一阶段，则自动切换
            if current_idx != -1 and current_idx < len(stages_list) - 1:
                next_stage = stages_list[current_idx + 1]
                training_session.current_stage = next_stage.get("stage_name")
        
        new_fact = result.get("new_fact_revealed")
        if new_fact and str(new_fact).lower() != "null":
            try:
                current_revealed = json.loads(training_session.revealed_info or "[]")
                if new_fact not in current_revealed:
                    current_revealed.append(new_fact)
                    training_session.revealed_info = json.dumps(current_revealed, ensure_ascii=False)
            except:
                training_session.revealed_info = json.dumps([new_fact], ensure_ascii=False)
        
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
