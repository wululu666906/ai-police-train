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
    original_content = Column(Text) # 案件剧本原文
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
    
    # 🌟 学员视角信息（取代上帝视角）
    dispatch_brief = Column(Text, nullable=True)     # 接警简报 (给学员看的接警指令)
    first_impression = Column(Text, nullable=True)   # 现场第一印象 (学员推门看到的客观景象)
    
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
    
    # 角色能力与心理维度
    iq_level = Column(String(20), default="中等")        # 低/中等/较高/高
    eq_level = Column(String(20), default="中等")        # 低/中等/较高/高  
    lying_ability = Column(String(20), default="一般")    # 差/一般/较强/极强
    weakness = Column(Text, nullable=True)               # 性格弱点/软肋
    
    # 知识边界
    knows_facts = Column(Text, default="[]")             # 该角色知道的事实
    does_not_know = Column(Text, default="[]")           # 该角色不知道的事实
    hidden_truths = Column(Text, default="[]")           # 该角色掌握并打算隐瞒的秘密
    
    case = relationship("Case", back_populates="roles")
    scene = relationship("Scene", back_populates="roles")

class SceneRole(Base):
    """场景-角色多对多关联表，标记谁是主对话角色"""
    __tablename__ = "scene_roles"
    
    id = Column(Integer, primary_key=True, index=True)
    scene_id = Column(Integer, ForeignKey("scenes.id"))
    role_id = Column(Integer, ForeignKey("roles.id"))
    is_primary = Column(Boolean, default=False)  # 是否是该场景的主对话角色


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
    evaluation_result = Column(Text, nullable=True) # 存储评分结果 JSON
    status = Column(String(20), default="active") # active, finished
    created_at = Column(DateTime, default=datetime.utcnow)
    
    messages = relationship("Message", back_populates="session")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("training_sessions.id"))
    role = Column(String(20)) # human, ai, system
    content = Column(Text)
    inner_thought = Column(Text, nullable=True) # AI角色的内心独白
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("TrainingSession", back_populates="messages")

