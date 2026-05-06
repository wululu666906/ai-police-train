import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

CASE_TYPE_GROUPS = {
    "纠纷求助类": [
        "邻里纠纷",
        "家庭纠纷",
        "感情纠纷",
        "劳资纠纷",
        "消费纠纷",
        "噪音扰民",
        "失踪求助",
        "自杀干预",
        "校园警情",
        "宠物纠纷",
    ],
    "治安案件类": [
        "打架斗殴",
        "寻衅滋事",
        "故意伤害",
        "损毁财物",
        "醉酒闹事",
        "赌博",
        "卖淫嫖娼",
        "非法侵入住宅",
    ],
    "刑事案件类": [
        "故意杀人",
        "盗窃",
        "扒窃",
        "诈骗",
        "电信网络诈骗",
        "入室盗窃",
        "抢夺抢劫",
        "敲诈勒索",
        "涉毒",
    ],
    "交通警情类": [
        "交通事故",
        "酒驾醉驾",
        "肇事逃逸",
    ],
}

CASE_TYPE_OPTIONS = [item for group in CASE_TYPE_GROUPS.values() for item in group] + ["其他"]

CASE_TYPE_SYNONYMS = {
    "民间纠纷": "邻里纠纷",
    "邻里矛盾": "邻里纠纷",
    "夫妻纠纷": "家庭纠纷",
    "婚恋纠纷": "感情纠纷",
    "情感纠纷": "感情纠纷",
    "工资纠纷": "劳资纠纷",
    "欠薪纠纷": "劳资纠纷",
    "消费维权": "消费纠纷",
    "扰民": "噪音扰民",
    "斗殴": "打架斗殴",
    "打架": "打架斗殴",
    "伤害": "故意伤害",
    "伤人": "故意伤害",
    "命案": "故意杀人",
    "杀人": "故意杀人",
    "偷窃": "盗窃",
    "盗窃案": "盗窃",
    "电诈": "电信网络诈骗",
    "网络诈骗": "电信网络诈骗",
    "电信诈骗": "电信网络诈骗",
    "室内盗窃": "入室盗窃",
    "入户盗窃": "入室盗窃",
    "抢劫": "抢夺抢劫",
    "抢夺": "抢夺抢劫",
    "勒索": "敲诈勒索",
    "毁坏财物": "损毁财物",
    "砸车": "损毁财物",
    "轻生": "自杀干预",
    "跳楼": "自杀干预",
    "醉酒滋事": "醉酒闹事",
    "车祸": "交通事故",
    "醉驾": "酒驾醉驾",
    "酒驾": "酒驾醉驾",
    "逃逸": "肇事逃逸",
    "吸毒": "涉毒",
    "贩毒": "涉毒",
    "涉黄": "卖淫嫖娼",
    "强行入室": "非法侵入住宅",
}

CASE_TYPE_KEYWORDS = [
    ("电信网络诈骗", ["刷单", "冒充客服", "冒充公检法", "验证码", "转账", "诈骗电话", "被骗", "电信诈骗", "网络诈骗"]),
    ("入室盗窃", ["入室盗窃", "入户盗窃", "撬门", "翻窗", "家中被盗"]),
    ("抢夺抢劫", ["抢劫", "抢夺", "持刀抢", "拦路抢", "飞车抢夺"]),
    ("敲诈勒索", ["敲诈", "勒索", "威胁转账", "要挟"]),
    ("肇事逃逸", ["肇事逃逸", "撞人后逃逸", "交通逃逸", "逃逸"]),
    ("故意杀人", ["杀人", "命案", "尸体", "死亡", "被捅死", "致死"]),
    ("故意伤害", ["持刀伤人", "砍伤", "打伤", "轻伤", "重伤", "受伤"]),
    ("打架斗殴", ["打架", "斗殴", "互殴", "群殴"]),
    ("寻衅滋事", ["寻衅滋事", "故意挑衅", "无故滋事", "闹事"]),
    ("盗窃", ["盗窃", "偷窃", "被偷", "扒窃", "偷手机", "偷电动车"]),
    ("扒窃", ["扒窃", "扒手"]),
    ("涉毒", ["吸毒", "贩毒", "毒品", "冰毒", "海洛因", "K粉"]),
    ("赌博", ["赌博", "赌资", "赌局", "麻将馆赌博"]),
    ("卖淫嫖娼", ["卖淫", "嫖娼", "招嫖", "色情交易"]),
    ("酒驾醉驾", ["酒驾", "醉驾", "酒后驾驶"]),
    ("交通事故", ["交通事故", "追尾", "碰撞", "车祸", "剐蹭"]),
    ("家庭纠纷", ["家庭纠纷", "夫妻吵架", "家暴", "婆媳矛盾"]),
    ("感情纠纷", ["感情纠纷", "恋爱纠纷", "分手", "情感矛盾"]),
    ("邻里纠纷", ["邻里纠纷", "邻居", "楼上楼下", "小区住户争吵"]),
    ("劳资纠纷", ["劳资纠纷", "欠薪", "讨薪", "工资", "老板拖欠", "工钱", "围堵工地", "讨要工资"]),
    ("消费纠纷", ["消费纠纷", "退款", "商家", "售后", "商品质量"]),
    ("噪音扰民", ["扰民", "噪音", "施工噪音", "深夜唱歌", "音响太大"]),
    ("损毁财物", ["砸车", "砸门", "损坏", "毁坏财物", "打砸"]),
    ("失踪求助", ["失踪", "走失", "找不到人", "离家出走"]),
    ("自杀干预", ["轻生", "跳楼", "自杀", "割腕", "站上天台"]),
    ("醉酒闹事", ["醉酒闹事", "醉汉", "酒后滋事", "喝多了闹事"]),
    ("非法侵入住宅", ["非法侵入住宅", "强行进入住宅", "私闯民宅"]),
    ("校园警情", ["校园", "学生打架", "宿舍纠纷", "老师报警"]),
    ("宠物纠纷", ["宠物", "狗咬人", "遛狗纠纷", "养狗纠纷"]),
]

PARSE_PROMPT = f"""
# 你的角色
你是警务案件文本结构化解析专家。你需要把原始案件文本解析成适合训练平台使用的稳定 JSON。

# 任务要求
请从输入文本中提取并输出以下信息：
1. case_name：案件名称
2. case_type：案件类型。必须优先从以下受控类型中选择最贴近的一项，不要自造类型：
{json.dumps(CASE_TYPE_OPTIONS, ensure_ascii=False)}
3. case_background：案件背景。这里必须是案件级别的背景介绍，供学员进入训练前快速了解事件背景，要求简洁、客观、非上帝视角总结。
4. fact_sheet：客观事实表，尽量包含案发时间、地点、报警时间、关键时间线、人物关系
5. full_narrative：案件全景叙述
6. criminal_process：如果涉及违法犯罪，请描述作案或冲突发展过程；如果不适用可写“未明确提及”
7. main_culprit：主要嫌疑人或主要责任方；如果无法确定可写“未明确”
8. persons：所有涉及人物，必须区分谁活着、谁死亡、谁重伤、谁昏迷

# 对人物的严格要求
每个人物都必须包含：
- name
- role
- role_type
- personality
- speaking_style
- init_emotion
- init_trust
- status
- knows_facts
- does_not_know
- hidden_truths
- iq_level
- eq_level
- lying_ability
- weakness

# 关键约束
1. 严禁把死者、重伤无法交流者、昏迷者当成可正常对话对象。
2. 严禁把报警人、受害人、嫌疑人身份混淆。
3. 如果原文没有明确时间、地点、身份，请写“未明确”或空列表，不要脑补。
4. 必须输出合法 JSON，不要输出解释性文字。

# 输出格式
{{
  "case_name": "...",
  "case_type": "...",
  "case_background": "...",
  "fact_sheet": {{
    "case_time": "...",
    "case_location": "...",
    "report_time": "...",
    "timeline": [
      {{"time": "...", "event": "..."}}
    ],
    "relationships": [
      {{"from": "...", "to": "...", "relation": "..."}}
    ]
  }},
  "full_narrative": "...",
  "criminal_process": "...",
  "main_culprit": "...",
  "persons": [
    {{
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
      "eq_level": "中等",
      "lying_ability": "一般",
      "weakness": "..."
    }}
  ]
}}
"""

SCENE_GEN_PROMPT = """
# 你的角色
你是警情训练场景设计专家，需要基于案件结构化信息生成可直接用于学员训练的场景。

# 任务目标
请生成 2-3 个训练场景。每个场景都必须可落地、符合办案流程，并且人物安排必须与案件事实一致。

# 每个场景必须输出
1. scene_name：场景名称
2. scene_description：训练目标与场景说明
3. difficulty：简单 / 中等 / 困难
4. dispatch_brief：接警简报。用于学员进入场景前看到的 110 指令信息，只能写学员此时合理能知道的信息，绝不能暴露真相。
5. first_impression：现场第一印象。用于学员进入场景后第一眼看到、听到、感受到的客观情况，不能写上帝视角结论。
6. roles：该场景会出场的人物姓名列表，必须严格使用 persons 里已有的人名
7. stages：对话推进阶段，数组元素包含 stage_name 和 stage_goal

# 强约束
1. 已死亡、昏迷、重伤无法交流的人物，不能被安排为问话对象。
2. 如果案件文本里明确某人已死亡，这个人可以存在于案件里，但只能用于现场勘查、尸体发现、证据核验类场景，不能开口说话。
3. dispatch_brief 和 first_impression 不能为空。
4. roles 中不要编造新人物。
5. 所有输出必须是合法 JSON。

# 输出格式
{
  "scenes": [
    {
      "scene_name": "...",
      "scene_description": "...",
      "difficulty": "中等",
      "dispatch_brief": "...",
      "first_impression": "...",
      "roles": ["..."],
      "stages": [
        {
          "stage_name": "...",
          "stage_goal": "..."
        }
      ]
    }
  ]
}
"""


class WorkflowService:
    @staticmethod
    def _safe_json_loads(value, default):
        if isinstance(value, (dict, list)):
            return value
        if not value:
            return default
        try:
            return json.loads(value)
        except Exception:
            return default

    @staticmethod
    def _truncate_text(text: str, size: int = 120) -> str:
        return (text or "").strip()[:size]

    @staticmethod
    def _normalize_case_type_name(value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return ""
        if raw in CASE_TYPE_OPTIONS:
            return raw
        if raw in CASE_TYPE_SYNONYMS:
            return CASE_TYPE_SYNONYMS[raw]
        compact = raw.replace("类", "").replace("案件", "").replace("警情", "").strip()
        if compact in CASE_TYPE_OPTIONS:
            return compact
        if compact in CASE_TYPE_SYNONYMS:
            return CASE_TYPE_SYNONYMS[compact]
        return ""

    def normalize_case_type(self, text: str = "", ai_case_type: str = "") -> str:
        direct = self._normalize_case_type_name(ai_case_type)
        if direct:
            return direct

        combined = f"{ai_case_type or ''}\n{text or ''}"
        for case_type, keywords in CASE_TYPE_KEYWORDS:
            if any(keyword in combined for keyword in keywords):
                return case_type
        return "其他"

    @staticmethod
    def _default_dispatch_brief(case_info: dict, scene_name: str) -> str:
        case_name = case_info.get("case_name") or "该案件"
        fact_sheet = case_info.get("fact_sheet") or {}
        location = fact_sheet.get("case_location") or "相关现场"
        return f"接警指令：请前往{location}处置与“{case_name}”相关警情，并尽快核实现场情况。"

    @staticmethod
    def _default_first_impression(scene_name: str, dispatch_brief: str) -> str:
        if "接警" in scene_name or "报警" in scene_name:
            return "你接通后，能听到对方语气急促，正在试图说明现场发生的情况。"
        if dispatch_brief:
            return "你到场后发现现场气氛紧张，已有相关人员或群众在场，需先稳定秩序并核实情况。"
        return "你到场后先对现场环境、人员状态和异常迹象进行了初步观察。"

    def parse_case_text(self, text: str):
        default_res = {
            "case_name": "解析失败",
            "case_type": "其他",
            "case_background": self._truncate_text(text, 120) or "未提取到案件背景",
            "fact_sheet": {
                "case_time": "未明确",
                "case_location": "未明确",
                "report_time": "未明确",
                "timeline": [],
                "relationships": [],
            },
            "full_narrative": self._truncate_text(text, 500),
            "criminal_process": "未明确提及",
            "main_culprit": "未明确",
            "persons": [],
            "conflict_points": [],
            "key_facts": [],
            "hidden_info": [],
        }
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": PARSE_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
            result = self._safe_json_loads(response.choices[0].message.content, default_res)
            if not isinstance(result, dict):
                return default_res
            result.setdefault("case_name", default_res["case_name"])
            raw_case_type = result.get("case_type") or ""
            result["ai_case_type_raw"] = raw_case_type
            result["case_type"] = self.normalize_case_type(text=text, ai_case_type=raw_case_type)
            result["case_background"] = (
                result.get("case_background")
                or result.get("background")
                or default_res["case_background"]
            )
            result.setdefault("fact_sheet", default_res["fact_sheet"])
            result.setdefault("full_narrative", default_res["full_narrative"])
            result.setdefault("criminal_process", default_res["criminal_process"])
            result.setdefault("main_culprit", default_res["main_culprit"])
            result.setdefault("persons", [])
            result.setdefault("conflict_points", [])
            result.setdefault("key_facts", [])
            result.setdefault("hidden_info", [])
            return result
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
                    {"role": "user", "content": json.dumps(case_info, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
            )
            result = self._safe_json_loads(response.choices[0].message.content, default_scenes)
            if not isinstance(result, dict):
                return default_scenes

            scenes = result.get("scenes") or []
            normalized_scenes = []
            for index, scene in enumerate(scenes, start=1):
                if not isinstance(scene, dict):
                    continue
                scene_name = scene.get("scene_name") or f"训练场景{index}"
                dispatch_brief = (scene.get("dispatch_brief") or "").strip()
                first_impression = (scene.get("first_impression") or "").strip()
                normalized_scenes.append(
                    {
                        **scene,
                        "scene_name": scene_name,
                        "scene_description": scene.get("scene_description") or "围绕案件关键节点开展训练。",
                        "difficulty": scene.get("difficulty") or "中等",
                        "dispatch_brief": dispatch_brief or self._default_dispatch_brief(case_info, scene_name),
                        "first_impression": first_impression or self._default_first_impression(scene_name, dispatch_brief),
                        "roles": scene.get("roles") or [],
                        "stages": scene.get("stages") or [],
                    }
                )
            return {"scenes": normalized_scenes}
        except Exception as e:
            print(f"Error generating scenes: {e}")
            return default_scenes


workflow_service = WorkflowService()
