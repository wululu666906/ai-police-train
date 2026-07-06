"""Tests for DeepSeek case completion officer."""

from services import case_completion_service
from services.workflow_service import workflow_service


def test_field_catalog_has_core_groups():
    catalog = case_completion_service.list_field_catalog()
    groups = catalog["groups"]
    assert "case_basic" in groups
    assert "persons" in groups
    assert "scenes" in groups


def test_merge_fill_gaps_preserves_existing_title(monkeypatch):
    monkeypatch.setattr(
        case_completion_service.workflow_service,
        "extract_case_person_names",
        lambda text: [],
    )

    def fake_completion(**kwargs):
        class _Msg:
            content = '{"case_name":"AI标题","case_type":"打架斗殴","case_background":"新背景","persons":[],"parse_engine":"ai","completion_engine":"deepseek-case-officer","filled_field_paths":["case_background"]}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr(
        "services.case_completion_service.create_case_completion_chat_completion",
        fake_completion,
    )

    result = case_completion_service.complete_case_information(
        source_text="2024年1月1日，张某与李某在小区门口打架。",
        existing_case={"case_name": "人工标题", "case_type": "邻里纠纷", "case_background": ""},
        mode="fill_gaps",
        include_scenes=False,
    )
    assert result["case_info"]["case_name"] == "人工标题"
    assert "张某" in result["case_info"]["case_background"]
    assert "李某" in result["case_info"]["case_background"]


def test_merge_case_info_standardizes_completed_person_names_and_scene_roles():
    merged, filled = case_completion_service._merge_case_info(
        {
            "persons": [
                {"name": "张三", "role_type": "嫌疑人", "status": "正常"},
            ],
            "scenes": [
                {"scene_name": "重点询问", "roles": ["张三（审讯阶段）"]},
            ],
        },
        {
            "persons": [
                {"name": "张三嫌疑人", "role_type": "嫌疑人", "hidden_truths": ["不愿说明动手细节"]},
                {"name": "幸福小区", "role_type": "相关人员"},
            ],
            "scenes": [
                {"scene_name": "重点询问", "roles": ["张三嫌疑人", "幸福小区"]},
            ],
        },
        mode="fill_gaps",
    )

    assert [person["name"] for person in merged["persons"]] == ["张三"]
    assert merged["persons"][0]["person_id"] == "P001"
    assert "不愿说明动手细节" in merged["persons"][0]["hidden_truths"]
    assert merged["scenes"][0]["roles"] == ["张三"]
    assert any(path.startswith("persons[张三]") for path in filled)


def test_heuristic_parse_extracts_background_timeline_and_relationships():
    text = (
        "2024年1月1日20时许，报警人张某称在幸福小区南门与邻居李某因停车问题发生争吵。"
        "李某将张某推倒并造成手臂擦伤，现场有小区监控和物业人员在场。"
        "张某要求民警处理赔偿问题，李某否认自己先动手。"
    )

    result = workflow_service._heuristic_parse_case(text, "plain_case", None)

    assert result["case_type"] in {"打架斗殴", "故意伤害", "邻里纠纷"}
    assert "张某" in result["case_background"]
    assert "李某" in result["case_background"]
    assert result["fact_sheet"]["timeline"]
    assert result["fact_sheet"]["relationships"]
    assert result["key_facts"]
    assert result["evidence_points"]
    assert "谁：" in result["transcript_summary"]


def test_case_completion_fallback_preserves_failure_warning(monkeypatch):
    monkeypatch.setattr(
        case_completion_service.workflow_service,
        "extract_case_person_names",
        lambda text: [],
    )
    monkeypatch.setattr(
        case_completion_service.workflow_service,
        "parse_case_text",
        lambda text, source_mode="plain_case", source_meta=None: workflow_service._heuristic_parse_case(text, source_mode, source_meta),
    )

    def broken_completion(**kwargs):
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(
        "services.case_completion_service.create_case_completion_chat_completion",
        broken_completion,
    )

    result = case_completion_service.complete_case_information(
        source_text=(
            "2024年1月1日20时许，报警人张某称在幸福小区南门与邻居李某因停车问题发生争吵。"
            "李某将张某推倒并造成手臂擦伤，现场有小区监控。"
        ),
        existing_case={},
        mode="fill_gaps",
        include_scenes=False,
    )

    assert result["completion_engine"] == "heuristic"
    assert any("upstream timeout" in warning for warning in result["completion_warnings"])
    assert "张某" in result["case_info"]["case_background"]
    assert result["case_info"]["fact_sheet"]["timeline"]


def test_scene_group_is_not_sent_to_case_completion_prompt(monkeypatch):
    monkeypatch.setattr(
        case_completion_service.workflow_service,
        "extract_case_person_names",
        lambda text: [],
    )

    captured = {}

    def fake_completion(**kwargs):
        captured["messages"] = kwargs["messages"]

        class _Msg:
            content = '{"case_name":"测试案件","case_type":"盗窃","case_background":"报警人称手机被盗。","persons":[],"parse_engine":"ai","completion_engine":"deepseek-case-officer"}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    monkeypatch.setattr(
        "services.case_completion_service.create_case_completion_chat_completion",
        fake_completion,
    )
    monkeypatch.setattr(
        case_completion_service.workflow_service,
        "generate_scenes",
        lambda *args, **kwargs: {"scenes": [], "scene_generation_mode": "ai_case_driven", "scene_generation_warning": ""},
    )

    result = case_completion_service.complete_case_information(
        source_text="报警人称手机被盗。",
        existing_case={},
        mode="fill_gaps",
        target_groups=["case_basic", "persons", "scenes"],
        include_scenes=True,
    )

    user_payload = captured["messages"][1]["content"]
    assert "scenes[]" not in user_payload
    assert result["completion_engine"] == "deepseek-case-officer"
    assert result["completion_target_groups"] == ["case_basic", "persons"]
    assert "scenes" in result["target_groups"]


def test_scene_generation_failure_does_not_downgrade_case_completion(monkeypatch):
    monkeypatch.setattr(
        case_completion_service.workflow_service,
        "extract_case_person_names",
        lambda text: [],
    )

    def fake_completion(**kwargs):
        class _Msg:
            content = '{"case_name":"测试案件","case_type":"盗窃","case_background":"报警人称手机被盗。","persons":[],"parse_engine":"ai","completion_engine":"deepseek-case-officer"}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()

    def broken_scene_generation(*args, **kwargs):
        raise RuntimeError("scene timeout")

    monkeypatch.setattr(
        "services.case_completion_service.create_case_completion_chat_completion",
        fake_completion,
    )
    monkeypatch.setattr(case_completion_service.workflow_service, "generate_scenes", broken_scene_generation)

    result = case_completion_service.complete_case_information(
        source_text="报警人称手机被盗。",
        existing_case={},
        mode="fill_gaps",
        target_groups=["case_basic", "scenes"],
        include_scenes=True,
    )

    assert result["completion_engine"] == "deepseek-case-officer"
    assert result["scenes"] == []
    assert "场景生成子任务失败" in result["scene_generation_warning"]
