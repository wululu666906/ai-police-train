"""Scene engine: merge multi-role outputs into consecutive reply_turns (bubbles).

Each role may contribute 1-8 utterances in one burst before the student speaks again.
"""

from __future__ import annotations

from typing import Any, Optional

import models
from .multi_role_service import _role_display_name


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clamp_score(value: Any, fallback: int = 50) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0, min(100, numeric))


def _is_meaningful_fact(value: Any) -> bool:
    clean = _text(value)
    return bool(clean) and clean.lower() not in {"null", "none", "无", "没有"}


def consolidate_scene_conversation(
    *,
    director_plan: dict[str, Any],
    actor_outputs: list[dict[str, Any]],
    role_snapshots: dict[str, dict[str, int]],
    previous_primary_role: Optional[models.Role] = None,
) -> dict[str, Any]:
    reply_turns: list[dict[str, Any]] = []
    active_role_ids: list[int] = []
    new_facts: list[str] = []
    inner_thoughts: list[str] = []
    role_contracts: dict[str, Any] = {}

    for actor in actor_outputs:
        role = actor.get("role")
        role_id = actor.get("speaker_role_id") or getattr(role, "id", None)
        speaker_name = actor.get("speaker_name") or _role_display_name(role)
        if role_id:
            active_role_ids.append(int(role_id))
        snap_key = str(role_id) if role_id is not None else ""
        if snap_key:
            role_snapshots[snap_key] = actor.get("updated_snapshot") or role_snapshots.get(snap_key) or {}
            contract = actor.get("state_contract")
            if isinstance(contract, dict):
                role_contracts[snap_key] = contract

        thought = _text(actor.get("inner_thought"))
        if thought:
            inner_thoughts.append(f"{speaker_name}：{thought}")

        fact = actor.get("new_fact_revealed")
        if _is_meaningful_fact(fact):
            new_facts.append(_text(fact))

        first = True
        for utterance in actor.get("utterances") or []:
            content = _text(utterance.get("content") if isinstance(utterance, dict) else utterance)
            if not content:
                continue
            reply_turns.append(
                {
                    "speaker_name": speaker_name,
                    "speaker_role_id": role_id,
                    "content": content,
                    "inner_thought": thought if first else None,
                    "participation": actor.get("participation"),
                    "delivery": _text(utterance.get("delivery")) if isinstance(utterance, dict) else "normal",
                }
            )
            first = False

    primary_role = previous_primary_role
    primary_snap: dict[str, int] = {"emotion": 50, "cooperation": 30, "risk": 50, "clarity": 50}
    if actor_outputs:
        first_actor = actor_outputs[0]
        primary_role = first_actor.get("role") or primary_role
        key = str(first_actor.get("speaker_role_id") or "")
        primary_snap = role_snapshots.get(key) or first_actor.get("updated_snapshot") or primary_snap
    elif previous_primary_role:
        key = str(previous_primary_role.id)
        primary_snap = role_snapshots.get(key) or primary_snap

    active_snaps = [role_snapshots[str(rid)] for rid in active_role_ids if str(rid) in role_snapshots]
    if active_snaps:
        scene_snapshot = {
            "cooperation": round(sum(item.get("cooperation", 30) for item in active_snaps) / len(active_snaps)),
            "risk": max(item.get("risk", 50) for item in active_snaps),
            "clarity": round(sum(item.get("clarity", 50) for item in active_snaps) / len(active_snaps)),
        }
    else:
        scene_snapshot = {
            "cooperation": primary_snap.get("cooperation", 30),
            "risk": primary_snap.get("risk", 50),
            "clarity": primary_snap.get("clarity", 50),
        }

    return {
        "director_plan": director_plan,
        "interaction_mode": _text(director_plan.get("interaction_mode")) or "mixed",
        "routing_summary": _text(director_plan.get("routing_summary")) or "",
        "addressing_warning": _text(director_plan.get("addressing_warning")) or "",
        "reply_turns": reply_turns,
        "reply_sequence": [item["content"] for item in reply_turns],
        "response": reply_turns[0]["content"] if reply_turns else "……",
        "inner_thought": inner_thoughts[0] if inner_thoughts else "现场仍在博弈。",
        "primary_role": primary_role,
        "active_role_ids": active_role_ids,
        "role_state_snapshots": role_snapshots,
        "scene_state_snapshot": scene_snapshot,
        "updated_emotion": primary_snap.get("emotion", 50),
        "updated_trust": scene_snapshot.get("cooperation", 30),
        "updated_cooperation": scene_snapshot.get("cooperation", 30),
        "updated_risk": scene_snapshot.get("risk", 50),
        "updated_clarity": scene_snapshot.get("clarity", 50),
        "new_fact_revealed": new_facts[0] if new_facts else None,
        "is_stage_completed": False,
        "follow_up_response": None,
        "active_speakers": [
            {"id": item.get("speaker_role_id"), "name": item.get("speaker_name")}
            for item in reply_turns
            if item.get("speaker_name")
        ],
        "role_contracts": role_contracts,
        "state_contract": (
            role_contracts.get(str(getattr(primary_role, "id", "") or ""))
            if primary_role
            else None
        ),
    }
