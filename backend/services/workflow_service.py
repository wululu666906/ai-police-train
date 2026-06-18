from __future__ import annotations

import json
import re
from typing import Any

from .llm_provider import create_json_chat_completion, extract_json_payload, extract_message_text, get_chat_model
from .persona_engine import get_behavior_archetype_defaults, infer_persona_template, normalize_compact_persona_fields
from .case_schema_service import canonicalize_person_payload, migrate_structured_data_payload
from .stage_config_service import normalize_stages

CASE_TYPE_GROUPS = {
    "纠纷求助类": ["邻里纠纷", "家庭纠纷", "情感纠纷", "劳资纠纷", "消费纠纷", "噪音扰民", "失踪求助", "自杀干预", "校园警情", "宠物纠纷"],
    "治安案件类": ["打架斗殴", "寻衅滋事", "故意伤害", "损毁财物", "醉酒闹事", "赌博", "卖淫嫖娼", "非法侵入住宅"],
    "刑事案件类": ["故意杀人", "盗窃", "抢夺", "诈骗", "电信网络诈骗", "入室盗窃", "抢劫", "敲诈勒索", "涉毒"],
    "交通警情类": ["交通事故", "酒驾醉驾", "肇事逃逸"],
}

CASE_TYPE_OPTIONS = [item for group in CASE_TYPE_GROUPS.values() for item in group] + ["其他"]

CASE_TYPE_SYNONYMS = {
    "民间纠纷": "邻里纠纷",
    "邻里矛盾": "邻里纠纷",
    "夫妻纠纷": "家庭纠纷",
    "婚恋纠纷": "情感纠纷",
    "情感矛盾": "情感纠纷",
    "工资纠纷": "劳资纠纷",
    "讨薪纠纷": "劳资纠纷",
    "消费维权": "消费纠纷",
    "扰民": "噪音扰民",
    "斗殴": "打架斗殴",
    "打架": "打架斗殴",
    "伤害": "故意伤害",
    "伤人": "故意伤害",
    "命案": "故意杀人",
    "杀人": "故意杀人",
    "偷窃": "盗窃",
    "电诈": "电信网络诈骗",
    "网络诈骗": "电信网络诈骗",
    "电信诈骗": "电信网络诈骗",
    "室内盗窃": "入室盗窃",
    "入户盗窃": "入室盗窃",
    "劫财": "抢劫",
    "抢夺财物": "抢夺",
    "勒索": "敲诈勒索",
    "毁坏财物": "损毁财物",
    "砸车": "损毁财物",
    "轻生": "自杀干预",
    "跳楼": "自杀干预",
    "车祸": "交通事故",
    "醉驾": "酒驾醉驾",
    "酒驾": "酒驾醉驾",
    "逃逸": "肇事逃逸",
    "吸毒": "涉毒",
    "贩毒": "涉毒",
}

CASE_TYPE_KEYWORDS = [
    ("电信网络诈骗", ["刷单", "验证码", "转账", "被骗", "电诈", "诈骗电话", "冒充客服", "网络诈骗"]),
    ("入室盗窃", ["撬门", "翻窗", "入户盗窃", "家中被盗", "室内盗窃"]),
    ("抢劫", ["持刀抢劫", "拦路抢劫", "暴力劫财", "飞车抢劫"]),
    ("抢夺", ["抢夺", "夺走", "趁机夺取"]),
    ("敲诈勒索", ["敲诈", "勒索", "威胁转账", "威胁给钱"]),
    ("肇事逃逸", ["撞人后逃逸", "交通逃逸", "肇事逃逸", "逃离现场"]),
    ("故意杀人", ["命案", "尸体", "死亡", "被杀", "致死", "凶杀"]),
    ("故意伤害", ["持刀伤人", "砍伤", "打伤", "轻伤", "重伤", "受伤"]),
    ("打架斗殴", ["打架", "斗殴", "互殴", "群殴"]),
    ("寻衅滋事", ["寻衅滋事", "无故滋事", "故意挑衅", "闹事"]),
    ("盗窃", ["盗窃", "偷窃", "被偷", "扒窃", "偷手机", "偷电动车"]),
    ("涉毒", ["吸毒", "贩毒", "毒品", "冰毒", "K粉"]),
    ("赌博", ["赌博", "赌资", "赌局", "赌钱"]),
    ("卖淫嫖娼", ["卖淫", "嫖娼", "色情交易"]),
    ("酒驾醉驾", ["酒驾", "醉驾", "酒后驾驶"]),
    ("交通事故", ["交通事故", "追尾", "碰撞", "车祸"]),
    ("家庭纠纷", ["家庭纠纷", "夫妻吵架", "家暴", "婆媳矛盾"]),
    ("情感纠纷", ["情感纠纷", "恋爱纠纷", "分手", "感情矛盾"]),
    ("邻里纠纷", ["邻里纠纷", "邻居", "楼上楼下", "住户争吵"]),
    ("劳资纠纷", ["讨薪", "欠薪", "工资", "工钱", "围堵工地", "劳资纠纷"]),
    ("消费纠纷", ["退款", "商家", "售后", "商品质量", "消费纠纷"]),
    ("噪音扰民", ["噪音", "扰民", "施工噪音", "音响太大"]),
    ("失踪求助", ["失踪", "走失", "找不到人", "离家出走"]),
    ("自杀干预", ["轻生", "跳楼", "自杀", "割腕", "天台"]),
    ("非法侵入住宅", ["非法侵入住宅", "强行进入住宅", "私闯民宅"]),
    ("校园警情", ["校园", "学生打架", "宿舍纠纷", "老师报警"]),
    ("宠物纠纷", ["宠物", "狗咬人", "遛狗纠纷"]),
]

BASE_PARSE_RESULT = {
    "case_name": "解析失败",
    "case_type": "其他",
    "case_background": "未提取到案件背景",
    "fact_sheet": {"case_time": "未明确", "case_location": "未明确", "report_time": "未明确", "timeline": [], "relationships": []},
    "full_narrative": "",
    "criminal_process": "未明确提取",
    "main_culprit": "未明确",
    "persons": [],
    "conflict_points": [],
    "key_facts": [],
    "hidden_info": [],
    "source_classification": "普通案件文本",
    "dispatch_brief_suggestion": "",
    "first_impression_suggestion": "",
    "transcript_summary": "",
    "evidence_points": [],
    "inconsistencies": [],
    "parse_warnings": [],
    "parse_engine": "heuristic",
}

NAME_EXTRACTION_PROMPT = """你是公安警情训练平台的人物名称识别专家。你的准确率直接影响训练系统的数据质量，误报一个非人名就会导致角色污染。

任务：从以下案件文本中，找出所有**真实人物的完整姓名**，返回一个纯 JSON 字符串数组。

核心规则（严格遵循，违者将导致系统故障）：
1. 只提取2-4个汉字的真实完整人名（如：张三、李四、王小明、赵建国）。
2. **绝对禁止**把以下任何类型当作人名输出，即使它们在文本中紧邻角色称谓或动词：
   - 地名/地点（如：某某村、东风路、向阳街、幸福小区、某某庄、某某路、某某大厦、某某巷、某某街道、某某社区、某某镇、某某乡）
   - 抽象名词/事件词（如：证言、陈述、供述、交代、案情、纠纷、口供、笔录、报警记录、报案材料、情况、材料、线索、证据）
   - 物品名称（如：电动车、手机、菜刀、木棍、汽车、钱包、自行车、砖头、铁锹、钢管、绳索）
   - 角色称谓/身份词（如：嫌疑人、犯罪嫌疑人、被害人、受害人、报警人、报案人、证人、邻居、家属、目击者、当事人、伤者、死者、对方、男子、女子、顾客、店员、保安、路人、同学、朋友、工友、老乡、房东、租客、乘客、司机、业主）
   - 行为描述词（如：争吵、打架、受伤、逃离、抓捕、调解、询问、审讯、报案、报警、追赶、推搡、辱骂、威胁、敲诈、勒索、盗窃、抢劫、诈骗）
   - 占位符名称（如：张某某、李某某、某某某、王某、赵某、刘某、陈某——只有姓氏加"某"的不算完整人名）
   - 仅称谓+姓氏（如：老王、小张、大刘、李姐、王哥、赵叔——这些不是完整姓名）
3. **姓名结构规则**：中国真实人名由「姓氏+名字」组成。确认提取的每个名字都以一个真实姓氏开头（如：王、李、张、刘、陈、杨、赵、黄、周、吴、徐、孙、马、胡、朱、郭、何、罗、高、林等）。如果无法确认，宁可漏过。
4. 同一人物只保留一个标准名称。如果文本中出现同一人的不同写法（如"张三供述"和"张三（审讯）"），只保留最简洁的标准名"张三"。
5. 如果姓名前后夹着身份、阶段、关系词或动词（如"证人张三""张三嫌疑人""张三称""张三说"），必须还原成纯人名"张三"。
6. **自我验证**：在输出前，逐个检查候选名单中的每一项——问自己"这真的是一个真实人物的人名吗？还是地名/事件词/身份词？"如果不确定，移除它。
7. **宁可漏过，绝不误报**：如果不确定某个词是否为真实人名（如只有姓氏加"某"：王某、李某），必须排除。如果文本中没有明确真实的人名，必须返回空数组 []。
8. 只输出一个合法的 JSON 数组，不要 markdown、解释或额外说明。

示例：
输入："报警人张三称，其与邻居李四因纠纷发生冲突，李四手持木棍打伤张三。"
输出：["张三", "李四"]

输入："某某村幸福小区发生一起邻里纠纷，现场无人员受伤。"
输出：[]

输入："据被害人王小花陈述，嫌疑人赵大龙在东风路持刀抢劫其手机。"
输出：["王小花", "赵大龙"]

输入："民警到场后，证言显示某某村的李某和王某因琐事发生口角。"
输出：[]（李某、王某只有姓氏加"某"，不是明确完整人名）

输入："报警人陈述称其在东风路被一名男子抢走手机。"
输出：[]（没有明确人名）

输入："嫌疑人张某因纠纷将被害人李某打伤，张某系某某村村民。"
输出：[]（张某、李某只有姓氏加"某"，不是明确完整人名）

输入："王小明与赵丽华因感情纠纷发生争吵，赵丽华将王小明电动车砸坏。"
输出：["王小明", "赵丽华"]

输入："在东风路发生纠纷，幸福小区的保安和业主因停车费问题争吵。"
输出：[]（没有明确人名）

输入："民警到达现场后发现店主张强与顾客刘芳因商品质量问题发生争执。"
输出：["张强", "刘芳"]

输入："伤者已被送医，死者身份待确认，现场证言已收集完毕。"
输出：[]（"伤者""死者""证言"都不是人名）

输入："老公王磊和老婆赵敏因家庭琐事发生争吵。"
输出：["王磊", "赵敏"]
"""


PARSE_PROMPT = f"""你是“公安警情训练平台”的案件结构化解析专家。你的输出会直接进入管理员的“AI 解析结果预览”页，管理员会把其中一部分当作 AI 建议值，再人工确认最终发布值。

你的任务：仅依据输入文本，把案件整理成训练平台需要的结构化 JSON。

硬性要求：
1. 只能依据输入文本，不得脑补、补剧情、补人物关系、补时间地点。
2. 案件类型必须从以下列表中选择最接近的一项：{json.dumps(CASE_TYPE_OPTIONS, ensure_ascii=False)}
3. 如果标题无法明确提炼，case_name 写“未明确”；不要自己编一个文学化标题。
4. 时间、地点、人物身份、关系链不明确时，写“未明确”或空数组，不得猜测。
5. person_status / status 只能使用：正常、受伤可交流、昏迷、重伤无法交流、死亡。
6. dispatch_brief_suggestion 只能写“接警电话或文本中当下可知”的信息，不能混入到场后观察结果。
7. first_impression_suggestion 只能写“民警到场第一眼可能观察到”的信息，不能写尚未核实的内心推断。
8. transcript_summary 要压缩成便于管理员复核的客观摘要，不要写成评论。
9. evidence_points 只提取文本里已经出现的证据、物品、监控、伤情、录音录像、目击线索。
10. inconsistencies 只写文本里已经出现或可直接看出的前后不一致、表述冲突、信息缺口。
11. parse_warnings 必须列出所有会影响训练建模的重要不确定性，例如“关键人物身份未明确”“案发时间缺失”“材料像摘要而非完整案情”。
12. parse_engine 固定输出为 "ai"。
13. 只输出一个合法 JSON 对象，不要输出 markdown、解释或额外说明。
14. case_background 必须是给管理员预览的案件背景，优先 120-300 字，交代警情来源、时间、地点、人物、起因、已发生行为、后果和当前风险/争议；信息不足时仍要基于原文客观概括，并在 parse_warnings 写出缺口。
15. fact_sheet.timeline 至少尝试提炼 2-6 条时间线短句；fact_sheet.relationships 至少尝试提炼人物关系、冲突关系或“关系未明确”的核实点。
16. 如果输出长度受限，优先保证 case_name、case_type、case_background、fact_sheet、persons、key_facts、transcript_summary 完整。

persons 字段要求：
- persons 是人物数组，每个人物都要尽量输出这些字段：
  name, role, role_type, status, behavior_archetype, police_attitude,
  current_goal, core_concern, trigger_points, calming_points,
  init_emotion, init_trust, knows_facts, does_not_know, hidden_truths
- 如果原文对人物说话特点、互动风格很明确，也可以补 interaction_style / personality / speaking_style，但这三项不是硬性必填。
- name 只能写“纯人名”或明确身份称谓本身，不要把“称、表示、供述、位于、发现、与某某因纠纷”等后续案情一起带进名字字段。

        - 【禁止用非人名代替】严禁将以下类型当作 name 输出：
          - 地名（如：某某村、东风路、向阳街、幸福小区、某某庄、某某路）
          - 抽象名词/事件词（如：证言、陈述、供述、纠纷、口供、笔录、报警记录）
          - 物品名称（如：电动车、手机、菜刀、木棍、汽车、钱包）
          - 角色称谓/身份词（如：嫌疑人、被害人、报警人、证人、邻居、目击者、男子、女子、当事人、伤者、死者）
          - 行为描述词（如：争吵、打架、受伤、调解、询问、审讯）
          - 占位符名称（如：张某某、李某某、王某、赵某——仅姓氏加"某"不算完整人名）
        - name 必须是"姓氏+名字"结构的真实人名（如：王小明、张三、李四、赵建国），如果不确定是否为真实人名，宁可不输出。
        - 同一人物在所有场景中必须使用完全相同的 name，不得因场景变化在名称中追加身份后缀（如写入"张三(审讯)"或"张三嫌疑人"是错误的；只能使用纯人名"张三"，身份写在 role_type 字段中）。

- 如果文本足够支撑，就尽量把这些字段填具体，不要只写“待核实”。
- behavior_archetype 优先从这些类型里选最接近的一种：求助配合型、委屈宣泄型、谨慎回避型、防御切责型、强硬对抗型、醉酒失控型、绝望封闭型、围观起哄型。
- police_attitude 只写人物面对警方时的基本姿态，例如：主动求助、试探观望、防备排斥、敌对抵触。
- knows_facts 只写该人物确实知道、见到、听到或参与过的事实。
- does_not_know 只写该人物不知道、没看见或无法确认的部分，避免角色无所不知。
- hidden_truths 只写其主观上可能隐瞒、拖延或避重就轻的事实；如果原文完全没有依据，可以留空。
- current_goal 写“此刻最想保住或达成什么”。
- core_concern 写“最怕什么、最痛的后果或现实软肋”。
- trigger_points 用短句列表写“问到哪些点容易情绪波动或改口”。
- calming_points 用短句列表写“说到哪些点、采取什么沟通方式时更容易稳住或继续交流”。

输出风格要求：
- 面向训练平台，而不是卷宗归档。
- 优先抽取“可训练、可问询、可复核”的信息。
- 不要把 AI 建议值伪装成最终定论。"""

TRANSCRIPT_PARSE_PROMPT = f"""你是“公安警情训练平台”的公安笔录与案件材料解析专家。你的结果会被管理员作为 AI 建议值复核后再发布，因此必须尽量稳、尽量可追溯。

你的任务：把提取出的正文整理成训练案件结构 JSON。

硬性要求：
1. 只能依据原文输出，不得脑补。
2. source_classification 只能是：笔录、混合材料、非标准文本。
3. 案件类型必须从以下列表中选择最接近的一项：{json.dumps(CASE_TYPE_OPTIONS, ensure_ascii=False)}
4. case_name 只允许从正文中概括，不得虚构吸引眼球的标题；无法明确时写“未明确”。
5. dispatch_brief_suggestion 只能写接警时可知信息；first_impression_suggestion 只能写到场观察可知信息。
6. transcript_summary 要总结“谁、何时、何地、发生了什么、当前争议点/风险点是什么”。
7. evidence_points 只保留正文中出现的证据、物品、视频、伤情、电话记录、目击线索等客观线索。
8. inconsistencies 只保留正文里真实存在的矛盾、冲突口径、信息缺口。
9. parse_warnings 要明确指出会影响训练生成的缺口，如“材料只有单方陈述”“缺少时间线”“关键角色状态不清”。
10. parse_engine 固定输出为 "ai"。
11. 只输出一个合法 JSON 对象，不要附带解释。
12. case_background 必须是给管理员预览的案件背景，优先 120-300 字，交代材料来源、时间、地点、人物、核心经过、后果、当前争议或风险；不要只复制笔录标题。
13. fact_sheet.timeline 至少尝试提炼 2-6 条时间线短句；fact_sheet.relationships 至少尝试提炼人物关系、冲突关系或待核实关系。
14. 如果输出长度受限，优先保证 case_name、case_type、case_background、fact_sheet、persons、key_facts、transcript_summary 完整。
15. 如果正文包含“【文档识别结果】”“--- 块 n / type / location ---”“[表格]”“[图片OCR]”等标记，它们是 OCR/文档识别保真标记，不是案情原文；解析时必须利用这些标记恢复原文顺序、表格关系和图片文字，不要把标记本身当成人物、地点或案情事实。

persons 字段要求：
- persons 中每个人尽量输出：
  name, role, role_type, status, behavior_archetype, police_attitude,
  current_goal, core_concern, trigger_points, calming_points,
  init_emotion, init_trust, knows_facts, does_not_know, hidden_truths
- 如果笔录里明确体现出说话方式、稳定性格底色或明显互动风格，也可以补 interaction_style / personality / speaking_style。
- name 只能保留纯人名，不要输出“报警人李某称”“张某因”“王某和其妻子”等带后缀情节的长字符串。

        - 【禁止用非人名代替】严禁将以下类型当作 name 输出：
          - 地名（如：某某村、东风路、向阳街、幸福小区、某某庄、某某路）
          - 抽象名词/事件词（如：证言、陈述、供述、纠纷、口供、笔录、报警记录）
          - 物品名称（如：电动车、手机、菜刀、木棍、汽车、钱包）
          - 角色称谓/身份词（如：嫌疑人、被害人、报警人、证人、邻居、目击者、男子、女子、当事人、伤者、死者）
          - 行为描述词（如：争吵、打架、受伤、调解、询问、审讯）
          - 占位符名称（如：张某某、李某某、王某、赵某——仅姓氏加"某"不算完整人名）
        - name 必须是"姓氏+名字"结构的真实人名（如：王小明、张三、李四、赵建国），如果不确定是否为真实人名，宁可不输出。
        - 同一人物在所有场景中必须使用完全相同的 name，不得因场景变化在名称中追加身份后缀（如写入"张三(审讯)"或"张三嫌疑人"是错误的；只能使用纯人名"张三"，身份写在 role_type 字段中）。

- 如果笔录里体现出其回避、护短、怕牵连、怕处罚、怕家属知道、怕赔偿、怕失面子等倾向，要尽量体现在 behavior_archetype / police_attitude / current_goal / core_concern / trigger_points / calming_points 这些字段里。
- 所有内容都必须有文本依据，不能为了戏剧性乱补剧情。

额外要求：
- 如果是笔录，不要把询问人口吻误写成案件事实。
- 如果是混合材料，优先保留可验证事实，把主观评价放进 parse_warnings 或 transcript_summary 的“待核实”语气中。"""

SCENE_GEN_PROMPT = """你是公安警情训练场景设计专家。你的结果将直接进入管理员的"场景生成"预览页，管理员会人工复核后发布。

任务：严格基于输入案件 JSON，生成 2 到 3 个适合警务训练的平台场景，最多不超过 3 个。

硬性要求：
1. 只能使用输入案件中的事实、人物、地点、关系和风险点，不得虚构新人物、新地点、新案件类型、新证据。
2. 已死亡、昏迷、重伤无法交流的人物绝不能出现在 roles 中作为主对话对象。roles 只能用案件 persons 表中已有的 name（纯人名），不得编造新名字。
3. 场景必须符合处警流程，优先组织成"接警研判/现场处置/重点问询或时间线压实"等渐进路径。
4. 每个场景都必须有清晰的 stage 列表，stage_name 和 stage_goal 要能支撑多轮问答，不能空泛重复。
5. 场景目标要鼓励"先核实、再追问、再压实矛盾"，不要让角色一两轮就把全部核心事实说完。
6. dispatch_brief 只能写该场景开始前警方已知内容；first_impression 只能写该场景一进入时可观察内容。不得把案件完整事实全写在同一个场景的 dispatch_brief 中。
7. difficulty 要和信息复杂度、人物对抗性、情绪强度匹配，优先使用"低 / 中等 / 高"。
8. 如果输入材料本身信息不足，也要尽量在现有事实上组织可训练场景，但不能靠脑补补齐。
9. 每个 stage 除了 stage_name / stage_goal，还应尽量补 assessment_points、action_catalog、completion_rules、end_conditions。
10. assessment_points 要体现真正能训练能力提升的检查点，不要只复述 stage_goal。每条 assessment_point 包含 label（核心能力）、content（80-200字具体题目+达标标准）、category（procedure/risk/evidence）、required（布尔）、weight（必考12-15/选考8-10）、keywords（2-5个）。
11. action_catalog 要优先覆盖执法动作、取证动作、收尾动作，不要只写说话动作。
12. end_conditions 要体现这个场景在真实流程下何时应结束，并给出 closing_script。
13. 只输出一个包含 scenes 的合法 JSON 对象，不要附加解释。

场景设计偏好：
- 每个场景都应有明确主任务。
- 角色要有可问询空间、可压实的矛盾点或风险点。
- 多个场景之间要形成递进，而不是简单改写同一段话。

输出 JSON 结构参考：
{
  "scenes": [
    {
      "scene_name": "接警研判",
      "scene_description": "学员接到报案电话，需快速核实时间、地点、人员身份和现场风险。",
      "difficulty": "低",
      "dispatch_brief": "接警台接到一男子来电，称在某小区发生冲突，具体情况不明。",
      "first_impression": "",
      "roles": ["报警人姓名"],
      "stages": [
        {
          "stage_name": "信息初核",
          "stage_goal": "核实报警人身份和事发地点，判断是否需要立即出警。",
          "assessment_points": [
            {
              "label": "初判警情等级",
              "content": "学员应判断是否存在人身危险，追问至少2项风险要素并给出处置倾向。怎样算完成：回放时能听出你给出了明确的派警判断。",
              "category": "risk",
              "required": true,
              "weight": 14,
              "keywords": ["风险判断", "派警"]
            }
          ],
          "action_catalog": [
            {"label": "接警登记", "type": "physical", "aliases": ["记录警情", "填写接警单"], "counts_for": []}
          ],
          "completion_rules": {"min_user_turns": 2, "required_point_ids": [], "required_action_ids": []},
          "end_conditions": {"must_complete_current_stage": false, "closure_actions": [], "closing_script": ""}
        }
      ]
    }
  ]
}"""


class WorkflowService:
    @staticmethod
    def _append_warning(result: dict[str, Any], message: str):
        warnings = result.get("parse_warnings")
        if not isinstance(warnings, list):
            warnings = []
        if message and message not in warnings:
            warnings.append(message)
        result["parse_warnings"] = warnings
        return result

    @staticmethod
    def _safe_json_loads(value: Any, default: Any):
        if isinstance(value, (dict, list)):
            return value
        if value in (None, ""):
            return default
        try:
            return json.loads(value)
        except Exception:
            extracted = extract_json_payload(value)
            return extracted if extracted is not None else default

    @staticmethod
    def _split_lines(text: str) -> list[str]:
        return [line.strip() for line in str(text or "").splitlines() if line.strip()]

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            clean = str(item or "").strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            result.append(clean)
        return result

    @staticmethod
    def _default_scene_name(index: int) -> str:
        names = {1: "接警研判", 2: "现场初查", 3: "重点询问"}
        return names.get(index, f"训练场景{index}")

    @staticmethod
    def _is_placeholder(value: Any) -> bool:
        text = str(value or "").strip()
        return text in {"", "未明确", "未知", "待核实", "未提取到案件背景", "未明确提取", "其他"}

    @staticmethod
    def _normalize_case_type_name(value: str) -> str:
        raw = str(value or "").strip()
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
        if direct and direct != "其他":
            return direct
        combined = f"{ai_case_type}\n{text}"
        scores = self._case_type_scores(combined)
        if scores:
            return max(scores.items(), key=lambda item: item[1])[0]
        return direct or "其他"

    def _case_type_scores(self, text: str) -> dict[str, int]:
        scores: dict[str, int] = {}
        for case_type, keywords in CASE_TYPE_KEYWORDS:
            score = sum(1 for keyword in keywords if keyword in text)
            if score:
                scores[case_type] = score
        return scores

    def _best_case_type_from_text(self, text: str, fallback: str = "其他") -> str:
        scores = self._case_type_scores(text)
        if not scores:
            return fallback
        return max(scores.items(), key=lambda item: item[1])[0]

    @staticmethod
    def _normalize_person_status(status: str) -> str:
        value = str(status or "").strip()
        if not value:
            return "正常"
        if value in {"正常", "受伤可交流", "昏迷", "重伤无法交流", "死亡"}:
            return value
        if any(token in value for token in ["死亡", "身亡", "尸体", "当场死亡", "已死亡", "被杀", "遇害"]):
            return "死亡"
        if any(token in value for token in ["昏迷", "意识不清", "失去意识"]):
            return "昏迷"
        if any(token in value for token in ["重伤", "伤势严重", "无法交流", "不能说话"]):
            return "重伤无法交流"
        if any(token in value for token in ["轻伤", "轻微伤", "受伤", "擦伤", "划伤", "意识清楚", "神志清楚", "可交流"]):
            return "受伤可交流"
        return "正常"

    @staticmethod
    def _is_speakable_status(status: str) -> bool:
        return WorkflowService._normalize_person_status(status) not in {"死亡", "昏迷", "重伤无法交流"}

    @staticmethod
    def _guess_role_type(role: str) -> str:
        value = str(role or "")
        if any(token in value for token in ["嫌疑", "犯罪", "被告"]):
            return "嫌疑人"
        if any(token in value for token in ["受害", "被害", "伤者", "死者"]):
            return "被害人"
        if any(token in value for token in ["报警", "报案", "证人", "邻居", "家属", "目击"]):
            return "证人"
        if "民警" in value or "警察" in value:
            return "民警"
        return "相关人员"

    @staticmethod
    def _infer_person_defaults(person: dict[str, Any]) -> dict[str, Any]:
        person = person or {}

        def score(value: Any, default: int) -> int:
            if value in (None, ""):
                return default
            if isinstance(value, bool):
                return default
            try:
                parsed = int(float(str(value).strip()))
            except (TypeError, ValueError):
                return default
            return max(0, min(100, parsed))

        role_type = str(person.get("role_type") or person.get("role") or "相关人员").strip()
        status = str(person.get("status") or "正常").strip()
        compact_fields = normalize_compact_persona_fields(person)
        behavior_archetype = compact_fields.get("behavior_archetype") or "求助配合型"
        archetype_defaults = get_behavior_archetype_defaults(behavior_archetype)
        interaction_style = str(person.get("interaction_style") or "").strip()
        personality = str(person.get("personality") or "").strip()
        speaking_style = str(person.get("speaking_style") or "").strip()
        hidden_truths = person.get("hidden_truths") if isinstance(person.get("hidden_truths"), list) else []
        knows_facts = person.get("knows_facts") if isinstance(person.get("knows_facts"), list) else []

        if not interaction_style or interaction_style == "待核实":
            if archetype_defaults.get("interaction_style"):
                interaction_style = str(archetype_defaults.get("interaction_style") or "").strip()
            elif role_type == "嫌疑人":
                interaction_style = "对抗型" if hidden_truths else "观察型"
            elif role_type == "证人":
                interaction_style = "观察型"
            elif role_type in {"被害人", "受害人"}:
                interaction_style = "情绪型"
            else:
                interaction_style = "配合型"

        if not personality or personality == "待核实":
            if archetype_defaults.get("personality"):
                personality = str(archetype_defaults.get("personality") or "").strip()
            elif role_type == "嫌疑人":
                personality = "防备心强，先考虑自保和切割责任"
            elif role_type == "证人":
                personality = "谨慎怕事，不愿轻易卷入冲突中心"
            elif role_type in {"被害人", "受害人"}:
                personality = "委屈敏感，希望先被理解和保护"
            else:
                personality = "有现实顾虑，先看警方态度再决定说多少"

        if not speaking_style or speaking_style in {"常规", "陈述型", "待核实"}:
            if archetype_defaults.get("speaking_style"):
                speaking_style = str(archetype_defaults.get("speaking_style") or "").strip()
            elif role_type == "嫌疑人":
                speaking_style = "先试探再回答，敏感点容易绕开或淡化"
            elif role_type == "证人":
                speaking_style = "碎片化回忆，先说记得住的部分"
            elif role_type in {"被害人", "受害人"}:
                speaking_style = "带情绪地描述自身遭遇，反复强调受损和委屈"
            else:
                speaking_style = "口语化陈述，先说对自己有利的部分"

        init_emotion = person.get("init_emotion")
        if not isinstance(init_emotion, int):
            emotion_level = str(person.get("emotion_level") or "").strip()
            if emotion_level == "高":
                init_emotion = 84
            elif emotion_level == "低":
                init_emotion = 36
            elif archetype_defaults.get("init_emotion") is not None:
                init_emotion = int(archetype_defaults.get("init_emotion") or 50)
            elif status in {"受伤可交流"} or role_type in {"被害人", "受害人"}:
                init_emotion = 72
            elif role_type == "嫌疑人":
                init_emotion = 64 if hidden_truths else 56
            elif role_type == "证人":
                init_emotion = 52
            else:
                init_emotion = 50

        init_trust = person.get("init_trust")
        if not isinstance(init_trust, int):
            cooperation_level = str(person.get("cooperation_level") or "").strip()
            if cooperation_level == "高":
                init_trust = 66
            elif cooperation_level == "低":
                init_trust = 18
            elif archetype_defaults.get("init_trust") is not None:
                init_trust = int(archetype_defaults.get("init_trust") or 30)
            elif interaction_style == "对抗型":
                init_trust = 18
            elif interaction_style == "观察型":
                init_trust = 26
            elif interaction_style == "情绪型":
                init_trust = 30
            else:
                init_trust = 35 if knows_facts else 30

        init_risk = person.get("init_risk")
        if not isinstance(init_risk, int):
            risk_level = str(person.get("risk_level") or "").strip()
            if risk_level == "高":
                init_risk = 82
            elif risk_level == "低":
                init_risk = 22
            elif archetype_defaults.get("init_risk") is not None:
                init_risk = int(archetype_defaults.get("init_risk") or 50)
            elif status in {"昏迷", "重伤无法交流"}:
                init_risk = 68
            elif interaction_style == "对抗型":
                init_risk = 72
            elif interaction_style == "情绪型":
                init_risk = 60
            else:
                init_risk = 44

        init_expression_clarity = person.get("init_expression_clarity")
        if not isinstance(init_expression_clarity, int):
            clarity_level = str(person.get("clarity_level") or "").strip()
            if clarity_level == "高":
                init_expression_clarity = 82
            elif clarity_level == "低":
                init_expression_clarity = 22
            elif archetype_defaults.get("init_expression_clarity") is not None:
                init_expression_clarity = int(archetype_defaults.get("init_expression_clarity") or 52)
            elif any(token in speaking_style for token in ["断裂", "含糊", "跑题", "反复", "混乱"]):
                init_expression_clarity = 26
            elif any(token in speaking_style for token in ["谨慎", "冷静", "具体", "清楚"]):
                init_expression_clarity = 72
            else:
                init_expression_clarity = 52

        return {
            "interaction_style": interaction_style,
            "personality": personality,
            "speaking_style": speaking_style,
            "init_emotion": score(init_emotion, 50),
            "init_trust": score(init_trust, 30),
            "init_risk": score(init_risk, 44),
            "init_expression_clarity": score(init_expression_clarity, 52),
        }

    @staticmethod
    def _clean_person(person: dict[str, Any]) -> dict[str, Any]:
        person = person or {}
        inferred_defaults = WorkflowService._infer_person_defaults(person)
        compact_fields = normalize_compact_persona_fields(person)
        scene_behavior_mode = str(compact_fields.get("scene_behavior_mode") or person.get("scene_behavior_mode") or "核查取证型").strip() or "核查取证型"
        cleaned = {
            "person_id": str(person.get("person_id") or "").strip(),
            "name": WorkflowService._normalize_person_name(person.get("name")) or "未明确",
            "aliases": person.get("aliases") if isinstance(person.get("aliases"), list) else [],
            "role": str(person.get("role") or "相关人员").strip(),
            "role_type": str(person.get("role_type") or WorkflowService._guess_role_type(person.get("role"))).strip() or "相关人员",
            "interaction_style": str(person.get("interaction_style") or inferred_defaults["interaction_style"]).strip() or inferred_defaults["interaction_style"],
            "personality": inferred_defaults["personality"],
            "speaking_style": inferred_defaults["speaking_style"],
            "init_emotion": inferred_defaults["init_emotion"],
            "init_trust": inferred_defaults["init_trust"],
            "init_risk": inferred_defaults["init_risk"],
            "init_expression_clarity": inferred_defaults["init_expression_clarity"],
            "status": WorkflowService._normalize_person_status(person.get("status")),
            "behavior_archetype": str(compact_fields.get("behavior_archetype") or "求助配合型").strip(),
            "police_attitude": str(compact_fields.get("police_attitude") or "").strip(),
            "knows_facts": person.get("knows_facts") if isinstance(person.get("knows_facts"), list) else [],
            "does_not_know": person.get("does_not_know") if isinstance(person.get("does_not_know"), list) else [],
            "hidden_truths": person.get("hidden_truths") if isinstance(person.get("hidden_truths"), list) else [],
            "iq_level": str(person.get("iq_level") or "中等").strip(),
            "eq_level": str(person.get("eq_level") or "中等").strip(),
            "lying_ability": str(person.get("lying_ability") or "一般").strip(),
            "weakness": str(person.get("weakness") or compact_fields.get("core_concern") or "").strip(),
            "self_image": str(person.get("self_image") or "").strip(),
            "current_goal": str(compact_fields.get("current_goal") or "").strip(),
            "core_concern": str(compact_fields.get("core_concern") or "").strip(),
            "relationship_pressure": compact_fields.get("relationship_pressure") if isinstance(compact_fields.get("relationship_pressure"), list) else [],
            "surface_stance": str(compact_fields.get("surface_stance") or "").strip(),
            "pressure_response": str(compact_fields.get("pressure_response") or "").strip(),
            "trigger_points": compact_fields.get("trigger_points") if isinstance(compact_fields.get("trigger_points"), list) else [],
            "calming_points": compact_fields.get("calming_points") if isinstance(compact_fields.get("calming_points"), list) else [],
            "scene_behavior_mode": scene_behavior_mode,
            "emotion_level": str(compact_fields.get("emotion_level") or person.get("emotion_level") or "中").strip() or "中",
            "cooperation_level": str(compact_fields.get("cooperation_level") or person.get("cooperation_level") or "中").strip() or "中",
            "risk_level": str(compact_fields.get("risk_level") or person.get("risk_level") or "中").strip() or "中",
            "clarity_level": str(compact_fields.get("clarity_level") or person.get("clarity_level") or "中").strip() or "中",
            "current_need": str(person.get("current_need") or compact_fields.get("current_goal") or "").strip(),
            "authority_attitude": str(person.get("authority_attitude") or compact_fields.get("police_attitude") or compact_fields.get("pressure_response") or "").strip(),
            "stress_response": str(person.get("stress_response") or compact_fields.get("pressure_response") or "").strip(),
            "protected_targets": person.get("protected_targets") if isinstance(person.get("protected_targets"), list) else [],
            "feared_people": person.get("feared_people") if isinstance(person.get("feared_people"), list) else [],
            "conflict_targets": person.get("conflict_targets") if isinstance(person.get("conflict_targets"), list) else [],
            "feared_consequences": person.get("feared_consequences") if isinstance(person.get("feared_consequences"), list) else [],
            "trigger_topics": compact_fields.get("trigger_points") if isinstance(compact_fields.get("trigger_points"), list) else [],
            "coping_patterns": person.get("coping_patterns") if isinstance(person.get("coping_patterns"), list) else [],
            "public_mask": str(person.get("public_mask") or compact_fields.get("surface_stance") or "").strip(),
            "private_drive": str(person.get("private_drive") or compact_fields.get("current_goal") or "").strip(),
            "known_key_points": compact_fields.get("known_key_points") if isinstance(compact_fields.get("known_key_points"), list) else [],
            "withheld_key_points": compact_fields.get("withheld_key_points") if isinstance(compact_fields.get("withheld_key_points"), list) else [],
            "conflict_core": compact_fields.get("conflict_core") if isinstance(compact_fields.get("conflict_core"), list) else [],
            "acceptable_outcomes": compact_fields.get("acceptable_outcomes") if isinstance(compact_fields.get("acceptable_outcomes"), list) else [],
            "no_go_topics": compact_fields.get("no_go_topics") if isinstance(compact_fields.get("no_go_topics"), list) else [],
            "trigger_sources": compact_fields.get("trigger_sources") if isinstance(compact_fields.get("trigger_sources"), list) else [],
            "concerned_targets": compact_fields.get("concerned_targets") if isinstance(compact_fields.get("concerned_targets"), list) else [],
            "taboo_actions": compact_fields.get("taboo_actions") if isinstance(compact_fields.get("taboo_actions"), list) else [],
            "escalation_actions": compact_fields.get("escalation_actions") if isinstance(compact_fields.get("escalation_actions"), list) else [],
            "deescalation_conditions": compact_fields.get("deescalation_conditions") if isinstance(compact_fields.get("deescalation_conditions"), list) else [],
            "impairment_state": str(compact_fields.get("impairment_state") or person.get("impairment_state") or "").strip(),
            "persona_template_version": "minimal_v3",
        }
        cleaned.update(infer_persona_template({**person, **cleaned}))
        canonical_cleaned, _ = canonicalize_person_payload(cleaned)
        return canonical_cleaned

    @staticmethod
    def _merge_person_record(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
        for key, value in source.items():
            if value in (None, ""):
                continue
            if isinstance(value, list):
                existing = target.get(key) if isinstance(target.get(key), list) else []
                merged = list(existing)
                for item in value:
                    if item not in merged:
                        merged.append(item)
                target[key] = merged
                continue
            if key == "role_type" and target.get(key) in {"", None, "相关人员"} and value:
                target[key] = value
                continue
            if target.get(key) in (None, ""):
                target[key] = value
        return target

    def standardize_person_records(self, persons: Any) -> list[dict[str, Any]]:
        if not isinstance(persons, list):
            return []
        standardized: list[dict[str, Any]] = []
        by_name: dict[str, dict[str, Any]] = {}
        next_index = 1
        for item in persons:
            if not isinstance(item, dict):
                continue
            cleaned = self._clean_person(item)
            name = str(cleaned.get("name") or "").strip()
            if not name or not self._is_valid_person_name(name):
                continue
            raw_name = str(item.get("name") or "").strip()
            aliases = cleaned.get("aliases") if isinstance(cleaned.get("aliases"), list) else []
            if raw_name and raw_name != name and raw_name not in aliases:
                aliases = [*aliases, raw_name]
            cleaned["aliases"] = aliases
            if name in by_name:
                self._merge_person_record(by_name[name], cleaned)
                continue
            if not str(cleaned.get("person_id") or "").strip():
                cleaned["person_id"] = f"P{next_index:03d}"
            next_index += 1
            by_name[name] = cleaned
            standardized.append(cleaned)
        return standardized

    def canonicalize_role_names(self, roles: Any, persons: Any) -> list[str]:
        if isinstance(roles, str):
            source_roles = [roles]
        elif isinstance(roles, list):
            source_roles = roles
        else:
            source_roles = []
        if not source_roles or not isinstance(persons, list):
            return []

        name_map: dict[str, str] = {}
        for person in persons:
            if not isinstance(person, dict):
                continue
            canonical_name = str(person.get("name") or "").strip()
            if not canonical_name:
                continue
            name_map[canonical_name] = canonical_name
            for alias in person.get("aliases") or []:
                alias_text = str(alias or "").strip()
                if alias_text:
                    name_map[alias_text] = canonical_name

        result: list[str] = []
        for role in source_roles:
            raw_name = str(role or "").strip()
            if not raw_name:
                continue
            normalized_name = self._normalize_person_name(raw_name) or raw_name
            canonical_name = name_map.get(raw_name) or name_map.get(normalized_name)
            if canonical_name and canonical_name not in result:
                result.append(canonical_name)
        return result

    def canonicalize_role_name(self, role: Any, persons: Any) -> str:
        names = self.canonicalize_role_names([role], persons)
        return names[0] if names else ""

    # Most common Chinese surnames (~150) for name validation
    COMMON_SURNAMES = frozenset({
        "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
        "徐", "孙", "马", "胡", "朱", "郭", "何", "罗", "高", "林",
        "梁", "宋", "郑", "谢", "韩", "唐", "冯", "于", "董", "萧",
        "程", "曹", "袁", "邓", "许", "傅", "沈", "曾", "彭", "吕",
        "苏", "卢", "蒋", "蔡", "贾", "丁", "魏", "薛", "叶", "阎",
        "余", "潘", "杜", "戴", "夏", "钟", "汪", "田", "任", "姜",
        "范", "方", "石", "姚", "谭", "廖", "邹", "熊", "金", "陆",
        "郝", "孔", "白", "崔", "康", "毛", "邱", "秦", "江", "史",
        "顾", "侯", "邵", "孟", "龙", "万", "段", "漕", "钱", "汤",
        "尹", "黎", "易", "常", "武", "乔", "贺", "赖", "龚", "文",
        "庞", "樊", "殷", "施", "陶", "洪", "翟", "安", "颜", "倪",
        "严", "牛", "温", "芦", "季", "俞", "章", "鲁", "葛", "伍",
        "韦", "申", "尤", "毕", "聂", "丛", "焦", "向", "柳", "邢",
        "岳", "齐", "欧", "祝", "尚", "梅", "莫", "佘", "牟", "练",
    })

    # Names that are not real person names (role labels, objects, places, events)
    BAD_TOKENS = frozenset({
        "男子", "女子", "男人", "女人", "对方", "一名", "一位", "民警", "警方", "警察",
        "嫌疑人", "犯罪嫌疑人", "被害人", "受害人", "报警人", "报案人", "证言", "陈述",
        "供述", "交代", "笔录", "口供", "某某", "目击者", "家属", "邻居", "当事人",
        "伤者", "死者", "纠纷", "冲突", "争吵", "警情", "案情", "案件", "现场",
        "报警记录", "报案材料", "询问记录", "调解记录", "情况", "材料",
        "线索", "证据", "监控", "录像", "视频", "照片",
        "电动车", "手机", "菜刀", "木棍", "汽车", "钱包", "自行车",
        "店长", "顾客", "店员", "保安", "路人", "同学", "朋友",
        "工友", "老乡", "房东", "租客", "乘客", "司机", "业主",
        "物业", "领导", "同事", "网友", "男方", "女方", "双方",
        "询问", "审讯", "调解", "抓捕", "调查", "侦查",
        "某某村", "某某路", "某某街",
        "打伤", "刺伤", "砍伤", "烧伤", "砸伤", "撞伤",
    })

    @staticmethod
    def _is_valid_person_name(name: str) -> bool:
        clean = WorkflowService._normalize_person_name(name)
        if not clean or not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", clean):
            return False
        # Reject known non-person tokens
        if clean in WorkflowService.BAD_TOKENS:
            return False
        # Reject names ending with location/place suffixes
        place_suffixes = ("村", "路", "街", "镇", "乡", "县", "区", "市", "省", "巷", "号", "院", "所", "站", "店", "楼", "室", "桥", "路口", "小区", "学校", "医院", "商场", "广场", "仓库", "大厦", "花园", "公寓")
        if any(clean.endswith(suffix) for suffix in place_suffixes):
            return False
        # Reject names starting with ambiguous prefix characters
        place_prefixes = ("某", "该", "本", "各", "全", "原", "被", "涉")
        if clean[0] in place_prefixes:
            return False
        # Surname validation: first character must be a known Chinese surname
        if clean[0] not in WorkflowService.COMMON_SURNAMES:
            return False
        return True

    @staticmethod
    def _normalize_person_name(name: Any) -> str:
        clean = str(name or "").strip()
        if not clean:
            return ""

        clean = re.sub(r"[（(][^()（）]{0,20}[)）]", "", clean).strip()
        clean = re.sub(
            r"^(?:一名|一位|该|报警人|报案人|被害人|受害人|嫌疑人|犯罪嫌疑人|证人|家属|邻居|目击者|伤者|死者|民警|男子|女子)+[:：]?",
            "",
            clean,
        ).strip()
        clean = re.sub(r"(?:称|说|表示|反映|供述|陈述|介绍|联系|发现|报警|报案|哭诉|求助|证言|口供|笔录|交代|讲述|回忆|证实)$", "", clean).strip()
        clean = re.sub(r"(?:嫌疑人|犯罪嫌疑人|证人|报警人|报案人|被害人|受害人|当事人|家属|邻居|目击者|伤者|死者)$", "", clean).strip()

        prefix_match = re.match(r"^([\u4e00-\u9fa5]{2,4})(?=称|说|表示|反映|供述|陈述|介绍|与|和|因|于|在|被|将|把|向|对|及|并|后|时|处|，|。|、|：|:|$)", clean)
        if prefix_match:
            clean = prefix_match.group(1)

        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", clean):
            return clean
        return ""

    @staticmethod
    def _extract_case_name(text: str) -> str:
        for line in WorkflowService._split_lines(text)[:8]:
            cleaned = re.sub(r"^[#>\-\*\d\.\s、:：]+", "", line).strip("：: ")
            if not cleaned:
                continue
            if any(token in cleaned for token in ["笔录", "记录", "问：", "答：", "第", "页"]):
                continue
            if re.match(r"^(报警时间|接警时间|报案时间|案发时间|案发地点|地点|报警人|报案人|受害人|被害人|嫌疑人)[：: ]", cleaned):
                continue
            if len(cleaned) <= 40:
                return cleaned
        sentence = re.split(r"[。！？\n]", str(text or "").strip())[0].strip()
        return sentence[:30] if sentence else "未命名案件"

    @staticmethod
    def _extract_fact_value(text: str, patterns: list[str], default: str = "未明确") -> str:
        for pattern in patterns:
            match = re.search(pattern, str(text or ""), flags=re.IGNORECASE)
            if not match:
                continue
            value = next((item for item in match.groups() if item), "")
            value = str(value).strip("：:，,。 ")
            if value:
                return value[:80]
        return default

    @staticmethod
    def _sentence_chunks(text: str, limit: int = 80) -> list[str]:
        chunks: list[str] = []
        for raw_line in str(text or "").replace("\r", "\n").splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            for part in re.split(r"(?<=[。！？!?；;])", line):
                clean = part.strip(" \t-—")
                if not clean:
                    continue
                if len(clean) > 180:
                    for subpart in re.split(r"[，,]", clean):
                        subpart = subpart.strip()
                        if subpart:
                            chunks.append(subpart[:180])
                else:
                    chunks.append(clean[:180])
                if len(chunks) >= limit:
                    return WorkflowService._dedupe(chunks)
        return WorkflowService._dedupe(chunks)

    @staticmethod
    def _compact_text(items: list[str], limit: int = 320) -> str:
        cleaned = WorkflowService._dedupe([str(item or "").strip("；;，,。 ") for item in items if str(item or "").strip()])
        if not cleaned:
            return ""
        result = "；".join(cleaned)
        if len(result) <= limit:
            return result
        return result[:limit].rstrip("；;，,。 ") + "..."

    @staticmethod
    def _extract_timeline(text: str, fact_sheet: dict[str, Any] | None = None, limit: int = 8) -> list[str]:
        fact_sheet = fact_sheet or {}
        timeline: list[str] = []
        case_time = str(fact_sheet.get("case_time") or "").strip()
        report_time = str(fact_sheet.get("report_time") or "").strip()
        if report_time and report_time != "未明确":
            timeline.append(f"报案/接警时间：{report_time}")
        if case_time and case_time != "未明确":
            timeline.append(f"案发/事发时间：{case_time}")

        time_regex = re.compile(
            r"(\d{4}年\d{1,2}月\d{1,2}日(?:\d{1,2}时(?:\d{1,2}分)?(?:许)?)?|"
            r"\d{1,2}月\d{1,2}日|\d{1,2}时(?:\d{1,2}分)?(?:许)?|"
            r"凌晨|上午|中午|下午|晚上|晚间|当日|当天|随后|之后|后|接警|报警|报案|到场|发现|抓获|逃离)"
        )
        for chunk in WorkflowService._sentence_chunks(text):
            if time_regex.search(chunk):
                timeline.append(chunk[:140])
            if len(timeline) >= limit:
                break
        return WorkflowService._dedupe(timeline)[:limit]

    def _extract_relationships(self, text: str, persons: list[dict[str, Any]] | None = None, limit: int = 6) -> list[str]:
        names = [
            str((person or {}).get("name") or "").strip()
            for person in (persons or [])
            if self._is_valid_person_name(str((person or {}).get("name") or "").strip())
        ]
        relationships: list[str] = []
        relation_tokens = ["与", "和", "系", "夫妻", "情侣", "朋友", "同事", "邻居", "家属", "父子", "母子", "兄弟", "纠纷", "矛盾", "冲突"]
        for chunk in self._sentence_chunks(text):
            name_hit_count = sum(1 for name in names if name and name in chunk)
            if name_hit_count >= 2 or (name_hit_count >= 1 and any(token in chunk for token in relation_tokens)):
                relationships.append(chunk[:140])
            if len(relationships) >= limit:
                break

        if len(relationships) < limit:
            for pattern in (
                r"([\u4e00-\u9fa5]{2,4})(?:与|和)([\u4e00-\u9fa5]{2,4})(?:因|系|为|发生|存在|有)([^。；;，,]{0,40})",
                r"([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})",
            ):
                for match in re.finditer(pattern, text):
                    left = self._normalize_person_name(match.group(1))
                    right = self._normalize_person_name(match.group(2))
                    if not self._is_valid_person_name(left) or not self._is_valid_person_name(right):
                        continue
                    tail = str(match.group(3) if len(match.groups()) >= 3 else "").strip()
                    relationships.append(f"{left}与{right}{tail}".strip())
                    if len(relationships) >= limit:
                        break
        return self._dedupe(relationships)[:limit]

    def _extract_key_facts_from_text(
        self,
        text: str,
        fact_sheet: dict[str, Any] | None = None,
        persons: list[dict[str, Any]] | None = None,
        limit: int = 8,
    ) -> list[str]:
        keywords = [
            "报警", "报案", "接警", "到场", "发现", "发生", "称", "表示", "反映",
            "持刀", "殴打", "打伤", "受伤", "死亡", "逃离", "抓获", "盗窃", "诈骗",
            "转账", "损失", "威胁", "纠纷", "冲突", "争吵", "监控", "证据",
        ]
        facts = self._extract_list_by_keywords(text, keywords, limit=limit)
        names = [str((person or {}).get("name") or "").strip() for person in (persons or []) if (person or {}).get("name")]
        if len(facts) < 3:
            for chunk in self._sentence_chunks(text):
                if any(name and name in chunk for name in names) or any(keyword in chunk for keyword in keywords):
                    facts.append(chunk[:140])
                if len(facts) >= limit:
                    break

        fact_sheet = fact_sheet or {}
        for label, key in (("案发时间", "case_time"), ("案发地点", "case_location"), ("报案时间", "report_time")):
            value = str(fact_sheet.get(key) or "").strip()
            if value and value != "未明确":
                facts.insert(0, f"{label}：{value}")
        return self._dedupe(facts)[:limit]

    def _extract_criminal_process(self, text: str) -> str:
        action_keywords = [
            "持刀", "殴打", "打伤", "刺伤", "砍伤", "抢", "盗窃", "偷", "诈骗", "骗",
            "转账", "威胁", "敲诈", "勒索", "逃离", "损毁", "砸", "酒后", "毒品",
        ]
        chunks = [chunk for chunk in self._sentence_chunks(text) if any(keyword in chunk for keyword in action_keywords)]
        return self._compact_text(chunks[:4], limit=360) or "未明确提取"

    @staticmethod
    def _infer_main_culprit(persons: list[dict[str, Any]] | None) -> str:
        for person in persons or []:
            role_type = str((person or {}).get("role_type") or (person or {}).get("role") or "").strip()
            if "嫌疑" in role_type:
                name = str((person or {}).get("name") or "").strip()
                if name:
                    return name
        return "未明确"

    def _extract_inconsistencies(self, text: str, limit: int = 6) -> list[str]:
        keywords = ["矛盾", "不一致", "前后不一", "各执一词", "否认", "反驳", "不承认", "说法", "版本", "争议"]
        return self._extract_list_by_keywords(text, keywords, limit=limit)

    def _infer_hidden_info(
        self,
        *,
        text: str,
        fact_sheet: dict[str, Any],
        persons: list[dict[str, Any]],
        evidence_points: list[str],
        conflict_points: list[str],
        limit: int = 8,
    ) -> list[str]:
        hidden = self._extract_list_by_keywords(text, ["隐瞒", "不敢说", "没提", "担心", "害怕", "未说明", "不清楚", "无法确认"], limit=limit)
        if self._is_placeholder(fact_sheet.get("case_time")):
            hidden.append("案发或事发时间未明确，需要继续核实。")
        if self._is_placeholder(fact_sheet.get("case_location")):
            hidden.append("案发地点或具体现场位置未明确，需要继续核实。")
        if not persons:
            hidden.append("关键人物姓名、身份或可交流状态未明确。")
        if not evidence_points:
            hidden.append("原文未明确可固定的证据材料，需追问监控、伤情、物品、聊天记录等线索。")
        if not conflict_points and any(token in text for token in ["纠纷", "冲突", "争吵", "打架", "矛盾"]):
            hidden.append("双方冲突起因、责任分歧或利益诉求仍需进一步压实。")
        if len(str(text or "").strip()) < 120:
            hidden.append("原始材料较短，案件经过、人物关系和风险细节可能不完整。")
        return self._dedupe(hidden)[:limit]

    def _compose_case_background(
        self,
        text: str,
        *,
        case_type: str,
        fact_sheet: dict[str, Any],
        persons: list[dict[str, Any]],
        limit: int = 360,
    ) -> str:
        names = [str((person or {}).get("name") or "").strip() for person in persons or [] if (person or {}).get("name")]
        intro_parts = []
        if case_type and case_type != "其他":
            intro_parts.append(f"案件类型初判为{case_type}")
        case_time = str(fact_sheet.get("case_time") or "").strip()
        case_location = str(fact_sheet.get("case_location") or "").strip()
        if case_time and case_time != "未明确":
            intro_parts.append(f"案发时间为{case_time}")
        if case_location and case_location != "未明确":
            intro_parts.append(f"地点为{case_location}")
        if names:
            intro_parts.append(f"涉及人员包括{'、'.join(names[:5])}")

        event_keywords = ["报警", "报案", "接警", "发生", "发现", "称", "表示", "反映", "纠纷", "冲突", "争吵", "打架", "受伤", "死亡", "盗窃", "诈骗", "威胁", "损失", "现场"]
        body_candidates = []
        for chunk in self._sentence_chunks(text):
            if any(keyword in chunk for keyword in event_keywords) or any(name and name in chunk for name in names):
                body_candidates.append(chunk[:160])
            if len(body_candidates) >= 4:
                break
        if not body_candidates:
            body_candidates = self._sentence_chunks(text, limit=3)

        intro = "；".join(intro_parts)
        body = self._compact_text(body_candidates, limit=260)
        if intro and body:
            return self._compact_text([intro, body], limit=limit)
        return body or intro or "未提取到案件背景"

    def _compose_transcript_summary(
        self,
        *,
        fact_sheet: dict[str, Any],
        persons: list[dict[str, Any]],
        key_facts: list[str],
        conflict_points: list[str],
        hidden_info: list[str],
        case_background: str,
        limit: int = 420,
    ) -> str:
        who = "、".join([str((person or {}).get("name") or "").strip() for person in persons or [] if (person or {}).get("name")]) or "相关人员"
        when = str(fact_sheet.get("case_time") or fact_sheet.get("report_time") or "未明确").strip()
        where = str(fact_sheet.get("case_location") or "未明确").strip()
        event = key_facts[0] if key_facts else case_background
        risk = (conflict_points or hidden_info or ["暂无明确争议点，需继续核实"])[0]
        return self._compact_text(
            [
                f"谁：{who}",
                f"何时：{when}",
                f"何地：{where}",
                f"发生：{event}",
                f"争议/风险：{risk}",
            ],
            limit=limit,
        )

    @staticmethod
    def _extract_list_by_keywords(text: str, keywords: list[str], limit: int = 6) -> list[str]:
        result = []
        for line in WorkflowService._split_lines(text):
            if any(keyword in line for keyword in keywords):
                result.append(line[:120])
            if len(result) >= limit:
                break
        return WorkflowService._dedupe(result)

    @staticmethod
    def _default_dispatch_brief(case_info: dict[str, Any], scene_name: str) -> str:
        case_name = str(case_info.get("case_name") or "该案件").strip()
        location = str((case_info.get("fact_sheet") or {}).get("case_location") or "相关现场").strip()
        existing = str(case_info.get("dispatch_brief_suggestion") or "").strip()
        if existing and not ("未明确" in existing and location not in {"", "未明确", "相关现场"}):
            return existing
        return f"接警指令：请前往 {location} 处置与“{case_name}”相关警情，并尽快核实现场情况。"

    @staticmethod
    def _enrich_dispatch_brief(case_info: dict[str, Any], dispatch_brief: str) -> str:
        fact_sheet = case_info.get("fact_sheet") or {}
        location = str(fact_sheet.get("case_location") or "").strip()
        case_time = str(fact_sheet.get("case_time") or "").strip()
        brief = str(dispatch_brief or "").strip()

        parts = []
        if case_time and case_time != "未明确" and case_time not in brief:
            parts.append(f"时间：{case_time}")
        if location and location != "未明确" and location not in brief:
            parts.append(f"地点：{location}")

        if not brief:
            return WorkflowService._default_dispatch_brief(case_info, "接警研判")
        if not parts:
            return brief
        return f"{brief}（{'；'.join(parts)}）"

    @staticmethod
    def _should_refresh_dispatch_brief(existing: str, case_info: dict[str, Any]) -> bool:
        clean_existing = str(existing or "").strip()
        if not clean_existing:
            return True

        fact_sheet = case_info.get("fact_sheet") or {}
        location = str(fact_sheet.get("case_location") or "").strip()
        case_time = str(fact_sheet.get("case_time") or "").strip()
        case_name = str(case_info.get("case_name") or "").strip()

        if "未明确" in clean_existing and any(value not in {"", "未明确"} for value in [location, case_time]):
            return True
        if location not in {"", "未明确"} and location not in clean_existing:
            return True
        if case_name and len(case_name) <= 40 and case_name not in clean_existing:
            return True
        return False

    @staticmethod
    def _default_first_impression(case_info: dict[str, Any], scene_name: str, dispatch_brief: str) -> str:
        if case_info.get("first_impression_suggestion"):
            return str(case_info["first_impression_suggestion"]).strip()
        if "接警" in scene_name or "报警" in scene_name:
            return "你接通后，能听出对方语气急促，正在尽力说明现场发生的情况。"
        if dispatch_brief:
            return "你到场后发现现场气氛紧张，相关人员已在场，需要先稳定秩序并核实情况。"
        return "你到场后先对现场环境、人员状态和异常痕迹进行了初步观察。"

    def _default_parse_result(self, text: str, source_classification: str) -> dict[str, Any]:
        result = json.loads(json.dumps(BASE_PARSE_RESULT, ensure_ascii=False))
        result["case_name"] = self._extract_case_name(text)
        result["case_background"] = str(text or "").strip()[:120] or "未提取到案件背景"
        result["full_narrative"] = str(text or "").strip()[:1200]
        result["rawText"] = str(text or "")
        result["original_content"] = str(text or "")
        result["source_classification"] = source_classification
        result["dispatch_brief_suggestion"] = self._default_dispatch_brief(result, "接警研判")
        result["first_impression_suggestion"] = self._default_first_impression(result, "接警研判", result["dispatch_brief_suggestion"])
        return result

    def _extract_persons_from_text(self, text: str) -> list[dict[str, Any]]:
        persons: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        def add_person(name: str, role: str, status_hint: str = "正常", fact_hint: str = ""):
            clean_name = self._normalize_person_name(name)
            if not self._is_valid_person_name(clean_name) or clean_name in seen_names:
                return
            seen_names.add(clean_name)
            persons.append(self._clean_person({"name": clean_name, "role": role, "role_type": self._guess_role_type(role), "status": status_hint, "knows_facts": [fact_hint[:80]] if fact_hint else []}))

        role_patterns = [
            (r"(报警人|报案人|被害人|受害人|嫌疑人|证人|家属|邻居|目击者)[：:\s]{0,2}([\u4e00-\u9fa5]{2,4})(?=称|说|表示|反映|在|于|，|。|、|$)", "group", 1, 2),
            (r"([\u4e00-\u9fa5]{2,4})[（(](报警人|报案人|被害人|受害人|嫌疑人|证人|家属|邻居|目击者)[)）]", "group", 2, 1),
            (r"(?:嫌疑人|犯罪嫌疑人)([\u4e00-\u9fa5]{2,4})(?=与|因|在|于|，|。|、|$)", "嫌疑人", 0, 1),
            (r"(?:被害人|受害人)([\u4e00-\u9fa5]{2,4})(?=与|因|在|于|，|。|、|$)", "被害人", 0, 1),
        ]
        for line in self._split_lines(text):
            for pattern, role_source, role_index, name_index in role_patterns:
                for match in re.finditer(pattern, line):
                    role = match.group(role_index).strip() if role_source == "group" else role_source
                    name = match.group(name_index).strip()
                    status = self._normalize_person_status(line) if role in {"被害人", "受害人"} else "正常"
                    add_person(name, role, status, line)

        relation_patterns = [
            (r"([\u4e00-\u9fa5]{2,4})与([\u4e00-\u9fa5]{2,4})因", "相关人员", "相关人员"),
            (r"([\u4e00-\u9fa5]{2,4})(?:与|和)([\u4e00-\u9fa5]{2,4})(?:发生|产生|因|争吵|冲突|纠纷|打架|互殴)", "相关人员", "相关人员"),
            (r"([\u4e00-\u9fa5]{2,4})(?:将|把)([\u4e00-\u9fa5]{2,4})(?:打伤|刺伤|砍伤|推倒|撞伤)", "嫌疑人", "被害人"),
            (r"([\u4e00-\u9fa5]{2,4})被([\u4e00-\u9fa5]{2,4})(?:打伤|刺伤|砍伤|抢|骗|盗|威胁)", "被害人", "嫌疑人"),
            (r"([\u4e00-\u9fa5]{2,4})因被害人([\u4e00-\u9fa5]{2,4})", "嫌疑人", "被害人"),
        ]
        for line in self._split_lines(text):
            for pattern, left_role, right_role in relation_patterns:
                match = re.search(pattern, line)
                if not match:
                    continue
                add_person(match.group(1), left_role, "正常", line)
                add_person(match.group(2), right_role, self._normalize_person_status(line) if right_role == "被害人" else "正常", line)

        suspect_match = re.search(r"(?:嫌疑人|犯罪嫌疑人)([\u4e00-\u9fa5]{2,4})(?=与|因|在|于|，|。|、|$)", text)
        if suspect_match:
            add_person(suspect_match.group(1), "嫌疑人", "正常", text)

        victim_match = re.search(r"(?:被害人|受害人)([\u4e00-\u9fa5]{2,4})(?=与|因|在|于|，|。|、|$)", text)
        if victim_match:
            add_person(victim_match.group(1), "被害人", self._normalize_person_status(text), text)

        return persons

    def extract_case_person_names(self, text: str) -> list[str]:
        """Extract unique character names from case text using focused LLM call."""
        messages = [
            {"role": "system", "content": NAME_EXTRACTION_PROMPT},
            {"role": "user", "content": str(text or "")[:8000]},
        ]
        try:
            from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model
            response = create_json_chat_completion(messages=messages, model=get_chat_model(), temperature=0.1, max_tokens=1000)
            payload = self._safe_json_loads(extract_message_text(response), [])
            if isinstance(payload, list):
                valid_names = []
                seen = set()
                for name in payload:
                    clean = self._normalize_person_name(str(name or "").strip())
                    if clean and self._is_valid_person_name(clean) and clean not in seen:
                        seen.add(clean)
                        valid_names.append(clean)
                return valid_names
        except Exception:
            pass
        return []

    def _normalize_parsed_case(self, text: str, payload: dict[str, Any], source_mode: str, source_meta: dict[str, Any] | None, allowed_names: list[str] | None = None) -> dict[str, Any]:
        result = self._default_parse_result(text, "笔录" if source_mode == "transcript_file" else "普通案件文本")
        result.update(payload or {})
        result["case_name"] = str(result.get("case_name") or self._extract_case_name(text)).strip() or "未命名案件"
        ai_case_type = self._normalize_case_type_name(str(result.get("case_type") or ""))
        text_case_type = self._best_case_type_from_text(text, fallback="其他")
        result["case_type"] = text_case_type if text_case_type != "其他" else self.normalize_case_type(text=text, ai_case_type=ai_case_type)
        result["rawText"] = str(result.get("rawText") or text or "")
        result["original_content"] = str(result.get("original_content") or result["rawText"] or text or "")

        fact_sheet = self._safe_json_loads(result.get("fact_sheet"), {})
        if not isinstance(fact_sheet, dict):
            fact_sheet = {}
        extracted_case_time = self._extract_fact_value(text, [r"(?:案发时间|事发时间|时间)[：: ]*([^\n，。,；;]{2,40})", r"(\d{4}年\d{1,2}月\d{1,2}日(?:\d{1,2}时(?:\d{1,2}分)?(?:许)?|上午|下午|晚间|凌晨)?)"])
        extracted_case_location = self._extract_fact_value(text, [r"(?:案发地点|地点|现场位于)[：: ]*([^\n，。,；;]{2,60})", r"在([A-Za-z0-9\u4e00-\u9fa5区市县路街道巷号弄村镇仓库小区广场学校医院商场]{2,40}?)(?:发现|见到|看见|发生|打架|争吵|冲突|纠纷|报警|报案|内|处|附近|，|。)"])
        extracted_report_time = self._extract_fact_value(text, [r"(?:报警时间|接警时间|报案时间)[：: ]*([^\n，。,；;]{2,40})", r"(\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时(?:\d{1,2}分)?(?:许)?)"])
        ai_case_time = str(fact_sheet.get("case_time") or "").strip()
        ai_case_location = str(fact_sheet.get("case_location") or "").strip()
        ai_report_time = str(fact_sheet.get("report_time") or "").strip()
        if ai_case_location and ai_case_location not in text:
            ai_case_location = ""
        result["fact_sheet"] = {
            "case_time": str((ai_case_time if not self._is_placeholder(ai_case_time) else "") or extracted_case_time).strip() or "未明确",
            "case_location": str((ai_case_location if not self._is_placeholder(ai_case_location) else "") or extracted_case_location).strip() or "未明确",
            "report_time": str((ai_report_time if not self._is_placeholder(ai_report_time) else "") or extracted_report_time).strip() or "未明确",
            "timeline": fact_sheet.get("timeline") if isinstance(fact_sheet.get("timeline"), list) else [],
            "relationships": fact_sheet.get("relationships") if isinstance(fact_sheet.get("relationships"), list) else [],
        }

        raw_persons = self._safe_json_loads(result.get("persons"), [])
        persons = self.standardize_person_records(raw_persons)
        extracted_persons = self._extract_persons_from_text(text)
        if not persons:
            persons = extracted_persons
        else:
            merged = {person["name"]: person for person in persons}
            for person in extracted_persons:
                if person["name"] in merged:
                    merged_person = merged[person["name"]]
                    if person.get("role") and person.get("role") != "相关人员":
                        merged_person["role"] = person["role"]
                    if person.get("role_type") and person.get("role_type") != "相关人员":
                        merged_person["role_type"] = person["role_type"]
                    if person.get("status") and person.get("status") != "正常":
                        merged_person["status"] = person["status"]
                else:
                    merged[person["name"]] = person
            persons = list(merged.values())
        persons = [person for person in persons if person.get("name") != "未明确"]

        # Strict post-processing: filter persons against pre-extracted allowed_names
        if allowed_names:
            allowed_set = set(allowed_names)
            before_count = len(persons)
            persons = [person for person in persons if person.get("name") in allowed_set]
            if len(persons) < before_count:
                self._append_warning(result, f"AI 解析生成了 {before_count - len(persons)} 个不在预提取名单中的人物，已自动过滤（仅保留预提取名单中的人物）。")

        result["persons"] = persons

        if not result["fact_sheet"]["timeline"]:
            result["fact_sheet"]["timeline"] = self._extract_timeline(text, result["fact_sheet"])
        if not result["fact_sheet"]["relationships"]:
            result["fact_sheet"]["relationships"] = self._extract_relationships(text, persons)

        for key in ["conflict_points", "key_facts", "hidden_info", "evidence_points", "inconsistencies", "parse_warnings"]:
            value = self._safe_json_loads(result.get(key), [])
            result[key] = value if isinstance(value, list) else []

        if not result["key_facts"]:
            result["key_facts"] = self._extract_key_facts_from_text(text, result["fact_sheet"], persons)
        if not result["conflict_points"]:
            result["conflict_points"] = self._extract_list_by_keywords(text, ["争吵", "矛盾", "冲突", "纠纷", "欠款", "威胁", "各执一词"], limit=6)
        if not result["evidence_points"]:
            result["evidence_points"] = self._extract_list_by_keywords(
                text,
                ["监控", "录像", "视频", "录音", "指纹", "DNA", "刀", "血迹", "足迹", "聊天记录", "转账记录", "伤情", "医院", "票据"],
                limit=8,
            )
        if not result["inconsistencies"]:
            result["inconsistencies"] = self._extract_inconsistencies(text)
        if not result["hidden_info"]:
            result["hidden_info"] = self._infer_hidden_info(
                text=text,
                fact_sheet=result["fact_sheet"],
                persons=persons,
                evidence_points=result["evidence_points"],
                conflict_points=result["conflict_points"],
            )

        current_background = str(result.get("case_background") or "").strip()
        if self._is_placeholder(current_background) or len(current_background) < 20:
            result["case_background"] = self._compose_case_background(
                text,
                case_type=str(result.get("case_type") or ""),
                fact_sheet=result["fact_sheet"],
                persons=persons,
            )
        else:
            result["case_background"] = current_background
        result["full_narrative"] = str(result.get("full_narrative") or text or "").strip()[:4000]
        criminal_process = str(result.get("criminal_process") or "").strip()
        result["criminal_process"] = criminal_process if not self._is_placeholder(criminal_process) else self._extract_criminal_process(text)
        main_culprit = str(result.get("main_culprit") or "").strip()
        result["main_culprit"] = main_culprit if not self._is_placeholder(main_culprit) else self._infer_main_culprit(persons)

        current_dispatch_brief = str(result.get("dispatch_brief_suggestion") or "").strip()
        if self._should_refresh_dispatch_brief(current_dispatch_brief, result):
            result["dispatch_brief_suggestion"] = self._default_dispatch_brief(result, "接警研判")
        else:
            result["dispatch_brief_suggestion"] = current_dispatch_brief
        result["dispatch_brief_suggestion"] = self._enrich_dispatch_brief(result, result["dispatch_brief_suggestion"])

        current_first_impression = str(result.get("first_impression_suggestion") or "").strip()
        if not current_first_impression or ("未明确" in current_first_impression and "接警" in result["dispatch_brief_suggestion"]):
            result["first_impression_suggestion"] = self._default_first_impression(result, "接警研判", result["dispatch_brief_suggestion"])
        else:
            result["first_impression_suggestion"] = current_first_impression
        current_summary = str(result.get("transcript_summary") or "").strip()
        if self._is_placeholder(current_summary) or len(current_summary) < 20:
            result["transcript_summary"] = self._compose_transcript_summary(
                fact_sheet=result["fact_sheet"],
                persons=persons,
                key_facts=result["key_facts"],
                conflict_points=result["conflict_points"],
                hidden_info=result["hidden_info"],
                case_background=result["case_background"],
            )
        else:
            result["transcript_summary"] = current_summary
        result["source_mode"] = source_mode
        if source_meta:
            result["source_file_name"] = source_meta.get("name")
            result["source_file_type"] = source_meta.get("type")
            result["source_file_size"] = source_meta.get("size")
            result["extracted_text_preview"] = str(text or "")[:500]
        migrated_result, _ = migrate_structured_data_payload(result)
        return migrated_result

    def _heuristic_parse_case(self, text: str, source_mode: str, source_meta: dict[str, Any] | None) -> dict[str, Any]:
        result = self._default_parse_result(text, "笔录" if source_mode == "transcript_file" else "普通案件文本")
        result["parse_engine"] = "heuristic"
        result["case_type"] = self.normalize_case_type(text=text)
        result["persons"] = self._extract_persons_from_text(text)
        result["fact_sheet"]["case_time"] = self._extract_fact_value(text, [r"(?:案发时间|事发时间|时间)[：: ]*([^\n，。,；;]{2,40})", r"(\d{4}年\d{1,2}月\d{1,2}日(?:\d{1,2}时(?:\d{1,2}分)?(?:许)?|上午|下午|晚间|凌晨)?)"])
        result["fact_sheet"]["case_location"] = self._extract_fact_value(text, [r"(?:案发地点|地点|现场位于)[：: ]*([^\n，。,；;]{2,60})", r"在([A-Za-z0-9\u4e00-\u9fa5区市县路街道巷号弄村镇仓库小区广场学校医院商场]{2,40}?)(?:发现|见到|看见|发生|打架|争吵|冲突|纠纷|报警|报案|内|处|附近|，|。)"])
        result["fact_sheet"]["report_time"] = self._extract_fact_value(text, [r"(?:报警时间|接警时间|报案时间)[：: ]*([^\n，。,；;]{2,40})", r"(\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时(?:\d{1,2}分)?(?:许)?)"])
        result["fact_sheet"]["timeline"] = self._extract_timeline(text, result["fact_sheet"])
        result["fact_sheet"]["relationships"] = self._extract_relationships(text, result["persons"])
        result["conflict_points"] = self._extract_list_by_keywords(text, ["争吵", "矛盾", "冲突", "纠纷", "欠款", "威胁", "各执一词"])
        result["key_facts"] = self._extract_key_facts_from_text(text, result["fact_sheet"], result["persons"])
        result["evidence_points"] = self._extract_list_by_keywords(text, ["监控", "录像", "视频", "录音", "指纹", "DNA", "刀", "血迹", "足迹", "聊天记录", "转账记录", "伤情", "医院", "票据"])
        result["inconsistencies"] = self._extract_inconsistencies(text)
        result["hidden_info"] = self._infer_hidden_info(
            text=text,
            fact_sheet=result["fact_sheet"],
            persons=result["persons"],
            evidence_points=result["evidence_points"],
            conflict_points=result["conflict_points"],
        )
        result["case_background"] = self._compose_case_background(
            text,
            case_type=result["case_type"],
            fact_sheet=result["fact_sheet"],
            persons=result["persons"],
        )
        result["criminal_process"] = self._extract_criminal_process(text)
        result["main_culprit"] = self._infer_main_culprit(result["persons"])
        result["transcript_summary"] = self._compose_transcript_summary(
            fact_sheet=result["fact_sheet"],
            persons=result["persons"],
            key_facts=result["key_facts"],
            conflict_points=result["conflict_points"],
            hidden_info=result["hidden_info"],
            case_background=result["case_background"],
        )
        result["source_mode"] = source_mode
        if source_meta:
            result["source_file_name"] = source_meta.get("name")
            result["source_file_type"] = source_meta.get("type")
            result["source_file_size"] = source_meta.get("size")
            result["extracted_text_preview"] = str(text or "")[:500]
        self._append_warning(result, "本次案件解析未拿到完整 AI 结果，已切换为规则兜底解析，内容需要人工复核。")
        normalized = self._normalize_parsed_case(text, result, source_mode, source_meta)
        normalized["parse_engine"] = "heuristic"
        return normalized

    def parse_case_text(self, text: str, source_mode: str = "plain_case", source_meta: dict[str, Any] | None = None):
        text = str(text or "").strip()
        if not text:
            raise ValueError("案件文本为空，无法解析")

        def _safe_heuristic(reason: str) -> dict[str, Any]:
            try:
                fallback = self._heuristic_parse_case(text, source_mode, source_meta)
            except Exception as fallback_exc:
                fallback = self._default_parse_result(text, "笔录" if source_mode == "transcript_file" else "普通案件文本")
                fallback.update(
                    {
                        "case_name": self._extract_case_name(text),
                        "case_background": self._compose_case_background(
                            text,
                            case_type="其他",
                            fact_sheet={"case_time": "未明确", "case_location": "未明确", "report_time": "未明确"},
                            persons=[],
                        ),
                        "full_narrative": text[:4000],
                        "rawText": text,
                        "original_content": text,
                        "source_mode": source_mode,
                        "parse_engine": "heuristic",
                    }
                )
                if source_meta:
                    fallback["source_file_name"] = source_meta.get("name")
                    fallback["source_file_type"] = source_meta.get("type")
                    fallback["source_file_size"] = source_meta.get("size")
                    fallback["extracted_text_preview"] = text[:500]
                self._append_warning(fallback, f"规则兜底解析也遇到异常，已返回最小可复核结果：{fallback_exc}")
            self._append_warning(fallback, reason)
            fallback["parse_engine"] = "heuristic"
            return fallback

        # Step 1: Pre-extract character names via LLM for accurate constraint
        extracted_names = self.extract_case_person_names(text)
        # Step 1b: Also extract via regex as supplement for maximum coverage
        regex_persons = self._extract_persons_from_text(text)
        regex_names = set()
        for p in regex_persons:
            n = WorkflowService._normalize_person_name(p.get("name"))
            if n and WorkflowService._is_valid_person_name(n):
                regex_names.add(n)
        # Merge LLM + regex names (deduplicated)
        all_allowed_names = list(dict.fromkeys(extracted_names + list(regex_names)))
        # Step 2: Build name constraint for the prompt
        name_constraint = ""
        if all_allowed_names:
            name_constraint = (
                "\n\n【已在文本中识别到以下角色名】"
                + json.dumps(all_allowed_names, ensure_ascii=False)
                + "\n【强制规则】persons 中每个条目的 name 字段必须严格从该名单中选取，不得编造不在名单中的新名字。"
                + "name 只能是纯人名，不得追加「嫌疑人/证人/审讯阶段/现场阶段」等身份或场景后缀。"
                + "角色身份只能写入 role_type，场景状态只能写入场景或阶段字段，不得污染 name。"
                + "所有场景中同一角色必须使用完全相同的 name 作为标识。"
                + "\n如果原文中没有明确的人名出现在上述名单中，persons 必须返回空数组 []。"
            )
        else:
            name_constraint = (
                "\n\n【强制规则】本文本中未识别到明确的人名，persons 字段必须返回空数组 []。"
                + "严禁将地名、抽象名词、物品名、角色称谓当作人名输出。"
            )
        base_prompt = TRANSCRIPT_PARSE_PROMPT if source_mode == "transcript_file" else PARSE_PROMPT
        prompt = base_prompt + name_constraint
        if source_meta:
            user_content = json.dumps(
                {
                    "source_text": text,
                    "source_meta": source_meta,
                    "parse_instruction": "请基于 source_text 做案件结构化解析。source_meta 中的 OCR 信息只用于判断文本来源、识别质量和不确定性，不要当作案情事实。",
                },
                ensure_ascii=False,
            )
        else:
            user_content = text
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}]
        try:
            response = create_json_chat_completion(messages=messages, model=get_chat_model(), temperature=0.2, max_tokens=4000)
            payload = self._safe_json_loads(extract_message_text(response), {})
            if isinstance(payload, dict) and payload:
                result = self._normalize_parsed_case(text, payload, source_mode, source_meta, allowed_names=all_allowed_names if all_allowed_names else None)
                result["parse_engine"] = "ai"
                return result
        except Exception as exc:
            return _safe_heuristic(f"DeepSeek AI 解析调用失败，已进入规则兜底：{exc}")
        return _safe_heuristic("DeepSeek AI 解析未返回可用 JSON，已进入规则兜底。")

    def _pick_scene_roles(self, case_info: dict[str, Any], preferred_types: list[str], limit: int = 3) -> list[str]:
        selected = []
        for role_type in preferred_types:
            for person in case_info.get("persons") or []:
                if str(person.get("role_type") or "").strip() != role_type:
                    continue
                if not self._is_speakable_status(person.get("status")):
                    continue
                name = str(person.get("name") or "").strip()
                if name and name not in selected:
                    selected.append(name)
        if len(selected) < limit:
            for person in case_info.get("persons") or []:
                if not self._is_speakable_status(person.get("status")):
                    continue
                name = str(person.get("name") or "").strip()
                if name and name not in selected:
                    selected.append(name)
        return selected[:limit]

    def _fallback_scenes(self, case_info: dict[str, Any]) -> dict[str, Any]:
        case_name = str(case_info.get("case_name") or "该案件").strip()
        dispatch_brief = self._default_dispatch_brief(case_info, "接警研判")
        first_impression = self._default_first_impression(case_info, "接警研判", dispatch_brief)
        scenes = [
            {
                "scene_name": "接警研判",
                "scene_description": f"围绕“{case_name}”开展首次接警问询，核实时间、地点、人员和风险等级。",
                "difficulty": "低",
                "dispatch_brief": dispatch_brief,
                "first_impression": first_impression,
                "roles": self._pick_scene_roles(case_info, ["证人", "相关人员", "被害人"]),
                "stages": normalize_stages(
                    [
                        {"stage_name": "信息初核", "stage_goal": "核实报警人身份、当前位置、现场是否存在持续风险。"},
                        {"stage_name": "关键要素确认", "stage_goal": "确认时间、地点、人物、经过和是否需要立即增援。"},
                    ],
                    case_type=str(case_info.get("case_type") or ""),
                    scene_name="接警研判",
                ),
            },
            {
                "scene_name": "现场初查",
                "scene_description": f"到达现场后围绕“{case_name}”开展现场初步核查和人员接触。",
                "difficulty": "中等",
                "dispatch_brief": dispatch_brief,
                "first_impression": "你到场后需要先保护现场、确认人员状态，并快速识别关键证人或重点对象。",
                "roles": self._pick_scene_roles(case_info, ["证人", "被害人", "相关人员"]),
                "stages": normalize_stages(
                    [
                        {"stage_name": "现场控制", "stage_goal": "稳定现场秩序，确认受伤、危险和可疑人员情况。"},
                        {"stage_name": "情况摸排", "stage_goal": "围绕在场人员的第一手所见所闻展开初步问询。"},
                    ],
                    case_type=str(case_info.get("case_type") or ""),
                    scene_name="现场初查",
                ),
            },
            {
                "scene_name": "重点询问",
                "scene_description": f"围绕“{case_name}”中的关键矛盾点，对重点对象开展深入问询。",
                "difficulty": "高",
                "dispatch_brief": dispatch_brief,
                "first_impression": "你已掌握基础情况，接下来要围绕矛盾点、时间线和关键细节压实陈述。",
                "roles": self._pick_scene_roles(case_info, ["嫌疑人", "证人", "相关人员"]),
                "stages": normalize_stages(
                    [
                        {"stage_name": "时间线压实", "stage_goal": "让对方按时间顺序说明关键行为和去向。"},
                        {"stage_name": "矛盾点核查", "stage_goal": "围绕前后不一致、动机或利益冲突展开追问。"},
                    ],
                    case_type=str(case_info.get("case_type") or ""),
                    scene_name="重点询问",
                ),
            },
        ]
        normalized = [scene for scene in scenes if scene["roles"]]
        return {
            "scenes": normalized[:3] or scenes[:2],
            "scene_generation_mode": "fallback",
            "scene_generation_warning": "本次训练场景未拿到完整 AI 结果，已切换为规则兜底场景，请人工复核场景描述与角色分配。",
        }

    def _normalize_scenes(self, case_info: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        scenes = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
        valid_names = {str(person.get("name") or "").strip() for person in case_info.get("persons") or [] if self._is_speakable_status(person.get("status"))}
        normalized = []
        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            roles = []
            for role_name in scene.get("roles") or []:
                clean_name = str(role_name or "").strip()
                if clean_name in valid_names and clean_name not in roles:
                    roles.append(clean_name)
            stages = []
            for stage_index, stage in enumerate(scene.get("stages") or [], start=1):
                if not isinstance(stage, dict):
                    continue
                stages.append(stage)
            scene_name = str(scene.get("scene_name") or self._default_scene_name(index)).strip()
            if re.fullmatch(r"训练场景\d+", scene_name, flags=re.IGNORECASE) or scene_name in {"场景1", "场景2", "场景3"}:
                scene_name = self._default_scene_name(index)
            default_dispatch_brief = self._default_dispatch_brief(case_info, scene_name)
            dispatch_brief = str(scene.get("dispatch_brief") or default_dispatch_brief).strip()
            if "未明确" in dispatch_brief and "未明确" not in default_dispatch_brief:
                dispatch_brief = default_dispatch_brief
            first_impression = str(scene.get("first_impression") or self._default_first_impression(case_info, scene_name, dispatch_brief)).strip()
            stages = normalize_stages(stages, case_type=str(case_info.get("case_type") or ""), scene_name=scene_name)
            normalized.append(
                {
                    "scene_name": scene_name,
                    "scene_description": str(scene.get("scene_description") or "围绕案件关键节点开展训练。").strip(),
                    "difficulty": str(scene.get("difficulty") or "中等").strip(),
                    "dispatch_brief": dispatch_brief,
                    "first_impression": first_impression,
                    "roles": roles or self._pick_scene_roles(case_info, ["证人", "相关人员", "嫌疑人"]),
                    "stages": stages,
                }
            )
        if normalized:
            return {
                "scenes": normalized[:3],
                "scene_generation_mode": "ai",
                "scene_generation_warning": "",
            }
        return self._fallback_scenes(case_info)

    def generate_scenes(self, case_info: dict[str, Any], use_case_completion_officer: bool = False):
        messages = [{"role": "system", "content": SCENE_GEN_PROMPT}, {"role": "user", "content": json.dumps(case_info, ensure_ascii=False)}]
        try:
            if use_case_completion_officer:
                from .llm_provider import create_case_completion_chat_completion

                response = create_case_completion_chat_completion(messages=messages, temperature=0.3, max_tokens=3000)
            else:
                response = create_json_chat_completion(messages=messages, model=get_chat_model(), temperature=0.3, max_tokens=3000)
            payload = self._safe_json_loads(extract_message_text(response), {})
            if isinstance(payload, dict):
                return self._normalize_scenes(case_info, payload)
        except Exception:
            pass
        return self._fallback_scenes(case_info)


workflow_service = WorkflowService()
