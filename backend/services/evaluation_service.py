import json
from openai import OpenAI
from sqlalchemy.orm import Session
import os
import models
from .rag_service import rag_service

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
)

EVALUATION_PROMPT_TEMPLATE = """
# 你的角色
你是警务执法训练专业评分官，负责对民警在模拟警情训练中的表现进行专业评分。

# 评分维度（满分100分）
1. 执法语言规范性（权重25%）：语言是否规范、符合执法要求，有没有不当表述
2. 执法流程完整性（权重25%）：是否按照合理流程询问，有没有遗漏关键信息
3. 法律依据正确性（权重20%）：引用法律是否正确，处理方式是否合法
4. 情绪控制能力（权重15%）：面对对方情绪激动时，能否保持冷静专业
5. 信息获取效率（权重15%）：能否快速、准确获取关键信息

# 输入信息
- 案件信息：{case_info}
- 完整对话历史：{dialogue_history}
- 参考知识库（评分标准依据）：{knowledge_base}

# 评分要求
1. 每个维度分别打分，并给出扣分原因
2. 计算总分
3. 给出具体改进建议，指出哪里做得好，哪里需要改进
4. 评价要客观、具体，结合对话中的具体内容

# 输出格式
严格JSON：
{{
  "scores": [
    {{
      "dimension": "执法语言规范性",
      "score": 20,
      "full_score": 25,
      "reason": "整体语言规范，但在XX地方有不恰当表述"
    }}
  ],
  "total_score": 85,
  "strengths": ["做得好的地方1"],
  "improvements": ["需要改进的地方1"],
  "suggestions": "整体改进建议总结"
}}

# 约束
1. 严格扣分制：没有问题就给满分，有问题根据严重程度扣分
2. 必须结合对话中的具体内容说明原因，不要空泛评价
3. 如果出现明显违法违规表述，直接对应维度给0分
"""

def evaluate_session(db: Session, session_id: int):
    # 1. 加载数据
    session = db.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first()
    if not session:
         return None
    
    # 如果已经评分过，直接返回保存的结果
    if session.status == "finished" and session.evaluation_result:
        return json.loads(session.evaluation_result)
    
    scene = db.query(models.Scene).filter(models.Scene.id == session.scene_id).first()
    case = db.query(models.Case).filter(models.Case.id == scene.case_id).first()
    msgs = db.query(models.Message).filter(models.Message.session_id == session_id).order_by(models.Message.created_at.asc()).all()
    
    # 格式化对话
    dialogue_history = "\n".join([f"{'学员' if m.role == 'user' else 'AI角色'}: {m.content}" for m in msgs])
    
    # 3. 准备知识库参考 (针对案件类型检索相关知识)
    knowledge = rag_service.search(case.case_type, limit=5)
    knowledge_base = "\n".join([f"- {k}" for k in knowledge]) if knowledge else "暂无相关法律标准参考。"

    # 2. 调用 LLM 评估
    full_prompt = EVALUATION_PROMPT_TEMPLATE.format(
        case_info=f"案件标题：{case.title}\n案件背景：{case.background}",
        dialogue_history=dialogue_history,
        knowledge_base=knowledge_base
    )
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "你是一名公正专业的警察学院教官。"},
                      {"role": "user", "content": full_prompt}],
            response_format={"type": "json_object"}
        )
        
        report_json = response.choices[0].message.content
        report = json.loads(report_json)
        
        # 3. 持久化状态与结果
        session.status = "finished"
        session.evaluation_result = report_json
        db.commit()
        
        return report
    except Exception as e:
        print(f"Evaluation error: {e}")
        return {"error": str(e)}
