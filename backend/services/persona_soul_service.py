"""Model-assisted persona profiles with conservative police-contact priors."""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .llm_provider import (
    create_json_chat_completion,
    extract_json_payload,
    extract_message_text,
    get_chat_completion_binding,
    get_chat_model,
)
from .ai_workflow_audit import new_correlation_id, record_workflow_run


_HIGH_RISK_MARKERS = ("醉", "酒", "精神", "幻觉", "持刀", "持械", "扬言", "自伤", "轻生", "失控")
_RESISTANCE_MARKERS = ("拒不", "抗拒", "袭警", "逃跑", "暴力抗法", "威胁民警")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clamp(value: Any, default: int, low: int = 0, high: int = 100) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _source_excerpt(person: dict[str, Any]) -> str:
    memories: list[str] = []
    seen: set[str] = set()
    for item in _items(person.get("role_memories")):
        if isinstance(item, dict) and _text(item.get("statement")):
            statement = _text(item.get("statement"))
            normalized = "".join(statement.split())
            if normalized and normalized not in seen:
                memories.append(statement)
                seen.add(normalized)
    return "\n".join(memories)


def _baseline(person: dict[str, Any]) -> dict[str, Any]:
    role_type = _text(person.get("role_type") or person.get("role")) or "相关人员"
    corpus = " ".join(
        [role_type, _text(person.get("status")), _text(person.get("personality")), _source_excerpt(person)]
    )
    exceptional = any(token in corpus for token in (*_HIGH_RISK_MARKERS, *_RESISTANCE_MARKERS))
    suspect = "嫌疑" in role_type or "违法" in role_type
    victim = any(token in role_type for token in ("报警", "报案", "被害", "受害", "求助"))
    witness = any(token in role_type for token in ("证人", "目击", "群众", "相关人员"))

    trust = 58 if victim else 52 if witness else 40 if suspect else 50
    cooperation = 68 if victim else 62 if witness else 46 if suspect else 58
    arousal = 52 if victim else 42 if witness else 48
    risk = 24 if victim or witness else 38 if suspect else 30
    if exceptional:
        arousal += 22
        risk += 35
        trust -= 18
        cooperation -= 20

    return {
        "schema_version": 1,
        "source": "behavior_prior",
        "confidence": 0.35,
        "authority_trust": _clamp(trust, 50),
        "cooperation_baseline": _clamp(cooperation, 58),
        "arousal_baseline": _clamp(arousal, 45),
        "risk_baseline": _clamp(risk, 30),
        "clarity_baseline": 62 if exceptional else 76,
        "face_sensitivity": 62 if suspect else 42,
        "threat_sensitivity": 72 if exceptional else 46,
        "self_control": 30 if exceptional else 68,
        "police_stance": "谨慎配合" if suspect else "信任并愿意配合",
        "primary_need": _text(person.get("current_goal")) or ("解决当前警情并获得明确安排" if victim else "安全说明自己知道的情况"),
        "coping_style": "先自保再逐步说明" if suspect else "在警方平稳沟通下逐步说明",
        "speech_tendency": "日常口语，优先回答当前问题",
        "deescalation_keys": ["被认真倾听", "警方说明下一步", "确认安全与处理边界"],
        "escalation_keys": ["被公开羞辱", "被无依据定性"] if not exceptional else ["多人逼近", "连续命令", "高刺激围观"],
        "dynamic_weight": 0.22,
    }


def _persona_context(person: dict[str, Any]) -> dict[str, Any]:
    source_excerpt = _source_excerpt(person)
    event_rows = []
    for item in _items(person.get("role_event_ledger")):
        if isinstance(item, dict) and _text(item.get("content")):
            event_rows.append(_text(item.get("content")))
    narrative_rows = []
    for item in _items(person.get("narrative_context")):
        if isinstance(item, dict) and item.get("is_scoring_fact") is False and _text(item.get("content")):
            narrative_rows.append(_text(item.get("content")))
    return {
        "name": _text(person.get("name")),
        "role_type": _text(person.get("role_type") or person.get("role")),
        "status": _text(person.get("status")),
        "source_memories": source_excerpt[:5000],
        "source_event_summary": "\n".join(dict.fromkeys(event_rows))[:5000],
        "narrative_context_for_persona_only": "\n".join(dict.fromkeys(narrative_rows))[:2400],
        "current_training_stage": _text(person.get("current_training_stage")) or "民警到场后的沟通与核查",
    }


def _model_profiles(persons: list[dict[str, Any]], case_info: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    compact_people = [
        _persona_context(person)
        for person in persons
        if _text(person.get("name"))
    ]
    if not compact_people:
        return {}, []
    configured_provider = os.getenv("PERSONA_PROFILE_PROVIDER", "").strip() or None
    configured_model = os.getenv("PERSONA_PROFILE_MODEL", "").strip() or None
    llm_client = None
    model = get_chat_model()
    if configured_provider or configured_model:
        llm_client, model, _, _ = get_chat_completion_binding(configured_provider, configured_model)
    correlation_id = new_correlation_id()
    system_prompt = (
        "你是警务情境人物画像分析员。优先根据身份、本人来源记忆和来源事件归纳，不诊断精神疾病，不默认敌视警方，不增强戏剧性。"
        "narrative_context_for_persona_only可能包含剧情拓写，只能辅助判断表达和沟通方式，禁止把其中新增心理或动作当成案件事实。"
        "普通报警人、群众和证人通常尊重警方并愿意有限配合。输出JSON对象profiles，数量和姓名必须与输入完全一致。"
        "字段：name,police_stance,primary_need,coping_style,speech_tendency,authority_trust,cooperation_baseline,"
        "arousal_baseline,risk_baseline,clarity_baseline,face_sensitivity,threat_sensitivity,self_control,"
        "deescalation_keys,escalation_keys,evidence_notes。分数0-100，无依据保持中性。"
    )

    def generate_batch(batch: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        response, trace = create_json_chat_completion(
            model=model,
            llm_client=llm_client,
            temperature=0.1,
            max_tokens=max(2400, int(os.getenv("PERSONA_PROFILE_MAX_TOKENS", "3600"))),
            extra_kwargs={"timeout": max(10, int(os.getenv("PERSONA_PROFILE_TIMEOUT_SECONDS", "60")))},
            retries=1,
            return_trace=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps({"case_type": _text(case_info.get("case_type")), "persons": batch}, ensure_ascii=False)},
            ],
        )
        record_workflow_run(correlation_id=correlation_id, stage="persona_profile", trace=trace)
        payload = extract_json_payload(extract_message_text(response)) or {}
        profiles = payload.get("profiles") if isinstance(payload, dict) else []
        result = {
            _text(item.get("name")): item
            for item in _items(profiles)
            if isinstance(item, dict) and _text(item.get("name"))
        }
        expected = {_text(item.get("name")) for item in batch}
        if not result or not expected.issubset(result):
            raise ValueError(f"人物画像接口返回不完整：期望{len(expected)}人，实际{len(result)}人")
        return result

    batch_size = max(1, int(os.getenv("PERSONA_PROFILE_BATCH_SIZE", "4")))
    batches = [compact_people[index:index + batch_size] for index in range(0, len(compact_people), batch_size)]
    generated: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    workers = min(max(1, int(os.getenv("PERSONA_PROFILE_PARALLELISM", "3"))), len(batches))
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="persona-profile") as executor:
        futures = [(batch, executor.submit(generate_batch, batch)) for batch in batches]
        for batch, future in futures:
            try:
                generated.update(future.result())
            except Exception as exc:
                names = "、".join(_text(item.get("name")) for item in batch)
                warnings.append(f"{names}：{str(exc)[:180]}")
    return generated, warnings


def enrich_personas(case_info: dict[str, Any], *, use_model: bool = True) -> dict[str, Any]:
    """Attach compact profiles; model evidence is blended with conservative priors."""
    persons = [dict(item) for item in _items(case_info.get("persons")) if isinstance(item, dict)]
    generated: dict[str, dict[str, Any]] = {}
    model_errors: list[str] = []
    if use_model:
        try:
            generated, model_errors = _model_profiles(persons, case_info)
        except Exception as exc:
            model_errors = [str(exc)[:240]]

    for person in persons:
        base = _baseline(person)
        candidate = generated.get(_text(person.get("name"))) or {}
        # Model assistance refines a profile but cannot create an extreme state
        # without corresponding source evidence.
        corpus = " ".join([_text(person.get("status")), _source_excerpt(person)])
        exceptional = any(token in corpus for token in (*_HIGH_RISK_MARKERS, *_RESISTANCE_MARKERS))
        for key in (
            "authority_trust", "cooperation_baseline", "arousal_baseline", "risk_baseline",
            "clarity_baseline", "face_sensitivity", "threat_sensitivity", "self_control",
        ):
            if key not in candidate:
                continue
            proposed = _clamp(candidate.get(key), base[key])
            max_shift = 28 if exceptional else 16
            base[key] = max(base[key] - max_shift, min(base[key] + max_shift, proposed))
        for key in ("police_stance", "primary_need", "coping_style", "speech_tendency"):
            candidate_text = candidate.get(key)
            if isinstance(candidate_text, str) and _text(candidate_text).lower() not in {"unknown", "none", "null", "未知", "无"}:
                base[key] = _text(candidate_text)[:180]
        for key in ("deescalation_keys", "escalation_keys"):
            values = [_text(item) for item in _items(candidate.get(key)) if _text(item)]
            if values:
                base[key] = values[:4]
        base["source"] = "model_assisted" if candidate else "behavior_prior"
        base["confidence"] = 0.65 if candidate else 0.35
        base["evidence_notes"] = [_text(item) for item in _items(candidate.get("evidence_notes")) if _text(item)][:4]
        person["soul_profile"] = base
        # Existing runtime fields remain compatible while adopting calmer priors.
        person["init_emotion"] = base["arousal_baseline"]
        person["init_trust"] = base["cooperation_baseline"]
        person["police_attitude"] = base["police_stance"]
        person["current_goal"] = base["primary_need"]
        person["persona_generation"] = {
            "status": "generated" if candidate else "behavior_prior",
            "model_assisted": bool(candidate),
            "source_memory_count": len(_items(person.get("role_memories"))),
        }
    result = dict(case_info)
    result["persons"] = persons
    result["persona_generation"] = {
        "mode": "model_assisted" if generated else "behavior_prior",
        "profile_count": len(persons),
        "model_profile_count": len(generated),
        "failed_profile_count": max(0, len(persons) - len(generated)),
        "warning": "；".join(model_errors)[:1200],
    }
    return result
