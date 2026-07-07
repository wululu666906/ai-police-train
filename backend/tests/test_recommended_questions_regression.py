"""Regression tests for recommended question generation."""

from services.recommended_questions_service import build_recommended_question_items


def test_missing_first_correction_does_not_wrap_bool_in_any():
    items = build_recommended_question_items(
        current_stage="安抚止损",
        current_stage_goal="核实时间、地点和人物",
        missing_requirements=["时间"],
        use_llm=False,
    )

    assert items
    assert isinstance(items[0]["text"], str)


def test_page_load_llm_recommendations_are_bounded(mock_llm_provider):
    build_recommended_question_items(
        current_stage="initial",
        recent_messages=[
            {"role": "assistant", "content": "The caller has already described the incident.", "speaker_name": "caller"}
        ],
        last_user_message="Please confirm whether anyone is injured.",
        use_llm=True,
    )

    kwargs = mock_llm_provider.call_args.kwargs
    assert kwargs["retries"] == 1
    assert kwargs["allow_plain_json_fallback"] is False
    assert kwargs["extra_kwargs"]["timeout"] == 3.0


def test_page_load_recommendations_fall_back_when_llm_times_out(mock_llm_provider):
    mock_llm_provider.side_effect = TimeoutError("upstream timed out")

    items = build_recommended_question_items(
        current_stage="initial",
        recent_messages=[
            {"role": "assistant", "content": "The caller has already described the incident.", "speaker_name": "caller"}
        ],
        last_user_message="Please confirm whether anyone is injured.",
        use_llm=True,
    )

    assert items


def test_llm_recommendations_filter_non_officer_perspective(mock_llm_provider):
    mock_llm_provider.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"items":[{"text":"建议民警先询问现场风险？","category":"追问","target_role_name":null},{"text":"你现在人安全吗？","category":"核实","target_role_name":null}]}'
                }
            }
        ]
    }

    items = build_recommended_question_items(
        current_stage="接警",
        scene_kind="intake",
        recent_messages=[{"role": "assistant", "content": "我这边有人吵起来了。", "speaker_name": "报警人"}],
        last_user_message="你先别急。",
        use_llm=True,
    )

    texts = [item["text"] for item in items]
    assert "建议民警先询问现场风险？" not in texts
    assert all(text.endswith("？") for text in texts)
    assert all("建议" not in text and "学员" not in text for text in texts)
