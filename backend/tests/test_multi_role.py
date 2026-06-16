"""Multi-role dialogue training tests."""

import models
from services import ai_service
from services.training_runtime_service import dump_runtime_state, load_runtime_state


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

    client.request("DELETE", f"/training/session/{session_id}", headers=student_headers)


def test_session_scene_roles_include_per_role_state_deltas(client, student_headers, db_session):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]
    session = db_session.query(models.TrainingSession).filter_by(id=session_id).first()
    zhang = db_session.query(models.Role).filter_by(name="张某").first()
    li = db_session.query(models.Role).filter_by(name="李某").first()

    runtime_state = load_runtime_state(session.revealed_info)
    runtime_state["role_state_snapshots"] = {
        str(zhang.id): {"emotion": 72, "cooperation": 43, "risk": 64, "clarity": 56},
        str(li.id): {"emotion": 66, "cooperation": 24, "risk": 58, "clarity": 48},
    }
    runtime_state["role_state_deltas"] = {
        str(zhang.id): {"emotion": -4, "cooperation": 3, "risk": -2, "clarity": 1},
        str(li.id): {"emotion": 2, "cooperation": -5, "risk": 4, "clarity": -3},
    }
    runtime_state["last_active_role_ids"] = [li.id]
    session.revealed_info = dump_runtime_state(runtime_state)
    db_session.commit()

    response = client.get(f"/training/session/{session_id}", headers=student_headers)
    assert response.status_code == 200
    roles = {item["name"]: item for item in response.json().get("scene_roles") or []}

    assert roles["张某"]["emotion"] == 72
    assert roles["张某"]["emotion_delta"] == -4
    assert roles["张某"]["cooperation_delta"] == 3
    assert roles["张某"]["risk_delta"] == -2
    assert roles["张某"]["clarity_delta"] == 1
    assert roles["李某"]["emotion_delta"] == 2
    assert roles["李某"]["cooperation_delta"] == -5
    assert roles["李某"]["risk_delta"] == 4
    assert roles["李某"]["clarity_delta"] == -3
    assert roles["李某"]["is_active"] is True

    client.request("DELETE", f"/training/session/{session_id}", headers=student_headers)


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

    client.request("DELETE", f"/training/session/{session_id}", headers=student_headers)
