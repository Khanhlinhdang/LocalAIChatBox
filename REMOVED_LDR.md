# 🔧 Fix: Removed local-deep-research Dependency

## ⚠️ Vấn đề:
- Folder `local-deep-research` đã bị xóa
- Docker build failed: `COPY local-deep-research: not found`

## ✅ Đã fix:

### 1. Backend Dockerfile
- ❌ Removed: `COPY local-deep-research /build/local-deep-research`
- ❌ Removed: `RUN pip install -e /build/local-deep-research`
- ❌ Removed: `COPY --from=builder /build/local-deep-research /app/local-deep-research`

### 2. Deep Research Service
- ✅ Added graceful error handling
- ✅ Check if `local-deep-research` package available
- ✅ Return error message instead of crash if not installed
- ✅ App still works, only Deep Research feature disabled

### 3. Requirements.txt
- ✅ Fixed ChromaDB version: `chromadb==0.5.3`
- ✅ Fixed NumPy version: `numpy==1.26.4`

## 📊 Impact:

| Feature | Status | Notes |
|---------|--------|-------|
| **Backend API** | ✅ Working | No impact |
| **User Auth** | ✅ Working | No impact |
| **RAG (Document Chat)** | ✅ Working | No impact |
| **Knowledge Graph** | ✅ Working | No impact |
| **Deep Research** | ⚠️ Disabled | Returns error message if accessed |

## 🚀 Deploy trên VPS (PHẢI REBUILD):

```bash
ssh root@194.59.165.202
cd ~/LocalAIChatBox

# Pull code mới
git pull origin main

# Stop containers
docker-compose down

# Rebuild backend (bắt buộc vì Dockerfile thay đổi)
docker-compose build --no-cache backend

# Start lại
docker-compose up -d

# Kiểm tra logs
docker-compose logs backend --tail=50 -f
```

## ✓ Expected Logs:

```
ragchat-backend  | WARNING: local-deep-research package not installed: ...
ragchat-backend  | Deep Research features will be disabled.
ragchat-backend  | Created new ChromaDB collection
ragchat-backend  | Database tables created
ragchat-backend  | Default admin user created (admin / admin123)
ragchat-backend  | Warning: Deep Research Service init failed (non-fatal): ...
ragchat-backend  | Company RAG Chat Server Started (v2.0 with Deep Research)
ragchat-backend  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

**NOTE:** WARNING về Deep Research là bình thường và không ảnh hưởng ứng dụng!

## 🧪 Test sau khi deploy:

```bash
# Test health check
curl http://194.59.165.202:81/api/health

# Test login
curl -X POST http://194.59.165.202:81/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Mở browser
# http://194.59.165.202:81
```

## 💡 Nếu muốn enable Deep Research lại:

### Option 1: Clone local-deep-research về
```bash
cd ~/LocalAIChatBox
git clone https://github.com/user/local-deep-research.git

# Rebuild backend
docker-compose build --no-cache backend
docker-compose up -d
```

### Option 2: Install như pip package (nếu có trên PyPI)
```bash
# Thêm vào backend/requirements.txt:
# local-deep-research==x.x.x

# Rebuild
docker-compose build --no-cache backend
docker-compose up -d
```

## 📝 Technical Details:

### Graceful Degradation Implementation:

```python
# backend/app/deep_research.py

LDR_AVAILABLE = False
try:
    import local_deep_research
    LDR_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: local-deep-research not installed")
    print("Deep Research features will be disabled.")

class DeepResearchService:
    def start_research(self, ...):
        if not self._ldr_available:
            # Return error instead of crash
            task.status = "failed"
            task.error_message = "Deep Research not installed"
            return task_id
        # ... normal code
```

### Main.py Already Handles This:

```python
# backend/app/main.py line 62-66

try:
    from app.deep_research import get_research_service
    get_research_service()
    print("Deep Research Service initialized")
except Exception as e:
    print(f"Warning: Deep Research Service init failed (non-fatal): {e}")
```

## 🎯 Kết luận:

- ✅ Backend CÓ THỂ build và chạy mà không cần `local-deep-research`
- ✅ App hoạt động bình thường (RAG, Auth, Knowledge Graph)
- ⚠️ Deep Research feature disabled (trả về error nếu user thử dùng)
- 🔧 Có thể enable lại bằng cách clone folder về hoặc cài package

---

**Thời gian rebuild:** ~5-7 phút

**Downtime:** ~1 phút (trong khi restart containers)
