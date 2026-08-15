from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

WORKFLOW_CONTRACT_VERSION = "2026-08-15"


class WorkflowStage(str, Enum):
    training = "TRAINING"
    completed = "COMPLETED"
    evaluated = "EVALUATED"
    archived = "ARCHIVED"
    failed = "FAILED"


class SkillName(str, Enum):
    case_import_harness = "case_import_harness"
    role_simulation = "role_simulation"
    evaluation = "evaluation"
    report = "report"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FourDimensionalState(StrictModel):
    emotion: int = Field(default=50, ge=0, le=100)
    cooperation: int = Field(default=35, ge=0, le=100)
    risk: int = Field(default=50, ge=0, le=100)
    clarity: int = Field(default=50, ge=0, le=100)


class RoleInitialState(StrictModel):
    person_id: str
    name: str = ""
    initial_state: FourDimensionalState = Field(default_factory=FourDimensionalState)


class Fact(StrictModel):
    fact_id: str
    content: str
    source: str = ""
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    fact_type: str = "事实"
    status: str = "claimed"
    known_by: list[str] = Field(default_factory=list)
    unknown_by: list[str] = Field(default_factory=list)
    secret: bool = False
    disclosure_policy: dict[str, Any] = Field(default_factory=dict)


class Person(StrictModel):
    person_id: str
    name: str
    role: str = "相关人员"
    facts_known: list[str] = Field(default_factory=list)
    facts_hidden: list[str] = Field(default_factory=list)
    speakable: bool = True
    training_relevance: str = "dialogue"
    initial_state: FourDimensionalState = Field(default_factory=FourDimensionalState)
    traits: list[str] = Field(default_factory=list)
    speaking_style: str = "自然口语"
    goals: list[str] = Field(default_factory=list)


class CaseWorld(StrictModel):
    case_id: str
    title: str = ""
    summary: str = ""
    case_type: str = "其他"
    persons: list[Person] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)


class Persona(StrictModel):
    person_id: str
    name: str
    role: str
    traits: list[str] = Field(default_factory=list)
    speaking_style: str = "自然口语"
    goals: list[str] = Field(default_factory=list)
    known_fact_ids: list[str] = Field(default_factory=list)
    hidden_fact_ids: list[str] = Field(default_factory=list)
    state: FourDimensionalState = Field(default_factory=FourDimensionalState)
    platform_role_id: str = ""
    state_label: str = ""
    is_primary: bool = False
    role_memories: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_ledger: list[Any] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    response_constraints: list[str] = Field(default_factory=list)


class RoleParticipation(StrictModel):
    person_id: str
    present: bool = True
    interaction_purpose: str = ""
    can_initiate: bool = False
    can_interrupt: bool = False
    relevant_fact_ids: list[str] = Field(default_factory=list)


class SceneWorld(StrictModel):
    scene_id: str
    case_id: str
    name: str
    environment: dict[str, Any] = Field(default_factory=dict)
    role_ids: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
    current_stage: str = ""
    stages: list[dict[str, Any]] = Field(default_factory=list)
    role_states: list[RoleInitialState] = Field(default_factory=list)
    role_participation: list[RoleParticipation] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)


class WorkflowRequest(StrictModel):
    workflow_id: str = Field(min_length=1, max_length=128)
    stage: WorkflowStage
    skill: SkillName | None = None
    case_id: str | None = Field(default=None, max_length=128)
    training_id: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowError(StrictModel):
    code: str
    message: str
    retryable: bool = False


class WorkflowResponse(StrictModel):
    workflow_id: str
    trace_id: str
    stage: WorkflowStage
    next_stage: WorkflowStage
    skill: SkillName
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    transition_proposal: dict[str, Any] | None = None
    error: WorkflowError | None = None
