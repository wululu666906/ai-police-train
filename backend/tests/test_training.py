import json
from types import SimpleNamespace
import models
import routers.training as training_router
import services.ai_service as ai_service
from services.training_runtime_service import dump_runtime_state, load_runtime_state
from services.dialogue_sanitize_service import limit_role_reply_turns_with_remainders


def test_plain_text_dialogue_fallback_preserves_complete_content():
    raw_content = "这是一段必须完整保留的角色台词。" * 40
    session = SimpleNamespace(
        current_trust=30,
        current_emotion=50,
        current_stage="初始接触",
        revealed_info=dump_runtime_state(load_runtime_state([])),
    )

    result = ai_service._build_plain_text_result(
        raw_content,
        session,
        "核实现场情况",
        None,
        {"cooperation": 30, "risk": 50, "clarity": 50},
    )

    assert len(raw_content) > 420
    assert result["response"] == raw_content


def test_targeted_role_continues_persisted_reply_before_new_answer():
    stored = {"7": {"role_name": "王某", "content": "上轮未展示的第二句事实。"}}
    turns = [{"speaker_role_id": 7, "speaker_name": "王某", "content": "这是本轮新回答。"}]

    combined, consumed_key = ai_service._prepend_targeted_pending_reply(turns, stored, "王某")
    visible, generated_pending = limit_role_reply_turns_with_remainders(combined)
    merged = ai_service._merge_pending_role_replies(stored, generated_pending, consumed_key)
    restored = load_runtime_state(dump_runtime_state({"pending_role_replies": merged}))

    assert consumed_key == "7"
    assert [item["content"] for item in visible] == ["上轮未展示的第二句事实。", "这是本轮新回答。"]
    assert restored["pending_role_replies"] == {}


class TestStartTraining:
    def test_start_training_success(self, client, student_headers, db_session):
        response = client.post("/training/start/1", headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["scene_id"] == 1
        assert 0 <= data["current_emotion"] <= 100
        assert data["current_trust"] == data["current_cooperation"]
        assert 0 <= data["current_cooperation"] <= 100
        assert 0 <= data["current_risk"] <= 100
        assert 0 <= data["current_clarity"] <= 100
        assert "初始接触" in data["current_stage"]

    def test_start_training_nonexistent_scene(self, client, student_headers):
        response = client.post("/training/start/9999", headers=student_headers)
        assert response.status_code == 404

    def test_start_training_returns_existing_active_session(self, client, student_headers):
        first = client.post("/training/start/1", headers=student_headers)
        first_data = first.json()
        second = client.post("/training/start/1", headers=student_headers)
        second_data = second.json()
        assert first_data["id"] == second_data["id"]

    def test_start_training_unauthorized(self, client):
        response = client.post("/training/start/1")
        assert response.status_code == 401


class TestChat:
    def test_chat_sends_message_and_gets_response(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        payload = {"role": "user", "content": "您好，请问发生了什么事情？"}
        response = client.post(f"/training/chat/{session_id}", json=payload, headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["response"] != ""
        assert "current_stage" in data
        assert isinstance(data["recommended_questions"], list)
        assert "updated_cooperation" in data
        assert "updated_risk" in data
        assert "updated_clarity" in data

    def test_chat_empty_content(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        response = client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "   "},
            headers=student_headers,
        )
        assert response.status_code == 400

    def test_chat_session_not_owned(self, client, student_headers, admin_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        response = client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "hello"},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_multiple_chat_turns(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        for i in range(5):
            response = client.post(
                f"/training/chat/{session_id}",
                json={"role": "user", "content": f"第{i + 1}轮提问：请详细说说情况。"},
                headers=student_headers,
            )
            assert response.status_code == 200

    def test_chat_returns_502_when_ai_generation_fails(self, client, student_headers, monkeypatch):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]

        def fake_generate_dialogue(db, session_id, user_message, user_id=None, **kwargs):
            return {
                "response": "(由于系统异常，对话暂时无法继续。)",
                "inner_thought": "ERROR",
                "communication_feedback": {
                    "message": "当前系统响应异常，请稍后重试。",
                },
            }

        monkeypatch.setattr(training_router, "generate_dialogue", fake_generate_dialogue)

        response = client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "请继续说明。"},
            headers=student_headers,
        )
        assert response.status_code == 502
        assert response.json()["detail"] == "当前系统响应异常，请稍后重试。"

    def test_comforting_question_lowers_high_emotion_even_when_llm_keeps_it_high(
        self,
        client,
        student_headers,
        db_session,
        monkeypatch,
    ):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        session = db_session.query(models.TrainingSession).filter_by(id=session_id).first()
        session.current_emotion = 86
        session.current_trust = 35
        runtime_state = load_runtime_state(session.revealed_info)
        runtime_state["state_snapshot"] = {"cooperation": 35, "risk": 76, "clarity": 42}
        session.revealed_info = dump_runtime_state(runtime_state)
        db_session.commit()

        monkeypatch.setattr(ai_service, "should_use_scene_conversation", lambda *args, **kwargs: False)

        def fake_chat_completion(*args, **kwargs):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "response": "我还是很急，我现在就怕他们又打起来。",
                                    "inner_thought": "还是紧张",
                                    "updated_emotion": 88,
                                    "updated_cooperation": 34,
                                    "updated_risk": 78,
                                    "updated_clarity": 42,
                                    "new_fact_revealed": None,
                                    "is_stage_completed": False,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

        monkeypatch.setattr(ai_service, "create_roleplay_json_completion", fake_chat_completion)

        response = client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "你先别急，我理解你着急，民警已经在路上，你先到安全位置，我们一步一步处理。"},
            headers=student_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_emotion"] <= 78
        assert data["updated_risk"] <= 69
        assert data["updated_cooperation"] >= 40

        client.request("DELETE", f"/training/session/{session_id}", headers=student_headers)


class TestIntakeOpening:
    def test_start_intake_session_waits_for_face_verified_opening_request(self, client, student_headers, db_session):
        student = db_session.query(models.User).filter(models.User.role == "student").first()
        db_session.query(models.TrainingSession).filter(
            models.TrainingSession.user_id == student.id,
            models.TrainingSession.scene_id == 1,
            models.TrainingSession.status == "active",
        ).update({"status": "finished"}, synchronize_session=False)
        db_session.commit()
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        detail = client.get(f"/training/session/{session_id}", headers=student_headers)
        assert detail.status_code == 200
        data = detail.json()
        assert data["scene_kind"] == "intake"
        assert data["dialogue_mode"] == "caller_first"
        assert data["dispatch_brief"] == "110 有新报警来电，等待接听。"
        assert data["first_impression"] in (None, "")
        assert data["opening_delivered"] is False
        messages = data.get("messages") or []
        assert messages == []

        opening_response = client.post(f"/training/session/{session_id}/opening", headers=student_headers)
        assert opening_response.status_code == 409
        assert opening_response.json()["detail"] == "请先完成人脸身份验证"

        db_session.add(
            models.FaceVerificationEvent(
                session_id=session_id,
                student_id=student.id,
                event_type="verify",
                status="passed",
            )
        )
        db_session.commit()

        delivered = client.post(f"/training/session/{session_id}/opening", headers=student_headers)
        assert delivered.status_code == 200
        delivered_data = delivered.json()
        assert delivered_data["opening_delivered"] is True
        assert delivered_data["messages"]
        first_message_ids = [item["id"] for item in delivered_data["messages"]]

        repeated = client.post(f"/training/session/{session_id}/opening", headers=student_headers)
        assert repeated.status_code == 200
        assert [item["id"] for item in repeated.json()["messages"]] == first_message_ids

        streamed = client.post(f"/training/session/{session_id}/opening-stream", headers=student_headers)
        assert streamed.status_code == 200
        assert "event: meta" in streamed.text
        assert "event: chunk" in streamed.text
        assert "event: done" in streamed.text

        after_stream = client.get(f"/training/session/{session_id}", headers=student_headers)
        assert [item["id"] for item in after_stream.json()["messages"]] == first_message_ids

        resumed = client.get(f"/training/session/{session_id}", headers=student_headers)
        assert resumed.status_code == 200
        assert resumed.json()["opening_delivered"] is True

    def test_intake_premature_question_feedback(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        response = client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "你电话多少？几点发生的？"},
            headers=student_headers,
        )
        assert response.status_code == 200
        feedback = response.json().get("communication_feedback") or {}
        tags = feedback.get("tags") or []
        message = str(feedback.get("message") or "")
        assert any("premature" in tag or "question_order" in tag for tag in tags) or "安全" in message or "什么事" in message


class TestGetSession:
    def test_get_session(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "你好，请说说情况。"},
            headers=student_headers,
        )
        response = client.get(f"/training/session/{session_id}", headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["status"] == "active"
        assert data["case_title"] == "邻里纠纷测试案件"
        assert data["case_type"] == "邻里纠纷"
        assert data["role_name"] == "张某"
        assert data["difficulty"] == "中等"
        assert len(data["messages"]) >= 2
        assert data["current_trust"] == data["current_cooperation"]
        assert 0 <= data["current_risk"] <= 100
        assert 0 <= data["current_clarity"] <= 100

    def test_get_session_not_owned(self, client, student_headers, admin_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        response = client.get(f"/training/session/{session_id}", headers=admin_headers)
        assert response.status_code == 404

    def test_get_session_includes_resume_guidance(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]

        response = client.get(f"/training/session/{session_id}", headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["stage_completion_requirements"], list)
        assert isinstance(data["stage_completion_satisfied"], list)
        assert isinstance(data["stage_completion_missing"], list)
        assert isinstance(data["recommended_questions"], list)
        assert isinstance(data["communication_feedback"], dict)
        assert "message" in data["communication_feedback"]

    def test_get_session_never_enables_model_backed_guidance(self, client, student_headers, monkeypatch):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        calls = []
        original = training_router.build_recommended_question_items

        def capture_guidance_call(**kwargs):
            calls.append(kwargs)
            return original(**kwargs)

        monkeypatch.setattr(training_router, "build_recommended_question_items", capture_guidance_call)
        response = client.get(f"/training/session/{session_id}", headers=student_headers)

        assert response.status_code == 200
        assert calls
        assert all(call.get("use_llm") is False for call in calls)


class TestFinishTraining:
    def test_finish_training_success(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "请问发生了什么事情？"},
            headers=student_headers,
        )
        response = client.post(f"/training/finish/{session_id}", headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_score" in data
        assert "scores" in data
        common_scores = [item for item in data["scores"] if item.get("group") == "common"]
        assessment_scores = [item for item in data["scores"] if item.get("group") == "assessment"]
        other_scores = [item for item in data["scores"] if item.get("group") not in {"common", "assessment"}]
        assert len(common_scores) == 4
        assert not other_scores
        assert all(item.get("assessment_point_id") for item in assessment_scores)
        assert sum(1 for item in data["scores"] if item.get("group") == "common") == 4
        assert len(data["scores"]) == len(common_scores) + len(assessment_scores)

    def test_finish_training_no_messages(self, client, student_headers):
        # Use student002 who has no active sessions from prior tests
        token_response = client.post("/auth/token", data={"username": "student002", "password": "123456"})
        headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
        start_response = client.post("/training/start/1", headers=headers)
        session_id = start_response.json()["id"]
        response = client.post(f"/training/finish/{session_id}", headers=headers)
        assert response.status_code == 400

    def test_finish_training_not_owned(self, client, student_headers, admin_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "你好"},
            headers=student_headers,
        )
        response = client.post(f"/training/finish/{session_id}", headers=admin_headers)
        assert response.status_code == 404


class TestReEvaluate:
    def test_re_evaluate(self, client, student_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "请问发生了什么事情？"},
            headers=student_headers,
        )
        client.post(f"/training/finish/{session_id}", headers=student_headers)
        response = client.post(f"/training/re-evaluate/{session_id}", headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_score" in data

    def test_re_evaluate_no_messages(self, client, student_headers):
        token_response = client.post("/auth/token", data={"username": "student002", "password": "123456"})
        headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
        start_response = client.post("/training/start/1", headers=headers)
        session_id = start_response.json()["id"]
        response = client.post(f"/training/re-evaluate/{session_id}", headers=headers)
        assert response.status_code == 400


class TestDeleteSession:
    def test_delete_training_session_removes_messages_and_session(self, client, student_headers, db_session):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]
        client.post(
            f"/training/chat/{session_id}",
            json={"role": "user", "content": "你好，请先说明情况。"},
            headers=student_headers,
        )

        response = client.request("DELETE", f"/training/session/{session_id}", headers=student_headers)
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

        assert db_session.query(models.TrainingSession).filter_by(id=session_id).first() is None
        assert db_session.query(models.Message).filter_by(session_id=session_id).count() == 0

    def test_delete_training_session_not_owned(self, client, student_headers, admin_headers):
        start_response = client.post("/training/start/1", headers=student_headers)
        session_id = start_response.json()["id"]

        response = client.request("DELETE", f"/training/session/{session_id}", headers=admin_headers)
        assert response.status_code == 404

    def test_delete_active_training_sessions_removes_only_current_users_active_sessions(self, client, student_headers, db_session):
        first = client.post("/training/start/1", headers=student_headers).json()["id"]
        client.post(
            f"/training/chat/{first}",
            json={"role": "user", "content": "先说一下现场情况。"},
            headers=student_headers,
        )

        other_login = client.post("/auth/token", data={"username": "student002", "password": "123456"})
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
        third = client.post("/training/start/1", headers=other_headers).json()["id"]

        response = client.request("DELETE", "/training/sessions/active", headers=student_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert data["session_ids"] == [first]

        assert db_session.query(models.TrainingSession).filter_by(id=first).first() is None
        assert db_session.query(models.TrainingSession).filter_by(id=third).first() is not None
        assert db_session.query(models.Message).filter_by(session_id=first).count() == 0


class TestStructuredTrainingFlow:
    def test_chat_response_contains_structured_fields(self, client, student_headers):
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

    def test_chat_auto_finish_triggers_evaluation(self, client, student_headers, monkeypatch):
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

    def test_action_route_success(self, client, student_headers, monkeypatch):
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
