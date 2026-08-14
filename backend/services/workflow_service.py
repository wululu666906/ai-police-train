from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .llm_provider import CASE_AI_MAX_TOKENS, create_json_chat_completion, create_text_chat_completion, extract_json_payload, extract_message_text, get_case_workflow_model, get_chat_completion_binding, get_chat_model, get_fast_generation_kwargs
from .ai_workflow_audit import new_correlation_id, record_issue, record_workflow_run, save_story_version
from .case_persona_defaults import get_behavior_archetype_defaults, infer_persona_template, normalize_compact_persona_fields
from .case_schema_service import canonicalize_person_payload, migrate_structured_data_payload
from .case_intelligence_service import assess_source_quality, normalize_case_intelligence
from .training_compiler_service import build_observable_scoring_rules, build_training_tasks, compile_state_machine
from .dialogue_scene_admission_service import admission_prompt_block
from .stage_config_service import normalize_stages
from .case_scene_module_service import build_case_frequency_prompt, build_scene_module_prompt
from .scene_story_planner_service import (
    bind_scenes_to_story,
    build_scene_portfolio_plan,
    complete_scene_blueprint_portfolio,
)
from .scene_design_service import compile_scene_lifecycles
from .role_information_management_service import compile_person_role_information

CASE_SCENE_MIN_COUNT = 1
CASE_SCENE_MAX_COUNT = 4

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
    "case_tags": [],
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
  name, role, role_type, status, role_memories, unresolved_claims, response_constraints
- role_memories 每条包含 statement、memory_type、time_hint、place_hint、actors、certainty、quote；quote 必须是原文连续摘录。
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

- 每条人物线只可写其本人陈述、亲历、所见所闻或事后得知；不能用全案事实替代本人记忆。原文没有的心理、动机或性格不得推断。

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
  name, role, role_type, status, role_memories, unresolved_claims, response_constraints
- role_memories 每条包含 statement、memory_type、time_hint、place_hint、actors、certainty、quote；quote 必须是原文连续摘录。
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

- 如果笔录里出现回避、护短、怕牵连、怕处罚等表述，只能作为对应人物的原文证言或待核实陈述保存，不得推断成性格、动机或行为标签。
- 所有内容都必须有文本依据，不能为了戏剧性乱补剧情。

额外要求：
- 如果是笔录，不要把询问人口吻误写成案件事实。
- 如果是混合材料，优先保留可验证事实，把主观评价放进 parse_warnings 或 transcript_summary 的“待核实”语气中。"""

SCENE_GEN_PROMPT = """你是公安警情训练场景设计专家。你的结果将直接进入管理员的"场景生成"预览页，管理员会人工复核后发布。

任务：严格基于输入案件 JSON，生成 3 到 4 个适合警务训练的平台场景，不得少于 3 个或超过 4 个。

硬性要求：
1. 只能使用输入案件中的事实、人物、地点、关系和风险点，不得虚构新人物、新地点、新案件类型、新证据。
2. 已死亡、昏迷、重伤无法交流的人物绝不能出现在 roles 中作为主对话对象。roles 只能用案件 persons 表中已有的 name（纯人名），不得编造新名字。
3. 场景生成有两种策略：
   - template_first：先参考候选模块/模板，再按本案人物、地点、证据、风险和矛盾点重组、改名、删减或合并。
   - case_driven：不从模板里找场景，直接根据案件事实自动生成场景；候选模块只能作为现实警情常识参考，不得照搬。
4. 每个场景都必须有清晰的 stage 列表，stage_name 和 stage_goal 要能支撑多轮问答，不能空泛重复。
5. 场景目标以训练为主，既可以训练民警与群众/嫌疑人/证人的对话，也可以训练案件复盘、诈骗话术还原、证据链梳理、笔录制作、协同流转、结果回访等非群众对话任务。
6. dispatch_brief 只能写该场景开始前警方已知内容；first_impression 只能写该场景一进入时可观察内容。不得把案件完整事实全写在同一个场景的 dispatch_brief 中。
7. difficulty 要和信息复杂度、人物对抗性、情绪强度匹配，优先使用"低 / 中等 / 高"。
8. 如果输入材料本身信息不足，也要尽量在现有事实上组织可训练场景，但不能靠脑补补齐。
9. 每个 stage 除了 stage_name / stage_goal，还应尽量补 assessment_points、action_catalog、completion_rules、end_conditions。
10. assessment_points 要体现真正能训练能力提升的检查点，不要只复述 stage_goal。每条 assessment_point 包含 label（核心能力）、content（80-200字具体题目+达标标准）、category（procedure/risk/evidence）、required（布尔）、weight（必考12-15/选考8-10）、keywords（2-5个）。
11. action_catalog 要优先覆盖执法动作、取证动作、收尾动作，不要只写说话动作。
12. end_conditions 要体现这个场景在真实流程下何时应结束，并给出 closing_script。
13. 必须输出 3-4 个目标不同且相互递进的场景。第一场可为接警；其余场景必须位于案件主要行为发生后，由学员作为民警开展到场处置、调查询问、证据固定、复盘回访或协同流转。
14. 禁止让学员进入案件正在发生的历史过程，禁止要求学员阻止、参与或改写已经发生的行为。只有原案明确记载民警接警到场时事件仍在持续，才可呈现到场时尚未结束的现实风险；即便如此，也不得改变案件既定结果。
15. 学员行为只影响处置质量、证据完整度、沟通效果与后续风险控制，不得改变案件事实和最终结果。
16. 只输出一个包含 scenes 的合法 JSON 对象，不要附加解释。

场景设计偏好：
- 每个场景都应有明确主任务。
- 角色要有可问询空间、可压实的矛盾点或风险点。
- 多个场景之间要形成递进，而不是简单改写同一段话。
- 可以在还原案件后追加“复盘/整理/笔录/协同/回访”类训练场景；这类场景不一定要求学员以民警身份继续询问群众，重点是快速积累同类案件处置经验。
- 对电诈等案件，可生成“诈骗话术过程还原”“资金流与电子证据核查”“止付冻结协同流转”等训练场景；对盗窃可生成“监控轨迹研判”“证据链梳理”；对纠纷伤害可生成“笔录要素补齐”“调解边界复盘”。
- 场景名应体现本案任务，不只写流程名。例如电诈可写"涉诈报警与预警劝阻/资金流与证据核查"，盗窃可写"失窃报警核实/盗窃现场勘查/可疑线索询问"，纠纷伤害可写"冲突报警与风险稳控/现场分离与证据固定/双方陈述重点询问"。
- 如果候选模块与案件事实不一致，以案件事实为准；不要为了使用模块而生成不存在的现场、证据或人物。

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


EVIDENCE_CARD_PROMPT = """你是案件材料证据整理助手。根据给出的原文分块输出一个紧凑 JSON 对象：
{"facts":[{"content":"可核对的短事实","fact_type":"行为|时间|地点|关系|证据|风险|陈述","quote":"原文连续摘录","status":"confirmed|claimed|conflicted|unknown"}],"person_observations":[{"name":"原文明确姓名","observation":"该人物做了什么、知道什么或否认什么","quote":"原文摘录"}]}
只提取本块原文明确表达的内容；不要写剧本、推断、解释、重复事实或完整案情复述。
硬性容量规则：facts 最多 16 条；person_observations 最多 12 人、每人最多 2 条；content 最多 60 字；observation 最多 50 字；quote 最多 120 字且必须是原文连续片段。优先保留人物、关键行为、时间地点、伤害/损失、证据、冲突和风险。材料再长也必须停止在上述上限内，直接输出完整闭合 JSON。"""

DOCUMENT_STRUCTURE_LABELING_PROMPT = """你是案件材料首席阅读员。请先完整阅读输入文档分块，再为后续人物线、证据与剧情重建建立唯一的“文档导航索引”。只输出 JSON：
{"sections":[{"section_type":"document_title|document_metadata|case_overview|procedural_history|evidence|testimony|interrogation_record|judgment_reasoning|disposition|conclusion|appendix|other","semantic_label":"用本段真实主题自定义命名，例如：被害人黎某18的陈述、现场监控与物证、法院认定理由","processing_priority":"role_memory|case_reconstruction|evidence_linking|context_only|ignore_header","anchor_quote":"本段开头的原文连续摘录","summary":"本段对后续分析的作用","characters":["本段直接相关人物"]}]}
规则：
1. 这不是固定关键词匹配。必须依据文档真实结构、说话主体、材料功能和叙事顺序给出语义标签；semantic_label 必须具体，不能只写“证言”“证据”。
2. 必须覆盖本分块从标题/案情介绍、证据、角色陈述或问答笔录，到裁判理由、结果、附件等实际出现的区域；每个区域单独一项。
3. anchor_quote 必须是该区域开头的原文连续摘录（8-80 字），用于程序精确回指位置；不得编造、改写或把整段内容放进 summary。
4. 角色的陈述、证言、供述、问答笔录必须标为 testimony 或 interrogation_record，processing_priority 必须为 role_memory；案件标题、判决书名称、目录、页眉标为 ignore_header，绝不能标为 role_memory。
5. 不要抽取人物线、事实或完整剧情；本步骤只负责阅读、分区、语义标注和导航。"""

ROLE_LINE_EXTRACTION_PROMPT = """你是公安案件人物线整理员。只依据输入原文，完整识别所有明确出现的人物，并整理每个人自己的陈述、证言和案件经历。只输出 JSON：
{"persons":[{"name":"原文姓名或明确匿名代号","role_type":"嫌疑人|被害人|证人|报警人|相关人员","role_basis":"原文依据","testimony_lines":[{"statement":"尽量保留原文表达，仅做轻微语序润色","memory_type":"direct_statement|personal_experience|direct_observation|hearsay|later_learned","time_hint":"原文时间或相对时间","place_hint":"原文地点","actors":["涉及人物"],"certainty":"claimed|source_supported|conflicted|unknown","quote":"原文连续摘录"}],"unresolved_claims":["本人无法确认或与他人矛盾的内容"]}]}
规则：
1. 人名识别优先完整，不得只保留主犯或被害人；被告人、被害人、证人、报警人、陈述人、被提及的行为人都要检查。
2. 同一人的长篇陈述拆成多条人物线，按其经历顺序整理：事前背景、到场/行动、亲眼所见、亲耳所闻、事后处置。
3. statement 必须贴近原文，不总结成空泛标签，不推断心理；角色自己的判断写成“其认为/其称”。每条尽量保留完整动作、时间、地点和涉及人物。
4. quote 必须是原文连续摘录，用于回溯；没有原文支持的内容不得输出。
5. 每人最多 24 条 testimony_lines，每条只表达一个事件或认知；不得因输出长度只保留一个人物。长材料优先保留原文中的多条证言，不要把整段压成一条摘要。
6. 人物过多时优先缩短 statement 和 quote，仍须保留全部姓名及至少一条关键人物线。
7. 输入会带有文档区段标签。案件介绍、判决理由、证据目录、标题和收尾总结不是角色本人说的话；只有“陈述、证言、供述、询问/讯问笔录”及其连续正文，或明确使用“其称/表示/看到/听到”的原文，才可写入 testimony_lines。
8. 严禁把案件标题、案由、判决书名称、章节标题、证据名称本身当作 testimony_lines；例如“某某聚众斗殴—审判刑事判决书”不是人物记忆。
"""

STORY_RECONSTRUCTION_PROMPT = """你是案件故事重建专家。把本段材料恢复成可供训练后台理解全案的正文故事，只输出 JSON：
{"story_segment":"按时间和因果顺序写清起因、经过、转折、报警、到场和后续结果","person_lines":[{"name":"人物名","role_type":"嫌疑人|被害人|证人|相关人员","role_confidence":0.0,"role_basis":"原文依据摘要","timeline_actions":["何时做了什么"],"experienced":["亲历"],"observed":["看见"],"heard":["听闻"],"known":["知道"],"unknown":["不知道或无法确认"],"withheld":["明确隐瞒或矛盾点"]}]}
story_segment 必须按自然段写：①发生时间、地点和在场人员；②起因；③谁以何种方式做了什么；④各人随后做了什么、报警/到场/处置情况；⑤证据、伤情、损失、矛盾和待核实点。不得补写原文没有的案件事实。单方说法必须写成“某人陈述/声称”，冲突说法必须同时保留。完整故事用于后台理解全案，不代表每个角色都知道全部内容。story_segment 不超过 3000 个汉字；每人每个数组最多 5 项，只保留会影响问询、角色回复或评分的信息。"""

WORLDVIEW_PROMPT = """你是公安警情训练案件状态编辑。输出一个 JSON 对象，字段为：
case_name, case_type, case_background, fact_sheet, persons, key_facts, evidence_points, inconsistencies, transcript_summary,
story_world。
story_world 只作为承载结构，包含 complete_story、facts、roles、metrics；不得在 story_world 中生成事件账本、时间线/空间线、人物关系图或业务决策规则。
facts 每项使用 id、content、fact_type、status、source_refs；roles 每项只保留 name、role_type、status、role_memories、knowledge_ledger。
confirmed 只能是有原文引用的事实；单方说法写 claimed；互相矛盾写 conflicted；无法确认写 unknown。不得把模拟补写写入 confirmed 或人物已知事实。"""

SCENE_BLUEPRINT_PROMPT = (
    """你是警务训练场景规划师。基于案件完整剧情、程序化事实卡、角色记忆和 candidate_scene_slots 生成必要的训练场景蓝图，只输出 JSON：
{"blueprints":[{"scene_id":"S1","portfolio_role":"intake|primary|investigation|followup","is_primary":false,"scene_name":"","scene_kind":"接警|案发后现场处置|案发后调查询问|案发后复盘回访|其他","scene_purpose":"为什么训练该场景","training_goal":"学员完成什么","start_state":"训练开始时的状态","completion_criteria":["可观察的完成条件"],"end_prompt":"达标后的结束提示","training_entry_phase":"intake|post_incident_onsite|post_incident_inquiry|post_incident_followup","entry_time_policy":"dispatch_intake|after_canonical_event","canonical_outcome_locked":true,"student_role":"民警","time":"","place":"","roles":["可交互人物名"],"present_roles":["在场人物名"],"mentioned_roles":["被提及人物名"],"fact_ids":["F1"],"open_question_ids":[],"supplement_ids":[],"stages":[{"stage_name":"","stage_goal":""}]}]}。

规则：
1. 必要性原则优先：输出 1-4 个场景。单一场景可以完成训练目标时，必须只输出 1 个；禁止按案件难易、事实数量或模板槽位凑多场景。
2. 拆分场景只能基于不可合并的实操训练目标，例如角色矛盾调处、现场控制、双方陈述核实、关键线索摸排、人员关系识别、证据/时间线/地点/行为链核查、后续处置措施说明。没有新增实操训练价值的场景必须合并或删除。
3. 场景时间节点优先选择案发过程中学员可以介入控制和处置的阶段，或案发完毕后学员到场开展现场处置、人员接触、信息核实、线索摸排的阶段。
4. 禁止生成审问、讯问、事后复盘、总结汇报、单纯接警信息复述等无实质训练价值的冗余情节；不得让学员穿越到不能介入的历史过程。
5. 学员固定为民警。学员不得改写案件既定事实和结果；其操作只影响处置质量、证据完整度、沟通效果、矛盾化解和风险控制。
6. 每个场景必须写清：学员当前面对谁、当前矛盾或信息缺口是什么、需要完成哪些处置动作、系统通过什么行为判断训练目标完成。
7. 场景按不同警务目标拆分，不能把同一段事实换标题重复生成。相同地点但工作对象、矛盾焦点或线索任务不同，才可以形成独立场景。
8. roles 应列出该处置阶段可接触且可交流的相关人物；死亡、昏迷或无法交流者除外。历史节点的在场名单仅作人物相关性参考。
9. 每个场景引用 1-24 条真正用于该场景的事实，不得把全案所有事实平均分给每个场景；不得依赖事件账本、时间线/空间线或人物关系图生成业务决策。
10. 每个场景必须写清 scene_purpose、training_goal、start_state、completion_criteria 和 end_prompt；完成条件必须是学员可执行、系统可观察的行为。
11. """
    + admission_prompt_block()
)

SCENE_BLUEPRINT_COMPLETION_PROMPT = """你是警务训练场景组合补全器。输入中包含已经生成的场景和 missing_scene_slots。
只为 missing_scene_slots 逐项生成蓝图，不得重写已有场景，不得增加槽位，不得复制主场景目标。
每个蓝图必须使用对应 portfolio_role，并完整提供 scene_purpose、training_goal、start_state、completion_criteria、end_prompt、stages、roles 和 fact_ids。
只能引用输入提供的人物和事实卡；学员固定为民警；除 intake 外均从案件主要行为发生后进入，案件结果不可改变。只输出 {"blueprints": [...]}。"""

SCENE_SCRIPT_PROMPT = """你是警务训练剧本编辑。基于一个场景蓝图、人物卡和可引用事实，输出一个 JSON 对象：
{"scene_name":"","portfolio_role":"","is_primary":false,"scene_purpose":"","training_goal":"","start_state":"","completion_criteria":[""],"end_prompt":"","scene_description":"","difficulty":"低|中等|高","dispatch_brief":"","first_impression":"","roles":[""],"fact_ids":[""],"supplement_ids":[""],"stages":[{"stage_name":"","stage_goal":"","fact_ids":[""]}],"script_markdown":"# 民警任务\\n..."}。
first_impression 是专属“现场第一印象”字段，只能由本剧本生成节点产出。必须写成 80-160 字的一个短段落，且只包含民警进入该场景第一眼可观察内容：环境与空间、可见人员及位置、正在发生的动作、伤情或危险物、声音和围观干扰、即时风险。
first_impression 禁止写接警时间、报警内容复述、路线/时空链路、当前可接触人员清单、训练任务、询问目标、流程提示、案件结论、隐藏证据、裁判判断、人物内心推断；不得复制 dispatch_brief、scene_description 或 script_markdown。
roles 必须保留蓝图中的全部现场可交流人员。主线和支线允许丰富动作、反应和心理变化，但不得改变事实、人物关系和案件结果。
场景当前时点必须服从蓝图的 training_entry_phase 和 entry_time_policy。除接警外，只能描写案件主要行为发生后的状态；历史冲突和行为只能作为待核实的过去事实，不得写成学员眼前正在发生。
script_markdown 使用 Markdown，写民警任务、角色已知范围与回应边界、可问询线索、执法/取证动作、阶段推进和结束条件。任何案件事实必须引用 fact_ids；补写必须引用 supplement_ids，并明确标为“模拟补充”，不可作为评分事实。"""

SCENE_TEXT_TEMPLATE_PROMPT = """你是警务训练剧本编辑。JSON 输出不可用时，使用下面的纯文本模板生成 1-4 个必要的民警训练场景；只使用输入事实卡，模拟补充必须明确标为【模拟补充】，不得写成案件事实。单一场景可以完成训练目标时必须只生成 1 个。场景优先选取案发过程中学员可以介入处置的节点，或案发完毕后民警开展现场处置、人员接触、信息核实、线索摸排的节点。禁止生成审问、讯问、事后复盘、总结汇报、单纯接警信息复述等冗余情节，不得改变案件既定结果。

# 场景 1
场景名称：
场景职责：intake|primary|investigation|followup
是否主场景：是|否
场景目的：
训练目标：
开始状态：
完成条件：条件一；条件二；条件三
结束提示：
场景信息：
接警信息：
现场第一印象：
参与角色：
引用事实：F1、F2
## 训练阶段
1. 阶段名称：阶段目标
## 民警任务与角色回应边界
用 Markdown 写出民警的问询、处置、取证和结束条件。

现场第一印象必须写成 80-160 字的一个短段落，只描述环境、人员位置、当前动作、伤情/危险物、声音/围观干扰和即时风险；禁止写接警时间、路线链路、任务说明、可接触人员名单、案件结论或隐藏信息，不得只写“现场混乱”。每个场景都必须有独立实操训练价值；没有新增训练价值时不要生成。"""


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
    def _chunk_source_text(text: str) -> list[dict[str, Any]]:
        """Keep every source character addressable; split only for provider context limits."""
        chunk_chars = max(4000, int(os.getenv("CASE_AI_CHUNK_CHARS", "120000")))
        overlap = min(chunk_chars // 4, max(0, int(os.getenv("CASE_AI_CHUNK_OVERLAP", "4000"))))
        clean = str(text or "")
        if not clean:
            return []
        chunks = []
        start = 0
        index = 1
        while start < len(clean):
            end = min(len(clean), start + chunk_chars)
            chunks.append({"source_id": f"source-{index}", "start": start, "end": end, "text": clean[start:end]})
            if end == len(clean):
                break
            start = max(start + 1, end - overlap)
            index += 1
        return chunks

    def _generate_free_case_narrative(self, text: str) -> tuple[str, dict[str, Any]]:
        """Ask the model only for readable prose; never for a transport schema."""
        response, trace = create_text_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是公安训练案件的叙事整理员。仅依据原文，写成连贯、准确、便于人工复核的 Markdown 案情主叙事。"
                        "保留不确定、矛盾和缺失，不得补造人物、时间、地点、动机或证据。不要输出 JSON、字段表或代码块。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            model=get_chat_model(),
            temperature=0.2,
            max_tokens=max(1200, int(os.getenv("CASE_AI_NARRATIVE_MAX_TOKENS", "3500"))),
            return_trace=True,
            long_output=False,
            extra_kwargs=get_fast_generation_kwargs(),
        )
        narrative = extract_message_text(response).strip()
        if not narrative:
            raise ValueError("模型未返回可用的自由文本案情主叙事")
        return narrative, trace

    def _generate_story_from_role_checkpoint(
        self,
        persons: list[dict[str, Any]],
        reconstruction: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """Polish the checkpointed role/event ledger into a readable case story."""
        compact_people = []
        for person in persons:
            compact_people.append({
                "name": person.get("name"),
                "role_type": person.get("role_type"),
                "testimony_lines": [
                    {
                        "statement": item.get("statement"), "memory_type": item.get("memory_type"),
                        "time_hint": item.get("time_hint"), "place_hint": item.get("place_hint"),
                        "certainty": item.get("certainty"),
                    }
                    for item in (person.get("role_memories") or [])
                    if isinstance(item, dict)
                ],
                "unresolved_claims": person.get("unresolved_claims") or [],
            })
        payload = {
            "event_ledger": [
                {key: item.get(key) for key in ("event_id", "time_hint", "place_hint", "participants", "statement", "certainty")}
                for item in reconstruction.get("event_ledger") or []
            ],
            "persons": compact_people,
        }
        system_prompt = (
            "你是公安案件剧情编排员。输入的人物线和事件账本已经完成并经过原文回溯，禁止删除人物、合并不同人物或补造事实。"
            "你必须做‘重构’，不能按原文顺序整句复制，也不能只输出事件账本。将同一阶段的多条证言交叉组织成因果叙事，"
            "并保留‘某人称/陈述/认为’等证言属性、矛盾与待核实边界。"
            "严格按如下 Word 正文结构输出 Markdown：# 案件还原剧情；## 案件背景与起因；## 事件全流程（按时间与空间转换）；"
            "## 角色记忆与证言交叉印证；## 报警、处置与待核实问题。每一节至少一个自然段；事件全流程必须写明阶段、地点变化、"
            "人物行为及后续影响。角色记忆节必须逐一覆盖有 testimony_lines 的人物，优先保留原话但只能作为句中引述，不能整段照抄。"
        )

        def request_story(repair: bool = False):
            suffix = "上一版未完成重构或过度复述材料。请完全按规定的五个标题重写，输出正文，不要解释失败原因。" if repair else ""
            return create_text_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt + suffix},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                model=get_chat_model(), temperature=0.15,
                max_tokens=max(4000, int(os.getenv("CASE_AI_ASSEMBLY_MAX_TOKENS", "10000"))),
                return_trace=True, long_output=True, extra_kwargs=get_fast_generation_kwargs(),
            )

        def is_reconstructed(story: str) -> bool:
            headings = re.findall(r"(?m)^##\s+.+$", story)
            required = ("背景", "流程", "证言", "处置")
            if len(headings) < 4 or not all(any(token in heading for heading in headings) for token in required):
                return False
            memory_people = [person for person in compact_people if person["testimony_lines"]]
            if len(memory_people) >= 2:
                mentioned = sum(1 for person in memory_people if str(person["name"] or "") in story)
                if mentioned < min(2, len(memory_people)):
                    return False
            return len(story) >= 240

        response, trace = request_story()
        story = extract_message_text(response).strip()
        finish_reason = str((trace.get("attempts") or [{}])[-1].get("finish_reason") or "")
        if not story or finish_reason == "length":
            raise ValueError("案件剧情生成被截断")
        if not is_reconstructed(story):
            repair_response, repair_trace = request_story(repair=True)
            repaired = extract_message_text(repair_response).strip()
            repair_finish = str((repair_trace.get("attempts") or [{}])[-1].get("finish_reason") or "")
            if repaired and repair_finish != "length" and is_reconstructed(repaired):
                return repaired, repair_trace
            raise ValueError("模型未按人物线完成案件剧情重构")
        return story, trace

    @staticmethod
    def _programmatic_claim_cards(text: str) -> list[dict[str, Any]]:
        """Extract source-grounded claims/evidence locally from original text."""
        cards = []
        evidence_words = ("监控", "录音", "录像", "照片", "伤情", "鉴定", "物证", "证据", "证言", "笔录")
        for sentence in re.split(r"(?<=[。！？；])|\n+", str(text or "")):
            clean = sentence.strip()
            if len(clean) < 6:
                continue
            start = text.find(clean)
            if start < 0:
                continue
            cards.append({
                "id": f"F{len(cards) + 1}",
                "content": clean[:300],
                "fact_type": "证据" if any(word in clean for word in evidence_words) else "陈述主张",
                "status": "claimed",
                "source_refs": [{"source_id": "source-1", "start": start, "end": start + len(clean), "summary": clean[:180]}],
            })
            if len(cards) >= max(240, int(os.getenv("CASE_EVENT_LEDGER_LIMIT", "1200"))):
                break
        return cards

    def _programmatic_people(self, text: str) -> list[dict[str, Any]]:
        people: dict[str, dict[str, Any]] = {}

        def add(name: str, role_type: str, evidence: str, *, strong_action_context: bool = False):
            raw_candidates = [name]
            normalized = self._normalize_person_name(name)
            # Action clauses often greedily capture a leading adverb/time word
            # (“上午李平赶到”). Retry surname-aligned suffixes so real names survive.
            if strong_action_context and len(normalized) >= 3:
                raw_candidates.extend([normalized[-3:], normalized[-2:]])
            for raw in raw_candidates:
                clean = self._normalize_person_name(raw)
                for suffix in ("称其", "表示", "反映", "报警", "报案", "搬走", "拿走", "打伤", "推倒", "离开", "进入"):
                    if clean.endswith(suffix) and len(clean) - len(suffix) >= 2:
                        clean = clean[: -len(suffix)]
                        break
                valid_name = (
                    self._is_contextual_person_name(clean)
                    if strong_action_context
                    else self._is_programmatic_person_name(clean)
                )
                if not valid_name:
                    continue
                item = people.setdefault(clean, {
                    "name": clean,
                    "role": role_type,
                    "role_type": self._guess_role_type(role_type),
                    "status": "正常",
                    "knows_facts": [],
                    "known_key_points": [],
                    "source_verification": "source_matched",
                    "persona_source": "programmatic_identity_only",
                    "persona_autofill": False,
                    "role_template_version": "source_memory_v2",
                })
                fact = str(evidence or "").strip()[:120]
                if fact and fact not in item["knows_facts"]:
                    item["knows_facts"].append(fact)
                    item["known_key_points"].append(fact)
                return

        role_labels = "报警人|报案人|证人|目击者|嫌疑人|犯罪嫌疑人|被告人|上诉人|原审被告人|同案人|被害人|受害人"
        for match in re.finditer(
            rf"(?:^|[，。；：:\s（(及和与、])({role_labels})[）)]?[：:\s]{{0,2}}([\u4e00-\u9fa5]{{2,4}}?(?:\d{{1,2}})?)(?=称|说|表示|反映|陈述|证言|供述|辩解|报警|报案|在|于|与|和|及|均|、|，|。|；|发生|的证言|的陈述|的供述|$)",
            text,
        ):
            add(match.group(2), match.group(1), match.group(0))
        # Legal documents often list several parties after one identity label,
        # e.g. “被害人黎某壬、黎某辛的陈述”. Split only the short name list;
        # prose and institutional roles are intentionally excluded.
        for match in re.finditer(
            rf"({role_labels})[：:\s]{{0,2}}([\u4e00-\u9fa5]{{2,4}}(?:\d{{1,2}})?(?:[、及和与][\u4e00-\u9fa5]{{2,4}}(?:\d{{1,2}})?){{1,5}})(?=称|说|表示|供述|，|。|的证言|的陈述|$)",
            text,
        ):
            for candidate in re.split(r"[、及和与]", match.group(2)):
                add(candidate, match.group(1), match.group(0))
        for match in re.finditer(r"(?:^|[，。；\n])([\u4e00-\u9fa5]{2,4})(?:报警|报案)", text):
            add(match.group(1), "报警人", match.group(0))
        for match in re.finditer(r"(?:看见|看到|目击)([\u4e00-\u9fa5]{2,4}?)(?=搬|拿|打|推|跑|离开|进入|在|于|，|。|等人|后|时)", text):
            add(match.group(1), "相关人员", match.group(0))
        for match in re.finditer(r"(?:^|[，。；\n])([\u4e00-\u9fa5]{2,4})在.{0,35}?(?:看见|看到|目击)([\u4e00-\u9fa5]{2,4}?)(?=搬|拿|打|推|跑|离开|进入|在|于|，|。|等人|后|时)", text):
            add(match.group(1), "证人", match.group(0))
            add(match.group(2), "相关人员", match.group(0))
        for match in re.finditer(r"([\u4e00-\u9fa5]{2,4})和([\u4e00-\u9fa5]{2,4})(?=在|于|发生|争吵|冲突)", text):
            add(match.group(1), "相关人员", match.group(0))
            add(match.group(2), "相关人员", match.group(0))
        # Facts sections describe many participants through actions rather than
        # testimony headings. Register those source-grounded actors separately
        # so role coverage is not coupled to the amount of quoted testimony.
        action_words = (
            "持|拿|携带|组织|召集|通知|纠集|带领|参与|实施|殴打|击打|追赶|"
            "阻拦|劝阻|报警|报案|送医|救助|受伤|损伤|轻伤|重伤|被打|被砍|逃离|离开|到场|赶到|种植|毁坏"
        )
        name_atom = r"(?:[\u4e00-\u9fff]某(?:甲|乙|丙|丁|戊|己|庚|辛|壬|癸)?\d{0,2}|[\u4e00-\u9fff]{2,4})"
        for sentence_match in re.finditer(r"[^。！？；\n]{4,260}[。！？；]?", text):
            sentence = sentence_match.group(0).strip()
            if not re.search(action_words, sentence):
                continue
            for list_match in re.finditer(
                rf"(?P<names>{name_atom}(?:[、及和与]{name_atom}){{1,16}})"
                rf"(?:（[^）]{{0,40}}）)?(?:等(?:人|村民)?)?"
                rf"(?=共同|一起|伙同|手持|不顾|不听|在|从|前往|赶到|商量|决定|{action_words})",
                sentence,
            ):
                for candidate in re.split(r"[、及和与]", list_match.group("names")):
                    add(candidate, "相关人员", sentence, strong_action_context=True)
            for match in re.finditer(rf"(?P<name>{name_atom})(?={action_words})", sentence):
                add(match.group("name"), "相关人员", sentence, strong_action_context=True)
            for match in re.finditer(rf"(?:被|向|对|将)(?P<name>{name_atom})(?={action_words})", sentence):
                add(match.group("name"), "被害人" if re.search(r"被打|被砍|受伤", match.group(0)) else "相关人员", sentence, strong_action_context=True)
            # Handle compact participant lists such as
            # “农长望和农长站、许明向、农盛星一起殴打……”.
            for list_match in re.finditer(
                rf"(?P<names>{name_atom}(?:[、及和与]{name_atom}){{1,10}})(?:共同|一起)?(?:{action_words})",
                sentence,
            ):
                for candidate in re.split(r"[、及和与]", list_match.group("names")):
                    add(candidate, "相关人员", sentence, strong_action_context=True)
            for list_match in re.finditer(
                rf"(?P<names>{name_atom}(?:、{name_atom}){{1,10}})(?=(?:共同|一起)?(?:{action_words}))",
                sentence,
            ):
                for candidate in list_match.group("names").split("、"):
                    add(candidate, "相关人员", sentence, strong_action_context=True)
            for match in re.finditer(
                rf"(?:殴打|击打|追赶|阻拦|伤害|砍伤|打伤)(?P<name>{name_atom})",
                sentence,
            ):
                add(match.group("name"), "被害人", sentence, strong_action_context=True)
        # Numbered records often begin with a compact heading such as
        # "12. 证人韩某的证言". Register that speaker independently from the
        # prose matcher, which can otherwise consume "的证" as part of a name.
        for match in re.finditer(
            rf"({role_labels})\s*([\u4e00-\u9fff]{{2,4}}?(?:\d{{1,2}})?)(?:的)?(?:证言|陈述|供述|辩解|询问笔录|讯问笔录)",
            text,
        ):
            add(match.group(2), match.group(1), match.group(0))
        # Numbered records may omit the identity label, e.g. "12. 韩某陈述".
        # Register the speaker so the source-block pass can attach their memory.
        for match in re.finditer(
            r"(?:^|[\n。])\s*(?:第?\d+[.、．]?\s*)?([\u4e00-\u9fff]{2,4}(?:\d{1,2})?)(?:的)?(?:证言|陈述|供述|辩解|询问笔录|讯问笔录)",
            text,
        ):
            add(match.group(1), "相关人员", match.group(0))
        # Transcript / interview headers: 被询问人：李平 / 询问对象彭某乙
        for match in re.finditer(
            r"(?:被询问人|被讯问人|询问对象|谈话对象|陈述人|受访人)[：:\s]{0,4}"
            r"([\u4e00-\u9fff]{2,4}(?:某[甲乙丙丁戊己庚辛壬癸]?\d{0,2}|\d{0,2})?)"
            r"(?=称|说|表示|反映|陈述|证言|供述|辩解|报警|报案|在|于|与|和|及|均|、|，|。|；|:|：|\s|$)",
            text,
        ):
            add(match.group(1), "相关人员", match.group(0))
        for match in re.finditer(
            r"(?:报警人|报案人|被害人|受害人|证人)(?:姓名)?[：:\s]{0,4}"
            r"([\u4e00-\u9fff]{2,4}(?:某[甲乙丙丁戊己庚辛壬癸]?\d{0,2}|\d{0,2})?)"
            r"(?=称|说|表示|反映|陈述|证言|供述|辩解|报警|报案|在|于|与|和|及|均|、|，|。|；|:|：|\s|$)",
            text,
        ):
            add(match.group(1), "相关人员", match.group(0))
        # Keep legal aliases mentioned inside a statement as separate roles.
        # They must not inherit the current witness's testimony, so their
        # memory remains empty until the source contains their own statement.
        for match in re.finditer(
            r"(?<![\u4e00-\u9fff])([\u4e00-\u9fff]某(?:甲|乙|丙|丁|戊|己|庚|辛|壬|癸)?\d{0,2})(?=$|[，。；、\s]|到|在|被|将|回|称|说|和|与|去|来|上|下)",
            text,
        ):
            add(match.group(1), "相关人员", match.group(0))
        return list(people.values())

    @staticmethod
    def _classify_source_sections(text: str) -> list[dict[str, Any]]:
        """Tag document regions without physically splitting the source.

        The tags give the role-line model document order and intent while all
        quotes still point into the original, untouched text.
        """
        source = str(text or "")
        if not source:
            return []
        # These are metadata boundaries only: source text is never rewritten or
        # physically split, so every quote can still be located by its offset.
        # Line starts catch conventional document headings; in-line testimony
        # markers cover exported judgments/transcripts that arrive as one long
        # paragraph without line breaks.
        markers: list[tuple[int, int, str, str]] = [(0, 0, "case_overview", source[:100].strip())]
        patterns = (
            ("conclusion", r"本院认为|判决如下|裁定如下|综上|判决结果|审判委员会"),
            (
                "testimony",
                r"(?:被害人|受害人|证人|被告人|犯罪嫌疑人|报警人|报案人).{0,16}(?:陈述|证言|供述|辩解)"
                r"|(?:询问|讯问)笔录|(?:其|本人)(?:称|表示|反映)|(?:供述|陈述|证言)称",
            ),
            ("evidence", r"(?m)^(?:\s*第[一二三四五六七八九十\d]+[、.]?\s*)?(?:证据目录|证据材料|证据|书证|物证|鉴定意见|勘验检查笔录|辨认笔录|监控录像|现场照片)"),
            ("case_overview", r"(?m)^\s*(?:案件简介|基本案情|案情|公诉机关指控|起诉书|案发经过|事实与理由|案由)"),
        )
        for label, pattern in patterns:
            for match in re.finditer(pattern, source):
                markers.append((match.start(), -(match.end() - match.start()), label, match.group(0)[:100]))

        # Preserve the intent carried by ordinary multi-line source material.
        # A label selected on a line becomes a boundary at that line start,
        # while inline testimony above can still take effect mid-line.
        for match in re.finditer(r"[^\r\n]+(?:\r?\n|$)", source):
            content = match.group(0).strip()
            if not content:
                continue
            if re.search(r"本院认为|判决如下|裁定如下|综上|判决结果|审判委员会", content):
                label = "conclusion"
            elif re.search(r"被害人.{0,12}(陈述|证言)|证人.{0,12}(证言|陈述)|被告人.{0,12}(供述|辩解)|询问笔录|讯问笔录|其称|其表示|供述称|陈述称", content):
                label = "testimony"
            elif re.search(r"证据|证实|鉴定|勘验|检查笔录|监控|录像|照片|物证|书证|辨认笔录", content):
                label = "evidence"
            elif re.search(r"案件简介|基本案情|案情|公诉机关指控|起诉书|案发经过|事实与理由|案由", content):
                label = "case_overview"
            else:
                continue
            markers.append((match.start(), -len(content), label, content[:100]))

        # At one offset, the longer/more specific marker wins. Build contiguous
        # label spans from the resulting anchor positions.
        selected: dict[int, tuple[int, str, str]] = {}
        for start, priority, label, title in markers:
            previous = selected.get(start)
            if previous is None or priority < previous[0]:
                selected[start] = (priority, label, title)
        ordered = sorted((start, label, title) for start, (_priority, label, title) in selected.items())
        rows = []
        for index, (start, label, title) in enumerate(ordered):
            end = ordered[index + 1][0] if index + 1 < len(ordered) else len(source)
            if end > start:
                rows.append({"label": label, "start": start, "end": end, "title": title})
        merged: list[dict[str, Any]] = []
        for row in rows:
            if merged and merged[-1]["label"] == row["label"] and merged[-1]["end"] == row["start"]:
                merged[-1]["end"] = row["end"]
            else:
                merged.append(row)
        return [{"section_id": f"S{index}", **row} for index, row in enumerate(merged, start=1)]

    def _label_source_sections_ai(self, text: str, correlation_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        """Create an AI-read semantic document index before any role extraction.

        The model returns exact opening quotes instead of offsets.  We resolve
        those quotes against untouched source text locally, which makes the AI
        navigation index both semantic and safely addressable by later stages.
        """
        source = str(text or "")
        fallback = self._classify_source_sections(source)
        if not source:
            return fallback, [], "empty_source"

        chunk_size = max(12000, int(os.getenv("CASE_AI_DOCUMENT_LABEL_CHARS", "50000")))
        chunks = []
        start = 0
        while start < len(source):
            end = min(len(source), start + chunk_size)
            chunks.append({"source_id": f"document-source-{len(chunks) + 1}", "start": start, "text": source[start:end]})
            if end >= len(source):
                break
            start = max(start + 1, end - 800)

        known_types = {
            "document_title", "document_metadata", "case_overview", "procedural_history", "evidence",
            "testimony", "interrogation_record", "judgment_reasoning", "disposition", "conclusion", "appendix", "other",
        }
        default_priority = {
            "document_title": "ignore_header", "document_metadata": "context_only", "case_overview": "case_reconstruction",
            "procedural_history": "case_reconstruction", "evidence": "evidence_linking", "testimony": "role_memory",
            "interrogation_record": "role_memory", "judgment_reasoning": "context_only", "disposition": "context_only",
            "conclusion": "context_only", "appendix": "context_only", "other": "context_only",
        }
        rows: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        errors: list[str] = []
        for chunk in chunks:
            try:
                payload, trace = self._call_case_ai(
                    stage="document_structure_labeling",
                    correlation_id=correlation_id,
                    messages=[
                        {"role": "system", "content": DOCUMENT_STRUCTURE_LABELING_PROMPT},
                        {"role": "user", "content": "【文档分块起始位置】" + str(chunk["start"]) + "\n【原文】\n" + chunk["text"]},
                    ],
                )
                traces.append(trace)
            except Exception as exc:
                errors.append(str(exc)[:200])
                continue
            cursor = 0
            resolved_in_chunk = 0
            for raw in payload.get("sections") or []:
                if not isinstance(raw, dict):
                    continue
                anchor = str(raw.get("anchor_quote") or "").strip()
                if len(anchor) < 8:
                    continue
                local_start = chunk["text"].find(anchor, cursor)
                if local_start < 0:
                    local_start = chunk["text"].find(anchor)
                if local_start < 0:
                    continue
                cursor = local_start + max(1, len(anchor))
                section_type = str(raw.get("section_type") or "other").strip().lower()
                if section_type not in known_types:
                    section_type = "other"
                priority = str(raw.get("processing_priority") or default_priority[section_type]).strip()
                if priority not in {"role_memory", "case_reconstruction", "evidence_linking", "context_only", "ignore_header"}:
                    priority = default_priority[section_type]
                label = str(raw.get("semantic_label") or raw.get("title") or section_type).strip()[:120]
                rows.append({
                    "start": chunk["start"] + local_start,
                    "section_type": section_type,
                    "label": label or section_type,
                    "processing_priority": priority,
                    "title": label or section_type,
                    "anchor_quote": anchor[:180],
                    "summary": str(raw.get("summary") or "").strip()[:240],
                    "characters": [str(item).strip() for item in raw.get("characters") or [] if str(item).strip()][:20],
                    "source": "ai_document_reading",
                })
                resolved_in_chunk += 1
            if not resolved_in_chunk:
                errors.append(f"分块 {chunk['source_id']} 未返回可回指的结构锚点")

        # A partial index is more dangerous than a rule fallback because it can
        # silently hide an unlabelled testimony region.  Only publish the AI
        # index when every document chunk has at least one resolvable anchor.
        if errors or not rows:
            return fallback, traces, "；".join(dict.fromkeys(errors))[:600]
        unique: dict[int, dict[str, Any]] = {}
        for row in rows:
            current = unique.get(row["start"])
            if current is None or len(row["anchor_quote"]) > len(current["anchor_quote"]):
                unique[row["start"]] = row
        ordered = [unique[key] for key in sorted(unique)]
        if ordered[0]["start"] > 0:
            ordered.insert(0, {
                "start": 0, "section_type": "document_metadata", "label": "文档开头与标题信息",
                "processing_priority": "ignore_header", "title": "文档开头与标题信息", "anchor_quote": source[:80],
                "summary": "AI 结构锚点之前的文档标题或元数据。", "characters": [], "source": "ai_document_reading_boundary",
            })
        sections = []
        for index, row in enumerate(ordered, start=1):
            end = ordered[index]["start"] if index < len(ordered) else len(source)
            if end <= row["start"]:
                continue
            sections.append({"section_id": f"AIS{index}", **row, "end": end})
        return sections or fallback, traces, ""

    @staticmethod
    def _section_for_position(sections: list[dict[str, Any]], position: int) -> str:
        for section in sections or []:
            if int(section.get("start", -1)) <= position < int(section.get("end", -1)):
                return str(section.get("section_type") or section.get("label") or "case_overview")
        return "case_overview"

    @staticmethod
    def _section_context(sections: list[dict[str, Any]], start: int, end: int) -> list[dict[str, Any]]:
        return [
            {key: item.get(key) for key in ("section_id", "section_type", "label", "processing_priority", "start", "end", "title", "summary", "characters")}
            for item in sections or []
            if int(item.get("end", -1)) > start and int(item.get("start", 0)) < end
        ]

    @staticmethod
    def _derive_time_hint(value: str) -> str:
        text = str(value or "")
        patterns = (
            r"\d{4}年\d{1,2}月\d{1,2}日(?:凌晨|早晨|上午|中午|下午|晚上|晚间|傍晚)?\s*\d{1,2}(?:时|点)(?:\d{1,2}分)?",
            r"\d{1,2}月\d{1,2}日(?:凌晨|早晨|上午|中午|下午|晚上|晚间|傍晚)?\s*\d{1,2}(?:时|点)(?:\d{1,2}分)?",
            r"\d{4}年\d{1,2}月\d{1,2}日(?:凌晨|早晨|上午|中午|下午|晚上|晚间|傍晚)?",
            r"\d{1,2}月\d{1,2}日(?:凌晨|早晨|上午|中午|下午|晚上|晚间|傍晚)?",
            r"(?:凌晨|早晨|上午|中午|下午|晚上|晚间|傍晚)\s*\d{1,2}(?:时|点)(?:\d{1,2}分)?",
            r"\d{1,2}(?:时|点)(?:\d{1,2}分)?(?:许|左右)?",
            r"(?:案发前|案发后|事发前|事发后|当日|当天|当晚|此前|之后|随后|次日|第二天|冲突后|报警后|到场后)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return "未明确"

    @staticmethod
    def _derive_place_hint(value: str) -> str:
        text = str(value or "")
        suffix = r"村|路|街|巷|号|小区|镇|乡|社区|广场|山脚|山上|公路|水库|桥|门口|房间|院内|店内|现场|医院|派出所|法院"
        direct = re.search(rf"(?:在|于|位于|赶到|来到|走到|经过|从|向)\s*([\u4e00-\u9fa5A-Za-z0-9]{{0,20}}?(?:{suffix}))", text)
        if direct:
            return direct.group(1).strip("，。；、 ")
        generic = re.search(r"(?:在|于|位于)\s*([\u4e00-\u9fa5A-Za-z0-9]{2,12})(处|家中|住所|附近)", text)
        if generic:
            return f"{generic.group(1)}{generic.group(2)}".strip("，。；、 ")
        known = re.search(rf"([\u4e00-\u9fa5A-Za-z0-9]{{0,20}}?(?:{suffix}))", text)
        return known.group(1).strip("，。；、 ") if known else "未明确"

    @classmethod
    def _memory_hints(cls, statement: str, quote: str, source: str, start: int) -> tuple[str, str]:
        context_start = max(0, start - 320)
        context_end = min(len(source), start + max(len(quote), len(statement)) + 320)
        context = f"{statement}\n{quote}\n{source[context_start:context_end]}"
        return cls._derive_time_hint(context), cls._derive_place_hint(context)

    @classmethod
    def _is_testimony_candidate(cls, name: str, statement: str, quote: str, memory_type: str, section_label: str) -> bool:
        clean_quote = str(quote or "").strip()
        clean_statement = str(statement or "").strip()
        if len(clean_quote) < 8 or len(clean_statement) < 8:
            return False
        candidate_text = f"{clean_statement}\n{clean_quote}"
        if re.search(r"判决书|裁定书|审判|刑事判决|聚众斗殴.{0,8}判决|案件名称|案由", candidate_text):
            return False
        speech_markers = ("陈述", "证言", "供述", "辩解", "称", "表示", "反映", "看到", "看见", "听到", "听说", "得知", "笔录")
        if section_label in {"testimony", "interrogation_record", "evidence"} and (any(marker in clean_quote for marker in speech_markers) or memory_type in {"direct_statement", "personal_experience", "direct_observation", "hearsay", "later_learned"}):
            return True
        return any(marker in clean_quote for marker in speech_markers) and name in clean_quote

    def _extract_role_lines_ai(
        self,
        text: str,
        correlation_id: str,
        source_sections: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Extract complete role lines in parallel and merge them by source name."""
        source = str(text or "")
        sections = source_sections or self._classify_source_sections(source)
        chunk_chars = max(4000, int(os.getenv("CASE_AI_ROLE_CHUNK_CHARS", "6500")))
        chunks = []
        start = 0
        while start < len(source):
            end = min(len(source), start + chunk_chars)
            chunks.append({"source_id": f"role-source-{len(chunks) + 1}", "start": start, "text": source[start:end]})
            if end >= len(source):
                break
            start = max(start + 1, end - 800)

        def extract(chunk: dict[str, Any]):
            try:
                payload, trace = self._call_case_ai(
                    stage="role_line_extraction",
                    correlation_id=correlation_id,
                    messages=[
                        {"role": "system", "content": ROLE_LINE_EXTRACTION_PROMPT},
                        {"role": "user", "content": "【文档结构标签】\n" + json.dumps(self._section_context(sections, chunk["start"], chunk["start"] + len(chunk["text"])), ensure_ascii=False) + "\n【原文分块】\n" + chunk["text"]},
                    ],
                )
                return chunk, payload, trace
            except Exception as exc:
                return chunk, {"persons": [], "_error": str(exc)[:300]}, {"attempts": [], "error": str(exc)[:300]}

        workers = min(len(chunks), max(1, int(os.getenv("CASE_AI_ROLE_PARALLELISM", "3"))))
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="case-role-lines") as executor:
                results = list(executor.map(extract, chunks))
        else:
            results = [extract(chunk) for chunk in chunks]

        merged: dict[str, dict[str, Any]] = {}
        traces = []
        for chunk, payload, trace in results:
            traces.append(trace)
            for raw_person in payload.get("persons") or []:
                if not isinstance(raw_person, dict):
                    continue
                name = self._normalize_person_name(raw_person.get("name"))
                if not name or name not in source or len(name) > 10:
                    continue
                person = merged.setdefault(name, {
                    "name": name,
                    "role": str(raw_person.get("role_type") or "相关人员"),
                    "role_type": str(raw_person.get("role_type") or "相关人员"),
                    "status": "正常",
                    "role_basis": str(raw_person.get("role_basis") or "").strip(),
                    "role_memories": [],
                    "unresolved_claims": [],
                    "source_verification": "source_matched",
                    "persona_source": "ai_role_line_extraction",
                    "persona_autofill": False,
                })
                if person["role_type"] == "相关人员" and raw_person.get("role_type"):
                    person["role_type"] = str(raw_person.get("role_type"))
                    person["role"] = person["role_type"]
                for raw_line in raw_person.get("testimony_lines") or []:
                    if not isinstance(raw_line, dict):
                        continue
                    statement = str(raw_line.get("statement") or "").strip()
                    quote = str(raw_line.get("quote") or "").strip()
                    local_pos = chunk["text"].find(quote) if quote else -1
                    if not statement or local_pos < 0:
                        continue
                    absolute_start = chunk["start"] + local_pos
                    section_label = self._section_for_position(sections, absolute_start)
                    memory_type = str(raw_line.get("memory_type") or "direct_statement")
                    if not self._is_testimony_candidate(name, statement, quote, memory_type, section_label):
                        continue
                    time_hint, place_hint = self._memory_hints(statement, quote, source, absolute_start)
                    model_time = str(raw_line.get("time_hint") or "").strip()
                    model_place = str(raw_line.get("place_hint") or "").strip()
                    if model_time in {"时间待核实", "未明确", "未知"}:
                        model_time = time_hint
                    if model_place in {"地点待核实", "未明确", "未知"}:
                        model_place = place_hint
                    ref = {"source_id": chunk["source_id"], "start": absolute_start, "end": absolute_start + len(quote), "summary": quote[:180], "section": section_label}
                    fingerprint = (statement, ref["start"])
                    if any((item.get("statement"), (item.get("source_refs") or [{}])[0].get("start")) == fingerprint for item in person["role_memories"]):
                        continue
                    person["role_memories"].append({
                        "memory_id": f"{name}-M{len(person['role_memories']) + 1}",
                        "memory_type": memory_type,
                        "statement": statement,
                        "time_hint": model_time or "未明确",
                        "place_hint": model_place or "未明确",
                        "actors": [str(item).strip() for item in raw_line.get("actors") or [] if str(item).strip()],
                        "certainty": str(raw_line.get("certainty") or "claimed"),
                        "source_refs": [ref],
                        "quote": quote,
                    })
                person["unresolved_claims"].extend(str(item).strip() for item in raw_person.get("unresolved_claims") or [] if str(item).strip())

        for person in merged.values():
            person["role_memories"].sort(key=lambda item: (item.get("source_refs") or [{}])[0].get("start", 10**9))
            person["unresolved_claims"] = list(dict.fromkeys(person["unresolved_claims"]))[:12]
            person["response_constraints"] = ["只依据本人的原文证言、亲历、所见所闻和本轮公开信息回答。"]
        return list(merged.values()), traces

    def _build_role_memories_and_case_flow(
        self,
        text: str,
        persons: list[dict[str, Any]],
        cards: list[dict[str, Any]],
        source_sections: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Compile source statements into per-role memories and a traceable case flow.

        A role may only receive sentences that name that role.  The same source
        sentence is also an event candidate, so role testimony, timeline and the
        readable case reconstruction always point back to the same original text.
        """
        source = str(text or "")
        sections = source_sections or self._classify_source_sections(source)
        names = [str(person.get("name") or "").strip() for person in persons if str(person.get("name") or "").strip()]
        memories: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
        events: list[dict[str, Any]] = []
        place_pattern = re.compile(r"(?:在|于|地点(?:为|是)?|现场(?:位于|在)?)([\u4e00-\u9fa5A-Za-z0-9]{2,30}(?:路|街|巷|号|小区|村|镇|社区|广场|楼|门口|房间|店|院|停车场|附近)?)")
        time_pattern = re.compile(r"(?:(?:\d{4}年)?\d{1,2}月\d{1,2}日)?(?:凌晨|早晨|上午|中午|下午|晚上|晚间|傍晚)?\s*\d{1,2}(?:时|点)(?:\d{1,2}分)?(?:许|左右)?|(?:事发|争吵|冲突|报警|到场)(?:前|后|时|期间)?")

        # A witness's name often appears only in the heading, while the
        # following sentences are their uninterrupted statement. Preserve that
        # source block before the normal sentence-level association below.
        role_labels = "报警人|报案人|证人|目击者|被害人|受害人|嫌疑人|犯罪嫌疑人|被告人|家属|邻居|陈述人"
        heading_pattern = re.compile(
            rf"(?:^|(?<=\n)|(?<=。))\s*(?:第?\d+[.、．]?\s*)?"
            rf"(?P<role>{role_labels})\s*(?P<name>[\u4e00-\u9fff]{{2,4}}?(?:\d{{1,2}})?)"
            rf"(?:的)?(?P<label>证言|陈述|供述|辩解|询问笔录|讯问笔录)"
        )
        generic_heading_pattern = re.compile(
            r"(?:^|(?<=\n)|(?<=。))\s*(?:第?\d+[.、．]?\s*)?"
            r"(?P<name>[\u4e00-\u9fff]{2,4}(?:\d{1,2})?)(?:的)?"
            r"(?P<label>证言|陈述|供述|辩解|询问笔录|讯问笔录)"
        )
        labeled_headings = list(heading_pattern.finditer(source))
        labeled_starts = {item.start() for item in labeled_headings}
        headings = sorted(
            [*labeled_headings, *(item for item in generic_heading_pattern.finditer(source) if item.start() not in labeled_starts)],
            key=lambda item: item.start(),
        )
        explicit_testimony_ranges: list[tuple[int, int, str]] = []
        for heading_index, match in enumerate(headings):
            name = self._normalize_person_name(match.group("name"))
            if name not in memories:
                continue
            next_start = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(source)
            # A numbered non-testimony item is also a boundary. This avoids
            # putting later evidence or judgment reasoning into the witness's memory.
            boundary = re.search(r"\n\s*(?:第?\d+[.、．]|[一二三四五六七八九十]+[、.])\s*", source[match.end():next_start])
            end = match.end() + boundary.start() if boundary else next_start
            start = match.start()
            while start < end and source[start].isspace():
                start += 1
            quote = source[start:end].strip()
            if len(quote) < 8:
                continue
            time_hint, place_hint = self._memory_hints(quote, quote, source, start)
            memories[name].append({
                "memory_id": f"{name}-M{len(memories[name]) + 1}",
                "memory_type": "direct_statement",
                "statement": quote,
                "time_hint": time_hint,
                "place_hint": place_hint,
                "actors": [name],
                "certainty": "claimed",
                "source_refs": [{
                    "source_id": "source-1",
                    "start": start,
                    "end": end,
                    "summary": quote[:180],
                    "section": self._section_for_position(sections, start),
                }],
                "quote": quote,
            })
            explicit_testimony_ranges.append((start, end, name))

        for index, card in enumerate(cards, start=1):
            statement = str(card.get("content") or "").strip()
            if not statement:
                continue
            refs = card.get("source_refs") if isinstance(card.get("source_refs"), list) else []
            start = min((int(ref.get("start", 10**9)) for ref in refs if isinstance(ref, dict)), default=source.find(statement))
            participants = [name for name in names if name in statement]
            derived_time, derived_place = self._memory_hints(statement, statement, source, max(0, start))
            time_match = time_pattern.search(statement)
            place_match = place_pattern.search(statement)
            time_hint = time_match.group(0).strip() if time_match else derived_time
            # The shared helper requires a real place suffix and avoids the
            # greedy legacy expression swallowing following actions.
            place_hint = derived_place if derived_place != "未明确" else (place_match.group(1).strip() if place_match else "未明确")
            event = {
                "event_id": f"E{index}",
                "sequence": index,
                "source_start": start if start >= 0 else 10**9,
                "time_hint": time_hint,
                "place_hint": place_hint,
                "participants": participants,
                "statement": statement,
                "source_refs": refs,
                "certainty": "source_supported" if refs else "unverified",
            }
            events.append(event)
            for name in participants:
                # The names of people mentioned inside a witness statement are
                # not speakers. Its raw block is already assigned to the
                # heading owner above, so do not leak it into other templates.
                # Multi-role coverage for those aliases is preserved later by
                # identity seeding / source knows_facts during reconciliation.
                if any(range_start <= start < range_end for range_start, range_end, _speaker in explicit_testimony_ranges):
                    continue
                section_label = self._section_for_position(sections, max(0, start))
                if re.search(re.escape(name) + r"(?:称|说|表示|供述|陈述|反映|指认)", statement):
                    memory_type = "direct_statement"
                elif any(token in statement for token in ("看见", "看到", "目击", "发现", "听见")):
                    memory_type = "direct_observation"
                elif any(token in statement for token in ("得知", "听说", "转述")):
                    memory_type = "hearsay"
                elif any(token in statement for token in ("持", "拿", "携带", "组织", "召集", "参与", "实施", "殴打", "击打", "追赶", "阻拦", "报警", "送医", "受伤", "损伤", "轻伤", "重伤", "被打", "逃离", "到场", "种植", "毁坏")):
                    memory_type = "personal_experience"
                else:
                    # A plain mention is not enough to become role memory. It
                    # remains available in the shared event ledger instead.
                    if not self._is_testimony_candidate(name, statement, statement, "source_mention", section_label):
                        continue
                    memory_type = "source_event"
                memories[name].append({
                    "memory_id": f"{name}-M{len(memories[name]) + 1}",
                    "memory_type": memory_type,
                    "statement": statement,
                    "time_hint": time_hint,
                    "place_hint": place_hint,
                    "actors": participants,
                    "certainty": event["certainty"],
                    "source_refs": refs,
                    "event_id": event["event_id"],
                    "quote": statement,
                })

        events.sort(key=lambda item: (item["source_start"], item["sequence"]))
        timeline = [
            {"event_id": item["event_id"], "time": item["time_hint"], "event": item["statement"], "participants": item["participants"], "source_refs": item["source_refs"]}
            for item in events
        ]
        spatial = [
            {"event_id": item["event_id"], "place": item["place_hint"], "event": item["statement"], "participants": item["participants"], "source_refs": item["source_refs"]}
            for item in events
            if item["place_hint"] != "未明确"
        ]
        lines = ["# 案件还原剧情", "", "## 事件全流程（按原文顺序）"]
        for item in events:
            actor_text = "、".join(item["participants"]) or "相关人员"
            lines.append(f"{item['sequence']}. 【{item['time_hint']}｜{item['place_hint']}｜{actor_text}】{item['statement']}")
        if not events:
            lines.append("原文未能拆分出可核对事件，需人工补充。")
        lines.extend(["", "## 人物证言与还原记忆"])
        for name in names:
            rows = memories.get(name) or []
            if not rows:
                continue
            lines.append(f"### {name}")
            for row in rows:
                lines.append(f"- 【{row['memory_type']}｜{row['time_hint']}｜{row['place_hint']}】{row['statement']}")
        return {"role_memories": memories, "event_ledger": events, "timeline": timeline, "spatial_timeline": spatial, "complete_story": "\n".join(lines)}

    @staticmethod
    def _render_complete_story(reconstruction: dict[str, Any], persons: list[dict[str, Any]]) -> str:
        """Render the deterministic Word-ready source reconstruction.

        AI role lines are injected before this renderer is called, so a story
        fallback still contains the same testimony that was checkpointed.
        """
        events = reconstruction.get("event_ledger") if isinstance(reconstruction.get("event_ledger"), list) else []
        memories = reconstruction.get("role_memories") if isinstance(reconstruction.get("role_memories"), dict) else {}
        lines = ["# 案件还原剧情", "", "## 事件全流程（按时间与空间）"]
        for index, item in enumerate(events, start=1):
            actor_text = "、".join(item.get("participants") or []) or "相关人员"
            lines.append(f"{index}. 【{item.get('time_hint') or '未明确'}｜{item.get('place_hint') or '未明确'}｜{actor_text}】{item.get('statement') or ''}")
        if not events:
            lines.append("原文未能拆分出可核对事件，需人工补充。")
        lines.extend(["", "## 人物证言与还原记忆"])
        names = [str(person.get("name") or "").strip() for person in persons if str(person.get("name") or "").strip()]
        for name in names:
            rows = memories.get(name) or []
            if not rows:
                continue
            lines.append(f"### {name}")
            for row in rows:
                lines.append(f"- 【{row.get('memory_type') or 'source_mention'}｜{row.get('time_hint') or '未明确'}｜{row.get('place_hint') or '未明确'}】{row.get('statement') or ''}")
        return "\n".join(lines)

    @staticmethod
    def _attach_programmatic_role_knowledge(
        people: list[dict[str, Any]],
        intelligence: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compile source-grounded role cognition ledgers from local claims."""
        claims = intelligence.get("claims") if isinstance(intelligence, dict) else []
        unresolved = intelligence.get("unresolved_questions") if isinstance(intelligence, dict) else []
        claims = claims if isinstance(claims, list) else []
        unresolved = unresolved if isinstance(unresolved, list) else []
        for person in people:
            name = str(person.get("name") or "").strip()
            role_type = str(person.get("role_type") or person.get("role") or "相关人员")
            ledger: list[dict[str, Any]] = []
            source_refs: list[dict[str, Any]] = []
            known: list[str] = []
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                statement = str(claim.get("statement") or "").strip()
                if not name or name not in statement:
                    continue
                if any(word in statement for word in ("亲眼", "看见", "看到", "目击")):
                    mode = "direct_observation"
                elif any(word in statement for word in ("称", "表示", "供述", "陈述", "反映")):
                    mode = "personal_statement"
                elif role_type in {"嫌疑人", "被害人", "受害人"}:
                    mode = "personal_experience"
                else:
                    mode = "source_mention"
                refs = claim.get("source_refs") if isinstance(claim.get("source_refs"), list) else []
                for ref in refs:
                    if isinstance(ref, dict) and ref not in source_refs:
                        source_refs.append(ref)
                certainty = str(claim.get("certainty") or "source_supported")
                ledger.append({
                    "knowledge_id": f"K{len(ledger) + 1}",
                    "claim_id": str(claim.get("claim_id") or ""),
                    "knowledge_mode": mode,
                    "content": statement,
                    "source_refs": refs,
                    "certainty": certainty,
                    "disclosure_policy": "answer_when_asked",
                    "verbalization": statement,
                })
                known.append(statement)
            related_unresolved = []
            for item in unresolved:
                question = str((item or {}).get("question") if isinstance(item, dict) else item or "").strip()
                if question and (name in question or not people):
                    related_unresolved.append(item)
            person["knowledge_ledger"] = ledger
            person["knows_facts"] = list(dict.fromkeys(known))
            person["known_key_points"] = list(dict.fromkeys(known))
            existing_unresolved = person.get("unresolved_claims") if isinstance(person.get("unresolved_claims"), list) else []
            person["unresolved_claims"] = list(dict.fromkeys(
                json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item)
                for item in [*existing_unresolved, *related_unresolved]
            ))
            person["response_constraints"] = list(dict.fromkeys([
                *(person.get("response_constraints") if isinstance(person.get("response_constraints"), list) else []),
                "只能依据本角色认知账本和本轮公开获知内容回答",
                "材料模糊时具体说明能确认与不能确认的边界",
                "不得使用全案事实补全本角色不知道的信息",
            ]))
            person["source_refs"] = source_refs
            person["persona_contract_version"] = "source_memory_v2"
            person["role_template_version"] = "source_memory_v2"
        return people

    @staticmethod
    def _merge_extracted_people(
        ai_people: list[dict[str, Any]],
        programmatic_people: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge model detail with deterministic source identity coverage."""
        people_by_name = {
            str(item.get("name") or "").strip(): dict(item)
            for item in ai_people
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }
        for fallback in programmatic_people:
            name = str(fallback.get("name") or "").strip()
            if not name:
                continue
            if name not in people_by_name:
                people_by_name[name] = dict(fallback)
                continue
            target = people_by_name[name]
            if target.get("role_type") == "相关人员" and fallback.get("role_type"):
                target["role_type"] = fallback["role_type"]
                target["role"] = fallback.get("role") or fallback["role_type"]
            # A model-returned name without any usable line is only identity
            # recognition. Preserve the deterministic provenance in that case.
            if not target.get("role_memories"):
                target["persona_source"] = fallback.get("persona_source") or "programmatic_identity_only"
        return list(people_by_name.values())

    @staticmethod
    def _ai_result_with_trace(result: Any) -> tuple[Any, dict[str, Any]]:
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
            return result[0], result[1]
        return result, {"primary_provider": "unknown", "final_provider": "unknown", "attempts": []}

    def _call_case_ai(self, *, messages: list[dict[str, str]], stage: str, correlation_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run one compact machine-contract task and persist its provider trace."""
        trace: dict[str, Any] = {"primary_provider": "deepseek", "final_provider": "", "attempts": []}
        budget_names = {
            "document_structure_labeling": ("CASE_AI_DOCUMENT_LABEL_MAX_TOKENS", 6000),
            "role_line_extraction": ("CASE_AI_ROLE_MAX_TOKENS", 4800),
            "evidence_extraction": ("CASE_AI_EVIDENCE_MAX_TOKENS", 4500),
            "case_story_segment": ("CASE_AI_STORY_MAX_TOKENS", 5000),
            "case_worldview": ("CASE_AI_WORLDVIEW_MAX_TOKENS", 32000),
            "scene_blueprint": ("CASE_AI_BLUEPRINT_MAX_TOKENS", 8000),
            "scene_blueprint_completion": ("CASE_AI_BLUEPRINT_MAX_TOKENS", 8000),
            "scene_script": ("CASE_AI_SCRIPT_MAX_TOKENS", 12000),
            "scene_repair": ("CASE_AI_REPAIR_MAX_TOKENS", 8000),
        }
        budget_name, default_budget = budget_names.get(stage, ("CASE_AI_DEFAULT_STAGE_MAX_TOKENS", 16000))
        stage_max_tokens = min(CASE_AI_MAX_TOKENS, max(1024, int(os.getenv(budget_name, str(default_budget)))))
        pro_stages = {"scene_script"}
        selected_model = get_case_workflow_model() if stage in pro_stages else get_chat_model()
        generation_controls = get_fast_generation_kwargs()
        try:
            result = create_json_chat_completion(
                messages=messages,
                model=selected_model,
                temperature=0.2,
                max_tokens=stage_max_tokens,
                extra_kwargs=generation_controls,
                return_trace=True,
                long_output=True,
            )
            response, trace = self._ai_result_with_trace(result)
            payload = self._safe_json_loads(extract_message_text(response), {})
            finish_reason = str((trace.get("attempts") or [{}])[-1].get("finish_reason") or "")
            required_key = {"document_structure_labeling": "sections", "role_line_extraction": "persons", "evidence_extraction": "facts", "case_story_segment": "story_segment", "scene_blueprint": "blueprints", "scene_blueprint_completion": "blueprints", "scene_script": "stages"}.get(stage)
            valid_payload = isinstance(payload, dict) and bool(payload) and (not required_key or required_key in payload)
            if not valid_payload or finish_reason == "length":
                repair_messages = [
                    *messages,
                    {"role": "system", "content": f"上一版输出{'被截断' if finish_reason == 'length' else '不符合 JSON 契约'}。只重新输出一个紧凑、完整、闭合的 JSON 对象；不要解释。字段 {required_key or '按原契约'} 必须存在，数组只保留最关键项目。"},
                ]
                repair_result = create_json_chat_completion(
                    messages=repair_messages, model=selected_model, temperature=0.1,
                    max_tokens=min(2400, stage_max_tokens), extra_kwargs=generation_controls,
                    return_trace=True, retries=1,
                )
                repair_response, repair_trace = self._ai_result_with_trace(repair_result)
                repair_payload = self._safe_json_loads(extract_message_text(repair_response), {})
                record_workflow_run(correlation_id=correlation_id, stage=f"{stage}_compact_repair", trace=repair_trace)
                repair_finish = str((repair_trace.get("attempts") or [{}])[-1].get("finish_reason") or "")
                if isinstance(repair_payload, dict) and repair_payload and (not required_key or required_key in repair_payload) and repair_finish != "length":
                    return repair_payload, repair_trace

                # Schema/JSON failure is distinct from transport failure: make
                # an explicit compact Qwen handover before rules are allowed.
                qwen_client, qwen_model, qwen_provider, qwen_key = get_chat_completion_binding("qwen")
                if qwen_provider == "qwen" and qwen_key:
                    qwen_result = create_json_chat_completion(
                        messages=repair_messages, model=qwen_model, llm_client=qwen_client,
                        temperature=0.1, max_tokens=min(2400, stage_max_tokens),
                        return_trace=True, retries=1,
                    )
                    qwen_response, qwen_trace = self._ai_result_with_trace(qwen_result)
                    qwen_payload = self._safe_json_loads(extract_message_text(qwen_response), {})
                    record_workflow_run(correlation_id=correlation_id, stage=f"{stage}_qwen_handover", trace=qwen_trace)
                    qwen_finish = str((qwen_trace.get("attempts") or [{}])[-1].get("finish_reason") or "")
                    if isinstance(qwen_payload, dict) and qwen_payload and (not required_key or required_key in qwen_payload) and qwen_finish != "length":
                        return qwen_payload, qwen_trace
                raise ValueError("模型未返回可用、完整的 JSON 对象")
            record_workflow_run(correlation_id=correlation_id, stage=stage, trace=trace)
            return payload, trace
        except Exception as exc:
            exception_trace = getattr(exc, "trace", [])
            trace_payload = trace if trace.get("attempts") else {"primary_provider": "deepseek", "final_provider": "", "attempts": exception_trace}
            error_text = str(exc)
            error_code = "MODEL_OUTPUT_LIMIT" if any(token in error_text.lower() for token in ("max_tokens", "maximum tokens", "context length", "output limit")) else "AI_CALL_FAILED"
            run_id = record_workflow_run(
                correlation_id=correlation_id,
                stage=stage,
                trace=trace_payload,
                status="failed",
                error_code=error_code,
                error_summary=error_text,
            )
            record_issue(
                category="ai_exception",
                severity="error",
                title=("AI 模型输出上限不足" if error_code == "MODEL_OUTPUT_LIMIT" else f"AI {stage} 调用失败"),
                detail=error_text,
                workflow_run_id=run_id,
                metadata={"correlation_id": correlation_id, "stage": stage, "provider": "deepseek", "error_code": error_code, "stage_max_tokens": stage_max_tokens},
            )
            raise

    def _call_scene_text_ai(self, *, messages: list[dict[str, str]], stage: str, correlation_id: str) -> tuple[str, dict[str, Any]]:
        """Long-form fallback that keeps the model in control without requiring JSON."""
        try:
            result = create_text_chat_completion(
                messages=messages,
                model=get_chat_model(),
                temperature=0.25,
                max_tokens=min(CASE_AI_MAX_TOKENS, max(4096, int(os.getenv("CASE_AI_TEXT_SCENE_MAX_TOKENS", "24000")))),
                return_trace=True,
                long_output=True,
                extra_kwargs=get_fast_generation_kwargs(),
            )
            response, trace = self._ai_result_with_trace(result)
            content = extract_message_text(response).strip()
            if not content:
                raise ValueError("模型未返回场景文本模板")
            record_workflow_run(correlation_id=correlation_id, stage=stage, trace=trace)
            return content, trace
        except Exception:
            raise

    def _scenes_from_text_template(self, text: str, case_info: dict[str, Any], story_world: dict[str, Any]) -> list[dict[str, Any]]:
        """Convert a forgiving Markdown template into the existing scene contract."""
        known_fact_ids = {str(item.get("id")) for item in story_world.get("fact_cards") or [] if isinstance(item, dict)}
        ordered_fact_ids = [
            str(item.get("id")) for item in story_world.get("fact_cards") or []
            if isinstance(item, dict) and str(item.get("id") or "") in known_fact_ids
        ]
        chunks = [part.strip() for part in re.split(r"(?m)^#\s*场景\s*\d+.*$", text) if part.strip()]
        scenes = []
        for index, chunk in enumerate(chunks[:4], start=1):
            def field(label: str, fallback: str = "") -> str:
                match = re.search(rf"(?m)^{re.escape(label)}[：:]\s*(.+)$", chunk)
                return match.group(1).strip() if match else fallback
            fact_line = field("引用事实")
            explicit_fact_ids = [item for item in re.findall(r"F\d+", fact_line) if item in known_fact_ids]
            if explicit_fact_ids:
                fact_ids = list(dict.fromkeys(explicit_fact_ids))
            else:
                width = max(1, min(8, (len(ordered_fact_ids) + max(1, len(chunks[:4])) - 1) // max(1, len(chunks[:4]))))
                start = (index - 1) * width
                fact_ids = ordered_fact_ids[start:start + width] or ordered_fact_ids[:width]
            stage_block = re.split(r"(?im)^##\s*训练阶段\s*$", chunk, maxsplit=1)
            stage_text = stage_block[1] if len(stage_block) > 1 else ""
            stages = []
            for row in stage_text.splitlines():
                match = re.match(r"\s*\d+[.、]\s*([^：:]+)[：:]\s*(.+)", row)
                if match:
                    stage_name = match.group(1).strip()
                    stage_goal = match.group(2).strip()
                    if stage_name in {"阶段名称", "名称"} or stage_goal in {"阶段目标", "目标"}:
                        continue
                    stages.append({"stage_name": stage_name, "stage_goal": stage_goal, "fact_ids": fact_ids})
            if not stages:
                stages = [{"stage_name": "事实核实", "stage_goal": "围绕已引用案件事实开展民警问询和处置。", "fact_ids": fact_ids}]
            available_names = {
                str(person.get("name") or "").strip()
                for person in case_info.get("persons") or []
                if self._is_speakable_status(person.get("status"))
            }
            template_roles = [
                name.strip()
                for name in re.split(r"[、，,；;\s]+", field("参与角色"))
                if name.strip() in available_names
            ]
            roles = list(dict.fromkeys(template_roles)) or self._pick_scene_roles(
                case_info, ["报警人", "证人", "相关人员", "嫌疑人", "被害人"], limit=6
            )
            scenes.append({
                "scene_name": field("场景名称", self._default_scene_name(index)),
                "portfolio_role": field("场景职责"),
                "is_primary": field("是否主场景") == "是",
                "scene_purpose": field("场景目的"),
                "training_goal": field("训练目标"),
                "start_state": field("开始状态"),
                "completion_criteria": [
                    item.strip() for item in re.split(r"[；;]", field("完成条件")) if item.strip()
                ],
                "end_prompt": field("结束提示"),
                "scene_description": field("场景信息", "围绕案件事实开展民警训练。"),
                "difficulty": "中等",
                "dispatch_brief": field("接警信息", self._default_dispatch_brief(case_info, self._default_scene_name(index))),
                "first_impression": field("现场第一印象", self._default_first_impression(case_info, self._default_scene_name(index), "")),
                "roles": roles,
                "fact_ids": fact_ids,
                "supplement_ids": [],
                "stages": stages,
                "script_markdown": "# 场景 " + str(index) + "\n" + chunk,
            })
        return scenes

    @staticmethod
    def _source_ref_from_quote(source: dict[str, Any], quote: Any) -> dict[str, Any] | None:
        excerpt = str(quote or "").strip()
        source_text = str(source.get("text") or "")
        if not excerpt or not source_text:
            return None
        local_start = source_text.find(excerpt)
        if local_start < 0:
            return None
        start = int(source.get("start") or 0) + local_start
        return {
            "source_id": source.get("source_id"),
            "start": start,
            "end": start + len(excerpt),
            "summary": excerpt[:180],
        }

    def _extract_evidence_cards(self, text: str, correlation_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        cards: list[dict[str, Any]] = []
        person_observations: list[dict[str, Any]] = []
        sources = self._chunk_source_text(text)

        def extract_source(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
            try:
                payload, _trace = self._call_case_ai(
                    stage="evidence_extraction",
                    correlation_id=correlation_id,
                    messages=[{"role": "system", "content": EVIDENCE_CARD_PROMPT}, {"role": "user", "content": source["text"]}],
                )
            except Exception as exc:
                # Preserve successful sibling chunks and let deterministic
                # extraction cover this chunk rather than failing the case.
                payload = {"facts": [], "person_observations": [], "_error": str(exc)[:300]}
            return source, payload

        workers = min(len(sources), max(1, int(os.getenv("CASE_AI_PARALLELISM", "3"))))
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="case-evidence") as executor:
                extracted = list(executor.map(extract_source, sources))
        else:
            extracted = [extract_source(source) for source in sources]

        for source, payload in extracted:
            for item in payload.get("facts") or []:
                if not isinstance(item, dict):
                    continue
                ref = self._source_ref_from_quote(source, item.get("quote"))
                if not ref:
                    continue
                cards.append({
                    "id": f"F{len(cards) + 1}",
                    "content": str(item.get("content") or "").strip(),
                    "fact_type": str(item.get("fact_type") or "其他").strip(),
                    "status": str(item.get("status") or "claimed").strip(),
                    "source_refs": [ref],
                })
            for item in payload.get("person_observations") or []:
                if not isinstance(item, dict):
                    continue
                name = self._normalize_person_name(item.get("name"))
                ref = self._source_ref_from_quote(source, item.get("quote"))
                if not name or not self._is_valid_person_name(name) or not ref:
                    continue
                person_observations.append({
                    "name": name,
                    "role": "相关人员",
                    "role_type": "相关人员",
                    "status": "正常",
                    "knows_facts": [str(item.get("observation") or "").strip()] if str(item.get("observation") or "").strip() else [],
                    "source_refs": [ref],
                })
        return [item for item in cards if item["content"]], person_observations

    def _reconstruct_story_segments(self, text: str, correlation_id: str) -> list[dict[str, Any]]:
        """Reconstruct narrative and person lines in parallel with evidence extraction."""
        sources = self._chunk_source_text(text)

        def reconstruct(source: dict[str, Any]) -> dict[str, Any]:
            payload, _trace = self._call_case_ai(
                stage="case_story_segment",
                correlation_id=correlation_id,
                messages=[{"role": "system", "content": STORY_RECONSTRUCTION_PROMPT}, {"role": "user", "content": source["text"]}],
            )
            return {
                "source_id": source["source_id"],
                "start": source["start"],
                "end": source["end"],
                "story_segment": str(payload.get("story_segment") or "").strip(),
                "person_lines": (
                    payload.get("person_lines") if isinstance(payload.get("person_lines"), list)
                    else (payload.get("persons") if isinstance(payload.get("persons"), list) else [])
                ),
            }

        workers = min(len(sources), max(1, int(os.getenv("CASE_AI_PARALLELISM", "3"))))
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="case-story") as executor:
                return list(executor.map(reconstruct, sources))
        return [reconstruct(source) for source in sources]

    def _build_case_payload_from_parallel_analysis(
        self,
        text: str,
        evidence_cards: list[dict[str, Any]],
        evidence_people: list[dict[str, Any]],
        story_segments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the training case state without a second giant LLM synthesis.

        Evidence cards remain the source of truth; the story branch supplies a
        readable causal narrative and each person's timeline.  This removes a
        duplicate 15k+ token worldview request from the synchronous path.
        """
        complete_story = "\n".join(
            str(item.get("story_segment") or "").strip()
            for item in story_segments
            if isinstance(item, dict) and str(item.get("story_segment") or "").strip()
        )
        story_people: list[dict[str, Any]] = []
        for segment in story_segments:
            if not isinstance(segment, dict):
                continue
            for line in segment.get("person_lines") or []:
                if not isinstance(line, dict):
                    continue
                name = self._normalize_person_name(line.get("name"))
                if not self._is_valid_person_name(name):
                    continue
                known = [str(value).strip() for key in ("experienced", "observed", "heard", "known") for value in (line.get(key) or []) if str(value).strip()]
                unknown = [str(value).strip() for value in (line.get("unknown") or []) if str(value).strip()]
                withheld = [str(value).strip() for value in (line.get("withheld") or []) if str(value).strip()]
                role_type = str(line.get("role_type") or "相关人员").strip()
                if role_type not in {"嫌疑人", "被害人", "证人", "相关人员", "民警"}:
                    role_type = "相关人员"
                try:
                    role_confidence = max(0.0, min(1.0, float(line.get("role_confidence") or 0.5)))
                except (TypeError, ValueError):
                    role_confidence = 0.5
                story_people.append({
                    "name": name, "role": role_type, "role_type": role_type,
                    "role_confidence": role_confidence, "role_basis": str(line.get("role_basis") or "").strip(),
                    "knows_facts": known, "does_not_know": unknown, "hidden_truths": withheld,
                    "timeline_actions": list(line.get("timeline_actions") or []),
                    "case_memory": {"experienced": list(line.get("experienced") or []), "observed": list(line.get("observed") or []), "heard": list(line.get("heard") or [])},
                    "role_thread_id": f"case:pending:role:{name}",
                })
        return {
            "case_name": self._extract_case_name(text),
            "case_type": self.normalize_case_type(text=text),
            "full_narrative": complete_story,
            "case_background": complete_story[:900],
            "persons": [*evidence_people, *story_people],
            "key_facts": [str(card.get("content") or "").strip() for card in evidence_cards if str(card.get("content") or "").strip()][:20],
            "evidence_points": [str(card.get("content") or "").strip() for card in evidence_cards if str(card.get("fact_type") or "") == "证据"][:12],
            "story_world": {
                "complete_story": complete_story,
                "facts": evidence_cards,
                "fact_cards": evidence_cards,
                "roles": [*evidence_people, *story_people],
                "metrics": {
                    "fact_count": len(evidence_cards),
                    "role_count": len([*evidence_people, *story_people]),
                },
                "processing_policy": "storage_metrics_rendering_only",
            },
        }

    def _build_story_world(
        self,
        text: str,
        parsed: dict[str, Any],
        evidence_cards: list[dict[str, Any]],
        persons: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        raw_world = parsed.get("story_world") if isinstance(parsed.get("story_world"), dict) else {}
        source_chunks = self._chunk_source_text(text)
        normalized_cards = []
        for index, item in enumerate(raw_world.get("fact_cards") or evidence_cards, start=1):
            if not isinstance(item, dict):
                continue
            refs = item.get("source_refs") if isinstance(item.get("source_refs"), list) else []
            valid_refs = [ref for ref in refs if isinstance(ref, dict) and isinstance(ref.get("start"), int) and isinstance(ref.get("end"), int) and 0 <= ref["start"] < ref["end"] <= len(text)]
            status = str(item.get("status") or "unknown")
            if status == "confirmed" and not valid_refs:
                status = "claimed"
            normalized_cards.append({
                "id": str(item.get("id") or f"F{index}"),
                "content": str(item.get("content") or "").strip(),
                "fact_type": str(item.get("fact_type") or "其他"),
                "status": status if status in {"confirmed", "claimed", "conflicted", "unknown"} else "unknown",
                "source_refs": valid_refs,
            })
        if not normalized_cards:
            for index, fact in enumerate(parsed.get("key_facts") or [], start=1):
                fact_text = str(fact or "").strip()
                position = text.find(fact_text)
                normalized_cards.append({
                    "id": f"F{index}", "content": fact_text, "fact_type": "事实", "status": "claimed",
                    "source_refs": ([{"source_id": "source-1", "start": position, "end": position + len(fact_text), "summary": fact_text[:180]}] if position >= 0 else []),
                })
        persons = persons if isinstance(persons, list) else (parsed.get("persons") if isinstance(parsed.get("persons"), list) else [])
        roles = [
            {
                "name": item.get("name"),
                "role_type": item.get("role") or item.get("role_type"),
                "status": item.get("status"),
                "role_memories": item.get("role_memories") if isinstance(item.get("role_memories"), list) else [],
                "knowledge_ledger": item.get("knowledge_ledger") if isinstance(item.get("knowledge_ledger"), list) else [],
            }
            for item in persons
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        return {
            "source_index": [{key: value for key, value in source.items() if key != "text"} for source in source_chunks],
            "complete_story": str(raw_world.get("complete_story") or parsed.get("complete_story") or parsed.get("full_narrative") or "").strip(),
            "facts": [item for item in normalized_cards if item["content"]],
            "fact_cards": [item for item in normalized_cards if item["content"]],
            "roles": roles,
            "metrics": {
                "fact_count": len([item for item in normalized_cards if item["content"]]),
                "role_count": len(roles),
            },
            "processing_policy": "storage_metrics_rendering_only",
        }

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
        if person.get("persona_autofill") is False:
            # Text-first extraction establishes identity and source-grounded
            # knowledge only.  It must not invent a behavioral archetype,
            # attitude, motive or stress response from a role label.
            role = str(person.get("role") or person.get("role_type") or "相关人员").strip() or "相关人员"
            cleaned = {
                "person_id": str(person.get("person_id") or "").strip(),
                "name": WorkflowService._normalize_person_name(person.get("name")) or "未明确",
                "aliases": person.get("aliases") if isinstance(person.get("aliases"), list) else [],
                "role": role,
                "role_type": str(person.get("role_type") or WorkflowService._guess_role_type(role)).strip() or "相关人员",
                "status": WorkflowService._normalize_person_status(person.get("status")),
                "knowledge_ledger": person.get("knowledge_ledger") if isinstance(person.get("knowledge_ledger"), list) else [],
                "role_memories": person.get("role_memories") if isinstance(person.get("role_memories"), list) else [],
                "unresolved_claims": person.get("unresolved_claims") if isinstance(person.get("unresolved_claims"), list) else [],
                "response_constraints": person.get("response_constraints") if isinstance(person.get("response_constraints"), list) else [],
                "persona_source": str(person.get("persona_source") or "programmatic_identity_only").strip(),
                "persona_autofill": False,
                "role_template_version": "source_memory_v2",
                "persona_contract_version": "source_memory_v2",
            }
            for key in (
                "source_verification", "source_refs", "source_name_match", "timeline_actions",
                "case_memory", "role_thread_id", "role_confidence", "role_basis",
            ):
                if key in person:
                    cleaned[key] = person[key]
            return cleaned
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
        # Traceability fields are workflow metadata, not persona aliases. Keep
        # them when a parsed case is saved and later re-opened for scene design.
        for key in (
            "source_verification", "source_refs", "source_name_match", "timeline_actions", "case_memory",
            "role_thread_id", "role_confidence", "role_basis", "knowledge_ledger", "role_memories",
            "unresolved_claims", "response_constraints", "role_template_version",
            "persona_contract_version", "persona_source", "persona_autofill",
            "knows_facts", "does_not_know", "hidden_truths",
        ):
            if key in person:
                canonical_cleaned[key] = person[key]
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
        "韦", "申", "尤", "毕", "聂", "丛", "焦", "向", "柳", "邢", "农", "蒙",
        "岳", "齐", "欧", "祝", "尚", "梅", "莫", "佘", "牟", "练",
    })

    # Names that are not real person names (role labels, objects, places, events)
    BAD_TOKENS = frozenset({
        "男子", "女子", "男人", "女人", "对方", "一名", "一位", "民警", "警方", "警察",
        "嫌疑人", "犯罪嫌疑人", "被害人", "受害人", "报警人", "报案人", "证言", "陈述",
        "被告人", "原告人", "上诉人", "辩护人", "审判员", "书记员", "公诉机关", "公诉人",
        "及被告人", "及被害人", "及受害人", "及嫌疑人", "和被告人", "与被告人",
        "本院认为", "经审理查明", "上述人员", "相关人员", "原审被告人",
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

    PROGRAMMATIC_NAME_FORBIDDEN_PARTS = (
        "被告", "原告", "上诉", "辩护", "审判", "书记", "公诉", "本院", "审理",
        "报警", "报案", "嫌疑", "被害", "受害", "证人", "人员", "机关", "法院",
        "检察院", "公安局", "派出所", "查明", "认为", "上述", "相关", "以及",
    )

    @staticmethod
    def _is_programmatic_person_name(name: str) -> bool:
        """Strict source-name gate used by the text-first local extractor.

        The legacy normalizer is intentionally permissive because it also
        repairs administrator-entered values. Automated extraction must be
        stricter: legal connectors/identity labels may never become people.
        """
        clean = WorkflowService._normalize_person_name(name)
        if not clean or clean in WorkflowService.BAD_TOKENS:
            return False
        if clean.endswith(("的", "等", "均", "称", "说", "在", "于", "与", "和", "及", "被", "将", "把", "向", "对")):
            return False
        if any(part in clean for part in WorkflowService.PROGRAMMATIC_NAME_FORBIDDEN_PARTS):
            return False
        return WorkflowService._is_valid_person_name(clean)

    @staticmethod
    def _is_contextual_person_name(name: str) -> bool:
        """Allow rare real names that collide with suffix rules in action clauses."""
        clean = WorkflowService._normalize_person_name(name)
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", clean):
            return False
        if clean in WorkflowService.BAD_TOKENS:
            return False
        if any(part in clean for part in WorkflowService.PROGRAMMATIC_NAME_FORBIDDEN_PARTS):
            return False
        if clean.endswith(("的", "手", "参", "伙", "一", "准备", "方向", "工具", "行为", "现场", "过程")):
            return False
        if any(token in clean for token in ("民警", "政府")):
            return False
        return clean[0] in WorkflowService.COMMON_SURNAMES

    @staticmethod
    def _is_valid_person_name(name: str) -> bool:
        clean = WorkflowService._normalize_person_name(name)
        if not clean:
            return False
        # Court records commonly anonymise parties as “黎某18”“王某甲2”“彭某乙”.
        # These are stable source identifiers, not incomplete names, and must
        # remain usable as role keys throughout the role-line checkpoint.
        legal_alias = re.fullmatch(
            r"([\u4e00-\u9fa5])某(?:[甲乙丙丁戊己庚辛壬癸]\d{0,2}|\d{1,2})",
            clean,
        )
        if legal_alias:
            return legal_alias.group(1) in WorkflowService.COMMON_SURNAMES
        if re.fullmatch(r"([\u4e00-\u9fa5])某", clean):
            return clean[0] in WorkflowService.COMMON_SURNAMES
        if not re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", clean):
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

        if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}(?:\d{1,2})?", clean):
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
    def _clean_case_title_part(value: Any, *, limit: int = 12) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^[#>\-\*\d\.\s、:：]+", "", text)
        text = re.sub(r"(?:案件名称|案由|标题|警情)[:：]\s*", "", text)
        text = re.sub(r"[，。；;、\s]+$", "", text)
        text = re.sub(r"[《》“”\"'`]+", "", text)
        text = re.sub(r"(?:一案|案件|案)$", "", text)
        if not text or text in {"未明确", "未知", "无", "解析失败"}:
            return ""
        return text[:limit]

    @staticmethod
    def _normalize_case_tags(values: Any, *, limit: int = 8) -> list[str]:
        raw_values: list[Any]
        if isinstance(values, list):
            raw_values = values
        elif isinstance(values, str):
            raw_values = re.split(r"[、,，;\s]+", values)
        else:
            raw_values = []
        tags: list[str] = []
        seen: set[str] = set()
        for value in raw_values:
            tag = re.sub(r"[#【】\[\]（）()]+", "", str(value or "").strip())
            if not tag or tag in seen or tag in {"未明确", "其他"}:
                continue
            seen.add(tag)
            tags.append(tag[:12])
            if len(tags) >= limit:
                break
        return tags

    def _derive_case_tags(self, text: str, case_info: dict[str, Any]) -> list[str]:
        tags: list[str] = []
        case_type = str(case_info.get("case_type") or "").strip()
        if case_type and case_type != "其他":
            tags.append(case_type)

        haystack = "\n".join(
            str(item or "")
            for item in [
                text,
                case_info.get("case_background"),
                case_info.get("transcript_summary"),
                *case_info.get("key_facts", []),
                *case_info.get("conflict_points", []),
                *case_info.get("hidden_info", []),
                *case_info.get("evidence_points", []),
            ]
        )
        keyword_tags = [
            ("情绪对抗", ("争吵", "辱骂", "情绪", "激动", "对峙", "冲突")),
            ("多人冲突", ("多人", "聚集", "围观", "双方", "村民", "群众")),
            ("伤情核实", ("受伤", "伤情", "医院", "鉴定", "流血", "骨折")),
            ("证据固定", ("监控", "录像", "录音", "照片", "聊天记录", "转账记录", "物证")),
            ("财产损失", ("损失", "赔偿", "被盗", "毁坏", "砸坏", "金额")),
            ("调解风险", ("调解", "各执一词", "不承认", "否认", "责任", "赔偿")),
            ("持续风险", ("威胁", "持刀", "轻生", "逃离", "继续", "再次", "失控")),
            ("身份待核实", ("身份不明", "关键人物", "未明确", "不详")),
        ]
        for tag, keywords in keyword_tags:
            if any(keyword in haystack for keyword in keywords):
                tags.append(tag)

        fact_sheet = case_info.get("fact_sheet") if isinstance(case_info.get("fact_sheet"), dict) else {}
        if any(str(fact_sheet.get(key) or "").strip() in {"", "未明确"} for key in ("case_time", "case_location")):
            tags.append("时空信息待核实")
        return self._normalize_case_tags([*(case_info.get("case_tags") or []), *tags])

    def _derive_formal_case_name(self, text: str, case_info: dict[str, Any]) -> str:
        case_type = str(case_info.get("case_type") or "").strip() or self.normalize_case_type(text=text)
        if case_type == "其他":
            case_type = "警情"

        persons = case_info.get("persons") if isinstance(case_info.get("persons"), list) else []
        main_culprit = self._clean_case_title_part(case_info.get("main_culprit"), limit=8)
        person_name = main_culprit
        if not person_name:
            for person in persons:
                if not isinstance(person, dict):
                    continue
                candidate = self._clean_case_title_part(person.get("name"), limit=8)
                if candidate:
                    person_name = candidate
                    break

        fact_sheet = case_info.get("fact_sheet") if isinstance(case_info.get("fact_sheet"), dict) else {}
        location = self._clean_case_title_part(fact_sheet.get("case_location"), limit=10)
        existing = self._clean_case_title_part(case_info.get("case_name"), limit=16)

        subject = person_name or location or existing
        if not subject:
            subject = self._clean_case_title_part(self._extract_case_name(text), limit=14)

        if subject and case_type in subject:
            title = subject
        elif subject:
            title = f"{subject}{case_type}"
        else:
            title = f"{case_type}"
        title = re.sub(r"(案件|一案|案)+$", "", title)
        title = re.sub(r"(纠纷|诈骗|盗窃|抢劫|事故|警情)\1+", r"\1", title)
        return f"{title[:24]}案" if title else "未命名案件"

    def _apply_case_identity(self, text: str, case_info: dict[str, Any]) -> dict[str, Any]:
        case_info["case_tags"] = self._derive_case_tags(text, case_info)
        case_info["case_name"] = self._derive_formal_case_name(text, case_info)
        return case_info

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

    def _normalize_parsed_case(
        self,
        text: str,
        payload: dict[str, Any],
        source_mode: str,
        source_meta: dict[str, Any] | None,
        allowed_names: list[str] | None = None,
        evidence_people: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
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
        evidence_persons = self.standardize_person_records(evidence_people or [])
        extracted_persons = self._extract_persons_from_text(text)
        # The final person roster is a union: worldview synthesis, every
        # evidence chunk's person observations, and deterministic text hits.
        # This prevents a concise synthesis response from silently dropping a
        # person who was present only in a later source chunk.
        merged = {person["name"]: person for person in persons}
        for person in [*evidence_persons, *extracted_persons]:
            if person["name"] in merged:
                merged_person = merged[person["name"]]
                if person.get("role") and person.get("role") != "相关人员":
                    merged_person["role"] = person["role"]
                if person.get("role_type") and person.get("role_type") != "相关人员":
                    merged_person["role_type"] = person["role_type"]
                if person.get("status") and person.get("status") != "正常":
                    merged_person["status"] = person["status"]
                self._merge_person_record(merged_person, person)
            else:
                merged[person["name"]] = person
        persons = list(merged.values())
        persons = [person for person in persons if person.get("name") != "未明确"]

        # A regex list is only a weak signal for complex OCR/table materials.
        # Retain AI-discovered people and make their evidence status explicit;
        # deleting them here was the direct cause of one-person parses.
        allowed_set = set(allowed_names or [])
        pending_review_count = 0
        for person in persons:
            name = str(person.get("name") or "").strip()
            position = text.find(name) if name else -1
            if position >= 0:
                person["source_verification"] = "source_matched"
                person["source_name_match"] = True
                person["source_refs"] = [{
                    "source_id": "source-1",
                    "start": position,
                    "end": position + len(name),
                    "summary": name,
                }]
            elif name in allowed_set:
                person["source_verification"] = "regex_matched"
                person["source_name_match"] = True
            else:
                person["source_verification"] = "pending_review"
                person["source_name_match"] = False
                person["source_refs"] = []
                pending_review_count += 1
        if pending_review_count:
            self._append_warning(
                result,
                f"AI 识别到 {pending_review_count} 名人物未能直接回指原文，已保留为“待核实”；如与场景事实相关，仍可作为训练角色入场复核。",
            )

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
        # Keep the model-produced complete narrative; long raw materials are
        # separately chunked into evidence cards rather than silently truncated.
        result["full_narrative"] = str(result.get("full_narrative") or text or "").strip()
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
        self._apply_case_identity(text, result)
        migrated_result, _ = migrate_structured_data_payload(result)
        for person in migrated_result.get("persons") or []:
            if not isinstance(person, dict):
                continue
            person["knows_facts"] = person.get("knows_facts") or person.get("known_key_points") or []
            person["hidden_truths"] = person.get("hidden_truths") or person.get("withheld_key_points") or []
            person["does_not_know"] = person.get("does_not_know") or person.get("cannot_answer") or []
        return migrated_result

    def _heuristic_parse_case(
        self,
        text: str,
        source_mode: str,
        source_meta: dict[str, Any] | None,
        *,
        mark_as_fallback: bool = True,
    ) -> dict[str, Any]:
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
        if mark_as_fallback:
            self._append_warning(result, "本次案件解析未拿到完整 AI 结果，已切换为规则兜底解析，内容需要人工复核。")
        normalized = self._normalize_parsed_case(text, result, source_mode, source_meta)
        normalized["parse_engine"] = "heuristic"
        return normalized

    def parse_case_text_with_rule_fallback(
        self,
        text: str,
        source_mode: str = "plain_case",
        source_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = str(text or "").strip()
        if not text:
            raise ValueError("案件文本为空，无法解析")
        try:
            return self.parse_case_text(text, source_mode=source_mode, source_meta=source_meta)
        except Exception as exc:
            try:
                fallback = self._heuristic_parse_case(text, source_mode, source_meta)
            except Exception as fallback_exc:
                fallback = self._default_parse_result(text, "笔录" if source_mode == "transcript_file" else "普通案件文本")
                fallback.update(
                    {
                        "case_name": self._extract_case_name(text),
                        "case_type": self.normalize_case_type(text=text),
                        "case_background": text[:1200],
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
            self._append_warning(fallback, f"AI 解析失败，已切换为规则兜底解析：{exc}")
            fallback["parse_engine"] = "heuristic"
            return fallback

    @staticmethod
    def _source_sentences(text: str) -> list[dict[str, Any]]:
        rows = []
        for match in re.finditer(r"[^。！？\n]+[。！？]?", str(text or "")):
            content = match.group(0).strip()
            if len(content) >= 6:
                rows.append({"content": content, "start": match.start(), "end": match.end()})
        return rows[:40]

    def _build_rule_intelligence(self, text: str) -> dict[str, Any]:
        claims = []
        evidence = []
        unresolved = []
        uncertainty = ("不清楚", "没看清", "不详", "大概", "可能", "不确定", "不记得")
        evidence_words = ("监控", "录像", "录音", "照片", "伤情", "医院", "物证", "手机", "证人")
        for index, item in enumerate(self._source_sentences(text), start=1):
            content = item["content"]
            source_ref = {"document_id": "source-1", "start": item["start"], "end": item["end"], "summary": content[:180]}
            claims.append({
                "claim_id": f"C{index}", "statement": content,
                "claim_type": "source_statement", "verification_status": "unverified",
                "certainty": "uncertain" if any(word in content for word in uncertainty) else "source_supported",
                "source_refs": [source_ref],
            })
            if any(word in content for word in evidence_words):
                evidence.append({"evidence_id": f"E{len(evidence)+1}", "description": content, "source_refs": [source_ref], "reliability": "reported"})
            if any(word in content for word in uncertainty):
                unresolved.append({"question": content, "reason": "source_explicit_uncertainty", "source_refs": [source_ref]})
        return {"schema_version": 2, "source_documents": [{"document_id": "source-1", "length": len(text)}], "claims": claims, "evidence": evidence, "events": [], "unresolved_questions": unresolved}

    def _parse_case_text_first(self, text: str, source_mode: str, source_meta: dict[str, Any] | None) -> dict[str, Any]:
        correlation_id = new_correlation_id()
        document_label_started = time.perf_counter()
        try:
            source_sections, document_label_traces, document_label_error = self._label_source_sections_ai(text, correlation_id)
        except Exception as exc:
            source_sections, document_label_traces, document_label_error = self._classify_source_sections(text), [], str(exc)
        # Deterministic extraction is a first-class part of this architecture,
        # not an error fallback.  Do not inherit the legacy fallback warning.
        base = self._heuristic_parse_case(text, source_mode, source_meta, mark_as_fallback=False)
        if document_label_error:
            self._append_warning(base, "AI 文档阅读/语义标签未完整生成，当前分区已切换为规则标签；人物线与剧情需要人工复核。")
        cards = self._programmatic_claim_cards(text)
        uncertainty_words = ("不清楚", "没看清", "不详", "大概", "可能", "不确定", "不记得")
        intelligence = normalize_case_intelligence({"case_intelligence": {
            "source_documents": [{"document_id": "source-1", "length": len(text)}],
            "claims": [{"claim_id": card["id"], "statement": card["content"], "claim_type": card["fact_type"], "verification_status": "unverified", "certainty": "uncertain" if any(word in card["content"] for word in uncertainty_words) else "source_supported", "source_refs": card["source_refs"]} for card in cards],
            "evidence": [{"evidence_id": f"E{i+1}", "description": card["content"], "source_refs": card["source_refs"], "reliability": "reported"} for i, card in enumerate(card for card in cards if card["fact_type"] == "证据")],
            "events": [],
            "unresolved_questions": [{"question": card["content"], "reason": "source_explicit_uncertainty", "source_refs": card["source_refs"]} for card in cards if any(word in card["content"] for word in uncertainty_words)],
        }})
        programmatic_people = self._programmatic_people(text)
        role_phase_error = ""
        role_phase_started = time.perf_counter()
        try:
            ai_people, role_traces = self._extract_role_lines_ai(text, correlation_id, source_sections)
            role_phase_error = "；".join(str(item.get("error") or "").strip() for item in role_traces if isinstance(item, dict) and item.get("error"))
            if role_phase_error:
                self._append_warning(base, "部分原文分块的人物线 AI 提取失败，已保留成功分块并使用规则补齐失败分块。")
        except Exception as exc:
            ai_people, role_traces = [], []
            role_phase_error = str(exc)
            self._append_warning(base, f"AI 人物线提取失败，已保留规则识别人物继续处理：{exc}")
        base["persons"] = self._attach_programmatic_role_knowledge(
            self._merge_extracted_people(ai_people, programmatic_people), intelligence
        )

        reconstruction = self._build_role_memories_and_case_flow(text, base["persons"], cards, source_sections)
        for person in base["persons"]:
            name = str(person.get("name") or "").strip()
            ai_memories = person.get("role_memories") if isinstance(person.get("role_memories"), list) else []
            rule_memories = reconstruction["role_memories"].get(name, [])
            role_memories = list(ai_memories)
            seen_memory_refs = {
                ((item.get("source_refs") or [{}])[0].get("start"), str(item.get("statement") or "").strip())
                for item in role_memories if isinstance(item, dict)
            }
            for memory in rule_memories:
                marker = ((memory.get("source_refs") or [{}])[0].get("start"), str(memory.get("statement") or "").strip())
                if marker not in seen_memory_refs:
                    role_memories.append(memory)
                    seen_memory_refs.add(marker)
            role_memories.sort(key=lambda item: (item.get("source_refs") or [{}])[0].get("start", 10**9))
            person["role_memories"] = role_memories
            compiled_person = compile_person_role_information(person)
            person.clear()
            person.update(compiled_person)
            reconstruction["role_memories"][name] = person["role_memories"]
            person["response_constraints"] = person.get("response_constraints") or ["只陈述本人亲历、亲眼所见或原文明确记载的内容。"]
            person["unresolved_claims"] = person.get("unresolved_claims") or []
        def person_source_start(person: dict[str, Any]) -> int:
            positions = []
            for memory in person.get("role_memories") or []:
                if not isinstance(memory, dict):
                    continue
                for ref in memory.get("source_refs") or []:
                    if isinstance(ref, dict) and isinstance(ref.get("start"), int):
                        positions.append(ref["start"])
            name = str(person.get("name") or "").strip()
            return min(positions) if positions else (text.find(name) if name and text.find(name) >= 0 else 10**9)

        # Person order is part of the source contract: the admin review and
        # scene allocator must see people in their first original occurrence.
        base["persons"].sort(key=lambda person: (person_source_start(person), str(person.get("name") or "")))
        reconstruction["complete_story"] = self._render_complete_story(reconstruction, base["persons"])
        # Persist the completed and normalized role phase before starting the
        # long-form story call. Output-limit failures can only affect the story.
        base["role_checkpoint_version_id"] = save_story_version(
            correlation_id=correlation_id,
            source_mode=source_mode,
            story={"checkpoint_type": "role_lines", "persons": base["persons"], "status": "ai_complete" if ai_people else "rule_fallback", "role_phase_error": role_phase_error},
        )
        role_phase_elapsed_ms = round((time.perf_counter() - role_phase_started) * 1000)
        narrative_error = ""
        story_phase_started = time.perf_counter()
        try:
            narrative, trace = self._generate_story_from_role_checkpoint(base["persons"], reconstruction)
        except Exception as exc:
            narrative, trace = reconstruction["complete_story"], {"attempts": []}
            narrative_error = str(exc)
            self._append_warning(base, f"AI 完整剧情生成失败，人物名册与人物线已保留，仅剧情切换为事件账本规则组装：{exc}")
        base["case_intelligence"] = intelligence
        base["ai_narrative"] = narrative
        base["complete_story"] = narrative or reconstruction["complete_story"]
        base["full_narrative"] = base["complete_story"]
        base["source_sections"] = source_sections
        base["document_labeling"] = {
            "mode": "ai_document_reading" if not document_label_error else "rule_fallback",
            "error": document_label_error,
            "section_count": len(source_sections),
            "traces": document_label_traces,
        }
        base["narrative_document"] = {"schema_version": 3, "format": "word", "content": base["complete_story"], "source_mode": source_mode, "role": "source_grounded_case_reconstruction", "policy": "story_first_source_grounded", "sections": source_sections}
        base["story_world"] = {
            "complete_story": base["complete_story"],
            "facts": cards,
            "fact_cards": cards,
            "roles": base.get("persons") or [],
            "metrics": {
                "fact_count": len(cards),
                "role_count": len(base.get("persons") or []),
                "memory_count": sum(len(person.get("role_memories") or []) for person in base.get("persons") or [] if isinstance(person, dict)),
            },
            "processing_policy": "storage_metrics_rendering_only",
        }
        base["source_quality"] = assess_source_quality(text)
        ai_narrative_used = bool(trace.get("attempts"))
        base["parse_engine"] = "ai_text_first" if ai_narrative_used else "rule_text_first"
        base["generation_mode"] = "ai_role_checkpoint_then_story_assembly"
        base["ai_workflow"] = {
            **trace,
            "correlation_id": correlation_id,
            "stage": "story_assembly_after_role_checkpoint",
            "architecture": "ai_role_lines_checkpoint_then_story_with_rule_fallback",
            "used_rule_fallback": not ai_narrative_used,
            "role_checkpoint_version_id": base.get("role_checkpoint_version_id"),
            "role_phase_status": "ai_complete" if ai_people else "rule_fallback",
            "role_chunk_count": len(role_traces),
            "stage_timings_ms": {
                "document_reading_and_labeling": round((role_phase_started - document_label_started) * 1000),
                "role_lines_and_checkpoint": role_phase_elapsed_ms,
                "story_assembly": round((time.perf_counter() - story_phase_started) * 1000),
            },
        }
        record_workflow_run(
            correlation_id=correlation_id,
            stage="story_assembly_after_role_checkpoint",
            trace=trace,
            status="success" if ai_narrative_used else "fallback",
            used_rule_fallback=not ai_narrative_used,
            error_code="narrative_generation_failed" if narrative_error else "",
            error_summary=narrative_error,
        )
        base["story_version_id"] = save_story_version(
            correlation_id=correlation_id,
            story=base["story_world"],
            source_mode=source_mode,
        )
        self._apply_case_identity(text, base)
        return base

    def parse_case_for_training(
        self,
        text: str,
        source_mode: str = "plain_case",
        source_meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fast path for training: preserve role evidence, skip decorative long-form rewriting."""
        text = str(text or "").strip()
        if not text:
            raise ValueError("案件文本为空，无法解析")

        base = self._heuristic_parse_case(text, source_mode, source_meta, mark_as_fallback=False)
        source_sections = self._classify_source_sections(text)
        cards = self._programmatic_claim_cards(text)
        uncertainty_words = ("不清楚", "没看清", "不详", "大概", "可能", "不确定", "不记得")
        intelligence = normalize_case_intelligence({"case_intelligence": {
            "source_documents": [{"document_id": "source-1", "length": len(text)}],
            "claims": [
                {
                    "claim_id": card["id"],
                    "statement": card["content"],
                    "claim_type": card["fact_type"],
                    "verification_status": "unverified",
                    "certainty": "uncertain" if any(word in card["content"] for word in uncertainty_words) else "source_supported",
                    "source_refs": card["source_refs"],
                }
                for card in cards
            ],
            "evidence": [
                {
                    "evidence_id": f"E{index}",
                    "description": card["content"],
                    "source_refs": card["source_refs"],
                    "reliability": "reported",
                }
                for index, card in enumerate((item for item in cards if item["fact_type"] == "证据"), start=1)
            ],
            "events": [],
            "unresolved_questions": [
                {"question": card["content"], "reason": "source_explicit_uncertainty", "source_refs": card["source_refs"]}
                for card in cards
                if any(word in card["content"] for word in uncertainty_words)
            ],
        }})

        programmatic_people = self._programmatic_people(text)
        ai_people: list[dict[str, Any]] = []
        extraction_warning = ""
        try:
            ai_people, _ = self._extract_role_lines_ai(text, new_correlation_id(), source_sections)
        except Exception as exc:
            extraction_warning = str(exc)[:240]

        persons = self._attach_programmatic_role_knowledge(
            self._merge_extracted_people(ai_people, programmatic_people), intelligence
        )
        reconstruction = self._build_role_memories_and_case_flow(text, persons, cards, source_sections)
        for person in persons:
            name = str(person.get("name") or "").strip()
            memories = person.get("role_memories") if isinstance(person.get("role_memories"), list) else []
            known = {(item.get("memory_id"), item.get("statement")) for item in memories if isinstance(item, dict)}
            for memory in reconstruction.get("role_memories", {}).get(name, []):
                marker = (memory.get("memory_id"), memory.get("statement"))
                if marker not in known:
                    memories.append(memory)
                    known.add(marker)
            person["role_memories"] = memories
            compiled_person = compile_person_role_information(person)
            person.clear()
            person.update(compiled_person)
            reconstruction.setdefault("role_memories", {})[name] = person["role_memories"]
        base["persons"] = self.standardize_person_records(persons)
        complete_story = self._render_complete_story(reconstruction, base["persons"])
        base.update({
            "case_intelligence": intelligence,
            "complete_story": complete_story,
            "full_narrative": complete_story,
            "story_world": {
                "complete_story": complete_story,
                "facts": cards,
                "fact_cards": cards,
                "roles": base["persons"],
                "metrics": {
                    "fact_count": len(cards),
                    "role_count": len(base["persons"]),
                    "memory_count": sum(len(person.get("role_memories") or []) for person in base["persons"] if isinstance(person, dict)),
                },
                "processing_policy": "storage_metrics_rendering_only",
            },
            "source_sections": source_sections,
            "source_quality": assess_source_quality(text),
            "parse_engine": "training_fast_path",
            "generation_mode": "role_evidence_then_training_compile",
            "rawText": text,
            "original_content": text,
        })
        if source_meta:
            for key in ("source_asset_id", "source_asset_key", "ocr_method", "ocr_engine", "ocr_warnings", "ocr_metadata"):
                if source_meta.get(key) is not None:
                    base[key] = source_meta[key]
        if extraction_warning:
            self._append_warning(base, f"人物线模型辅助未完整完成，已使用来源规则补齐：{extraction_warning}")
        self._apply_case_identity(text, base)
        return base

    def parse_case_text(self, text: str, source_mode: str = "plain_case", source_meta: dict[str, Any] | None = None):
        text = str(text or "").strip()
        if not text:
            raise ValueError("案件文本为空，无法解析")

        if os.getenv("CASE_PARSE_PIPELINE", "text_first").strip().lower() == "text_first":
            return self._parse_case_text_first(text, source_mode, source_meta)

        correlation_id = new_correlation_id()

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

        # Use deterministic names as the main constraint. The previous separate
        # LLM name-extraction call doubled failure opportunities before parsing.
        regex_persons = self._extract_persons_from_text(text)
        regex_names = set()
        for p in regex_persons:
            n = WorkflowService._normalize_person_name(p.get("name"))
            if n and WorkflowService._is_valid_person_name(n):
                regex_names.add(n)
        all_allowed_names = list(dict.fromkeys(regex_names))
        # Step 2: Build name constraint for the prompt
        name_constraint = ""
        if all_allowed_names:
            name_constraint = (
                "\n\n【正则初步识别到以下角色名】"
                + json.dumps(all_allowed_names, ensure_ascii=False)
                + "\n【人物识别规则】优先使用上述姓名；表格、OCR 块、附件或正文中有明确依据的其他姓名也必须保留。"
                + "不得仅凭案情推测编造人名；无法回指原文的角色请保留但在 source_verification 写 pending_review。"
                + "name 只能是纯人名，不得追加「嫌疑人/证人/审讯阶段/现场阶段」等身份或场景后缀。"
                + "角色身份只能写入 role_type，场景状态只能写入场景或阶段字段，不得污染 name。"
                + "所有场景中同一角色必须使用完全相同的 name 作为标识。"
                + "\n若材料只出现匿名代号（如李某甲、嫌疑人甲），可保留该代号作为角色名，并标记为待核实。"
            )
        else:
            name_constraint = (
                "\n\n【人物识别规则】正则未识别到完整姓名时，继续检查表格、OCR、附件和匿名代号；有明确原文依据的人物仍应输出。"
                + "严禁将地名、抽象名词、物品名或纯角色称谓当作人名输出。"
            )
        base_prompt = TRANSCRIPT_PARSE_PROMPT if source_mode == "transcript_file" else PARSE_PROMPT
        try:
            # Do not discard the tail of a complex document. Each source chunk
            # is converted to evidence cards first, then the synthesis task sees
            # the complete evidence set rather than a lossy text prefix.
            # Evidence extraction and full-story reconstruction are independent
            # reads of the same source, so run them concurrently.  The final
            # state merge waits for both but does not serialize their latency.
            parallel_started = time.perf_counter()
            narrative, narrative_trace = self._generate_free_case_narrative(text)
            evidence_cards = self._programmatic_claim_cards(text)
            evidence_people = self._programmatic_people(text)
            assembly_started = time.perf_counter()
            payload = self._heuristic_parse_case(text, source_mode, source_meta)
            payload.update({
                "full_narrative": narrative,
                "case_background": narrative[:900],
                "persons": evidence_people,
                "key_facts": [card["content"] for card in evidence_cards if card["fact_type"] != "证据"][:20],
                "evidence_points": [card["content"] for card in evidence_cards if card["fact_type"] == "证据"][:12],
                "inconsistencies": [
                    card["content"] for card in evidence_cards
                    if any(word in card["content"] for word in ("不清楚", "没看清", "不确定", "不详", "可能", "称", "但"))
                ][:12],
                "story_world": {
                    "complete_story": narrative,
                    "facts": evidence_cards,
                    "fact_cards": evidence_cards,
                    "roles": evidence_people,
                    "metrics": {"fact_count": len(evidence_cards), "role_count": len(evidence_people)},
                    "processing_policy": "storage_metrics_rendering_only",
                },
            })
            result = self._normalize_parsed_case(
                text, payload, source_mode, source_meta,
                allowed_names=all_allowed_names if all_allowed_names else None,
                evidence_people=evidence_people,
            )
            result["parse_engine"] = "ai"
            story_world = self._build_story_world(text, payload, evidence_cards, result["persons"])
            result["story_world"] = story_world
            result["case_intelligence"] = normalize_case_intelligence({
                **result,
                "story_world": story_world,
                "case_intelligence": {
                    "claims": [
                        {
                            "claim_id": item.get("id"),
                            "statement": item.get("content"),
                            "claim_type": item.get("fact_type") or "statement",
                            "verification_status": item.get("status") or "unverified",
                            "certainty": "source_supported" if item.get("source_refs") else "unknown",
                            "source_refs": item.get("source_refs") or [],
                        }
                        for item in evidence_cards
                    ],
                    "unresolved_questions": result.get("inconsistencies") or result.get("parse_warnings") or [],
                },
            })
            result["source_quality"] = assess_source_quality(text)
            result["complete_story"] = story_world.get("complete_story") or ""
            if result["complete_story"]:
                result["full_narrative"] = result["complete_story"]
            result["narrative_document"] = {
                "schema_version": 1,
                "format": "markdown",
                "content": result.get("complete_story") or result.get("full_narrative") or text,
                "source_mode": source_mode,
                "role": "primary_readable_case_document",
                "policy": "human_readable_not_canonical_fact_source",
            }
            result["generation_mode"] = "narrative_first_v2"
            result["ai_workflow"] = {
                "correlation_id": correlation_id,
                "stage": "parallel_case_analysis",
                "primary_provider": narrative_trace.get("primary_provider"),
                "final_provider": narrative_trace.get("final_provider"),
                "used_rule_fallback": False,
                "architecture": "free_narrative_plus_programmatic_extraction",
                "attempts": narrative_trace.get("attempts") or [],
                "stage_timings_ms": {
                    "evidence_and_story_parallel": round((assembly_started - parallel_started) * 1000),
                    "deterministic_case_state_assembly": round((time.perf_counter() - assembly_started) * 1000),
                },
            }
            result["story_version_id"] = save_story_version(correlation_id=correlation_id, story=story_world, source_mode=source_mode)
            return result
            source_payload = {
                "source_meta": source_meta or {},
                "source_mode": source_mode,
                "evidence_cards": evidence_cards,
                "person_observations": evidence_people,
                "story_segments": story_segments,
                "source_chunk_count": len(self._chunk_source_text(text)),
                "parse_instruction": "根据全部 evidence_cards 重建案件世界观；不得把文档标记当作案情。",
            }
            # A single short source can be supplied in full as an additional
            # review anchor. Long sources are represented by all chunks above.
            if len(self._chunk_source_text(text)) == 1:
                source_payload["source_text"] = text
            payload, trace = self._call_case_ai(
                stage="case_worldview",
                correlation_id=correlation_id,
                messages=[
                    {"role": "system", "content": base_prompt + name_constraint + "\n\n" + WORLDVIEW_PROMPT},
                    {"role": "user", "content": json.dumps(source_payload, ensure_ascii=False)},
                ],
            )
            if isinstance(payload, dict) and payload:
                result = self._normalize_parsed_case(
                    text,
                    payload,
                    source_mode,
                    source_meta,
                    allowed_names=all_allowed_names if all_allowed_names else None,
                    evidence_people=evidence_people,
                )
                result["parse_engine"] = "ai"
                story_world = self._build_story_world(text, payload, evidence_cards, result["persons"])
                result["story_world"] = story_world
                result["complete_story"] = story_world.get("complete_story") or ""
                if result["complete_story"]:
                    result["full_narrative"] = result["complete_story"]
                result["ai_workflow"] = {
                    **trace,
                    "correlation_id": correlation_id,
                    "stage": "case_worldview",
                    "used_rule_fallback": False,
                }
                result["story_version_id"] = save_story_version(
                    correlation_id=correlation_id,
                    story=story_world,
                    source_mode=source_mode,
                )
                return result
        except Exception as exc:
            fallback = _safe_heuristic(f"AI 解析调用失败，已进入规则兜底：{exc}")
            fallback["ai_workflow"] = {"correlation_id": correlation_id, "stage": "case_worldview", "used_rule_fallback": True, "summary": str(exc)[:500]}
            record_issue(category="rule_fallback", severity="warning", title="案件解析已使用规则兜底", detail=str(exc), metadata=fallback["ai_workflow"])
            return fallback
        return _safe_heuristic("AI 解析未返回可用 JSON，已进入规则兜底。")

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

    def _roles_relevant_to_scene(
        self,
        case_info: dict[str, Any],
        story_world: dict[str, Any],
        fact_ids: list[str],
        scene_context: str = "",
    ) -> list[str]:
        """Return every speakable person directly grounded in a scene's facts.

        The model decides the scene design, but its abbreviated roles array is
        not a safe source of truth: a fact may name several people.  Add those
        people deterministically so the scene roster remains traceable.
        """
        selected_fact_ids = {str(value) for value in fact_ids if str(value).strip()}
        fact_texts: list[str] = [str(scene_context or "")]
        for card in story_world.get("fact_cards") or story_world.get("facts") or []:
            if not isinstance(card, dict) or str(card.get("id")) not in selected_fact_ids:
                continue
            fact_texts.append(str(card.get("content") or ""))
            fact_texts.extend(str(ref.get("summary") or "") for ref in card.get("source_refs") or [] if isinstance(ref, dict))
        context = "\n".join(fact_texts)
        relevant: list[str] = []
        for person in case_info.get("persons") or []:
            if not isinstance(person, dict) or not self._is_speakable_status(person.get("status")):
                continue
            name = str(person.get("name") or "").strip()
            if not name:
                continue
            aliases = [str(alias).strip() for alias in person.get("aliases") or [] if str(alias).strip()]
            memories = " ".join(
                str((memory or {}).get("content") or (memory or {}).get("statement") or "")
                for memory in person.get("role_memories") or []
                if isinstance(memory, dict)
            )
            if name in context or any(alias in context for alias in aliases) or any(fact_id in memories for fact_id in selected_fact_ids):
                relevant.append(name)
        return list(dict.fromkeys(relevant))

    def _bind_scene_people_to_story(
        self,
        case_info: dict[str, Any],
        scenes: list[dict[str, Any]],
        story_world: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Resolve each scene roster from the complete story, after scene design.

        Scene generation may use JSON, Markdown, or a rule fallback. None of
        those outputs is permitted to decide who is present. This final pass
        assigns source facts to one scene and admits a person only when their
        name or source memory is supported by that scene's assigned facts.
        """
        if not scenes:
            return []
        facts = [item for item in story_world.get("fact_cards") or [] if isinstance(item, dict) and str(item.get("id") or "").strip()]
        facts.sort(key=self._fact_source_start)
        if not facts:
            return scenes

        people = [item for item in case_info.get("persons") or [] if isinstance(item, dict) and self._is_speakable_status(item.get("status"))]
        fact_by_id = {str(item["id"]): item for item in facts}
        scene_texts = [" ".join([
            str(scene.get("scene_name") or ""), str(scene.get("scene_description") or ""),
            str(scene.get("dispatch_brief") or ""), " ".join(str(stage.get("stage_goal") or "") for stage in scene.get("stages") or [] if isinstance(stage, dict)),
        ]) for scene in scenes]

        def phase_score(scene_text: str, fact: dict[str, Any]) -> int:
            fact_text = str(fact.get("content") or "") + " ".join(str(ref.get("summary") or "") for ref in fact.get("source_refs") or [] if isinstance(ref, dict))
            score = 0
            if any(token in scene_text for token in ("现场", "先期", "隔离", "稳控", "伤情", "处置")) and any(token in fact_text for token in ("现场", "到场", "争执", "冲突", "受伤", "报警")):
                score += 4
            if any(token in scene_text for token in ("证人", "走访", "辨认", "证言")) and any(token in fact_text for token in ("证人", "证言", "陈述", "看见", "听见")):
                score += 5
            if any(token in scene_text for token in ("讯问", "审讯", "嫌疑", "供述", "传唤")) and any(token in fact_text for token in ("嫌疑", "供述", "辩解", "被告", "犯罪")):
                score += 5
            if any(token in scene_text for token in ("取证", "证据", "固定", "勘验")) and any(token in fact_text for token in ("证据", "监控", "照片", "鉴定", "物证", "伤情")):
                score += 4
            return score

        assigned = [[] for _ in scenes]
        for fact_index, fact in enumerate(facts):
            requested = [index for index, scene in enumerate(scenes) if str(fact.get("id")) in {str(value) for value in scene.get("fact_ids") or []}]
            scores = [phase_score(scene_text, fact) + (1 if index in requested else 0) for index, scene_text in enumerate(scene_texts)]
            best_score = max(scores)
            candidates = [index for index, score in enumerate(scores) if score == best_score]
            if best_score == 0:
                candidates = [fact_index % len(scenes)]
            target = min(candidates, key=lambda index: (len(assigned[index]), index))
            assigned[target].append(str(fact["id"]))

        result = []
        for scene_index, scene in enumerate(scenes):
            scene_fact_ids = assigned[scene_index]
            scoped_facts = [fact_by_id[fact_id] for fact_id in scene_fact_ids]
            scoped_text = "\n".join(str(fact.get("content") or "") + " " + " ".join(str(ref.get("summary") or "") for ref in fact.get("source_refs") or [] if isinstance(ref, dict)) for fact in scoped_facts)
            source_positions = {self._fact_source_start(fact) for fact in scoped_facts}
            ranked = []
            for person_index, person in enumerate(people):
                name = str(person.get("name") or "").strip()
                if not name:
                    continue
                score = 3 if name in scoped_text else 0
                for memory in person.get("role_memories") or []:
                    if not isinstance(memory, dict):
                        continue
                    for ref in memory.get("source_refs") or []:
                        if isinstance(ref, dict) and isinstance(ref.get("start"), int) and any(abs(ref["start"] - pos) < 1200 for pos in source_positions):
                            score = max(score, 2)
                if score:
                    ranked.append((-score, person_index, name))
            roles = [name for _score, _index, name in sorted(ranked)[:4]]
            if not roles:
                # A scene without direct name mentions may retain one explicit
                # dialogue target, but never inherit the all-case roster.
                requested = [str(name).strip() for name in scene.get("roles") or [] if str(name).strip() in {str(person.get("name") or "").strip() for person in people}]
                roles = requested[:1]
            bound = dict(scene)
            bound["roles"] = roles
            bound["fact_ids"] = scene_fact_ids
            bound["stages"] = [
                {**stage, "fact_ids": [fact_id for fact_id in stage.get("fact_ids") or [] if fact_id in scene_fact_ids] or scene_fact_ids}
                if isinstance(stage, dict) else stage
                for stage in scene.get("stages") or []
            ]
            result.append(bound)
        return result

    def _minimum_fallback_scenes(self, case_info: dict[str, Any], dispatch_brief: str) -> list[dict[str, Any]]:
        case_name = str(case_info.get("case_name") or "该案件").strip()
        case_type = str(case_info.get("case_type") or "").strip()
        story_world = case_info.get("story_world") if isinstance(case_info.get("story_world"), dict) else {}
        definitions = build_scene_portfolio_plan(case_info, story_world)
        primary_definition = next((item for item in definitions if item.get("portfolio_role") == "primary"), definitions[0])
        role_types_by_slot = {
            "intake": ["报警人", "证人", "相关人员", "被害人"],
            "primary": ["被害人", "证人", "相关人员", "嫌疑人"],
            "investigation": ["被害人", "证人", "嫌疑人", "相关人员"],
            "followup": ["被害人", "证人", "相关人员", "嫌疑人"],
        }
        scenes: list[dict[str, Any]] = []
        scene_name = str(primary_definition["scene_name"])
        portfolio_role = str(primary_definition.get("portfolio_role") or "primary")
        scenes.append({
            "scene_name": scene_name,
            "scene_description": f"围绕“{case_name}”开展{primary_definition['scene_purpose']}",
            "difficulty": "中等",
            "estimated_minutes": 45,
            "dispatch_brief": dispatch_brief,
            "first_impression": str(primary_definition.get("start_state") or "").strip(),
            "roles": self._pick_scene_roles(case_info, role_types_by_slot.get(portfolio_role, [])),
            "stages": normalize_stages(primary_definition["stages"], case_type=case_type, scene_name=scene_name),
            "training_entry_phase": primary_definition["training_entry_phase"],
            "entry_time_policy": primary_definition["entry_time_policy"],
            "canonical_outcome_locked": True,
            "student_role": "民警",
            "portfolio_role": portfolio_role,
            "is_primary": True,
            "scene_kind": primary_definition.get("scene_kind"),
            "scene_purpose": primary_definition.get("scene_purpose"),
            "training_goal": primary_definition.get("training_goal"),
            "start_state": primary_definition.get("start_state"),
            "completion_criteria": primary_definition.get("completion_criteria") or [],
            "end_prompt": primary_definition.get("end_prompt"),
        })
        return scenes

    def _fallback_scenes(self, case_info: dict[str, Any], *, scene_generation_strategy: str = "case_driven") -> dict[str, Any]:
        dispatch_brief = self._default_dispatch_brief(case_info, "接警研判")
        scenes = self._minimum_fallback_scenes(case_info, dispatch_brief)
        return {
            "scenes": scenes,
            "scene_generation_mode": (
                "fallback_template_first" if scene_generation_strategy == "template_first" else "fallback_case_driven"
            ),
            "scene_generation_warning": "本次 AI 剧本未完整返回，已按必要性原则生成一个主训练场景，请人工复核具体事实与角色分配。",
        }

    @staticmethod
    def _resolve_estimated_minutes(value: Any) -> int | None:
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return None
        return minutes if minutes > 0 else None

    def _normalize_scenes(
        self,
        case_info: dict[str, Any],
        payload: dict[str, Any],
        *,
        scene_generation_strategy: str = "case_driven",
        story_world: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scenes = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
        persons = case_info.get("persons") or []
        valid_names = {
            str(person.get("name") or "").strip()
            for person in persons
            if self._is_speakable_status(person.get("status")) or str(person.get("status") or "").strip() in {"正常", "受伤可交流", ""}
        }
        normalized = []
        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue
            roles = [name for name in self.canonicalize_role_names(scene.get("roles") or scene.get("role_names") or [], persons) if name in valid_names]
            present_roles = [name for name in self.canonicalize_role_names(scene.get("present_roles") or [], persons) if name in valid_names]
            if str(scene.get("training_entry_phase") or "").strip() == "post_incident_onsite":
                roles = list(dict.fromkeys([*present_roles, *roles]))
            fact_ids = [str(value) for value in scene.get("fact_ids") or [] if str(value).strip()]
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
            first_impression = self._normalize_first_impression_text(
                scene.get("first_impression") or self._default_first_impression(case_info, scene_name, dispatch_brief),
                scene_name,
            )
            stages = normalize_stages(stages, case_type=str(case_info.get("case_type") or ""), scene_name=scene_name)
            estimated_minutes = self._resolve_estimated_minutes(
                scene.get("estimated_minutes")
                or scene.get("estimate_minutes")
                or scene.get("duration_minutes")
                or scene.get("training_minutes")
            )
            normalized.append(
                {
                    "scene_name": scene_name,
                    "scene_description": str(scene.get("scene_description") or "围绕案件关键节点开展训练。").strip(),
                    "difficulty": str(scene.get("difficulty") or "中等").strip(),
                    "estimated_minutes": estimated_minutes,
                    "dispatch_brief": dispatch_brief,
                    "first_impression": first_impression,
                    "roles": roles,
                    "present_roles": present_roles,
                    "mentioned_roles": [
                        str(value).strip() for value in scene.get("mentioned_roles") or [] if str(value).strip()
                    ],
                    "stages": stages,
                    "fact_ids": fact_ids,
                    "supplement_ids": [str(value) for value in scene.get("supplement_ids") or [] if str(value).strip()],
                    "script_markdown": str(scene.get("script_markdown") or "").strip(),
                    "training_entry_phase": str(scene.get("training_entry_phase") or "").strip(),
                    "entry_time_policy": str(scene.get("entry_time_policy") or "").strip(),
                    "canonical_outcome_locked": True,
                    "student_role": "民警",
                    "scene_kind": str(scene.get("scene_kind") or "").strip(),
                    "portfolio_role": str(scene.get("portfolio_role") or "").strip(),
                    "is_primary": bool(scene.get("is_primary")),
                    "scene_purpose": str(scene.get("scene_purpose") or "").strip(),
                    "training_goal": str(scene.get("training_goal") or "").strip(),
                    "start_state": str(scene.get("start_state") or "").strip(),
                    "completion_criteria": [
                        str(value).strip() for value in scene.get("completion_criteria") or [] if str(value).strip()
                    ],
                    "end_prompt": str(scene.get("end_prompt") or "").strip(),
                }
            )
        if len(normalized) >= CASE_SCENE_MIN_COUNT:
            return {
                "scenes": normalized[:CASE_SCENE_MAX_COUNT],
                "scene_generation_mode": (
                    "ai_template_first" if scene_generation_strategy == "template_first" else "ai_case_driven"
                ),
                "scene_generation_warning": "",
            }
        return self._fallback_scenes(case_info, scene_generation_strategy=scene_generation_strategy)

    def _story_world_for_case(self, case_info: dict[str, Any]) -> dict[str, Any]:
        existing = case_info.get("story_world")
        if isinstance(existing, dict) and (existing.get("fact_cards") or existing.get("facts")):
            return existing
        return self._build_story_world(
            str(case_info.get("original_content") or case_info.get("rawText") or case_info.get("full_narrative") or ""),
            case_info,
            [],
        )

    @staticmethod
    def _scene_blueprint_candidates(
        scenes: list[dict[str, Any]],
        default_fact_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        defaults = list(default_fact_ids or [])
        return [
            {
                "scene_id": f"S{index}",
                "scene_name": scene.get("scene_name"),
                "scene_kind": scene.get("scene_kind") or scene.get("scene_name"),
                "portfolio_role": scene.get("portfolio_role"),
                "is_primary": bool(scene.get("is_primary")),
                "scene_purpose": scene.get("scene_purpose"),
                "training_goal": scene.get("training_goal") or scene.get("scene_description"),
                "start_state": scene.get("start_state"),
                "completion_criteria": scene.get("completion_criteria") or [],
                "end_prompt": scene.get("end_prompt"),
                "training_entry_phase": scene.get("training_entry_phase"),
                "entry_time_policy": scene.get("entry_time_policy"),
                "canonical_outcome_locked": True,
                "student_role": "民警",
                "roles": scene.get("roles") or [],
                "fact_ids": scene.get("fact_ids") or defaults,
                "stages": scene.get("stages") or [],
            }
            for index, scene in enumerate(scenes, start=1)
        ]

    def _valid_scene_blueprints(
        self,
        payload: dict[str, Any],
        case_info: dict[str, Any],
        story_world: dict[str, Any],
        persons: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        fact_ids = {str(item.get("id")) for item in story_world.get("fact_cards") or story_world.get("facts") or [] if isinstance(item, dict)}
        supplement_ids: set[str] = set()
        person_by_name = {
            str(item.get("name")): item for item in persons if isinstance(item, dict) and str(item.get("name") or "").strip()
        }
        person_names = set(person_by_name)
        blueprints = []
        for index, item in enumerate(payload.get("blueprints") or [], start=1):
            if not isinstance(item, dict):
                continue
            roles = [
                str(name).strip() for name in item.get("roles") or []
                if str(name).strip() in person_names
                and self._is_speakable_status(person_by_name[str(name).strip()].get("status"))
            ]
            present_roles = [str(name).strip() for name in item.get("present_roles") or [] if str(name).strip() in person_names]
            mentioned_roles = [str(name).strip() for name in item.get("mentioned_roles") or [] if str(name).strip() in person_names]
            refs = [str(value).strip() for value in item.get("fact_ids") or [] if str(value).strip() in fact_ids]
            supplements = [str(value).strip() for value in item.get("supplement_ids") or [] if str(value).strip() in supplement_ids]
            stages = [stage for stage in item.get("stages") or [] if isinstance(stage, dict) and str(stage.get("stage_name") or "").strip()]
            if not refs or not stages:
                continue
            scene_context = " ".join([
                str(item.get("scene_name") or ""),
                str(item.get("training_goal") or ""),
                " ".join(str(stage.get("stage_goal") or "") for stage in stages),
            ])
            blueprints.append({
                "scene_id": str(item.get("scene_id") or f"S{index}"),
                "scene_name": str(item.get("scene_name") or self._default_scene_name(index)).strip(),
                "scene_kind": str(item.get("scene_kind") or "现场处置").strip(),
                "training_goal": str(item.get("training_goal") or "围绕本案事实开展民警处置训练。").strip(),
                "story_node_ids": [str(value).strip() for value in item.get("story_node_ids") or [] if str(value).strip()],
                "time": str(item.get("time") or "").strip(),
                "place": str(item.get("place") or "").strip(),
                "roles": roles,
                "present_roles": list(dict.fromkeys([*present_roles, *roles])),
                "mentioned_roles": list(dict.fromkeys(mentioned_roles)),
                "fact_ids": refs,
                "open_question_ids": [str(value) for value in item.get("open_question_ids") or []],
                "supplement_ids": supplements,
                "stages": stages,
                "training_entry_phase": str(item.get("training_entry_phase") or "").strip(),
                "entry_time_policy": str(item.get("entry_time_policy") or "").strip(),
                "canonical_outcome_locked": True,
                "student_role": "民警",
                "portfolio_role": str(item.get("portfolio_role") or "").strip(),
                "is_primary": bool(item.get("is_primary")),
                "scene_purpose": str(item.get("scene_purpose") or "").strip(),
                "start_state": str(item.get("start_state") or "").strip(),
                "completion_criteria": [
                    str(value).strip() for value in item.get("completion_criteria") or [] if str(value).strip()
                ],
                "end_prompt": str(item.get("end_prompt") or "").strip(),
            })
        return blueprints[:CASE_SCENE_MAX_COUNT]

    @staticmethod
    def _fact_source_start(fact: dict[str, Any]) -> int:
        refs = fact.get("source_refs") if isinstance(fact, dict) else []
        values = [ref.get("start") for ref in refs if isinstance(ref, dict) and isinstance(ref.get("start"), int)]
        return min(values) if values else 10**9

    def _scope_scene_blueprints(
        self,
        blueprints: list[dict[str, Any]],
        case_info: dict[str, Any],
        story_world: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Keep the model's local fact scope without using worldview graphs as logic."""
        if not blueprints:
            return []
        valid_fact_ids = {
            str(item.get("id"))
            for item in story_world.get("fact_cards") or story_world.get("facts") or []
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        scoped: list[dict[str, Any]] = []
        for blueprint in blueprints:
            item = dict(blueprint)
            item["fact_ids"] = list(dict.fromkeys(
                str(value).strip()
                for value in item.get("fact_ids") or []
                if str(value).strip() in valid_fact_ids
            ))[:max(24, int(os.getenv("CASE_SCENE_FACT_LIMIT", "80")))]
            if not item["fact_ids"]:
                continue
            item["canonical_outcome_locked"] = True
            item["student_role"] = "民警"
            item["training_entry_phase"] = str(item.get("training_entry_phase") or "").strip() or "post_incident_onsite"
            item["entry_time_policy"] = "dispatch_intake" if item["training_entry_phase"] == "intake" else "after_canonical_event"
            person_names = {
                str(person.get("name") or "").strip()
                for person in case_info.get("persons") or []
                if isinstance(person, dict) and str(person.get("name") or "").strip()
            }
            item["roles"] = list(dict.fromkeys(
                str(name).strip() for name in item.get("roles") or [] if str(name).strip() in person_names
            ))
            item["present_roles"] = list(dict.fromkeys(
                str(name).strip() for name in item.get("present_roles") or item["roles"] if str(name).strip() in person_names
            ))
            item["mentioned_roles"] = list(dict.fromkeys(
                str(name).strip() for name in item.get("mentioned_roles") or [] if str(name).strip() in person_names
            ))
            scoped.append(item)
        return scoped

    @staticmethod
    def _validate_first_impression_text(value: Any) -> tuple[bool, str]:
        text = str(value or "").strip()
        if not text:
            return False, "现场第一印象为空"
        if len(text) < 80:
            return False, "现场第一印象少于 80 字，需补足可观察信息"
        if len(text) > 160:
            return False, "现场第一印象超过 160 字，需压缩为短段落"
        if "\n" in text:
            return False, "现场第一印象应为一个短段落，不能拆成多段"
        banned_keywords = (
            "接警信息", "报警信息", "接报警", "接到报警", "派出所接110指令", "110指令",
            "当前可接触人员", "可接触人员", "当前时空", "村→", "现场→", "→",
            "训练目标", "训练任务", "民警任务", "需要先核实", "形成出警判断",
            "围绕", "开展询问", "开展处置", "后续处置", "案件结论", "裁判结论",
            "隐藏证据", "当前仅掌握", "当前应围绕",
        )
        if any(keyword in text for keyword in banned_keywords):
            return False, "现场第一印象混入接警、路线、任务、角色清单或结论性信息"
        if re.search(r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}时\d{1,2}分|F\d+", text):
            return False, "现场第一印象混入时间线或事实编号"
        return True, ""

    @classmethod
    def _normalize_first_impression_text(cls, value: Any, scene_name: str) -> str:
        text = re.sub(r"\s+", " ", str(value or "").strip())
        valid, _reason = cls._validate_first_impression_text(text)
        if valid:
            return text
        candidates = [
            item.strip()
            for item in re.split(r"(?<=[。！？；;])", text)
            if item.strip()
        ]
        kept: list[str] = []
        for candidate in candidates:
            if len("".join(kept) + candidate) > 160:
                continue
            candidate_valid, _ = cls._validate_first_impression_text(candidate)
            if candidate_valid:
                kept.append(candidate)
        if kept:
            candidate = "".join(kept)
            if len(candidate) >= 80:
                return candidate
        if "接警" in scene_name or "报警" in scene_name:
            return "通话中报警人语速急促，背景持续传来争执、脚步和物品碰撞声，旁侧有人插话催促；声音远近不断变化，现场秩序明显不稳，是否有人受伤或持有危险物尚无法直接看清，冲突继续升级的风险仍然存在。"
        return "现场通道和出入口附近聚集着围观人员，交谈声与争执声交织；可见相关人员分散在不同位置，有人来回走动并持续指向事发区域，地面物品散乱，局部存在疑似伤情或危险物，人员再次接近可能引发二次冲突。"

    @staticmethod
    def _validate_scene_script(payload: dict[str, Any], blueprint: dict[str, Any], story_world: dict[str, Any]) -> tuple[bool, str]:
        allowed_facts = set(blueprint.get("fact_ids") or [])
        allowed_supplements = set(blueprint.get("supplement_ids") or [])
        allowed_roles = {str(value).strip() for value in blueprint.get("roles") or [] if str(value).strip()}
        script_facts = {str(value) for value in payload.get("fact_ids") or []}
        script_supplements = {str(value) for value in payload.get("supplement_ids") or []}
        script_roles = {str(value).strip() for value in payload.get("roles") or [] if str(value).strip()}
        if not script_facts or not script_facts.issubset(allowed_facts):
            return False, "剧本引用了不存在或未授权的事实卡"
        if not script_supplements.issubset(allowed_supplements):
            return False, "剧本引用了不存在或未授权的模拟补写"
        if script_roles and not script_roles.issubset(allowed_roles):
            return False, "剧本角色超出场景蓝图允许范围"
        impression_valid, impression_reason = WorkflowService._validate_first_impression_text(payload.get("first_impression"))
        if not impression_valid:
            return False, impression_reason
        if not isinstance(payload.get("stages"), list) or not payload.get("stages"):
            return False, "剧本未生成训练阶段"
        for stage in payload.get("stages") or []:
            if not isinstance(stage, dict):
                return False, "剧本阶段格式无效"
            stage_facts = {str(value) for value in stage.get("fact_ids") or []}
            if not stage_facts or not stage_facts.issubset(allowed_facts):
                return False, "阶段存在未关联案件事实"
        return True, ""

    def generate_scenes(
        self,
        case_info: dict[str, Any],
        scene_generation_strategy: str = "case_driven",
    ):
        if scene_generation_strategy not in {"template_first", "case_driven"}:
            scene_generation_strategy = "case_driven"
        correlation_id = new_correlation_id()
        story_world = self._story_world_for_case(case_info)
        persons = case_info.get("persons") if isinstance(case_info.get("persons"), list) else []
        compact_fact_cards = [
            {
                "id": item.get("id"),
                "content": str(item.get("content") or ""),
                "fact_type": item.get("fact_type"),
                "status": item.get("status"),
            }
            for item in story_world.get("fact_cards") or story_world.get("facts") or []
            if isinstance(item, dict) and item.get("id") and item.get("content")
        ]
        compact_people = [
            {
                "name": person.get("name"),
                "role_type": person.get("role_type") or person.get("role"),
                "status": person.get("status"),
                "current_goal": person.get("current_goal"),
                "core_concern": person.get("core_concern"),
                "behavior_profile": person.get("behavior_profile") or person.get("personality"),
                "triggers": person.get("triggers") or person.get("trigger_points"),
                "calming_points": person.get("calming_points") or person.get("soothing_points"),
                "answer_boundaries": person.get("answer_boundaries") or person.get("does_not_know"),
                "role_memories": (person.get("role_memories") or [])[:12],
            }
            for person in persons
            if isinstance(person, dict) and person.get("name")
        ]
        generation_context = {
            "case_name": case_info.get("case_name"),
            "case_type": case_info.get("case_type"),
            "complete_story": story_world.get("complete_story") or case_info.get("complete_story") or case_info.get("full_narrative") or "",
            "fact_cards": compact_fact_cards,
            "persons": compact_people,
            "scene_generation_strategy": scene_generation_strategy,
            "reference": build_case_frequency_prompt(),
            "scene_module_reference": build_scene_module_prompt(case_info),
        }
        portfolio_plan = build_scene_portfolio_plan(case_info, story_world)
        generation_context["candidate_scene_slots"] = portfolio_plan
        generation_context["scene_count_policy"] = {
            "min": CASE_SCENE_MIN_COUNT,
            "max": CASE_SCENE_MAX_COUNT,
            "principle": "必要性原则：单一场景可以完成训练目标时禁止拓展多场景；只有存在不可合并的实操训练目标时才生成多个场景。",
            "preferred_time_nodes": ["案发过程中学员可以介入控制和处置的阶段", "案发完毕后学员到场开展现场处置、人员接触、信息核实、线索摸排的阶段"],
            "avoid": ["审问", "讯问", "事后复盘", "总结汇报", "单纯接警信息复述", "无新增实操价值的同义场景"],
        }
        failure_reason = ""
        combined_trace: list[dict[str, Any]] = []
        try:
            blueprint_payload, blueprint_trace = self._call_case_ai(
                stage="scene_blueprint",
                correlation_id=correlation_id,
                messages=[{"role": "system", "content": SCENE_BLUEPRINT_PROMPT}, {"role": "user", "content": json.dumps(generation_context, ensure_ascii=False)}],
            )
            combined_trace.extend(blueprint_trace.get("attempts") or [])
            blueprints = self._valid_scene_blueprints(blueprint_payload, case_info, story_world, persons)
            blueprints = complete_scene_blueprint_portfolio(
                blueprints,
                portfolio_plan,
                story_world,
                persons,
            )
            blueprints = self._scope_scene_blueprints(blueprints, case_info, story_world)
            if len(blueprints) < CASE_SCENE_MIN_COUNT:
                raise ValueError("案件事实不足以形成可用训练场景")
            def generate_script(blueprint: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
                facts = [
                    {
                        "id": item.get("id"),
                        "content": str(item.get("content") or ""),
                        "fact_type": item.get("fact_type"),
                        "status": item.get("status"),
                    }
                    for item in story_world.get("fact_cards") or story_world.get("facts") or []
                    if isinstance(item, dict) and item.get("id") in blueprint["fact_ids"]
                ][:max(24, int(os.getenv("CASE_SCENE_FACT_LIMIT", "80")))]
                script_people = [item for item in compact_people if item.get("name") in blueprint.get("roles", [])]
                script_payload, script_trace = self._call_case_ai(
                    stage="scene_script",
                    correlation_id=correlation_id,
                    messages=[
                        {"role": "system", "content": SCENE_SCRIPT_PROMPT},
                        {"role": "user", "content": json.dumps({"blueprint": blueprint, "fact_cards": facts, "persons": script_people}, ensure_ascii=False)},
                    ],
                )
                return blueprint, script_payload, script_trace

            workers = min(len(blueprints), max(1, int(os.getenv("CASE_AI_PARALLELISM", "3"))))
            if workers > 1:
                with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scene-script") as executor:
                    generated_scripts = list(executor.map(generate_script, blueprints))
            else:
                generated_scripts = [generate_script(blueprint) for blueprint in blueprints]

            scenes = []
            for blueprint, script_payload, script_trace in generated_scripts:
                combined_trace.extend(script_trace.get("attempts") or [])
                valid, reason = self._validate_scene_script(script_payload, blueprint, story_world)
                if not valid:
                    repair_payload, repair_trace = self._call_case_ai(
                        stage="scene_repair",
                        correlation_id=correlation_id,
                        messages=[
                            {"role": "system", "content": "你是场景 JSON 定向修复器。只输出完整 JSON；不得重写案件，不得新增人物或事实。roles 只能使用 allowed_roles；fact_ids 只能使用 allowed_fact_ids。first_impression 必须改为 80-160 字单段现场观察，只写环境、人员位置、当前动作、伤情/危险物、声音/围观干扰和即时风险，禁止接警时间、路线链路、任务说明、可接触人员名单和案件结论。"},
                            {"role": "user", "content": json.dumps({"invalid_script": script_payload, "blueprint": blueprint, "validation_error": reason, "allowed_fact_ids": blueprint.get("fact_ids") or [], "allowed_roles": blueprint.get("roles") or []}, ensure_ascii=False)},
                        ],
                    )
                    combined_trace.extend(repair_trace.get("attempts") or [])
                    valid, reason = self._validate_scene_script(repair_payload, blueprint, story_world)
                    if not valid:
                        raise ValueError(f"{blueprint['scene_name']}：{reason}")
                    script_payload = repair_payload
                # Blueprint scope is authoritative. A script model receives the
                # full person list for reference, so its own roles array must
                # never broaden the scene roster or reintroduce all-case facts.
                script_payload["roles"] = blueprint["roles"]
                script_payload["fact_ids"] = blueprint["fact_ids"]
                script_payload["scene_name"] = script_payload.get("scene_name") or blueprint["scene_name"]
                for key in (
                    "portfolio_role", "is_primary", "scene_kind", "scene_purpose", "training_goal",
                    "start_state", "completion_criteria", "end_prompt", "training_entry_phase",
                    "entry_time_policy", "canonical_outcome_locked", "student_role",
                ):
                    script_payload[key] = blueprint.get(key)
                scenes.append(script_payload)
            result = self._normalize_scenes(
                case_info,
                {"scenes": scenes},
                scene_generation_strategy=scene_generation_strategy,
                story_world=story_world,
            )
            if not result.get("scenes") or str(result.get("scene_generation_mode") or "").startswith("fallback"):
                raise ValueError("场景标准化未产生可用训练场景")
            result["scenes"] = bind_scenes_to_story(result["scenes"], blueprints)
            result["scenes"] = compile_scene_lifecycles(case_info, result["scenes"])
            result["scene_blueprints"] = blueprints
            result["training_tasks"] = build_training_tasks(case_info, result.get("scenes") or [])
            result["state_machine"] = compile_state_machine(result["training_tasks"])
            result["observable_scoring_rules"] = build_observable_scoring_rules(result["training_tasks"])
            result["ai_workflow"] = {
                "correlation_id": correlation_id,
                "primary_provider": (combined_trace[0] if combined_trace else {}).get("provider"),
                "final_provider": (combined_trace[-1] if combined_trace else {}).get("provider"),
                "failed_attempts": sum(1 for item in combined_trace if item.get("status") != "success"),
                "switched_provider": len({item.get("provider") for item in combined_trace if item.get("provider")}) > 1,
                "attempts": combined_trace,
                "used_rule_fallback": False,
            }
            return result
        except Exception as exc:
            failure_reason = f"AI 场景生成调用失败：{exc}"
            # JSON is a transport contract, not a reason to abandon the model.
            # If the large blueprint/script JSON cannot be parsed, request a
            # readable template and map its named fields back to scene records.
            try:
                text_scene, text_trace = self._call_scene_text_ai(
                    stage="scene_text_template",
                    correlation_id=correlation_id,
                    messages=[
                        {"role": "system", "content": SCENE_TEXT_TEMPLATE_PROMPT},
                        {"role": "user", "content": json.dumps({"case_name": case_info.get("case_name"), "case_type": case_info.get("case_type"), "fact_cards": compact_fact_cards, "persons": compact_people}, ensure_ascii=False)},
                    ],
                )
                combined_trace.extend(text_trace.get("attempts") or [])
                text_scenes = self._scenes_from_text_template(text_scene, case_info, story_world)
                text_result = self._normalize_scenes(
                    case_info,
                    {"scenes": text_scenes},
                    scene_generation_strategy=scene_generation_strategy,
                    story_world=story_world,
                )
                if text_result.get("scenes") and not str(text_result.get("scene_generation_mode") or "").startswith("fallback"):
                    text_plan = portfolio_plan[:max(CASE_SCENE_MIN_COUNT, min(len(text_result["scenes"]), CASE_SCENE_MAX_COUNT))]
                    text_blueprints = complete_scene_blueprint_portfolio(
                        self._scene_blueprint_candidates(text_result["scenes"]),
                        text_plan,
                        story_world,
                        persons,
                    )
                    text_blueprints = self._scope_scene_blueprints(text_blueprints, case_info, story_world)
                    if not text_blueprints:
                        raise ValueError("纯文本场景模板未形成有事实绑定的蓝图")
                    text_result["scenes"] = bind_scenes_to_story(text_result["scenes"][:len(text_blueprints)], text_blueprints)
                    text_result["scenes"] = compile_scene_lifecycles(case_info, text_result["scenes"])
                    text_result["scene_generation_mode"] = "ai_text_template"
                    text_result["scene_generation_warning"] = "大 JSON 场景生成未通过校验，已由 AI 纯文本剧本模板生成场景，请人工复核。"
                    text_result["ai_workflow"] = {
                        "correlation_id": correlation_id,
                        "primary_provider": (combined_trace[0] if combined_trace else {}).get("provider"),
                        "final_provider": (combined_trace[-1] if combined_trace else {}).get("provider"),
                        "failed_attempts": sum(1 for item in combined_trace if item.get("status") != "success"),
                        "switched_provider": len({item.get("provider") for item in combined_trace if item.get("provider")}) > 1,
                        "attempts": combined_trace,
                        "used_rule_fallback": False,
                    }
                    return text_result
            except Exception as text_exc:
                failure_reason = f"{failure_reason}；AI 纯文本场景模板也失败：{text_exc}"
        fallback = self._fallback_scenes(case_info, scene_generation_strategy=scene_generation_strategy)
        fallback_blueprints = self._scope_scene_blueprints(
            self._scene_blueprint_candidates(
                fallback.get("scenes") or [],
                [str(item.get("id")) for item in compact_fact_cards[:8] if item.get("id")],
            ),
            case_info,
            story_world,
        )
        fallback["scenes"] = bind_scenes_to_story((fallback.get("scenes") or [])[:len(fallback_blueprints)], fallback_blueprints)
        fallback["scenes"] = compile_scene_lifecycles(case_info, fallback["scenes"])
        fallback["scene_generation_warning"] = (
            f"{fallback['scene_generation_warning']} 原因：{failure_reason}"
            if failure_reason
            else fallback["scene_generation_warning"]
        )
        fallback["scene_generation_failure_reason"] = failure_reason
        fallback["ai_workflow"] = {"correlation_id": correlation_id, "attempts": combined_trace, "used_rule_fallback": True, "summary": failure_reason[:1000]}
        run_id = record_workflow_run(
            correlation_id=correlation_id,
            stage="scene_generation",
            trace={"attempts": combined_trace},
            status="fallback",
            used_rule_fallback=True,
            error_code="SCENE_GENERATION_FAILED",
            error_summary=failure_reason,
        )
        record_issue(category="rule_fallback", severity="warning", title="场景生成已使用规则兜底", detail=failure_reason, workflow_run_id=run_id, metadata=fallback["ai_workflow"])
        return fallback

    def generate_complete_case_story(self, source_text: str) -> tuple[str, dict[str, Any]]:
        """Step C: generate complete case narrative and basic metadata from cleaned source."""
        from .case_text_utils import strip_document_artifacts
        from .prompts.case_pipeline import COMPLETE_CASE_STORY_PROMPT
        from .llm_provider import get_story_generation_binding, get_story_generation_kwargs

        clean = strip_document_artifacts(source_text)
        if not clean:
            raise ValueError("案件正文为空，无法生成完整剧情")

        llm_client, model, provider, _ = get_story_generation_binding()
        response, trace = create_json_chat_completion(
            messages=[
                {"role": "system", "content": COMPLETE_CASE_STORY_PROMPT},
                {"role": "user", "content": clean[:28000]},
            ],
            model=model,
            llm_client=llm_client,
            temperature=0.2,
            max_tokens=max(8000, int(os.getenv("CASE_STORY_MAX_TOKENS", "16000"))),
            return_trace=True,
            extra_kwargs=get_story_generation_kwargs(),
            allow_provider_fallback=os.getenv("CASE_STORY_ALLOW_PROVIDER_FALLBACK", "0").strip() == "1",
        )
        payload = extract_json_payload(extract_message_text(response)) or {}
        story = strip_document_artifacts(payload.get("complete_story") or clean)
        if story and not story.startswith("#"):
            story = "# 案件完整剧情\n\n" + story.lstrip("# ")
        trace["story_metadata"] = {
            "case_name": str(payload.get("case_name") or "").strip(),
            "case_type": str(payload.get("case_type") or "").strip(),
            "case_background": str(payload.get("case_background") or "").strip(),
            "provider": provider,
            "model": model,
        }
        return story or clean, trace


workflow_service = WorkflowService()
