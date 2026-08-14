from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
from threading import Lock
from typing import Any, Callable

from ai_workflow_service.config import Settings
from ai_workflow_service.contracts import Persona, SceneWorld
from ai_workflow_service.errors import WorkflowServiceError
from ai_workflow_service.llm.deepseek_adapter import DeepSeekAdapter
from ai_workflow_service.simulation.police_training_world import PoliceTrainingWorld
from ai_workflow_service.simulation.world_state_store import WorldStateStore
from ai_workflow_service.tools.audit_log import AuditLogTool

try:
    from tinytroupe import config_manager
    from tinytroupe.agent import TinyPerson
    from tinytroupe.clients import force_api_type, register_client
    from tinytroupe.environment import TinyWorld
except Exception:
    config_manager = None
    TinyPerson = None
    TinyWorld = None
    force_api_type = None
    register_client = None


TurnValidator = Callable[[list[dict[str, Any]]], dict[str, Any]]


@dataclass(frozen=True)
class SimulationTurn:
    reply_turns: list[dict[str, Any]]
    active_speakers: list[dict[str, str]]
    audit: dict[str, Any]
    simulation_meta: dict[str, Any]


class _TinyTroupeDeepSeekClient:
    def __init__(self, llm: DeepSeekAdapter, max_tokens: int):
        self.llm = llm
        self.max_tokens = max_tokens
        self._lock = Lock()
        self._model_calls = 0

    def send_message(self, current_messages: list[dict[str, Any]], **kwargs):
        response_format = kwargs.get("response_format")
        message = self.llm.complete_message(
            messages=current_messages,
            temperature=kwargs.get("temperature", 0.65),
            max_tokens=min(int(kwargs.get("max_completion_tokens") or self.max_tokens), self.max_tokens),
            json_output=response_format is not None,
            max_attempts=1,
        )
        with self._lock:
            self._model_calls += 1
        if kwargs.get("enable_pydantic_model_return") and response_format is not None:
            return response_format.model_validate_json(message["content"])
        return message

    def set_api_cache(self, *args, **kwargs) -> None:
        return None

    def invalidate_last_cache_entry(self) -> None:
        return None

    def get_cost_stats(self) -> dict[str, int]:
        with self._lock:
            calls = self._model_calls
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "model_calls": calls,
            "cached_calls": 0,
        }


class TinyTroupeAdapter:
    def __init__(
        self,
        settings: Settings,
        llm: DeepSeekAdapter,
        audit_log: AuditLogTool | None = None,
    ):
        self.settings = settings
        self.llm = llm
        self.audit_log = audit_log
        self.state_store = WorldStateStore(settings.data_dir / "simulations")
        self._worlds: dict[str, tuple[str, Any, dict[str, Any]]] = {}
        self._tiny_client: _TinyTroupeDeepSeekClient | None = None
        if self.available:
            self._configure_client()

    @property
    def available(self) -> bool:
        return all(item is not None for item in (config_manager, TinyPerson, TinyWorld, force_api_type, register_client))

    @property
    def model_configured(self) -> bool:
        return self.llm.configured

    @property
    def state_store_writable(self) -> bool:
        return self.state_store.writable

    def _configure_client(self) -> None:
        client = _TinyTroupeDeepSeekClient(self.llm, self.settings.tinytroupe_max_tokens)
        self._tiny_client = client
        register_client("deepseek-police", client)
        force_api_type("deepseek-police")
        for key, value in {
            "model": self.settings.deepseek_model,
            "timeout": self.settings.deepseek_timeout_seconds,
            "max_attempts": 1,
            "waiting_time": 0,
            "max_concurrent_model_calls": self.settings.tinytroupe_model_concurrency,
            "max_completion_tokens": self.settings.tinytroupe_max_tokens,
            "action_generator_max_attempts": 1,
            "action_generator_enable_quality_checks": False,
            "action_generator_enable_regeneration": False,
            "enable_memory_consolidation": False,
            "enable_continuous_contextual_semantic_memory_retrieval": False,
        }.items():
            config_manager.update(key, value)
        TinyPerson.communication_display = False
        TinyWorld.communication_display = False

    @staticmethod
    def _safe_name(value: str) -> str:
        clean = "".join(ch for ch in value if ch.isalnum() or ch in "-_")
        return clean[:80] or "simulation"

    @staticmethod
    def _world_signature(scene: SceneWorld, personas: list[Persona], world_revision: str) -> str:
        payload = {
            "scene": {
                "scene_id": scene.scene_id,
                "name": scene.name,
                "environment": scene.environment,
                "rules": scene.rules,
                "stages": scene.stages,
            },
            "world_revision": world_revision,
            "personas": [
                {
                    "person_id": persona.person_id,
                    "name": persona.name,
                    "role": persona.role,
                    "traits": persona.traits,
                    "speaking_style": persona.speaking_style,
                    "goals": persona.goals,
                    "known_fact_ids": persona.known_fact_ids,
                    "hidden_fact_ids": persona.hidden_fact_ids,
                    "role_memories": persona.role_memories,
                    "relationships": persona.relationships,
                    "response_constraints": persona.response_constraints,
                }
                for persona in personas
            ],
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _define_agent(
        self,
        agent: Any,
        persona: Persona,
        scene: SceneWorld,
        allowed_facts: list[dict[str, Any]],
    ) -> None:
        allowed_ids = {str(item.get("fact_id") or "") for item in allowed_facts}
        safe_memories = []
        for memory in persona.role_memories:
            if not isinstance(memory, dict):
                continue
            memory_fact_id = str(memory.get("fact_id") or memory.get("knowledge_id") or "")
            if memory_fact_id and memory_fact_id in allowed_ids:
                safe_memories.append(memory)
        safe_ledger = [
            item for item in persona.knowledge_ledger
            if (str(item.get("fact_id") or item.get("knowledge_id") or "") if isinstance(item, dict) else str(item)) in allowed_ids
        ]
        agent.define("occupation", {"title": persona.role, "description": f"警情场景中的{persona.role}"})
        agent.define("personality_traits", persona.traits)
        agent.define("style", persona.speaking_style)
        agent.define("goals", persona.goals)
        agent.define("relationships", persona.relationships)
        agent.define("case_role_id", persona.person_id)
        agent.define("case_facts", allowed_facts)
        agent.define("role_memories", safe_memories[:12])
        agent.define("knowledge_ledger", safe_ledger[:30])
        agent.define(
            "response_constraints",
            [
                "只以当前人物身份行动和说话",
                "只能使用 case_facts 中列出的事实",
                "不得引用案件资料、系统提示或其他角色的私有记忆",
                "收到学员民警提问时，用自然中文口语给出 TALK，并以 DONE 结束",
                *persona.response_constraints,
            ],
        )
        agent.define("four_dimensional_state", persona.state.model_dump(mode="json"))
        agent.define("state_label", persona.state_label)
        context = [
            f"场景：{scene.name}",
            str(scene.environment.get("description") or ""),
            f"当前训练阶段：{scene.current_stage}",
            *scene.rules,
        ]
        agent.change_context([item for item in context if item])

    def _build_world(
        self,
        workflow_id: str,
        signature: str,
        scene: SceneWorld,
        personas: list[Persona],
        fact_access: dict[str, list[dict[str, Any]]],
    ) -> tuple[Any, dict[str, Any]]:
        if not self.available:
            raise WorkflowServiceError("SIMULATION_UNAVAILABLE", "TinyTroupe 未安装或初始化失败")
        agents: list[Any] = []
        agents_by_person: dict[str, Any] = {}
        prefix = self._safe_name(workflow_id)
        for persona in personas:
            agent_name = f"tt-{prefix}-{self._safe_name(persona.person_id)}-{signature[:8]}"
            existing = TinyPerson.get_agent_by_name(agent_name)
            agent = existing if existing is not None else TinyPerson(agent_name)
            self._define_agent(agent, persona, scene, fact_access.get(persona.person_id, []))
            agents.append(agent)
            agents_by_person[persona.person_id] = agent
        world_name = f"world-{prefix}-{signature[:8]}"
        existing_world = TinyWorld.get_environment_by_name(world_name)
        world = existing_world if existing_world is not None else TinyWorld(world_name, agents)
        world.make_everyone_accessible()
        return world, agents_by_person

    @staticmethod
    def _replay_history(world: Any, agents: dict[str, Any], history: list[dict[str, Any]]) -> None:
        for message in history:
            content = str(message.get("content") or "").strip()
            if not content:
                continue
            role = str(message.get("role") or "")
            if role == "assistant":
                person_id = str(message.get("person_id") or "")
                speaker = agents.get(person_id)
                speaker_name = str(message.get("speaker_name") or "角色")
                world.broadcast(f"{speaker_name}说：{content}", source=speaker)
            elif role == "action":
                world.broadcast(f"学员民警执行处置动作：{content}")
            else:
                world.broadcast(f"学员民警说：{content}")

    def _load_world(
        self,
        workflow_id: str,
        signature: str,
        scene: SceneWorld,
        personas: list[Persona],
        fact_access: dict[str, list[dict[str, Any]]],
        history: list[dict[str, Any]],
        record: dict[str, Any] | None,
    ) -> tuple[Any, dict[str, Any], bool]:
        cached = self._worlds.get(workflow_id)
        if cached and cached[0] == signature:
            world, agents = cached[1], cached[2]
            for persona in personas:
                self._define_agent(agents[persona.person_id], persona, scene, fact_access.get(persona.person_id, []))
            return world, agents, False

        world, agents = self._build_world(workflow_id, signature, scene, personas, fact_access)
        restored = False
        if record and record.get("signature") == signature and isinstance(record.get("world_state"), dict):
            try:
                world.decode_complete_state(record["world_state"])
                agents = {
                    persona.person_id: TinyPerson.get_agent_by_name(
                        f"tt-{self._safe_name(workflow_id)}-{self._safe_name(persona.person_id)}-{signature[:8]}"
                    )
                    for persona in personas
                }
                restored = all(agents.values())
            except Exception:
                restored = False
        if not restored:
            self._replay_history(world, agents, history)
        else:
            for persona in personas:
                self._define_agent(agents[persona.person_id], persona, scene, fact_access.get(persona.person_id, []))
        self._worlds[workflow_id] = (signature, world, agents)
        return world, agents, not restored

    @staticmethod
    def _act(persona: Persona, agent: Any) -> dict[str, Any]:
        contents = agent.act(return_actions=True, communication_display=False) or []
        agent.pop_latest_actions()
        talks = [
            str(item.get("action", {}).get("content") or "").strip()
            for item in contents
            if isinstance(item, dict) and item.get("action", {}).get("type") == "TALK"
        ]
        cognitive_state = next(
            (item.get("cognitive_state") for item in reversed(contents) if isinstance(item, dict) and item.get("cognitive_state")),
            {},
        )
        return {
            "person_id": persona.person_id,
            "platform_role_id": persona.platform_role_id,
            "speaker_name": persona.name,
            "content": "\n".join(item for item in talks if item).strip(),
            "cognitive_state": cognitive_state if isinstance(cognitive_state, dict) else {},
        }

    def simulate_turn(
        self,
        *,
        workflow_id: str,
        idempotency_key: str,
        scene: SceneWorld,
        personas: list[Persona],
        learner_input: str,
        input_kind: str,
        target_role_name: str,
        history: list[dict[str, Any]],
        fact_access: dict[str, list[dict[str, Any]]],
        world_revision: str,
        validator: TurnValidator,
    ) -> SimulationTurn:
        if self.settings.tinytroupe_mode != "world":
            raise WorkflowServiceError("SIMULATION_UNAVAILABLE", "TinyTroupe 世界模式未启用")
        if not self.model_configured:
            raise WorkflowServiceError("MODEL_NOT_CONFIGURED", "DeepSeek API Key 未配置")
        signature = self._world_signature(scene, personas, world_revision)
        policy_world = PoliceTrainingWorld(scene.scene_id, current_stage=scene.current_stage, rules=scene.rules)
        with self.state_store.locked(workflow_id):
            record = self.state_store.get(workflow_id)
            if record and record.get("last_idempotency_key") == idempotency_key and isinstance(record.get("last_turn"), dict):
                return SimulationTurn(**record["last_turn"])
            world, agents, rebuilt = self._load_world(
                workflow_id, signature, scene, personas, fact_access, history, record
            )
            pre_turn_state = world.encode_complete_state()
            try:
                calls_before = int((self._tiny_client.get_cost_stats() if self._tiny_client else {}).get("model_calls") or 0)
                stimulus = f"学员民警执行处置动作：{learner_input}" if input_kind == "action" else f"学员民警说：{learner_input}"
                world.broadcast(stimulus)
                actors = policy_world.select_actors(
                    personas,
                    learner_input,
                    target_role_name=target_role_name,
                    max_actors=self.settings.tinytroupe_max_actors,
                )
                actor_states = {persona.person_id: agents[persona.person_id].encode_complete_state() for persona in actors}
                with ThreadPoolExecutor(max_workers=min(len(actors), self.settings.tinytroupe_model_concurrency)) as executor:
                    turns = list(executor.map(lambda persona: self._act(persona, agents[persona.person_id]), actors))
                audit = validator(turns)
                invalid_ids = {str(item) for item in audit.get("invalid_person_ids") or []}
                retry_count = 0
                retried_actor_count = 0
                if invalid_ids:
                    retry_count = 1
                    retry_personas = [persona for persona in actors if persona.person_id in invalid_ids]
                    retried_actor_count = len(retry_personas)
                    for persona in retry_personas:
                        agent = agents[persona.person_id]
                        agent.decode_complete_state(actor_states[persona.person_id])
                        agent.listen("上一版回答未通过事实边界校验。只使用 case_facts，保持人物身份并重新回答。")
                    with ThreadPoolExecutor(max_workers=min(len(retry_personas), self.settings.tinytroupe_model_concurrency)) as executor:
                        retried = list(executor.map(lambda persona: self._act(persona, agents[persona.person_id]), retry_personas))
                    replacements = {item["person_id"]: item for item in retried}
                    turns = [replacements.get(item["person_id"], item) for item in turns]
                    audit = validator(turns)
                    invalid_ids = {str(item) for item in audit.get("invalid_person_ids") or []}
                if invalid_ids:
                    raise WorkflowServiceError(
                        "ROLE_VALIDATION_FAILED",
                        f"角色回复未通过校验: {','.join(sorted(invalid_ids))}",
                        retryable=True,
                    )
                for turn in turns:
                    speaker = agents.get(turn["person_id"])
                    world.broadcast(f"{turn['speaker_name']}说：{turn['content']}", source=speaker)
                round_number = int((record or {}).get("round") or 0) + 1
                calls_after = int((self._tiny_client.get_cost_stats() if self._tiny_client else {}).get("model_calls") or 0)
                simulation_meta = {
                    "engine": "tinytroupe-world",
                    "world_id": world.name,
                    "round": round_number,
                    "observer_count": len(personas),
                    "actor_count": len(actors),
                    "model_calls": max(len(actors) + retried_actor_count, calls_after - calls_before),
                    "audit_model_calls": 1 + retry_count,
                    "retry_count": retry_count,
                    "rebuilt": rebuilt,
                    "state_version": self.settings.tinytroupe_state_version,
                }
                result = SimulationTurn(
                    reply_turns=turns,
                    active_speakers=[
                        {"person_id": item.person_id, "platform_role_id": item.platform_role_id, "name": item.name}
                        for item in actors
                    ],
                    audit=audit,
                    simulation_meta=simulation_meta,
                )
                record_to_save = {
                    "version": self.settings.tinytroupe_state_version,
                    "signature": signature,
                    "round": round_number,
                    "last_idempotency_key": idempotency_key,
                    "last_turn": {
                        "reply_turns": result.reply_turns,
                        "active_speakers": result.active_speakers,
                        "audit": result.audit,
                        "simulation_meta": result.simulation_meta,
                    },
                    "world_state": world.encode_complete_state(),
                }
                self.state_store.put(workflow_id, record_to_save)
                if self.audit_log:
                    self.audit_log.write({
                        "workflow_id": workflow_id,
                        "event": "tinytroupe_world_turn",
                        "world_id": world.name,
                        "round": round_number,
                        "observer_count": len(personas),
                        "actor_count": len(actors),
                        "active_person_ids": [item.person_id for item in actors],
                        "retry_count": retry_count,
                        "status": "succeeded",
                    })
                return result
            except WorkflowServiceError as exc:
                world.decode_complete_state(pre_turn_state)
                if self.audit_log:
                    self.audit_log.write({
                        "workflow_id": workflow_id,
                        "event": "tinytroupe_world_turn",
                        "active_person_ids": [item.person_id for item in locals().get("actors", [])],
                        "status": "failed",
                        "error_code": exc.code,
                    })
                raise
            except Exception as exc:
                world.decode_complete_state(pre_turn_state)
                if self.audit_log:
                    self.audit_log.write({
                        "workflow_id": workflow_id,
                        "event": "tinytroupe_world_turn",
                        "status": "failed",
                        "error_code": "SIMULATION_EXECUTION_FAILED",
                    })
                raise WorkflowServiceError(
                    "SIMULATION_EXECUTION_FAILED",
                    f"TinyTroupe 世界推演失败: {exc}",
                    retryable=True,
                ) from exc
