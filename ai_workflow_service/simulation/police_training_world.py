from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from ai_workflow_service.contracts import Fact, Persona
from ai_workflow_service.domain.four_dimensional_state import normalize_state


_DISCLOSURE_STOP_WORDS = {
    "什么", "怎么", "是否", "这个", "那个", "事情", "情况", "当时", "已经", "没有", "知道", "进行",
}


@dataclass
class PoliceTrainingWorld:
    scene_id: str
    current_stage: str = ""
    rules: list[str] = field(default_factory=list)
    interventions: list[dict[str, Any]] = field(default_factory=list)

    def applicable_interventions(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        elapsed = int(context.get("elapsed_seconds") or 0)
        return [item for item in self.interventions if elapsed >= int(item.get("after_seconds") or 0)]

    @staticmethod
    def _trigger_terms(fact: Fact) -> list[str]:
        explicit = fact.disclosure_policy.get("trigger_terms")
        if isinstance(explicit, list):
            return [str(item).strip() for item in explicit if str(item).strip()]
        chunks = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", fact.content)
        terms: list[str] = []
        for chunk in chunks:
            if chunk in _DISCLOSURE_STOP_WORDS:
                continue
            if len(chunk) <= 8:
                terms.append(chunk)
            else:
                terms.extend(chunk[index:index + 4] for index in range(0, len(chunk) - 3, 3))
        return list(dict.fromkeys(terms))[:12]

    @classmethod
    def _directly_asked(cls, learner_input: str, fact: Fact) -> bool:
        text = learner_input.strip()
        if not text:
            return False
        if any(term in text for term in cls._trigger_terms(fact)):
            return True
        fact_pairs = {fact.content[index:index + 2] for index in range(max(0, len(fact.content) - 1))}
        input_pairs = {text[index:index + 2] for index in range(max(0, len(text) - 1))}
        return len(fact_pairs & input_pairs) >= 2

    def allowed_fact_ids(
        self,
        persona: Persona,
        facts: list[Fact],
        learner_input: str,
        *,
        revealed_fact_ids: set[str] | None = None,
    ) -> set[str]:
        known = set(persona.known_fact_ids)
        hidden = set(persona.hidden_fact_ids)
        revealed = revealed_fact_ids or set()
        allowed: set[str] = set()
        state = normalize_state(persona.state.model_dump())
        for fact in facts:
            if fact.fact_id not in known:
                continue
            policy = fact.disclosure_policy if isinstance(fact.disclosure_policy, dict) else {}
            if fact.secret and not bool(policy.get("allow_secret", False)):
                continue
            if fact.fact_id not in hidden:
                allowed.add(fact.fact_id)
                continue
            stages = {str(item) for item in policy.get("stages") or []}
            prerequisites = {str(item) for item in policy.get("required_fact_ids") or []}
            if stages and self.current_stage not in stages:
                continue
            if prerequisites and not prerequisites.issubset(revealed):
                continue
            if state["cooperation"] < int(policy.get("min_cooperation", 65)):
                continue
            if state["risk"] > int(policy.get("max_risk", 70)):
                continue
            if state["clarity"] < int(policy.get("min_clarity", 40)):
                continue
            if bool(policy.get("require_direct_question", True)) and not self._directly_asked(learner_input, fact):
                continue
            allowed.add(fact.fact_id)
        return allowed

    def select_actors(
        self,
        personas: list[Persona],
        learner_input: str,
        *,
        target_role_name: str = "",
        max_actors: int = 6,
    ) -> list[Persona]:
        target = target_role_name.strip()
        normalized_input = learner_input.strip()

        def score(item: tuple[int, Persona]) -> tuple[int, int, int, int]:
            index, persona = item
            named = bool(persona.name and persona.name in normalized_input)
            memory_text = " ".join(
                str(memory.get("statement") or memory.get("content") or memory.get("quote") or "")
                for memory in persona.role_memories
                if isinstance(memory, dict)
            )
            tokens = {token for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,8}", normalized_input)}
            relevance = sum(1 for token in tokens if token in memory_text)
            return (
                0 if target and persona.name == target else 1,
                0 if named else 1,
                0 if persona.is_primary else 1,
                -relevance * 1000 + index,
            )

        ordered = [persona for _, persona in sorted(enumerate(personas), key=score)]
        return ordered[:max(1, max_actors)]
