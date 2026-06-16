"""Tests for contextual recommended question generation."""

from services.recommended_questions_service import (
    apply_stage_hit_rate_correction,
    build_recommended_question_items,
    build_recommended_questions,
    filter_stale_missing_requirements_for_history,
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


def test_intake_moves_to_safety_after_incident_is_covered():
    items = build_recommended_question_items(
        scene_kind="intake",
        current_stage="接警",
        role_name="报警人",
        missing_requirements=["具体情况", "事情经过"],
        recent_messages=[
            {"role": "assistant", "content": "我邻居在楼下跟人打起来了，我刚报的警。", "speaker_name": "报警人"},
        ],
        last_user_message="请你说一下现场具体什么情况，发生什么事了？",
        use_llm=False,
    )

    texts = [item["text"] for item in items]
    assert texts
    assert any("安全" in text or "受伤" in text or "继续冲突" in text for text in texts[:2])
    assert not any("具体情况" in text or "事情经过能再说详细" in text for text in texts[:2])


def test_intake_moves_to_identity_after_time_location_and_safety():
    items = build_recommended_question_items(
        scene_kind="intake",
        current_stage="接警",
        role_name="报警人",
        missing_requirements=["事情经过", "身份信息"],
        recent_messages=[
            {"role": "user", "content": "具体出了什么事？你现在安全吗？有没有人受伤？"},
            {"role": "assistant", "content": "我安全，对方也没受伤，就是楼下两个人争吵推搡。", "speaker_name": "报警人"},
            {"role": "user", "content": "你现在具体在哪里？事情大概几点发生的？"},
            {"role": "assistant", "content": "在幸福小区3号楼门口，大概晚上8点半开始的。", "speaker_name": "报警人"},
        ],
        use_llm=False,
    )

    texts = [item["text"] for item in items]
    assert texts
    assert any("姓名" in text or "联系电话" in text or "联系方式" in text for text in texts[:2])
    assert not any("经过" in text or "具体出了什么事" in text for text in texts[:2])


def test_intake_moves_to_contact_after_core_facts_and_people():
    items = build_recommended_question_items(
        scene_kind="intake",
        current_stage="接警",
        role_name="报警人",
        missing_requirements=["案件基本情况", "事发时间", "事发地点", "涉事人员"],
        recent_messages=[
            {"role": "user", "content": "具体出了什么事？现场有没有人受伤？"},
            {"role": "assistant", "content": "楼下两个人因为停车吵起来了，没有人受伤。", "speaker_name": "报警人"},
            {"role": "user", "content": "事情是什么时候发生的？具体地点在哪里？现场还有哪些人在？"},
            {"role": "assistant", "content": "晚上8点半，在幸福小区3号楼门口，涉事双方都还在。", "speaker_name": "报警人"},
        ],
        use_llm=False,
    )

    texts = [item["text"] for item in items]
    assert texts
    assert any("姓名" in text or "联系电话" in text or "回拨" in text for text in texts[:2])
    assert not any("经过" in text or "具体出了什么事" in text or "几点" in text or "位置" in text for text in texts[:2])


def test_intake_closure_after_contact_and_dispatch_context():
    items = build_recommended_question_items(
        scene_kind="intake",
        current_stage="接警",
        role_name="报警人",
        recent_messages=[
            {"role": "user", "content": "具体出了什么事？有没有人受伤？具体地点在哪里？"},
            {"role": "assistant", "content": "停车纠纷，没人受伤，在幸福小区3号楼门口。", "speaker_name": "报警人"},
            {"role": "user", "content": "事情几点发生？现场还有哪些人？请报姓名和联系电话，方便回拨。"},
            {"role": "assistant", "content": "晚上8点半，双方都在。我叫王某，电话13800000000。", "speaker_name": "报警人"},
            {"role": "user", "content": "民警会到场处置，你先待在安全位置。"},
            {"role": "assistant", "content": "好的，我在门口等。", "speaker_name": "报警人"},
        ],
        use_llm=False,
    )

    texts = [item["text"] for item in items]
    assert texts
    assert any("电话畅通" in text or "安全位置" in text or "别离开" in text for text in texts[:2])
    assert not any("经过" in text or "具体出了什么事" in text or "几点" in text or "什么位置" in text for text in texts[:2])


def test_history_filter_removes_covered_intake_process_gap():
    missing = filter_stale_missing_requirements_for_history(
        ["什么事/经过", "风险/伤情", "身份/关系"],
        recent_messages=[
            {"role": "assistant", "content": "楼下有人打起来了，我刚报警。", "speaker_name": "报警人"},
        ],
        last_user_message="请说一下具体什么情况，发生什么事了？",
        use_intake_flow=True,
    )

    assert "什么事/经过" not in missing
    assert "风险/伤情" in missing
    assert "身份/关系" in missing


def test_stage_hit_correction_uses_filtered_gaps_without_repeating_process():
    missing = filter_stale_missing_requirements_for_history(
        ["什么事/经过"],
        recent_messages=[
            {"role": "assistant", "content": "楼下有人打起来了，我刚报警。", "speaker_name": "报警人"},
        ],
        last_user_message="请说一下具体什么情况，发生什么事了？",
        use_intake_flow=True,
    )
    items = [{"text": "你现在人安全吗？有没有人受伤？", "category": "安抚", "target_role_name": None}]

    corrected = apply_stage_hit_rate_correction(items, satisfied=["什么事/经过"], missing=missing)

    assert corrected[0]["text"] == "你现在人安全吗？有没有人受伤？"
