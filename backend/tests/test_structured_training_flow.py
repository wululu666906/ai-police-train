import routers.training as training_router


def test_chat_response_contains_structured_fields(client, student_headers):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]
    response = client.post(
        f"/training/chat/{session_id}",
        json={"role": "user", "content": "请先说一下事情经过"},
        headers=student_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("reply_sequence"), list)
    assert "assessment_progress" in data
    assert "available_actions" in data
    assert "auto_finished" in data


def test_chat_auto_finish_triggers_evaluation(client, student_headers, monkeypatch):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]
    called = {"evaluated": False}

    def fake_generate_dialogue(db, session_id, user_message, user_id=None, **kwargs):
        return {
            "response": "现场已经处理完毕。",
            "reply_sequence": ["现场已经处理完毕。", "本轮训练结束，转入评估。"],
            "inner_thought": "ok",
            "updated_emotion": 50,
            "updated_trust": 60,
            "is_stage_completed": True,
            "current_stage": "收尾",
            "current_stage_goal": "完成收尾",
            "recommended_questions": [],
            "communication_feedback": {"level": "good", "message": "已结束"},
            "assessment_progress": {"summary": {}},
            "available_actions": [],
            "auto_finished": True,
            "redirect_to_evaluation": True,
        }

    def fake_evaluate_session(db, session_id, user_id=None, force_recompute=False):
        called["evaluated"] = True
        return {"total_score": 80, "scores": []}

    monkeypatch.setattr(training_router, "generate_dialogue", fake_generate_dialogue)
    monkeypatch.setattr(training_router, "evaluate_session", fake_evaluate_session)

    response = client.post(
        f"/training/chat/{session_id}",
        json={"role": "user", "content": "结束本轮训练"},
        headers=student_headers,
    )
    assert response.status_code == 200
    assert response.json()["auto_finished"] is True
    assert called["evaluated"] is True


def test_action_route_success(client, student_headers, monkeypatch):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]

    def fake_apply_training_action(db, session_id, action_id, note="", user_id=None):
        return {
            "response": "好，我看到你们已经开始取证了。",
            "reply_sequence": ["好，我看到你们已经开始取证了。"],
            "inner_thought": "ok",
            "recognized_actions": [{"action_id": action_id, "label": "固定现场证据"}],
            "assessment_progress": {"summary": {}},
            "available_actions": [{"id": action_id, "label": "固定现场证据", "completed": True}],
            "communication_feedback": {"level": "info", "message": "动作已记录"},
            "recommended_questions": [],
            "current_stage": "现场处置",
            "current_stage_goal": "完成固定证据",
            "updated_emotion": 40,
            "updated_trust": 50,
            "auto_finished": False,
        }

    monkeypatch.setattr(training_router, "apply_training_action", fake_apply_training_action)

    response = client.post(
        f"/training/action/{session_id}",
        json={"action_id": "act_photo_evidence", "note": "先拍照固定现场"},
        headers=student_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recognized_actions"][0]["action_id"] == "act_photo_evidence"
    assert data["available_actions"][0]["completed"] is True
