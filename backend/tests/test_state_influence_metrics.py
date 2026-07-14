"""Tests for state influence metrics (P2)."""

from services.state_influence_metrics import (
    REGRESSION_SCENARIOS,
    build_calibration_report,
    record_turn_metrics,
    run_regression_suite,
    simulate_state_influence,
    summarize_turn_log,
)


def test_simulate_returns_contract_and_bands():
    preview = simulate_state_influence({"emotion": 85, "cooperation": 35, "risk": 82, "clarity": 18})
    assert preview["contract"]["primary_affect"] == "fearful"
    assert preview["bands"]["emotion"] == "very_high"
    assert preview["affect_label"]


def test_regression_suite_meets_target():
    report = run_regression_suite()
    assert report["total"] == len(REGRESSION_SCENARIOS)
    assert report["pass_rate"] >= report["target_pass_rate"]
    assert report["meets_target"] is True


def test_record_and_summarize_turn_log():
    runtime_state: dict = {}
    record_turn_metrics(
        runtime_state,
        contract={"primary_affect": "angry"},
        ai_reply="你别逼我！",
        postcheck={"adjusted": False, "validation": {"ok": True, "score": 1.0}},
        stage_missing=["核实身份"],
        stage_satisfied=["控制现场"],
    )
    summary = summarize_turn_log(runtime_state["state_influence_turn_log"])
    assert summary["turn_count"] == 1
    assert summary["consistency_rate"] == 1.0
    assert summary["stage_requirement_hit_rate"] > 0


def test_calibration_report_groups_turns_and_marks_review_sessions():
    report = build_calibration_report(
        [
            {
                "session_id": 7,
                "scene_id": 2,
                "runtime_state": {
                    "state_influence_turn_log": [
                        {
                            "primary_affect": "angry",
                            "validation_ok": True,
                            "postcheck_adjusted": False,
                            "repetition_repaired": True,
                            "expression_control": 62,
                            "behavior_archetype": "强硬对抗型",
                        }
                    ]
                },
            }
        ]
    )
    assert report["turn_count"] == 1
    assert report["by_archetype"]["强硬对抗型"]["repetition_repair_rate"] == 1.0
    assert report["review_session_ids"] == [7]
