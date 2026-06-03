"""Lightweight post-check: align role utterances with state contract."""

from __future__ import annotations

import re
from typing import Any

from .llm_provider import create_json_chat_completion, extract_message_text, get_chat_model

_AFFECT_LABELS = {
    "angry": "愤怒对抗",
    "fearful": "害怕慌乱",
    "agitated": "激动抱怨",
    "guarded": "防备回避",
    "cold": "冷拒敷衍",
    "cooperative": "愿意配合",
    "neutral": "谨慎观望",
    "flat": "压抑恐惧",
}

_RULE_FOLLOW_UPS = {
    "angry": "……你别这样逼我！",
    "fearful": "我、我真的记不清了……",
    "agitated": "……你先听我说完！",
    "cold": "……我不想说那么多。",
    "guarded": "……这个我不想讲。",
}


def affect_display_label(contract: dict[str, Any] | None) -> str:
    if not contract:
        return ""
    affect = str(contract.get("primary_affect") or "").strip()
    return _AFFECT_LABELS.get(affect, affect or "")


def validate_response_against_contract(text: str, contract: dict[str, Any]) -> dict[str, Any]:
    content = str(text or "").strip()
    issues: list[str] = []
    if not content or not contract:
        return {"ok": True, "issues": [], "score": 1.0}

    primary = str(contract.get("primary_affect") or "")
    max_sentences = int(contract.get("max_sentences") or 3)
    sentence_count = len([part for part in re.split(r"[。！？!?…]+", content) if part.strip()]) or 1

    if sentence_count > max_sentences + 1:
        issues.append("too_many_sentences")
    if primary in {"angry", "agitated", "fearful"} and len(content) > 140:
        issues.append("too_long_for_high_arousal")
    if primary in {"angry", "agitated"} and contract.get("interruption_allowed"):
        if not re.search(r"[？?！!]", content) and len(content) > 18:
            issues.append("missing_interrupt_markers")
    if primary == "fearful" and not re.search(r"(不|没|怕|慌|记不清|不知道)", content):
        issues.append("missing_fear_markers")

    for token in contract.get("must_include") or []:
        if token and token not in content:
            issues.append(f"missing:{token}")
    for token in contract.get("must_avoid") or []:
        if token and token in content:
            issues.append(f"forbidden:{token}")

    score = max(0.0, 1.0 - 0.18 * len(issues))
    return {"ok": len(issues) == 0, "issues": issues, "score": round(score, 2)}


def _rewrite_with_llm(
    text: str,
    contract: dict[str, Any],
    *,
    role_name: str,
    user_text: str,
) -> str:
    prompt = f"""你是台词校正器。把角色台词改到符合表现契约，保持口语、短句。

角色：{role_name}
学员刚说：{user_text or '（无）'}
原台词：{text}

契约：
- 主情绪：{contract.get('primary_affect')}（delivery={contract.get('delivery')}）
- 句式：{contract.get('sentence_style')}，最多 {contract.get('max_sentences')} 句
- 语气：{contract.get('tone_hint')}
- 宜体现：{'、'.join(contract.get('must_include') or []) or '无'}
- 禁止：{'、'.join(contract.get('must_avoid') or []) or '无'}

只输出 JSON：{{"response":"校正后的台词"}}"""
    try:
        response = create_json_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            model=get_chat_model(),
            max_tokens=400,
        )
        raw = extract_message_text(response) or ""
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return text
        import json

        payload = json.loads(match.group(0))
        rewritten = str(payload.get("response") or "").strip()
        if rewritten:
            check = validate_response_against_contract(rewritten, contract)
            if check.get("ok") or check.get("score", 0) >= validate_response_against_contract(text, contract).get("score", 0):
                return rewritten
    except Exception:
        pass
    return text


def apply_contract_postcheck(
    text: str,
    contract: dict[str, Any] | None,
    *,
    role_name: str = "",
    user_text: str = "",
    use_llm: bool = True,
) -> dict[str, Any]:
    if not contract:
        return {"text": str(text or "").strip(), "follow_up": None, "adjusted": False, "validation": {"ok": True}}

    original = str(text or "").strip()
    validation = validate_response_against_contract(original, contract)
    if validation.get("ok"):
        return {
            "text": original,
            "follow_up": None,
            "adjusted": False,
            "validation": validation,
        }

    revised = original
    adjusted = False
    if use_llm:
        candidate = _rewrite_with_llm(original, contract, role_name=role_name, user_text=user_text)
        if candidate != original:
            revised = candidate
            adjusted = True
            validation = validate_response_against_contract(revised, contract)

    follow_up = None
    if not validation.get("ok"):
        primary = str(contract.get("primary_affect") or "")
        follow_up = _RULE_FOLLOW_UPS.get(primary)
        if follow_up and follow_up not in revised:
            adjusted = True

    return {
        "text": revised,
        "follow_up": follow_up,
        "adjusted": adjusted,
        "validation": validation,
    }


def postcheck_reply_turns(
    turns: list[dict[str, Any]],
    role_contracts: dict[str, Any] | None,
    *,
    fallback_contract: dict[str, Any] | None = None,
    user_text: str = "",
    use_llm: bool = False,
) -> list[dict[str, Any]]:
    contracts = role_contracts if isinstance(role_contracts, dict) else {}
    output: list[dict[str, Any]] = []
    for item in turns or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        role_id = str(row.get("speaker_role_id") or "")
        contract = contracts.get(role_id) or fallback_contract
        content = str(row.get("content") or "").strip()
        if content and contract:
            post = apply_contract_postcheck(
                content,
                contract,
                role_name=str(row.get("speaker_name") or ""),
                user_text=user_text,
                use_llm=use_llm,
            )
            row["content"] = post.get("text") or content
        output.append(row)
    return output
