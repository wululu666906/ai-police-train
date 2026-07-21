import io
import json

import models


def ensure_interactive_video(db_session, title: str = "视频实训测试用例") -> models.TrainingVideo:
    video = db_session.query(models.TrainingVideo).filter(models.TrainingVideo.title == title).first()
    if video:
        return video

    admin = db_session.query(models.User).filter(models.User.username == "admin").first()
    case = db_session.query(models.Case).first()

    video = models.TrainingVideo(
        title=title,
        description="用于视频实训接口测试",
        video_type="interactive",
        file_path="test-video.mp4",
        duration=180,
        case_id=case.id if case else None,
        tags=json.dumps(["测试"], ensure_ascii=False),
        briefing="测试简报",
        status="published",
        uploaded_by=admin.id if admin else None,
    )
    db_session.add(video)
    db_session.flush()

    nodes = [
        models.VideoNode(
            video_id=video.id,
            node_index=0,
            title="节点一",
            trigger_time=15,
            node_type="action",
            prompt_content=json.dumps({"instruction": "请出示证件"}, ensure_ascii=False),
            required_keywords=json.dumps(["请配合"], ensure_ascii=False),
            score_weight=10,
        ),
        models.VideoNode(
            video_id=video.id,
            node_index=1,
            title="节点二",
            trigger_time=45,
            node_type="judge",
            node_config=json.dumps({"question": "该做法是否规范", "correct_answer": True}, ensure_ascii=False),
            score_weight=10,
        ),
        models.VideoNode(
            video_id=video.id,
            node_index=2,
            title="节点三",
            trigger_time=90,
            node_type="choice",
            node_config=json.dumps({"question": "下一步怎么做", "options": ["A", "B"], "correct_index": 0}, ensure_ascii=False),
            score_weight=10,
        ),
    ]
    db_session.add_all(nodes)
    db_session.commit()
    db_session.refresh(video)
    return video


def reset_video_training_sessions(db_session, user_id: int, video_id: int) -> None:
    sessions = (
        db_session.query(models.VideoTrainingSession)
        .filter(
            models.VideoTrainingSession.user_id == user_id,
            models.VideoTrainingSession.video_id == video_id,
        )
        .all()
    )
    for session in sessions:
        db_session.delete(session)
    db_session.commit()


class TestVideoTraining:
    def test_start_resume_returns_node_total_and_node_results(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训恢复测试")
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        start_payload = start_response.json()
        assert start_payload["resumed"] is False
        assert start_payload["node_total"] == 3
        assert start_payload["node_results"] == []

        first_node = video.nodes[0]
        submit_response = client.post(
            f"/video-training/session/{start_payload['id']}/node/submit",
            json={
                "node_id": first_node.id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "请配合检查",
            },
            headers=student_headers,
        )
        assert submit_response.status_code == 200
        assert submit_response.json()["result"] == "pass"

        resume_response = client.post(f"/video-training/start/{video.id}", headers=student_headers)
        assert resume_response.status_code == 200
        resume_payload = resume_response.json()
        assert resume_payload["resumed"] is True
        assert resume_payload["id"] == start_payload["id"]
        assert resume_payload["node_total"] == 3
        assert len(resume_payload["node_results"]) == 1
        assert resume_payload["node_results"][0]["node_index"] == 0
        assert resume_payload["node_results"][0]["result"] == "pass"

    def test_history_and_admin_sessions_include_node_total(self, client, db_session, student_headers, admin_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训进度测试")
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200

        history_response = client.get("/video-training/history", headers=student_headers)
        assert history_response.status_code == 200
        history_items = history_response.json()
        history_item = next(item for item in history_items if item["video_id"] == video.id)
        assert history_item["node_total"] == 3

        admin_response = client.get(
            f"/video-training/admin/sessions?video_id={video.id}",
            headers=admin_headers,
        )
        assert admin_response.status_code == 200
        admin_items = admin_response.json()["items"]
        admin_item = next(item for item in admin_items if item["video_id"] == video.id and item["user_id"] == student.id)
        assert admin_item["node_total"] == 3

    def test_backend_ignores_legacy_gesture_result_after_multimodal_removal(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训动作校验")
        video.nodes[0].required_gesture = "salute"
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]
        first_node = video.nodes[0]

        response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": first_node.id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "请配合检查",
                "answer_data": {
                    "gesture_result": {
                        "required_gesture": "salute",
                        "matched": False,
                        "confidence": 0.12,
                    }
                },
            },
            headers=student_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["result"] == "pass"
        assert "gesture_mismatch" not in payload["feedback"]["reasons"]

        session_detail = client.get(f"/video-training/session/{session_id}", headers=student_headers)
        assert session_detail.status_code == 200
        assert session_detail.json()["current_node_index"] == 1

    def test_backend_supports_either_pass_rule_for_gesture_and_speech(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训联合判定")
        video.nodes[0].required_gesture = "salute"
        video.nodes[0].required_keywords = json.dumps(["请配合"], ensure_ascii=False)
        video.nodes[0].node_config = json.dumps({
            "pass_rule": {"mode": "either"},
            "speech_rule": {"match_mode": "any", "min_count": 1, "min_length": 0},
        }, ensure_ascii=False)
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]
        first_node = video.nodes[0]

        response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": first_node.id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "请配合检查",
                "answer_data": {
                    "gesture_result": {
                        "required_gesture": "salute",
                        "matched": False,
                        "confidence": 0.12,
                        "streak": 0,
                    },
                    "speech_analysis": {
                        "keyword_hits": ["请配合"],
                        "pass_rule_mode": "either",
                    },
                },
            },
            headers=student_headers,
        )
        assert response.status_code == 200
        assert response.json()["result"] == "pass"

    def test_backend_rejects_manual_prop_node_when_virtual_prop_not_taken(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训道具校验")
        video.nodes[0].prop_mode = "manual"
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]
        first_node = video.nodes[0]

        response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": first_node.id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "请配合检查",
                "answer_data": {
                    "prop_interaction": {
                        "mode": "manual",
                        "ready": False,
                    },
                },
            },
            headers=student_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["result"] == "fail"
        assert "prop_missed" in payload["feedback"]["reasons"]

    def test_backend_cv_endpoint_returns_reserved_stub(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训视觉接口")
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        response = client.post(
            "/video-training/vision/evaluate",
            json={"session_id": session_id, "node_id": video.nodes[0].id, "mode": "reference_face"},
            headers=student_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is False
        assert payload["status"] == "not_configured"

    def test_backend_validates_judge_answer_even_if_frontend_is_bypassed(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训判断题校验")
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]
        judge_node = video.nodes[1]

        response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": judge_node.id,
                "node_index": 1,
                "action": "pass",
                "retry_count": 0,
                "answer_data": {"answer": False},
            },
            headers=student_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["result"] == "fail"
        assert "judge_incorrect" in payload["feedback"]["reasons"]

    def test_report_and_admin_analytics_include_failure_reasons_and_violations(
        self, client, db_session, student_headers, admin_headers
    ):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训统计分析")
        video.nodes[0].required_keywords = json.dumps(["required-token"], ensure_ascii=False)
        video.nodes[0].node_config = json.dumps({
            "pass_rule": {"mode": "all"},
            "speech_rule": {"match_mode": "any", "min_count": 1, "min_length": 0},
        }, ensure_ascii=False)
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        violation_response = client.post(
            f"/video-training/session/{session_id}/violation",
            json={"type": "tab_switch", "detail": "切屏"},
            headers=student_headers,
        )
        assert violation_response.status_code == 200
        assert violation_response.json()["violation_count"] == 1

        fail_response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": video.nodes[0].id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "missing keyword",
                "answer_data": {},
            },
            headers=student_headers,
        )
        assert fail_response.status_code == 200
        assert fail_response.json()["result"] == "fail"

        finish_response = client.post(f"/video-training/session/{session_id}/finish", headers=student_headers)
        assert finish_response.status_code == 200
        report_payload = finish_response.json()
        assert report_payload["violation_count"] == 1
        assert report_payload["failure_reason_summary"]["keyword_mismatch"] == 1
        assert report_payload["node_summaries"][0]["failure_reasons"] == ["keyword_mismatch"]
        assert "artifacts" in report_payload

        analytics_response = client.get(
            f"/video-training/admin/analytics?video_id={video.id}",
            headers=admin_headers,
        )
        assert analytics_response.status_code == 200
        analytics_payload = analytics_response.json()
        assert analytics_payload["total_violation_count"] == 1
        assert analytics_payload["failure_reason_summary"][0]["reason"] == "keyword_mismatch"
        assert analytics_payload["node_failure_summary"][0]["node_id"] == video.nodes[0].id
        assert isinstance(report_payload["dimension_scores"], list)
        assert "weakness_summary" in report_payload
        assert isinstance(report_payload["common_reviews"], list)
        assert report_payload["common_reviews"][0]["dimension"]
        assert isinstance(report_payload["assessment_check_results"], list)
        assert report_payload["assessment_check_results"][0]["full_score"] >= 1
        assert report_payload["assessment_check_results"][0]["reason"]
        assert report_payload["summary"]
        assert report_payload["grade_level"]
        assert report_payload["evaluation_meta"]["assessment_completion"]["total_count"] == len(
            report_payload["assessment_check_results"]
        )

    def test_session_artifact_upload_list_and_replace(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训练音视频留痕")
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=practice", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        first_upload = client.post(
            f"/video-training/session/{session_id}/artifacts/upload",
            headers=student_headers,
            files={"artifact_file": ("recording.webm", io.BytesIO(b"first-recording"), "video/webm;codecs=vp9")},
            data={"artifact_type": "camera_recording", "duration_seconds": "12"},
        )
        assert first_upload.status_code == 200
        first_payload = first_upload.json()
        assert first_payload["artifact_type"] == "camera_recording"
        assert first_payload["mime_type"] == "video/webm"
        assert first_payload["file_size"] == len(b"first-recording")
        assert first_payload["duration_seconds"] == 12
        assert first_payload["file_url"].startswith("/static/session_media/")

        list_response = client.get(f"/video-training/session/{session_id}/artifacts", headers=student_headers)
        assert list_response.status_code == 200
        listed_items = list_response.json()["items"]
        assert len(listed_items) == 1
        assert listed_items[0]["id"] == first_payload["id"]

        second_upload = client.post(
            f"/video-training/session/{session_id}/artifacts/upload",
            headers=student_headers,
            files={"artifact_file": ("recording.webm", io.BytesIO(b"second-recording"), "video/webm")},
            data={"artifact_type": "camera_recording"},
        )
        assert second_upload.status_code == 200
        second_payload = second_upload.json()
        assert second_payload["id"] != first_payload["id"]

        list_after_replace = client.get(f"/video-training/session/{session_id}/artifacts", headers=student_headers)
        assert list_after_replace.status_code == 200
        replaced_items = list_after_replace.json()["items"]
        assert len(replaced_items) == 1
        assert replaced_items[0]["id"] == second_payload["id"]

        history_response = client.get("/video-training/history", headers=student_headers)
        assert history_response.status_code == 200
        history_item = next(item for item in history_response.json() if item["id"] == session_id)
        assert len(history_item["artifacts"]) == 1
        assert history_item["artifacts"][0]["id"] == second_payload["id"]

    def test_admin_can_review_and_override_ai_result(self, client, db_session, student_headers, admin_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训人工复核")
        video.nodes[0].required_gesture = "salute"
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        fail_response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": video.nodes[0].id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "请配合检查",
                "answer_data": {
                    "gesture_result": {
                        "required_gesture": "salute",
                        "matched": False,
                    }
                },
            },
            headers=student_headers,
        )
        assert fail_response.status_code == 200
        node_result_id = fail_response.json()["node_result"]["id"]

        review_response = client.post(
            f"/video-training/admin/node-results/{node_result_id}/review",
            json={
                "result": "pass",
                "score_earned": 8,
                "review_note": "人工复核后确认动作有效，保留 2 分扣分。",
            },
            headers=admin_headers,
        )
        assert review_response.status_code == 200
        review_payload = review_response.json()
        assert review_payload["node_result"]["result"] == "pass"
        assert review_payload["node_result"]["score_earned"] == 8
        assert review_payload["node_result"]["score_deducted"] == 2
        assert review_payload["node_result"]["manual_review"]["reviewer_username"] == "admin"
        assert review_payload["node_result"]["failure_reasons"] == []
        assert review_payload["session_total_score"] == 8

        report_response = client.get(
            f"/video-training/admin/sessions/{session_id}/report",
            headers=admin_headers,
        )
        assert report_response.status_code == 200
        report_payload = report_response.json()
        assert report_payload["total_score"] == 8
        assert report_payload["failure_reason_summary"] == {}
        assert report_payload["node_summaries"][0]["manual_review"]["review_note"] == "人工复核后确认动作有效，保留 2 分扣分。"
        assert report_payload["node_summaries"][0]["manual_review"]["overridden"] is True

        sessions_response = client.get(
            f"/video-training/admin/sessions?video_id={video.id}&reviewed_only=true",
            headers=admin_headers,
        )
        assert sessions_response.status_code == 200
        assert sessions_response.json()["total"] >= 1

        overrides_response = client.get(
            f"/video-training/admin/sessions?video_id={video.id}&override_only=true",
            headers=admin_headers,
        )
        assert overrides_response.status_code == 200
        assert overrides_response.json()["total"] >= 1

        reviews_response = client.get(
            f"/video-training/admin/reviews?video_id={video.id}&override_only=true",
            headers=admin_headers,
        )
        assert reviews_response.status_code == 200
        review_items = reviews_response.json()["items"]
        assert review_items[0]["node_result_id"] == node_result_id
        assert review_items[0]["overridden"] is True
        assert review_items[0]["reviewer_username"] == "admin"

    def test_practice_mode_uses_lighter_retry_penalty_than_exam_mode(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训模式差异")
        reset_video_training_sessions(db_session, student.id, video.id)

        practice_start = client.post(f"/video-training/start/{video.id}?mode=practice", headers=student_headers)
        assert practice_start.status_code == 200
        practice_session_id = practice_start.json()["id"]

        practice_submit = client.post(
            f"/video-training/session/{practice_session_id}/node/submit",
            json={
                "node_id": video.nodes[0].id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 2,
                "speech_transcript": "请配合检查",
            },
            headers=student_headers,
        )
        assert practice_submit.status_code == 200
        assert practice_submit.json()["result"] == "pass"
        assert practice_submit.json()["score_deducted"] == 5

        reset_video_training_sessions(db_session, student.id, video.id)
        exam_start = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert exam_start.status_code == 200
        exam_session_id = exam_start.json()["id"]

        exam_submit = client.post(
            f"/video-training/session/{exam_session_id}/node/submit",
            json={
                "node_id": video.nodes[0].id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 2,
                "speech_transcript": "请配合检查",
            },
            headers=student_headers,
        )
        assert exam_submit.status_code == 200
        assert exam_submit.json()["result"] == "pass"
        assert exam_submit.json()["score_deducted"] == 10

    def test_exam_mode_rejects_keyword_mismatch_after_practice_pass(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训练习容错")
        video.nodes[0].required_keywords = json.dumps(["请配合"], ensure_ascii=False)
        video.nodes[0].node_config = json.dumps({
            "pass_rule": {"mode": "all"},
            "speech_rule": {"match_mode": "any", "min_count": 1, "min_length": 0},
        }, ensure_ascii=False)
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        practice_start = client.post(f"/video-training/start/{video.id}?mode=practice", headers=student_headers)
        assert practice_start.status_code == 200
        practice_session_id = practice_start.json()["id"]

        practice_submit = client.post(
            f"/video-training/session/{practice_session_id}/node/submit",
            json={
                "node_id": video.nodes[0].id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "请配合检查",
                "answer_data": {},
            },
            headers=student_headers,
        )
        assert practice_submit.status_code == 200
        assert practice_submit.json()["result"] == "pass"

        reset_video_training_sessions(db_session, student.id, video.id)
        exam_start = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert exam_start.status_code == 200
        exam_session_id = exam_start.json()["id"]

        exam_submit = client.post(
            f"/video-training/session/{exam_session_id}/node/submit",
            json={
                "node_id": video.nodes[0].id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "未包含关键词",
                "answer_data": {},
            },
            headers=student_headers,
        )
        assert exam_submit.status_code == 200
        assert exam_submit.json()["result"] == "fail"

    def test_admin_violation_type_filter_applies_to_sessions_and_analytics(
        self, client, db_session, student_headers, admin_headers
    ):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="视频实训违规筛选")
        reset_video_training_sessions(db_session, student.id, video.id)

        first_session_response = client.post(f"/video-training/start/{video.id}", headers=student_headers)
        assert first_session_response.status_code == 200
        first_session_id = first_session_response.json()["id"]
        first_violation = client.post(
            f"/video-training/session/{first_session_id}/violation",
            json={"type": "device_lost", "detail": "摄像头断开"},
            headers=student_headers,
        )
        assert first_violation.status_code == 200

        second_session_response = client.post(f"/video-training/start/{video.id}", headers=student_headers)
        assert second_session_response.status_code == 200
        second_session_id = second_session_response.json()["id"]
        second_violation = client.post(
            f"/video-training/session/{second_session_id}/violation",
            json={"type": "tab_switch", "detail": "切到其他窗口"},
            headers=student_headers,
        )
        assert second_violation.status_code == 200

        sessions_response = client.get(
            f"/video-training/admin/sessions?video_id={video.id}&violation_type=device_lost",
            headers=admin_headers,
        )
        assert sessions_response.status_code == 200
        sessions_payload = sessions_response.json()
        assert sessions_payload["total"] == 1
        assert sessions_payload["items"][0]["id"] == first_session_id
        assert sessions_payload["items"][0]["violation_log"][0]["type"] == "device_lost"

        analytics_response = client.get(
            f"/video-training/admin/analytics?video_id={video.id}&violation_type=device_lost",
            headers=admin_headers,
        )
        assert analytics_response.status_code == 200
        analytics_payload = analytics_response.json()
        assert analytics_payload["session_count"] == 1
        assert analytics_payload["total_violation_count"] == 1
        assert analytics_payload["violation_summary"][0]["type"] == "device_lost"

    def test_police_semantic_node_scores_standard_points(self, client, db_session, student_headers):
        student = db_session.query(models.User).filter(models.User.username == "student001").first()
        video = ensure_interactive_video(db_session, title="\u6a21\u62df\u8b66\u60c5\u8bed\u4e49\u8bc4\u5206")
        first_node = video.nodes[0]
        first_node.node_type = "voice_qa"
        first_node.required_gesture = None
        first_node.required_keywords = json.dumps(["legacy-keyword"], ensure_ascii=False)
        first_node.prop_mode = "auto"
        first_node.score_weight = 10
        first_node.prompt_content = json.dumps(
            {
                "instruction": "\u8bf7\u8bf4\u51fa\u5904\u7f6e\u601d\u8def",
                "police_question": "\u8bf7\u8bf4\u51fa\u5230\u573a\u540e\u7684\u5904\u7f6e\u8981\u70b9",
                "scene_summary": "\u9152\u540e\u7ea0\u7eb7\u73b0\u573a\u6709\u9152\u74f6\u98ce\u9669",
            },
            ensure_ascii=False,
        )
        first_node.node_config = json.dumps(
            {
                "police_node_type": "risk_identification",
                "standard_points": [
                    "\u8bc6\u522b\u9152\u74f6\u7b49\u5371\u9669\u7269\u54c1",
                    "\u62c9\u5f00\u53cc\u65b9\u4fdd\u6301\u5b89\u5168\u8ddd\u79bb",
                    "\u8bf7\u6c42\u652f\u63f4\u5230\u573a",
                ],
                "semantic_pass_threshold": 60,
                "pass_rule": {"mode": "speech_only"},
                "speech_rule": {"match_mode": "any", "min_count": 0, "min_length": 0},
            },
            ensure_ascii=False,
        )
        db_session.commit()
        reset_video_training_sessions(db_session, student.id, video.id)

        start_response = client.post(f"/video-training/start/{video.id}?mode=exam", headers=student_headers)
        assert start_response.status_code == 200
        session_id = start_response.json()["id"]

        submit_response = client.post(
            f"/video-training/session/{session_id}/node/submit",
            json={
                "node_id": first_node.id,
                "node_index": 0,
                "action": "pass",
                "retry_count": 0,
                "speech_transcript": "\u5148\u63a7\u5236\u9152\u74f6\u7b49\u5371\u9669\u7269\u54c1\uff0c\u62c9\u5f00\u53cc\u65b9\u4fdd\u6301\u5b89\u5168\u8ddd\u79bb\uff0c\u5e76\u547c\u53eb\u652f\u63f4\u3002",
            },
            headers=student_headers,
        )

        assert submit_response.status_code == 200
        payload = submit_response.json()
        assert payload["result"] == "pass"
        assert payload["score_earned"] == 10
        semantic = payload["feedback"]["police_semantic"]
        assert semantic["enabled"] is True
        assert semantic["passed"] is True
        assert semantic["hit_count"] == 3
        assert not semantic["missed_points"]
