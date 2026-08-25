from __future__ import annotations

import re
import hashlib
from typing import Any

from ai_workflow_service.contracts import CaseWorld, Person
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.domain.case_import_quality import memory_quality


class PersonMemorySkill:
    def __init__(self, llm: DeepSeekAdapter):
        self.llm = llm

    @staticmethod
    def _initial_state(value: Any, person_id: str, role: str = "") -> dict[str, int]:
        raw = value if isinstance(value, dict) else {}
        digest = hashlib.sha256(person_id.encode("utf-8")).digest()
        role_defaults = {
            "嫌疑人": {"emotion": 64, "cooperation": 22, "risk": 72, "clarity": 48},
            "被害人": {"emotion": 76, "cooperation": 42, "risk": 58, "clarity": 52},
            "受害人": {"emotion": 76, "cooperation": 42, "risk": 58, "clarity": 52},
            "证人": {"emotion": 48, "cooperation": 38, "risk": 36, "clarity": 62},
            "报警人": {"emotion": 68, "cooperation": 48, "risk": 46, "clarity": 56},
        }
        base = role_defaults.get(str(role or "").strip(), {
            "emotion": 42 + digest[0] % 17,
            "cooperation": 38 + digest[1] % 17,
            "risk": 32 + digest[2] % 17,
            "clarity": 48 + digest[3] % 17,
        })
        result: dict[str, int] = {}
        for key, fallback in base.items():
            try:
                result[key] = max(0, min(100, int(raw.get(key, fallback))))
            except (TypeError, ValueError):
                result[key] = fallback
        return result

    @staticmethod
    def _ledger_rows(facts: list[Any]) -> list[dict[str, Any]]:
        rows = []
        for fact in facts:
            content = str(getattr(fact, "content", "") or "").strip()
            fact_id = str(getattr(fact, "fact_id", "") or "").strip()
            if not content:
                continue
            rows.append({
                "knowledge_id": fact_id or f"K{len(rows) + 1}",
                "fact_id": fact_id,
                "content": content,
                "statement": content,
                "certainty": str(getattr(fact, "status", "") or "source_supported"),
                "source_refs": list(getattr(fact, "source_refs", None) or []),
            })
        return rows

    def execute(self, world: CaseWorld, complete_story: str) -> tuple[CaseWorld, list[dict[str, Any]], dict]:
        try:
            result = self.llm.complete_json(
                system=("根据案件剧情和事实账本，为剧情中出现的全部角色构建完整训练档案。"
                        "必须正向给出标准化参数，不得留空后依赖后置质量拦截。"
                        "排除法官、检察官、辩护人、审判员、书记员等非警情对话角色。"
                        "只输出 JSON："
                        "{persons:[{person_id,name,role,speakable,training_relevance,traits,speaking_style,goals,"
                        "facts_known,facts_hidden,initial_state:{emotion,cooperation,risk,clarity},"
                        "memories:[{fact_id,memory_type,statement,source_quote,certainty}],response_constraints:[]}]}。"
                        "每个角色都必须给出完整 initial_state（0-100 整数四维）和至少一条 memories；"
                        "memories.statement 必须是原文内容，不得只输出 fact_id 或序号。"
                        "memory_type 只能是 direct_statement、personal_experience、direct_observation、hearsay、later_learned。"
                        "每条记忆必须引用给定 fact_id，statement 只能表达本人已知范围。"),
                user=complete_story + "\n事实账本：" + str([fact.model_dump(mode="json") for fact in world.facts]),
                max_tokens=7000, max_attempts=1,
            )
        except WorkflowServiceError as exc:
            if exc.code not in {"MODEL_REQUEST_FAILED", "MODEL_NOT_CONFIGURED"}:
                raise
            result = {}
        valid_fact_ids = {fact.fact_id for fact in world.facts}
        persons = []
        raw_by_person_id: dict[str, dict[str, Any]] = {}
        for index, raw in enumerate(result.get("persons") or []):
            item = raw if isinstance(raw, dict) else {}
            person_id = str(item.get("person_id") or f"P{index + 1:03d}")
            role = str(item.get("role") or "相关人员")
            person = Person(
                person_id=person_id, name=str(item.get("name") or "未知人员"),
                role=role,
                facts_known=[str(v) for v in item.get("facts_known") or [] if str(v) in valid_fact_ids],
                facts_hidden=[str(v) for v in item.get("facts_hidden") or [] if str(v) in valid_fact_ids],
                speakable=bool(item.get("speakable", True)),
                training_relevance=str(item.get("training_relevance") or "dialogue"),
                initial_state=self._initial_state(item.get("initial_state"), person_id, role),
                traits=[str(value) for value in item.get("traits") or [] if str(value).strip()] or [f"{role}现场表现"],
                speaking_style=str(item.get("speaking_style") or "自然口语"),
                goals=[str(value) for value in item.get("goals") or [] if str(value).strip()] or ["按本人立场自然回应"],
            )
            persons.append(person)
            raw_by_person_id[person_id] = item
        if not persons:
            excluded = {"办案机关", "鉴定机构", "公安机关", "人民法院", "检察机关", "辩护人", "审判员", "书记员", "公诉人"}
            names = list(dict.fromkeys(
                name for fact in world.facts for name in fact.known_by
                if name and name in complete_story and name not in excluded and len(name) <= 8
            ))[:12]
            if not names:
                names = list(dict.fromkeys(
                    name.strip("，。；：、 ")
                    for values in re.findall(
                        r"(?:报警人|报案人|被害人|受害人|证人|当事人|嫌疑人|被告人)[：为是称叫]?([\u4e00-\u9fa5某甲乙丙丁0-9]{2,10}(?:、[\u4e00-\u9fa5某甲乙丙丁0-9]{2,10})*)",
                        complete_story,
                    )
                    for name in values.split("、")
                    if name.strip("，。；：、 ") not in excluded
                ))[:12]
            persons = [Person(
                person_id=f"P{i + 1:03d}", name=name,
                facts_known=[fact.fact_id for fact in world.facts if name in fact.known_by],
                initial_state=self._initial_state({}, f"P{i + 1:03d}"),
            ) for i, name in enumerate(names)]
        if not persons:
            persons = [Person(
                person_id="P001", name="报警人",
                facts_known=[fact.fact_id for fact in world.facts if "报警人" in fact.known_by],
                initial_state=self._initial_state({}, "P001", "报警人"),
            )]
        persons = [
            person if person.facts_known else person.model_copy(update={
                "facts_known": [fact.fact_id for fact in world.facts if person.name in fact.known_by]
            })
            for person in persons
        ]
        updated = world.model_copy(update={"persons": persons})
        memories = []
        for person in persons:
            raw_person = raw_by_person_id.get(person.person_id, {})
            inferred_known = [fact.fact_id for fact in world.facts if person.name in fact.known_by]
            known = set(person.facts_known or inferred_known)
            facts = [fact for fact in world.facts if fact.fact_id in known or person.name in fact.known_by]
            if not facts:
                facts = list(world.facts[:3])
            fact_by_id = {fact.fact_id: fact for fact in facts}
            role_memories = []
            for raw_memory in raw_person.get("memories") or []:
                if not isinstance(raw_memory, dict):
                    continue
                fact_id = str(raw_memory.get("fact_id") or "")
                fact = fact_by_id.get(fact_id)
                if not fact:
                    continue
                statement = str(raw_memory.get("statement") or fact.content).strip()
                if not statement or statement == fact_id:
                    statement = fact.content
                role_memories.append({
                    "memory_id": f"{person.person_id}-M{len(role_memories) + 1}",
                    "memory_type": str(raw_memory.get("memory_type") or "personal_experience"),
                    "statement": statement,
                    "content": statement,
                    "quote": str(raw_memory.get("source_quote") or fact.content),
                    "certainty": str(raw_memory.get("certainty") or fact.status),
                    "fact_id": fact_id,
                    "source_refs": fact.source_refs,
                })
            covered_fact_ids = {item["fact_id"] for item in role_memories}
            for fact in facts:
                if fact.fact_id in covered_fact_ids:
                    continue
                role_memories.append({
                    "memory_id": f"{person.person_id}-M{len(role_memories) + 1}",
                    "memory_type": "personal_experience",
                    "statement": fact.content,
                    "content": fact.content,
                    "quote": fact.content,
                    "certainty": fact.status,
                    "fact_id": fact.fact_id,
                    "source_refs": fact.source_refs,
                })
            memories.append({
                "person_id": person.person_id, "name": person.name,
                "initial_state": person.initial_state.model_dump(mode="json"),
                "traits": person.traits,
                "speaking_style": person.speaking_style,
                "goals": person.goals,
                "role_memories": role_memories,
                "knowledge_ledger": self._ledger_rows(facts),
                "response_constraints": list(raw_person.get("response_constraints") or ["只依据本人记忆、已知事实和本轮公开信息回答。"]),
            })
        return updated, memories, memory_quality(updated.persons, memories)
