from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20), default="student")
    display_name = Column(String(80), nullable=True)
    real_name = Column(String(80), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(120), nullable=True)
    unit = Column(String(120), nullable=True)
    department = Column(String(120), nullable=True)
    bio = Column(Text, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class OpsAuditLog(Base):
    __tablename__ = "ops_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(60), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    actor = relationship("User", foreign_keys=[actor_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class SpeechUsageLog(Base):
    __tablename__ = "speech_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mode = Column(String(30), nullable=False, default="transcribe")
    status = Column(String(30), nullable=False, default="success")
    language = Column(String(20), nullable=True)
    model = Column(String(120), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    text_length = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True)
    case_type = Column(String(50))
    background = Column(Text)
    original_content = Column(Text)
    structured_data = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    scenes = relationship("Scene", back_populates="cases", cascade="all, delete-orphan")
    roles = relationship("Role", back_populates="case", cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    name = Column(String(100))
    description = Column(Text)
    difficulty = Column(String(20))
    dispatch_brief = Column(Text, nullable=True)
    first_impression = Column(Text, nullable=True)
    stages = Column(Text, default="[]")

    cases = relationship("Case", back_populates="scenes")
    roles = relationship("Role", back_populates="scene", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=True)
    name = Column(String(50))
    person_id = Column(String(50), nullable=True, index=True)
    role_type = Column(String(20))
    interaction_style = Column(String(20), default="配合型")
    personality = Column(Text)
    speaking_style = Column(String(100))
    init_emotion = Column(Integer, default=50)
    init_trust = Column(Integer, default=30)
    status = Column(String(50), default="正常")
    iq_level = Column(String(20), default="中等")
    eq_level = Column(String(20), default="中等")
    lying_ability = Column(String(20), default="一般")
    weakness = Column(Text, nullable=True)
    knows_facts = Column(Text, default="[]")
    does_not_know = Column(Text, default="[]")
    hidden_truths = Column(Text, default="[]")
    persona_meta = Column(Text, default="{}")

    case = relationship("Case", back_populates="roles")
    scene = relationship("Scene", back_populates="roles")


class SceneRole(Base):
    __tablename__ = "scene_roles"

    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"))
    role_id = Column(Integer, ForeignKey("roles.id"))
    is_primary = Column(Boolean, default=False)


class AvatarImage(Base):
    __tablename__ = "avatar_images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(50), nullable=False)
    gender = Column(String(10), nullable=False)
    age_group = Column(String(10), nullable=False)


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    content = Column(Text)


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    scene_id = Column(Integer, ForeignKey("scenes.id"))
    current_stage = Column(String(50), default="初始接触")
    current_emotion = Column(Integer)
    current_trust = Column(Integer)
    revealed_info = Column(Text, default="[]")
    evaluation_result = Column(Text, nullable=True)
    status = Column(String(20), default="active")
    training_started_at = Column(DateTime, nullable=True)
    training_finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="session")
    artifacts = relationship(
        "TrainingSessionArtifact",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TrainingSessionArtifact.created_at",
    )


class FaceProfile(Base):
    __tablename__ = "face_profiles"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    face_embedding = Column(Text, nullable=False)
    face_image_url = Column(String(255), nullable=True)
    embeddings_json = Column(Text, nullable=True)
    sample_images_json = Column(Text, nullable=True)
    quality_json = Column(Text, nullable=True)
    embedding_model = Column(String(80), default="insightface:buffalo_l")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("User")


class FaceVerificationEvent(Base):
    __tablename__ = "face_verification_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(30), default="verify")
    status = Column(String(30), default="failed")
    reason = Column(String(120), nullable=True)
    reason_code = Column(String(60), nullable=True)
    similarity = Column(Integer, nullable=True)
    liveness_score = Column(Integer, nullable=True)
    quality_json = Column(Text, nullable=True)
    liveness_json = Column(Text, nullable=True)
    abnormal_level = Column(String(20), nullable=True)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TrainingSession")
    student = relationship("User")


class TrainingSessionArtifact(Base):
    """普通训练会话留痕：截图、语音、录屏等附件"""
    __tablename__ = "training_session_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=False)
    artifact_type = Column(String(30), nullable=False, default="screenshot")
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(120), nullable=True)
    file_size = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TrainingSession", back_populates="artifacts")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"))
    role = Column(String(20))
    content = Column(Text)
    speaker_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    speaker_name = Column(String(50), nullable=True)
    inner_thought = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("TrainingSession", back_populates="messages")


class TrainingClass(Base):
    __tablename__ = "training_classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    invite_code = Column(String(32), unique=True, index=True, nullable=False)
    muted = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("ClassMembership", back_populates="classroom", cascade="all, delete-orphan")
    assignments = relationship("TrainingAssignment", back_populates="classroom", cascade="all, delete-orphan")
    announcements = relationship("ClassAnnouncement", back_populates="classroom", cascade="all, delete-orphan")


class ClassMembership(Base):
    __tablename__ = "class_memberships"
    __table_args__ = (UniqueConstraint("class_id", "user_id", name="uq_class_membership_user"),)

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("training_classes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), default="student")
    status = Column(String(20), default="active")
    joined_at = Column(DateTime, default=datetime.utcnow)

    classroom = relationship("TrainingClass", back_populates="members")
    user = relationship("User")


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("training_classes.id"), nullable=False)
    title = Column(String(160), nullable=False)
    instructions = Column(Text, nullable=True)
    scoring_rule = Column(Text, nullable=True)
    status = Column(String(20), default="published")
    allow_late = Column(Boolean, default=False)
    published_at = Column(DateTime, default=datetime.utcnow)
    due_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    classroom = relationship("TrainingClass", back_populates="assignments")
    cases = relationship("TrainingAssignmentCase", back_populates="assignment", cascade="all, delete-orphan")
    submissions = relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan")


class TrainingAssignmentCase(Base):
    __tablename__ = "training_assignment_cases"
    __table_args__ = (UniqueConstraint("assignment_id", "case_id", name="uq_assignment_case"),)

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("training_assignments.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    sort_order = Column(Integer, default=0)

    assignment = relationship("TrainingAssignment", back_populates="cases")
    case = relationship("Case")


class TrainingAssignmentScene(Base):
    __tablename__ = "training_assignment_scenes"
    __table_args__ = (UniqueConstraint("assignment_id", "scene_id", name="uq_assignment_scene"),)

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("training_assignments.id"), nullable=False)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    sort_order = Column(Integer, default=0)

    assignment = relationship("TrainingAssignment")
    scene = relationship("Scene")
    case = relationship("Case")


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("training_assignments.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=True)
    training_session_id = Column(Integer, ForeignKey("training_sessions.id"), nullable=True)
    status = Column(String(20), default="in_progress")
    score = Column(Integer, nullable=True)
    evaluation_result = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignment = relationship("TrainingAssignment", back_populates="submissions")
    user = relationship("User")
    case = relationship("Case")
    scene = relationship("Scene")
    training_session = relationship("TrainingSession")


class AssignmentStudentOverride(Base):
    __tablename__ = "assignment_student_overrides"
    __table_args__ = (UniqueConstraint("assignment_id", "user_id", name="uq_assignment_student_override"),)

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("training_assignments.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    allow_late = Column(Boolean, nullable=True)
    due_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignment = relationship("TrainingAssignment")
    user = relationship("User")


class ClassAnnouncement(Base):
    __tablename__ = "class_announcements"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("training_classes.id"), nullable=False)
    title = Column(String(160), nullable=False)
    content = Column(Text, nullable=True)
    category = Column(String(30), default="notice")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    classroom = relationship("TrainingClass", back_populates="announcements")
    creator = relationship("User")


# ─────────────────────────────────────────────
# 视频实训模块（第一阶段）
# ─────────────────────────────────────────────

class TrainingVideo(Base):
    """视频素材表：区分教学素材视频 / 交互式实训视频"""
    __tablename__ = "training_videos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(120), nullable=False, index=True)
    description = Column(Text, nullable=True)
    # teaching=教学素材（预习/复盘），interactive=交互式实训（含节点考核）
    video_type = Column(String(20), nullable=False, default="teaching")
    file_path = Column(String(500), nullable=False)          # 相对于 static/videos/ 的路径
    thumbnail_path = Column(String(500), nullable=True)      # 封面图相对路径
    duration = Column(Integer, nullable=True)                # 时长（秒）
    file_size = Column(Integer, nullable=True)               # 文件大小（字节）
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=True)   # 可选关联案件
    tags = Column(Text, default="[]")                        # JSON 字符串
    # 训练前简报（案情背景、训练要点、评分规则等，富文本/纯文本均可）
    briefing = Column(Text, nullable=True)
    # published=已发布，draft=草稿，archived=归档
    status = Column(String(20), default="draft")
    sort_order = Column(Integer, default=0)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nodes = relationship("VideoNode", back_populates="video", cascade="all, delete-orphan",
                         order_by="VideoNode.node_index")
    case = relationship("Case")
    uploader = relationship("User")
class VideoNode(Base):
    """视频训练节点：在某个时间点暂停并触发考核"""
    __tablename__ = "video_nodes"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("training_videos.id"), nullable=False)
    node_index = Column(Integer, nullable=False, default=0)  # 节点顺序
    title = Column(String(100), nullable=True)               # 节点名称
    trigger_time = Column(Integer, nullable=False, default=0) # 触发时间点（秒）
    # auto_pause=自动暂停，light_motion=保留轻微动态
    pause_mode = Column(String(20), default="auto_pause")
    prompt_content = Column(Text, nullable=True)             # 弹窗提示内容（JSON）
    timeout_seconds = Column(Integer, default=60)            # 超时阈值（秒）
    retry_score_deduct = Column(Integer, default=5)          # 重试扣分
    skip_score_deduct = Column(Integer, default=20)          # 跳过扣分
    # auto=练习模式自动弹出，manual=考核模式手动取出
    prop_mode = Column(String(20), default="auto")
    # action=指令引导，judge=判断题，choice=单选题
    node_type = Column(String(20), default="action")
    node_config = Column(Text, default="{}")                 # 题目/选项等扩展配置（JSON）
    required_gesture = Column(String(50), nullable=True)     # 要求的手势类型
    required_keywords = Column(Text, default="[]")           # 要求匹配的关键词（JSON）
    score_weight = Column(Integer, default=10)               # 本节点满分权重
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("TrainingVideo", back_populates="nodes")


# ─────────────────────────────────────────────
# 视频实训模块（第二阶段）
# ─────────────────────────────────────────────

class VideoTrainingSession(Base):
    """视频实训 Session：跟踪学员的单次视频实训进度"""
    __tablename__ = "video_training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    video_id = Column(Integer, ForeignKey("training_videos.id"), nullable=False)
    # practice=练习模式，exam=正式考核
    mode = Column(String(20), default="practice")
    # active=进行中，finished=已完成，abandoned=中途放弃
    status = Column(String(20), default="active")
    # 当前进行到哪个节点（0-based index）
    current_node_index = Column(Integer, default=0)
    # 总得分（完成后计算）
    total_score = Column(Integer, nullable=True)
    # 满分（所有节点 score_weight 之和）
    full_score = Column(Integer, nullable=True)
    # 每个节点的详细记录（JSON 数组）
    node_records = Column(Text, default="[]")
    # 违规记录（切屏、退出等）
    violation_log = Column(Text, default="[]")
    evaluation_status = Column(String(20), default="pending")
    evaluation_result = Column(Text, nullable=True)
    evaluation_error = Column(Text, nullable=True)
    evaluation_started_at = Column(DateTime, nullable=True)
    evaluation_completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    user = relationship("User")
    video = relationship("TrainingVideo")
    node_results = relationship(
        "VideoNodeResult",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="VideoNodeResult.node_index",
    )
    artifacts = relationship(
        "VideoTrainingArtifact",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="VideoTrainingArtifact.created_at",
    )


class VideoNodeResult(Base):
    """单个节点的判定结果"""
    __tablename__ = "video_node_results"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("video_training_sessions.id"), nullable=False)
    node_id = Column(Integer, ForeignKey("video_nodes.id"), nullable=False)
    node_index = Column(Integer, nullable=False)
    # pass=通过，skip=跳过，timeout=超时后跳过，fail=未通过（多次重试后放弃）
    result = Column(String(20), nullable=False, default="pass")
    retry_count = Column(Integer, default=0)        # 重试次数
    time_used = Column(Integer, nullable=True)       # 实际用时（秒）
    score_earned = Column(Integer, default=0)        # 本节点得分
    score_deducted = Column(Integer, default=0)      # 本节点扣分
    # 学员提交的答案（JSON）
    answer_data = Column(Text, nullable=True)
    # 语音识别结果
    speech_transcript = Column(Text, nullable=True)
    evidence_payload = Column(Text, nullable=True)
    assessment_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("VideoTrainingSession", back_populates="node_results")
    node = relationship("VideoNode")


class VideoTrainingArtifact(Base):
    """训练过程媒体留存：当前用于摄像头/麦克风录制回放"""
    __tablename__ = "video_training_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("video_training_sessions.id"), nullable=False)
    artifact_type = Column(String(30), nullable=False, default="camera_recording")
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(120), nullable=True)
    file_size = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("VideoTrainingSession", back_populates="artifacts")
