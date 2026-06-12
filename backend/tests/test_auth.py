import json
from datetime import datetime, timedelta

import models
import pytest


class TestLogin:
    def test_login_success_admin(self, client):
        response = client.post("/auth/token", data={"username": "admin", "password": "123456"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin"
        assert data["role"] == "admin"

    def test_login_success_student(self, client):
        response = client.post("/auth/token", data={"username": "student001", "password": "123456"})
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "student001"
        assert data["role"] == "student"

    def test_login_invalid_password(self, client):
        response = client.post("/auth/token", data={"username": "admin", "password": "wrong_password"})
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        response = client.post("/auth/token", data={"username": "no_one", "password": "123456"})
        assert response.status_code == 401

    def test_login_returns_expires_in(self, client):
        response = client.post("/auth/token", data={"username": "admin", "password": "123456"})
        data = response.json()
        assert data["expires_in"] > 0
        assert isinstance(data["expires_in"], int)


class TestRegister:
    def test_register_as_admin(self, client, admin_headers):
        response = client.post(
            "/auth/register",
            json={"username": "new_user_01", "password": "test123", "role": "student"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "new_user_01"
        assert data["role"] == "student"

    def test_register_duplicate_username(self, client, admin_headers):
        client.post(
            "/auth/register",
            json={"username": "dup_user", "password": "test123", "role": "student"},
            headers=admin_headers,
        )
        response = client.post(
            "/auth/register",
            json={"username": "dup_user", "password": "test123", "role": "student"},
            headers=admin_headers,
        )
        assert response.status_code == 400

    def test_register_as_student_should_fail(self, client, student_headers):
        response = client.post(
            "/auth/register",
            json={"username": "unauth_user", "password": "test123", "role": "student"},
            headers=student_headers,
        )
        assert response.status_code == 403


class TestListStudents:
    def test_list_students_as_admin(self, client, admin_headers):
        response = client.get("/auth/students", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        assert all(item["role"] == "student" for item in data)

    def test_list_students_as_student_should_fail(self, client, student_headers):
        response = client.get("/auth/students", headers=student_headers)
        assert response.status_code == 403

    def test_get_student_profile_as_admin(self, client, admin_headers, db_session):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        db_session.query(models.Message).filter(models.Message.session_id.in_(
            db_session.query(models.TrainingSession.id).filter(models.TrainingSession.user_id == student.id)
        )).delete(synchronize_session=False)
        db_session.query(models.TrainingSession).filter(models.TrainingSession.user_id == student.id).delete(
            synchronize_session=False
        )
        db_session.commit()

        base_time = datetime.utcnow() - timedelta(days=6)
        payloads = [
            (72, ["关键信息遗漏"], [18, 16, 14, 13, 11]),
            (58, ["情绪安抚不足", "关键信息遗漏"], [14, 12, 10, 8, 14]),
            (81, ["流程收束不足"], [20, 17, 16, 14, 14]),
            (64, ["关键信息遗漏"], [16, 13, 12, 10, 13]),
            (67, ["风险识别不足"], [17, 15, 11, 12, 12]),
            (86, ["关键信息遗漏"], [21, 18, 17, 15, 15]),
        ]
        dimensions = ["沟通表达", "流程规范", "风险判断", "情绪控制", "信息获取"]
        full_scores = [25, 25, 20, 15, 15]

        for index, (total_score, missing_items, score_values) in enumerate(payloads):
            db_session.add(
                models.TrainingSession(
                    user_id=student.id,
                    scene_id=1,
                    status="finished",
                    current_stage="完成",
                    current_emotion=60,
                    current_trust=60,
                    revealed_info="[]",
                    evaluation_result=json.dumps(
                        {
                            "total_score": total_score,
                            "scores": [
                                {
                                    "dimension": dimensions[item_index],
                                    "score": score_values[item_index],
                                    "full_score": full_scores[item_index],
                                    "reason": "",
                                }
                                for item_index in range(len(dimensions))
                            ],
                            "evaluation_meta": {
                                "stage_gap_summary": {
                                    "missing": missing_items,
                                }
                            },
                        },
                        ensure_ascii=False,
                    ),
                    created_at=base_time + timedelta(days=index),
                )
            )
        db_session.commit()

        response = client.get(f"/auth/students/{student.id}/profile", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["student"]["username"] == "student001"
        assert data["summary"]["total_sessions"] == 6
        assert data["summary"]["finished_sessions"] == 6
        assert len(data["dimensions"]) == 5
        assert data["high_frequency_issues"][0]["label"] == "关键信息遗漏"
        assert len(data["suggestions"]) >= 1
        assert len(data["trend_points"]) == 6

    def test_get_student_profile_as_student_should_fail(self, client, student_headers):
        response = client.get("/auth/students/2/profile", headers=student_headers)
        assert response.status_code == 403


class TestBatchCreateStudents:
    def test_batch_create_with_template(self, client, admin_headers):
        payload = {
            "template": "test_student_xx",
            "start_no": 1,
            "end_no": 5,
            "password": "batch123",
        }
        response = client.post("/auth/students/batch", json=payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 5
        assert "test_student_01" in data["created_usernames"]
        assert "test_student_05" in data["created_usernames"]

    def test_batch_create_duplicate(self, client, admin_headers):
        payload = {
            "template": "dup_student_x",
            "start_no": 1,
            "end_no": 1,
            "password": "batch123",
        }
        client.post("/auth/students/batch", json=payload, headers=admin_headers)
        response = client.post("/auth/students/batch", json=payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 0
        assert data["skipped_count"] == 1

    def test_batch_create_no_password(self, client, admin_headers):
        payload = {"template": "test_xx", "start_no": 1, "end_no": 3, "password": ""}
        response = client.post("/auth/students/batch", json=payload, headers=admin_headers)
        assert response.status_code == 400

    def test_batch_create_invalid_template(self, client, admin_headers):
        payload = {"template": "no_placeholder", "start_no": 1, "end_no": 3, "password": "test"}
        response = client.post("/auth/students/batch", json=payload, headers=admin_headers)
        assert response.status_code == 400

    def test_batch_create_start_gt_end(self, client, admin_headers):
        payload = {"template": "test_xx", "start_no": 5, "end_no": 3, "password": "test"}
        response = client.post("/auth/students/batch", json=payload, headers=admin_headers)
        assert response.status_code == 400


class TestBatchDeleteStudents:
    def test_batch_delete(self, client, admin_headers):
        create_payload = {
            "template": "del_test_xx",
            "start_no": 1,
            "end_no": 3,
            "password": "delete123",
        }
        client.post("/auth/students/batch", json=create_payload, headers=admin_headers)

        delete_payload = {"template": "del_test_xx", "start_no": 1, "end_no": 3}
        response = client.request(
            "DELETE", "/auth/students/batch", json=delete_payload, headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 3

    def test_batch_delete_nonexistent(self, client, admin_headers):
        payload = {"template": "nonexist_xx", "start_no": 99, "end_no": 99}
        response = client.request("DELETE", "/auth/students/batch", json=payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 0


class TestImportStudents:
    def test_import_students(self, client, admin_headers):
        payload = {
            "usernames": ["import_user_01", "import_user_02", "import_user_03"],
            "password": "import123",
        }
        response = client.post("/auth/students/import", json=payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 3

    def test_import_duplicate_skip(self, client, admin_headers):
        payload = {"usernames": ["import_dup_01"], "password": "import123"}
        client.post("/auth/students/import", json=payload, headers=admin_headers)
        response = client.post("/auth/students/import", json=payload, headers=admin_headers)
        data = response.json()
        assert data["skipped_count"] == 1

    def test_import_empty_usernames(self, client, admin_headers):
        payload = {"usernames": [], "password": "test"}
        response = client.post("/auth/students/import", json=payload, headers=admin_headers)
        assert response.status_code == 400


class TestAuthGuard:
    def test_unauthorized_access(self, client):
        response = client.get("/auth/students")
        assert response.status_code == 401

    def test_invalid_token(self, client):
        response = client.get("/auth/students", headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == 401


class TestTokenRoleVerification:
    def test_token_contains_correct_role(self, admin_token, student_token):
        from jose import jwt as pyjwt

        admin_payload = pyjwt.decode(admin_token, "dummy", options={"verify_signature": False})
        student_payload = pyjwt.decode(student_token, "dummy", options={"verify_signature": False})
        assert admin_payload["role"] == "admin"
        assert student_payload["role"] == "student"
