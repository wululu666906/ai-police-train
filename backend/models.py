from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
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
