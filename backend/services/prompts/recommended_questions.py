"""追问话术提示词 — 最小版本。"""

RECOMMENDED_QUESTIONS_PROMPT = """根据当前案件情况，以民警视角生成 3-5 条可以问的问题。
案件: {case_title}  场景: {scene_name}  阶段: {current_stage}
角色: {role_name} ({role_type})
已掌握: {revealed_info}
缺失项: {missing_requirements}
最近对话: {recent_messages}
只输出 JSON 数组: [{{"text":"问题内容","category":"信息核实","priority":"high"}}]
"""
