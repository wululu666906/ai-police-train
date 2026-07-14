import models
from services.training_runtime_service import dump_runtime_state


def test_admin_can_read_state_calibration_report(client, db_session, admin_headers):
    session = models.TrainingSession(
        user_id=2,
        scene_id=1,
        current_stage="现场处置",
        current_emotion=88,
        current_trust=30,
        status="active",
        revealed_info=dump_runtime_state(
            {
                "state_influence_turn_log": [
                    {
                        "primary_affect": "angry",
                        "validation_ok": True,
                        "validation_score": 1.0,
                        "postcheck_adjusted": False,
                        "repetition_repaired": True,
                        "expression_control": 64,
                        "behavior_archetype": "强硬对抗型",
                    }
                ]
            }
        ),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get("/dashboard/state-calibration?limit=20", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["turn_count"] >= 1
    assert payload["by_archetype"]["强硬对抗型"]["repetition_repair_rate"] == 1.0


def test_student_cannot_read_state_calibration_report(client, student_headers):
    response = client.get("/dashboard/state-calibration", headers=student_headers)
    assert response.status_code == 403
