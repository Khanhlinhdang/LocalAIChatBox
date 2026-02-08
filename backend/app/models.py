from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, UniqueConstraint, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


# ==================== ENTERPRISE: TENANTS ====================

class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    settings_json = Column(Text, nullable=True)  # JSON config per tenant
    is_active = Column(Boolean, default=True)
    max_users = Column(Integer, default=0)  # 0 = unlimited
    max_storage_mb = Column(Integer, default=0)  # 0 = unlimited
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")


# ==================== ENTERPRISE: ROLES & PERMISSIONS ====================

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, default=False)  # System roles can't be deleted
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="role")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission = Column(String(100), nullable=False)

    role = relationship("Role", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint('role_id', 'permission', name='uq_role_permission'),
    )


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id], back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
    )


# ==================== ENTERPRISE: DOCUMENT PERMISSIONS ====================

class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=True)
    access_level = Column(String(20), default="read")  # read, write, manage
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    granted_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="permissions")
    user = relationship("User", foreign_keys=[user_id])
    granter = relationship("User", foreign_keys=[granted_by])

    __table_args__ = (
        UniqueConstraint('document_id', 'user_id', name='uq_doc_user_perm'),
    )


# ==================== ENTERPRISE: AUDIT LOG ====================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
    tenant = relationship("Tenant")


# ==================== USERS ====================

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

    # Enterprise fields
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    ldap_dn = Column(String(500), nullable=True)  # LDAP Distinguished Name
    auth_provider = Column(String(20), default="local")  # local, ldap

    documents = relationship("Document", back_populates="uploader", foreign_keys="Document.uploaded_by")
    conversations = relationship("Conversation", back_populates="user")
    research_tasks = relationship("ResearchTask", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")
    usage_logs = relationship("UsageLog", back_populates="user")
    user_roles = relationship("UserRole", back_populates="user", foreign_keys="UserRole.user_id")
    tenant = relationship("Tenant", back_populates="users")


# ==================== FOLDER & TAG SYSTEM ====================

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    color = Column(String(7), default="#4f8cff")
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)

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

    # Enterprise fields
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    is_encrypted = Column(Boolean, default=False)

    uploader = relationship("User", back_populates="documents", foreign_keys=[uploaded_by])
    folder = relationship("Folder", back_populates="documents")
    tags = relationship("DocumentTag", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    permissions = relationship("DocumentPermission", back_populates="document", cascade="all, delete-orphan")
    tenant = relationship("Tenant", back_populates="documents")


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


# ==================== TOKEN USAGE TRACKING ====================

class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model = Column(String(100), nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    action = Column(String(50), default="chat")  # chat, research, report, query
    resource_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")


# ==================== SCHEDULED RESEARCH ====================

class ScheduledResearch(Base):
    __tablename__ = "scheduled_research"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    query = Column(Text, nullable=False)
    strategy = Column(String(50), default="source-based")
    interval_hours = Column(Integer, default=24)
    is_enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)
    last_task_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# ==================== SEARCH METRICS ====================

class SearchMetric(Base):
    __tablename__ = "search_metrics"

    id = Column(Integer, primary_key=True, index=True)
    engine_name = Column(String(50), nullable=False)
    query = Column(Text, nullable=False)
    result_count = Column(Integer, default=0)
    response_time_ms = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
