from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ai_workflow_service.contracts import SkillName, WorkflowRequest, WorkflowStage


class Skill(ABC):
    name: SkillName
    next_stage: WorkflowStage

    @abstractmethod
    def execute(self, request: WorkflowRequest) -> dict[str, Any]:
        raise NotImplementedError
