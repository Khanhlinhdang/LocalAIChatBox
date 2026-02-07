from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, UniqueConstraint, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100))
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", back_populates="uploader")
    conversations = relationship("Conversation", back_populates="user")
    research_tasks = relationship("ResearchTask", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")
    usage_logs = relationship("UsageLog", back_populates="user")


# ==================== FOLDER & TAG SYSTEM ====================

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    color = Column(String(7), default="#4f8cff")

    parent = relationship("Folder", remote_side=[id], backref="children")
    creator = relationship("User")
    documents = relationship("Document", back_populates="folder")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    color = Column(String(7), default="#4f8cff")
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentTag(Base):
    __tablename__ = "document_tags"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint('document_id', 'tag_id', name='uq_document_tag'),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_mb = Column(Integer)
    file_type = Column(String(50))
    num_chunks = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    is_indexed = Column(Boolean, default=False)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    version = Column(Integer, default=1)
    description = Column(Text, nullable=True)

    uploader = relationship("User", back_populates="documents")
    folder = relationship("Folder", back_populates="documents")
    tags = relationship("DocumentTag", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_mb = Column(Integer)
    num_chunks = Column(Integer)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    change_note = Column(Text, nullable=True)

    document = relationship("Document", back_populates="versions")
    uploader = relationship("User")


# ==================== CHAT SESSIONS (Multi-turn) ====================

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("Conversation", back_populates="session", order_by="Conversation.created_at")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources_used = Column(Text)
    context_used = Column(Boolean, default=True)
    entities_found = Column(Text, nullable=True)  # JSON string
    search_mode = Column(String(20), default="hybrid")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    session = relationship("ChatSession", back_populates="messages")


# ==================== USAGE ANALYTICS ====================

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # query, upload, delete, research, export, login, kg_search
    resource_type = Column(String(50), nullable=True)  # document, chat, research, kg, export
    resource_id = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON string for extra details
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="usage_logs")


# ==================== RESEARCH ====================

class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    query = Column(Text, nullable=False)
    strategy = Column(String(50), default="source-based")
    status = Column(String(20), default="pending")  # pending, running, completed, failed, cancelled
    progress = Column(Float, default=0.0)
    progress_message = Column(String(500), default="")
    result_knowledge = Column(Text)
    result_report = Column(Text)
    result_sources = Column(Text)  # JSON string
    result_metadata = Column(Text)  # JSON string
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="research_tasks")


class ResearchSetting(Base):
    __tablename__ = "research_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    key = Column(String(100), nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='uq_research_setting_user_key'),
    )
