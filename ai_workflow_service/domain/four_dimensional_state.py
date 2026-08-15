from __future__ import annotations

from dataclasses import dataclass
from typing import Any


STATE_KEYS = ("emotion", "cooperation", "risk", "clarity")
STATE_PRIORITY = ("crisis", "confused", "resistant", "agitated", "engaged", "guarded")
DEFAULT_STATE = {"emotion": 50, "cooperation": 35, "risk": 50, "clarity": 50}
MAX_TURN_DELTA = 12
HYSTERESIS = 5


def clamp(value: Any, low: int = 0, high: int = 100) -> int:
    try:
        return max(low, min(high, round(float(value))))
    except (TypeError, ValueError):
        return low


def normalize_state(value: Any) -> dict[str, int]:
    raw = value if isinstance(value, dict) else {}
    return {key: clamp(raw.get(key, default)) for key, default in DEFAULT_STATE.items()}


DEFAULT_THRESHOLDS: dict[str, dict[str, dict[str, int]]] = {
    "crisis": {"enter": {"risk_gte": 80}, "exit": {"risk_lt": 75}},
    "confused": {"enter": {"clarity_lte": 30}, "exit": {"clarity_gt": 35}},
    "resistant": {"enter": {"cooperation_lte": 30}, "exit": {"cooperation_gt": 35}},
    "agitated": {"enter": {"emotion_gte": 70}, "exit": {"emotion_lt": 65}},
    "engaged": {"enter": {"cooperation_gte": 65, "clarity_gte": 60, "risk_lte": 60}, "exit": {"cooperation_lt": 60}},
    "guarded": {"enter": {}, "exit": {}},
}


def _matches(state: dict[str, int], rules: dict[str, int]) -> bool:
    for expression, threshold in rules.items():
        key, operator = expression.rsplit("_", 1)
        value = state.get(key, 0)
        if operator == "gte" and value < threshold:
            return False
        if operator == "gt" and value <= threshold:
            return False
        if operator == "lte" and value > threshold:
            return False
        if operator == "lt" and value >= threshold:
            return False
    return True


def _threshold_table(overrides: Any) -> dict[str, dict[str, dict[str, int]]]:
    table = {label: {"enter": dict(config["enter"]), "exit": dict(config["exit"])} for label, config in DEFAULT_THRESHOLDS.items()}
    if not isinstance(overrides, dict):
        return table
    for label, raw in overrides.items():
        if label not in table or not isinstance(raw, dict):
            continue
        enter = raw.get("enter") if isinstance(raw.get("enter"), dict) else {}
        exit_rules = raw.get("exit") if isinstance(raw.get("exit"), dict) else {}
        if enter:
            table[label]["enter"] = {str(key): int(value) for key, value in enter.items()}
        if exit_rules:
            table[label]["exit"] = {str(key): int(value) for key, value in exit_rules.items()}
        elif enter:
            derived = {}
            for expression, value in table[label]["enter"].items():
                key, operator = expression.rsplit("_", 1)
                if operator in {"gte", "gt"}:
                    derived[f"{key}_lt"] = int(value) - HYSTERESIS
                else:
                    derived[f"{key}_gt"] = int(value) + HYSTERESIS
            table[label]["exit"] = derived
    return table


def resolve_label(state: dict[str, int], previous: str = "", thresholds: Any = None) -> str:
    table = _threshold_table(thresholds)
    if previous in table:
        exit_rules = table[previous].get("exit") or {}
        if exit_rules and not _matches(state, exit_rules):
            return previous
    for label in STATE_PRIORITY:
        if _matches(state, (table.get(label) or {}).get("enter") or {}):
            return label
    return "guarded"


@dataclass(frozen=True)
class StateTransition:
    state: dict[str, int]
    delta: dict[str, int]
    label: str
    crisis_blocked: bool


def transition(current: Any, proposed_delta: Any, *, previous_label: str = "", thresholds: Any = None) -> StateTransition:
    before = normalize_state(current)
    raw_delta = proposed_delta if isinstance(proposed_delta, dict) else {}
    delta = {key: clamp(raw_delta.get(key, 0), -MAX_TURN_DELTA, MAX_TURN_DELTA) for key in STATE_KEYS}
    after = {key: clamp(before[key] + delta[key]) for key in STATE_KEYS}
    actual_delta = {key: after[key] - before[key] for key in STATE_KEYS}
    label = resolve_label(after, previous_label, thresholds)
    return StateTransition(after, actual_delta, label, label == "crisis")


def infer_rule_delta(text: str, *, input_kind: str = "dialogue") -> dict[str, int]:
    content = (text or "").strip()
    delta = {key: 0 for key in STATE_KEYS}
    positive = ("请", "理解", "慢慢", "安全", "确认", "核实", "谢谢", "保护")
    coercive = ("撒谎", "老实交代", "必须", "警告", "闭嘴", "废话")
    risk_control = ("隔离", "疏散", "增援", "控制", "急救", "保护现场", "停止危险")
    clarifying = ("时间", "地点", "谁", "什么", "经过", "证据", "是否", "为什么")
    delta["cooperation"] += 4 if any(token in content for token in positive) else 0
    delta["emotion"] -= 3 if any(token in content for token in positive) else 0
    delta["cooperation"] -= 7 if any(token in content for token in coercive) else 0
    delta["emotion"] += 6 if any(token in content for token in coercive) else 0
    delta["risk"] -= 6 if any(token in content for token in risk_control) else 0
    delta["clarity"] += 5 if any(token in content for token in clarifying) else 0
    if input_kind == "action" and content:
        delta["risk"] -= 3
        delta["cooperation"] += 1
    return delta
