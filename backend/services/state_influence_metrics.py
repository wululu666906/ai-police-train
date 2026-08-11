"""Metrics and regression suite for four-axis state influence (P2)."""

from __future__ import annotations

from statistics import mean
from typing import Any

from .state_contract_validation import affect_display_label, validate_response_against_contract
from .state_influence_engine import (
    build_state_contract,
    enrich_momentum_with_axis_deltas,
    format_state_contract_block,
    resolve_band,
)

REGRESSION_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "angry_high_clear",
        "label": "高情绪+高风险+清晰度中上 → 愤怒对抗",
        "scores": {"emotion": 88, "cooperation": 40, "risk": 78, "clarity": 62},
        "expected_affect": "angry",
    },
    {
        "id": "fearful_high_low_clarity",
        "label": "高情绪+高风险+低清晰 → 害怕慌乱",
        "scores": {"emotion": 85, "cooperation": 35, "risk": 82, "clarity": 18},
        "expected_affect": "fearful",
    },
    {
        "id": "cold_low_coop",
        "label": "低情绪+低配合 → 冷拒",
        "scores": {"emotion": 25, "cooperation": 18, "risk": 45, "clarity": 55},
        "expected_affect": "cold",
    },
    {
        "id": "cooperative_mid",
        "label": "中高配合+中清晰 → 愿意配合",
        "scores": {"emotion": 45, "cooperation": 72, "risk": 35, "clarity": 68},
        "expected_affect": "cooperative",
    },
    {
        "id": "guarded_low_emotion",
        "label": "低情绪+中配合 → 防备回避",
        "scores": {"emotion": 35, "cooperation": 45, "risk": 58, "clarity": 50},
        "expected_affect": "guarded",
    },
    {
        "id": "agitated_very_high_emotion",
        "label": "极高情绪 → 激动抱怨",
        "scores": {"emotion": 92, "cooperation": 30, "risk": 40, "clarity": 70},
        "expected_affect": "angry",
    },
    {
        "id": "angry_clear_control",
        "label": "高情绪+高风险+清晰表达 → 激动但仍可理解",
        "scores": {"emotion": 92, "cooperation": 28, "risk": 82, "clarity": 78},
        "expected_affect": "angry",
        "min_expression_control": 48,
        "expected_control_mode": "clear",
    },
]

TARGET_REGRESSION_PASS_RATE = 0.85
MAX_TURN_LOG = 80


def _normalize_scores(raw: dict[str, Any] | None) -> dict[str, int]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "emotion": int(raw.get("emotion", 50)),
        "cooperation": int(raw.get("cooperation", raw.get("trust", 30))),
        "risk": int(raw.get("risk", 50)),
        "clarity": int(raw.get("clarity", 50)),
    }


def simulate_state_influence(
    scores: dict[str, Any],
    *,
    user_message: str = "",
    recognized_actions: list[str] | None = None,
) -> dict[str, Any]:
    normalized = _normalize_scores(scores)
    for axis in normalized:
        normalized[axis] = max(0, min(100, normalized[axis]))

    momentum: dict[str, Any] = {}
    if user_message.strip() or recognized_actions:
        momentum = enrich_momentum_with_axis_deltas({}, user_message, recognized_actions)

    contract = build_state_contract(normalized, momentum)
    bands = {axis: resolve_band(normalized[axis]) for axis in normalized}
    return {
        "scores": normalized,
        "bands": bands,
        "contract": contract,
        "affect_label": affect_display_label(contract),
        "contract_block": format_state_contract_block(contract),
        "trigger_deltas": momentum.get("trigger_axis_deltas") or {},
    }


def run_regression_suite() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0
    for scenario in REGRESSION_SCENARIOS:
        preview = simulate_state_influence(scenario["scores"])
        actual = str(preview["contract"].get("primary_affect") or "")
        expected = str(scenario.get("expected_affect") or "")
        ok = actual == expected
        if ok:
            passed += 1
        results.append(
            {
                "id": scenario["id"],
                "label": scenario.get("label") or scenario["id"],
                "expected_affect": expected,
                "actual_affect": actual,
                "affect_label": preview.get("affect_label"),
                "bands": preview.get("bands"),
                "expression_control": preview["contract"].get("expression_control"),
                "control_mode": preview["contract"].get("control_mode"),
                "passed": ok,
            }
        )
        if scenario.get("min_expression_control") is not None:
            control_ok = int(preview["contract"].get("expression_control") or 0) >= int(scenario["min_expression_control"])
            mode_ok = not scenario.get("expected_control_mode") or preview["contract"].get("control_mode") == scenario["expected_control_mode"]
            results[-1]["control_passed"] = control_ok and mode_ok
            results[-1]["passed"] = results[-1]["passed"] and results[-1]["control_passed"]
    total = len(REGRESSION_SCENARIOS)
    pass_rate = round(passed / total, 3) if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "pass_rate": pass_rate,
        "target_pass_rate": TARGET_REGRESSION_PASS_RATE,
        "meets_target": pass_rate >= TARGET_REGRESSION_PASS_RATE,
        "results": results,
    }


def record_turn_metrics(
    runtime_state: dict[str, Any],
    *,
    contract: dict[str, Any] | None,
    ai_reply: str,
    postcheck: dict[str, Any] | None = None,
    stage_missing: list[str] | None = None,
    stage_satisfied: list[str] | None = None,
    behavior_archetype: str | None = None,
    role_type: str | None = None,
) -> dict[str, Any]:
    validation = (postcheck or {}).get("validation")
    if not validation and contract:
        validation = validate_response_against_contract(ai_reply, contract)

    entry = {
        "primary_affect": (contract or {}).get("primary_affect"),
        "delivery": (contract or {}).get("delivery"),
        "validation_ok": bool((validation or {}).get("ok")),
        "validation_score": float((validation or {}).get("score") or 0),
        "postcheck_adjusted": bool((postcheck or {}).get("adjusted")),
        "repetition_repaired": bool((postcheck or {}).get("repetition_repaired")),
        "expression_control": int((contract or {}).get("expression_control") or 0),
        "control_mode": (contract or {}).get("control_mode"),
        "stage_missing_count": len(stage_missing or []),
        "stage_satisfied_count": len(stage_satisfied or []),
        "behavior_archetype": behavior_archetype or (contract or {}).get("behavior_archetype") or "unknown",
        "role_type": role_type or (contract or {}).get("role_type") or "unknown",
    }

    log = runtime_state.get("state_influence_turn_log")
    if not isinstance(log, list):
        log = []
    log.append(entry)
    runtime_state["state_influence_turn_log"] = log[-MAX_TURN_LOG:]
    return entry


def summarize_turn_log(log: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not isinstance(log, list) or not log:
        return {
            "turn_count": 0,
            "consistency_rate": 0.0,
            "avg_validation_score": 0.0,
            "postcheck_adjustment_rate": 0.0,
            "repetition_repair_rate": 0.0,
            "high_arousal_clear_rate": 0.0,
            "stage_requirement_hit_rate": 0.0,
            "affect_distribution": {},
        }

    n = len(log)
    consistency_rate = sum(1 for item in log if item.get("validation_ok")) / n
    avg_validation_score = mean(float(item.get("validation_score") or 0) for item in log)
    postcheck_adjustment_rate = sum(1 for item in log if item.get("postcheck_adjusted")) / n
    repetition_repair_rate = sum(1 for item in log if item.get("repetition_repaired")) / n
    high_arousal = [item for item in log if str(item.get("primary_affect") or "") in {"angry", "agitated", "fearful"}]
    high_arousal_clear_rate = (
        sum(1 for item in high_arousal if int(item.get("expression_control") or 0) >= 48) / len(high_arousal)
        if high_arousal else 0.0
    )

    stage_hits: list[float] = []
    for item in log:
        satisfied = int(item.get("stage_satisfied_count") or 0)
        missing = int(item.get("stage_missing_count") or 0)
        total = satisfied + missing
        if total > 0:
            stage_hits.append(satisfied / total)

    affect_distribution: dict[str, int] = {}
    for item in log:
        affect = str(item.get("primary_affect") or "unknown")
        affect_distribution[affect] = affect_distribution.get(affect, 0) + 1

    return {
        "turn_count": n,
        "consistency_rate": round(consistency_rate, 3),
        "avg_validation_score": round(avg_validation_score, 3),
        "postcheck_adjustment_rate": round(postcheck_adjustment_rate, 3),
        "repetition_repair_rate": round(repetition_repair_rate, 3),
        "high_arousal_clear_rate": round(high_arousal_clear_rate, 3),
        "stage_requirement_hit_rate": round(mean(stage_hits), 3) if stage_hits else 0.0,
        "affect_distribution": affect_distribution,
    }


def build_session_metrics(runtime_state: dict[str, Any] | None) -> dict[str, Any]:
    state = runtime_state if isinstance(runtime_state, dict) else {}
    log = state.get("state_influence_turn_log")
    summary = summarize_turn_log(log if isinstance(log, list) else [])
    summary["meets_consistency_target"] = summary.get("consistency_rate", 0) >= TARGET_REGRESSION_PASS_RATE
    summary["last_postcheck"] = state.get("last_postcheck")
    return summary


def build_calibration_report(session_records: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Aggregate runtime logs for threshold calibration and human review."""
    records = [item for item in (session_records or []) if isinstance(item, dict)]
    logs: list[dict[str, Any]] = []
    for record in records:
        runtime_state = record.get("runtime_state")
        turn_log = runtime_state.get("state_influence_turn_log") if isinstance(runtime_state, dict) else []
        for turn in turn_log if isinstance(turn_log, list) else []:
            if isinstance(turn, dict):
                logs.append(
                    {
                        **turn,
                        "session_id": record.get("session_id"),
                        "scene_id": record.get("scene_id"),
                        "role_type": record.get("role_type") or turn.get("role_type") or "unknown",
                        "behavior_archetype": record.get("behavior_archetype") or turn.get("behavior_archetype") or "unknown",
                    }
                )

    def _rate(items: list[dict[str, Any]], key: str) -> float:
        return round(sum(1 for item in items if item.get(key)) / len(items), 3) if items else 0.0

    def _group(items: list[dict[str, Any]], key: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault(str(item.get(key) or "unknown"), []).append(item)
        return {
            name: {
                "turn_count": len(group),
                "consistency_rate": round(sum(1 for row in group if row.get("validation_ok")) / len(group), 3),
                "postcheck_adjustment_rate": _rate(group, "postcheck_adjusted"),
                "repetition_repair_rate": _rate(group, "repetition_repaired"),
                "high_arousal_clear_rate": round(
                    sum(
                        1
                        for row in group
                        if str(row.get("primary_affect") or "") in {"angry", "agitated", "fearful"}
                        and int(row.get("expression_control") or 0) >= 48
                    )
                    / max(1, sum(1 for row in group if str(row.get("primary_affect") or "") in {"angry", "agitated", "fearful"})),
                    3,
                ),
            }
            for name, group in grouped.items()
        }

    review_sessions = sorted(
        {
            int(item["session_id"])
            for item in logs
            if item.get("session_id") is not None
            and (item.get("repetition_repaired") or item.get("postcheck_adjusted") or not item.get("validation_ok"))
        }
    )
    return {
        "session_count": len(records),
        "turn_count": len(logs),
        "consistency_rate": round(sum(1 for item in logs if item.get("validation_ok")) / len(logs), 3) if logs else 0.0,
        "postcheck_adjustment_rate": _rate(logs, "postcheck_adjusted"),
        "repetition_repair_rate": _rate(logs, "repetition_repaired"),
        "high_arousal_clear_rate": round(
            sum(
                1
                for item in logs
                if str(item.get("primary_affect") or "") in {"angry", "agitated", "fearful"}
                and int(item.get("expression_control") or 0) >= 48
            )
            / max(1, sum(1 for item in logs if str(item.get("primary_affect") or "") in {"angry", "agitated", "fearful"})),
            3,
        ),
        "by_archetype": _group(logs, "behavior_archetype"),
        "by_affect": _group(logs, "primary_affect"),
        "review_session_ids": review_sessions[:100],
    }
