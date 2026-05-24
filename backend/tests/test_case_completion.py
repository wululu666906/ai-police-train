"""Tests for DeepSeek case completion officer."""

from services import case_completion_service


def test_field_catalog_has_core_groups():
    catalog = case_completion_service.list_field_catalog()
    groups = catalog["groups"]
    assert "case_basic" in groups
    assert "persons" in groups
    assert "scenes" in groups


def test_merge_fill_gaps_preserves_existing_title(monkeypatch):
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
    assert result["case_info"]["case_background"] == "新背景"
