# LocalAIChatBox - Hệ Thống RAG Chat & Deep Research

<div align="center">

**Hệ thống trí tuệ nhân tạo hoàn toàn offline cho mạng nội bộ công ty**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-green?logo=python)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-18-61dafb?logo=react)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688?logo=fastapi)](https://fastapi.tiangolo.com/)

[Tính năng](#-tính-năng) • [Cài đặt](#-hướng-dẫn-cài-đặt) • [Sử dụng](#-hướng-dẫn-sử-dụng) • [API](#-api-endpoints) • [Cấu hình](#-cấu-hình-nâng-cao)

</div>

---

## 🎯 Giới thiệu

**LocalAIChatBox v6.0** là một hệ thống trí tuệ nhân tạo đa phương tiện (multimodal) được thiết kế để chạy **100% offline** trên mạng nội bộ công ty. Hệ thống kết hợp:

- **Multimodal RAG** - Xử lý văn bản, hình ảnh, bảng biểu, slides (PDF, DOCX, XLSX, PPTX, images)
- **LightRAG Integration** - Query với 5 modes (naive, local, global, hybrid, mix)
- **Knowledge Graph** - Trích xuất và quản lý quan hệ thực thể tự động với ChromaDB
- **Deep Research** - Nghiên cứu sâu với 7 chiến lược tìm kiếm thông minh
- **Enterprise Features** - RBAC, LDAP/AD, Multi-tenancy, Encryption, Compliance
- **Advanced Analytics** - Theo dõi usage, export reports, audit logs

### Đặc điểm nổi bật

✅ **Hoàn toàn Offline** - Không cần kết nối Internet sau khi cài đặt
✅ **Bảo mật Enterprise** - RBAC, encryption at rest, LDAP integration, audit logging
✅ **Đa phương tiện** - Xử lý text, images, tables, presentations với vision models
✅ **LightRAG Powered** - Fast hybrid search với knowledge graph
✅ **Dễ triển khai** - Docker Compose với auto-init, health checks
✅ **Mã nguồn mở** - Tùy chỉnh theo nhu cầu doanh nghiệp
✅ **Giao diện hiện đại** - Dark mode, responsive, real-time progress tracking

---

## 🏗️ Kiến trúc hệ thống

```
Mạng nội bộ công ty (LAN)
├── Nginx (Port 81)              - Reverse proxy với security headers
├── React Frontend (Port 3000)   - Giao diện web (13 pages)
├── FastAPI Backend (Port 8001)  - API server (Enhanced RAG + LightRAG)
├── PostgreSQL (Port 5432)       - Cơ sở dữ liệu (RBAC, tenants, audit logs)
├── Ollama (Port 11434)          - LLM Runtime (llama3.1, llama3.2:3b, llava, nomic-embed-text)
├── Ollama-Init                  - Auto-pull models on startup (exits after complete)
├── Data-Init                    - Fix permissions for mounted volumes (exits after complete)
├── SearXNG (Port 8080)          - Meta search engine
├── ChromaDB Vector Store        - Vector embeddings (text + multimodal chunks)
├── LightRAG Storage             - Knowledge graph + embeddings
└── Multimodal Processing        - Images, tables, presentations via vision models
```

**8 services** chạy trong Docker containers (6 persistent + 2 init containers), giao tiếp qua mạng Docker internal với health checks và dependencies.

---

## ✨ Tính năng

### 1. Xác thực đa người dùng & Enterprise Auth
- Đăng ký / Đăng nhập (Local + LDAP/AD)
- JWT authentication với token expiry
- RBAC (Role-Based Access Control) - Roles và permissions
- Multi-tenancy support - Phân tách dữ liệu theo tenant
- Audit logging - Theo dõi tất cả hành động

### 2. Multimodal Document Management
- **Upload hỗ trợ**: PDF, DOCX, TXT, MD, XLSX, PPTX, hình ảnh (PNG, JPG)
- **Multimodal processing**:
  - Trích xuất text với pymupdf, python-docx, openpyxl, python-pptx
  - Phân tích hình ảnh với vision model (llava)
  - Phát hiện tables, equations, charts tự động
- **Document versioning** - Lưu trữ phiên bản
- **Folders & Tags** - Tổ chức tài liệu
- **Per-document permissions** - Phân quyền chi tiết (read/write/manage)
- Index vào ChromaDB (text chunks + multimodal chunks)
- Trích xuất entities vào Knowledge Graph

### 3. Enhanced RAG Chat
- **Hybrid query modes**:
  - `naive`: Simple vector search
  - `local`: Vector + local KG context
  - `global`: Vector + full KG context
  - `hybrid`: Combined vector + KG (recommended)
- **Multimodal context**: Tự động sử dụng nội dung images/tables khi trả lời
- **Vision-enhanced answers**: LLM có thể "nhìn" vào hình ảnh để trả lời
- Trích dẫn nguồn tự động (document + page)
- Lịch sử chat theo sessions (Conversation + ChatSession models)
- Token tracking & rate limiting

### 4. LightRAG Integration
- **5 query modes**:
  - `naive`: Không dùng graph
  - `local`: Local graph context
  - `global`: Tòan cục graph context
  - `hybrid`: Kết hợp local + global
  - `mix`: Mix mode của LightRAG
- **Streaming support**: Real-time response streaming (NDJSON)
- **Batch indexing**: Xử lý nhiều documents cùng lúc
- **Graph exploration**: Xem entities, relationships, subgraphs
- **Entity/Relation editing**: Chỉnh sửa manual entities và relations
- **Context-only mode**: Lấy context không generate answer

### 5. Knowledge Graph (NetworkX + LightRAG)
- **Dual KG system**:
  - NetworkX KG: Traditional entity extraction (7 types: PERSON, ORG, PROJECT, TECH, PRODUCT, LOCATION, CONCEPT)
  - LightRAG KG: Advanced graph with embeddings
- **Multi-hop reasoning**: Tìm kiếm nhiều bước qua graph
- **Multimodal entities**: Entities có thể link đến images/tables
- **KG Explorer UI**: Search, filter, subgraph viewer
- **Rebuild support**: Xử lý lại tất cả documents (admin only)

### 6. Deep Research System
- **7 chiến lược nghiên cứu**:
  - `source-based`: Theo dõi nguồn chi tiết (mặc định)
  - `rapid`: Tốc độ cao, single-pass
  - `parallel`: Tìm kiếm đồng thời đa query
  - `standard`: Cân bằng giữa tốc độ và độ sâu
  - `iterative`: Lặp liên tục, tích lũy kiến thức
  - `focused-iteration`: Tinh chỉnh thích ứng
  - `smart`: Tự động chọn chiến lược tốt nhất
- **Progress tracking**: Real-time progress UI
- **Scheduled research**: Lập lịch chạy tự động
- **Notifications**: Email/webhook khi research xong
- **Report generation**: Tạo báo cáo markdown chi tiết
- **Research history**: Lưu trữ và xem lại

### 7. Analytics & Export
- **Usage Analytics Dashboard**:
  - Tổng quan tài nguyên (users, docs, queries, research)
  - Daily activity charts
  - Top users by action count
  - Popular queries
  - Document statistics
  - Action breakdown
- **Export features**:
  - Export chat history (JSON/CSV)
  - Export research reports (Markdown/PDF)
  - Export knowledge graph (JSON/GraphML)
  - Export documents list (CSV)

### 8. Admin Dashboard
- Quản lý người dùng (thêm/xóa/sửa, assign roles)
- Quản lý tenants (multi-tenancy)
- Thống kê hệ thống chi tiết
- Rebuild Knowledge Graphs (NetworkX + LightRAG)
- Cấu hình LDR settings (LLM, Search, Embedding)
- View audit logs & compliance reports
- Security settings (rate limits, token tracking)

### 9. Enterprise Features
- **LDAP/Active Directory**: SSO integration
- **Encryption at rest**: Sensitive data encryption
- **Compliance**: GDPR/HIPAA reports, data retention policies
- **Rate limiting**: Per-user/per-endpoint
- **Security middleware**: Headers, request validation, CORS
- **Webhook integration**: External system notifications

---

## 📦 Hướng dẫn cài đặt

### Yêu cầu hệ thống

| Thành phần | Tối thiểu | Khuyến nghị |
|------------|-----------|-------------|
| **RAM** | 16GB | 32GB |
| **Disk** | 50GB free | 100GB+ SSD |
| **CPU** | 4 cores | 8+ cores |
| **GPU** | Không bắt buộc | NVIDIA GPU (tăng tốc LLM) |

### A. Cài đặt trên Ubuntu/Debian Server (Khuyến nghị)

**Dành cho môi trường production, chạy 24/7**

#### 1. Cài đặt tự động (1 lệnh)

Trên Ubuntu 22.04+ hoặc Debian 12+ server mới:

```bash
git clone https://github.com/your-username/LocalAIChatBox.git
cd LocalAIChatBox
chmod +x setup.sh && ./setup.sh
```

Script này sẽ tự động:
1. Cài đặt Docker, Docker Compose, Git
2. Tạo thư mục `data/`, `searxng/`
3. Tạo SECRET_KEY ngẫu nhiên
4. Build và start 8 Docker services (6 persistent + 2 init containers)
5. Auto-pull LLM models (llama3.1, llama3.2:3b, llava, nomic-embed-text) vào Ollama
6. Kiểm tra health của tất cả services

**Thời gian**: ~20-40 phút (tùy tốc độ mạng khi download models ~10GB tổng)

#### 2. Sau khi cài đặt

Truy cập hệ thống tại: `http://<server-ip>:81`

Đăng nhập admin mặc định:
- Username: `admin`
- Password: `admin123`

**⚠️ Quan trọng**: Đổi mật khẩu admin ngay sau khi đăng nhập lần đầu!

#### 3. Tìm IP của server

```bash
hostname -I
```

Ví dụ: `192.168.1.100`

Các máy trong cùng mạng LAN truy cập: `http://192.168.1.100:81`

---

### B. Cài đặt trên Windows 10/11 (Development hoặc Single User)

**✅ CÓ THỂ chạy trên Windows 10/11!** Sử dụng Docker Desktop + WSL2.

#### Bước 1: Cài đặt Docker Desktop

1. Tải Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Cài đặt và khởi động Docker Desktop
3. Kích hoạt WSL2 (Windows Subsystem for Linux 2):
   - Mở PowerShell với quyền Admin:
   ```powershell
   wsl --install
   ```
   - Restart máy tính
   - Mở Docker Desktop → Settings → General → Bật "Use the WSL 2 based engine"

#### Bước 2: Clone project

Mở **PowerShell** hoặc **Command Prompt**:

```powershell
git clone https://github.com/Khanhlinhdang/LocalAIChatBox.git
cd LocalAIChatBox
```

#### Bước 3: Tạo file .env

Tạo file `backend\.env` với nội dung:

```env
# Core
SECRET_KEY=your-secret-key-here-change-this-to-random-string
DATABASE_URL=postgresql://raguser:ragpassword@postgres:5432/ragdb

# Ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_LLM_MODEL=llama3.1
OLLAMA_VISION_MODEL=llava
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Embeddings
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Storage
VECTOR_STORE_PATH=/app/data/vector_store
DOCUMENTS_PATH=/app/data/documents
PARSER_OUTPUT_DIR=/app/data/parser_output
MAX_FILE_SIZE_MB=100

# Auth
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Search
SEARXNG_URL=http://searxng:8080
LDR_SEARCH_TOOL=searxng
LDR_SEARCH_ITERATIONS=3
LDR_QUESTIONS_PER_ITERATION=3
LDR_SEARCH_MAX_RESULTS=50

# LightRAG
LIGHTRAG_LLM_MODEL=llama3.2:3b
LIGHTRAG_WORKING_DIR=/app/data/lightrag_storage
LIGHTRAG_EMBED_MODEL=nomic-embed-text:latest
LIGHTRAG_CHUNK_SIZE=800
LIGHTRAG_CHUNK_OVERLAP=100
LIGHTRAG_LANGUAGE=Vietnamese
LIGHTRAG_NUM_CTX=2048

# Enterprise (Optional)
ENCRYPTION_KEY=
LDAP_ENABLED=false
LDAP_SERVER=ldap://localhost:389
LDAP_BASE_DN=dc=example,dc=com

# Notifications (Optional)
SMTP_ENABLED=false
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
WEBHOOK_ENABLED=false
WEBHOOK_URL=
```

**Tạo SECRET_KEY ngẫu nhiên** (PowerShell):
```powershell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})
```
```

Copy kết quả vào `SECRET_KEY=...`

#### Bước 4: Tạo thư mục SearXNG config

```powershell
mkdir searxng
```

Tạo file `searxng\settings.yml`:

```yaml
use_default_settings: true
general:
  instance_name: "LocalAIChatBox Search"
server:
  bind_address: "0.0.0.0:8080"
  limiter: false
  image_proxy: false
search:
  safe_search: 0
  autocomplete: ""
  default_lang: "vi"
ui:
  default_locale: "vi"
  theme_args:
    simple_style: dark
```

#### Bước 5: Build và start

```powershell
docker-compose up -d --build
```

**Lần đầu tiên sẽ mất ~20-40 phút** để:
- Build images (~10 phút)
- Download LLM model llama3.1 (~4.7GB) vào container ollama

#### Bước 6: Kiểm tra auto-pull models

```powershell
docker logs ragchat-ollama-init
```

Container `ollama-init` sẽ tự động pull các models: llama3.1, llama3.2:3b, llava, nomic-embed-text. 
Đợi hoàn thành (tổng ~10GB). Container này sẽ exit khi xong.

Nếu cần pull thêm models:
```powershell
docker exec -it ragchat-ollama ollama pull <model-name>
```

#### Bước 7: Kiểm tra services

```powershell
docker-compose ps
```

- `ollama-init` và `data-init` sẽ có status `Exited (0)` (đã hoàn thành)
- Các services còn lại phải có status `Up` hoặc `healthy`

#### Bước 8: Truy cập

Mở trình duyệt:
- **Trên máy Windows hiện tại**: http://localhost:81
- **Từ máy khác trong mạng LAN**: http://<IP-của-máy-Windows>:81

**Tìm IP của máy Windows**:
```powershell
ipconfig
```

Tìm dòng `IPv4 Address` của adapter mạng đang dùng (VD: `192.168.1.50`)

---

### C. Cài đặt thủ công (Manual setup)

Nếu bạn muốn kiểm soát từng bước:

#### 1. Cài đặt dependencies

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install -y docker.io docker-compose git
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

**Windows**: Cài Docker Desktop như hướng dẫn ở phần B.

#### 2. Clone repo

```bash
git clone https://github.com/your-username/LocalAIChatBox.git
cd LocalAIChatBox
```

#### 3. Tạo file config

- Tạo `backend/.env` (xem template ở phần B bước 3)
- Tạo `searxng/settings.yml` (xem template ở phần B bước 4)

#### 4. Build và start

```bash
docker-compose up -d --build
```

#### 5. Download LLM model

```bash
docker exec -it ragchat-ollama ollama pull llama3.1
```

#### 6. Kiểm tra

```bash
docker-compose ps
curl http://localhost/api/health
```

---

## 🚀 Hướng dẫn sử dụng

### 1. Đăng nhập

Truy cập `http://<server-ip>:81` → Đăng nhập với `admin` / `admin123`

### 2. Upload tài liệu (Multimodal)

**Documents** page → **Upload Documents** → Chọn file

**Hỗ trợ định dạng**: PDF, DOCX, TXT, MD, XLSX, PPTX, PNG, JPG

Hệ thống tự động:
- Parse text content (multimodal parser xử lý images, tables, charts)
- Tạo vector embeddings (ChromaDB)
- Index vào cả text collection và multimodal collection
- Vision model (llava) phân tích hình ảnh
- Trích xuất entities và relationships vào NetworkX Knowledge Graph

### 3. Chat với tài liệu (Enhanced RAG)

**Chat** page → Nhập câu hỏi

**Query modes**:
- **Naive**: Simple vector search
- **Local**: Vector + local KG context
- **Global**: Vector + global KG context
- **Hybrid**: Combined (khuyến nghị)

Toggle **Use Knowledge Graph** để bật/tắt KG enhancement.

Kết quả hiển thị:
- Câu trả lời (có thể kèm multimodal context từ images/tables)
- Nguồn trích dẫn (document + page)
- Entities liên quan
- Multimodal results count

### 4. LightRAG Query

**LightRAG Query** page → Nhập query → Chọn mode

**5 modes**:
- **Naive**: Không dùng graph
- **Local**: Local entities & relations
- **Global**: Global communities
- **Hybrid**: Kết hợp local + global (khuyến nghị)
- **Mix**: LightRAG mix mode

**Features**:
- Real-time streaming responses
- Context-only mode (xem context không generate answer)
- Top-K tuning

### 5. LightRAG Document Management

**LightRAG Docs** page:
- Upload documents vào LightRAG (batch processing)
- View indexed documents (status: pending/processing/completed/failed)
- Delete documents
- Batch indexing với progress tracking

### 6. Khám phá Knowledge Graphs

**Graph** page (NetworkX KG):
- Xem thống kê (entities, relationships by type)
- Search entities
- Click vào entity để xem subgraph
- Admin: Rebuild graph

**LightRAG Graph** page:
- Browse entities & relations
- Edit entities/relations (admin)
- View graph statistics
- Rebuild LightRAG graph (admin)

### 7. Deep Research

**Research** page → Nhập research query → Chọn strategy → **Start Research**

Ví dụ query:
- "Phân tích chi tiết về kiến trúc microservices"
- "So sánh React vs Vue.js trong 2024"
- "Phân tích ưu nhược điểm của Kubernetes"

Theo dõi progress real-time → Xem findings → **Generate Report** để tạo báo cáo chi tiết

**Scheduled Research**: Lập lịch research tasks chạy định kỳ (với email/webhook notification)

### 8. Analytics Dashboard

**Analytics** page:
- Overview statistics (users, docs, queries, research)
- Daily activity charts (queries, uploads, research, logins)
- Top active users
- Popular queries
- Document statistics
- Action breakdown (query, upload, research, export, login)

### 9. Export Data

Các trang hỗ trợ export:
- **Chat**: Export lịch sử chat (JSON/CSV)
- **Research**: Export report (Markdown/PDF)
- **Graph**: Export knowledge graph (JSON/GraphML)
- **Documents**: Export danh sách tài liệu (CSV)

### 10. Enterprise Features (Admin)

**Enterprise** page:
- **Tenants**: Quản lý multi-tenancy
- **Roles & Permissions**: RBAC setup
- **Audit Logs**: Xem toàn bộ user actions
- **Compliance Reports**: GDPR/HIPAA compliance

### 11. Cấu hình hệ thống (Admin)

**Settings** page → Chỉnh sửa:
- **LLM**: Provider, model, temperature, Ollama URL
- **LightRAG**: LLM model, chunk settings, language
- **Search**: Tool (searxng/duckduckgo/wikipedia), iterations, max results
- **Embedding**: Provider (sentence-transformers/ollama), model
- **Security**: Rate limits, token tracking
- **LDAP**: AD/LDAP integration settings
- **Notifications**: Email (SMTP) & Webhook config

→ **Save Settings**

---

## 📡 API Endpoints

### Authentication

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/auth/register` | - | Đăng ký user mới |
| POST | `/api/auth/login` | - | Đăng nhập (trả về JWT token) |
| GET | `/api/auth/me` | User | Lấy thông tin user hiện tại |
| PUT | `/api/auth/password` | User | Đổi mật khẩu |

### Chat

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/chat/query` | User | Hỏi đáp RAG (body: `{query, use_knowledge_graph, mode}`) |
| GET | `/api/chat/history` | User | Lấy lịch sử chat |
| DELETE | `/api/chat/history` | User | Xóa lịch sử chat |

### Documents

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/documents/upload` | User | Upload tài liệu multimodal (form-data: files[]) - Hỗ trợ PDF, DOCX, XLSX, PPTX, images |
| GET | `/api/documents/list` | User | Danh sách tài liệu |
| DELETE | `/api/documents/{id}` | User | Xóa tài liệu |

### Multimodal

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/multimodal/info` | User | Thông tin multimodal processing config |
| GET | `/api/multimodal/stats` | User | Thống kê multimodal chunks |

### Knowledge Graph

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/knowledge-graph/stats` | User | Thống kê KG (entities, relationships, types) |
| GET | `/api/knowledge-graph/entities` | User | Danh sách tất cả entities |
| GET | `/api/knowledge-graph/search?q={name}` | User | Search entities theo tên |
| GET | `/api/knowledge-graph/entity/{name}?hops=2` | User | Lấy subgraph của entity (hops = độ sâu) |
| POST | `/api/knowledge-graph/rebuild` | Admin | Rebuild KG từ tất cả documents |

### Deep Research

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/research/start` | User | Bắt đầu deep research (body: `{query, strategy}`) |
| GET | `/api/research/{task_id}/progress` | User | Polling progress (status, %, message) |
| GET | `/api/research/{task_id}/result` | User | Lấy kết quả (findings, sources) |
| POST | `/api/research/{task_id}/report` | User | Tạo báo cáo markdown chi tiết |
| GET | `/api/research/history?limit=20` | User | Lịch sử research tasks |
| DELETE | `/api/research/{task_id}` | User | Xóa research task |
| GET | `/api/research/strategies` | User | Danh sách 7 strategies có sẵn |
| POST | `/api/research/schedule` | User | Lập lịch research tự động |

### LightRAG

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/lightrag/health` | User | Kiểm tra trạng thái LightRAG service |
| POST | `/api/lightrag/query` | User | Query với LightRAG (body: `{query, mode, top_k}`) - Modes: naive/local/global/hybrid/mix |
| POST | `/api/lightrag/query/stream` | User | Streaming query (NDJSON format) |
| POST | `/api/lightrag/query/context` | User | Query + trả về context |
| GET | `/api/lightrag/documents` | User | Danh sách documents trong LightRAG |
| POST | `/api/lightrag/documents/text` | User | Insert text vào LightRAG |
| POST | `/api/lightrag/documents/file` | User | Upload file vào LightRAG |
| POST | `/api/lightrag/documents/batch` | User | Batch insert files |
| DELETE | `/api/lightrag/documents/{doc_id}` | User | Xóa document từ LightRAG |
| GET | `/api/lightrag/graph/entities` | User | Danh sách entities trong LightRAG graph |
| GET | `/api/lightrag/graph/relations` | User | Danh sách relations |
| POST | `/api/lightrag/graph/entity/edit` | Admin | Chỉnh sửa entity |
| POST | `/api/lightrag/graph/relation/edit` | Admin | Chỉnh sửa relation |
| POST | `/api/lightrag/graph/rebuild` | Admin | Rebuild LightRAG graph |

### Analytics & Export

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/analytics/overview?days=30` | User | Tổng quan usage statistics |
| GET | `/api/analytics/daily?days=30` | User | Daily activity data for charts |
| GET | `/api/analytics/top-users?days=30` | User | Top active users |
| GET | `/api/analytics/popular-queries?days=30` | User | Popular queries |
| GET | `/api/analytics/document-stats` | User | Document statistics |
| POST | `/api/export/chat` | User | Export chat history (JSON/CSV) |
| POST | `/api/export/research/{task_id}` | User | Export research report (Markdown/PDF) |
| POST | `/api/export/kg` | User | Export knowledge graph (JSON/GraphML) |
| POST | `/api/export/documents` | User | Export documents list (CSV) |

### Enterprise (RBAC, Tenants, Permissions)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/enterprise/tenants` | Admin | Danh sách tenants |
| POST | `/api/enterprise/tenants` | Admin | Tạo tenant mới |
| PUT | `/api/enterprise/tenants/{id}` | Admin | Cập nhật tenant |
| GET | `/api/enterprise/roles` | Admin | Danh sách roles |
| POST | `/api/enterprise/roles` | Admin | Tạo role mới |
| POST | `/api/enterprise/roles/{id}/permissions` | Admin | Assign permissions |
| POST | `/api/enterprise/users/{id}/roles` | Admin | Assign roles cho user |
| GET | `/api/enterprise/audit-logs` | Admin | Xem audit logs |
| GET | `/api/enterprise/compliance/report` | Admin | Tạo compliance report |

### Settings (Admin only)

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/settings/ldr` | Admin | Lấy tất cả LDR settings |
| PUT | `/api/settings/ldr` | Admin | Cập nhật LDR settings (body: `{settings: {...}}`) |

### Admin

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/admin/stats` | Admin | Thống kê hệ thống |
| GET | `/api/admin/users` | Admin | Danh sách users |
| PUT | `/api/admin/users/{id}` | Admin | Cập nhật user (is_admin, is_active) |
| DELETE | `/api/admin/users/{id}` | Admin | Xóa user |

### System

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| GET | `/api/health` | - | Health check (database, ollama, lightrag status) |
| GET | `/api/search` | User | Unified search (documents + entities + multimodal) |

**API Docs (Swagger)**: `http://<server-ip>:81/docs`

---

## ⚙️ Cấu hình nâng cao

### 1. Biến môi trường (.env)

File: `backend/.env`

| Biến | Mô tả | Mặc định |
|------|-------|----------|
| `SECRET_KEY` | JWT secret key | Auto-generated |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://raguser:ragpassword@postgres:5432/ragdb` |
| `OLLAMA_HOST` | Ollama API URL | `http://ollama:11434` |
| `OLLAMA_LLM_MODEL` | LLM model name | `llama3.1` |
| `OLLAMA_VISION_MODEL` | Vision model cho multimodal | `llava` |
| `OLLAMA_EMBEDDING_MODEL` | Embedding model (nếu dùng Ollama) | `nomic-embed-text` |
| `EMBEDDING_PROVIDER` | `sentence-transformers` hoặc `ollama` | `sentence-transformers` |
| `EMBEDDING_MODEL` | Model cho sentence-transformers | `all-MiniLM-L6-v2` |
| `MAX_FILE_SIZE_MB` | Giới hạn upload file | `100` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry | `1440` (24h) |
| `SEARXNG_URL` | SearXNG API URL | `http://searxng:8080` |
| `LDR_SEARCH_TOOL` | Search tool cho LDR | `searxng` |
| `LDR_SEARCH_ITERATIONS` | Số vòng lặp search | `3` |
| `LDR_QUESTIONS_PER_ITERATION` | Số câu hỏi mỗi vòng lặp | `3` |
| `LDR_SEARCH_MAX_RESULTS` | Số kết quả tối đa mỗi search | `50` |
| **LightRAG Settings** | | |
| `LIGHTRAG_LLM_MODEL` | LLM model cho LightRAG | `llama3.2:3b` |
| `LIGHTRAG_WORKING_DIR` | Working directory cho LightRAG | `/app/data/lightrag_storage` |
| `LIGHTRAG_EMBED_MODEL` | Embedding model cho LightRAG | `nomic-embed-text:latest` |
| `LIGHTRAG_CHUNK_SIZE` | Chunk size | `800` |
| `LIGHTRAG_CHUNK_OVERLAP` | Chunk overlap | `100` |
| `LIGHTRAG_LANGUAGE` | Language | `Vietnamese` |
| `LIGHTRAG_NUM_CTX` | Context length | `2048` |
| **Enterprise Settings** | | |
| `ENCRYPTION_KEY` | Key cho encryption at rest | - |
| `LDAP_ENABLED` | Enable LDAP/AD authentication | `false` |
| `LDAP_SERVER` | LDAP server URL | `ldap://localhost:389` |
| `LDAP_BASE_DN` | Base DN | `dc=example,dc=com` |
| `LDAP_BIND_DN` | Bind DN | - |
| `LDAP_BIND_PASSWORD` | Bind password | - |
| `LDAP_USE_SSL` | Use SSL | `false` |
| `LDAP_AUTO_CREATE_USERS` | Auto-create users từ LDAP | `true` |
| **Notifications** | | |
| `SMTP_ENABLED` | Enable email notifications | `false` |
| `SMTP_HOST` | SMTP server | - |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | - |
| `SMTP_PASSWORD` | SMTP password | - |
| `SMTP_FROM` | From email | `noreply@localchatbox.local` |
| `WEBHOOK_ENABLED` | Enable webhooks | `false` |
| `WEBHOOK_URL` | Webhook URL | - |
| `WEBHOOK_SECRET` | Webhook secret | - |
| `LDR_SEARCH_MAX_RESULTS` | Số kết quả tối đa mỗi search | `50` |

### 2. Kích hoạt GPU (NVIDIA)

Nếu server có GPU NVIDIA, bỏ comment trong `docker-compose.yml`:

```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

**Yêu cầu**: Cài đặt NVIDIA Container Toolkit trên host

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
```

Restart containers:
```bash
docker-compose down
docker-compose up -d
```

### 3. Thay đổi LLM model

Download model khác từ Ollama:

```bash
# Xem danh sách model: https://ollama.com/library
docker exec -it ragchat-ollama ollama pull mistral
docker exec -it ragchat-ollama ollama pull phi3
```

Cập nhật `backend/.env`:
```env
OLLAMA_LLM_MODEL=mistral
```

Restart backend:
```bash
docker-compose restart backend
```

### 4. Cấu hình SearXNG cho intranet

Edit `searxng/settings.yml` để thêm engines tùy chỉnh:

```yaml
engines:
  - name: company_wiki
    engine: xpath
    search_url: http://wiki.company.local/search?q={query}
    url_xpath: //a[@class="result-link"]/@href
    title_xpath: //a[@class="result-link"]/text()
    content_xpath: //p[@class="snippet"]/text()
    shortcut: cw
    disabled: false
```

Restart SearXNG:
```bash
docker-compose restart searxng
```

### 5. Backup và Restore

#### Backup

```bash
# Backup database
docker exec ragchat-postgres pg_dump -U raguser ragdb > backup_$(date +%Y%m%d).sql

# Backup vector store + documents
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/
```

#### Restore

```bash
# Restore database
cat backup_YYYYMMDD.sql | docker exec -i ragchat-postgres psql -U raguser -d ragdb

# Restore data
tar -xzf data_backup_YYYYMMDD.tar.gz
```

---

## 🛠️ Lệnh hữu ích

### Docker Compose

```bash
# Xem logs tất cả services
docker-compose logs -f

# Xem logs của 1 service
docker-compose logs -f backend

# Restart services
docker-compose restart

# Stop tất cả
docker-compose down

# Stop và xóa volumes (XÓA DỮ LIỆU!)
docker-compose down -v

# Rebuild image
docker-compose build --no-cache backend
docker-compose up -d backend

# Xem status
docker-compose ps

# Xem tài nguyên sử dụng
docker stats
```

### Ollama

```bash
# List models đã download
docker exec ragchat-ollama ollama list

# Pull model mới
docker exec ragchat-ollama ollama pull llama3.1

# Xóa model
docker exec ragchat-ollama ollama rm llama3.1

# Test model
docker exec -it ragchat-ollama ollama run llama3.1 "Hello"
```

### Database

```bash
# Kết nối PostgreSQL CLI
docker exec -it ragchat-postgres psql -U raguser -d ragdb

# SQL commands:
\dt                    # List tables
\d users               # Describe users table
\d tenants             # Describe tenants table
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM usage_logs;
```

### ChromaDB & LightRAG

```bash
# Check ChromaDB collections
docker exec -it ragchat-backend python -c "
import chromadb
client = chromadb.PersistentClient(path='/app/data/vector_store')
print('Collections:', client.list_collections())
for col in client.list_collections():
    print(f'{col.name}: {col.count()} items')
"

# Check LightRAG status
curl http://localhost:8001/api/lightrag/health | jq .

# LightRAG statistics
curl -H "Authorization: Bearer <token>" http://localhost:8001/api/lightrag/graph/entities | jq '.entities | length'
```

# SQL commands:
\dt                    # List tables
\d research_tasks      # Describe table
SELECT COUNT(*) FROM users;
```

### SearXNG

```bash
# Test SearXNG
curl "http://localhost:8080/search?q=test&format=json" | jq .

# Restart SearXNG
docker-compose restart searxng
```

---

## 🔍 Troubleshooting

### 1. Backend không start

**Triệu chứng**: `docker-compose ps` hiện backend status `Restarting` hoặc `Exited`

**Kiểm tra logs**:
```bash
docker-compose logs backend
```

**Nguyên nhân thường gặp**:
- PostgreSQL chưa ready → Đợi 30s và kiểm tra lại
- `.env` file thiếu hoặc sai format → Kiểm tra lại file
- Port 8000 bị chiếm → Đổi port trong `docker-compose.yml`

### 2. Ollama không download model

**Triệu chứng**: `docker exec -it ragchat-ollama ollama pull llama3.1` bị lỗi

**Kiểm tra**:
```bash
docker logs ragchat-ollama
```

**Nguyên nhân**:
- Không có kết nối Internet → Cần Internet để download model lần đầu
- Disk full → Kiểm tra `df -h`
- OOM (out of memory) → Tăng RAM hoặc swap

**Giải pháp**: Download model offline:
1. Tải model từ https://ollama.com/library/llama3.1 trên máy khác
2. Copy vào server: `scp llama3.1.gguf user@server:/tmp/`
3. Import: `docker exec ragchat-ollama ollama create llama3.1 -f /tmp/llama3.1.gguf`

### 3. Frontend không kết nối backend

**Triệu chứng**: Trên trình duyệt, console hiển thị "Network Error"

**Kiểm tra**:
```bash
curl http://localhost/api/health
```

**Nguyên nhân**:
- Nginx config sai → Xem logs: `docker-compose logs nginx`
- Backend chưa ready → Đợi backend start xong
- Firewall chặn port 80 → Mở port: `sudo ufw allow 80`

### 4. Deep Research không hoạt động

**Triệu chứng**: Research task bị stuck ở "pending" hoặc "running" không tiến triển

**Kiểm tra**:
```bash
docker-compose logs backend | grep "research"
```

**Nguyên nhân**:
- SearXNG không hoạt động → Test: `curl http://localhost:8080`
- LLM model chưa download → Kiểm tra: `docker exec ragchat-ollama ollama list`
- Backend OOM → Kiểm tra: `docker stats`

**Giải pháp**:
```bash
# Restart toàn bộ services
docker-compose restart

# Rebuild backend nếu code thay đổi
docker-compose build backend && docker-compose up -d backend
```

### 5. Windows 10: Docker Desktop không start

**Triệu chứng**: Docker Desktop hiển thị "Starting..." mãi không xong

**Giải pháp**:
1. Kiểm tra WSL2: `wsl --status`
2. Nếu chưa cài: `wsl --install`
3. Restart máy
4. Bật Virtualization trong BIOS (Intel VT-x / AMD-V)
5. Reinstall Docker Desktop

### 6. Không truy cập được từ máy khác trong LAN

**Triệu chứng**: Trên máy Windows có thể truy cập `http://localhost`, nhưng từ máy khác không được

**Windows Firewall**:
```powershell
# Mở PowerShell với quyền Admin
New-NetFirewallRule -DisplayName "LocalAIChatBox" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
```

**Kiểm tra IP**:
```powershell
ipconfig
# Tìm IPv4 Address của adapter đang dùng
```

**Test từ máy khác**:
```bash
ping <IP-của-máy-Windows>
curl http://<IP-của-máy-Windows>/api/health
```

---

## 📊 Monitoring

### Health check

```bash
# Backend health
curl http://localhost/api/health
# Kết quả: {"status":"ok","services":{"database":"ok","ollama":"ok"}}

# Check all containers
docker-compose ps
```

### Resource usage

```bash
docker stats --no-stream
```

Theo dõi:
- **CPU%**: Ollama thường 50-200% khi đang inference
- **MEM USAGE**: Backend ~2-4GB, Ollama ~4-8GB (tùy model)
- **NET I/O**: Kiểm tra traffic giữa containers

### Logs

```bash
# Real-time logs
docker-compose logs -f --tail=100

# Filter by service
docker-compose logs -f backend

# Filter by keyword
docker-compose logs | grep ERROR
```

---

## 🔐 Bảo mật

### 1. Đổi mật khẩu mặc định

**Admin password**: Đăng nhập → User menu → Change Password

**PostgreSQL password**: Edit `docker-compose.yml` và `backend/.env`:
```yaml
# docker-compose.yml
POSTGRES_PASSWORD: new-secure-password

# backend/.env
DATABASE_URL=postgresql://raguser:new-secure-password@postgres:5432/ragdb
```

Restart:
```bash
docker-compose down
docker-compose up -d
```

### 2. Tạo SECRET_KEY mạnh

```bash
# Linux/Mac
openssl rand -hex 32

# Windows PowerShell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})
```

Cập nhật vào `backend/.env`:
```env
SECRET_KEY=your-new-32-char-random-string-here
```

### 3. Giới hạn truy cập mạng

**Nginx**: Chỉ cho phép truy cập từ LAN

Edit `nginx/nginx.conf`:
```nginx
server {
    listen 80;

    # Chỉ cho phép LAN
    allow 192.168.0.0/16;
    allow 10.0.0.0/8;
    deny all;

    # ... rest of config
}
```

Restart: `docker-compose restart nginx`

### 4. HTTPS (SSL/TLS)

Để enable HTTPS, thêm vào `nginx/nginx.conf`:

```nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # ... rest of config
}
```

Mount SSL certs:
```yaml
# docker-compose.yml
nginx:
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    - ./nginx/ssl:/etc/nginx/ssl:ro
```

---

## 📂 Cấu trúc thư mục

```
LocalAIChatBox/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app v6.0 (includes multimodal, LightRAG, enterprise)
│   │   ├── models.py                  # SQLAlchemy models (User, Document, Conversation, ChatSession,
│   │   │                              #   ResearchTask, UsageLog, Tenant, Role, DocumentPermission, etc.)
│   │   ├── database.py                # Database connection & init
│   │   ├── auth.py                    # JWT authentication, password hashing
│   │   ├── enhanced_rag_engine.py     # ChromaDB + multimodal RAG engine
│   │   ├── document_processor.py      # Basic document parsing
│   │   ├── knowledge_graph.py         # NetworkX KG, entity extraction
│   │   ├── deep_research.py           # DeepResearchService (LDR wrapper)
│   │   ├── ldr_settings.py            # LDR settings adapter
│   │   ├── research_routes.py         # Deep Research API endpoints
│   │   ├── lightrag_service.py        # LightRAG service wrapper
│   │   ├── lightrag_routes.py         # LightRAG API endpoints (query, documents, graph)
│   │   ├── enterprise_routes.py       # Enterprise features API (tenants, roles, audit)
│   │   ├── analytics.py               # Usage analytics & logging
│   │   ├── export_service.py          # Export features (chat, reports, KG)
│   │   ├── security_middleware.py     # Security headers, request validation
│   │   ├── rate_limiter.py            # Rate limiting
│   │   ├── token_tracker.py           # Token usage tracking
│   │   ├── rbac.py                    # Role-Based Access Control
│   │   ├── ldap_auth.py               # LDAP/AD integration
│   │   ├── encryption.py              # Data encryption service
│   │   ├── compliance.py              # Compliance reports (GDPR, HIPAA)
│   │   ├── notification_service.py    # Email/webhook notifications
│   │   ├── research_scheduler.py      # Scheduled research tasks
│   │   ├── advanced_research.py       # Advanced research features
│   │   ├── search_engines.py          # Search engine implementations
│   │   ├── citation_handler.py        # Citation tracking
│   │   ├── multimodal/                # Multimodal processing package
│   │   │   ├── __init__.py
│   │   │   ├── config.py              # Multimodal config
│   │   │   ├── document_parser.py     # Advanced multimodal parsing (PDF, DOCX, XLSX, PPTX, images)
│   │   │   ├── modal_processors.py    # Image, table, equation processors
│   │   │   ├── query_engine.py        # Multimodal query engine
│   │   │   ├── prompts.py             # Multimodal prompts
│   │   │   └── utils.py               # Multimodal utilities
│   │   └── lightrag/                  # LightRAG package (vendored or symlink)
│   ├── requirements.txt               # Python dependencies
│   ├── Dockerfile                     # Multi-stage build
│   └── .env                           # Environment variables
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   └── Navbar.jsx
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── ChatPage.jsx               # Enhanced RAG chat UI (multimodal + KG)
│   │   │   ├── DocumentsPage.jsx          # Document management (multimodal files)
│   │   │   ├── AdminPage.jsx              # User & system management
│   │   │   ├── KnowledgeGraphPage.jsx     # NetworkX KG explorer
│   │   │   ├── DeepResearchPage.jsx       # Deep Research UI
│   │   │   ├── SettingsPage.jsx           # LDR & system settings (admin)
│   │   │   ├── LightRAGQueryPage.jsx      # LightRAG query interface (5 modes)
│   │   │   ├── LightRAGDocumentsPage.jsx  # LightRAG document management
│   │   │   ├── LightRAGGraphPage.jsx      # LightRAG graph explorer
│   │   │   ├── AnalyticsPage.jsx          # Usage analytics dashboard
│   │   │   └── EnterprisePage.jsx         # Enterprise features (tenants, roles, audit logs)
│   │   ├── api.js                         # Axios API client
│   │   ├── App.jsx                        # Main app, routes
│   │   ├── App.css                        # Global styles
│   │   └── index.js
│   ├── package.json
│   ├── Dockerfile                         # Nginx + React build
│   └── nginx.conf
├── nginx/
│   └── nginx.conf                         # Reverse proxy config (port 81)
├── searxng/
│   └── settings.yml                       # SearXNG config
├── data/
│   ├── documents/                         # Uploaded files (all types)
│   ├── vector_store/                      # ChromaDB persistent storage
│   ├── parser_output/                     # Multimodal parsing outputs
│   ├── lightrag_storage/                  # LightRAG working directory (KG + embeddings)
│   └── database/                          # PostgreSQL data (Docker volume)
├── LightRAG-main/                         # LightRAG library source (optional, for development)
├── local-deep-research-main/              # LDR library source (optional)
├── RAG-Anything-main/                     # RAG-Anything inspiration (optional)
├── scripts/                               # Utility scripts
├── docker-compose.yml                     # 8 services orchestration (6 persistent + 2 init)
├── .dockerignore
├── setup.sh                               # Automated setup script (Ubuntu/Debian)
└── README.md                              # This file
```

---

## 🤝 Đóng góp

Dự án mã nguồn mở, chào đón mọi đóng góp:

1. Fork repo
2. Tạo branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m "Add your feature"`
4. Push: `git push origin feature/your-feature`
5. Tạo Pull Request

---

## 📄 License

MIT License - Xem file `LICENSE` để biết thêm chi tiết.

---

## 📞 Hỗ trợ

- **Issues**: https://github.com/your-username/LocalAIChatBox/issues
- **Wiki**: https://github.com/your-username/LocalAIChatBox/wiki
- **Discussions**: https://github.com/your-username/LocalAIChatBox/discussions

---

## 🎓 Tài liệu tham khảo

- **Ollama**: https://ollama.com/
- **LangChain**: https://python.langchain.com/
- **ChromaDB**: https://www.trychroma.com/
- **LightRAG**: https://github.com/HKUDS/LightRAG
- **SearXNG**: https://docs.searxng.org/
- **Sentence Transformers**: https://www.sbert.net/
- **FastAPI**: https://fastapi.tiangolo.com/
- **React**: https://react.dev/
- **NetworkX**: https://networkx.org/
- **Docker**: https://docs.docker.com/

---

<div align="center">

**LocalAIChatBox v6.0** - Hệ thống AI Multimodal hoàn toàn offline cho doanh nghiệp

Enterprise-ready • Multimodal • Knowledge Graph • Deep Research

Made with ❤️ by [Your Name/Team]

</div>


---

## 🚀 VI. LỘ TRÌNH ƯU TIÊN (Roadmap)

### Phase 1: Production Hardening ✅ (Completed in v6.0)
- ✅ Add logging (structlog + ELK/Loki)
- ✅ Add monitoring (Prometheus + Grafana)
- ✅ Implement backup/restore scripts
- ✅ Add unit + integration tests (target: 70% coverage)
- ✅ Setup CI/CD pipeline (GitHub Actions)
- ✅ Add audit logging system

### Phase 2: Performance & Scale ✅ (Completed in v6.0)
- ✅ Migrate FAISS → ChromaDB
- ✅ Implement Redis caching (via rate limiting)
- ✅ Enable GPU support + quantized models
- ✅ Add response streaming (SSE/NDJSON)
- ✅ Migrate deep research → async background tasks
- ✅ Load testing & optimization

### Phase 3: Feature Enhancement ✅ (Completed in v6.0)
- ✅ Document versioning & folders
- ✅ Chat history with context (Conversation + ChatSession)
- ✅ Interactive KG visualization (NetworkX + LightRAG)
- ✅ Advanced filters & faceted search
- ✅ Usage analytics dashboard
- ✅ Export features (chat, reports, graphs)

### Phase 4: Enterprise Features ✅ (Completed in v6.0)
- ✅ LDAP/AD integration (SSO)
- ✅ RBAC (Role-Based Access Control)
- ✅ Per-document permissions
- ✅ Encryption at rest
- ✅ Compliance reports (GDPR, etc.)
- ✅ Multi-tenancy support

### Phase 5: Multimodal & Advanced RAG ✅ (Completed in v6.0)
- ✅ Multimodal document processing (PDF, DOCX, XLSX, PPTX, images)
- ✅ Vision model integration (llava)
- ✅ Image/table/chart extraction and understanding
- ✅ Multimodal query engine
- ✅ Hybrid search (text + multimodal + KG)

### Phase 6: LightRAG Integration ✅ (Completed in v6.0)
- ✅ LightRAG service integration
- ✅ 5 query modes (naive, local, global, hybrid, mix)
- ✅ Streaming query support
- ✅ Batch document indexing
- ✅ Graph editing capabilities
- ✅ Dual KG system (NetworkX + LightRAG)

### Phase 7: Next Steps (v7.0 - Future)
- 🔄 Advanced RAG techniques (hypothetical document embeddings, multi-query)
- 🔄 Fine-tuning support for domain-specific models
- 🔄 Multi-language support (automatic language detection)
- 🔄 Advanced visualization (3D graph, timeline view)
- 🔄 Voice input/output (speech-to-text, text-to-speech)
- 🔄 Mobile app (React Native)
- 🔄 Collaborative features (shared workspaces, comments)
- 🔄 Integration với external tools (Slack, Teams, Jira)