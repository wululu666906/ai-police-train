from services.case_scene_module_service import select_scene_modules
from services.scene_design_service import compile_scene_lifecycles
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

    assert "失窃警情要素核实" in titles
    assert "盗窃现场勘查" in titles
    assert "盗窃可疑线索询问" in titles
    assert "接警研判" not in titles


def test_scene_modules_pick_self_harm_and_missing_person_modules():
    titles = _module_titles(
        {
            "case_name": "学生失联轻生风险求助",
            "case_type": "自杀干预",
            "case_background": "家属报警称学生离家失联，曾发轻生信息，可能在学校附近。",
        }
    )

    assert "走失人员信息核查" in titles
    assert "自伤轻生风险干预" in titles


def test_fallback_scenes_follow_primary_and_supporting_portfolio():
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
    assert result["scene_generation_mode"] == "fallback_case_driven"
    assert 3 <= len(result["scenes"]) <= 4
    roles = [scene["portfolio_role"] for scene in result["scenes"]]
    assert roles[:3] == ["intake", "primary", "investigation"]
    assert sum(1 for scene in result["scenes"] if scene["is_primary"]) == 1
    assert all(scene["stages"] for scene in result["scenes"])
    assert all(scene["scene_purpose"] for scene in result["scenes"])
    assert all(scene["training_goal"] for scene in result["scenes"])
    assert all(scene["completion_criteria"] for scene in result["scenes"])
    assert all(scene["end_prompt"] for scene in result["scenes"])
    assert all(scene["student_role"] == "民警" for scene in result["scenes"])
    assert all(scene["canonical_outcome_locked"] is True for scene in result["scenes"])
    assert all(
        scene["entry_time_policy"] == "after_canonical_event"
        for scene in result["scenes"]
        if scene["training_entry_phase"] != "intake"
    )


def test_scene_lifecycle_locks_post_incident_training_boundary():
    scenes = compile_scene_lifecycles(
        {"case_name": "测试案件"},
        [{
            "scene_name": "案发后询问",
            "training_entry_phase": "post_incident_inquiry",
            "entry_time_policy": "after_canonical_event",
            "first_impression": "当事人等待询问。",
            "roles": ["张三"],
            "stages": [{"stage_name": "询问", "stage_goal": "核实陈述"}],
        }],
    )

    contract = scenes[0]["entry_contract"]
    assert contract["student_role"] == "民警"
    assert contract["entry_time_policy"] == "after_canonical_event"
    assert contract["canonical_outcome_locked"] is True
    assert "不得改变案件既定事实与结果" in contract["impact_boundary"]
