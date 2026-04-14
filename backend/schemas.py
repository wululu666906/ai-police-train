from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

class RoleBase(BaseModel):
    name: str
    personality: str
    init_emotion: int = 50
    init_trust: int = 30
    hidden_truths: Optional[str] = "[]"

class RoleCreate(RoleBase):
    pass

class Role(RoleBase):
    id: int
    scene_id: int
    model_config = ConfigDict(from_attributes=True)

class SceneBase(BaseModel):
    name: str
    difficulty: str

class SceneCreate(SceneBase):
    roles: List[RoleCreate] = []

class Scene(SceneBase):
    id: int
    case_id: int
    roles: List[Role] = []
    model_config = ConfigDict(from_attributes=True)

class CaseBase(BaseModel):
    title: str
    case_type: str
    background: str

class CaseCreate(CaseBase):
    scenes: List[SceneCreate] = []

class Case(CaseBase):
    id: int
    created_at: datetime
    scenes: List[Scene] = []
    model_config = ConfigDict(from_attributes=True)

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
    current_emotion: int
    current_trust: int
    revealed_info: str
    status: str
    messages: List[Message] = []
    model_config = ConfigDict(from_attributes=True)
