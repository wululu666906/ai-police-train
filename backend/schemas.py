from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class RoleBase(BaseModel):
    name: str
    role_type: str = "配合型"
    personality: str
    speaking_style: Optional[str] = "冷静"
    init_emotion: int = 50
    init_trust: int = 30
    status: Optional[str] = "正常"
    iq_level: Optional[str] = "中等"
    eq_level: Optional[str] = "中等"
    lying_ability: Optional[str] = "一般"
    weakness: Optional[str] = None
    knows_facts: Optional[str] = "[]"
    does_not_know: Optional[str] = "[]"
    hidden_truths: Optional[str] = "[]"


class RoleCreate(RoleBase):
    pass


class Role(RoleBase):
    id: int
    scene_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class SceneBase(BaseModel):
    name: str
    description: Optional[str] = None
    difficulty: str
    dispatch_brief: Optional[str] = None
    first_impression: Optional[str] = None
    stages: Optional[str] = "[]"


class SceneCreate(SceneBase):
    roles: List[RoleCreate] = []


class Scene(SceneBase):
    id: int
    case_id: int
    roles: List[Role] = []
    model_config = ConfigDict(from_attributes=True)


class CaseBase(BaseModel):
    title: Optional[str] = None
    case_type: Optional[str] = None
    background: Optional[str] = None
    original_content: Optional[str] = None
    structured_data: Optional[str] = "{}"


class CaseCreate(CaseBase):
    scenes: List[SceneCreate] = []


class Case(CaseBase):
    id: int
    created_at: datetime
    scenes: List[Scene] = []
    model_config = ConfigDict(from_attributes=True)


class KnowledgeItemBase(BaseModel):
    content: str
    source: Optional[str] = "manual"


class KnowledgeItemCreate(KnowledgeItemBase):
    pass


class KnowledgeItem(KnowledgeItemBase):
    id: str
    model_config = ConfigDict(from_attributes=True)


class MessageBase(BaseModel):
    role: str
    content: str


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: int
    session_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SessionBase(BaseModel):
    scene_id: int
    user_id: int


class SessionCreate(SessionBase):
    pass


class Session(SessionBase):
    id: int
    current_stage: str
    current_emotion: int
    current_trust: int
    revealed_info: str
    status: str
    messages: List[Message] = []
    model_config = ConfigDict(from_attributes=True)


class SessionDetail(BaseModel):
    id: int
    scene_id: int
    user_id: int
    current_stage: str
    current_stage_goal: Optional[str] = None
    current_emotion: int
    current_trust: int
    revealed_info: str
    evaluation_result: Optional[str] = None
    status: str
    case_title: Optional[str] = None
    case_type: Optional[str] = None
    case_background: Optional[str] = None
    case_original_content: Optional[str] = None
    role_name: Optional[str] = None
    role_status: Optional[str] = None
    scene_name: Optional[str] = None
    difficulty: Optional[str] = None
    dispatch_brief: Optional[str] = None
    first_impression: Optional[str] = None
    structured_data: Optional[str] = None
    messages: List[Message] = []
    model_config = ConfigDict(from_attributes=True)


class ScoreDetail(BaseModel):
    dimension: str
    score: int
    full_score: int
    reason: str


class ScoringResult(BaseModel):
    scores: List[ScoreDetail]
    total_score: int
    strengths: List[str] = []
    improvements: List[str] = []
    suggestions: Optional[str] = None


class PromptTemplateBase(BaseModel):
    name: str
    content: str


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplate(PromptTemplateBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    username: str
    role: str = "student"


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
