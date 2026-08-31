from __future__ import annotations

import json
import re
from typing import Any

from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter

_KIND_HINT = "hint"
_KIND_PLOT = "plot_advance"
_VALID_KINDS = {_KIND_HINT, _KIND_PLOT}
_NORMALIZE_RE = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()【】\[\]《》<>·…—\-]+")
_COACH_PREFIX_RE = re.compile(
    r"^(请立即|请先|请务必|请尽快|请具体说明|请核实|请确认|为推进处置[，,]?请说明|为推进|建议你|学员应|需要你|应当|必须先|"
    r"请说明与|如何推进|阶段下一步)"
)
_MAX_QUESTION_LEN = 56


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_question_key(value: Any) -> str:
    return _NORMALIZE_RE.sub("", _text(value)).casefold()


def _is_coach_question(text: str) -> bool:
    cleaned = _text(text)
    if not cleaned:
        return True
    if "…" in cleaned or "..." in cleaned:
        return True
    if _COACH_PREFIX_RE.search(cleaned):
        return True
    # 对学员的旁白指令，而非对角色说话
    coach_markers = ("学员", "建议追问", "本阶段", "考核点", "考察点未", "请完成")
    return any(marker in cleaned for marker in coach_markers)


def _to_speakable_question(raw: str, *, kind: str, target_name: str | None = None) -> str:
    """把方向种子改写成民警可对角色直接说出口的口语。"""
    cleaned = _text(raw)
    cleaned = re.sub(
        r"^(请立即|请先|请务必|请尽快|请具体说明|请核实|请确认|为推进处置[，,]?请说明|为推进|建议你|学员应|需要你|应当|必须先|确认|核实)",
        "",
        cleaned,
    )
    cleaned = cleaned.strip(" ：:，,。.")
    if not cleaned:
        cleaned = "刚才发生了什么"
    if cleaned.endswith(("？", "?")) and not _is_coach_question(cleaned):
        return cleaned[:_MAX_QUESTION_LEN]
    topic = cleaned[:16].rstrip("，。；、 ")
    address = f"{target_name}，" if target_name else ""
    if kind == _KIND_PLOT:
        if any(token in topic for token in ("伤", "救护", "医疗", "送医")):
            candidate = f"{address}现场有没有人受伤？要不要马上叫救护车？"
        elif any(token in topic for token in ("隔离", "隔开", "控制", "警告")):
            candidate = f"{address}你们先分开站好，谁再靠近一步我就不客气了？"
        else:
            candidate = f"{address}现在立刻说清楚，{topic}谁负责？"
    else:
        if any(token in topic for token in ("伤", "救护")):
            candidate = f"{address}有没有人受伤？"
        elif any(token in topic for token in ("动手", "打架", "冲突")):
            candidate = f"{address}刚才谁先动手的？"
        else:
            candidate = f"{address}{topic}是怎么回事？"
    if not candidate.endswith(("？", "?")):
        candidate = f"{candidate}？"
    return candidate[:_MAX_QUESTION_LEN]


def _stage_index(stages: list[dict[str, Any]], stage_name: str) -> int:
    target = _text(stage_name)
    for index, item in enumerate(stages):
        if _text(item.get("stage_name")) == target:
            return index
    return 0 if stages else -1


def _pick_stage(
    *,
    stages: list[dict[str, Any]],
    stage_name: str,
    stage_script: dict[str, Any] | None = None,
    fallback_stage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(stage_script, dict) and (
        not stage_name or _text(stage_script.get("stage_name")) in {"", stage_name}
    ):
        merged = dict(stage_script)
        if stage_name and not _text(merged.get("stage_name")):
            merged["stage_name"] = stage_name
        return merged
    for item in stages:
        if _text(item.get("stage_name")) == _text(stage_name):
            return dict(item)
    if isinstance(fallback_stage, dict) and fallback_stage:
        return dict(fallback_stage)
    return dict(stages[0]) if stages else {}


def _seed_directions(stage: dict[str, Any], expected_outcomes: list[str], missing: list[str]) -> list[str]:
    seeds: list[str] = []
    for key in ("recommended_prompts", "learner_actions", "role_pressure_points", "expected_stage_effects"):
        for item in stage.get(key) or []:
            text = _text(item if not isinstance(item, dict) else (item.get("label") or item.get("content") or item.get("text")))
            if text and text not in seeds:
                seeds.append(text)
    for item in missing + expected_outcomes:
        text = _text(item)
        if text and text not in seeds:
            seeds.append(text)
    return seeds[:8]


def _banned_keys(*groups: list[Any]) -> set[str]:
    banned: set[str] = set()
    for group in groups:
        for item in group or []:
            if isinstance(item, dict):
                key = _normalize_question_key(item.get("text") or item.get("content"))
            else:
                key = _normalize_question_key(item)
            if key:
                banned.add(key)
    return banned


def _category_for_kind(kind: str) -> str:
    return "快速发言" if kind == _KIND_HINT else "推进剧情"


class RecommendedQuestionsSkill:
    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    def execute(
        self,
        *,
        payload: dict[str, Any],
        training_result: dict[str, Any],
        role_intents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        missing = [_text(item) for item in (training_result.get("stage_completion_missing") or []) if _text(item)]
        scene = payload.get("scene_world") if isinstance(payload.get("scene_world"), dict) else {}
        stages = [item for item in (scene.get("stages") or payload.get("stages") or []) if isinstance(item, dict)]
        current_stage_name = _text(
            training_result.get("current_stage")
            or payload.get("current_stage")
            or (payload.get("stage") or {}).get("stage_name")
            or scene.get("current_stage")
        )
        stage_script = payload.get("current_stage_script") if isinstance(payload.get("current_stage_script"), dict) else {}
        # 阶段已推进时，必须以新阶段剧本为准，禁止继续吃旧阶段 seed。
        if training_result.get("stage_advanced") and current_stage_name:
            stage_script = next(
                (item for item in (payload.get("training_script_stages") or stages) if isinstance(item, dict) and _text(item.get("stage_name")) == current_stage_name),
                stage_script,
            )
        active_stage = _pick_stage(
            stages=stages,
            stage_name=current_stage_name,
            stage_script=stage_script,
            fallback_stage=payload.get("stage") if isinstance(payload.get("stage"), dict) else {},
        )
        stage_idx = _stage_index(stages, current_stage_name or _text(active_stage.get("stage_name")))
        total_stages = max(len(stages), 1)
        if stage_idx < 0:
            rhythm = "开端"
        elif stage_idx <= max(0, total_stages // 3):
            rhythm = "开端"
        elif stage_idx >= max(0, total_stages - 1 - max(0, total_stages // 3)):
            rhythm = "收尾"
        else:
            rhythm = "发展"

        expected_outcomes = [_text(item) for item in (payload.get("expected_outcomes") or []) if _text(item)]
        seed_directions = _seed_directions(active_stage, expected_outcomes, missing)
        personas = [item for item in payload.get("personas") or [] if isinstance(item, dict)]
        if not missing and not seed_directions and not personas and not _text(payload.get("plot_arc")):
            return []

        previous_items = [
            item for item in (payload.get("previous_recommended_question_items") or [])
            if isinstance(item, dict)
        ]
        previous_texts = [
            _text(item) for item in (payload.get("previous_recommended_question_texts") or []) if _text(item)
        ]
        served_texts = [
            _text(item) for item in (payload.get("served_recommended_question_texts") or []) if _text(item)
        ]
        used_texts = [
            _text(item) for item in (payload.get("used_recommended_question_texts") or []) if _text(item)
        ]
        banned = _banned_keys(previous_items, previous_texts, served_texts, used_texts)
        history = list(payload.get("public_history") or payload.get("recent_dialogue") or [])
        for item in history:
            if not isinstance(item, dict):
                continue
            if item.get("role") in {"user", "action"}:
                key = _normalize_question_key(item.get("content"))
                if key:
                    banned.add(key)

        request_payload = {
            "plot_arc": _text(payload.get("plot_arc") or scene.get("plot_arc")),
            "training_goal": _text(payload.get("training_goal")),
            "expected_outcomes": expected_outcomes[:6],
            "plot_rhythm": rhythm,
            "stage_index": stage_idx,
            "stage_count": total_stages,
            "current_stage": {
                "stage_name": _text(active_stage.get("stage_name") or current_stage_name),
                "stage_goal": _text(active_stage.get("stage_goal")),
                "role_pressure_points": active_stage.get("role_pressure_points") or [],
                "expected_stage_effects": active_stage.get("expected_stage_effects") or [],
                "learner_actions": active_stage.get("learner_actions") or [],
            },
            "direction_seeds": seed_directions,
            "missing_assessment_items": missing,
            "completed_point_ids": training_result.get("completed_point_ids") or [],
            "banned_question_texts": list(dict.fromkeys([
                *[_text(item.get("text")) for item in previous_items if _text(item.get("text"))],
                *previous_texts,
                *served_texts[-20:],
                *used_texts[-20:],
            ]))[:40],
            "public_history": history[-16:],
            "roles": [
                {"name": item.get("name"), "role": item.get("role"), "person_id": item.get("person_id")}
                for item in personas
            ],
            "role_intents": role_intents,
        }
        try:
            raw = self.llm.complete_json(
                system=(
                    "你是警情实训建议提问节点。必须严格按训练剧本当前节点节奏生成全新一批问句。"
                    "输出 JSON：questions 数组，恰好 4 条；其中 kind=hint 与 kind=plot_advance 各 2 条。"
                    "硬性要求：text 必须是学员（民警）对现场角色可直接说出口的第一人称口语对白，"
                    "点选后填入输入框就能发送。正面例子：“现场有没有人受伤？”“你们谁先动手的？”“先退后，把刀放下。”"
                    "严禁教练口吻/旁白指令，反例：“请立即确认…”，“请具体说明与…有关的情况”，“为推进处置，请说明…”，“建议你先核实”。"
                    "hint：短、好开口的核实/安抚问句；plot_advance：推动当前剧情节点的处置口令或关键追问。"
                    "必须指定合理在场目标角色 target_role_name；不得泄露未披露事实、标准答案或角色私有记忆。"
                    "严禁复用、改写 banned_question_texts；不得照抄 direction_seeds 原文；单条不超过 56 字，不要省略号。"
                    "每条含 text、kind、category、priority、target_role_name、related_point_id。"
                ),
                user=json.dumps(request_payload, ensure_ascii=False),
                temperature=0.65,
                max_tokens=1200,
                max_attempts=1,
            )
            rows = raw.get("questions") if isinstance(raw.get("questions"), list) else []
        except WorkflowServiceError:
            rows = []

        role_names = {_text(item.get("name")) for item in personas if _text(item.get("name"))}
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_item in rows:
            if not isinstance(raw_item, dict):
                continue
            text = _text(raw_item.get("text"))
            if _is_coach_question(text):
                continue
            if len(text) > _MAX_QUESTION_LEN:
                text = text[:_MAX_QUESTION_LEN].rstrip("，。；、 ") + "？"
            key = _normalize_question_key(text)
            if not text or not key or key in seen or key in banned:
                continue
            kind = _text(raw_item.get("kind") or "").casefold()
            if kind not in _VALID_KINDS:
                category = _text(raw_item.get("category"))
                kind = _KIND_PLOT if any(token in category for token in ("推进", "剧情", "处置", "收尾")) else _KIND_HINT
            target = _text(raw_item.get("target_role_name"))
            if not text.endswith(("？", "?")) and "。" not in text:
                text = f"{text}？"
            results.append({
                "text": text,
                "kind": kind,
                "category": _text(raw_item.get("category")) or _category_for_kind(kind),
                "priority": _text(raw_item.get("priority")) or ("high" if kind == _KIND_PLOT else "medium"),
                "target_role_name": target if target in role_names else None,
                "related_point_id": _text(raw_item.get("related_point_id")),
            })
            seen.add(key)
            if len(results) >= 4:
                break

        if self._has_both_kinds(results):
            return results[:4]
        return self._synthesize_batch(
            personas=personas,
            active_stage=active_stage,
            missing=missing,
            expected_outcomes=expected_outcomes,
            banned=banned | seen,
            prefer_existing=results,
            rhythm=rhythm,
        )

    @staticmethod
    def _has_both_kinds(items: list[dict[str, Any]]) -> bool:
        kinds = {item.get("kind") for item in items}
        return _KIND_HINT in kinds and _KIND_PLOT in kinds and len(items) >= 4

    def _synthesize_batch(
        self,
        *,
        personas: list[dict[str, Any]],
        active_stage: dict[str, Any],
        missing: list[str],
        expected_outcomes: list[str],
        banned: set[str],
        prefer_existing: list[dict[str, Any]],
        rhythm: str,
    ) -> list[dict[str, Any]]:
        """LLM 失败或种类不全时，按当前阶段方向现场合成可说出口的口语，绝不回吐上一批旧题。"""
        primary = next((item for item in personas if item.get("is_primary")), personas[0] if personas else {})
        target = _text(primary.get("name")) or None
        stage_goal = _text(active_stage.get("stage_goal")) or "现场情况"
        pressures = [_text(item) for item in (active_stage.get("role_pressure_points") or []) if _text(item)]
        actions = [_text(item) for item in (active_stage.get("learner_actions") or []) if _text(item)]
        hint_sources = [
            *missing[:2],
            *pressures[:2],
            *expected_outcomes[:2],
            "有没有人受伤",
            "刚才谁先动手",
        ]
        plot_sources = [
            *actions[:2],
            *pressures[1:3],
            *expected_outcomes[1:3],
            "先把两边隔开",
            f"{stage_goal}",
        ]

        def _make(text: str, kind: str) -> dict[str, Any] | None:
            cleaned = _to_speakable_question(text, kind=kind, target_name=target)
            if _is_coach_question(cleaned):
                return None
            key = _normalize_question_key(cleaned)
            if not key or key in banned:
                return None
            banned.add(key)
            return {
                "text": cleaned,
                "kind": kind,
                "category": _category_for_kind(kind),
                "priority": "high" if kind == _KIND_PLOT else "medium",
                "target_role_name": target,
                "related_point_id": "",
            }

        results = [
            item for item in prefer_existing
            if item.get("kind") in _VALID_KINDS and not _is_coach_question(str(item.get("text") or ""))
        ]
        for text in hint_sources:
            if sum(1 for item in results if item.get("kind") == _KIND_HINT) >= 2:
                break
            item = _make(text, _KIND_HINT)
            if item:
                results.append(item)
        for text in plot_sources:
            if sum(1 for item in results if item.get("kind") == _KIND_PLOT) >= 2:
                break
            item = _make(text, _KIND_PLOT)
            if item:
                results.append(item)
        while sum(1 for item in results if item.get("kind") == _KIND_HINT) < 2:
            item = _make(f"现场情况{len(results)+1}", _KIND_HINT)
            if not item:
                break
            results.append(item)
        while sum(1 for item in results if item.get("kind") == _KIND_PLOT) < 2:
            item = _make(f"先稳住现场{len(results)+1}", _KIND_PLOT)
            if not item:
                break
            results.append(item)
        ordered = [item for item in results if item.get("kind") == _KIND_HINT][:2]
        ordered.extend([item for item in results if item.get("kind") == _KIND_PLOT][:2])
        return ordered[:4]
