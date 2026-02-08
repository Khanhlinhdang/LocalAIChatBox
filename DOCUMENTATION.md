# LocalAIChatBox v5.0 — Documentation

> **Nền tảng AI Chat & Research hoàn toàn offline, self-hosted, tích hợp Multimodal RAG, Knowledge Graph và Deep Research Engine.**

---

## Mục lục

1. [Giới thiệu tổng quan](#1-giới-thiệu-tổng-quan)
2. [Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
3. [Công nghệ sử dụng](#3-công-nghệ-sử-dụng)
4. [Tính năng chi tiết](#4-tính-năng-chi-tiết)
5. [Cấu trúc mã nguồn](#5-cấu-trúc-mã-nguồn)
6. [Hướng dẫn Deploy](#6-hướng-dẫn-deploy)
7. [Cấu hình nâng cao](#7-cấu-hình-nâng-cao)
8. [API Reference](#8-api-reference)
9. [Roadmap & Kế hoạch nâng cấp](#9-roadmap--kế-hoạch-nâng-cấp)

---

## 1. Giới thiệu tổng quan

**LocalAIChatBox** là nền tảng AI Chat doanh nghiệp chạy **100% offline** trên hạ tầng riêng. Hệ thống kết hợp:

- **Retrieval-Augmented Generation (RAG)** — truy vấn tài liệu nội bộ với ngữ cảnh chính xác
- **Knowledge Graph** — xây dựng đồ thị tri thức tự động từ tài liệu
- **Deep Research Engine** — nghiên cứu chuyên sâu với 6 chiến lược, đa nguồn tìm kiếm
- **Multimodal Processing** — xử lý PDF, DOCX, XLSX, PPTX, ảnh với vision model
- **Enterprise Security** — RBAC, LDAP/AD, mã hóa dữ liệu, GDPR compliance

### Điểm nổi bật

| Đặc điểm | Mô tả |
|-----------|--------|
| **100% Offline** | Toàn bộ LLM, embedding, search chạy trên server riêng |
| **Zero Cloud Dependency** | Không gửi dữ liệu ra bên ngoài, phù hợp doanh nghiệp nhạy cảm |
| **One-Command Deploy** | Deploy tự động hoàn toàn bằng `docker compose up -d` hoặc script `deploy_vps.py` |
| **Self-Contained Research** | Engine nghiên cứu tự chủ, không phụ thuộc thư viện bên ngoài |
| **Multi-tenant Ready** | Hỗ trợ nhiều tổ chức trên cùng hạ tầng |

---

## 2. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX (Port 81)                         │
│                      Reverse Proxy + SSE                        │
├────────────────────────┬────────────────────────────────────────┤
│     Frontend (React)   │          Backend (FastAPI)              │
│     Port 3000          │          Port 8000                      │
│                        │                                         │
│  • Chat UI             │  • REST API + SSE Streaming             │
│  • Document Manager    │  • RAG Engine (ChromaDB + Embeddings)   │
│  • Research Dashboard  │  • Knowledge Graph (NetworkX)           │
│  • Analytics Panel     │  • Deep Research Engine (6 strategies)  │
│  • Admin Console       │  • Multi-Engine Search (5 engines)      │
│  • Enterprise Settings │  • Security Middleware + Rate Limiter   │
│                        │  • Notification Service (Email/Webhook) │
│                        │  • Research Scheduler                   │
├────────────────────────┼────────────────────────────────────────┤
│                        │                                         │
│   ┌──────────┐  ┌──────┴───────┐  ┌──────────┐  ┌───────────┐  │
│   │PostgreSQL│  │   Ollama     │  │ SearXNG  │  │ ChromaDB  │  │
│   │  16      │  │ llama3.1     │  │ Meta     │  │ Vector    │  │
│   │          │  │ llava        │  │ Search   │  │ Store     │  │
│   └──────────┘  └──────────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Docker Services (8 containers)

| # | Service | Image | Chức năng |
|---|---------|-------|-----------|
| 1 | **postgres** | `postgres:16-alpine` | Cơ sở dữ liệu quan hệ (users, documents, research tasks, analytics) |
| 2 | **ollama** | `ollama/ollama:latest` | LLM runtime — chạy llama3.1 (text) + llava (vision) |
| 3 | **ollama-init** | `curlimages/curl:latest` | Auto-pull models khi khởi tạo lần đầu, sau đó exit |
| 4 | **data-init** | `alpine:latest` | Thiết lập quyền thư mục data, sau đó exit |
| 5 | **searxng** | `searxng/searxng:latest` | Meta search engine — tìm kiếm từ Google, Bing, DuckDuckGo |
| 6 | **backend** | Custom (Python 3.11) | FastAPI API server + RAG + KG + Research |
| 7 | **frontend** | Custom (Node 18 + Nginx) | React SPA |
| 8 | **nginx** | `nginx:alpine` | Reverse proxy, gộp FE + BE vào cùng port 81 |

### Luồng khởi động

```
postgres (healthy) ─┐
ollama (healthy) ───┤
                    ├─→ ollama-init (pull models) ──┐
data-init (exit 0) ─┤                               │
searxng (started) ──┤                               │
                    └───────────────────────────────┴──→ backend (healthy) ──→ frontend ──→ nginx
```

---

## 3. Công nghệ sử dụng

### 3.1 Backend Stack

| Thành phần | Công nghệ | Phiên bản | Vai trò |
|------------|-----------|-----------|---------|
| **Web Framework** | FastAPI | latest | REST API, SSE streaming, middleware |
| **ASGI Server** | Uvicorn | latest | Production server với WebSocket support |
| **ORM** | SQLAlchemy | latest | Database abstraction, migrations |
| **Database** | PostgreSQL | 16 | Lưu trữ quan hệ (users, sessions, tasks) |
| **Vector Store** | ChromaDB | latest | Vector embeddings cho RAG |
| **Embeddings** | sentence-transformers | latest | Model `all-MiniLM-L6-v2` (384 dims) |
| **LLM Runtime** | Ollama | latest | Chạy llama3.1 + llava locally |
| **LangChain** | langchain + langchain-ollama | latest | LLM orchestration, chain management |
| **Knowledge Graph** | NetworkX | latest | In-memory graph database |
| **Search** | SearXNG + custom engines | latest | Multi-source web search |
| **Auth** | python-jose + bcrypt | latest | JWT tokens, password hashing |
| **Doc Processing** | PyMuPDF, python-docx, openpyxl, python-pptx | latest | PDF, DOCX, XLSX, PPTX parsing |
| **Image Processing** | Pillow | latest | Image analysis with vision model |
| **PDF Export** | fpdf2 | latest | Generate PDF reports |
| **Enterprise Auth** | ldap3 | latest | LDAP/Active Directory integration |
| **Encryption** | cryptography (Fernet) | latest | AES encryption at rest |

### 3.2 Frontend Stack

| Thành phần | Công nghệ | Phiên bản | Vai trò |
|------------|-----------|-----------|---------|
| **Framework** | React | 18.2 | Component-based UI |
| **Routing** | react-router-dom | 6.22 | Client-side routing |
| **HTTP Client** | axios | 1.6.5 | API communication với interceptors |
| **Markdown** | react-markdown | 9.0.1 | Render markdown content |
| **File Upload** | react-dropzone | 14.2.3 | Drag & drop document upload |

### 3.3 Infrastructure

| Thành phần | Công nghệ | Vai trò |
|------------|-----------|---------|
| **Container** | Docker + Docker Compose | Orchestration, isolation |
| **Reverse Proxy** | Nginx | Routing, SSE buffering, body size limit |
| **Deployment** | Paramiko (SSH) | Automated VPS deployment |
| **Version Control** | Git + GitHub | Source management |

### 3.4 AI Models

| Model | Type | Kích thước | Vai trò |
|-------|------|-----------|---------|
| **llama3.1** | Text LLM | ~4.7 GB | Chat, reasoning, research, report generation |
| **llava** | Vision LLM | ~4.7 GB | Image understanding, multimodal analysis |
| **all-MiniLM-L6-v2** | Embedding | ~80 MB | Text vectorization cho RAG retrieval |

---

## 4. Tính năng chi tiết

### 4.1 💬 AI Chat với RAG

- **Hybrid Search**: kết hợp vector similarity + keyword search
- **Multi-turn Conversations**: hỗ trợ hội thoại nhiều lượt với context window
- **Chat Sessions**: quản lý nhiều phiên trò chuyện
- **Source Attribution**: trích dẫn nguồn tài liệu trong câu trả lời
- **Search Modes**: `hybrid`, `semantic`, `keyword`
- **Knowledge Graph Integration**: bổ sung thông tin từ đồ thị tri thức

### 4.2 📄 Document Management

- **Multi-format Support**: PDF, DOCX, XLSX, PPTX, TXT, Markdown, HTML, images
- **Drag & Drop Upload**: kéo thả file để upload
- **Automatic Chunking**: tự động chia nhỏ tài liệu thành chunks
- **Folder Organization**: tổ chức tài liệu theo thư mục
- **Tag System**: gắn nhãn để phân loại
- **Version Control**: lịch sử phiên bản tài liệu
- **Batch Processing**: xử lý hàng loạt tài liệu

### 4.3 🔬 Deep Research Engine (Phase 5 — Self-Contained)

Hoàn toàn tự chủ, không phụ thuộc thư viện bên ngoài.

**6 chiến lược nghiên cứu:**

| Chiến lược | Mô tả | Phù hợp cho |
|-----------|--------|-------------|
| **rapid** | Tìm kiếm nhanh, tổng hợp 1 lần | Câu hỏi đơn giản, cần trả lời nhanh |
| **iterative** | Phân tích → tìm → bổ sung → lặp lại | Câu hỏi phức tạp cần nhiều góc nhìn |
| **focused-iteration** | Tinh chỉnh thích ứng với confidence scoring | Chủ đề cần độ chính xác cao |
| **parallel** | Chạy song song nhiều truy vấn | Chủ đề rộng cần phủ nhanh |
| **source-based** | Theo dõi chi tiết nguồn trích dẫn | Nghiên cứu cần citation chính xác |
| **smart** | LLM tự chọn chiến lược phù hợp | Khi không chắc nên dùng chiến lược nào |

**Các thành phần:**
- `OllamaLLM` — giao tiếp trực tiếp với Ollama API
- `MetaSearchEngine` — phân loại domain, tìm kiếm song song, loại trùng, xếp hạng
- `CitationHandler` — quản lý trích dẫn, định dạng APA/numbered
- `ReportGenerator` — tạo báo cáo có mục lục, executive summary, bibliography

### 4.4 🔍 Multi-Engine Search (5 engines)

| Engine | Loại | Yêu cầu | Mô tả |
|--------|------|---------|--------|
| **SearXNG** | General | Có sẵn trong Docker | Meta search qua Google, Bing, DDG |
| **Wikipedia** | Knowledge | Không cần API key | MediaWiki API, truy cập trực tiếp |
| **arXiv** | Academic | Không cần API key | Bài báo khoa học, preprint |
| **DuckDuckGo** | General (fallback) | Không cần API key | Instant Answer API |
| **Brave** | General (premium) | Cần API key (tùy chọn) | Brave Search API |

**Tính năng MetaSearch:**
- **Domain Classification**: tự động phân loại query → chọn engine phù hợp (academic/knowledge/code/news/general)
- **Parallel Execution**: chạy song song trên nhiều engine
- **Deduplication**: loại bỏ kết quả trùng lặp bằng URL + title hash
- **Relevance Ranking**: xếp hạng kết quả theo điểm liên quan

### 4.5 📊 Knowledge Graph

- **Automatic Entity Extraction**: trích xuất thực thể từ tài liệu
- **Relationship Mapping**: xây dựng quan hệ giữa các thực thể
- **Multi-hop Traversal**: duyệt đồ thị nhiều bước
- **Visual Graph**: hiển thị đồ thị trực quan
- **Export**: GraphML, JSON, CSV
- **Rebuild**: xây dựng lại toàn bộ đồ thị

### 4.6 📈 Analytics & Token Tracking

- **Usage Overview**: tổng quan hoạt động (queries, documents, users, actions)
- **Daily Activity Chart**: biểu đồ hoạt động theo ngày
- **Top Users**: bảng xếp hạng người dùng hoạt động nhất
- **Popular Queries**: truy vấn phổ biến nhất
- **Action Breakdown**: phân tích theo loại hành động
- **Token Usage**: theo dõi token LLM theo user/model/action
- **Cost Estimation**: ước tính chi phí sử dụng

### 4.7 📥 Export Service

| Định dạng | Chat | Research | Knowledge Graph | Documents |
|-----------|------|----------|-----------------|-----------|
| **JSON** | ✅ | ✅ | ✅ | ✅ |
| **CSV** | ✅ | — | ✅ | ✅ |
| **Markdown** | ✅ | ✅ | — | — |
| **PDF** | — | ✅ | — | — |
| **DOCX** | — | ✅ | — | — |
| **GraphML** | — | — | ✅ | — |

### 4.8 🔒 Enterprise Security (Phase 4)

- **RBAC**: Role-Based Access Control với 5 role mặc định (admin, manager, editor, viewer, guest) + custom roles
- **LDAP/AD Integration**: xác thực qua Active Directory
- **Encryption at Rest**: mã hóa dữ liệu nhạy cảm bằng Fernet (AES-128-CBC)
- **GDPR Compliance**: export data cá nhân, xóa dữ liệu theo yêu cầu
- **Audit Logging**: ghi log mọi hành động
- **Multi-tenancy**: tách dữ liệu giữa các tổ chức
- **Document Permissions**: phân quyền truy cập tài liệu
- **Security Headers**: X-Frame-Options, CSP, HSTS, X-Content-Type-Options
- **Input Sanitization**: chống XSS, SQL injection
- **SSRF Protection**: chặn request đến internal IP ranges
- **Rate Limiting**: giới hạn request theo user/IP (sliding window)

### 4.9 🔔 Notification Service

- **Email (SMTP)**: gửi thông báo qua email với HTML template
- **Webhook**: gửi notification đến Discord, Slack, Telegram, etc.
- **Queue-based**: hàng đợi xử lý background với retry mechanism

### 4.10 ⏰ Research Scheduler

- **Recurring Tasks**: lập lịch nghiên cứu định kỳ (theo giờ)
- **CRUD API**: tạo, sửa, xóa, bật/tắt schedule
- **Auto-notification**: thông báo khi nghiên cứu hoàn thành

### 4.11 🖥️ Frontend Pages (10 pages)

| Trang | Route | Mô tả |
|-------|-------|--------|
| **Chat** | `/` | Giao diện chat AI chính với multi-turn, RAG |
| **Documents** | `/documents` | Upload, quản lý tài liệu, thư mục, tags |
| **Deep Research** | `/research` | Start research, SSE progress, export kết quả |
| **Knowledge Graph** | `/knowledge-graph` | Xem đồ thị tri thức, tìm kiếm entities |
| **Analytics** | `/analytics` | Dashboard phân tích, token usage |
| **Admin** | `/admin` | Quản lý users (admin only) |
| **Enterprise** | `/enterprise` | RBAC, tenants, LDAP, encryption (admin only) |
| **Settings** | `/settings` | Cấu hình LDR/research settings (admin only) |
| **Login** | `/login` | Đăng nhập |
| **Register** | `/register` | Đăng ký tài khoản |

---

## 5. Cấu trúc mã nguồn

```
LocalAIChatBox/
├── docker-compose.yml          # Orchestrate 8 services
├── deploy_vps.py               # Automated VPS deployment (SSH/Paramiko)
├── setup.sh                    # Initial setup script
│
├── backend/
│   ├── Dockerfile              # Multi-stage: builder → runtime (Python 3.11)
│   ├── requirements.txt        # 30+ Python packages
│   └── app/
│       ├── main.py             # FastAPI app, startup, all endpoints
│       ├── models.py           # SQLAlchemy models (15+ tables)
│       ├── database.py         # DB connection, migrations
│       ├── auth.py             # JWT authentication, password hashing
│       │
│       ├── # ── RAG & AI ──
│       ├── enhanced_rag_engine.py  # Multimodal RAG (text + image + KG)
│       ├── knowledge_graph.py      # NetworkX knowledge graph
│       ├── document_processor.py   # Document chunking & indexing
│       │
│       ├── # ── Deep Research (Phase 5) ──
│       ├── advanced_research.py    # 6 strategies + OllamaLLM + ReportGenerator
│       ├── deep_research.py        # Research service (background tasks)
│       ├── search_engines.py       # 5 search engines + MetaSearchEngine
│       ├── citation_handler.py     # Citation management
│       ├── research_routes.py      # Research API + SSE + scheduler + search
│       ├── research_scheduler.py   # Recurring research scheduler
│       │
│       ├── # ── Security & Enterprise (Phase 4) ──
│       ├── security_middleware.py  # Headers, sanitization, SSRF, validation
│       ├── rate_limiter.py         # Per-user/IP rate limiting
│       ├── rbac.py                 # Role-Based Access Control
│       ├── ldap_auth.py            # LDAP/Active Directory auth
│       ├── encryption.py           # Fernet encryption at rest
│       ├── compliance.py           # GDPR, audit logging
│       ├── enterprise_routes.py    # Enterprise API endpoints
│       │
│       ├── # ── Analytics & Export ──
│       ├── analytics.py            # Usage analytics
│       ├── token_tracker.py        # LLM token counting & cost tracking
│       ├── export_service.py       # JSON/CSV/MD/PDF/DOCX export
│       ├── notification_service.py # Email + webhook notifications
│       │
│       ├── # ── Settings ──
│       ├── ldr_settings.py         # Research settings management
│       │
│       └── multimodal/             # Multimodal document processing
│           ├── config.py
│           ├── document_parser.py
│           ├── modal_processors.py
│           ├── prompts.py
│           ├── query_engine.py
│           └── utils.py
│
├── frontend/
│   ├── Dockerfile              # Multi-stage: node build → nginx serve
│   ├── nginx.conf              # Frontend nginx config
│   ├── package.json            # React 18 + dependencies
│   └── src/
│       ├── App.jsx             # Main app with routing
│       ├── App.css             # Global styles (dark theme)
│       ├── api.js              # 80+ API functions
│       ├── components/
│       │   └── Navbar.jsx
│       └── pages/
│           ├── ChatPage.jsx
│           ├── DocumentsPage.jsx
│           ├── DeepResearchPage.jsx
│           ├── KnowledgeGraphPage.jsx
│           ├── AnalyticsPage.jsx
│           ├── AdminPage.jsx
│           ├── EnterprisePage.jsx
│           ├── SettingsPage.jsx
│           ├── LoginPage.jsx
│           └── RegisterPage.jsx
│
├── nginx/
│   └── nginx.conf              # Main reverse proxy config
│
├── searxng/
│   └── settings.yml            # SearXNG configuration
│
├── data/                       # Persistent data (mounted volumes)
│   ├── database/
│   ├── documents/
│   ├── parser_output/
│   └── vector_store/
│
└── scripts/
    ├── backend-entrypoint.sh
    └── init-ollama.sh
```

---

## 6. Hướng dẫn Deploy

### 6.1 Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị |
|------------|-----------|-------------|
| **CPU** | 4 cores | 8+ cores |
| **RAM** | 8 GB | 16+ GB |
| **Disk** | 30 GB free | 50+ GB SSD |
| **OS** | Ubuntu 20.04+ / Debian 11+ | Ubuntu 22.04 LTS |
| **Docker** | 24.0+ | Latest |
| **Docker Compose** | v2.20+ | Latest |

> ⚠️ **GPU (tùy chọn)**: Nếu có GPU NVIDIA, uncomment phần `deploy.resources.reservations.devices` trong `docker-compose.yml` để tăng tốc Ollama.

### 6.2 Deploy nhanh (Local)

```bash
# 1. Clone repository
git clone https://github.com/Khanhlinhdang/LocalAIChatBox.git
cd LocalAIChatBox

# 2. Tạo thư mục data
mkdir -p data/{vector_store,documents,parser_output}
chmod -R 777 data/

# 3. (Tùy chọn) Tạo file .env cho backend
cat > backend/.env << 'EOF'
# Để trống nếu không cần
ENCRYPTION_KEY=
LDAP_ENABLED=false
EOF

# 4. Build và khởi chạy
docker compose up -d

# 5. Theo dõi khởi tạo (đợi models được pull)
docker compose logs -f ollama-init

# 6. Kiểm tra trạng thái
docker compose ps

# 7. Truy cập
# → http://localhost:81
# → Login: admin / admin123
```

### 6.3 Deploy lên VPS (Automated)

```bash
# Chỉnh sửa deploy_vps.py với thông tin VPS
# HOST = 'your-vps-ip'
# USER = 'root'
# PASSWORD = 'your-password'

python deploy_vps.py
```

**Script tự động thực hiện:**
1. SSH vào VPS
2. `git pull` code mới nhất
3. Tạo thư mục data + set permissions
4. `docker compose down` (dừng containers cũ)
5. `docker compose build backend frontend` (build images)
6. `docker compose up -d` (khởi chạy)
7. Monitor startup (tối đa 15 phút, kiểm tra mỗi 10s)
8. Health check qua `/api/health`
9. Hiển thị logs + container status

### 6.4 Deploy với GPU

Uncomment phần sau trong `docker-compose.yml`:

```yaml
ollama:
  # ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

Yêu cầu: NVIDIA GPU + nvidia-docker2 toolkit.

### 6.5 Kiểm tra sau deploy

```bash
# Health check
curl http://localhost:81/api/health

# Kết quả mong đợi:
{
  "status": "healthy",
  "service": "LocalAIChatBox",
  "version": "3.0 - Multimodal RAG",
  "services": {
    "database": "ok",
    "ollama": {"status": "ok", "models": ["llava:latest", "llama3.1:latest"]},
    "rag_engine": {"status": "ok", "text_chunks": 152},
    "knowledge_graph": {"status": "ok", "nodes": 207, "edges": 146}
  }
}
```

---

## 7. Cấu hình nâng cao

### 7.1 Biến môi trường

#### Core

| Biến | Mặc định | Mô tả |
|------|---------|--------|
| `DATABASE_URL` | `postgresql://raguser:ragpassword@postgres:5432/ragdb` | PostgreSQL connection string |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama API endpoint |
| `OLLAMA_LLM_MODEL` | `llama3.1` | Model LLM chính |
| `OLLAMA_VISION_MODEL` | `llava` | Model xử lý ảnh |
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG endpoint |

#### Enterprise (Phase 4)

| Biến | Mặc định | Mô tả |
|------|---------|--------|
| `ENCRYPTION_KEY` | *(trống)* | Fernet key cho encryption at rest |
| `LDAP_ENABLED` | `false` | Bật/tắt LDAP authentication |
| `LDAP_SERVER` | `ldap://localhost:389` | LDAP server URL |
| `LDAP_BASE_DN` | `dc=example,dc=com` | Base Distinguished Name |
| `LDAP_USER_SEARCH_FILTER` | `(sAMAccountName={username})` | LDAP search filter |

#### Advanced Research (Phase 5)

| Biến | Mặc định | Mô tả |
|------|---------|--------|
| `BRAVE_SEARCH_API_KEY` | *(trống)* | Brave Search API key (tùy chọn) |
| `SMTP_ENABLED` | `false` | Bật email notifications |
| `SMTP_HOST` | *(trống)* | SMTP server host |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | *(trống)* | SMTP username |
| `SMTP_PASSWORD` | *(trống)* | SMTP password |
| `SMTP_FROM` | `noreply@localchatbox.local` | Email sender |
| `WEBHOOK_ENABLED` | `false` | Bật webhook notifications |
| `WEBHOOK_URL` | *(trống)* | Webhook endpoint URL |
| `WEBHOOK_SECRET` | *(trống)* | Webhook signing secret |

### 7.2 Thay đổi LLM Model

Chỉnh `OLLAMA_MODELS` trong `docker-compose.yml` và `OLLAMA_LLM_MODEL`:

```yaml
ollama-init:
  environment:
    - OLLAMA_MODELS=mistral llava  # Thay llama3.1 bằng mistral

backend:
  environment:
    - OLLAMA_LLM_MODEL=mistral
```

### 7.3 Cấu hình SearXNG

Chỉnh file `searxng/settings.yml` để bật/tắt search engines cụ thể.

---

## 8. API Reference

### Authentication

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/auth/register` | Đăng ký user mới |
| POST | `/api/auth/login` | Đăng nhập, trả về JWT token |
| GET | `/api/auth/me` | Lấy thông tin user hiện tại |
| PUT | `/api/auth/password` | Đổi mật khẩu |

### Chat

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/chat/query` | Gửi câu hỏi (single turn) |
| POST | `/api/chat/query-multiturn` | Gửi câu hỏi (multi-turn với session) |
| GET | `/api/chat/history` | Lịch sử chat |
| POST | `/api/chat/sessions` | Tạo chat session mới |
| GET | `/api/chat/sessions` | Danh sách sessions |

### Documents

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/documents/upload` | Upload tài liệu (multipart) |
| GET | `/api/documents/list` | Danh sách tài liệu |
| DELETE | `/api/documents/{id}` | Xóa tài liệu |
| PUT | `/api/documents/{id}/move` | Di chuyển vào thư mục |
| PUT | `/api/documents/{id}/tags` | Gắn tags |

### Deep Research

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/research/start` | Bắt đầu nghiên cứu |
| GET | `/api/research/{id}/progress` | Tiến độ (polling) |
| GET | `/api/research/{id}/stream` | Tiến độ (SSE real-time) |
| GET | `/api/research/{id}/result` | Kết quả nghiên cứu |
| POST | `/api/research/{id}/report` | Tạo báo cáo chi tiết |
| GET | `/api/research/{id}/export?format=pdf` | Export (md/json/pdf/docx) |
| GET | `/api/research/strategies` | Danh sách chiến lược |
| GET | `/api/research/history` | Lịch sử nghiên cứu |

### Research Scheduler

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| POST | `/api/research/schedules` | Tạo lịch nghiên cứu |
| GET | `/api/research/schedules` | Danh sách schedules |
| PUT | `/api/research/schedules/{id}` | Cập nhật schedule |
| DELETE | `/api/research/schedules/{id}` | Xóa schedule |

### Search & Token

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/search/engines` | Danh sách search engines |
| POST | `/api/search/test` | Test search query |
| GET | `/api/tokens/stats` | Token usage stats (user) |
| GET | `/api/tokens/stats/all` | Token usage stats (admin) |

### Knowledge Graph

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/knowledge-graph/stats` | Thống kê KG |
| GET | `/api/knowledge-graph/entities` | Danh sách entities |
| GET | `/api/knowledge-graph/search?q=` | Tìm entity |
| GET | `/api/knowledge-graph/full` | Toàn bộ graph (JSON) |
| POST | `/api/knowledge-graph/rebuild` | Xây lại KG |

### Enterprise

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/enterprise/dashboard` | Enterprise overview |
| POST | `/api/enterprise/roles` | Tạo role |
| POST | `/api/enterprise/roles/assign` | Gán role cho user |
| GET | `/api/enterprise/tenants` | Danh sách tenants |
| POST | `/api/enterprise/gdpr/export` | Export dữ liệu cá nhân |
| POST | `/api/enterprise/gdpr/delete` | Xóa dữ liệu (GDPR) |

### Health & Admin

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| GET | `/api/health` | System health check |
| GET | `/api/admin/stats` | Admin statistics |
| GET | `/api/admin/users` | Danh sách users |

---

## 9. Roadmap & Kế hoạch nâng cấp

### Phase 6: Performance & Scalability (Q2 2026)

| Hạng mục | Mô tả | Ưu tiên |
|----------|--------|---------|
| **FAISS Vector Store** | Thay ChromaDB bằng FAISS cho tốc độ retrieval nhanh hơn 10-50x với datasets lớn | 🔴 Cao |
| **Redis Caching Layer** | Cache embeddings, search results, LLM responses để giảm latency | 🔴 Cao |
| **Async Ollama Client** | Chuyển từ `requests` sang `httpx.AsyncClient` cho non-blocking LLM calls | 🔴 Cao |
| **Connection Pooling** | SQLAlchemy connection pool tuning, pgBouncer cho PostgreSQL | 🟡 Trung bình |
| **Response Streaming** | Stream chat responses token-by-token (SSE) thay vì đợi toàn bộ | 🔴 Cao |
| **Embedding Cache** | Cache embeddings đã tính, tránh re-compute khi restart | 🟡 Trung bình |
| **Batch Embedding** | Batch multiple documents trong 1 embedding call | 🟡 Trung bình |

### Phase 7: Advanced AI (Q3 2026)

| Hạng mục | Mô tả | Ưu tiên |
|----------|--------|---------|
| **Multi-Model Support** | Hỗ trợ chọn model per-request (Mistral, Phi-3, CodeLlama, Gemma 2) | 🔴 Cao |
| **Agentic RAG** | Agent tự quyết định cần query documents, search web, hay trả lời trực tiếp | 🔴 Cao |
| **Hybrid Retrieval v2** | BM25 + Dense Retrieval + Cross-Encoder Re-ranking | 🔴 Cao |
| **Contextual Chunking** | Chunk tài liệu theo semantic boundaries thay vì fixed-size | 🟡 Trung bình |
| **Query Decomposition** | Tự động chia câu hỏi phức tạp thành sub-queries | 🟡 Trung bình |
| **Multi-modal RAG v2** | OCR tables, charts, diagrams → structured data | 🟡 Trung bình |
| **Conversation Memory** | Long-term memory với summary compression | 🟡 Trung bình |
| **Fine-tuning Pipeline** | LoRA fine-tuning trên dữ liệu nội bộ | 🟢 Thấp |

### Phase 8: Production Hardening (Q3 2026)

| Hạng mục | Mô tả | Ưu tiên |
|----------|--------|---------|
| **Health Dashboard** | Real-time monitoring: GPU/CPU/RAM usage, request latency, queue depth | 🔴 Cao |
| **Structured Logging** | JSON logs → ELK Stack hoặc Loki/Grafana | 🔴 Cao |
| **Database Migrations** | Alembic auto-migration thay vì manual `_safe_add_column` | 🔴 Cao |
| **Unit & Integration Tests** | pytest cho backend, Jest cho frontend, CI/CD pipeline | 🔴 Cao |
| **Rate Limiting v2** | Redis-backed distributed rate limiter (hiện tại in-memory) | 🟡 Trung bình |
| **Backup & Restore** | Automated PostgreSQL backup + vector store snapshot | 🔴 Cao |
| **SSL/TLS** | Let's Encrypt auto-renewal, HTTPS enforce | 🔴 Cao |
| **Horizontal Scaling** | Multiple backend workers, load balancer | 🟡 Trung bình |

### Phase 9: UX & Frontend (Q4 2026)

| Hạng mục | Mô tả | Ưu tiên |
|----------|--------|---------|
| **Real-time Chat Streaming** | Token-by-token response rendering | 🔴 Cao |
| **Markdown Rendering v2** | Code highlighting, LaTeX math, mermaid diagrams | 🔴 Cao |
| **Dark/Light Theme Toggle** | User preference cho theme | 🟡 Trung bình |
| **Mobile Responsive** | Responsive design cho tablet/mobile | 🔴 Cao |
| **PWA Support** | Progressive Web App cho offline access | 🟡 Trung bình |
| **File Preview** | Preview PDF, images, DOCX inline trong app | 🟡 Trung bình |
| **Research Visualization** | Timeline, mind map hiển thị research process | 🟢 Thấp |
| **i18n (Đa ngôn ngữ)** | Vietnamese, English, Japanese, Chinese | 🟡 Trung bình |
| **Keyboard Shortcuts** | Power user shortcuts (Ctrl+K search, etc.) | 🟢 Thấp |

### Phase 10: Integration & Ecosystem (Q1 2027)

| Hạng mục | Mô tả | Ưu tiên |
|----------|--------|---------|
| **Plugin System** | Extensible plugin architecture cho custom search engines, processors | 🟡 Trung bình |
| **API Gateway** | External API access with API keys, usage quotas | 🔴 Cao |
| **Webhook Integration v2** | Bi-directional webhooks, custom event triggers | 🟡 Trung bình |
| **Slack/Teams Bot** | Chat trực tiếp từ Slack hoặc Microsoft Teams | 🟡 Trung bình |
| **Mobile App** | React Native app cho iOS/Android | 🟢 Thấp |
| **CLI Tool** | Command-line interface cho research và document management | 🟢 Thấp |
| **Cloud LLM Fallback** | Optional fallback đến OpenAI/Claude khi cần model lớn hơn | 🟡 Trung bình |
| **S3/MinIO Storage** | Object storage cho documents thay vì filesystem | 🟡 Trung bình |

### Tổng kết Roadmap

```
2026-Q2  ┃ Phase 6: Performance & Scalability
         ┃  → FAISS, Redis, Async, Streaming
         ┃
2026-Q3  ┃ Phase 7: Advanced AI
         ┃  → Multi-model, Agentic RAG, Hybrid Retrieval v2
         ┃
         ┃ Phase 8: Production Hardening  
         ┃  → Monitoring, Testing, Backups, SSL
         ┃
2026-Q4  ┃ Phase 9: UX & Frontend
         ┃  → Streaming UI, Mobile, i18n
         ┃
2027-Q1  ┃ Phase 10: Integration & Ecosystem
         ┃  → Plugin system, API Gateway, Slack/Teams bot
```

---

## Phụ lục

### A. Lịch sử phát triển

| Phase | Nội dung | Files | Insertions |
|-------|----------|-------|------------|
| **Phase 1-2** | Core RAG Chat, Document Management | ~15 files | ~3,000 |
| **Phase 3** | Knowledge Graph, Multimodal RAG, Analytics | ~12 files | ~4,000 |
| **Phase 4** | Enterprise (RBAC, LDAP, Encryption, GDPR, Multi-tenant) | ~15 files | ~3,174 |
| **Phase 5** | Self-contained Research Engine, Multi-Engine Search, Security | ~21 files | ~4,188 |
| **Tổng** | **v5.0 — Advanced Research Edition** | **~40 files** | **~14,000+** |

### B. Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| **App** | `admin` | `admin123` |
| **PostgreSQL** | `raguser` | `ragpassword` |

> ⚠️ **Bảo mật**: Hãy đổi mật khẩu mặc định trước khi deploy production!

### C. Ports

| Port | Service |
|------|---------|
| 81 | Nginx (entry point) |
| 8001 | Backend (direct) |
| 3000 | Frontend (direct) |
| 5432 | PostgreSQL |
| 11434 | Ollama |
| 8080 | SearXNG |

---

