import models
from routers.auth import hash_password


def ensure_student(db_session, username: str, password: str = "123456") -> models.User:
    user = db_session.query(models.User).filter(models.User.username == username).first()
    if user:
        return user

    user = models.User(username=username, hashed_password=hash_password(password), role="student")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def reset_student_history(db_session, user: models.User) -> None:
    session_ids = [
        item[0]
        for item in db_session.query(models.TrainingSession.id)
        .filter(models.TrainingSession.user_id == user.id)
        .all()
    ]
    if session_ids:
        db_session.query(models.Message).filter(models.Message.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
        db_session.query(models.TrainingSession).filter(models.TrainingSession.id.in_(session_ids)).delete(
            synchronize_session=False
        )
        db_session.commit()


def login_student(client, username: str, password: str = "123456") -> dict[str, str]:
    response = client.post("/auth/token", data={"username": username, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestStudentHistory:
    def test_history_supports_status_filter_and_summary_counts(self, client, db_session):
        student = ensure_student(db_session, "history_status_student")
        reset_student_history(db_session, student)
        headers = login_student(client, student.username)

        finished_session_id = client.post("/training/start/1", headers=headers).json()["id"]
        client.post(
            f"/training/chat/{finished_session_id}",
            json={"role": "user", "content": "请说明事情经过。"},
            headers=headers,
        )
        client.post(f"/training/finish/{finished_session_id}", headers=headers)

        active_session_id = client.post("/training/start/1", headers=headers).json()["id"]
        client.post(
            f"/training/chat/{active_session_id}",
            json={"role": "user", "content": "继续补充一下现场情况。"},
            headers=headers,
        )

        active_response = client.get("/student/history?status=active", headers=headers)
        assert active_response.status_code == 200
        active_payload = active_response.json()
        assert active_payload["status_filter"] == "active"
        assert active_payload["visible_total_count"] == 2
        assert active_payload["active_count"] == 1
        assert active_payload["finished_count"] == 1
        assert active_payload["total"] == 1
        assert len(active_payload["items"]) == 1
        assert active_payload["items"][0]["status"] == "active"

        finished_response = client.get("/student/history?status=finished", headers=headers)
        assert finished_response.status_code == 200
        finished_payload = finished_response.json()
        assert finished_payload["status_filter"] == "finished"
        assert finished_payload["total"] == 1
        assert len(finished_payload["items"]) == 1
        assert finished_payload["items"][0]["status"] == "finished"
        assert "final_cooperation" in finished_payload["items"][0]
        assert "final_risk" in finished_payload["items"][0]
        assert "final_clarity" in finished_payload["items"][0]

    def test_history_hides_empty_sessions_by_default_and_can_include_them(self, client, db_session):
        student = ensure_student(db_session, "history_empty_student")
        reset_student_history(db_session, student)
        headers = login_student(client, student.username)

        client.post("/training/start/1", headers=headers)

        hidden_response = client.get("/student/history", headers=headers)
        assert hidden_response.status_code == 200
        hidden_payload = hidden_response.json()
        assert hidden_payload["total"] == 0
        assert hidden_payload["visible_total_count"] == 0
        assert hidden_payload["hidden_empty_count"] == 1
        assert hidden_payload["empty_session_count"] == 1

        visible_response = client.get("/student/history?include_empty=true", headers=headers)
        assert visible_response.status_code == 200
        visible_payload = visible_response.json()
        assert visible_payload["total"] == 1
        assert visible_payload["hidden_empty_count"] == 0
        assert visible_payload["items"][0]["is_empty_session"] is True

    def test_history_rejects_unknown_status_filter(self, client, student_headers):
        response = client.get("/student/history?status=paused", headers=student_headers)
        assert response.status_code == 400
