from services.case_scene_module_service import select_scene_modules
from services.workflow_service import workflow_service


def _module_titles(case_info):
    return [item["title"] for item in select_scene_modules(case_info, limit=4)]


def test_scene_modules_pick_theft_specific_workflow_from_case_facts():
    titles = _module_titles(
        {
            "case_name": "电动车被盗案",
            "case_type": "盗窃",
            "case_background": "报警人称电动车被偷，现场有监控，车棚门口有可疑人员。",
            "evidence_points": ["小区监控", "车棚出入口"],
        }
    )

    assert "失窃报警核实" in titles
    assert "盗窃现场勘查" in titles
    assert "可疑线索询问" in titles
    assert "接警研判" not in titles


def test_scene_modules_pick_self_harm_and_missing_person_modules():
    titles = _module_titles(
        {
            "case_name": "学生失联轻生风险求助",
            "case_type": "自杀干预",
            "case_background": "家属报警称学生离家失联，曾发轻生信息，可能在学校附近。",
        }
    )

    assert "走失求助信息核查" in titles
    assert "轻生自伤风险干预" in titles


def test_fallback_scenes_are_composed_from_reality_modules():
    case_info = {
        "case_name": "冒充客服诈骗案",
        "case_type": "电信网络诈骗",
        "persons": [
            {"name": "王明", "role_type": "报警人", "status": "正常"},
            {"name": "李丽", "role_type": "被害人", "status": "正常"},
        ],
        "case_background": "李丽接到冒充客服来电后按要求转账，王明陪同报警，手机中仍有聊天记录和转账记录。",
    }

    result = workflow_service._fallback_scenes(case_info)
    names = [scene["scene_name"] for scene in result["scenes"]]

    assert result["scene_generation_mode"] == "fallback_case_driven"
    assert "涉诈报警与预警劝阻" in names
    assert "资金流与电子证据核查" in names
    assert "接警研判" not in names
    assert all(scene["stages"] for scene in result["scenes"])
