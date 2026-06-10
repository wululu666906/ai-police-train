import json
from datetime import datetime, timedelta

import models
from database import SessionLocal, engine
from routers.auth import hash_password
from services.training_runtime_service import dump_runtime_state


DEMO_MARKER = "realistic_demo_seed_20260606"
PASSWORD = "123456"


def to_json(value):
    return json.dumps(value, ensure_ascii=False)


def ensure_user(db, username, role="student"):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        user.role = role
        return user

    user = models.User(
        username=username,
        hashed_password=hash_password(PASSWORD),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def ensure_case(db, data):
    case_obj = db.query(models.Case).filter(models.Case.title == data["title"]).first()
    if not case_obj:
        case_obj = models.Case(title=data["title"])
        db.add(case_obj)
        db.flush()

    case_obj.case_type = data["case_type"]
    case_obj.background = data["background"]
    case_obj.original_content = data["original_content"]
    case_obj.structured_data = to_json(data["structured_data"])
    return case_obj


def ensure_scene(db, case_obj, scene_data):
    scene = (
        db.query(models.Scene)
        .filter(models.Scene.case_id == case_obj.id, models.Scene.name == scene_data["name"])
        .first()
    )
    if not scene:
        scene = models.Scene(case_id=case_obj.id, name=scene_data["name"])
        db.add(scene)
        db.flush()

    scene.description = scene_data["description"]
    scene.difficulty = scene_data["difficulty"]
    scene.dispatch_brief = scene_data["dispatch_brief"]
    scene.first_impression = scene_data["first_impression"]
    scene.stages = to_json(scene_data["stages"])
    return scene


def ensure_role(db, case_obj, scene, role_data):
    role = (
        db.query(models.Role)
        .filter(
            models.Role.case_id == case_obj.id,
            models.Role.scene_id == scene.id,
            models.Role.name == role_data["name"],
        )
        .first()
    )
    if not role:
        role = models.Role(case_id=case_obj.id, scene_id=scene.id, name=role_data["name"])
        db.add(role)
        db.flush()

    role.role_type = role_data["role_type"]
    role.interaction_style = role_data["interaction_style"]
    role.personality = role_data["personality"]
    role.speaking_style = role_data["speaking_style"]
    role.init_emotion = role_data["init_emotion"]
    role.init_trust = role_data["init_trust"]
    role.status = role_data["status"]
    role.iq_level = role_data["iq_level"]
    role.eq_level = role_data["eq_level"]
    role.lying_ability = role_data["lying_ability"]
    role.weakness = role_data["weakness"]
    role.knows_facts = to_json(role_data["knows_facts"])
    role.does_not_know = to_json(role_data["does_not_know"])
    role.hidden_truths = to_json(role_data["hidden_truths"])
    role.persona_meta = to_json(role_data["persona_meta"])

    link = (
        db.query(models.SceneRole)
        .filter(models.SceneRole.scene_id == scene.id, models.SceneRole.role_id == role.id)
        .first()
    )
    if not link:
        db.add(models.SceneRole(scene_id=scene.id, role_id=role.id, is_primary=role_data.get("is_primary", False)))
    else:
        link.is_primary = role_data.get("is_primary", False)

    return role


def make_runtime_state(revealed, cooperation, risk, clarity):
    return dump_runtime_state(
        {
            "revealed_info": revealed,
            "assessment_progress": {
                "points": [],
                "actions": [],
                "summary": {
                    "requirements": [],
                    "satisfied": [],
                    "missing": [],
                    "completed_point_ids": [],
                    "completed_action_ids": [],
                    "total_weight": 0,
                    "earned_weight": 0,
                },
            },
            "completed_point_ids": [],
            "completed_action_ids": [],
            "auto_finish_ready": True,
            "closure_summary": {},
            "state_snapshot": {"cooperation": cooperation, "risk": risk, "clarity": clarity},
            "role_state_snapshots": {},
            "last_active_role_ids": [],
            "last_target_role_name": "",
        }
    )


def make_evaluation(score, missing, strengths, improvements):
    dimensions = [
        ("执法语言规范性", min(25, max(10, round(score * 0.26))), 25),
        ("事实查明完整性", min(30, max(12, round(score * 0.31))), 30),
        ("现场安全与程序意识", min(25, max(10, round(score * 0.25))), 25),
        ("沟通安抚与风险控制", min(20, max(8, score - min(25, max(10, round(score * 0.26))) - min(30, max(12, round(score * 0.31))) - min(25, max(10, round(score * 0.25))))), 20),
    ]
    return to_json(
        {
            "demo_seed": True,
            "seed_marker": DEMO_MARKER,
            "scores": [
                {
                    "dimension": name,
                    "score": item_score,
                    "full_score": full_score,
                    "reason": f"{name}表现{'较好' if score >= 80 else '基本达标' if score >= 70 else '仍需强化'}。",
                }
                for name, item_score, full_score in dimensions
            ],
            "total_score": score,
            "assessment_check_results": [
                {"name": "身份核验", "passed": score >= 60},
                {"name": "关键信息追问", "passed": score >= 75},
                {"name": "证据固定", "passed": score >= 80},
            ],
            "strengths": strengths,
            "improvements": improvements,
            "suggestions": "继续按照接警、稳控、核验、取证、告知的顺序推进，注意把口头信息转化为可核查证据。",
            "evaluation_meta": {
                "stage_gap_summary": {
                    "scene_type": "综合警情处置",
                    "missing": missing,
                }
            },
        }
    )


def add_session(db, user, scene, messages, created_at, status, score=None, revealed=None, cooperation=65, risk=45, clarity=70):
    session = models.TrainingSession(
        user_id=user.id,
        scene_id=scene.id,
        current_stage="总结反馈" if status == "finished" else "调查核实",
        current_emotion=max(20, min(90, 100 - risk)),
        current_trust=cooperation,
        revealed_info=make_runtime_state(revealed or [], cooperation, risk, clarity),
        evaluation_result=make_evaluation(
            score,
            missing=["未完整记录证人联系方式"] if score and score >= 80 else ["现场证据固定不充分", "告知权利义务不够完整"],
            strengths=["沟通语气稳定", "能围绕关键事实追问"] if score and score >= 75 else ["能完成基本询问流程"],
            improvements=["补强证据清单", "结束前复述并确认关键事实"] if score and score >= 75 else ["先控制现场风险", "按时间线梳理事实", "及时固定客观证据"],
        )
        if score is not None
        else None,
        status=status,
        created_at=created_at,
    )
    db.add(session)
    db.flush()

    for offset, msg in enumerate(messages):
        db.add(
            models.Message(
                session_id=session.id,
                role=msg["role"],
                content=msg["content"],
                speaker_name=msg.get("speaker_name"),
                inner_thought=msg.get("inner_thought"),
                created_at=created_at + timedelta(minutes=offset * 2),
            )
        )
    return session


CASE_DATA = [
    {
        "title": "刘军酒后殴打赵阳案",
        "case_type": "治安纠纷",
        "background": "烧烤店门口因结账插队发生口角，刘军饮酒后推搡并击打赵阳面部，现场有群众围观，双方情绪激动。",
        "original_content": "2026年5月28日21时42分，接群众报警称建设路夜市有人打架。民警到场发现赵阳左侧眉弓红肿，刘军身上有明显酒味。",
        "structured_data": {
            "persons": [
                {"name": "刘军", "role": "违法嫌疑人", "role_type": "违法嫌疑人"},
                {"name": "赵阳", "role": "被害人", "role_type": "被害人"},
                {"name": "孙桂兰", "role": "证人", "role_type": "证人"},
            ],
            "timeline": ["21:35 双方在收银台发生争执", "21:40 刘军击打赵阳面部", "21:42 群众报警"],
            "evidence_points": ["店内监控", "赵阳伤情照片", "孙桂兰证言", "付款记录"],
        },
        "scenes": [
            {
                "name": "现场接警与初步处置",
                "description": "到达夜市现场，分离当事人、控制围观秩序、核实伤情并寻找证人。",
                "difficulty": "低",
                "dispatch_brief": "建设路夜市烧烤店门口有人打架，现场人员较多，请立即处置。",
                "first_impression": "赵阳捂着眉弓站在店门口，刘军坐在路边椅子上，语速快且带酒气。",
                "stages": [
                    {"name": "稳控现场", "goal": "分离双方，确认是否有继续冲突风险"},
                    {"name": "核实伤情", "goal": "询问伤情、建议就医并拍照固定"},
                    {"name": "寻找证据", "goal": "确认监控位置和目击证人"},
                ],
                "roles": [
                    {
                        "name": "赵阳",
                        "role_type": "被害人",
                        "interaction_style": "急躁但配合",
                        "personality": "觉得自己无故被打，要求民警马上处理。",
                        "speaking_style": "语速较快，反复强调自己没有先动手。",
                        "init_emotion": 72,
                        "init_trust": 48,
                        "status": "眉弓红肿",
                        "iq_level": "中等",
                        "eq_level": "中等",
                        "lying_ability": "一般",
                        "weakness": "情绪上来时会省略自己推搡对方的细节。",
                        "knows_facts": ["刘军先挥拳", "店里有监控", "自己曾推开刘军"],
                        "does_not_know": ["刘军饮酒量", "围观者姓名"],
                        "hidden_truths": ["曾先用手推了刘军肩膀"],
                        "persona_meta": {"age": 32, "occupation": "外卖站点主管"},
                        "is_primary": True,
                    },
                    {
                        "name": "刘军",
                        "role_type": "违法嫌疑人",
                        "interaction_style": "防御抵触",
                        "personality": "酒后冲动，担心被拘留，起初否认先动手。",
                        "speaking_style": "含糊、辩解多，遇到证据后会软化。",
                        "init_emotion": 78,
                        "init_trust": 28,
                        "status": "饮酒后情绪不稳",
                        "iq_level": "中等",
                        "eq_level": "较低",
                        "lying_ability": "一般",
                        "weakness": "看到监控或证人一致陈述后容易承认。",
                        "knows_facts": ["自己喝了三瓶啤酒", "确实挥了一拳", "赵阳先推过自己"],
                        "does_not_know": ["赵阳具体伤情", "证人是否拍视频"],
                        "hidden_truths": ["挥拳后还骂了对方并想继续上前"],
                        "persona_meta": {"age": 41, "occupation": "货车司机"},
                    },
                ],
            }
        ],
    },
    {
        "title": "张伟醉酒驾驶交通事故案",
        "case_type": "交通事故",
        "background": "小客车夜间追尾电动自行车，骑行人腿部受伤。驾驶人张伟承认饮酒但试图淡化饮酒量。",
        "original_content": "2026年5月31日22时18分，人民路与新华街交叉口发生交通事故。现场酒精检测初筛显示驾驶人涉嫌酒后驾驶。",
        "structured_data": {
            "persons": [
                {"name": "张伟", "role": "嫌疑人", "role_type": "嫌疑人"},
                {"name": "李娜", "role": "伤者", "role_type": "伤者"},
                {"name": "王师傅", "role": "目击证人", "role_type": "目击证人"},
            ],
            "timeline": ["20:10 张伟在饭店聚餐饮酒", "22:12 车辆追尾电动自行车", "22:18 路人报警"],
            "evidence_points": ["呼气酒精检测", "行车记录仪", "路口监控", "医院诊断证明"],
        },
        "scenes": [
            {
                "name": "事故现场控制与伤情核实",
                "description": "夜间路口事故现场，需摆放警示、救助伤者、控制驾驶人并固定证据。",
                "difficulty": "中等",
                "dispatch_brief": "人民路口小客车与电动自行车事故，有人员受伤，驾驶人疑似饮酒。",
                "first_impression": "电动自行车倒在斑马线旁，李娜坐在路边，张伟不断打电话解释。",
                "stages": [
                    {"name": "安全防护", "goal": "设置警戒，避免二次事故"},
                    {"name": "救助伤者", "goal": "核实伤情并联系急救"},
                    {"name": "酒驾证据", "goal": "依法检测并固定车辆、监控、证人"},
                ],
                "roles": [
                    {
                        "name": "张伟",
                        "role_type": "嫌疑人",
                        "interaction_style": "回避拖延",
                        "personality": "担心酒驾后果，强调自己车速不快。",
                        "speaking_style": "反复说“我就喝了一点”，会要求先打电话。",
                        "init_emotion": 66,
                        "init_trust": 24,
                        "status": "呼气有酒味",
                        "iq_level": "中等",
                        "eq_level": "中等",
                        "lying_ability": "较强",
                        "weakness": "无法解释饭店小票和同行人陈述。",
                        "knows_facts": ["聚餐喝了白酒和啤酒", "撞车前低头看导航", "车上有行车记录仪"],
                        "does_not_know": ["伤者骨折情况", "路口监控是否清楚"],
                        "hidden_truths": ["实际喝了约三两白酒"],
                        "persona_meta": {"age": 37, "occupation": "销售经理"},
                        "is_primary": True,
                    },
                    {
                        "name": "李娜",
                        "role_type": "伤者",
                        "interaction_style": "紧张配合",
                        "personality": "腿部疼痛，担心医疗费用。",
                        "speaking_style": "说话断续，需要安抚后才能完整回忆。",
                        "init_emotion": 84,
                        "init_trust": 55,
                        "status": "右腿疼痛",
                        "iq_level": "中等",
                        "eq_level": "中等",
                        "lying_ability": "弱",
                        "weakness": "疼痛导致时间记忆不精确。",
                        "knows_facts": ["自己正常过路口", "车从后方撞上", "驾驶人身上有酒味"],
                        "does_not_know": ["车速", "驾驶人饮酒地点"],
                        "hidden_truths": [],
                        "persona_meta": {"age": 29, "occupation": "护士"},
                    },
                ],
            }
        ],
    },
    {
        "title": "王丽电信诈骗报案核查案",
        "case_type": "电信诈骗",
        "background": "王丽接到冒充客服来电后转账，发现被骗到派出所报案，需快速核实账户、固定聊天和转账证据。",
        "original_content": "2026年6月2日16时05分，王丽报警称被冒充电商客服诈骗39800元，对方要求其删除聊天记录并继续贷款转账。",
        "structured_data": {
            "persons": [
                {"name": "王丽", "role": "报案人", "role_type": "报案人"},
                {"name": "银行客服", "role": "相关人员", "role_type": "相关人员"},
                {"name": "陈警官", "role": "协作角色", "role_type": "协作角色"},
            ],
            "timeline": ["14:20 接到陌生客服电话", "15:05 首笔转账19800元", "15:47 第二笔转账20000元", "16:05 到所报案"],
            "evidence_points": ["转账凭证", "通话记录", "聊天截图", "涉诈账户"],
        },
        "scenes": [
            {
                "name": "接警信息核实",
                "description": "报案人情绪焦急，需迅速厘清被骗过程、金额、账户和仍在发生的风险。",
                "difficulty": "低",
                "dispatch_brief": "群众到所报称遭遇冒充客服诈骗，已转账两笔，对方仍在联系。",
                "first_impression": "王丽拿着手机在接警台前哭泣，屏幕上仍有陌生号码来电。",
                "stages": [
                    {"name": "安抚止损", "goal": "制止继续转账，提示保留证据"},
                    {"name": "核实要素", "goal": "记录金额、账户、时间、沟通渠道"},
                    {"name": "联动处置", "goal": "提示紧急止付和反诈协作"},
                ],
                "roles": [
                    {
                        "name": "王丽",
                        "role_type": "报案人",
                        "interaction_style": "焦虑配合",
                        "personality": "非常自责，害怕家人知道，容易被再次诱导。",
                        "speaking_style": "语速快，夹杂哭腔，细节需要引导。",
                        "init_emotion": 88,
                        "init_trust": 62,
                        "status": "情绪焦急",
                        "iq_level": "中等",
                        "eq_level": "中等",
                        "lying_ability": "弱",
                        "weakness": "羞于承认贷款转账细节。",
                        "knows_facts": ["两次转账合计39800元", "对方冒充电商客服", "手机里有聊天截图"],
                        "does_not_know": ["涉诈账户真实开户人", "资金是否已被转走"],
                        "hidden_truths": ["还准备按对方要求继续贷款转账"],
                        "persona_meta": {"age": 34, "occupation": "小学教师"},
                        "is_primary": True,
                    }
                ],
            }
        ],
    },
]


SCENE_BLUEPRINTS = [
    ("接警与风险初筛", "低", "确认报警人身份、案发时间地点、现场风险和紧急需求。"),
    ("现场核查与证据固定", "中等", "到达现场后核实人员关系、固定客观证据并同步安抚当事人。"),
    ("矛盾升级与闭环处置", "高", "面对多人陈述冲突、拒不配合或次生风险，完成依法处置和移交闭环。"),
]


ADDITIONAL_CASE_BLUEPRINTS = [
    {
        "title": "李娜早餐店消费纠纷案",
        "case_type": "治安纠纷",
        "background": "早餐店顾客因扫码付款失败与店主发生争执，双方互相指责辱骂并引发围观。",
        "persons": [("李娜", "报警人", "急躁配合"), ("周强", "店主", "防御抵触"), ("陈梅", "证人", "谨慎配合")],
        "evidence": ["付款记录", "店内监控", "围观群众视频", "收银小票"],
        "risk": "围观群众较多，双方有继续争吵风险。",
    },
    {
        "title": "赵磊出租屋噪音扰民案",
        "case_type": "邻里纠纷",
        "background": "楼上租户深夜聚会产生噪音，楼下住户多次沟通未果后报警。",
        "persons": [("赵磊", "报警人", "疲惫不满"), ("韩宇", "被投诉人", "不耐烦"), ("物业王姐", "协助人员", "配合型")],
        "evidence": ["报警记录", "物业沟通记录", "噪音视频", "租赁合同"],
        "risk": "双方长期积怨，容易从噪音问题扩大为肢体冲突。",
    },
    {
        "title": "孙伟便利店盗窃案",
        "case_type": "盗窃",
        "background": "便利店发现货架香烟和充电宝缺失，店员怀疑常客孙伟趁人多时拿走商品。",
        "persons": [("孙伟", "嫌疑人", "回避拖延"), ("刘萍", "店员", "坚定配合"), ("马强", "目击证人", "谨慎配合")],
        "evidence": ["店内监控", "库存记录", "收银台录像", "商品条码"],
        "risk": "嫌疑人否认盗窃并试图离开现场。",
    },
    {
        "title": "陈浩网约车遗失手机案",
        "case_type": "求助服务",
        "background": "乘客称手机遗落在网约车后无法联系司机，担心个人资料泄露。",
        "persons": [("陈浩", "求助人", "焦虑配合"), ("司机何师傅", "相关人员", "谨慎解释"), ("平台客服", "协助人员", "程序化配合")],
        "evidence": ["乘车订单", "通话记录", "车辆轨迹", "平台工单"],
        "risk": "求助人情绪激动，可能自行发布司机个人信息。",
    },
    {
        "title": "何敏校园门口走失儿童案",
        "case_type": "群众求助",
        "background": "家长接孩子时发现孩子未在校门口出现，现场人员密集且家长情绪焦急。",
        "persons": [("何敏", "报警人", "极度焦虑"), ("门卫老张", "证人", "配合型"), ("班主任林老师", "协助人员", "紧张配合")],
        "evidence": ["校门监控", "班级签到表", "家长群消息", "儿童照片"],
        "risk": "人员密集、时间紧迫，需要迅速组织查找和广播协作。",
    },
    {
        "title": "马俊停车场剐蹭纠纷案",
        "case_type": "交通事故",
        "background": "商场停车场两车低速剐蹭，双方对责任认定和赔偿金额争执不下。",
        "persons": [("马俊", "驾驶人", "强硬不满"), ("唐静", "驾驶人", "委屈配合"), ("保安小刘", "证人", "配合型")],
        "evidence": ["停车场监控", "行车记录仪", "车辆受损照片", "保险报案记录"],
        "risk": "双方堵在通道口，影响车辆通行并引发围观。",
    },
    {
        "title": "郑凯酒吧口角推搡案",
        "case_type": "治安纠纷",
        "background": "酒吧散场时两桌客人因碰撞发生口角，其中一人被推倒擦伤。",
        "persons": [("郑凯", "违法嫌疑人", "酒后防御"), ("罗敏", "被害人", "愤怒配合"), ("酒吧经理", "证人", "谨慎配合")],
        "evidence": ["酒吧监控", "消费记录", "伤情照片", "现场视频"],
        "risk": "酒后人员聚集，同行朋友可能继续挑衅。",
    },
    {
        "title": "周婷刷单返利诈骗案",
        "case_type": "电信诈骗",
        "background": "周婷参与网络刷单返利，连续充值后无法提现，诈骗人员仍诱导其继续转账。",
        "persons": [("周婷", "报案人", "焦虑自责"), ("反诈专员", "协助人员", "专业配合"), ("银行柜员", "证人", "谨慎配合")],
        "evidence": ["转账凭证", "聊天截图", "刷单链接", "涉诈账户"],
        "risk": "报案人仍在被远程诱导，有继续转账风险。",
    },
    {
        "title": "吴杰工地工资纠纷案",
        "case_type": "劳资纠纷",
        "background": "工人反映包工头拖欠工资，十余人在项目部门口聚集要求说法。",
        "persons": [("吴杰", "报警人", "激动但讲理"), ("包工头梁某", "相关人员", "回避拖延"), ("项目经理", "协助人员", "谨慎配合")],
        "evidence": ["工资表", "考勤记录", "施工合同", "转账流水"],
        "risk": "聚集人数较多，言语冲突可能升级。",
    },
    {
        "title": "林峰快递损毁赔偿案",
        "case_type": "消费纠纷",
        "background": "市民称贵重模型快递损坏，快递员和网点均称包装不合格，双方争执报警。",
        "persons": [("林峰", "报警人", "较为激动"), ("快递员小许", "相关人员", "防御解释"), ("网点负责人", "协助人员", "理性配合")],
        "evidence": ["快递面单", "开箱视频", "破损照片", "赔付规则"],
        "risk": "报警人情绪激动，要求现场扣留快递员。",
    },
    {
        "title": "高磊小区犬只伤人案",
        "case_type": "治安纠纷",
        "background": "小区内未牵绳犬只扑倒老人，犬主与老人家属因赔偿和责任产生争执。",
        "persons": [("高磊", "犬主", "辩解防御"), ("老人家属", "被害人家属", "愤怒焦急"), ("物业主管", "证人", "配合型")],
        "evidence": ["小区监控", "就医记录", "犬只免疫证明", "物业巡查记录"],
        "risk": "老人受伤，家属情绪高，周边业主围观议论。",
    },
    {
        "title": "宋倩直播购物退款案",
        "case_type": "电商纠纷",
        "background": "消费者直播间购买护肤品后怀疑假货，联系商家未果到派出所求助。",
        "persons": [("宋倩", "求助人", "焦虑配合"), ("商家客服", "相关人员", "敷衍回避"), ("平台专员", "协助人员", "程序化配合")],
        "evidence": ["订单截图", "商品照片", "聊天记录", "平台投诉单"],
        "risk": "求助人准备在网上公开个人争议内容，可能引发舆情。",
    },
    {
        "title": "钱斌棋牌室赌博线索核查案",
        "case_type": "治安案件",
        "background": "群众举报棋牌室夜间有人聚众赌博，现场需核查经营情况和人员身份。",
        "persons": [("钱斌", "经营者", "谨慎回避"), ("举报群众", "报警人", "担心报复"), ("现场顾客", "相关人员", "不愿配合")],
        "evidence": ["现场照片", "收付款记录", "人员身份信息", "监控录像"],
        "risk": "现场人员多且态度复杂，存在转移赌资或串供风险。",
    },
    {
        "title": "胡晨医院医患冲突案",
        "case_type": "公共秩序",
        "background": "患者家属因等待时间过长与护士发生争吵，并堵在分诊台影响就诊秩序。",
        "persons": [("胡晨", "患者家属", "急躁强硬"), ("护士张某", "被害人", "委屈配合"), ("保安队长", "协助人员", "配合型")],
        "evidence": ["医院监控", "分诊记录", "排队叫号信息", "现场视频"],
        "risk": "医院公共场所人员密集，冲突影响正常诊疗。",
    },
    {
        "title": "彭宇夜间可疑人员盘查案",
        "case_type": "巡逻盘查",
        "background": "夜间巡逻发现男子在多辆汽车旁徘徊并试拉车门，需依法盘查身份和目的。",
        "persons": [("彭宇", "被盘查人", "紧张回避"), ("车主代表", "报警人", "担心损失"), ("巡逻辅警", "协助人员", "配合型")],
        "evidence": ["巡逻记录", "小区监控", "车辆报警记录", "随身物品检查记录"],
        "risk": "被盘查人解释前后不一，可能携带工具或准备逃离。",
    },
]


def build_stage_set(case_type, scene_name):
    return [
        {"name": "身份与安全确认", "goal": f"确认{scene_name}相关人员身份，排除即时危险。"},
        {"name": "事实要素核实", "goal": f"围绕{case_type}的时间、地点、人物、经过逐项询问。"},
        {"name": "证据固定与告知", "goal": "固定客观证据，告知后续处理方式和权利义务。"},
    ]


def build_role(role_name, role_type, style, evidence, index, is_primary=False):
    hidden = [f"{role_name}起初没有主动说明对自己不利的细节"] if index == 0 else []
    return {
        "name": role_name,
        "role_type": role_type,
        "interaction_style": style,
        "personality": f"{role_name}在现场表现为{style}，需要学员通过具体问题逐步稳定沟通。",
        "speaking_style": "先表达情绪，再在追问下补充关键事实。",
        "init_emotion": 72 - min(index * 8, 18),
        "init_trust": 34 + min(index * 10, 24),
        "status": "等待询问",
        "iq_level": "中等",
        "eq_level": "中等",
        "lying_ability": "较强" if "嫌疑" in role_type or "经营者" in role_type or "被盘查" in role_type else "一般",
        "weakness": f"被问到{evidence[0]}和{evidence[1]}时，陈述会更具体。",
        "knows_facts": [f"知道案件核心经过的一部分", f"知道{evidence[0]}可核查", f"能说明与{evidence[1]}有关的情况"],
        "does_not_know": [f"不清楚{evidence[-1]}的完整内容"],
        "hidden_truths": hidden,
        "persona_meta": {"source": "demo_realistic_case", "profile": style},
        "is_primary": is_primary,
    }


def build_additional_case(data):
    scenes = []
    for scene_name, difficulty, focus in SCENE_BLUEPRINTS:
        scene_roles = [
            build_role(name, role_type, style, data["evidence"], index, is_primary=index == 0)
            for index, (name, role_type, style) in enumerate(data["persons"])
        ]
        scenes.append(
            {
                "name": scene_name,
                "description": f"{focus}案件背景：{data['background']}",
                "difficulty": difficulty,
                "dispatch_brief": f"{data['case_type']}警情：{data['background']}请到场核实并规范处置。",
                "first_impression": f"现场初见：{data['risk']}主要人员等待询问，情绪和配合度不一。",
                "stages": build_stage_set(data["case_type"], scene_name),
                "roles": scene_roles,
            }
        )

    return {
        "title": data["title"],
        "case_type": data["case_type"],
        "background": data["background"],
        "original_content": f"接处警记录：{data['background']} 风险提示：{data['risk']}",
        "structured_data": {
            "persons": [
                {"name": name, "role": role_type, "role_type": role_type}
                for name, role_type, _style in data["persons"]
            ],
            "timeline": ["报警受理", "到场核查", "询问相关人员", "证据固定", "依法处置"],
            "evidence_points": data["evidence"],
            "risk_points": [data["risk"]],
        },
        "scenes": scenes,
    }


CASE_DATA.extend(build_additional_case(item) for item in ADDITIONAL_CASE_BLUEPRINTS)


SESSION_TEMPLATES = [
    {
        "username": "student001",
        "case_title": "王丽电信诈骗报案核查案",
        "scene_name": "接警信息核实",
        "days_ago": 0,
        "status": "active",
        "score": None,
        "cooperation": 74,
        "risk": 58,
        "clarity": 63,
        "revealed": ["报案人已转账39800元", "对方仍在通过电话施压"],
        "messages": [
            {"role": "user", "content": "先不要接陌生电话，把手机放在桌上。你现在已经转了几笔、分别多少钱？"},
            {"role": "assistant", "speaker_name": "王丽", "content": "两笔，一笔19800，一笔20000。他们说不继续操作会影响征信。"},
            {"role": "user", "content": "你做得对，先来报案就能止损。把转账凭证和聊天截图都保留，不要删除。"},
            {"role": "assistant", "speaker_name": "王丽", "content": "我有截图，也有银行短信。他刚才还让我去贷款平台借一笔。"},
        ],
    },
    {
        "username": "student001",
        "case_title": "刘军酒后殴打赵阳案",
        "scene_name": "现场接警与初步处置",
        "days_ago": 1,
        "status": "finished",
        "score": 86,
        "cooperation": 82,
        "risk": 31,
        "clarity": 86,
        "revealed": ["赵阳承认曾推开刘军", "店内监控可覆盖收银台", "刘军承认挥拳"],
        "messages": [
            {"role": "user", "content": "双方先分开站，谁受伤先说明伤在哪里。赵阳，你现在眉弓疼痛吗？"},
            {"role": "assistant", "speaker_name": "赵阳", "content": "疼，他上来就打我，我没有先打他。"},
            {"role": "user", "content": "你说没有先打，我确认一下：有没有推开、拉扯或者用手挡过他？"},
            {"role": "assistant", "speaker_name": "赵阳", "content": "我推了他一下，是他一直骂我还往前冲。"},
            {"role": "user", "content": "现场有没有监控？旁边这位阿姨是否看到完整过程？"},
            {"role": "assistant", "speaker_name": "刘军", "content": "监控应该有。我也不是故意的，喝多了，他先推我我才动手。"},
        ],
    },
    {
        "username": "student001",
        "case_title": "张伟醉酒驾驶交通事故案",
        "scene_name": "事故现场控制与伤情核实",
        "days_ago": 3,
        "status": "finished",
        "score": 72,
        "cooperation": 61,
        "risk": 44,
        "clarity": 70,
        "revealed": ["驾驶人承认聚餐饮酒", "伤者右腿疼痛", "车辆有行车记录仪"],
        "messages": [
            {"role": "user", "content": "先把车钥匙交给我，现场要做安全防护。你是否饮酒？"},
            {"role": "assistant", "speaker_name": "张伟", "content": "喝了一点啤酒，真不多，我车速也不快。"},
            {"role": "user", "content": "饮酒情况稍后依法检测。李娜，你腿部哪里疼，是否需要120？"},
            {"role": "assistant", "speaker_name": "李娜", "content": "右腿很疼，我站不起来，他撞上来的时候我已经过了路口。"},
            {"role": "user", "content": "我会联系急救，同时调取路口监控和你的行车记录仪。"},
        ],
    },
    {
        "username": "student001",
        "case_title": "刘军酒后殴打赵阳案",
        "scene_name": "现场接警与初步处置",
        "days_ago": 7,
        "status": "finished",
        "score": 58,
        "cooperation": 43,
        "risk": 67,
        "clarity": 52,
        "revealed": ["赵阳受伤", "刘军饮酒"],
        "messages": [
            {"role": "user", "content": "你们两个谁先动手？"},
            {"role": "assistant", "speaker_name": "刘军", "content": "他先推我，我才还手。"},
            {"role": "user", "content": "那你们自己协商一下，别再吵了。"},
            {"role": "assistant", "speaker_name": "赵阳", "content": "他打我你让我协商？我要验伤。"},
        ],
    },
    {
        "username": "student002",
        "case_title": "王丽电信诈骗报案核查案",
        "scene_name": "接警信息核实",
        "days_ago": 2,
        "status": "finished",
        "score": 91,
        "cooperation": 88,
        "risk": 22,
        "clarity": 90,
        "revealed": ["涉诈账号已记录", "通话录音和聊天截图已固定", "已提示紧急止付"],
        "messages": [
            {"role": "user", "content": "你先不要再转账，我帮你按时间顺序记录。第一通电话是什么时间？"},
            {"role": "assistant", "speaker_name": "王丽", "content": "大概下午两点二十，说我的订单理赔异常。"},
            {"role": "user", "content": "把收款账户、两笔金额、通话号码和截图都给我，我们同步启动止付。"},
            {"role": "assistant", "speaker_name": "王丽", "content": "好，我都在手机里，可以马上发给你。"},
        ],
    },
    {
        "username": "student003",
        "case_title": "张伟醉酒驾驶交通事故案",
        "scene_name": "事故现场控制与伤情核实",
        "days_ago": 4,
        "status": "finished",
        "score": 79,
        "cooperation": 70,
        "risk": 38,
        "clarity": 75,
        "revealed": ["已设置警戒", "驾驶人承认饮酒", "伤者已联系急救"],
        "messages": [
            {"role": "user", "content": "先在车后设置警示标志，伤者保持原位不要移动。"},
            {"role": "assistant", "speaker_name": "李娜", "content": "我腿疼，能不能先叫救护车？"},
            {"role": "user", "content": "已经联系120。张伟，你现在配合呼气检测，并说明今晚饮酒地点。"},
            {"role": "assistant", "speaker_name": "张伟", "content": "在老街饭店，喝了一点白酒和啤酒。"},
        ],
    },
]


def seed():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_user(db, "admin", "admin")
        users = {f"student00{i}": ensure_user(db, f"student00{i}", "student") for i in range(1, 6)}

        scene_index = {}
        for case_data in CASE_DATA:
            case_obj = ensure_case(db, case_data)
            for scene_data in case_data["scenes"]:
                scene = ensure_scene(db, case_obj, scene_data)
                scene_index[(case_data["title"], scene_data["name"])] = scene
                for role_data in scene_data["roles"]:
                    ensure_role(db, case_obj, scene, role_data)

        old_sessions = (
            db.query(models.TrainingSession)
            .filter(models.TrainingSession.evaluation_result.contains(DEMO_MARKER))
            .all()
        )
        old_ids = [session.id for session in old_sessions]
        if old_ids:
            db.query(models.Message).filter(models.Message.session_id.in_(old_ids)).delete(synchronize_session=False)
            db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(old_ids)).delete(synchronize_session=False)

        # Active sessions do not carry evaluation_result, so remove the previous demo active records by their exact message text.
        active_seed_sessions = (
            db.query(models.TrainingSession.id)
            .join(models.Message, models.Message.session_id == models.TrainingSession.id)
            .filter(models.Message.content.contains("先不要接陌生电话，把手机放在桌上"))
            .all()
        )
        active_ids = [row.id for row in active_seed_sessions]
        if active_ids:
            db.query(models.Message).filter(models.Message.session_id.in_(active_ids)).delete(synchronize_session=False)
            db.query(models.TrainingSession).filter(models.TrainingSession.id.in_(active_ids)).delete(synchronize_session=False)

        now = datetime(2026, 6, 6, 20, 30, 0)
        for template in SESSION_TEMPLATES:
            scene = scene_index[(template["case_title"], template["scene_name"])]
            created_at = now - timedelta(days=template["days_ago"], hours=template["days_ago"] % 3)
            add_session(
                db,
                users[template["username"]],
                scene,
                template["messages"],
                created_at,
                template["status"],
                template["score"],
                template["revealed"],
                template["cooperation"],
                template["risk"],
                template["clarity"],
            )

        db.commit()
        print("Imported realistic demo data.")
        print(f"Cases: {db.query(models.Case).count()}")
        print(f"Scenes: {db.query(models.Scene).count()}")
        print(f"Roles: {db.query(models.Role).count()}")
        print(f"Training sessions: {db.query(models.TrainingSession).count()}")
        print(f"Messages: {db.query(models.Message).count()}")
        print("Demo users: admin/student001-student005, password: 123456")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
