import models
from services.multi_role_actor import _auto_ground_utterance, _build_scene_presence_contract, _grounding_memory_reply
from services.case_intelligence_service import validate_supporting_knowledge_ids
from services.multi_role_director import _enforce_cast_plan


def test_invalid_model_citation_repairs_from_own_memory_not_stock_phrase():
    role = models.Role(name="韩某", role_type="证人")
    reply = _grounding_memory_reply(
        role,
        {
            "ledger": [
                {"knowledge_id": "韩某-M1", "knowledge_mode": "direct_statement", "content": "我看见两人在山路边争执，后来其中一人受伤。"},
            ]
        },
        "讲一下现场发生了什么",
    )
    assert "山路边争执" in reply
    assert "只能说我当时亲眼看到" not in reply


def test_director_keeps_one_speaker_for_an_ordinary_question():
    first = models.Role(id=1, name="甲某", role_type="证人")
    second = models.Role(id=2, name="乙某", role_type="证人")
    plan = _enforce_cast_plan(
        {"cast_plan": [{"role": first}, {"role": second}]},
        addressed=[],
        roles=[first, second],
        user_text="讲一下现场发生了什么",
    )
    assert len(plan["cast_plan"]) == 1


def test_actor_reply_without_model_id_is_bound_to_matching_role_memory():
    view = {
        "ledger": [
            {
                "knowledge_id": "韩某-M1",
                "knowledge_mode": "direct_statement",
                "content": "我看见两人在山路边争执，其中一人后来脸部受伤。",
            },
            {
                "knowledge_id": "韩某-M2",
                "knowledge_mode": "direct_statement",
                "content": "我没有看到是谁先动手。",
            },
        ]
    }
    ids = _auto_ground_utterance("我看到他们在山路边吵起来，之后有人受伤了。", view, "现场发生了什么？")

    assert ids == ["韩某-M1"]
    assert validate_supporting_knowledge_ids(view, ids, require_support=True)["valid"] is True


def test_last_resort_reply_removes_statement_document_heading():
    role = models.Role(name="韩某", role_type="证人")
    reply = _grounding_memory_reply(
        role,
        {
            "ledger": [
                {
                    "knowledge_id": "韩某-M1",
                    "knowledge_mode": "direct_statement",
                    "content": "11. 证人韩某的证言：我看见两人在山路边争执。",
                }
            ]
        },
        "说一下你看到的情况",
    )

    assert "证言" not in reply
    assert "山路边争执" in reply


def test_scene_presence_prefers_current_scene_position_over_cross_timeline_memory():
    role = models.Role(name="韩某", role_type="证人")
    scene = models.Scene(
        name="群体性冲突现场",
        first_impression="民警在山脚公路边看到双方隔路对峙，政府工作人员正在劝阻。",
    )
    presence = _build_scene_presence_contract(
        role,
        scene,
        [
            {"statement": "韩某后来回到家中，听说山上还有人。", "place_hint": "家中", "time_hint": "事后"},
            {"statement": "韩某和工作人员在山脚劝阻群众。", "place_hint": "山脚", "time_hint": "当时"},
        ],
    )

    assert presence["presence"] == "present_with_source_position"
    assert presence["position"] == "山脚"
    assert presence["activity"] == "劝阻"
