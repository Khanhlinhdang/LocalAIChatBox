# 🚨 QUICK FIX - NumPy 2.0 Compatibility Error

## ❌ Lỗi gặp phải:
```
AttributeError: `np.float_` was removed in the NumPy 2.0 release
```

**Nguyên nhân:** ChromaDB 0.4.22 không hỗ trợ NumPy 2.0

## ✅ Giải pháp:
- **Nâng cấp ChromaDB** lên version **0.5.3** (hỗ trợ NumPy 2.0)
- Pin NumPy về **1.26.4** (stable version)
- Code đã được cập nhật và test với ChromaDB 0.5.3

## 🔧 Làm ngay trên VPS:

### Option 1: Tự động (Recommended) ⚡

```bash
ssh root@194.59.165.202
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
ragchat-backend  | Created new ChromaDB collection
ragchat-backend  | Database tables created
ragchat-backend  | Default admin user created (admin / admin123)
ragchat-backend  | Company RAG Chat Server Started
ragchat-backend  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 🎯 Sau khi fix:

Test ngay: http://194.59.165.202:81

- Username: `admin`
- Password: `admin123`

---

**Tổng thời gian:** ~5-7 phút (chủ yếu là rebuild image)
