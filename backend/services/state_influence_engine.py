"""Four-axis state influence: bands, triggers, contracts, and blending."""

from __future__ import annotations

import re
from typing import Any

from .state_influence_config import get_tables

_BAND_ORDER = ["very_low", "low", "mid", "high", "very_high"]
_BAND_RANK = {name: index for index, name in enumerate(_BAND_ORDER)}


def _tables() -> dict[str, Any]:
    return get_tables()


def clamp_score(value: Any, fallback: int = 50) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0, min(100, numeric))


def resolve_band(score: Any) -> str:
    numeric = clamp_score(score, 50)
    for name, upper in _tables()["BAND_THRESHOLDS"]:
        if numeric <= upper:
            return name
    return "very_high"


def _band_interval(score: Any) -> tuple[str, float, str | None]:
    """Return (current_band, position 0-1 within band, next_band for interpolation)."""
    numeric = clamp_score(score, 50)
    lower = 0
    for name, upper in _tables()["BAND_THRESHOLDS"]:
        if numeric <= upper:
            span = max(1, upper - lower + 1)
            position = (numeric - lower) / span
            idx = _BAND_RANK.get(name, 2)
            next_band = _BAND_ORDER[idx + 1] if idx + 1 < len(_BAND_ORDER) else None
            return name, min(1.0, max(0.0, position)), next_band
        lower = upper + 1
    return "very_high", 1.0, None


def _lerp_scalar(start: float, end: float, t: float) -> float:
    return start + (end - start) * max(0.0, min(1.0, t))


def _interp_axis_numeric(
    score: int,
    axis_table: dict[str, dict[str, Any]],
    key: str,
    *,
    default: float,
    as_int: bool = False,
) -> float | int:
    band, position, next_band = _band_interval(score)
    start = float(axis_table.get(band, {}).get(key, default))
    if not next_band:
        return int(round(start)) if as_int else start
    end = float(axis_table.get(next_band, {}).get(key, start))
    value = _lerp_scalar(start, end, position)
    return int(round(value)) if as_int else value


def _interp_emotion_config(score: int, axis_emotion: dict[str, dict[str, Any]]) -> dict[str, Any]:
    band, position, next_band = _band_interval(score)
    base = dict(axis_emotion.get(band, axis_emotion.get("mid", {})))
    if next_band:
        nxt = axis_emotion.get(next_band, {})
        base["max_sentences"] = int(
            round(_lerp_scalar(float(base.get("max_sentences", 3)), float(nxt.get("max_sentences", 3)), position))
        )
        base["interruption_allowed"] = bool(base.get("interruption_allowed")) or (
            bool(nxt.get("interruption_allowed")) and position >= 0.55
        )
        if position >= 0.72:
            for field in ("affect", "delivery", "sentence_style"):
                if nxt.get(field):
                    base[field] = nxt[field]
        if position >= 0.8:
            base["must_include"] = _dedupe(list(base.get("must_include") or []) + list(nxt.get("must_include") or []))
        if position >= 0.65:
            base["must_avoid"] = _dedupe(list(base.get("must_avoid") or []) + list(nxt.get("must_avoid") or []))
    return base


def contract_strictness(contract: dict[str, Any] | None) -> str:
    """loose | moderate | strict — drives generation temperature and postcheck."""
    if not contract:
        return "loose"
    disclosure = float(contract.get("disclosure_level") or 0.45)
    escalation = float(contract.get("escalation_bias") or 0.35)
    affect = str(contract.get("primary_affect") or "")
    if disclosure <= 0.22 or escalation >= 0.72 or affect in {"angry", "fearful"}:
        return "strict"
    if disclosure <= 0.32 or escalation >= 0.5 or affect in {"agitated", "cold", "guarded"}:
        return "moderate"
    return "loose"


def generation_temperature_for_contract(contract: dict[str, Any] | None) -> float:
    level = contract_strictness(contract)
    if level == "strict":
        return 0.66
    if level == "moderate":
        return 0.74
    return 0.82


def max_chars_for_disclosure(disclosure_level: float) -> int:
    """Hard cap on reply length derived from disclosure tendency."""
    level = max(0.05, min(0.95, float(disclosure_level)))
    return int(40 + level * 120)


def max_new_facts_for_disclosure(disclosure_level: float) -> int:
    level = max(0.05, min(0.95, float(disclosure_level)))
    if level < 0.2:
        return 0
    if level < 0.4:
        return 1
    if level < 0.65:
        return 2
    return 3


def cap_new_fact_for_contract(fact: Any, contract: dict[str, Any] | None) -> Any:
    if not contract:
        return fact
    clean = str(fact or "").strip()
    if not clean or clean.lower() in {"null", "none", "无", "没有"}:
        return None
    disclosure = float(contract.get("disclosure_level") or 0.45)
    if max_new_facts_for_disclosure(disclosure) < 1:
        return None
    if disclosure < 0.35 and re.search(r"(先.{1,8}再|然后|最后|时间线)", clean):
        return None
    if len(clean) > 72:
        return clean[:69].rstrip() + "…"
    return clean


def _band_at_least(band: str, minimum: str) -> bool:
    return _BAND_RANK.get(band, 2) >= _BAND_RANK.get(minimum, 2)


def _band_at_most(band: str, maximum: str) -> bool:
    return _BAND_RANK.get(band, 2) <= _BAND_RANK.get(maximum, 2)


def _clamp_delta(value: Any, low: int | None = None, high: int | None = None) -> int:
    tables = _tables()
    if low is None:
        low = -int(tables["MAX_DELTA_PER_TURN"])
    if high is None:
        high = int(tables["MAX_DELTA_PER_TURN"])
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return 0
    return max(low, min(high, numeric))


def compute_trigger_axis_deltas(
    user_message: str,
    recognized_actions: list[str] | None = None,
) -> dict[str, int]:
    text = str(user_message or "").strip()
    deltas = {"emotion": 0, "cooperation": 0, "risk": 0, "clarity": 0}
    for rule in _tables()["TRIGGER_DELTAS"]:
        pattern = rule.get("pattern")
        if pattern and re.search(pattern, text):
            deltas["emotion"] += int(rule.get("emotion", 0))
            deltas["cooperation"] += int(rule.get("cooperation", 0))
            deltas["risk"] += int(rule.get("risk", 0))
            deltas["clarity"] += int(rule.get("clarity", 0))

    for action in recognized_actions or []:
        action_text = str(action or "").strip()
        for key, delta in _tables()["ACTION_DELTAS"].items():
            if key in action_text:
                for axis, amount in delta.items():
                    deltas[axis] += int(amount)

    for axis in deltas:
        deltas[axis] = _clamp_delta(deltas[axis])
    return deltas


def enrich_momentum_with_axis_deltas(
    momentum: dict[str, Any],
    user_message: str,
    recognized_actions: list[str] | None = None,
) -> dict[str, Any]:
    enriched = dict(momentum or {})
    trigger = compute_trigger_axis_deltas(user_message, recognized_actions)
    enriched["emotion_delta"] = _clamp_delta(int(enriched.get("emotion_delta", 0)) + trigger["emotion"])
    enriched["cooperation_delta"] = _clamp_delta(
        int(enriched.get("trust_delta", enriched.get("cooperation_delta", 0))) + trigger["cooperation"]
    )
    enriched["trust_delta"] = enriched["cooperation_delta"]
    enriched["risk_delta"] = _clamp_delta(int(enriched.get("risk_delta", 0)) + trigger["risk"])
    enriched["clarity_delta"] = _clamp_delta(int(enriched.get("clarity_delta", 0)) + trigger["clarity"])
    enriched["trigger_axis_deltas"] = trigger
    return enriched


def _match_combination(
    scores: dict[str, int],
    bands: dict[str, str],
) -> dict[str, Any] | None:
    for rule in _tables()["COMBINATION_RULES"]:
        when = rule.get("when") or {}
        ok = True
        if "emotion_min" in when and not _band_at_least(bands["emotion"], when["emotion_min"]):
            ok = False
        if "emotion_max" in when and not _band_at_most(bands["emotion"], when["emotion_max"]):
            ok = False
        if "cooperation_min" in when and not _band_at_least(bands["cooperation"], when["cooperation_min"]):
            ok = False
        if "cooperation_max" in when and not _band_at_most(bands["cooperation"], when["cooperation_max"]):
            ok = False
        if "risk_min" in when and not _band_at_least(bands["risk"], when["risk_min"]):
            ok = False
        if "risk_max" in when and not _band_at_most(bands["risk"], when["risk_max"]):
            ok = False
        if "clarity_min" in when and not _band_at_least(bands["clarity"], when["clarity_min"]):
            ok = False
        if "clarity_max" in when and not _band_at_most(bands["clarity"], when["clarity_max"]):
            ok = False
        if ok:
            return dict(rule.get("override") or {})
    return None


def build_state_contract(
    scores: dict[str, int],
    momentum: dict[str, Any] | None = None,
) -> dict[str, Any]:
    momentum = momentum or {}
    emotion = clamp_score(scores.get("emotion"), 50)
    cooperation = clamp_score(scores.get("cooperation", scores.get("trust")), 30)
    risk = clamp_score(scores.get("risk"), 50)
    clarity = clamp_score(scores.get("clarity"), 50)

    bands = {
        "emotion": resolve_band(emotion),
        "cooperation": resolve_band(cooperation),
        "risk": resolve_band(risk),
        "clarity": resolve_band(clarity),
    }

    tables = _tables()
    axis_emotion = tables["AXIS_EMOTION"]
    axis_coop = tables["AXIS_COOPERATION"]
    axis_risk = tables["AXIS_RISK"]
    axis_clarity = tables["AXIS_CLARITY"]
    emotion_cfg = _interp_emotion_config(emotion, axis_emotion)
    coop_cfg = dict(axis_coop.get(bands["cooperation"], axis_coop["mid"]))
    risk_cfg = dict(axis_risk.get(bands["risk"], axis_risk["mid"]))
    clarity_cfg = dict(axis_clarity.get(bands["clarity"], axis_clarity["mid"]))
    disclosure_level = _interp_axis_numeric(
        cooperation,
        axis_coop,
        "disclosure_level",
        default=0.45,
    )
    escalation_bias = _interp_axis_numeric(
        risk,
        axis_risk,
        "escalation_bias",
        default=0.35,
    )
    self_correction_min = _interp_axis_numeric(
        clarity,
        axis_clarity,
        "self_correction_min",
        default=0,
        as_int=True,
    )

    contract: dict[str, Any] = {
        "scores": {"emotion": emotion, "cooperation": cooperation, "risk": risk, "clarity": clarity},
        "bands": bands,
        "primary_affect": emotion_cfg.get("affect", "neutral"),
        "delivery": emotion_cfg.get("delivery", "normal"),
        "sentence_style": emotion_cfg.get("sentence_style", "normal"),
        "max_sentences": int(emotion_cfg.get("max_sentences", 3)),
        "disclosure_level": float(disclosure_level),
        "escalation_bias": float(escalation_bias),
        "max_chars": max_chars_for_disclosure(float(disclosure_level)),
        "tone_hint": emotion_cfg.get("tone_hint", ""),
        "cooperation_stance": coop_cfg.get("stance", ""),
        "risk_hint": risk_cfg.get("hint", ""),
        "clarity_hint": clarity_cfg.get("hint", ""),
        "must_include": list(emotion_cfg.get("must_include") or []),
        "must_avoid": list(emotion_cfg.get("must_avoid") or []),
        "interruption_allowed": bool(emotion_cfg.get("interruption_allowed", False)),
        "self_correction_min": int(self_correction_min),
    }

    if clarity_cfg.get("style") in {"broken", "fragmented"}:
        contract["sentence_style"] = clarity_cfg["style"]

    combo = _match_combination(
        {"emotion": emotion, "cooperation": cooperation, "risk": risk, "clarity": clarity},
        bands,
    )
    if combo:
        contract["primary_affect"] = combo.get("primary_affect", contract["primary_affect"])
        contract["delivery"] = combo.get("delivery", contract["delivery"])
        contract["sentence_style"] = combo.get("sentence_style", contract["sentence_style"])
        if combo.get("tone_hint"):
            contract["tone_hint"] = combo["tone_hint"]
        if combo.get("must_include"):
            contract["must_include"] = _dedupe(contract["must_include"] + list(combo["must_include"]))
        if combo.get("must_avoid"):
            contract["must_avoid"] = _dedupe(contract["must_avoid"] + list(combo["must_avoid"]))
        if "disclosure_level_cap" in combo:
            contract["disclosure_level"] = min(
                float(contract["disclosure_level"]),
                float(combo["disclosure_level_cap"]),
            )

    rapport = str(momentum.get("rapport") or "neutral")
    pressure = str(momentum.get("pressure") or "medium")
    if pressure == "high":
        contract["max_sentences"] = min(contract["max_sentences"], 2)
        contract["interruption_allowed"] = True
    if rapport == "warming":
        contract["disclosure_level"] = min(1.0, contract["disclosure_level"] + 0.08)
    elif rapport == "defensive":
        contract["disclosure_level"] = max(0.05, contract["disclosure_level"] - 0.1)

    contract["disclosure_level"] = round(max(0.05, min(0.95, contract["disclosure_level"])), 2)
    contract["max_chars"] = max_chars_for_disclosure(contract["disclosure_level"])
    contract["strictness"] = contract_strictness(contract)
    return contract


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def format_state_contract_block(contract: dict[str, Any]) -> str:
    if not contract:
        return "- 暂无表现契约"
    scores = contract.get("scores") or {}
    bands = contract.get("bands") or {}
    disclosure = float(contract.get("disclosure_level") or 0.45)
    max_chars = int(contract.get("max_chars") or max_chars_for_disclosure(disclosure))
    fact_cap = 0 if disclosure < 0.2 else (1 if disclosure < 0.4 else (2 if disclosure < 0.65 else 3))
    lines = [
        f"- 当前分值：情绪={scores.get('emotion')} / 配合={scores.get('cooperation')} / 风险={scores.get('risk')} / 清晰度={scores.get('clarity')}",
        f"- 分档：情绪={bands.get('emotion')} / 配合={bands.get('cooperation')} / 风险={bands.get('risk')} / 清晰度={bands.get('clarity')}",
        f"- 主情绪表现：{contract.get('primary_affect')}（delivery={contract.get('delivery')}）",
        f"- 句式：{contract.get('sentence_style')}，本轮最多 {contract.get('max_sentences')} 句、总字数不超过 {max_chars} 字",
        f"- 披露倾向：{contract.get('disclosure_level')}（{contract.get('cooperation_stance')}）",
        f"- 硬性披露：本轮 new_fact_revealed 最多 {fact_cap} 条；配合度低时禁止主动交代完整时间线或自证全部细节",
        f"- 失控风险倾向：{contract.get('escalation_bias')}（{contract.get('risk_hint')}）",
        f"- 表达清晰度：{contract.get('clarity_hint')}",
        f"- 语气指引：{contract.get('tone_hint')}",
        "- 若与案情、人设其它描述冲突，以本契约为准，宁可少说、短说、情绪化，也不要写成冷静说明书",
    ]
    if contract.get("must_include"):
        lines.append(f"- 台词中宜体现：{'、'.join(contract['must_include'])}")
    if contract.get("must_avoid"):
        lines.append(f"- 禁止出现：{'、'.join(contract['must_avoid'])}")
    if contract.get("interruption_allowed"):
        lines.append("- 允许打断、半句、重复核心不满")
    if int(contract.get("self_correction_min") or 0) > 0:
        lines.append(f"- 至少 {contract['self_correction_min']} 处口头自我纠正或改口")
    return "\n".join(lines)


def _pick_llm_score(result: dict[str, Any], *keys: str, fallback: int) -> int:
    for key in keys:
        if key in result and result.get(key) not in (None, ""):
            return clamp_score(result.get(key), fallback)
    return clamp_score(fallback, fallback)


def blend_four_axis_state(
    current: dict[str, int],
    llm_result: dict[str, Any],
    momentum: dict[str, Any],
) -> dict[str, int]:
    momentum = momentum or {}
    base = {
        "emotion": clamp_score(current.get("emotion"), 50),
        "cooperation": clamp_score(current.get("cooperation", current.get("trust")), 30),
        "risk": clamp_score(current.get("risk"), 50),
        "clarity": clamp_score(current.get("clarity"), 50),
    }

    proposed = {
        "emotion": _pick_llm_score(
            llm_result,
            "updated_emotion",
            fallback=base["emotion"],
        ),
        "cooperation": _pick_llm_score(
            llm_result,
            "updated_cooperation",
            "updated_trust",
            fallback=base["cooperation"],
        ),
        "risk": _pick_llm_score(llm_result, "updated_risk", fallback=base["risk"]),
        "clarity": _pick_llm_score(llm_result, "updated_clarity", fallback=base["clarity"]),
    }

    deltas = {
        "emotion": int(momentum.get("emotion_delta", 0)),
        "cooperation": int(momentum.get("cooperation_delta", momentum.get("trust_delta", 0))),
        "risk": int(momentum.get("risk_delta", 0)),
        "clarity": int(momentum.get("clarity_delta", 0)),
    }

    blended: dict[str, int] = {}
    for axis in ("emotion", "cooperation", "risk", "clarity"):
        target = proposed[axis] + deltas[axis]
        max_step = int(_tables()["MAX_DELTA_FROM_CURRENT"])
        step = _clamp_delta(target - base[axis], -max_step, max_step)
        blended[axis] = clamp_score(base[axis] + step, base[axis])
    return blended


def apply_delivery_from_contract(
    utterances: list[dict[str, Any]],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    delivery = str(contract.get("delivery") or "normal").strip() or "normal"
    output: list[dict[str, Any]] = []
    for item in utterances or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["delivery"] = delivery
        output.append(row)
    return output
