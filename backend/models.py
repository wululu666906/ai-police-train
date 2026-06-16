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
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="session")


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
