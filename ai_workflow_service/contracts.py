from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStage(str, Enum):
    case_uploaded = "CASE_UPLOADED"
    case_parsing = "CASE_PARSING"
    case_parsed = "CASE_PARSED"
    persona_building = "PERSONA_BUILDING"
    personas_ready = "PERSONAS_READY"
    scene_building = "SCENE_BUILDING"
    ready = "READY"
    training = "TRAINING"
    completed = "COMPLETED"
    evaluating = "EVALUATING"
    evaluated = "EVALUATED"
    archived = "ARCHIVED"
    failed = "FAILED"


class SkillName(str, Enum):
    case_parse = "case_parse"
    persona_build = "persona_build"
    scene_build = "scene_build"
    role_simulation = "role_simulation"
    evaluation = "evaluation"
    report = "report"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(StrictModel):
    fact_id: str
    content: str
    source: str = ""
    known_by: list[str] = Field(default_factory=list)
    unknown_by: list[str] = Field(default_factory=list)
    secret: bool = False


class Person(StrictModel):
    person_id: str
    name: str
    role: str = "相关人员"
    facts_known: list[str] = Field(default_factory=list)
    facts_hidden: list[str] = Field(default_factory=list)


class CaseWorld(StrictModel):
    case_id: str
    title: str = ""
    summary: str = ""
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
    state: dict[str, float] = Field(default_factory=dict)


class SceneWorld(StrictModel):
    scene_id: str
    case_id: str
    name: str
    environment: dict[str, Any] = Field(default_factory=dict)
    role_ids: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


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
