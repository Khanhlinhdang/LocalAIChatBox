from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta
import shutil
from pathlib import Path

from app.database import get_db, init_db
from app.models import User, Document as DBDocument, Conversation
from app.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, get_current_admin
)
from app.rag_engine import get_rag_engine
from app.knowledge_graph import get_kg_engine
from app.document_processor import DocumentProcessor
from app.research_routes import router as research_router
from pydantic import BaseModel, EmailStr

app = FastAPI(
    title="Company RAG Chat API",
    version="2.0.0",
    description="Private company knowledge base chat system with deep research"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount research router
app.include_router(research_router)


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
                is_admin=True
            )
            db.add(admin)
            db.commit()
            print("Default admin user created (admin / admin123)")
    finally:
        db.close()

    # Initialize deep research service
    try:
        from app.deep_research import get_research_service
        get_research_service()
        print("Deep Research Service initialized")
    except Exception as e:
        print(f"Warning: Deep Research Service init failed (non-fatal): {e}")

    print("Company RAG Chat Server Started (v2.0 with Deep Research)")


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
    k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    num_sources: int
    entities_found: Optional[List[dict]] = None
    graph_connections: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ==================== AUTH ENDPOINTS ====================

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        # Check if username exists
        if db.query(User).filter(User.username == user_data.username).first():
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )

        # Check if email exists
        if db.query(User).filter(User.email == user_data.email).first():
            raise HTTPException(
                status_code=400,
                detail="Email already exists"
            )

        # Create new user
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

        # Create access token
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
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user and return JWT token"""
    try:
        # Find user by username
        user = db.query(User).filter(User.username == credentials.username).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Verify password
        if not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="User account is disabled"
            )

        # Create access token
        access_token = create_access_token(data={"sub": user.username})

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
        print(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}"
        )


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin
    }


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


# ==================== DOCUMENT ENDPOINTS ====================

@app.post("/api/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rag_engine = get_rag_engine()
    doc_processor = DocumentProcessor()
    documents_path = Path("/app/data/documents")
    documents_path.mkdir(parents=True, exist_ok=True)

    uploaded_files = []

    for file in files:
        file_path = documents_path / f"{current_user.id}_{file.filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            result = doc_processor.process_file(str(file_path))

            metadatas = [
                {
                    "filename": file.filename,
                    "uploaded_by": current_user.username,
                    "user_id": current_user.id,
                    "chunk_id": i
                }
                for i in range(len(result["chunks"]))
            ]

            rag_engine.add_documents(result["chunks"], metadatas)

            db_document = DBDocument(
                filename=file.filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_size_mb=round(file_path.stat().st_size / (1024 * 1024), 2),
                file_type=file_path.suffix,
                num_chunks=result["num_chunks"],
                uploaded_by=current_user.id,
                is_indexed=True
            )

            db.add(db_document)
            db.commit()
            db.refresh(db_document)

            # Extract entities for Knowledge Graph
            kg_result = {"entities_added": 0, "relations_added": 0}
            try:
                kg_engine = get_kg_engine()
                kg_result = kg_engine.add_document_to_graph(
                    doc_id=str(db_document.id),
                    filename=file.filename,
                    chunks=result["chunks"]
                )
            except Exception as e:
                print(f"Knowledge Graph extraction error (non-fatal): {e}")

            uploaded_files.append({
                "filename": file.filename,
                "chunks": result["num_chunks"],
                "entities": kg_result.get("entities_added", 0),
                "relations": kg_result.get("relations_added", 0),
                "status": "success"
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
                "is_indexed": doc.is_indexed
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

    # Remove from vector store
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

    return {"message": f"Document deleted, {removed} chunks removed from knowledge base"}


# ==================== CHAT ENDPOINTS ====================

@app.post("/api/chat/query", response_model=ChatResponse)
async def chat_query(
    query: ChatQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rag_engine = get_rag_engine()

    # Get Knowledge Graph context if enabled
    graph_context = ""
    entities_found = []
    graph_connections = 0

    if query.use_knowledge_graph:
        try:
            kg_engine = get_kg_engine()
            graph_context = kg_engine.get_graph_context(query.question)
            entities = kg_engine.find_entities(query.question)
            entities_found = entities[:5]
            for e in entities_found[:3]:
                sub = kg_engine.get_entity_subgraph(e['name'], max_hops=2)
                graph_connections += len(sub.get('edges', []))
        except Exception as e:
            print(f"Knowledge Graph error (non-fatal): {e}")

    result = rag_engine.query_with_context(query.question, k=query.k, graph_context=graph_context)

    # Add KG info to result
    result["entities_found"] = entities_found
    result["graph_connections"] = graph_connections

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
    db.query(Conversation)\
        .filter(Conversation.user_id == current_user.id)\
        .delete()
    db.commit()
    return {"message": "Chat history cleared"}


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
    """Health check endpoint with database connectivity test"""
    health_status = {
        "status": "healthy",
        "service": "Company RAG Chat",
        "version": "2.0",
        "services": {}
    }
    
    # Check database
    try:
        db.execute("SELECT 1")
        health_status["services"]["database"] = "ok"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Ollama (optional)
    try:
        import os
        import requests
        ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
        response = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if response.status_code == 200:
            health_status["services"]["ollama"] = "ok"
        else:
            health_status["services"]["ollama"] = "unreachable"
    except:
        health_status["services"]["ollama"] = "unreachable"
    
    return health_status


# ==================== KNOWLEDGE GRAPH ENDPOINTS ====================

@app.get("/api/knowledge-graph/stats")
async def kg_stats(
    current_user: User = Depends(get_current_user)
):
    """Get Knowledge Graph statistics"""
    try:
        kg_engine = get_kg_engine()
        return kg_engine.get_stats()
    except Exception as e:
        return {"total_nodes": 0, "total_edges": 0, "entity_types": {}, "relation_types": {}, "error": str(e)}


@app.get("/api/knowledge-graph/entities")
async def kg_list_entities(
    current_user: User = Depends(get_current_user)
):
    """List all entities in the Knowledge Graph"""
    kg_engine = get_kg_engine()
    entities = kg_engine.get_all_entities()
    return {"total": len(entities), "entities": entities}


@app.get("/api/knowledge-graph/search")
async def kg_search_entities(
    q: str,
    current_user: User = Depends(get_current_user)
):
    """Search for entities by name"""
    kg_engine = get_kg_engine()
    entities = kg_engine.find_entities(q)
    return {"query": q, "results": entities}


@app.get("/api/knowledge-graph/entity/{entity_name}")
async def kg_get_entity(
    entity_name: str,
    hops: int = 2,
    current_user: User = Depends(get_current_user)
):
    """Get subgraph around a specific entity"""
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

    doc_processor = DocumentProcessor()
    documents = db.query(DBDocument).filter(DBDocument.is_indexed == True).all()

    results = []
    for doc in documents:
        try:
            file_path = Path(doc.file_path)
            if not file_path.exists():
                results.append({"filename": doc.filename, "status": "file_not_found"})
                continue

            processed = doc_processor.process_file(str(file_path))
            kg_result = kg_engine.add_document_to_graph(
                doc_id=str(doc.id),
                filename=doc.filename,
                chunks=processed["chunks"]
            )
            results.append({
                "filename": doc.filename,
                "status": "success",
                **kg_result
            })
        except Exception as e:
            results.append({"filename": doc.filename, "status": "error", "error": str(e)})

    stats = kg_engine.get_stats()
    return {
        "message": "Knowledge graph rebuilt",
        "documents_processed": len(results),
        "results": results,
        "graph_stats": stats
    }
