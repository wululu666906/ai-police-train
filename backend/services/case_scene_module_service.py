"""Reality-oriented scene modules for case-driven police training generation."""

from __future__ import annotations

import re
from typing import Any


OFFICIAL_CASE_FREQUENCY_REFERENCE: list[dict[str, Any]] = [
    {
        "rank": 1,
        "case_family": "纠纷求助与现场稳控",
        "common_cases": ["邻里纠纷", "家庭纠纷", "情感纠纷", "劳资纠纷", "消费纠纷", "噪音扰民", "宠物纠纷"],
        "scene_focus": "情绪稳控、风险筛查、分离双方、调解边界、伤情与证据固定",
    },
    {
        "rank": 2,
        "case_family": "电信网络诈骗与预警劝阻",
        "common_cases": ["刷单返利", "冒充客服", "虚假投资理财", "冒充公检法", "网络贷款", "屏幕共享"],
        "scene_focus": "阻断转账、止付冻结、电子证据固定、诈骗话术和资金链路核查",
    },
    {
        "rank": 3,
        "case_family": "盗窃等侵财警情",
        "common_cases": ["盗窃电动车/手机", "入室盗窃", "拉车门盗窃", "商铺盗窃", "扒窃"],
        "scene_focus": "失窃要素核实、现场保护、监控走访、可疑人员和赃物去向追问",
    },
    {
        "rank": 4,
        "case_family": "交通警情与酒驾醉驾",
        "common_cases": ["交通事故", "酒驾醉驾", "肇事逃逸", "路面纠纷"],
        "scene_focus": "地点伤情核实、二次事故预防、现场保护、呼气检测、驾驶轨迹询问",
    },
    {
        "rank": 5,
        "case_family": "打架斗殴与故意伤害",
        "common_cases": ["打架斗殴", "故意伤害", "寻衅滋事", "持械威胁"],
        "scene_focus": "伤情风险、持械与聚集风险、双方陈述矛盾、现场证据固定",
    },
    {
        "rank": 6,
        "case_family": "走失、自伤和救助类警情",
        "common_cases": ["失踪求助", "自杀干预", "精神异常求助", "老人儿童走失", "醉酒求助"],
        "scene_focus": "生命安全优先、定位与关系链核查、安抚谈判、医疗和家属联动",
    },
    {
        "rank": 7,
        "case_family": "黄赌毒与场所治安线索",
        "common_cases": ["赌博", "卖淫嫖娼", "涉毒", "娱乐场所治安问题"],
        "scene_focus": "举报线索甄别、现场控制检查、物证电子证据、人员分工和上下线线索",
    },
    {
        "rank": 8,
        "case_family": "校园与未成年人警情",
        "common_cases": ["校园打架", "未成年人走失", "欺凌纠纷", "校外滋扰"],
        "scene_focus": "未成年人保护、学校家长联动、伤情与证据固定、隐私和二次伤害控制",
    },
    {
        "rank": 9,
        "case_family": "高风险侵害和人身财产案件",
        "common_cases": ["抢劫", "抢夺", "敲诈勒索", "非法侵入住宅", "威胁恐吓"],
        "scene_focus": "人身风险核查、嫌疑人去向、财物损失、现场追查和保护受害人",
    },
    {
        "rank": 10,
        "case_family": "网络与平台交易纠纷",
        "common_cases": ["网购消费纠纷", "租房平台纠纷", "游戏账号交易", "二手交易纠纷"],
        "scene_focus": "民事/治安/诈骗边界识别、平台证据固定、交易链路核查",
    },
]


def _module(
    module_id: str,
    title: str,
    case_families: list[str],
    triggers: list[str],
    stage_examples: list[tuple[str, str]],
    role_types: list[str],
    scene_kind_hint: str,
    difficulty: str,
    first_impression_hint: str,
) -> dict[str, Any]:
    return {
        "module_id": module_id,
        "title": title,
        "case_families": case_families,
        "triggers": triggers,
        "stage_examples": [{"stage_name": name, "stage_goal": goal} for name, goal in stage_examples],
        "role_types": role_types,
        "scene_kind_hint": scene_kind_hint,
        "difficulty": difficulty,
        "first_impression_hint": first_impression_hint,
    }


SCENE_MODULES: list[dict[str, Any]] = [
    _module(
        "dispute_risk_screening",
        "冲突警情风险稳控",
        ["纠纷求助与现场稳控", "打架斗殴与故意伤害"],
        ["纠纷", "争吵", "吵架", "打架", "推搡", "持械", "受伤", "邻里", "家庭", "情感"],
        [("现实风险筛查", "核实是否仍在冲突、是否有人受伤、是否持械或聚集。"), ("安全隔离引导", "引导报警人保持安全距离并等待民警。")],
        ["报警人", "被害人", "证人", "相关人员"],
        "intake",
        "中等",
        "报警人可能情绪激动，只想要求处理，需要先确认安全和是否需要增援。",
    ),
    _module(
        "dispute_scene_separation",
        "现场分离与证据固定",
        ["纠纷求助与现场稳控", "打架斗殴与故意伤害"],
        ["现场", "双方", "分离", "伤情", "监控", "证人", "物品损坏", "调解"],
        [("分离双方稳控现场", "先控制双方距离，告知身份，避免二次冲突。"), ("伤情证据固定", "核实伤情、监控、物损、目击人和现场遗留物。")],
        ["报警人", "被害人", "证人", "相关人员"],
        "onsite",
        "中等",
        "双方可能各执一词，现场情绪未完全平复，需要先控制再核实。",
    ),
    _module(
        "dispute_statement_contradiction",
        "双方陈述矛盾核查",
        ["纠纷求助与现场稳控", "打架斗殴与故意伤害"],
        ["谁先", "动手", "矛盾", "口供", "陈述", "否认", "伤情来源", "起因"],
        [("冲突起因压实", "分别核实起因、升级节点、谁先动手和是否使用工具。"), ("陈述矛盾核查", "对双方不一致处逐项追问并明确后续处置路径。")],
        ["嫌疑人", "被害人", "证人", "相关人员"],
        "investigation",
        "高",
        "基础事实已掌握，重点是把双方陈述差异、伤情与证据对应起来。",
    ),
    _module(
        "fraud_warning_dissuasion",
        "涉诈警情预警劝阻",
        ["电信网络诈骗与预警劝阻", "网络与平台交易纠纷"],
        ["诈骗", "刷单", "客服", "投资", "理财", "贷款", "公检法", "验证码", "屏幕共享", "转账"],
        [("诈骗线索核实", "核实诈骗方式、对方身份、联系渠道和已发生资金操作。"), ("紧急止付引导", "判断是否需要立即止付、冻结、保全聊天和转账证据。")],
        ["报警人", "被害人", "相关人员"],
        "intake",
        "中等",
        "报警人可能紧张、懊悔或仍相信对方，需要先稳住情绪并阻断继续转账。",
    ),
    _module(
        "fraud_fund_evidence",
        "资金流与电子证据核查",
        ["电信网络诈骗与预警劝阻", "网络与平台交易纠纷"],
        ["转账", "银行卡", "流水", "聊天记录", "通话", "链接", "二维码", "APP", "平台"],
        [("转账链路还原", "按时间顺序核实转账次数、金额、账户、平台和操作诱因。"), ("电子证据固定", "保存聊天记录、通话记录、网址链接、二维码和付款凭证。")],
        ["被害人", "报警人", "相关人员"],
        "onsite",
        "高",
        "手机或平台中可能仍保留聊天、转账、网页或 APP 记录，需引导当事人配合固定。",
    ),
    _module(
        "fraud_script_inquiry",
        "涉诈话术细节询问",
        ["电信网络诈骗与预警劝阻"],
        ["话术", "诱导", "威胁", "冒充", "下载", "共享屏幕", "验证码", "继续转账"],
        [("话术节点压实", "追问对方如何取得信任、如何施压、何时要求转账或下载软件。"), ("持续风险排查", "核实是否还有借贷、验证码泄露、屏幕共享等持续风险。")],
        ["被害人", "相关人员", "证人"],
        "investigation",
        "高",
        "基础警情已掌握，重点转向诈骗话术、时间线和仍可能扩大的风险。",
    ),
    _module(
        "theft_loss_report",
        "失窃警情要素核实",
        ["盗窃等侵财警情"],
        ["盗窃", "被偷", "丢失", "电动车", "手机", "钱包", "入室", "商铺", "拉车门"],
        [("失窃要素确认", "核实失窃物品、发现时间、最后一次见到物品的时间地点。"), ("线索保全提示", "提醒保留现场、监控、票据、序列号或车辆信息。")],
        ["报警人", "被害人", "相关人员"],
        "intake",
        "低",
        "报警人通常急于找回财物，可能先描述损失，需要引导其补齐时间和地点。",
    ),
    _module(
        "theft_scene_check",
        "盗窃现场勘查",
        ["盗窃等侵财警情"],
        ["门锁", "窗户", "撬", "翻动", "监控", "出入口", "车门", "柜台", "痕迹"],
        [("出入口痕迹核查", "检查门窗、锁具、车门、柜台等是否存在撬动或异常。"), ("监控证人固定", "查找监控覆盖范围、目击人员和可疑时间段。")],
        ["被害人", "证人", "相关人员"],
        "onsite",
        "中等",
        "现场可能存在被翻动、监控盲区或多人进出情况，需先保护现场再问询。",
    ),
    _module(
        "theft_suspect_inquiry",
        "盗窃可疑线索询问",
        ["盗窃等侵财警情", "高风险侵害和人身财产案件"],
        ["嫌疑", "可疑", "赃物", "销赃", "交易", "去向", "同伙", "异常消费"],
        [("可疑时间线压实", "让对象说明案发前后去向、接触物品机会和与被害人的关系。"), ("赃物线索追问", "追问物品流向、交易平台、同伴和异常消费情况。")],
        ["嫌疑人", "证人", "相关人员"],
        "investigation",
        "高",
        "已掌握部分线索，需围绕可疑时间段和物品去向压实陈述。",
    ),
    _module(
        "traffic_report",
        "交通事故报警核实",
        ["交通警情与酒驾醉驾"],
        ["交通事故", "车祸", "碰撞", "追尾", "受伤", "堵车", "肇事逃逸"],
        [("地点伤情确认", "核实具体位置、方向、车辆数量、人员伤情和救助需求。"), ("二次事故预防", "提示设置警示、撤离安全区域并保持现场信息。")],
        ["报警人", "驾驶人", "被害人", "证人"],
        "intake",
        "低",
        "报警人可能处在道路环境中，需优先确认安全位置和救助需求。",
    ),
    _module(
        "traffic_scene_protection",
        "交通事故现场保护",
        ["交通警情与酒驾醉驾"],
        ["事故现场", "警示", "车牌", "驾驶证", "行驶证", "碰撞痕迹", "监控", "目击"],
        [("现场警戒处置", "设置警示、保护现场、疏导交通并防止二次事故。"), ("车辆人员证据固定", "核实驾驶证、行驶证、车牌、碰撞痕迹和监控证人。")],
        ["驾驶人", "被害人", "证人", "相关人员"],
        "onsite",
        "中等",
        "现场可能有围观、拥堵或车辆移动风险，需要先保护现场再问询。",
    ),
    _module(
        "drunk_driving_check",
        "酒驾醉驾现场查处",
        ["交通警情与酒驾醉驾"],
        ["酒驾", "醉驾", "喝酒", "酒精", "吹气", "拒测", "继续驾驶"],
        [("身份告知与控制车辆", "表明身份和检查事由，防止驾驶人继续驾驶或离开。"), ("呼气检测实施", "依法告知并实施呼气酒精检测，固定现场过程。")],
        ["驾驶人", "证人", "相关人员"],
        "onsite",
        "中等",
        "驾驶人可能辩解、拒测或试图离开，需要规范告知并固定证据。",
    ),
    _module(
        "missing_person_search",
        "走失人员信息核查",
        ["走失、自伤和救助类警情", "校园与未成年人警情"],
        ["走失", "失踪", "找不到", "老人", "儿童", "学生", "离家", "失联"],
        [("最后出现信息", "核实最后出现时间、地点、衣着、随身物品和可能去向。"), ("关系链排查", "核实亲友、学校、医院、车站等可联系或可查找地点。")],
        ["报警人", "家属", "证人", "相关人员"],
        "intake",
        "中等",
        "报警人通常焦急，需要先获得可用于查找的具体信息和风险等级。",
    ),
    _module(
        "self_harm_intervention",
        "自伤轻生风险干预",
        ["走失、自伤和救助类警情"],
        ["轻生", "自杀", "跳楼", "割腕", "绝望", "威胁自伤", "服药"],
        [("生命风险确认", "确认位置、工具、伤情、是否独处和可接触的刺激源。"), ("安抚牵挂建立", "用低刺激话术稳定对象，寻找牵挂人和可协助资源。")],
        ["当事人", "报警人", "家属", "相关人员"],
        "onsite",
        "高",
        "对象可能绝望或抗拒，必须先降低刺激、确保生命安全，再推进信息核实。",
    ),
    _module(
        "public_order_tip",
        "黄赌毒治安线索核查",
        ["黄赌毒与场所治安线索"],
        ["赌博", "卖淫", "嫖娼", "涉毒", "吸毒", "贩毒", "场所", "举报"],
        [("线索来源核实", "核实举报来源、违法活动时间、地点、人员数量和特征。"), ("现场风险判断", "判断是否仍在进行、是否存在逃跑、毁证或人身风险。")],
        ["报警人", "证人", "相关人员"],
        "intake",
        "中等",
        "举报信息可能片段化，需要快速区分事实、猜测和可验证线索。",
    ),
    _module(
        "public_order_scene_control",
        "涉案场所控制检查",
        ["黄赌毒与场所治安线索"],
        ["现场", "赌资", "毒品", "房间", "人员", "通讯工具", "交易", "逃跑", "毁证"],
        [("人员控制与告知", "控制现场人员出入，表明身份和检查事由。"), ("物证电子证据固定", "固定赌资、毒品、通讯工具、房间记录或交易线索。")],
        ["嫌疑人", "证人", "相关人员"],
        "onsite",
        "高",
        "现场人员可能否认、串供或毁证，需要先控制现场再分类询问。",
    ),
    _module(
        "campus_minor_protection",
        "校园未成年人警情处置",
        ["校园与未成年人警情", "纠纷求助与现场稳控"],
        ["校园", "学生", "未成年", "老师", "家长", "欺凌", "宿舍", "校门"],
        [("未成年人保护", "核实伤情、身份、监护人和学校责任人，避免公开刺激和二次伤害。"), ("学校家长联动", "明确学校、家长、医疗或后续调查衔接。")],
        ["报警人", "被害人", "证人", "老师", "家属", "相关人员"],
        "onsite",
        "中等",
        "现场可能有学生围观或家长情绪激动，需要兼顾保护、稳控和事实核实。",
    ),
    _module(
        "robbery_threat_report",
        "侵财侵害警情追查",
        ["高风险侵害和人身财产案件"],
        ["抢劫", "抢夺", "威胁", "恐吓", "敲诈", "入室", "持刀", "逃离"],
        [("人身风险核查", "核实嫌疑人去向、是否持械、受害人伤情和继续侵害风险。"), ("追查线索固定", "核实嫌疑人体貌、逃离方向、交通工具、财物特征和监控位置。")],
        ["报警人", "被害人", "证人", "相关人员"],
        "intake",
        "高",
        "受害人可能惊恐，现场风险和嫌疑人去向比一般侵财警情更紧迫。",
    ),
    _module(
        "platform_trade_boundary",
        "平台交易纠纷性质核查",
        ["网络与平台交易纠纷", "电信网络诈骗与预警劝阻"],
        ["网购", "退款", "二手", "租房", "游戏账号", "平台", "客服", "定金", "押金"],
        [("交易链路核实", "核实交易平台、聊天记录、付款路径、收货或服务履行情况。"), ("诈骗边界识别", "区分普通消费纠纷、合同争议和可能诈骗线索。")],
        ["报警人", "被害人", "相关人员"],
        "investigation",
        "中等",
        "当事人可能把民事纠纷和诈骗混在一起，需要先固定交易链路再判断处置路径。",
    ),
]


CASE_TYPE_TO_FAMILIES: dict[str, list[str]] = {
    "邻里纠纷": ["纠纷求助与现场稳控"],
    "家庭纠纷": ["纠纷求助与现场稳控"],
    "情感纠纷": ["纠纷求助与现场稳控"],
    "劳资纠纷": ["纠纷求助与现场稳控"],
    "消费纠纷": ["纠纷求助与现场稳控", "网络与平台交易纠纷"],
    "噪音扰民": ["纠纷求助与现场稳控"],
    "宠物纠纷": ["纠纷求助与现场稳控"],
    "打架斗殴": ["打架斗殴与故意伤害", "纠纷求助与现场稳控"],
    "故意伤害": ["打架斗殴与故意伤害"],
    "寻衅滋事": ["打架斗殴与故意伤害"],
    "盗窃": ["盗窃等侵财警情"],
    "入室盗窃": ["盗窃等侵财警情"],
    "抢劫": ["高风险侵害和人身财产案件"],
    "抢夺": ["高风险侵害和人身财产案件", "盗窃等侵财警情"],
    "敲诈勒索": ["高风险侵害和人身财产案件"],
    "非法侵入住宅": ["高风险侵害和人身财产案件", "纠纷求助与现场稳控"],
    "电信网络诈骗": ["电信网络诈骗与预警劝阻"],
    "诈骗": ["电信网络诈骗与预警劝阻", "网络与平台交易纠纷"],
    "交通事故": ["交通警情与酒驾醉驾"],
    "酒驾醉驾": ["交通警情与酒驾醉驾"],
    "肇事逃逸": ["交通警情与酒驾醉驾"],
    "赌博": ["黄赌毒与场所治安线索"],
    "卖淫嫖娼": ["黄赌毒与场所治安线索"],
    "涉毒": ["黄赌毒与场所治安线索"],
    "失踪求助": ["走失、自伤和救助类警情"],
    "自杀干预": ["走失、自伤和救助类警情"],
    "校园警情": ["校园与未成年人警情"],
}


def _case_text(case_info: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "case_name",
        "case_type",
        "case_background",
        "background",
        "full_narrative",
        "criminal_process",
        "transcript_summary",
        "original_content",
    ):
        value = case_info.get(key)
        if value:
            values.append(str(value))
    for key in ("key_facts", "conflict_points", "hidden_info", "evidence_points", "inconsistencies"):
        value = case_info.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item)
    return "\n".join(values)


def families_for_case_type(case_type: str) -> list[str]:
    clean = str(case_type or "").strip()
    return CASE_TYPE_TO_FAMILIES.get(clean, [])


def score_scene_module(case_info: dict[str, Any], module: dict[str, Any]) -> int:
    text = _case_text(case_info)
    case_type = str(case_info.get("case_type") or "").strip()
    families = set(families_for_case_type(case_type))
    score = 0
    if families & set(module.get("case_families") or []):
        score += 8
    for trigger in module.get("triggers") or []:
        if trigger and re.search(re.escape(str(trigger)), text, flags=re.IGNORECASE):
            score += 3
    kind = str(module.get("scene_kind_hint") or "")
    if kind == "intake" and any(token in text for token in ("报警", "来电", "求助", "举报")):
        score += 1
    if kind == "onsite" and any(token in text for token in ("现场", "到场", "监控", "伤情", "痕迹")):
        score += 1
    if kind == "investigation" and any(token in text for token in ("询问", "否认", "矛盾", "时间线", "嫌疑")):
        score += 1
    return score


def select_scene_modules(case_info: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    scored = [
        (score_scene_module(case_info, module), index, module)
        for index, module in enumerate(SCENE_MODULES)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [dict(module) for score, _, module in scored if score > 0][:limit]
    if selected:
        return selected

    default_families = {"纠纷求助与现场稳控", "盗窃等侵财警情", "电信网络诈骗与预警劝阻", "交通警情与酒驾醉驾"}
    return [
        dict(module)
        for module in SCENE_MODULES
        if set(module.get("case_families") or []) & default_families
    ][:limit]


def build_scene_module_prompt(case_info: dict[str, Any]) -> str:
    modules = select_scene_modules(case_info, limit=10)
    compact = [
        {
            "module_id": item["module_id"],
            "title": item["title"],
            "scene_kind_hint": item["scene_kind_hint"],
            "difficulty": item["difficulty"],
            "stage_examples": item["stage_examples"],
            "role_types": item["role_types"],
        }
        for item in modules
    ]
    return (
        "下面是根据案件类型和案情关键词选出的候选训练模块。它们不是场景模板，不能逐条照搬；"
        "你必须根据案件事实自动组合、改名、删减或合并，生成 2-4 个真正适配本案的场景。"
        "若某模块缺少事实支撑，必须舍弃。\n"
        f"{compact}"
    )


def build_case_frequency_prompt() -> str:
    rows = [
        f"{item['rank']}. {item['case_family']}：常见案由 {', '.join(item['common_cases'])}；训练重点 {item['scene_focus']}"
        for item in OFFICIAL_CASE_FREQUENCY_REFERENCE
    ]
    return "\n".join(rows)
