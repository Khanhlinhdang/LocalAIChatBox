# 🚨 QUICK FIX - Common Deployment Errors

## ❌ Các lỗi đã gặp:

### 1. NumPy 2.0 Error:
```
AttributeError: `np.float_` was removed in the NumPy 2.0 release
```

### 2. Bcrypt Error:
```
AttributeError: module 'bcrypt' has no attribute '__about__'
ValueError: password cannot be longer than 72 bytes
```

### 3. Docker Build Error:
```
failed to solve: process "/bin/sh -c pip install..." did not complete successfully
```

### 4. Disk Space Error:
```
ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device
```

## 🔍 Nguyên nhân:

1. **NumPy 2.0**: ChromaDB 0.4.22 không hỗ trợ NumPy 2.0
2. **Bcrypt 4.x**: passlib 1.7.4 không tương thích với bcrypt 4.0+ (đã thay đổi API)
3. **ChromaDB 0.5.3**: Version này không tồn tại trên PyPI
4. **Disk full**: Docker build cache và old images chiếm hết disk space

## ✅ Giải pháp:

### A. Nếu gặp DISK SPACE ERROR (No space left):
```bash
# Chạy script cleanup (giải phóng 5-15 GB)
bash cleanup_docker.sh
```
📖 Chi tiết: [FIX_DISK_SPACE.md](FIX_DISK_SPACE.md)

### B. Dependency fixes:
- **ChromaDB**: Dùng version **0.4.22** (stable, đã test)
- **NumPy**: Pin **<2.0** để tránh NumPy 2.0 error
- **passlib**: Version **1.7.4** không có `[bcrypt]` extra
- **bcrypt**: Pin **3.2.2** (tương thích với passlib 1.7.4)
- **local-deep-research**: Đã remove (không còn cần thiết)

> 📘 **Lưu ý:** Deep Research feature đã bị disable. Xem [REMOVED_LDR.md](REMOVED_LDR.md) để biết chi tiết.

## 🔧 Làm ngay trên VPS:

### Option 1: Tự động (Recommended) ⚡

```bash
ssh root@194.59.xxx.xxx
cd ~/LocalAIChatBox
git pull origin main

# Chạy script tự động fix
bash fix_numpy_error.sh
```

Script sẽ tự động:
- ✅ Stop containers
- ✅ Pull code mới
- ✅ Rebuild với --no-cache
- ✅ Start services
- ✅ Verify ChromaDB & NumPy versions
- ✅ Test health endpoint

### Option 2: Manual (Step by step)

```bash
# 1. Pull code mới có fix ChromaDB 0.5.3
cd ~/LocalAIChatBox
git pull origin main

# 2. Stop containers
docker-compose down

# 3. XÓA Docker build cache cũ (QUAN TRỌNG!)
docker-compose build --no-cache backend

# 4. Start lại tất cả services
docker-compose up -d

# 5. Kiểm tra logs (chờ 10-15 giây để backend khởi động)
docker-compose logs backend --tail=50 -f
```

**⚠️ Lưu ý:** Phải dùng `--no-cache` để Docker không dùng lại layer cũ có ChromaDB 0.4.22!

## ✓ Expected logs (thành công):

```
ragchat-backend  | WARNING: local-deep-research package not installed
ragchat-backend  | Deep Research features will be disabled.
ragchat-backend  | Created new ChromaDB collection
ragchat-backend  | Database tables created
ragchat-backend  | Default admin user created (admin / admin123)
ragchat-backend  | Company RAG Chat Server Started
ragchat-backend  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

**✓ KHÔNG có error về bcrypt hay NumPy!**

**NOTE:** Warning về Deep Research là bình thường! App vẫn hoạt động đầy đủ (RAG, Auth, Chat).

## 🎯 Sau khi fix:

Test ngay: http://194.59.xxx.xxx:81

- Username: `admin`
- Password: `admin123`

---

**Tổng thời gian:** ~5-7 phút (chủ yếu là rebuild image)
