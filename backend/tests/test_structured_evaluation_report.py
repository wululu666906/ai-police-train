from services.evaluation_service import evaluate_session


def test_evaluate_session_contains_structured_review(client, student_headers, db_session):
    start_response = client.post("/training/start/1", headers=student_headers)
    session_id = start_response.json()["id"]
    client.post(
        f"/training/chat/{session_id}",
        json={"role": "user", "content": "请先把事情经过说清楚"},
        headers=student_headers,
    )

    report = evaluate_session(db_session, session_id, 2, force_recompute=True)
    assert "assessment_point_results" in report
    assert "action_results" in report
    assert "closure_summary" in report
    assert "scene_template_version" in report["evaluation_meta"]
