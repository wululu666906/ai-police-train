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
2. 你的分析必须包含：完整的案发故事背景、案件发展全过程、各方的因果逻辑、以及最终确定的违法犯罪嫌疑人及其犯罪手段。

# 任务目标
请从输入的案件原始文本中，结构化输出以下核心信息：
1. 案件名称：高度概括案件性质。
2. 案件类型：从 [邻里纠纷, 打架斗殴, 酒驾, 盗窃, 诈骗, 群体性事件, 其他] 中选择。
3. 案情全景描述 (full_narrative)：包含起因、经过、结果的完整、逻辑连贯的故事全貌。
4. 犯罪/违规过程详解 (criminal_process)：详细描述违法人员的操作过程、作案动机、作案手段。
5. 最终责任人/嫌疑人 (main_culprit)：明确指出谁是核心过错方或犯罪分子。
6. 人物列表 (persons)：列出所有涉及的人物，包含：
   - name: 姓名/称谓
   - role: 身份（报警人/嫌疑人/证人/群众/受害人）
   - personality: 深度性格画像及心理动机分析
   - speaking_style: 说话风格（如：冲动、粗鲁、胆怯、冷静）
   - init_emotion: 初始情绪值（0非常冷静，100情绪完全失控）
   - init_trust: 初始信任度（0完全不信任不配合，100完全信任配合）
   - status: 角色当前状态（如：正常、受伤、重伤、昏迷、死亡等）
   - role_type: 角色类型评价（配合型/情绪型/对抗型/隐瞒型）
7. 矛盾/核心冲突点：各方利益或情绪的冲突根源。
8. 法律事实清单 (key_facts)：支撑案件定性的所有证据性事实，按顺序编号。
9. 隐藏线索 (hidden_info)：由于人性、利益等原因，人物在对话中可能会隐瞒、撒谎或回避的信息点。

# 输出格式
必须严格按照JSON格式输出，不要有额外解释：
{
  "case_name": "...",
  "case_type": "...",
  "full_narrative": "...",
  "criminal_process": "...",
  "main_culprit": "...",
  "persons": [
    {
      "name": "...",
      "role": "...",
      "personality": "...",
      "speaking_style": "...",
      "init_emotion": 50,
      "init_trust": 30,
      "status": "...",
      "role_type": "..."
    }
  ],
  "conflict_points": ["冲突点1", "冲突点2"],
  "key_facts": ["事实1", "事实2"],
  "hidden_info": ["潜在线索1"]
}

# 约束规则
- 细节至上：确保所有细节（如具体案发时间、特定的犯罪动作、涉案工具等）都体现在 JSON 中。
- 严禁脑补：若文本中确实缺失某些信息，对应字段留空，不得凭空捏造。
- 逻辑一致性：full_narrative 与 persons 中的背景必须相互印证。
"""

# 🎯 二、训练场景生成岗位提示词
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
