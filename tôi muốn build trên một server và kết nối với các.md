<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# tôi muốn build trên một server và kết nối với các máy tính trong mạng LAN để dùng, vẫn mục tiêu là tạo chatAI cho team/Công ty dùng riêng để train dữ liệu nội bộ để dùng. Thì phương án như trên có thực hiện được  không? nếu có hãy tạo tutorial từng bước thực hiện, cụ thể để làm được điều đó.

Hoàn hảo! Tôi đã có đủ thông tin để tạo hướng dẫn chi tiết. Đây là solution architecture và implementation guide:

***

## 🏢 Architecture Overview: Private Company RAG Chat System

```
┌─────────────────────────────────────────────────────────────┐
│                    Company LAN Network                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Employee   │  │   Employee   │  │   Employee   │      │
│  │   PC #1      │  │   PC #2      │  │   PC #3      │      │
│  │ (Browser)    │  │ (Browser)    │  │ (Browser)    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         └─────────────────┼─────────────────┘               │
│                           │                                 │
│                           ▼                                 │
│              ┌─────────────────────────┐                    │
│              │   Nginx Reverse Proxy   │                    │
│              │   (Port 80/443)         │                    │
│              └────────────┬────────────┘                    │
│                           │                                 │
│              ┌────────────┴────────────┐                    │
│              │                         │                    │
│              ▼                         ▼                    │
│  ┌─────────────────────┐   ┌─────────────────────┐        │
│  │  FastAPI Backend    │   │   Static Files      │        │
│  │  (Port 8000)        │   │   (React Frontend)  │        │
│  │  - Authentication   │   │   (Port 3000)       │        │
│  │  - RAG Engine       │   │                     │        │
│  │  - Document Upload  │   │                     │        │
│  └──────────┬──────────┘   └─────────────────────┘        │
│             │                                               │
│  ┌──────────┴──────────┐                                   │
│  │                     │                                   │
│  ▼                     ▼                                   │
│ ┌─────────────┐  ┌──────────────┐                         │
│ │   Ollama    │  │ PostgreSQL   │                         │
│ │  (LLM +     │  │ - Users      │                         │
│ │ Embeddings) │  │ - Sessions   │                         │
│ │ Port 11434  │  │ - Documents  │                         │
│ └─────────────┘  └──────────────┘                         │
│                                                            │
│ ┌────────────────────────────────┐                        │
│ │   FAISS Vector Store           │                        │
│ │   (Shared Knowledge Base)      │                        │
│ └────────────────────────────────┘                        │
│                                                            │
│              🖥️  Central Server                           │
│              IP: 192.168.1.100 (ví dụ)                    │
└────────────────────────────────────────────────────────────┘
```


***

## 📋 Prerequisites

### **Hardware Requirements:**

**Server (Central Machine):**

- CPU: 8+ cores recommended
- RAM: 32GB+ (16GB minimum)
- Storage: 500GB+ SSD
- GPU: Optional (RTX 3060+ để tăng tốc)
- Network: Gigabit Ethernet

**Client Machines:**

- Any computer with web browser
- Kết nối LAN tốt


### **Software Requirements:**

```bash
# Server cần cài:
- Ubuntu 22.04 LTS (hoặc Debian-based Linux)
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+
```


***

## 🚀 PHASE 1: Setup Server Infrastructure

### **Step 1.1: Chuẩn Bị Server**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y git curl wget vim build-essential

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install -y docker-compose

# Reboot để apply docker group
sudo reboot
```


### **Step 1.2: Install Ollama**

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
sudo systemctl enable ollama
sudo systemctl start ollama

# Download models
ollama pull llama3.1          # LLM chính
ollama pull nomic-embed-text  # Embedding model
# hoặc với GPU mạnh:
# ollama pull qwen2.5:14b
```


### **Step 1.3: Tạo Project Structure**

```bash
# Create project directory
mkdir -p ~/company-rag-chat
cd ~/company-rag-chat

# Create structure
mkdir -p {backend,frontend,nginx,data/{documents,vector_store,database}}
```


***

## 🔧 PHASE 2: Build Backend API (FastAPI)

### **Step 2.1: Backend Dependencies**

Tạo `backend/requirements.txt`:

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1

# RAG components
ollama==0.1.6
faiss-cpu==1.7.4
numpy==1.26.3

# Document processing
pymupdf==1.23.21
python-docx==1.1.0
Pillow==10.2.0
pytesseract==0.3.10

# Utilities
aiofiles==23.2.1
pydantic==2.5.3
pydantic-settings==2.1.0
```


### **Step 2.2: Environment Configuration**

Tạo `backend/.env`:

```bash
# Application
APP_NAME="Company RAG Chat"
APP_VERSION="1.0.0"
DEBUG=False
HOST=0.0.0.0
PORT=8000

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# Database
DATABASE_URL=postgresql://raguser:ragpassword@postgres:5432/ragdb

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.1
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_CONTEXT_LENGTH=4096

# Vector Store
VECTOR_STORE_PATH=/app/data/vector_store
DOCUMENTS_PATH=/app/data/documents

# Limits
MAX_FILE_SIZE_MB=100
MAX_FILES_PER_UPLOAD=10
MAX_USERS=100
```


### **Step 2.3: Database Models**

Tạo `backend/app/models.py`:

```python
"""
Database models cho multi-user system
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

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
    
    # Relationships
    documents = relationship("Document", back_populates="uploader")
    conversations = relationship("Conversation", back_populates="user")


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
    
    # Relationships
    uploader = relationship("User", back_populates="documents")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources_used = Column(Text)  # JSON string of source document IDs
    context_used = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="conversations")
```


### **Step 2.4: Authentication System**

Tạo `backend/app/auth.py`:

```python
"""
JWT Authentication cho multi-user system
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
import os

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = decode_token(token)
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verify user is admin"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
```


### **Step 2.5: Database Connection**

Tạo `backend/app/database.py`:

```python
"""
Database connection và session management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models import Base
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://raguser:ragpassword@localhost:5432/ragdb"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")


def get_db() -> Session:
    """Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```


### **Step 2.6: RAG Engine (Shared Knowledge Base)**

Tạo `backend/app/rag_engine.py`:

```python
"""
Shared RAG Engine cho toàn công ty
Tất cả users dùng chung một knowledge base
"""

import ollama
import faiss
import numpy as np
import pickle
import os
from typing import List, Dict
from pathlib import Path

class SharedRAGEngine:
    """
    RAG Engine được share giữa tất cả users
    """
    
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
        self.embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
        self.vector_store_path = Path(os.getenv("VECTOR_STORE_PATH", "./data/vector_store"))
        
        self.embedding_dim = 768  # nomic-embed-text dimension
        self.index = None
        self.documents = []
        self.metadatas = []
        
        # Create directory
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        
        # Load or create index
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing index hoặc tạo mới"""
        index_file = self.vector_store_path / "faiss_index.bin"
        data_file = self.vector_store_path / "documents.pkl"
        
        if index_file.exists() and data_file.exists():
            try:
                self.index = faiss.read_index(str(index_file))
                with open(data_file, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data['documents']
                    self.metadatas = data['metadatas']
                print(f"✅ Loaded {len(self.documents)} documents from vector store")
            except Exception as e:
                print(f"⚠️  Error loading index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """Tạo FAISS index mới"""
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # Cosine similarity
        self.documents = []
        self.metadatas = []
        print("✅ Created new FAISS index")
    
    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings cho texts"""
        embeddings = []
        
        for text in texts:
            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            embeddings.append(response['embedding'])
        
        embeddings = np.array(embeddings, dtype='float32')
        
        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-10)
        
        return embeddings
    
    def add_documents(self, texts: List[str], metadatas: List[Dict]) -> None:
        """Thêm documents vào shared knowledge base"""
        if not texts:
            return
        
        print(f"📥 Adding {len(texts)} chunks to knowledge base...")
        
        # Generate embeddings
        embeddings = self._embed_texts(texts)
        
        # Add to FAISS
        self.index.add(embeddings)
        
        # Store documents and metadata
        self.documents.extend(texts)
        self.metadatas.extend(metadatas)
        
        # Save immediately
        self.save()
        
        print(f"✅ Total documents in knowledge base: {len(self.documents)}")
    
    def search(self, query: str, k: int = 5) -> Dict:
        """Tìm kiếm relevant documents"""
        if len(self.documents) == 0:
            return {"documents": [], "metadatas": [], "distances": []}
        
        # Generate query embedding
        query_embedding = self._embed_texts([query])
        
        # Search
        k = min(k, len(self.documents))
        distances, indices = self.index.search(query_embedding, k)
        
        return {
            "documents": [self.documents[i] for i in indices[^0]],
            "metadatas": [self.metadatas[i] for i in indices[^0]],
            "distances": distances[^0].tolist()
        }
    
    def query_with_context(self, question: str, k: int = 5) -> Dict:
        """Trả lời question với RAG"""
        # Search for context
        search_results = self.search(question, k=k)
        
        context_str = ""
        if search_results["documents"]:
            context_str = "\n\n---\n\n".join(search_results["documents"])
        
        # Build prompt
        if context_str:
            prompt = f"""Dựa trên thông tin nội bộ của công ty sau đây, hãy trả lời câu hỏi một cách chính xác và chi tiết.

THÔNG TIN TỪ TÀI LIỆU:
{context_str}

CÂU HỎI: {question}

Trả lời bằng tiếng Việt, dựa trên thông tin được cung cấp."""
        else:
            prompt = question
        
        # Call LLM
        response = ollama.chat(
            model=self.llm_model,
            messages=[
                {
                    'role': 'system',
                    'content': 'Bạn là trợ lý AI của công ty, trả lời dựa trên tài liệu nội bộ. Trả lời bằng tiếng Việt.'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
        )
        
        return {
            "answer": response['message']['content'],
            "sources": search_results["documents"][:3],  # Top 3 sources
            "num_sources": len(search_results["documents"])
        }
    
    def save(self):
        """Lưu index xuống disk"""
        index_file = self.vector_store_path / "faiss_index.bin"
        data_file = self.vector_store_path / "documents.pkl"
        
        faiss.write_index(self.index, str(index_file))
        
        with open(data_file, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'metadatas': self.metadatas
            }, f)
        
        print(f"💾 Saved vector store")
    
    def get_stats(self) -> Dict:
        """Get knowledge base stats"""
        return {
            "total_documents": len(self.documents),
            "embedding_dimension": self.embedding_dim,
            "llm_model": self.llm_model,
            "embedding_model": self.embedding_model
        }


# Singleton instance
_rag_engine = None

def get_rag_engine() -> SharedRAGEngine:
    """Get shared RAG engine instance"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = SharedRAGEngine()
    return _rag_engine
```


### **Step 2.7: Document Processor**

Tạo `backend/app/document_processor.py`:

```python
"""
Document processor - giống như offline version
"""

import os
import fitz  # PyMuPDF
from docx import Document
from PIL import Image
import pytesseract
from typing import List, Dict

class DocumentProcessor:
    def __init__(self):
        self.chunk_size = 1000
        self.chunk_overlap = 200
        self.supported_formats = ['.pdf', '.docx', '.doc', '.txt', '.md']
    
    def process_file(self, file_path: str) -> Dict:
        """Process file và return chunks"""
        ext = os.path.splitext(file_path)[^1].lower()
        
        if ext == '.pdf':
            text = self._process_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            text = self._process_word(file_path)
        elif ext in ['.txt', '.md']:
            text = self._process_txt(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")
        
        chunks = self.chunk_text(text)
        
        return {
            "text": text,
            "chunks": chunks,
            "text_length": len(text),
            "num_chunks": len(chunks)
        }
    
    def _process_pdf(self, file_path: str) -> str:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    
    def _process_word(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    
    def _process_txt(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def chunk_text(self, text: str) -> List[str]:
        """Chia text thành chunks"""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence
            if end < len(text):
                for delim in ['. ', '.\n', '! ', '?\n']:
                    last_delim = text[start:end].rfind(delim)
                    if last_delim != -1:
                        end = start + last_delim + len(delim)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start += (self.chunk_size - self.chunk_overlap)
        
        return chunks
```


### **Step 2.8: API Endpoints (Main FastAPI)**

Tạo `backend/app/main.py`:

```python
"""
Main FastAPI application
"""

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
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
from app.document_processor import DocumentProcessor
from pydantic import BaseModel, EmailStr

# Initialize FastAPI
app = FastAPI(
    title="Company RAG Chat API",
    version="1.0.0",
    description="Private company knowledge base chat system"
)

# CORS - Allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("🚀 Company RAG Chat Server Started")


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
    k: int = 5

class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    num_sources: int


# ==================== AUTH ENDPOINTS ====================

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register new user"""
    # Check existing user
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Create user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        is_admin=False  # First user should be manually set as admin
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create token
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


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    user = db.query(User).filter(User.username == credentials.username).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    
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


@app.get("/api/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_admin": current_user.is_admin
    }


# ==================== DOCUMENT ENDPOINTS ====================

@app.post("/api/documents/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload documents to shared knowledge base"""
    rag_engine = get_rag_engine()
    doc_processor = DocumentProcessor()
    documents_path = Path("./data/documents")
    documents_path.mkdir(parents=True, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        # Save file
        file_path = documents_path / f"{current_user.id}_{file.filename}"
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process file
        try:
            result = doc_processor.process_file(str(file_path))
            
            # Add to knowledge base
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
            
            # Save to database
            db_document = DBDocument(
                filename=file.filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_size_mb=file_path.stat().st_size / (1024 * 1024),
                file_type=file_path.suffix,
                num_chunks=result["num_chunks"],
                uploaded_by=current_user.id,
                is_indexed=True
            )
            
            db.add(db_document)
            db.commit()
            
            uploaded_files.append({
                "filename": file.filename,
                "chunks": result["num_chunks"],
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
    """List all documents in knowledge base"""
    documents = db.query(DBDocument).all()
    
    return {
        "total": len(documents),
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "uploaded_by": doc.uploader.username if doc.uploader else "Unknown",
                "uploaded_at": doc.uploaded_at.isoformat(),
                "num_chunks": doc.num_chunks
            }
            for doc in documents
        ]
    }


# ==================== CHAT ENDPOINTS ====================

@app.post("/api/chat/query", response_model=ChatResponse)
async def chat_query(
    query: ChatQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Query shared knowledge base"""
    rag_engine = get_rag_engine()
    
    # Get answer from RAG
    result = rag_engine.query_with_context(query.question, k=query.k)
    
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
    """Get user's chat history"""
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


# ==================== ADMIN ENDPOINTS ====================

@app.get("/api/admin/stats")
async def get_stats(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get system statistics (admin only)"""
    rag_engine = get_rag_engine()
    
    total_users = db.query(User).count()
    total_documents = db.query(DBDocument).count()
    total_conversations = db.query(Conversation).count()
    
    rag_stats = rag_engine.get_stats()
    
    return {
        "users": total_users,
        "documents": total_documents,
        "conversations": total_conversations,
        **rag_stats
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Company RAG Chat"}
```


***

Phần này quá dài. Tôi sẽ tiếp tục với **Docker setup, Frontend, và deployment instructions** trong response tiếp theo.

Bạn có muốn tôi tiếp tục với:

1. Docker Compose configuration
2. PostgreSQL setup
3. Nginx reverse proxy
4. Frontend (React)
5. Deployment và testing instructions

Hay bạn muốn tôi tạo tất cả thành **một file documentation hoàn chỉnh** để download? 🚀
<span style="display:none">[^10][^11][^12][^13][^14][^15][^2][^3][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://kuberns.com/blogs/post/fastapi-deployment-guide/

[^2]: https://www.theserverside.com/blog/Coffee-Talk-Java-News-Stories-and-Opinions/Docker-Nginx-reverse-proxy-setup-example

[^3]: https://github.com/19mddil/JWT-MultiUser-Authentication-API

[^4]: https://render.com/articles/fastapi-production-deployment-best-practices

[^5]: https://phoenixnap.com/kb/docker-nginx-reverse-proxy

[^6]: https://workos.com/blog/how-to-handle-jwt-in-python

[^7]: https://dev.to/mrchike/fastapi-in-production-build-scale-deploy-series-b-services-queues-containers-2i08

[^8]: https://github.com/nginx-proxy/nginx-proxy

[^9]: https://stackoverflow.com/questions/63875328/jwt-architecture-for-multiple-users

[^10]: https://dev.to/mrchike/fastapi-in-production-build-scale-deploy-series-a-codebase-design-ao3

[^11]: https://stackoverflow.com/questions/71008651/use-nginx-as-reverse-proxy-for-a-docker-container

[^12]: https://python.plainenglish.io/building-a-custom-authentication-system-in-python-using-jwt-and-oauth2-f7a010d46fce

[^13]: https://fastapi.tiangolo.com/deployment/

[^14]: https://www.reddit.com/r/selfhosted/comments/1amm9wf/starting_to_use_nginx_as_a_reverse_proxy_for/

[^15]: https://auth0.com/blog/how-to-handle-jwt-in-python/

