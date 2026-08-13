from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_workflow_service.contracts import Persona, SceneWorld
from ai_workflow_service.errors import WorkflowServiceError

try:
    from tinytroupe.agent import TinyPerson
    from tinytroupe.environment import TinyWorld
except Exception:
    TinyPerson = None
    TinyWorld = None


@dataclass
class SimulationSnapshot:
    role_id: str
    behavior_tendency: str
    state: dict[str, float]


class TinyTroupeAdapter:
    @property
    def available(self) -> bool:
        return TinyPerson is not None and TinyWorld is not None

    def build_world(self, scene: SceneWorld, personas: list[Persona]) -> Any:
        if not self.available:
            raise WorkflowServiceError("SIMULATION_UNAVAILABLE", "TinyTroupe 未安装或初始化失败")
        agents = []
        for persona in personas:
            agent = TinyPerson(persona.name)
            agent.define("occupation", persona.role)
            agent.define("personality_traits", persona.traits)
            agent.define("communication_style", persona.speaking_style)
            agent.define("goals", persona.goals)
            agents.append(agent)
        return TinyWorld(scene.name, agents)

    def infer_tendency(self, persona: Persona, learner_input: str) -> SimulationSnapshot:
        if not self.available:
            raise WorkflowServiceError("SIMULATION_UNAVAILABLE", "TinyTroupe 未安装或初始化失败")
        state = dict(persona.state)
        trust = float(state.get("trust", 0.4))
        pressure = float(state.get("pressure", 0.3))
        if any(token in learner_input for token in ("别急", "慢慢", "理解", "放心")):
            trust = min(1.0, trust + 0.08)
        if any(token in learner_input for token in ("撒谎", "老实交代", "必须", "警告")):
            pressure = min(1.0, pressure + 0.12)
        state.update({"trust": trust, "pressure": pressure})
        tendency = "谨慎回应"
        if pressure >= 0.75 and trust < 0.45:
            tendency = "提高防备，缩短回答"
        elif trust >= 0.65:
            tendency = "主动补充本人已知信息"
        return SimulationSnapshot(persona.person_id, tendency, state)
