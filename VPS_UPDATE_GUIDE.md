# 🔧 Hướng dẫn Update Backend sau khi Fix lỗi FAISS

## ⚠️ Vấn đề đã fix:
- **FAISS library** không tương thích với CPU của VPS (thiếu AVX2)
- Đã thay thế bằng **ChromaDB** - pure Python, không yêu cầu AVX2
- **NumPy 2.0 compatibility** - Nâng cấp ChromaDB lên **0.5.3** (hỗ trợ NumPy 2.0)
- Pin NumPy về **1.26.4** (stable version)

## 📋 Các bước thực hiện trên VPS

### Bước 1: SSH vào VPS

```bash
ssh root@194.59.xxx.xxx
cd ~/LocalAIChatBox  # Hoặc đường dẫn project của bạn
```

### Bước 2: Stop containers hiện tại

```bash
docker-compose down
```

### Bước 3: Pull code mới từ GitHub

```bash
git pull origin main
```

**Expected output:**
```
From https://github.com/Khanhlinhdang/LocalAIChatBox
 * branch            main       -> FETCH_HEAD
Updating xxxxxxx..xxxxxxx
Fast-forward
 backend/app/rag_engine.py              | 442 lines
 backend/app/rag_engine_faiss_backup.py | 224 lines
 backend/requirements.txt               | Changed (ChromaDB 0.5.3)
 3 files changed
```

> **⚠️ Important:** Code đã được nâng cấp ChromaDB lên 0.5.3 để fix NumPy compatibility!

### Bước 4: Rebuild backend image

```bash
docker-compose build --no-cache backend
```

**Thời gian:** ~5-10 phút (download ChromaDB và dependencies)

### Bước 5: Start lại containers

```bash
docker-compose up -d
```

### Bước 6: Kiểm tra backend logs

```bash
docker-compose logs backend --tail=50 -f
```

**Expected logs (sau vài giây):**
```
ragchat-backend  | Created new ChromaDB collection
ragchat-backend  | Database tables created
ragchat-backend  | Default admin user created (admin / admin123)
ragchat-backend  | Deep Research Service initialized
ragchat-backend  | Company RAG Chat Server Started (v2.0 with Deep Research)
ragchat-backend  | INFO:     Started server process [1]
ragchat-backend  | INFO:     Waiting for application startup.
ragchat-backend  | INFO:     Application startup complete.
ragchat-backend  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

Press **Ctrl+C** để thoát logs.

### Bước 7: Test API

```bash
# Test health check
curl http://localhost:8001/api/health

# Expected output:
# {
#   "status": "healthy",
#   "service": "Company RAG Chat",
#   "version": "2.0",
#   "services": {
#     "database": "ok",
#     "ollama": "ok"
#   }
# }
```

```bash
# Test login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Expected: JSON response with access_token
```

### Bước 8: Chạy test script

```bash
chmod +x test_api_vps.sh
./test_api_vps.sh
```

**Expected:** Tất cả tests PASS ✓

### Bước 9: Truy cập từ browser

Mở browser và truy cập: **http://194.59.xxx.xxx:81**

- Username: `admin`
- Password: `admin123`

## ✅ Checklist

- [ ] Git pull thành công
- [ ] Rebuild backend xong không lỗi
- [ ] Containers đang chạy: `docker-compose ps`
- [ ] Backend logs không có error
- [ ] Health check trả về status "healthy"
- [ ] Admin login thành công
- [ ] Frontend có thể truy cập
- [ ] Đăng nhập từ browser thành công

## 🔄 Nếu vẫn gặp lỗi

### Lỗi 1: NumPy 2.0 compatibility error

**Error message:**
```
AttributeError: `np.float_` was removed in the NumPy 2.0 release
```

**Nguyên nhân:** Docker vẫn dùng cached layer với ChromaDB 0.4.22 (không hỗ trợ NumPy 2.0)

**Giải pháp:** Đã nâng cấp lên ChromaDB 0.5.3

```bash
# PHẢI dùng --no-cache để xóa layer cũ
docker-compose down
docker-compose build --no-cache backend
docker-compose up -d

# Verify ChromaDB version
docker-compose exec backend pip show chromadb | grep Version
# Expected: Version: 0.5.3
```

### Lỗi 2: Backend vẫn không start

```bash
# Xem logs chi tiết
docker-compose logs backend --tail=100

# Rebuild lại hoàn toàn
docker-compose down -v  # Cảnh báo: Xóa data!
docker-compose build --no-cache
docker-compose up -d
```

### Lỗi 3: ChromaDB error

```bash
# Xóa ChromaDB data cũ (nếu có)
rm -rf data/vector_store/*

# Restart
docker-compose restart backend
```

### Lỗi 4: Database connection error

```bash
# Restart postgres trước
docker-compose restart postgres
sleep 10

# Rồi mới restart backend
docker-compose restart backend
```

### Lỗi 5: Port conflict

```bash
# Kiểm tra port đang bị chiếm
netstat -tulpn | grep -E ':(8001|81|5432)'

# Sửa port trong docker-compose.yml nếu cần
nano docker-compose.yml
```

## 📊 So sánh FAISS vs ChromaDB

| Feature | FAISS | ChromaDB |
|---------|-------|----------|
| **Yêu cầu CPU** | Cần AVX2 | Không cần AVX2 |
| **Cài đặt** | Phức tạp, C++ dependencies | Đơn giản, Pure Python |
| **Performance** | Rất nhanh (C++) | Nhanh (Python với Rust backend) |
| **API** | Phức tạp | Đơn giản, dễ dùng |
| **Persistence** | Manual (pickle) | Tự động (SQLite) |
| **Filtering** | Không có built-in | Có metadata filtering |

## 🎯 Next Steps

Sau khi backend chạy thành công:

1. **Upload documents**: Test chức năng RAG
2. **Chat**: Hỏi đáp về documents
3. **Deep Research**: Test research system
4. **Admin Panel**: Quản lý users

## 📞 Support

Nếu vẫn gặp vấn đề, gửi:

```bash
# Container status
docker-compose ps > status.log

# Backend logs
docker-compose logs backend --tail=200 > backend.log

# System info
uname -a > system.log
cat /proc/cpuinfo | grep flags > cpu_flags.log
```

## 🔍 Verify AVX2 Support (Optional)

Để kiểm tra CPU có hỗ trợ AVX2 không:

```bash
# Check CPU flags
grep -o 'avx2' /proc/cpuinfo | head -1

# If output is empty -> No AVX2 support
# If output is "avx2" -> AVX2 is supported
```

## 📚 ChromaDB Documentation

- Homepage: https://www.trychroma.com/
- Docs: https://docs.trychroma.com/
- GitHub: https://github.com/chroma-core/chroma

## 🎉 Kết luận

ChromaDB là lựa chọn tốt hơn cho môi trường production vì:
- ✅ Tương thích với mọi CPU
- ✅ Dễ cài đặt và maintain
- ✅ API đơn giản, ít bug
- ✅ Built-in persistence
- ✅ Metadata filtering
- ✅ Active development & support
