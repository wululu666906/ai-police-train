from datetime import datetime, timedelta

import models


def _reset_student_sessions(db_session, username: str):
    student = db_session.query(models.User).filter(models.User.username == username).first()
    session_ids = [
        row.id
        for row in db_session.query(models.TrainingSession.id)
        .filter(models.TrainingSession.user_id == student.id)
        .all()
    ]
    if session_ids:
        db_session.query(models.AssignmentSubmission).filter(
            models.AssignmentSubmission.training_session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        db_session.query(models.Message).filter(models.Message.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
        db_session.query(models.TrainingSession).filter(models.TrainingSession.id.in_(session_ids)).delete(
            synchronize_session=False
        )
    db_session.commit()
    return student


def test_class_assignment_training_submission_flow(client, admin_headers, student_headers, db_session):
    student = _reset_student_sessions(db_session, "student001")

    class_response = client.post(
        "/classes",
        json={"name": "测试训练班", "description": "用于作业流转测试"},
        headers=admin_headers,
    )
    assert class_response.status_code == 200
    classroom = class_response.json()

    add_response = client.post(
        f"/classes/{classroom['id']}/students",
        json={"usernames": [student.username]},
        headers=admin_headers,
    )
    assert add_response.status_code == 200
    assert add_response.json()["matched_count"] == 1

    due_at = (datetime.utcnow() + timedelta(days=1)).isoformat()
    assignment_response = client.post(
        f"/classes/{classroom['id']}/assignments",
        json={
            "title": "接警训练作业",
            "case_ids": [1],
            "instructions": "完成接警场景并提交评估。",
            "scoring_rule": "系统默认评分。",
            "due_at": due_at,
        },
        headers=admin_headers,
    )
    assert assignment_response.status_code == 200
    assignment = assignment_response.json()

    student_assignments = client.get("/classes/student/assignments", headers=student_headers)
    assert student_assignments.status_code == 200
    assignment_ids = [item["id"] for item in student_assignments.json()]
    assert assignment["id"] in assignment_ids

    start_response = client.post(
        f"/training/start/1?assignment_id={assignment['id']}",
        headers=student_headers,
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["id"]

    submission = (
        db_session.query(models.AssignmentSubmission)
        .filter(
            models.AssignmentSubmission.assignment_id == assignment["id"],
            models.AssignmentSubmission.user_id == student.id,
            models.AssignmentSubmission.training_session_id == session_id,
        )
        .first()
    )
    assert submission is not None
    assert submission.status == "in_progress"

    chat_response = client.post(
        f"/training/chat/{session_id}",
        json={"role": "user", "content": "您好，我是接警员，请问现在具体位置在哪里？"},
        headers=student_headers,
    )
    assert chat_response.status_code == 200

    finish_response = client.post(f"/training/finish/{session_id}", headers=student_headers)
    assert finish_response.status_code == 200

    db_session.refresh(submission)
    assert submission.status == "submitted"
    assert submission.submitted_at is not None
    assert submission.evaluation_result

    review_response = client.get(
        f"/classes/{classroom['id']}/assignments/{assignment['id']}/review",
        headers=admin_headers,
    )
    assert review_response.status_code == 200
    review = review_response.json()
    row = next(item for item in review["rows"] if item["student"]["id"] == student.id)
    assert row["status"] == "submitted"
    assert row["completed_count"] == 1

    detail_response = client.get(
        f"/classes/student/assignments/{assignment['id']}",
        headers=student_headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "completed"
    assert detail["cases"][0]["status"] == "completed"
