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

**LocalAIChatBox** là một hệ thống trí tuệ nhân tạo đầy đủ tính năng được thiết kế để chạy **100% offline** trên mạng nội bộ công ty. Hệ thống kết hợp:

- **RAG (Retrieval-Augmented Generation)** - Hỏi đáp dựa trên tài liệu công ty
- **Knowledge Graph** - Trích xuất và quản lý quan hệ thực thể tự động
- **Deep Research** - Nghiên cứu sâu với tìm kiếm đa bước thông minh
- **Multi-user System** - Quản lý nhiều người dùng với phân quyền admin

### Đặc điểm nổi bật

✅ **Hoàn toàn Offline** - Không cần kết nối Internet sau khi cài đặt
✅ **Bảo mật tuyệt đối** - Dữ liệu không rời khỏi mạng nội bộ
✅ **Dễ dàng triển khai** - Chỉ 1 lệnh cài đặt tự động
✅ **Mã nguồn mở** - Có thể tùy chỉnh theo nhu cầu
✅ **Giao diện hiện đại** - Dark mode, responsive design

---

## 🏗️ Kiến trúc hệ thống

```
Mạng nội bộ công ty (LAN)
├── Nginx (Port 80)             - Reverse proxy
├── React Frontend (Port 3000)  - Giao diện web
├── FastAPI Backend (Port 8000) - API server
├── PostgreSQL (Port 5432)      - Cơ sở dữ liệu
├── Ollama (Port 11434)         - LLM + Embeddings
├── SearXNG (Port 8080)         - Meta search engine
├── FAISS Vector Store          - Tìm kiếm vector tài liệu
└── Knowledge Graph (networkx)  - Trích xuất quan hệ thực thể
```

**7 services** chạy trong Docker containers, giao tiếp qua mạng Docker internal.

---

## ✨ Tính năng

### 1. Xác thực đa người dùng (JWT)
- Đăng ký / Đăng nhập
- Quản lý phiên làm việc
- Phân quyền admin / user thường

### 2. Quản lý tài liệu
- Upload: PDF, DOCX, TXT, MD
- Tự động parse + chunking
- Index vào FAISS vector store
- Trích xuất thực thể vào Knowledge Graph

### 3. RAG Chat (Retrieval-Augmented Generation)
- Hỏi đáp dựa trên tài liệu công ty
- Trích dẫn nguồn tự động
- Toggle giữa **KG-RAG** (sử dụng Knowledge Graph) và **Basic RAG** (chỉ vector search)
- Lịch sử chat riêng cho từng user

### 4. Knowledge Graph RAG
- **Entity Extraction**: Tự động trích xuất 7 loại thực thể (PERSON, ORGANIZATION, PROJECT, TECHNOLOGY, PRODUCT, LOCATION, CONCEPT)
- **Relationship Discovery**: Phát hiện quan hệ giữa các thực thể
- **Multi-hop Reasoning**: Tìm kiếm đa bước thông qua graph
- **KG Explorer**: Giao diện khám phá graph với search, filter, subgraph viewer

### 5. Deep Research System
- **7 chiến lược nghiên cứu**:
  - `source-based`: Theo dõi nguồn chi tiết (mặc định)
  - `rapid`: Tốc độ cao, single-pass
  - `parallel`: Tìm kiếm đồng thời đa query
  - `standard`: Cân bằng giữa tốc độ và độ sâu
  - `iterative`: Lặp liên tục, tích lũy kiến thức
  - `focused-iteration`: Tinh chỉnh thích ứng
  - `smart`: Tự động chọn chiến lược tốt nhất
- **Progress tracking**: Theo dõi tiến độ real-time
- **Report generation**: Tạo báo cáo markdown chi tiết
- **Research history**: Lưu trữ và xem lại các nghiên cứu cũ

### 6. Admin Dashboard
- Quản lý người dùng (thêm/xóa/sửa)
- Thống kê hệ thống (số user, tài liệu, entities, relationships)
- Rebuild Knowledge Graph
- Cấu hình LDR settings (LLM, Search, Embedding)

### 7. LAN Networking
- Truy cập từ mọi máy tính trong mạng nội bộ
- Không cần kết nối Internet sau khi setup
- Có thể cấu hình SearXNG cho intranet search

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
4. Build và start 7 Docker containers
5. Download LLM model (llama3.1) vào Ollama
6. Kiểm tra health của tất cả services

**Thời gian**: ~15-30 phút (tùy tốc độ mạng khi download LLM model 4.7GB)

#### 2. Sau khi cài đặt

Truy cập hệ thống tại: `http://<server-ip>`

Đăng nhập admin mặc định:
- Username: `admin`
- Password: `admin123`

**⚠️ Quan trọng**: Đổi mật khẩu admin ngay sau khi đăng nhập lần đầu!

#### 3. Tìm IP của server

```bash
hostname -I
```

Ví dụ: `192.168.1.100`

Các máy trong cùng mạng LAN truy cập: `http://192.168.1.100`

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
SECRET_KEY=your-secret-key-here-change-this-to-random-string
DATABASE_URL=postgresql://raguser:ragpassword@postgres:5432/ragdb
OLLAMA_HOST=http://ollama:11434
OLLAMA_LLM_MODEL=llama3.1
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
MAX_FILE_SIZE_MB=100
ACCESS_TOKEN_EXPIRE_MINUTES=1440
SEARXNG_URL=http://searxng:8080
LDR_SEARCH_TOOL=searxng
LDR_SEARCH_ITERATIONS=3
LDR_QUESTIONS_PER_ITERATION=3
LDR_SEARCH_MAX_RESULTS=50
```

**Tạo SECRET_KEY ngẫu nhiên** (PowerShell):
```powershell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | % {[char]$_})
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

#### Bước 6: Download LLM model

```powershell
docker exec -it ragchat-ollama ollama pull llama3.1
```

Đợi download hoàn thành (4.7GB).

#### Bước 7: Kiểm tra services

```powershell
docker-compose ps
```

Tất cả services phải có status `Up` hoặc `healthy`.

#### Bước 8: Truy cập

Mở trình duyệt:
- **Trên máy Windows hiện tại**: http://localhost
- **Từ máy khác trong mạng LAN**: http://<IP-của-máy-Windows>

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

Truy cập `http://<server-ip>` → Đăng nhập với `admin` / `admin123`

### 2. Upload tài liệu

**Documents** page → **Upload Documents** → Chọn file (PDF, DOCX, TXT, MD)

Hệ thống tự động:
- Parse và chunk text
- Tạo vector embeddings
- Index vào FAISS
- Trích xuất entities và relationships vào Knowledge Graph

### 3. Chat với tài liệu (RAG)

**Chat** page → Nhập câu hỏi

Toggle **KG-RAG** / **Basic RAG**:
- **KG-RAG**: Sử dụng cả vector search + knowledge graph (khuyến nghị)
- **Basic RAG**: Chỉ vector search (nhanh hơn, ít context hơn)

Kết quả hiển thị:
- Câu trả lời
- Nguồn trích dẫn (document + page)
- Entities liên quan (nếu dùng KG-RAG)

### 4. Khám phá Knowledge Graph

**Graph** page → Xem thống kê, search entities, click vào entity để xem subgraph

**Admin only**: Rebuild Graph (xử lý lại tất cả documents)

### 5. Deep Research

**Research** page → Nhập research query → Chọn strategy → **Start Research**

Ví dụ query:
- "Tóm tắt các xu hướng AI trong 2024"
- "So sánh React vs Vue.js"
- "Phân tích ưu nhược điểm của Kubernetes"

Theo dõi progress real-time → Xem findings → **Generate Report** để tạo báo cáo chi tiết

### 6. Cấu hình hệ thống (Admin)

**Settings** page → Chỉnh sửa:
- **LLM**: Provider, model, temperature, Ollama URL
- **Search**: Tool (searxng/duckduckgo/wikipedia), iterations, questions per iteration, max results
- **Embedding**: Provider (sentence-transformers/ollama), model
- **Report**: Searches per section

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
| POST | `/api/chat/query` | User | Hỏi đáp RAG (body: `{query, use_knowledge_graph}`) |
| GET | `/api/chat/history` | User | Lấy lịch sử chat |
| DELETE | `/api/chat/history` | User | Xóa lịch sử chat |

### Documents

| Method | Endpoint | Auth | Mô tả |
|--------|----------|------|-------|
| POST | `/api/documents/upload` | User | Upload tài liệu (form-data: files[]) |
| GET | `/api/documents/list` | User | Danh sách tài liệu |
| DELETE | `/api/documents/{id}` | User | Xóa tài liệu |

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
| GET | `/api/health` | - | Health check |

**API Docs (Swagger)**: `http://<server-ip>/docs`

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
│   │   ├── main.py                # FastAPI app, lifespan events
│   │   ├── models.py              # SQLAlchemy models (User, Document, ChatHistory, ResearchTask, ResearchSetting)
│   │   ├── database.py            # Database connection
│   │   ├── auth.py                # JWT authentication, password hashing
│   │   ├── rag_engine.py          # FAISS + sentence-transformers RAG
│   │   ├── document_processor.py  # PDF/DOCX/TXT/MD parsing
│   │   ├── knowledge_graph.py     # NetworkX KG, entity extraction
│   │   ├── deep_research.py       # DeepResearchService (LDR wrapper)
│   │   ├── ldr_settings.py        # LDR settings adapter
│   │   └── research_routes.py     # Deep Research API endpoints
│   ├── requirements.txt           # Python dependencies
│   ├── Dockerfile                 # Multi-stage build
│   └── .env                       # Environment variables
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   └── Navbar.jsx
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   ├── ChatPage.jsx          # RAG chat UI
│   │   │   ├── DocumentsPage.jsx      # Document management
│   │   │   ├── AdminPage.jsx          # User management
│   │   │   ├── KnowledgeGraphPage.jsx # KG explorer
│   │   │   ├── DeepResearchPage.jsx   # Deep Research UI
│   │   │   └── SettingsPage.jsx       # LDR settings (admin)
│   │   ├── api.js                     # Axios API client
│   │   ├── App.jsx                    # Main app, routes
│   │   ├── App.css                    # Global styles
│   │   └── index.js
│   ├── package.json
│   ├── Dockerfile                     # Nginx + React build
│   └── nginx.conf
├── nginx/
│   └── nginx.conf                     # Reverse proxy config
├── searxng/
│   └── settings.yml                   # SearXNG config
├── data/
│   ├── documents/                     # Uploaded files
│   ├── vector_store/                  # FAISS index files
│   └── database/                      # PostgreSQL data (managed by Docker volume)
├── local-deep-research/               # LDR package (git submodule hoặc copy)
│   ├── local_deep_research/
│   │   ├── __init__.py
│   │   ├── search_system.py           # AdvancedSearchSystem
│   │   ├── report_generator.py        # IntegratedReportGenerator
│   │   ├── config/
│   │   │   ├── llm_config.py          # get_llm()
│   │   │   └── search_config.py       # get_search()
│   │   └── ...
│   └── setup.py
├── docker-compose.yml                 # 7 services orchestration
├── .dockerignore
├── setup.sh                           # Automated setup script (Ubuntu/Debian)
└── README.md                          # This file
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
- **FAISS**: https://github.com/facebookresearch/faiss
- **SearXNG**: https://docs.searxng.org/
- **Sentence Transformers**: https://www.sbert.net/
- **FastAPI**: https://fastapi.tiangolo.com/
- **React**: https://react.dev/

---

<div align="center">

**LocalAIChatBox** - Hệ thống AI hoàn toàn offline cho doanh nghiệp

Made with ❤️ by [Your Name/Team]

</div>


🚀 VI. LỘ TRÌNH ƯU TIÊN (Roadmap)
Phase 1: Production Hardening (1-2 tháng)
✅ Add logging (structlog + ELK/Loki)
✅ Add monitoring (Prometheus + Grafana)
✅ Implement backup/restore scripts
✅ Add unit + integration tests (target: 70% coverage)
✅ Setup CI/CD pipeline (GitHub Actions)
✅ Add audit logging system
Phase 2: Performance & Scale (1-2 tháng)
✅ Migrate ChromaDB → Qdrant/Milvus
✅ Implement Redis caching
✅ Enable GPU support + quantized models
✅ Add response streaming (SSE)
✅ Migrate deep research → Celery + Redis
✅ Load testing & optimization
Phase 3: Feature Enhancement (2-3 tháng)
✅ Document versioning & folders
✅ Chat history with context (multi-turn)
✅ Interactive KG visualization (D3.js/Cytoscape)
✅ Advanced filters & faceted search
✅ Usage analytics dashboard
✅ Export features (chat, reports, graphs)
Phase 4: Enterprise Features (2-3 tháng)
✅ LDAP/AD integration (SSO)
✅ RBAC (Role-Based Access Control)
✅ Per-document permissions
✅ Encryption at rest
✅ Compliance reports (GDPR, etc.)
✅ Multi-tenancy support