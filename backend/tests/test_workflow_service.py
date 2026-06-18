import json
from types import SimpleNamespace

from services.ai_service import _build_role_archetype_block, _get_stage_goal
from services.evaluation_service import _build_scene_info
from services.persona_engine import normalize_compact_persona_fields
from services.workflow_service import workflow_service


class MockScene:
    def __init__(self, stages):
        self.stages = stages


def test_get_stage_goal_prefers_stage_goal_field():
    scene = MockScene(
        json.dumps(
            [
                {
                    "stage_name": "信息初核",
                    "stage_goal": "优先核实报警人身份和现场风险。",
                    "goal": "旧字段目标",
                }
            ],
            ensure_ascii=False,
        )
    )

    assert _get_stage_goal(scene, "信息初核") == "优先核实报警人身份和现场风险。"


def test_normalize_parsed_case_refreshes_dispatch_brief_from_fact_sheet():
    text = "2026年5月1日21时许，报警人李娟称在XX路东段废弃仓库发现一名男子倒地。"
    payload = {
        "case_name": "仓库发现尸体警情",
        "case_type": "故意杀人",
        "fact_sheet": {
            "case_time": "2026年5月1日21时许",
            "case_location": "XX路东段废弃仓库",
            "report_time": "2026年5月1日21时许",
        },
        "dispatch_brief_suggestion": "接警指令：请前往 未明确 处置与“仓库发现尸体警情”相关警情，并尽快核实现场情况。",
    }

    result = workflow_service._normalize_parsed_case(text, payload, "plain_case", None)

    assert "XX路东段废弃仓库" in result["dispatch_brief_suggestion"]
    assert "未明确" not in result["dispatch_brief_suggestion"]


def test_normalize_compact_persona_fields_derives_relation_pressure_from_legacy_lists():
    compact = normalize_compact_persona_fields(
        {
            "protected_targets": ["儿子"],
            "feared_people": ["岳父"],
            "conflict_targets": ["王某"],
            "feared_consequences": ["怕被单位追责"],
        }
    )

    assert "护着儿子" in compact["relationship_pressure"]
    assert "忌惮岳父" in compact["relationship_pressure"]
    assert "和王某有旧怨或关系压力" in compact["relationship_pressure"]
    assert "怕被单位追责" in compact["relationship_pressure"]


def test_clean_person_maps_legacy_template_into_minimal_fields():
    person = workflow_service._clean_person(
        {
            "name": "李某",
            "role": "报警人",
            "role_type": "证人",
            "personality": "护短、嘴硬",
            "speaking_style": "先试探再补充",
            "current_need": "先别把儿子牵连进来",
            "weakness": "最怕单位知道",
            "public_mask": "我就是想把事情说明白，没有故意偏袒谁",
            "stress_response": "先回避，再看警方掌握多少",
            "trigger_topics": ["问到儿子", "问到单位责任"],
            "hidden_truths": ["其实提前和对方起过冲突"],
        }
    )

    assert person["current_goal"] == "先别把儿子牵连进来"
    assert person["core_concern"] == "最怕单位知道"
    assert person["surface_stance"] == "我就是想把事情说明白，没有故意偏袒谁"
    assert person["pressure_response"] == "先回避，再看警方掌握多少"
    assert person["trigger_points"] == ["问到儿子", "问到单位责任"]
    assert person["behavior_archetype"] == "强硬对抗型"
    assert person["police_attitude"] == "敌对抵触"
    assert person["calming_points"] == ["先稳语气再问事实", "给台阶，不当众硬压"]
    assert person["persona_template_version"] == "minimal_v3"


def test_person_name_standardization_strips_role_and_scene_suffixes():
    payload = {
        "case_name": "邻里纠纷",
        "case_type": "其他",
        "persons": [
            {"name": "张三（审讯阶段）", "role_type": "嫌疑人", "knows_facts": ["承认到过现场"]},
            {"name": "张三嫌疑人", "role_type": "嫌疑人", "hidden_truths": ["不愿说明动手细节"]},
            {"name": "证人张三", "role_type": "证人", "does_not_know": ["不清楚报警时间"]},
            {"name": "幸福小区", "role_type": "相关人员"},
            {"name": "口供", "role_type": "相关人员"},
        ],
    }

    result = workflow_service._normalize_parsed_case(
        "报警人李四称，张三在幸福小区与其发生争执。证人张三表示只看到争吵。",
        payload,
        "plain_case",
        None,
    )

    names = [person["name"] for person in result["persons"]]
    assert "张三" in names
    assert "张三嫌疑人" not in names
    assert "证人张三" not in names
    assert "幸福小区" not in names
    assert "口供" not in names

    zhang = next(person for person in result["persons"] if person["name"] == "张三")
    assert zhang["person_id"] == "P001"
    assert zhang["role_type"] in {"嫌疑人", "证人"}
    assert "承认到过现场" in zhang["knows_facts"]
    assert "不愿说明动手细节" in zhang["hidden_truths"]


def test_scene_role_names_are_locked_to_case_person_names():
    case_info = {
        "persons": [
            {"person_id": "P001", "name": "张三", "aliases": ["张三嫌疑人"], "status": "正常"},
            {"person_id": "P002", "name": "李四", "status": "正常"},
        ]
    }
    payload = {
        "scenes": [
            {
                "scene_name": "重点询问",
                "roles": ["张三（审讯阶段）", "证人李四", "幸福小区"],
                "stages": [{"stage_name": "核实身份", "stage_goal": "核实到场人员身份。"}],
            }
        ]
    }

    result = workflow_service._normalize_scenes(case_info, payload)

    assert result["scenes"][0]["roles"] == ["张三", "李四"]


def test_role_archetype_block_uses_compact_persona_signals():
    role = SimpleNamespace(role_type="嫌疑人", interaction_style="观察型", weakness="最怕孩子被牵连")
    scene = SimpleNamespace(name="现场调查")
    persona_profile = {
        "behavior_archetype": "防御切责型",
        "police_attitude": "防备排斥",
        "current_goal": "先把主动责任切出去",
        "core_concern": "最怕孩子被牵连",
        "trigger_points": ["问谁先动手"],
        "calming_points": ["先按时间线核实"],
    }

    block = _build_role_archetype_block(role, scene, persona_profile)

    assert "切割关键行为" in block
    assert "先切责任再谈细节" in block
    assert "先把主动责任切出去" in block
    assert "问谁先动手" in block
    assert "先按时间线核实" in block


def test_evaluation_scene_info_includes_compact_persona_snapshot():
    role = SimpleNamespace(
        name="李某",
        role_type="证人",
        interaction_style="观察型",
        personality="谨慎、护短",
        speaking_style="先试探，再补充",
        weakness="最怕孩子受牵连",
        status="正常",
        hidden_truths="[]",
        knows_facts="[]",
        does_not_know="[]",
        persona_meta=json.dumps(
            {
                "behavior_archetype": "谨慎回避型",
                "police_attitude": "试探观望",
                "current_goal": "先别把自己卷进正式责任",
                "core_concern": "最怕孩子受牵连",
                "relationship_pressure": ["护着孩子"],
                "trigger_points": ["孩子会不会被牵连"],
                "calming_points": ["先讲清不会乱定性"],
            },
            ensure_ascii=False,
        ),
    )
    scene = SimpleNamespace(name="现场调查")

    scene_info = _build_scene_info(scene, "现场", role)

    assert "行为原型：谨慎回避型" in scene_info
    assert "对警方基本态度：试探观望" in scene_info
    assert "当前诉求：先别把自己卷进正式责任" in scene_info
    assert "核心顾虑：最怕孩子受牵连" in scene_info
    assert "关系压力：护着孩子" in scene_info
    assert "可安抚点：先讲清不会乱定性" in scene_info
