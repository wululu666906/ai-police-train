from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PoliceTrainingWorld:
    scene_id: str
    rules: list[str] = field(default_factory=list)
    interventions: list[dict[str, Any]] = field(default_factory=list)

    def applicable_interventions(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        elapsed = int(context.get("elapsed_seconds") or 0)
        return [item for item in self.interventions if elapsed >= int(item.get("after_seconds") or 0)]
