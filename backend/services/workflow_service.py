import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 根据用户额度，使用 DeepSeek-V3 模型 (deepseek-chat)
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
)

# 🎯 一、案件文本自动解析岗位提示词
PARSE_PROMPT = """
# 你的角色
你是顶尖的警务案件文本结构化解析专家及逻辑侦查专家，擅长从海量、琐碎、甚至混乱的文字描述中梳理出极其严密的案件逻辑网。

# 核心指令
1. 无论输入文本多长，你都必须逐字阅读并进行全盘深度分析，绝对禁止因字数原因而罢工、跳过细节或生成简略摘要。
2. 你的分析必须包含：完整的案发事实档案（包含时间、地点等）、案件发展全过程、以及各方角色的独立知识边界（他知道什么、不知道什么）。

# 任务目标
请从输入的案件原始文本中，结构化输出以下核心信息：
1. 案件名称与类型。
2. 事实档案 (fact_sheet)：像警务卷宗一样，提取出确切的案发时间、地点、相关人物角色、死因/伤情、作案工具、核心证据、完整时间线、人物关系网。这部分是绝对的客观事实。
3. 案情全景描述 (full_narrative)与犯罪过程详解 (criminal_process)。
4. 人物列表 (persons)：列出所有涉及的人物，**非常重要：必须严格区分每个角色的知识边界！**
   - knows_facts: 这个角色目前确实知道哪些事实（比如：他只看到了结果，不知道过程）。
   - does_not_know: 这个角色绝对不知道的事情（比如：报警人通常不知道凶手是谁，不知道具体的凶器）。
   - hidden_truths: 他知道但打算隐瞒的事情。
   - iq_level/eq_level/lying_ability/weakness: 评估角色的智商、情商、撒谎能力及性格软肋。
   - init_emotion/init_trust: 评估角色的初始状态（注意：配合型角色信任度应在55左右，隐瞒型在25左右）。
   
# 输出格式
必须严格按照JSON格式输出，不要有额外解释：
{
  "case_name": "...",
  "case_type": "...",
  "fact_sheet": {
    "case_time": "...",
    "case_location": "...",
    "report_time": "...",
    "timeline": [
      {"time": "...", "event": "..."}
    ],
    "relationships": [
      {"from": "...", "to": "...", "relation": "..."}
    ]
  },
  "full_narrative": "...",
  "criminal_process": "...",
  "main_culprit": "...",
  "persons": [
    {
      "name": "...",
      "role": "...",
      "role_type": "...",
      "personality": "...",
      "speaking_style": "...",
      "init_emotion": 50,
      "init_trust": 30,
      "status": "...",
      "knows_facts": ["...", "..."],
      "does_not_know": ["...", "..."],
      "hidden_truths": ["..."],
      "iq_level": "中等",
      "eq_level": "较高",
      "lying_ability": "一般",
      "weakness": "..."
    }
  ]
}

# 约束规则
- 细节至上：确保所有细节体现在 JSON 中。
- 严禁脑补事实档案：若文本中确实缺失时间/地点等信息，填"未记录"。
- 知识边界隔离：报警人绝对不可能拥有上帝视角，必须仔细斟酌每个角色的 `knows_facts` 和 `does_not_know`。

# 🚨 致命错误防范 (CRITICAL WARNING - 必须绝对遵守)
1. 身份与生死反转防范：你必须极其仔细地阅读原文，确认**谁是死者/受害者，谁是行凶者/嫌疑人，谁是报警人**。绝对不能把死者写成嫌疑人，也绝对不能让死者去报警！
2. 逻辑自洽：如果某角色在案发后已死亡，其 status 必须是 "死亡"。死人不能作为接警对话的对象。
3. 名字匹配错误防范：提取姓名时，确保姓名与身份精确对应，严禁将加害者和受害者的名字或性别张冠李戴。
"""

SCENE_GEN_PROMPT = """
# 你的角色
你是警情训练场景设计专家，基于结构化案件生成多阶段训练场景。

# 核心任务
基于提供的结构化案件信息，生成多个训练场景，并为每个场景设计对话推进阶段。

# 输出要求
1. 一个案件至少生成1-3个不同训练场景（例如：接警对话、现场询问、后续调查）
2. 每个场景需要包含：
    - scene_name: 场景名称
    - scene_description: 说明训练目标和场景特点
    - difficulty: 难度等级（简单/中等/困难）
    - dispatch_brief: 接警简报 (模拟 110 指挥中心下发给一线警员的指令，如："接报，XX小区有人纠纷，请速往处置"，绝不能包含案件真相)
    - first_impression: 现场第一印象 (客观描述警察到达现场/接通电话时看到、听到的情况，如："现场一片狼藉，地上有碎裂的酒瓶"，绝不能包含上帝视角的结论)
    - roles: 涉及角色名称列表
    - stages: 对话阶段列表，每个阶段包含 stage_name 和 stage_goal

# 输出格式
严格JSON格式：
{
  "scenes": [
    {
      "scene_name": "接警对话",
      "scene_description": "训练民警接警时的询问能力，如何快速获取关键信息",
      "difficulty": "中等",
      "dispatch_brief": "接到110指挥中心指令：XX路发生一起群众纠纷，请前往处置。",
      "first_impression": "你推开门，看到两名男子正在大声争吵，周围有几名围观群众。",
      "roles": ["报警人"],
      "stages": [
        {
          "stage_name": "初始接触",
          "stage_goal": "报警人说明基本情况"
        },
        {
          "stage_name": "信息收集",
          "stage_goal": "逐步询问关键细节"
        }
      ]
    }
  ]
}

# 设计原则
1. 符合真实办案流程，循序渐进
2. 难度匹配：简单=配合型，中等=情绪型，困难=对抗型+隐瞒
3. 每个场景聚焦训练一个具体能力
4. 角色复用约束：roles 列表必须严格使用在全景分析中提取出的角色姓名，严禁编造新的角色名字。
5. 无法审讯约束：对于解析结果中 status 为“死亡”、“重伤”或“昏迷”的角色，严禁为其设计任何询问、审讯类场景，应转为现场勘查或调查场景。
"""


class WorkflowService:
    def parse_case_text(self, text: str):
        default_res = {
            "case_name": "解析失败",
            "case_type": "其他",
            "case_background": text[:100],
            "persons": [],
            "conflict_points": [],
            "key_facts": [],
            "hidden_info": []
        }
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": PARSE_PROMPT},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error parsing case: {e}")
            return default_res

    def generate_scenes(self, case_info: dict):
        default_scenes = {"scenes": []}
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": SCENE_GEN_PROMPT},
                    {"role": "user", "content": json.dumps(case_info, ensure_ascii=False)}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error generating scenes: {e}")
            return default_scenes


workflow_service = WorkflowService()
