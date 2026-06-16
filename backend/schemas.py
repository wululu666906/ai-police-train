from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class RoleBase(BaseModel):
    name: str
    role_type: str = "相关人员"
    interaction_style: str = "配合型"
    personality: str
    speaking_style: Optional[str] = "冷静"
    init_emotion: int = 50
    init_trust: int = 30
    status: Optional[str] = "正常"
    iq_level: Optional[str] = "中等"
    eq_level: Optional[str] = "中等"
    lying_ability: Optional[str] = "一般"
    weakness: Optional[str] = None
    knows_facts: Optional[List[str] | str] = "[]"
    does_not_know: Optional[List[str] | str] = "[]"
    hidden_truths: Optional[List[str] | str] = "[]"


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
    title: Optional[str] = "未命名知识"
    category: Optional[str] = "通用"
    tags: List[str] = []


class KnowledgeItemCreate(KnowledgeItemBase):
    pass


class KnowledgeItem(KnowledgeItemBase):
    id: str
    referenced_by_count: int = 0
    referenced_by: List[str] = []
    model_config = ConfigDict(from_attributes=True)


class MessageBase(BaseModel):
    role: str
    content: str


class MessageCreate(MessageBase):
    target_role_name: Optional[str] = None


class Message(MessageBase):
    id: int
    session_id: int
    speaker_role_id: Optional[int] = None
    speaker_name: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SceneRoleBrief(BaseModel):
    id: int
    name: str
    role_type: Optional[str] = None
    status: Optional[str] = None
    is_primary: bool = False
    speakable: bool = True
    emotion: Optional[int] = None
    cooperation: Optional[int] = None
    risk: Optional[int] = None
    clarity: Optional[int] = None
    emotion_delta: int = 0
    cooperation_delta: int = 0
    risk_delta: int = 0
    clarity_delta: int = 0
    state_label: Optional[str] = None
    truth_stage: Optional[str] = None
    is_active: bool = False
    is_targeted: bool = False
    avatar_id: Optional[int] = None
    avatar_url: Optional[str] = None


class RecommendedQuestionItem(BaseModel):
    text: str
    category: str = "追问"
    target_role_name: Optional[str] = None


class ActionTrigger(BaseModel):
    action_id: str
    note: Optional[str] = None


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
    current_cooperation: int = 30
    current_risk: int = 50
    current_clarity: int = 50
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
    current_cooperation: int = 30
    current_risk: int = 50
    current_clarity: int = 50
    revealed_info: str
    evaluation_result: Optional[str] = None
    status: str
    case_title: Optional[str] = None
    case_type: Optional[str] = None
    case_background: Optional[str] = None
    case_original_content: Optional[str] = None
    role_name: Optional[str] = None
    role_status: Optional[str] = None
    scene_roles: List["SceneRoleBrief"] = []
    scene_name: Optional[str] = None
    scene_kind: Optional[str] = "generic"
    dialogue_mode: Optional[str] = "officer_led"
    difficulty: Optional[str] = None
    dispatch_brief: Optional[str] = None
    first_impression: Optional[str] = None
    structured_data: Optional[str] = None
    stage_completion_requirements: List[str] = []
    stage_completion_satisfied: List[str] = []
    stage_completion_missing: List[str] = []
    recommended_questions: List[str] = []
    recommended_question_items: List[RecommendedQuestionItem] = []
    communication_feedback: Optional[dict] = None
    persona_hint: Optional[str] = None
    role_state_label: Optional[str] = None
    truth_stage: Optional[str] = None
    available_actions: List[dict] = []
    assessment_progress: Optional[dict] = None
    completed_point_ids: List[str] = []
    completed_action_ids: List[str] = []
    auto_finish_ready: bool = False
    closure_summary: Optional[dict] = None
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


class AdminStudentOverview(User):
    total_sessions: int = 0
    finished_sessions: int = 0
    avg_score: Optional[float] = None
    top_gap_missing: List[str] = []


class StudentProfileSummary(BaseModel):
    level: str
    summary_text: str
    total_sessions: int = 0
    finished_sessions: int = 0
    average_score: Optional[float] = None
    latest_training_at: Optional[datetime] = None
    stability_status: str
    progress_status: str


class StudentProfileDimension(BaseModel):
    key: str
    label: str
    score: float
    full_score: float
    trend: str


class StudentProfileScenePerformance(BaseModel):
    label: str
    session_count: int = 0
    average_score: Optional[float] = None
    status: str


class StudentProfileIssue(BaseModel):
    label: str
    count: int = 0
    severity: str
    category: str


class StudentProfileTrendPoint(BaseModel):
    session_id: int
    score: float
    created_at: Optional[datetime] = None


class AdminStudentProfile(BaseModel):
    student: User
    summary: StudentProfileSummary
    dimensions: List[StudentProfileDimension] = []
    scene_performance: List[StudentProfileScenePerformance] = []
    high_frequency_issues: List[StudentProfileIssue] = []
    high_risk_issues: List[StudentProfileIssue] = []
    stubborn_issues: List[StudentProfileIssue] = []
    suggestions: List[str] = []
    trend_points: List[StudentProfileTrendPoint] = []


class BatchStudentCreateRequest(BaseModel):
    template: str
    start_no: int
    end_no: int
    password: str


class BatchStudentCreateResponse(BaseModel):
    created_count: int
    skipped_count: int
    created_usernames: List[str] = []
    skipped_usernames: List[str] = []


class BatchStudentDeleteRequest(BaseModel):
    template: str
    start_no: int
    end_no: int


class BatchStudentDeleteResponse(BaseModel):
    deleted_count: int
    skipped_count: int
    deleted_usernames: List[str] = []
    skipped_usernames: List[str] = []


class StudentImportCreateRequest(BaseModel):
    usernames: List[str]
    password: str
