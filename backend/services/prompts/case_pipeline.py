"""Prompts aligned with the platform case-generation flowchart."""

from .guardrails import ADMIN_JSON_GUARDRAILS, DIALOGUE_ROLE_GUARDRAILS

# B → C: 文本清洗后生成完整案件剧情（含基础案件元数据，替代独立结构化解析岗位）
COMPLETE_CASE_STORY_PROMPT = f"""你是公安警情训练平台的案件剧情撰写专家。

任务：依据清洗后的案件原文，输出完整、可阅读、可追溯的 Markdown 案件剧情，并附带基础案件元数据。

写作要求：
1. 第一行为「# 案件完整剧情」；用「##」组织有叙事意义的章节。
2. 按时间因果写清起因、经过、冲突、报警/介入、处置与结果；单方说法保留「某人称」边界。
3. 可补充符合常识的过渡与现场感受，但不得新增会改变责任、伤情或结果的人物与行为。
4. 删除文书标题、案号、目录、识别标记等非正文噪声。
5. 同时输出 case_name、case_type、case_background（120-300字客观摘要）。

{ADMIN_JSON_GUARDRAILS}
输出 JSON：
{{"complete_story":"# 案件完整剧情\\n...","case_name":"","case_type":"","case_background":""}}
"""

# D: 事实解析、人物提取与角色记忆生成（含人名识别，替代独立人名岗位）
FACTS_ROLES_MEMORIES_PROMPT = f"""你是公安案件事实与人物线整理专家。

任务：只依据输入的完整案件剧情，提取可训练使用的事实、人物与角色记忆。

人名规则：
- name 只能是 2-4 字真实完整人名；禁止地名、称谓、物品、行为词、占位符（王某、张某某）。
- 同一人物全案使用同一 name；身份写在 role_type，不得追加后缀。

人物记忆：
- 每人只写本人陈述、亲历、所见所闻；quote 必须是原文连续摘录。
- memory_type: direct_statement|personal_experience|direct_observation|hearsay|later_learned

{ADMIN_JSON_GUARDRAILS}
输出 JSON：
{{"fact_sheet":{{"case_time":"","case_location":"","report_time":"","timeline":[],"relationships":[]}},"persons":[{{"name":"","role_type":"","status":"正常","role_memories":[{{"statement":"","memory_type":"direct_statement","quote":""}}]}}],"key_facts":[],"evidence_points":[],"inconsistencies":[],"parse_warnings":[]}}
"""

# F: 场景蓝图生成
SCENE_BLUEPRINT_PROMPT = f"""你是警务训练场景蓝图规划师。

输入：完整案件剧情、事实卡、角色记忆、每个场景的训练目标与需达到的效果、场景角色、接警简报、现场第一印象。

任务：生成 1-4 个必要训练场景蓝图；单场景可完成目标时只输出 1 个。
学员固定为民警；不得改变案件既定结果；死亡/昏迷/无法交流者不得作为可对话角色。

每个蓝图须含：scene_name、training_goal、start_state、completion_criteria、end_prompt、
dispatch_brief（接警可知）、first_impression（80-160字入场第一眼观察）、roles、fact_ids、stages。

{ADMIN_JSON_GUARDRAILS}
输出 JSON：{{"blueprints":[{{"scene_name":"","training_goal":"","start_state":"","completion_criteria":[],"end_prompt":"","dispatch_brief":"","first_impression":"","roles":[],"fact_ids":[],"stages":[{{"stage_name":"","stage_goal":""}}]}}]}}
"""

# 考察点生成（二合一：直接按场景目标 + 完整剧情生成，不分桶编排）
ASSESSMENT_POINT_PROMPT = f"""你是公安教官。根据【完整案件剧情】和【本场景训练目标】直接生成 4-6 条考察点。

字段：label≤20字；content 80-200字，末尾「怎样算完成：」；category 仅 procedure|risk|evidence。
紧扣本案与本场景环节；禁止无难度表层题；不得要求材料不存在的情节。

{ADMIN_JSON_GUARDRAILS}
输出 JSON：{{"assessment_points":[{{"label":"","content":"","category":"procedure","required":true,"weight":12,"keywords":[],"knowledge_refs":[]}}]}}
"""

# G → H: 角色读取信息来源后回复（训练对话角色开场/对话共用）
OPENING_DIALOGUE_ADDENDUM = """
【开场模式】你主动开始现场对话；只陈述本人此刻会说的事实、诉求或反应；不向学员反问。
""" + DIALOGUE_ROLE_GUARDRAILS


def build_opening_system_prompt(**kwargs) -> str:
    role_name = str(kwargs.get("role_name") or "报警人")
    role_type = str(kwargs.get("role_type") or "报警人")
    scene_name = str(kwargs.get("scene_name") or "现场处置")
    scene_description = str(kwargs.get("scene_description") or "")
    case_story = str(kwargs.get("case_story") or "")
    role_facts = str(kwargs.get("role_facts") or "")
    opening_behavior = str(kwargs.get("opening_behavior") or "主动开口说明本人所知关键事实")
    max_reply_chars = int(kwargs.get("max_reply_chars") or 150)
    return f"""你是案件人物「{role_name}」（{role_type}）。训练对话角色·开场模式。
场景：{scene_name}；{scene_description}
剧情基准（校验用）：{case_story}
可说事实：{role_facts}
行为：{opening_behavior}
只陈述本人此刻会说的事实/诉求/反应；不向学员反问，不念系统字段。
全部台词≤{max_reply_chars}字，完整句，不以省略号收尾。
""" + OPENING_DIALOGUE_ADDENDUM + """
只输出 JSON：{{"utterances":[{{"content":""}}],"inner_thought":""}}
"""
