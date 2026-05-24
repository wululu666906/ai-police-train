"""Multi-role dialogue training tests."""

from services import ai_service


def test_session_includes_scene_roles(client, student_headers):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]
    response = client.get(f"/training/session/{session_id}", headers=student_headers)
    assert response.status_code == 200
    data = response.json()
    roles = data.get("scene_roles") or []
    names = {item["name"] for item in roles}
    assert "张某" in names
    assert "李某" in names
    assert len(roles) >= 2


def test_chat_multi_role_reply_turns(client, student_headers, monkeypatch):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]

    def fake_generate_multi_role_turn(db, scene=None, case=None, roles=None, **kwargs):
        zhang = next((role for role in roles or [] if role.name == "张某"), None)
        li = next((role for role in roles or [] if role.name == "李某"), None)
        return {
            "primary_role": zhang or (roles[0] if roles else None),
            "response": "你别血口喷人！",
            "inner_thought": "不想承认。",
            "reply_turns": [
                {
                    "speaker_name": "张某",
                    "speaker_role_id": getattr(zhang, "id", None),
                    "content": "就是他先骂我！",
                    "inner_thought": "委屈",
                },
                {
                    "speaker_name": "李某",
                    "speaker_role_id": getattr(li, "id", None),
                    "content": "你别血口喷人！",
                    "inner_thought": "防御",
                },
            ],
            "updated_emotion": 58,
            "updated_trust": 32,
            "new_fact_revealed": None,
            "is_stage_completed": False,
        }

    monkeypatch.setattr(ai_service, "generate_multi_role_turn", fake_generate_multi_role_turn)

    response = client.post(
        f"/training/chat/{session_id}",
        json={"role": "user", "content": "你们俩都冷静一下，分别说经过"},
        headers=student_headers,
    )
    assert response.status_code == 200
    data = response.json()
    turns = data.get("reply_turns") or []
    assert len(turns) >= 2
    speakers = {item.get("speaker_name") for item in turns}
    assert "张某" in speakers
    assert "李某" in speakers
