"""Tests for contextual recommended question generation."""

from services.recommended_questions_service import (
    build_recommended_question_items,
    build_recommended_questions,
)


def test_goal_does_not_quote_stage_goal_verbatim():
    goal = "评估现场安全，呼叫120，初步了解伤者情况，保护现场"
    questions = build_recommended_questions(
        current_stage="现场处置",
        current_stage_goal=goal,
        case_type="求助",
        role_name="报警人",
    )
    assert questions
    assert not any("先围绕" in item for item in questions)
    assert not any(goal[:12] in item for item in questions)
    joined = " ".join(questions)
    assert any(token in joined for token in ("120", "伤者", "危险", "外伤", "处置"))


def test_neighborhood_dispute_questions_sound_natural():
    questions = build_recommended_questions(
        current_stage="核实调解",
        current_stage_goal="核实对方情况，尝试调解",
        case_type="邻里纠纷",
        scene_name="楼道纠纷调解",
        role_name="张某",
        role_type="报警人",
    )
    assert questions
    assert all(len(item) <= 48 for item in questions)
    assert any("？" in item for item in questions)


def test_multi_role_adds_addressed_prompts():
    questions = build_recommended_questions(
        current_stage="核实调解",
        current_stage_goal="核实双方陈述",
        case_type="邻里纠纷",
        scene_roles=[
            {"name": "张某", "speakable": True},
            {"name": "李某", "speakable": True},
        ],
    )
    assert any("张某" in item or "李某" in item for item in questions)


def test_filters_meta_instruction_style():
    bad = build_recommended_questions(
        current_stage_goal="评估现场安全，呼叫120，初步了解伤者情况，保护",
    )
    assert not any("把最关键" in item for item in bad)


def test_custom_prompts_have_priority():
    items = build_recommended_question_items(
        custom_prompts=["张某，楼道杂物是你放的吗？"],
        current_stage_goal="评估现场安全",
        use_llm=False,
    )
    assert items
    assert items[0]["text"] == "张某，楼道杂物是你放的吗？"
    assert items[0]["category"] == "定制"


def test_skips_redundant_time_question_after_user_asked_time():
    items = build_recommended_question_items(
        recent_messages=[
            {"role": "user", "content": "事情大概是上午9点发生的，当时还有谁在场？"},
            {"role": "assistant", "content": "对，就是9点左右。", "speaker_name": "张某"},
        ],
        current_stage_goal="了解时间与经过",
        use_llm=False,
    )
    texts = [item["text"] for item in items]
    assert not any("什么时候" in text or "几点" in text for text in texts)


def test_followup_from_last_assistant_reply():
    items = build_recommended_question_items(
        recent_messages=[
            {"role": "assistant", "content": "就是他先骂我，还推了我一下！", "speaker_name": "张某"},
        ],
        use_llm=False,
    )
    joined = " ".join(item["text"] for item in items)
    assert "动手" in joined or "在场" in joined or "具体" in joined
