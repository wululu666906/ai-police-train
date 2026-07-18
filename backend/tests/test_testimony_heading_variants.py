from services.workflow_service import workflow_service


def test_numbered_unlabeled_statement_heading_creates_speaker_memory():
    text = "12. 韩某陈述：其在现场看见双方争执。\n13. 王某证言：其后拨打报警电话。"
    people = workflow_service._programmatic_people(text)
    names = {item["name"] for item in people}
    assert {"韩某", "王某"}.issubset(names)

    reconstruction = workflow_service._build_role_memories_and_case_flow(
        text,
        people,
        workflow_service._programmatic_claim_cards(text),
    )
    assert reconstruction["role_memories"]["韩某"][0]["quote"].startswith("12. 韩某陈述")
    assert reconstruction["role_memories"]["王某"][0]["quote"].startswith("13. 王某证言")
