import json

import models


def ensure_unlock_case(db_session):
    case = db_session.query(models.Case).filter(
        models.Case.title == "视频实训解锁专项案件"
    ).first()
    if case:
        return case

    case = models.Case(
        title="视频实训解锁专项案件",
        case_type="专项测试",
        background="用于验证教学视频是否会在交互实训完成后解锁。",
        original_content="用于验证教学视频是否会在交互实训完成后解锁。",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def ensure_video_pair(db_session):
    case = ensure_unlock_case(db_session)
    admin = db_session.query(models.User).filter(models.User.username == "admin").first()

    interactive = db_session.query(models.TrainingVideo).filter(
        models.TrainingVideo.title == "教学解锁-交互实训",
        models.TrainingVideo.case_id == case.id,
    ).first()
    if not interactive:
        interactive = models.TrainingVideo(
            title="教学解锁-交互实训",
            description="用于验证教学素材解锁前置条件的交互视频。",
            video_type="interactive",
            file_path="unlock-interactive.mp4",
            duration=120,
            case_id=case.id,
            tags=json.dumps(["解锁", "交互"], ensure_ascii=False),
            status="published",
            uploaded_by=admin.id if admin else None,
        )
        db_session.add(interactive)
        db_session.flush()

    teaching = db_session.query(models.TrainingVideo).filter(
        models.TrainingVideo.title == "教学解锁-教学素材",
        models.TrainingVideo.case_id == case.id,
    ).first()
    if not teaching:
        teaching = models.TrainingVideo(
            title="教学解锁-教学素材",
            description="用于验证教学素材是否会被正确锁定。",
            video_type="teaching",
            file_path="unlock-teaching.mp4",
            duration=90,
            case_id=case.id,
            tags=json.dumps(["解锁", "教学"], ensure_ascii=False),
            status="published",
            uploaded_by=admin.id if admin else None,
        )
        db_session.add(teaching)
        db_session.flush()

    db_session.commit()
    db_session.refresh(interactive)
    db_session.refresh(teaching)
    return interactive, teaching


def clear_user_sessions(db_session, user_id: int, video_ids: list[int]):
    sessions = db_session.query(models.VideoTrainingSession).filter(
        models.VideoTrainingSession.user_id == user_id,
        models.VideoTrainingSession.video_id.in_(video_ids),
    ).all()
    for session in sessions:
        db_session.delete(session)
    db_session.commit()


def test_teaching_video_stays_locked_until_related_interactive_training_is_finished(
    client,
    db_session,
    student_headers,
):
    student = db_session.query(models.User).filter(models.User.username == "student001").first()
    interactive, teaching = ensure_video_pair(db_session)
    clear_user_sessions(db_session, student.id, [interactive.id, teaching.id])

    hall_response = client.get("/videos/student/hall", headers=student_headers)
    assert hall_response.status_code == 200
    hall_items = hall_response.json()
    teaching_item = next(item for item in hall_items if item["id"] == teaching.id)
    assert teaching_item["teaching_unlocked"] is False
    assert teaching_item["video_url"] is None
    assert teaching_item["lock_reason"]

    detail_locked = client.get(f"/videos/{teaching.id}", headers=student_headers)
    assert detail_locked.status_code == 403

    finished_session = models.VideoTrainingSession(
        user_id=student.id,
        video_id=interactive.id,
        mode="practice",
        status="finished",
        current_node_index=0,
        total_score=10,
        full_score=10,
    )
    db_session.add(finished_session)
    db_session.commit()

    hall_after = client.get("/videos/student/hall", headers=student_headers)
    assert hall_after.status_code == 200
    unlocked_item = next(item for item in hall_after.json() if item["id"] == teaching.id)
    assert unlocked_item["teaching_unlocked"] is True
    assert unlocked_item["video_url"]
    assert unlocked_item["lock_reason"] is None

    detail_unlocked = client.get(f"/videos/{teaching.id}", headers=student_headers)
    assert detail_unlocked.status_code == 200
    assert detail_unlocked.json()["video_url"]
