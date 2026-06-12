#!/usr/bin/env python3
"""Add NAME_EXTRACTION_PROMPT to workflow_service.py"""
import re

with open('backend/services/workflow_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

name_prompt = '''NAME_EXTRACTION_PROMPT = """你是公安警情训练平台的人物名称识别专家。

任务：从以下案件文本中，找出所有**真实人物的姓名**，返回一个纯 JSON 字符串数组。

核心规则（严格遵循）：
1. 只提取2-4个汉字的真实人名（如：张三、李四、王小明、赵建国）。
2. **绝对不能**把以下类型当作人名输出：
   - 地名（如：某某村、东风路、向阳街、幸福小区、某小区、某村）
   - 名词/抽象词（如：证言、陈述、供述、交代、案情、纠纷、口供、笔录）
   - 物品名称（如：电动车、手机、菜刀、木棍、汽车、钱包）
   - 角色称谓本身（如：嫌疑人、被害人、报警人、证人、邻居、家属、报警、报案）
3. 同一人物只保留一个标准名称。如果文本中出现同一人的不同写法（如"张三供述"中的"张三"和"张三审讯"中的"张三"），只保留最简洁的标准名"张三"。
4. 如果文本中没有任何明确的人名，返回空数组 []。
5. 只输出一个合法的 JSON 数组，不要 markdown、解释或额外说明。

示例：
输入："报警人张三称，其与邻居李四因纠纷发生冲突，李四手持木棍打伤张三。"
输出：["张三", "李四"]

输入："某某村幸福小区发生一起邻里纠纷，现场无人员受伤。"
输出：[]

输入："据被害人王小花陈述，嫌疑人赵大龙在东风路持刀抢劫其手机。"
输出：["王小花", "赵大龙"]

输入："民警到场后，证言显示某某村的李某和王某因琐事发生口角。"
输出：["李某", "王某"]
"""

'''

old = '"parse_engine": "heuristic",\n}'
new = '"parse_engine": "heuristic",\n}\n\n' + name_prompt
content = content.replace(old, new, 1)

with open('backend/services/workflow_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('NAME_EXTRACTION_PROMPT added successfully')
