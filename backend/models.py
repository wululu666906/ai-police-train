from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20), default="student") # admin, instructor, student
    created_at = Column(DateTime, default=datetime.utcnow)

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True)
    case_type = Column(String(50)) # 纠纷/打架/酒驾等
    background = Column(Text)
    # 结构化解析后的详细数据 (JSON格式)
    # 包含: conflict_points, key_facts, hidden_info, persons
    structured_data = Column(Text, default="{}") 
    created_at = Column(DateTime, default=datetime.utcnow)
    
    scenes = relationship("Scene", back_populates="cases", cascade="all, delete-orphan")
    roles = relationship("Role", back_populates="case", cascade="all, delete-orphan")
    
class Scene(Base):
    __tablename__ = "scenes"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    name = Column(String(100)) # e.g. 接警对话, 现场调查
    description = Column(Text) # 场景详细描述
    difficulty = Column(String(20)) # 简单, 中等, 困难
    # 场景对话阶段 (JSON格式)
    # e.g. [{"name": "初始接触", "goal": "..."}, ...]
    stages = Column(Text, default="[]")
    
    cases = relationship("Case", back_populates="scenes")
    roles = relationship("Role", back_populates="scene", cascade="all, delete-orphan")

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id")) # Unified grouping under case
    scene_id = Column(Integer, ForeignKey("scenes.id"), nullable=True)
    name = Column(String(50)) # 报警人/嫌疑人
    role_type = Column(String(20)) # 配合型/情绪型/对抗型/隐瞒型
    personality = Column(Text) # 性格详细特征
    speaking_style = Column(String(100)) # 说话风格: 粗鲁, 胆怯, 隐晦等
    init_emotion = Column(Integer, default=50)
    init_trust = Column(Integer, default=30)
    status = Column(String(50), default="正常") # 角色状态: 正常/受伤/由于伤情较重无法接受审问/死亡等
    # 该角色掌握的所有信息 (JSON格式)
    hidden_truths = Column(Text, default="[]") 
    
    case = relationship("Case", back_populates="roles")
    scene = relationship("Scene", back_populates="roles")


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    content = Column(Text) # e.g. "你叫{role}，当前状态{emotion}..."

class TrainingSession(Base):
    __tablename__ = "training_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    scene_id = Column(Integer, ForeignKey("scenes.id"))
    current_stage = Column(String(50), default="初始接触")
    current_emotion = Column(Integer)
    current_trust = Column(Integer)
    revealed_info = Column(Text, default="[]") # JSON list of strings
    status = Column(String(20), default="active") # active, finished
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"))
    role = Column(String(20)) # human, ai, system
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("TrainingSession", back_populates="messages")

