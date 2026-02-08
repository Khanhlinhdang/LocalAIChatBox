"""
LocalAIChatBox - Main FastAPI Application
Enhanced with multimodal RAG capabilities inspired by RAG-Anything.

Features:
- Multimodal document processing (PDF, DOCX, XLSX, PPTX, images, etc.)
- Knowledge graph with multimodal entities
- Hybrid query engine (text + multimodal + KG)
- Vision model integration for image understanding
- Batch document processing
"""

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import timedelta
import shutil
import json
from pathlib import Path

from app.database import get_db, init_db
from app.models import (
    User, Document as DBDocument, Conversation, ChatSession,
    Folder, Tag, DocumentTag, DocumentVersion, UsageLog
)
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, get_current_admin
)
from app.enhanced_rag_engine import get_rag_engine
from app.knowledge_graph import get_kg_engine
from app.research_routes import router as research_router
from app.enterprise_routes import router as enterprise_router
from app.lightrag_routes import router as lightrag_router
from app.analytics import (
    log_usage, get_usage_overview, get_daily_activity,
    get_top_users, get_popular_queries, get_document_stats,
    get_action_breakdown
)
from app.export_service import (
    export_chat_history, export_research_report,
    export_knowledge_graph, export_documents_list
)
from pydantic import BaseModel, EmailStr
from fastapi.responses import Response

app = FastAPI(
    title="LocalAIChatBox API",
    version="6.0.0",
    description="Multimodal RAG Chat System with LightRAG Knowledge Graph, Deep Research & Advanced Search"
)

# Security middleware (must be added before CORS)
try:
    from app.security_middleware import SecurityHeadersMiddleware, RequestValidationMiddleware
    app.add_middleware(RequestValidationMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    print("Security middleware: ENABLED")
except Exception as e:
    print(f"Warning: Security middleware not loaded (non-fatal): {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount research router
app.include_router(research_router)

# Mount enterprise router
app.include_router(enterprise_router, prefix="/api/enterprise", tags=["Enterprise"])

# Mount LightRAG router
app.include_router(lightrag_router)

# Mount LDR (Local Deep Research) router
from app.ldr_routes import router as ldr_router
app.include_router(ldr_router)


@app.on_event("startup")
async def startup_event():
    init_db()
    # Create default admin user if no users exist
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                email="admin@company.local",
                full_name="Administrator",
                hashed_password=get_password_hash("admin123"),
                is_admin=True,
                auth_provider="local"
            )
            db.add(admin)
            db.commit()
            print("Default admin user created (admin / admin123)")

        # Initialize RBAC default roles
        try:
            from app.rbac import RBACService
            RBACService.initialize_default_roles(db)
            print("RBAC default roles initialized")
        except Exception as e:
            print(f"Warning: RBAC init failed (non-fatal): {e}")

        # Assign admin role to admin user
        try:
            from app.rbac import RBACService
            admin_user = db.query(User).filter(User.username == "admin").first()
            if admin_user:
                RBACService.assign_role_to_user(db, admin_user.id, "admin", admin_user.id)
        except Exception:
            pass

    finally:
        db.close()

    # Initialize encryption service
    try:
        from app.encryption import get_encryption_service
        enc = get_encryption_service()
        if enc.enabled:
            print("Encryption at rest: ENABLED")
        else:
            print("Encryption at rest: DISABLED (set ENCRYPTION_KEY to enable)")
    except Exception as e:
        print(f"Warning: Encryption service init failed (non-fatal): {e}")

    # Initialize LDAP service
    try:
        from app.ldap_auth import get_ldap_service
        ldap = get_ldap_service()
        if ldap.available:
            print("LDAP/AD Authentication: ENABLED")
        else:
            print("LDAP/AD Authentication: DISABLED")
    except Exception as e:
        print(f"Warning: LDAP service init failed (non-fatal): {e}")

    # Initialize deep research service
    try:
        from app.deep_research import get_research_service
        get_research_service()
        print("Deep Research Service initialized (self-contained engine)")
    except Exception as e:
        print(f"Warning: Deep Research Service init failed (non-fatal): {e}")

    # Initialize multi-engine search
    try:
        from app.search_engines import get_meta_search_engine
        meta = get_meta_search_engine()
        available = [n for n, e in meta.engines.items() if e.is_available]
        print(f"Multi-Engine Search initialized: {', '.join(available)}")
    except Exception as e:
        print(f"Warning: Multi-Engine Search init failed (non-fatal): {e}")

    # Initialize notification service
    try:
        from app.notification_service import get_notification_service
        notif = get_notification_service()
        notif.start_worker()
        caps = []
        if notif.config.smtp_enabled:
            caps.append("Email")
        if notif.config.webhook_enabled:
            caps.append("Webhook")
        if caps:
            print(f"Notification Service: ENABLED ({', '.join(caps)})")
        else:
            print("Notification Service: DISABLED (no channels configured)")
    except Exception as e:
        print(f"Warning: Notification Service init failed (non-fatal): {e}")

    # Initialize research scheduler
    try:
        from app.research_scheduler import get_research_scheduler
        scheduler = get_research_scheduler()
        scheduler.start()
        print("Research Scheduler: STARTED")
    except Exception as e:
        print(f"Warning: Research Scheduler init failed (non-fatal): {e}")

    # Initialize enhanced RAG engine
    try:
        engine = get_rag_engine()
        print(f"Enhanced Multimodal RAG Engine initialized")
        info = engine.get_multimodal_info()
        print(f"  Supported formats: {list(info['supported_formats'].keys())}")
        print(f"  LLM: {info['llm_model']}, Vision: {info['vision_model']}")
    except Exception as e:
        print(f"Warning: Enhanced RAG Engine init failed (non-fatal): {e}")

    # Initialize LightRAG engine
    try:
        from app.lightrag_service import get_lightrag_service
        lightrag_svc = get_lightrag_service()
        initialized = await lightrag_svc.initialize()
        if initialized:
            health = await lightrag_svc.get_health()
            print(f"LightRAG Engine initialized: {health.get('graph_nodes', 0)} nodes, {health.get('graph_edges', 0)} edges")
            print(f"  LLM: {health.get('llm_model')}, Embed: {health.get('embed_model')}")
        else:
            print("Warning: LightRAG initialization failed (will retry on first request)")
    except Exception as e:
        print(f"Warning: LightRAG init failed (non-fatal): {e}")

    print("LocalAIChatBox Server Started (v6.0 - LightRAG Edition)")


# ==================== SCHEMAS ====================

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class ChatQuery(BaseModel):
    question: str
    use_context: bool = True
    use_knowledge_graph: bool = True
    include_multimodal: bool = True
    search_mode: str = "hybrid"
    k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    num_sources: int
    entities_found: Optional[List[dict]] = None
    graph_connections: Optional[int] = None
    multimodal_results: Optional[int] = None
    search_mode: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    color: Optional[str] = "#4f8cff"


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    color: Optional[str] = None


class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#4f8cff"


class DocumentMoveRequest(BaseModel):
    folder_id: Optional[int] = None


class DocumentTagRequest(BaseModel):
    tag_ids: List[int]


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class ChatQueryMultiTurn(BaseModel):
    question: str
    session_id: Optional[str] = None
    use_context: bool = True
    use_knowledge_graph: bool = True
    include_multimodal: bool = True
    search_mode: str = "hybrid"
    k: int = 5
    context_turns: int = 5  # Number of previous turns to include as context


# ==================== AUTH ENDPOINTS ====================

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")

        new_user = User(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=get_password_hash(user_data.password),
            is_admin=False,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        access_token = create_access_token(data={"sub": new_user.username})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "is_admin": new_user.is_admin
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user and return JWT token (supports local + LDAP)"""
    try:
        user = None

        # Try LDAP authentication first
        try:
            from app.auth import authenticate_with_ldap
            user = authenticate_with_ldap(credentials.username, credentials.password, db)
        except Exception:
            pass

        # Fallback to local authentication
        if not user:
            user = db.query(User).filter(User.username == credentials.username).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            if not verify_password(credentials.password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"}
                )

        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is disabled")

        access_token = create_access_token(data={"sub": user.username})
        log_usage(db, user.id, "login", "auth")

        # Log audit
        try:
            from app.compliance import get_compliance_service
            get_compliance_service().log_action(db, user.id, "login", "auth")
        except Exception:
            pass

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_admin": user.is_admin
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin,
        "auth_provider": getattr(current_user, 'auth_provider', 'local'),
        "tenant_id": getattr(current_user, 'tenant_id', None),
    }
    # Add roles and permissions
    try:
        from app.rbac import RBACService
        from app.models import UserRole, Role
        user_roles = db.query(UserRole).filter(UserRole.user_id == current_user.id).all()
        roles = []
        for ur in user_roles:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role:
                roles.append(role.name)
        user_data["roles"] = roles
        user_data["permissions"] = sorted(list(RBACService.get_user_permissions(db, current_user)))
    except Exception:
        user_data["roles"] = []
        user_data["permissions"] = []
    return user_data


@app.put("/api/auth/password")
async def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


# ==================== DOCUMENT ENDPOINTS (Enhanced Multimodal) ====================

@app.post("/api/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    folder_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and process documents with multimodal content extraction.

    Supports: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, TXT, MD, CSV,
              JPG, JPEG, PNG, BMP, TIFF, GIF, WEBP, HTML

    Processing pipeline:
    1. Parse document -> extract text, images, tables, equations
    2. Chunk text -> store in vector DB
    3. Process multimodal items -> generate descriptions via LLM/VLM
    4. Store multimodal chunks -> vector DB
    5. Extract entities -> knowledge graph
    """
    rag_engine = get_rag_engine()
    documents_path = Path("/app/data/documents")
    documents_path.mkdir(parents=True, exist_ok=True)

    uploaded_files = []

    for file in files:
        file_path = documents_path / f"{current_user.id}_{file.filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            # Use enhanced document processing pipeline
            result = rag_engine.process_document_complete(
                file_path=str(file_path),
                doc_id=f"doc_{current_user.id}_{file.filename}",
                filename=file.filename,
                user_id=current_user.id,
                username=current_user.username,
                enable_multimodal=True,
            )

            # Save to database
            db_document = DBDocument(
                filename=file.filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_size_mb=round(file_path.stat().st_size / (1024 * 1024), 2),
                file_type=file_path.suffix,
                num_chunks=result.get("text_chunks", 0),
                uploaded_by=current_user.id,
                is_indexed=True,
                folder_id=folder_id,
                description=description,
            )
            db.add(db_document)
            db.commit()
            db.refresh(db_document)

            uploaded_files.append({
                "filename": file.filename,
                "chunks": result.get("text_chunks", 0),
                "multimodal_items": result.get("multimodal_items", 0),
                "entities": result.get("entities_added", 0),
                "relations": result.get("relations_added", 0),
                "content_types": result.get("content_types", {}),
                "status": result.get("status", "success"),
            })

        except Exception as e:
            uploaded_files.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })

    return {"uploaded": uploaded_files}


@app.get("/api/documents/list")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    documents = db.query(DBDocument).order_by(DBDocument.uploaded_at.desc()).all()
    return {
        "total": len(documents),
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size_mb": doc.file_size_mb,
                "uploaded_by": doc.uploader.username if doc.uploader else "Unknown",
                "uploaded_at": doc.uploaded_at.isoformat(),
                "num_chunks": doc.num_chunks,
                "is_indexed": doc.is_indexed,
                "folder_id": doc.folder_id,
                "version": doc.version,
                "description": doc.description,
                "tags": [
                    {"id": dt.tag_id, "name": db.query(Tag).filter(Tag.id == dt.tag_id).first().name if db.query(Tag).filter(Tag.id == dt.tag_id).first() else ""}
                    for dt in (doc.tags or [])
                ],
            }
            for doc in documents
        ]
    }


@app.delete("/api/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    document = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not current_user.is_admin and document.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    # Remove from vector store (both text and multimodal)
    rag_engine = get_rag_engine()
    removed = rag_engine.delete_document_chunks(document.filename)

    # Remove from knowledge graph
    try:
        kg_engine = get_kg_engine()
        kg_engine.remove_document_from_graph(str(document.id))
    except Exception as e:
        print(f"KG cleanup error (non-fatal): {e}")

    # Remove file from disk
    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()

    db.delete(document)
    db.commit()

    return {"message": f"Document deleted, chunks removed from knowledge base"}


# ==================== CHAT ENDPOINTS (Enhanced Multimodal) ====================

@app.post("/api/chat/query", response_model=ChatResponse)
async def chat_query(
    query: ChatQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Query the knowledge base with multimodal RAG.
    Searches across text, images, tables, and equations.
    """
    from app.multimodal.query_engine import QueryEngine

    rag_engine = get_rag_engine()
    query_engine = QueryEngine(rag_engine)

    result = query_engine.query(
        question=query.question,
        mode=query.search_mode,
        k=query.k,
        use_knowledge_graph=query.use_knowledge_graph,
        include_multimodal=query.include_multimodal,
    )

    # Save conversation
    conversation = Conversation(
        user_id=current_user.id,
        question=query.question,
        answer=result["answer"],
        sources_used=str(result.get("num_sources", 0)),
        context_used=query.use_context
    )
    db.add(conversation)
    db.commit()

    return result


@app.get("/api/chat/history")
async def get_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50
):
    conversations = db.query(Conversation)\
        .filter(Conversation.user_id == current_user.id)\
        .order_by(Conversation.created_at.desc())\
        .limit(limit)\
        .all()

    return {
        "total": len(conversations),
        "conversations": [
            {
                "id": conv.id,
                "question": conv.question,
                "answer": conv.answer,
                "created_at": conv.created_at.isoformat()
            }
            for conv in conversations
        ]
    }


@app.delete("/api/chat/history")
async def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db.query(Conversation).filter(Conversation.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Chat history cleared"}


# ==================== MULTIMODAL INFO ENDPOINT ====================

@app.get("/api/multimodal/info")
async def get_multimodal_info(
    current_user: User = Depends(get_current_user),
):
    """Get information about multimodal processing capabilities."""
    rag_engine = get_rag_engine()
    return rag_engine.get_multimodal_info()


@app.get("/api/multimodal/stats")
async def get_multimodal_stats(
    current_user: User = Depends(get_current_user),
):
    """Get multimodal processing statistics."""
    rag_engine = get_rag_engine()
    stats = rag_engine.get_stats()
    return stats


# ==================== SEARCH ENDPOINT ====================

@app.get("/api/search")
async def search_documents(
    q: str,
    k: int = 10,
    include_multimodal: bool = True,
    current_user: User = Depends(get_current_user),
):
    """
    Search the knowledge base.
    Returns raw search results without LLM answer generation.
    """
    from app.multimodal.query_engine import QueryEngine

    rag_engine = get_rag_engine()
    query_engine = QueryEngine(rag_engine)

    return query_engine.get_search_results_only(
        question=q,
        k=k,
        include_multimodal=include_multimodal,
    )


# ==================== ADMIN ENDPOINTS ====================

@app.get("/api/admin/stats")
async def get_stats(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    rag_engine = get_rag_engine()

    total_users = db.query(User).count()
    total_documents = db.query(DBDocument).count()
    total_conversations = db.query(Conversation).count()
    active_users = db.query(User).filter(User.is_active == True).count()

    rag_stats = rag_engine.get_stats()

    # Knowledge Graph stats
    kg_stats = {}
    try:
        kg_engine = get_kg_engine()
        kg_stats = kg_engine.get_stats()
    except Exception:
        kg_stats = {"total_nodes": 0, "total_edges": 0, "entity_types": {}, "relation_types": {}}

    return {
        "users": total_users,
        "active_users": active_users,
        "documents": total_documents,
        "conversations": total_conversations,
        **rag_stats,
        "knowledge_graph": kg_stats
    }


@app.get("/api/admin/users")
async def list_users(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return {
        "total": len(users),
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat()
            }
            for u in users
        ]
    }


@app.put("/api/admin/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin

    db.commit()
    return {"message": "User updated successfully"}


@app.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


# ==================== HEALTH CHECK ====================

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check with service status"""
    health_status = {
        "status": "healthy",
        "service": "LocalAIChatBox",
        "version": "6.0.0 - LightRAG Edition",
        "services": {}
    }

    # Check database
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "ok"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"

    # Check Ollama
    try:
        import os
        import requests
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        response = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            health_status["services"]["ollama"] = {"status": "ok", "models": models}
        else:
            health_status["services"]["ollama"] = "unreachable"
    except Exception:
        health_status["services"]["ollama"] = "unreachable"

    # Check RAG Engine
    try:
        rag_engine = get_rag_engine()
        stats = rag_engine.get_stats()
        health_status["services"]["rag_engine"] = {
            "status": "ok",
            "text_chunks": stats.get("text_chunks", 0),
            "multimodal_chunks": stats.get("multimodal_chunks", 0),
        }
    except Exception as e:
        health_status["services"]["rag_engine"] = f"error: {str(e)}"

    # Check Knowledge Graph
    try:
        kg_engine = get_kg_engine()
        kg_stats = kg_engine.get_stats()
        health_status["services"]["knowledge_graph"] = {
            "status": "ok",
            "nodes": kg_stats.get("total_nodes", 0),
            "edges": kg_stats.get("total_edges", 0),
        }
    except Exception as e:
        health_status["services"]["knowledge_graph"] = f"error: {str(e)}"

    return health_status


# ==================== KNOWLEDGE GRAPH ENDPOINTS ====================

@app.get("/api/knowledge-graph/stats")
async def kg_stats(current_user: User = Depends(get_current_user)):
    try:
        kg_engine = get_kg_engine()
        return kg_engine.get_stats()
    except Exception as e:
        return {"total_nodes": 0, "total_edges": 0, "entity_types": {}, "relation_types": {}, "error": str(e)}


@app.get("/api/knowledge-graph/entities")
async def kg_list_entities(current_user: User = Depends(get_current_user)):
    kg_engine = get_kg_engine()
    entities = kg_engine.get_all_entities()
    return {"total": len(entities), "entities": entities}


@app.get("/api/knowledge-graph/search")
async def kg_search_entities(q: str, current_user: User = Depends(get_current_user)):
    kg_engine = get_kg_engine()
    entities = kg_engine.find_entities(q)
    return {"query": q, "results": entities}


@app.get("/api/knowledge-graph/entity/{entity_name}")
async def kg_get_entity(
    entity_name: str,
    hops: int = 2,
    current_user: User = Depends(get_current_user)
):
    kg_engine = get_kg_engine()
    subgraph = kg_engine.get_entity_subgraph(entity_name, max_hops=min(hops, 3))
    return subgraph


@app.post("/api/knowledge-graph/rebuild")
async def kg_rebuild(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Rebuild knowledge graph from all documents (admin only)"""
    kg_engine = get_kg_engine()
    kg_engine.clear()

    documents = db.query(DBDocument).filter(DBDocument.is_indexed == True).all()

    results = []
    for doc in documents:
        try:
            file_path = Path(doc.file_path)
            if not file_path.exists():
                results.append({"filename": doc.filename, "status": "file_not_found"})
                continue

            from app.multimodal.document_parser import DocumentParserService
            parser = DocumentParserService()
            parsed = parser.parse_document(str(file_path))

            kg_result = kg_engine.add_document_to_graph(
                doc_id=str(doc.id),
                filename=doc.filename,
                chunks=parsed["chunks"][:20]
            )
            results.append({"filename": doc.filename, "status": "success", **kg_result})
        except Exception as e:
            results.append({"filename": doc.filename, "status": "error", "error": str(e)})

    stats = kg_engine.get_stats()
    return {
        "message": "Knowledge graph rebuilt",
        "documents_processed": len(results),
        "results": results,
        "graph_stats": stats
    }


# ==================== BATCH PROCESSING ENDPOINT ====================

@app.post("/api/documents/batch-process")
async def batch_process_documents(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Re-process all existing documents with multimodal extraction (admin only)."""
    rag_engine = get_rag_engine()
    documents = db.query(DBDocument).filter(DBDocument.is_indexed == True).all()

    results = []
    for doc in documents:
        try:
            file_path = Path(doc.file_path)
            if not file_path.exists():
                results.append({"filename": doc.filename, "status": "file_not_found"})
                continue

            result = rag_engine.process_document_complete(
                file_path=str(file_path),
                doc_id=f"doc_{doc.uploaded_by}_{doc.filename}",
                filename=doc.filename,
                user_id=doc.uploaded_by,
                username=doc.uploader.username if doc.uploader else "system",
                enable_multimodal=True,
            )

            results.append({
                "filename": doc.filename,
                "status": result.get("status", "success"),
                "text_chunks": result.get("text_chunks", 0),
                "multimodal_items": result.get("multimodal_items", 0),
                "entities": result.get("entities_added", 0),
            })
        except Exception as e:
            results.append({"filename": doc.filename, "status": "error", "error": str(e)})

    return {
        "message": "Batch processing complete",
        "documents_processed": len(results),
        "results": results,
    }


# ==================== FOLDER MANAGEMENT ENDPOINTS ====================

@app.post("/api/folders")
async def create_folder(
    folder_data: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new folder for organizing documents."""
    folder = Folder(
        name=folder_data.name,
        parent_id=folder_data.parent_id,
        created_by=current_user.id,
        color=folder_data.color or "#4f8cff",
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id, "color": folder.color}


@app.get("/api/folders")
async def list_folders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all folders with document counts."""
    folders = db.query(Folder).order_by(Folder.name).all()
    result = []
    for f in folders:
        doc_count = db.query(DBDocument).filter(DBDocument.folder_id == f.id).count()
        result.append({
            "id": f.id,
            "name": f.name,
            "parent_id": f.parent_id,
            "color": f.color,
            "document_count": doc_count,
            "created_by": f.creator.username if f.creator else "Unknown",
            "created_at": f.created_at.isoformat(),
        })
    return {"folders": result}


@app.put("/api/folders/{folder_id}")
async def update_folder(
    folder_id: int,
    folder_data: FolderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder_data.name is not None:
        folder.name = folder_data.name
    if folder_data.parent_id is not None:
        folder.parent_id = folder_data.parent_id
    if folder_data.color is not None:
        folder.color = folder_data.color
    db.commit()
    return {"message": "Folder updated"}


@app.delete("/api/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    # Move documents out of folder
    db.query(DBDocument).filter(DBDocument.folder_id == folder_id).update({"folder_id": None})
    # Move child folders out
    db.query(Folder).filter(Folder.parent_id == folder_id).update({"parent_id": folder.parent_id})
    db.delete(folder)
    db.commit()
    return {"message": "Folder deleted"}


@app.put("/api/documents/{doc_id}/move")
async def move_document_to_folder(
    doc_id: int,
    move_data: DocumentMoveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.folder_id = move_data.folder_id
    db.commit()
    return {"message": "Document moved"}


# ==================== TAG MANAGEMENT ENDPOINTS ====================

@app.post("/api/tags")
async def create_tag(
    tag_data: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(Tag).filter(Tag.name == tag_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")
    tag = Tag(name=tag_data.name, color=tag_data.color or "#4f8cff")
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "color": tag.color}


@app.get("/api/tags")
async def list_tags(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tags = db.query(Tag).order_by(Tag.name).all()
    result = []
    for t in tags:
        doc_count = db.query(DocumentTag).filter(DocumentTag.tag_id == t.id).count()
        result.append({"id": t.id, "name": t.name, "color": t.color, "document_count": doc_count})
    return {"tags": result}


@app.delete("/api/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.query(DocumentTag).filter(DocumentTag.tag_id == tag_id).delete()
    db.delete(tag)
    db.commit()
    return {"message": "Tag deleted"}


@app.put("/api/documents/{doc_id}/tags")
async def set_document_tags(
    doc_id: int,
    tag_data: DocumentTagRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clear existing tags
    db.query(DocumentTag).filter(DocumentTag.document_id == doc_id).delete()

    # Add new tags
    for tag_id in tag_data.tag_ids:
        dt = DocumentTag(document_id=doc_id, tag_id=tag_id)
        db.add(dt)

    db.commit()
    return {"message": "Tags updated"}


# ==================== DOCUMENT VERSIONING ====================

@app.post("/api/documents/{doc_id}/version")
async def upload_document_version(
    doc_id: int,
    file: UploadFile = File(...),
    change_note: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a new version of an existing document."""
    doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    rag_engine = get_rag_engine()
    documents_path = Path("/app/data/documents")
    documents_path.mkdir(parents=True, exist_ok=True)

    # Save old version record
    old_version = DocumentVersion(
        document_id=doc.id,
        version_number=doc.version,
        filename=doc.filename,
        file_path=doc.file_path,
        file_size_mb=doc.file_size_mb,
        num_chunks=doc.num_chunks,
        uploaded_by=doc.uploaded_by,
        change_note=change_note or f"Version {doc.version}",
    )
    db.add(old_version)

    # Save new file
    new_version = doc.version + 1
    file_path = documents_path / f"{current_user.id}_v{new_version}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Remove old chunks from vector store
    rag_engine.delete_document_chunks(doc.filename)

    # Process new version
    result = rag_engine.process_document_complete(
        file_path=str(file_path),
        doc_id=f"doc_{current_user.id}_{file.filename}",
        filename=file.filename,
        user_id=current_user.id,
        username=current_user.username,
        enable_multimodal=True,
    )

    # Update document record
    doc.filename = file.filename
    doc.original_filename = file.filename
    doc.file_path = str(file_path)
    doc.file_size_mb = round(file_path.stat().st_size / (1024 * 1024), 2)
    doc.file_type = file_path.suffix
    doc.num_chunks = result.get("text_chunks", 0)
    doc.version = new_version
    db.commit()

    log_usage(db, current_user.id, "upload", "document", str(doc_id), {"action": "version_update", "version": new_version})

    return {
        "message": f"Version {new_version} uploaded",
        "version": new_version,
        "chunks": result.get("text_chunks", 0),
        "status": result.get("status", "success"),
    }


@app.get("/api/documents/{doc_id}/versions")
async def get_document_versions(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(DocumentVersion.version_number.desc()).all()

    return {
        "current_version": doc.version,
        "versions": [
            {
                "version_number": v.version_number,
                "filename": v.filename,
                "file_size_mb": v.file_size_mb,
                "num_chunks": v.num_chunks,
                "uploaded_by": v.uploader.username if v.uploader else "Unknown",
                "created_at": v.created_at.isoformat(),
                "change_note": v.change_note,
            }
            for v in versions
        ],
    }


# ==================== CHAT SESSION ENDPOINTS (Multi-turn) ====================

@app.post("/api/chat/sessions")
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session for multi-turn conversations."""
    session = ChatSession(
        user_id=current_user.id,
        title=session_data.title or "New Chat",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "title": session.title, "created_at": session.created_at.isoformat()}


@app.get("/api/chat/sessions")
async def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all chat sessions for the current user."""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True,
    ).order_by(ChatSession.updated_at.desc()).all()

    result = []
    for s in sessions:
        msg_count = db.query(Conversation).filter(Conversation.session_id == s.id).count()
        last_msg = db.query(Conversation).filter(
            Conversation.session_id == s.id
        ).order_by(Conversation.created_at.desc()).first()

        result.append({
            "id": s.id,
            "title": s.title,
            "message_count": msg_count,
            "last_message": last_msg.question[:100] if last_msg else None,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        })

    return {"sessions": result}


@app.get("/api/chat/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages in a chat session."""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(Conversation).filter(
        Conversation.session_id == session_id
    ).order_by(Conversation.created_at.asc()).all()

    return {
        "session_id": session_id,
        "title": session.title,
        "messages": [
            {
                "id": m.id,
                "question": m.question,
                "answer": m.answer,
                "sources_used": m.sources_used,
                "entities_found": m.entities_found,
                "search_mode": m.search_mode,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@app.put("/api/chat/sessions/{session_id}")
async def update_chat_session(
    session_id: str,
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = session_data.title or session.title
    db.commit()
    return {"message": "Session updated"}


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Delete messages in session
    db.query(Conversation).filter(Conversation.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}


@app.post("/api/chat/query-multiturn")
async def chat_query_multiturn(
    query: ChatQueryMultiTurn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Multi-turn chat query with conversation context.
    Sends previous conversation turns to LLM for context-aware answers.
    Inspired by LightRAG's conversation history support.
    """
    from app.multimodal.query_engine import QueryEngine

    rag_engine = get_rag_engine()
    query_engine = QueryEngine(rag_engine)

    # Handle session
    session_id = query.session_id
    if not session_id:
        # Create new session
        session = ChatSession(user_id=current_user.id, title=query.question[:80])
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    else:
        session = db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    # Build conversation context from previous turns
    conversation_context = ""
    if query.context_turns > 0:
        prev_messages = db.query(Conversation).filter(
            Conversation.session_id == session_id
        ).order_by(Conversation.created_at.desc()).limit(query.context_turns).all()

        if prev_messages:
            prev_messages.reverse()
            context_parts = []
            for msg in prev_messages:
                context_parts.append(f"User: {msg.question}")
                # Truncate long answers in context
                answer_preview = msg.answer[:500] if len(msg.answer) > 500 else msg.answer
                context_parts.append(f"Assistant: {answer_preview}")
            conversation_context = "\n".join(context_parts)

    # Build enhanced question with conversation context
    enhanced_question = query.question
    if conversation_context:
        enhanced_question = (
            f"Previous conversation context:\n{conversation_context}\n\n"
            f"Current question: {query.question}\n\n"
            f"Answer the current question considering the conversation context above."
        )

    # Execute query
    result = query_engine.query(
        question=enhanced_question,
        mode=query.search_mode,
        k=query.k,
        use_knowledge_graph=query.use_knowledge_graph,
        include_multimodal=query.include_multimodal,
    )

    # Save conversation
    entities_json = json.dumps(result.get("entities_found", []), default=str) if result.get("entities_found") else None
    conversation = Conversation(
        user_id=current_user.id,
        session_id=session_id,
        question=query.question,
        answer=result["answer"],
        sources_used=str(result.get("num_sources", 0)),
        entities_found=entities_json,
        search_mode=query.search_mode,
        context_used=query.use_context,
    )
    db.add(conversation)

    # Update session title if it's the first message
    msg_count = db.query(Conversation).filter(Conversation.session_id == session_id).count()
    if msg_count == 0:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.title = query.question[:80]

    db.commit()

    # Log usage
    log_usage(db, current_user.id, "query", "chat", session_id, {
        "search_mode": query.search_mode,
        "use_kg": query.use_knowledge_graph,
        "context_turns": query.context_turns,
    })

    result["session_id"] = session_id
    return result


# ==================== ADVANCED SEARCH & FILTERS ====================

@app.get("/api/documents/search")
async def search_documents_advanced(
    q: str = "",
    file_type: str = "",
    folder_id: int = None,
    tag_id: int = None,
    uploaded_by: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced document search with filters and faceted results.
    Inspired by LightRAG's document listing with status filters.
    """
    from sqlalchemy import or_
    from datetime import datetime as dt

    query = db.query(DBDocument)

    # Text search
    if q:
        query = query.filter(
            or_(
                DBDocument.filename.ilike(f"%{q}%"),
                DBDocument.original_filename.ilike(f"%{q}%"),
                DBDocument.description.ilike(f"%{q}%"),
            )
        )

    # File type filter
    if file_type:
        query = query.filter(DBDocument.file_type == file_type)

    # Folder filter
    if folder_id is not None:
        if folder_id == 0:  # Root / unfiled
            query = query.filter(DBDocument.folder_id == None)
        else:
            query = query.filter(DBDocument.folder_id == folder_id)

    # Tag filter
    if tag_id:
        doc_ids = [dt.document_id for dt in db.query(DocumentTag).filter(DocumentTag.tag_id == tag_id).all()]
        query = query.filter(DBDocument.id.in_(doc_ids))

    # User filter
    if uploaded_by:
        user_obj = db.query(User).filter(User.username == uploaded_by).first()
        if user_obj:
            query = query.filter(DBDocument.uploaded_by == user_obj.id)

    # Date range
    if date_from:
        try:
            query = query.filter(DBDocument.uploaded_at >= dt.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(DBDocument.uploaded_at <= dt.fromisoformat(date_to))
        except ValueError:
            pass

    # Get total count before pagination
    total = query.count()

    # Sorting
    if sort_by == "name":
        order_col = DBDocument.filename
    elif sort_by == "size":
        order_col = DBDocument.file_size_mb
    elif sort_by == "chunks":
        order_col = DBDocument.num_chunks
    elif sort_by == "type":
        order_col = DBDocument.file_type
    else:
        order_col = DBDocument.uploaded_at

    if sort_order == "asc":
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())

    # Pagination
    documents = query.offset((page - 1) * page_size).limit(page_size).all()

    # Build facets
    all_types = db.query(DBDocument.file_type, func.count(DBDocument.id)).group_by(DBDocument.file_type).all()
    all_uploaders = db.query(User.username, func.count(DBDocument.id)).join(
        DBDocument, DBDocument.uploaded_by == User.id
    ).group_by(User.username).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "file_size_mb": doc.file_size_mb,
                "uploaded_by": doc.uploader.username if doc.uploader else "Unknown",
                "uploaded_at": doc.uploaded_at.isoformat(),
                "num_chunks": doc.num_chunks,
                "is_indexed": doc.is_indexed,
                "folder_id": doc.folder_id,
                "version": doc.version,
                "description": doc.description,
                "tags": [
                    {"id": dt.tag_id, "name": db.query(Tag).filter(Tag.id == dt.tag_id).first().name if db.query(Tag).filter(Tag.id == dt.tag_id).first() else ""}
                    for dt in (doc.tags or [])
                ],
            }
            for doc in documents
        ],
        "facets": {
            "file_types": [{"type": t[0] or "unknown", "count": t[1]} for t in all_types],
            "uploaders": [{"username": u[0], "count": u[1]} for u in all_uploaders],
        },
    }


# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/analytics/overview")
async def analytics_overview(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get usage analytics overview."""
    return get_usage_overview(db, days)


@app.get("/api/analytics/daily")
async def analytics_daily(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get daily activity data for charts."""
    return {"daily_activity": get_daily_activity(db, days)}


@app.get("/api/analytics/top-users")
async def analytics_top_users(
    days: int = 30,
    limit: int = 10,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get most active users (admin only)."""
    return {"top_users": get_top_users(db, days, limit)}


@app.get("/api/analytics/popular-queries")
async def analytics_popular_queries(
    days: int = 30,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get most common queries."""
    return {"popular_queries": get_popular_queries(db, days, limit)}


@app.get("/api/analytics/documents")
async def analytics_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document analytics."""
    return get_document_stats(db)


@app.get("/api/analytics/actions")
async def analytics_actions(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get action type breakdown."""
    return {"actions": get_action_breakdown(db, days)}


# ==================== EXPORT ENDPOINTS ====================

@app.get("/api/export/chat")
async def export_chat(
    format: str = "json",
    session_id: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export chat history as JSON, CSV, or Markdown."""
    try:
        result = export_chat_history(db, current_user.id, session_id, format)
        log_usage(db, current_user.id, "export", "chat", session_id, {"format": format})
        return Response(
            content=result["content"],
            media_type=result["content_type"],
            headers={"Content-Disposition": f"attachment; filename={result['filename']}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/export/research/{task_id}")
async def export_research(
    task_id: str,
    format: str = "markdown",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export a research report."""
    result = export_research_report(db, task_id, current_user.id, format)
    if not result:
        raise HTTPException(status_code=404, detail="Research task not found")
    log_usage(db, current_user.id, "export", "research", task_id, {"format": format})
    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={"Content-Disposition": f"attachment; filename={result['filename']}"},
    )


@app.get("/api/export/knowledge-graph")
async def export_kg(
    format: str = "json",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export knowledge graph as JSON, CSV, or GraphML."""
    try:
        kg_engine = get_kg_engine()
        result = export_knowledge_graph(kg_engine, format)
        log_usage(db, current_user.id, "export", "kg", None, {"format": format})
        return Response(
            content=result["content"],
            media_type=result["content_type"],
            headers={"Content-Disposition": f"attachment; filename={result['filename']}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/export/documents")
async def export_docs(
    format: str = "csv",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export documents list as CSV or JSON."""
    try:
        result = export_documents_list(db, format)
        log_usage(db, current_user.id, "export", "documents", None, {"format": format})
        return Response(
            content=result["content"],
            media_type=result["content_type"],
            headers={"Content-Disposition": f"attachment; filename={result['filename']}"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== KNOWLEDGE GRAPH FULL DATA (for visualization) ====================

@app.get("/api/knowledge-graph/full")
async def kg_full_graph(
    max_nodes: int = 500,
    current_user: User = Depends(get_current_user)
):
    """
    Get the full knowledge graph data for interactive visualization.
    Returns nodes and edges suitable for D3.js / Cytoscape rendering.
    Inspired by LightRAG's graph visualization API.
    """
    kg_engine = get_kg_engine()
    graph = kg_engine.graph

    nodes = []
    for node_name, data in list(graph.nodes(data=True))[:max_nodes]:
        degree = graph.degree(node_name)
        nodes.append({
            "id": node_name,
            "type": data.get("type", "CONCEPT"),
            "source_files": data.get("source_files", []),
            "degree": degree,
        })

    node_ids = {n["id"] for n in nodes}
    edges = []
    for u, v, data in graph.edges(data=True):
        if u in node_ids and v in node_ids:
            edges.append({
                "source": u,
                "target": v,
                "relation": data.get("relation", "RELATED_TO"),
                "source_file": data.get("source_file", ""),
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
    }