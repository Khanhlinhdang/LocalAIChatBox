# 🚨 QUICK FIX - NumPy 2.0 Error

## ❌ Lỗi gặp phải:
```
AttributeError: `np.float_` was removed in the NumPy 2.0 release
```

## ✅ Đã fix:
- Pin NumPy về version `<2.0` trong requirements.txt
- ChromaDB 0.4.22 chỉ hỗ trợ NumPy 1.x

## 🔧 Làm ngay trên VPS:

```bash
# 1. Pull code mới có fix
cd ~/LocalAIChatBox
git pull origin main

# 2. Rebuild backend với --no-cache (QUAN TRỌNG!)
docker-compose build --no-cache backend

# 3. Start lại
docker-compose up -d

# 4. Kiểm tra logs
docker-compose logs backend --tail=30 -f
```

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
