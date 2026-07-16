from services.workflow_service import workflow_service


def _trace(stage: str):
    return {
        "primary_provider": "deepseek",
        "final_provider": "deepseek",
        "switched_provider": False,
        "attempts": [{"provider": "deepseek", "model": "test-long", "mode": "plain_json", "status": "success", "stage": stage}],
    }


def test_parse_preserves_evidence_offsets_and_story_world(monkeypatch):
    text = "2026年5月10日，张三在东风路看见李四搬走电脑，随后报警。"

    def fake_call(*, stage, **_kwargs):
        if stage == "evidence_extraction":
            return {"facts": [{"content": "张三在东风路看见李四搬走电脑", "fact_type": "行为", "quote": "张三在东风路看见李四搬走电脑", "status": "confirmed"}]}, _trace(stage)
        return {
            "case_name": "电脑被搬走警情",
            "case_type": "盗窃",
            "persons": [{"name": "张三", "role": "报警人", "role_type": "证人"}, {"name": "李四", "role": "相关人员", "role_type": "嫌疑人"}],
            "story_world": {"fact_cards": [{"id": "F1", "content": "张三在东风路看见李四搬走电脑", "fact_type": "行为", "status": "confirmed", "source_refs": [{"source_id": "source-1", "start": 12, "end": 29, "summary": "张三在东风路看见李四搬走电脑"}]}], "simulation_supplements": [{"id": "SIM1", "content": "现场监控正在调取", "purpose": "训练取证流程", "applicable_scene_types": ["现场核查"], "is_scoring_fact": False}]},
        }, _trace(stage)

    monkeypatch.setattr(workflow_service, "_call_case_ai", fake_call)
    result = workflow_service.parse_case_text(text)
    card = result["story_world"]["fact_cards"][0]
    assert result["parse_engine"] == "ai"
    assert card["source_refs"][0]["start"] >= 0
    assert result["story_world"]["simulation_supplements"][0]["is_scoring_fact"] is False


def test_scene_scripts_must_reference_authorized_facts(monkeypatch):
    case_info = {
        "case_name": "测试案件", "case_type": "盗窃",
        "persons": [{"name": "张三", "role_type": "证人", "status": "正常"}],
        "story_world": {"fact_cards": [{"id": "F1", "content": "张三报警", "status": "confirmed", "source_refs": [{"start": 0, "end": 4}]}], "simulation_supplements": []},
    }

    def fake_call(*, stage, **_kwargs):
        if stage == "scene_blueprint":
            return {"blueprints": [{"scene_id": "S1", "scene_name": "报警核实", "training_goal": "核实情况", "roles": ["张三"], "fact_ids": ["F1"], "stages": [{"stage_name": "信息初核", "stage_goal": "核实报警"}]}]}, _trace(stage)
        return {"scene_name": "报警核实", "scene_description": "民警核实报警信息", "difficulty": "低", "dispatch_brief": "收到报警", "first_impression": "报警人在线", "roles": ["张三"], "fact_ids": ["F1"], "supplement_ids": [], "stages": [{"stage_name": "信息初核", "stage_goal": "核实报警", "fact_ids": ["F1"]}], "script_markdown": "# 民警任务\n核实报警"}, _trace(stage)

    monkeypatch.setattr(workflow_service, "_call_case_ai", fake_call)
    result = workflow_service.generate_scenes(case_info)
    assert result["scene_generation_mode"].startswith("ai_")
    assert result["scenes"][0]["fact_ids"] == ["F1"]
    assert "民警任务" in result["scenes"][0]["script_markdown"]


def test_scene_json_failure_uses_ai_text_template_before_rule_fallback(monkeypatch):
    case_info = {
        "case_name": "测试案件", "case_type": "盗窃",
        "persons": [{"name": "张三", "role_type": "证人", "status": "正常"}],
        "story_world": {"fact_cards": [{"id": "F1", "content": "张三报警", "status": "confirmed", "source_refs": [{"start": 0, "end": 4}]}], "simulation_supplements": []},
    }
    monkeypatch.setattr(workflow_service, "_call_case_ai", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("invalid json")))
    monkeypatch.setattr(
        workflow_service,
        "_call_scene_text_ai",
        lambda **_kwargs: ("# 场景 1\n场景名称：报警核实\n场景信息：民警核实报警。\n接警信息：收到张三报警。\n现场第一印象：张三在线等待。\n参与角色：张三\n引用事实：F1\n## 训练阶段\n1. 信息初核：核实报警经过。\n## 民警任务与角色回应边界\n围绕 F1 询问。", _trace("scene_text_template")),
    )

    result = workflow_service.generate_scenes(case_info)

    assert result["scene_generation_mode"] == "ai_text_template"
    assert result["ai_workflow"]["used_rule_fallback"] is False
    assert result["scenes"][0]["scene_name"] == "报警核实"
