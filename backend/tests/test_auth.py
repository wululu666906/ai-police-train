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


class TestOpsAccounts:
    def test_maintainer_login_and_list_accounts(self, client, maintainer_headers):
        response = client.post("/auth/token", data={"username": "maintainer", "password": "123456"})
        assert response.status_code == 200
        assert response.json()["role"] == "maintainer"

        response = client.get("/ops/accounts", headers=maintainer_headers)
        assert response.status_code == 200
        usernames = {item["username"] for item in response.json()}
        assert "maintainer" in usernames
        assert "admin" in usernames

    def test_ops_accounts_forbidden_for_admin_and_student(self, client, admin_headers, student_headers):
        assert client.get("/ops/accounts", headers=admin_headers).status_code == 403
        assert client.get("/ops/accounts", headers=student_headers).status_code == 403

    def test_ops_create_admin_and_student(self, client, maintainer_headers):
        admin_response = client.post(
            "/ops/accounts",
            json={"username": "ops_admin_01", "password": "admin123", "role": "admin"},
            headers=maintainer_headers,
        )
        assert admin_response.status_code == 200
        assert admin_response.json()["role"] == "admin"

        student_response = client.post(
            "/ops/accounts",
            json={"username": "ops_student_01", "password": "student123", "role": "student"},
            headers=maintainer_headers,
        )
        assert student_response.status_code == 200
        assert student_response.json()["role"] == "student"

        duplicate_response = client.post(
            "/ops/accounts",
            json={"username": "ops_student_01", "password": "student123", "role": "student"},
            headers=maintainer_headers,
        )
        assert duplicate_response.status_code == 400

    def test_ops_cannot_create_maintainer(self, client, maintainer_headers):
        response = client.post(
            "/ops/accounts",
            json={"username": "ops_maintainer_01", "password": "secret123", "role": "maintainer"},
            headers=maintainer_headers,
        )
        assert response.status_code == 400

    def test_ops_reset_password(self, client, maintainer_headers):
        create_response = client.post(
            "/ops/accounts",
            json={"username": "ops_reset_01", "password": "oldpass1", "role": "admin"},
            headers=maintainer_headers,
        )
        account_id = create_response.json()["id"]
        response = client.post(
            f"/ops/accounts/{account_id}/reset-password",
            json={"new_password": "newpass1"},
            headers=maintainer_headers,
        )
        assert response.status_code == 200
        assert client.post("/auth/token", data={"username": "ops_reset_01", "password": "oldpass1"}).status_code == 401
        assert client.post("/auth/token", data={"username": "ops_reset_01", "password": "newpass1"}).status_code == 200

    def test_ops_delete_student_cleans_training_records(self, client, maintainer_headers, db_session):
        create_response = client.post(
            "/ops/accounts",
            json={"username": "ops_delete_student", "password": "student123", "role": "student"},
            headers=maintainer_headers,
        )
        student_id = create_response.json()["id"]
        session = models.TrainingSession(
            user_id=student_id,
            scene_id=1,
            status="active",
            current_stage="test",
            current_emotion=50,
            current_trust=50,
            revealed_info="[]",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        session_id = session.id

        response = client.delete(f"/ops/accounts/{student_id}", headers=maintainer_headers)
        assert response.status_code == 200
        assert db_session.query(models.User).filter(models.User.id == student_id).first() is None
        assert db_session.query(models.TrainingSession).filter(models.TrainingSession.id == session_id).first() is None

    def test_ops_delete_admin_keeps_student_training_records(self, client, maintainer_headers, db_session):
        create_response = client.post(
            "/ops/accounts",
            json={"username": "ops_delete_admin", "password": "admin123", "role": "admin"},
            headers=maintainer_headers,
        )
        admin_id = create_response.json()["id"]
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        session = models.TrainingSession(
            user_id=student.id,
            scene_id=1,
            status="active",
            current_stage="test",
            current_emotion=50,
            current_trust=50,
            revealed_info="[]",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        response = client.delete(f"/ops/accounts/{admin_id}", headers=maintainer_headers)
        assert response.status_code == 200
        assert db_session.query(models.User).filter(models.User.id == admin_id).first() is None
        assert db_session.query(models.TrainingSession).filter(models.TrainingSession.id == session.id).first() is not None

    def test_ops_cannot_delete_current_maintainer(self, client, maintainer_headers, db_session):
        maintainer = db_session.query(models.User).filter(models.User.username == "maintainer").first()
        response = client.delete(f"/ops/accounts/{maintainer.id}", headers=maintainer_headers)
        assert response.status_code == 400

    def test_ops_import_preview_and_commit_csv(self, client, maintainer_headers):
        csv_content = (
            "username,password,role,display_name,real_name,phone,email,unit,department,bio\n"
            "ops_import_student,student123,student,导入学员,张三,13800000000,student@example.com,测试单位,训练部,备注\n"
            "ops_import_admin,admin123,admin,导入管理员,李四,13900000000,admin@example.com,测试单位,维护部,\n"
        ).encode("utf-8")
        preview = client.post(
            "/ops/accounts/import/preview",
            files={"file": ("accounts.csv", csv_content, "text/csv")},
            headers=maintainer_headers,
        )
        assert preview.status_code == 200
        data = preview.json()
        assert data["ready_count"] == 2
        assert data["error_count"] == 0

        commit = client.post(
            "/ops/accounts/import/commit",
            json={"accounts": data["items"]},
            headers=maintainer_headers,
        )
        assert commit.status_code == 200
        assert commit.json()["created_count"] == 2
        assert client.post("/auth/token", data={"username": "ops_import_student", "password": "student123"}).status_code == 200
        assert client.post("/auth/token", data={"username": "ops_import_admin", "password": "admin123"}).status_code == 200

    def test_ops_import_preview_can_force_target_role(self, client, maintainer_headers):
        csv_content = (
            "账号,初始密码,角色\n"
            "ops_force_role,student123,student\n"
        ).encode("utf-8")
        response = client.post(
            "/ops/accounts/import/preview",
            data={"target_role": "admin"},
            files={"file": ("accounts.csv", csv_content, "text/csv")},
            headers=maintainer_headers,
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["role"] == "admin"

    def test_ops_batch_delete_accounts(self, client, maintainer_headers, db_session):
        admin_response = client.post(
            "/ops/accounts",
            json={"username": "ops_batch_delete_admin", "password": "admin123", "role": "admin"},
            headers=maintainer_headers,
        )
        student_response = client.post(
            "/ops/accounts",
            json={"username": "ops_batch_delete_student", "password": "student123", "role": "student"},
            headers=maintainer_headers,
        )
        payload = {"account_ids": [admin_response.json()["id"], student_response.json()["id"]]}
        response = client.post("/ops/accounts/batch-delete", json=payload, headers=maintainer_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 2
        assert db_session.query(models.User).filter(models.User.username == "ops_batch_delete_admin").first() is None
        assert db_session.query(models.User).filter(models.User.username == "ops_batch_delete_student").first() is None

    def test_ops_import_preview_marks_duplicates_and_overrides_file_roles(self, client, maintainer_headers):
        csv_content = (
            "账号,初始密码,角色\n"
            "admin,123456,admin\n"
            "ops_bad_role,123456,maintainer\n"
            "ops_duplicate,123456,student\n"
            "ops_duplicate,123456,student\n"
        ).encode("utf-8")
        response = client.post(
            "/ops/accounts/import/preview",
            files={"file": ("accounts.csv", csv_content, "text/csv")},
            headers=maintainer_headers,
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert response.json()["ready_count"] == 2
        assert "账号已存在" in items[0]["errors"]
        assert items[1]["status"] == "ready"
        assert items[1]["role"] == "student"
        assert "文件内账号重复" in items[3]["errors"]

    def test_ops_import_preview_rejects_invalid_target_role(self, client, maintainer_headers):
        csv_content = (
            "账号,初始密码\n"
            "ops_invalid_target_role,123456\n"
        ).encode("utf-8")
        response = client.post(
            "/ops/accounts/import/preview",
            data={"target_role": "maintainer"},
            files={"file": ("accounts.csv", csv_content, "text/csv")},
            headers=maintainer_headers,
        )
        assert response.status_code == 400

    def test_ops_import_forbidden_for_admin(self, client, admin_headers):
        response = client.post(
            "/ops/accounts/import/preview",
            files={"file": ("accounts.csv", b"username,password\nx,123456\n", "text/csv")},
            headers=admin_headers,
        )
        assert response.status_code == 403

    def test_ops_usage_list_and_detail(self, client, maintainer_headers):
        response = client.get("/ops/accounts/usage", headers=maintainer_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data
        first = data[0]
        assert "stats" in first
        assert "recent_activities" in first

        detail = client.get(f"/ops/accounts/{first['id']}/usage", headers=maintainer_headers)
        assert detail.status_code == 200
        detail_data = detail.json()
        assert "activities" in detail_data

    def test_ops_usage_forbidden_for_admin_and_student(self, client, admin_headers, student_headers):
        assert client.get("/ops/accounts/usage", headers=admin_headers).status_code == 403
        assert client.get("/ops/accounts/usage", headers=student_headers).status_code == 403


class TestTokenRoleVerification:
    def test_token_contains_correct_role(self, admin_token, student_token):
        from jose import jwt as pyjwt

        admin_payload = pyjwt.decode(admin_token, "dummy", options={"verify_signature": False})
        student_payload = pyjwt.decode(student_token, "dummy", options={"verify_signature": False})
        assert admin_payload["role"] == "admin"
        assert student_payload["role"] == "student"
