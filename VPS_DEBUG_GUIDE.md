# Hướng dẫn Debug và Fix API trên VPS Ubuntu

## 🔍 Các thay đổi đã thực hiện

### 1. Cải thiện Health Check Endpoint
- Thêm kiểm tra kết nối database
- Thêm kiểm tra Ollama service
- Trả về chi tiết status của từng service

### 2. Tối ưu Auth Endpoints
- Thêm error handling toàn diện
- Logs chi tiết cho debugging
- Better HTTP status codes
- Transaction rollback khi lỗi

### 3. Database Connection
- Thêm connection pooling
- Pool pre-ping để tránh timeout

## 📋 Các bước thực hiện trên VPS

### Bước 1: Kết nối SSH vào VPS

```bash
ssh root@194.59.165.202
# Hoặc ssh user@194.59.165.202
```

### Bước 2: Vào thư mục project

```bash
cd /path/to/LocalAIChatBox
# Hoặc nếu deploy ở home: cd ~/LocalAIChatBox
```

### Bước 3: Pull code mới

```bash
git pull origin main
```

### Bước 4: Kiểm tra logs backend

```bash
# Xem logs backend để tìm lỗi
docker-compose logs backend --tail=50

# Hoặc follow real-time
docker-compose logs -f backend
```

### Bước 5: Restart containers

```bash
# Rebuild và restart backend
docker-compose build backend
docker-compose up -d backend

# Hoặc restart toàn bộ
docker-compose restart
```

### Bước 6: Test Health Check

```bash
# Test từ VPS
curl http://localhost:8001/api/health

# Kỳ vọng response:
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

### Bước 7: Test API trực tiếp

```bash
# Test register
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "full_name": "Test User",
    "password": "test123"
  }'

# Test login
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

## 🐛 Debug Common Issues

### Issue 1: Network Error từ Frontend

**Triệu chứng**: Không call được API từ browser

**Kiểm tra**:
```bash
# 1. Kiểm tra nginx có chạy không
docker-compose ps nginx

# 2. Xem logs nginx
docker-compose logs nginx --tail=50

# 3. Test API qua nginx
curl http://localhost:81/api/health
```

**Fix**: Kiểm tra nginx config
```bash
cat nginx/nginx.conf
```

Đảm bảo có đúng proxy_pass:
```nginx
location /api/ {
    proxy_pass http://backend:8000;
    ...
}
```

### Issue 2: Database Connection Error

**Triệu chứng**: Backend logs hiển thị "could not connect to server"

**Kiểm tra**:
```bash
# 1. PostgreSQL có chạy không
docker-compose ps postgres

# 2. Test connection
docker exec -it ragchat-postgres psql -U raguser -d ragdb -c "SELECT 1"
```

**Fix**: 
```bash
# Restart postgres
docker-compose restart postgres

# Chờ 10s rồi restart backend
sleep 10
docker-compose restart backend
```

### Issue 3: CORS Error

**Triệu chứng**: Browser console hiển thị CORS policy error

**Fix**: Backend đã set `allow_origins=["*"]` nhưng nếu vẫn lỗi, kiểm tra:

```bash
# Xem logs để tìm CORS error
docker-compose logs backend | grep -i cors
```

### Issue 4: 500 Internal Server Error

**Kiểm tra logs chi tiết**:
```bash
# Xem logs với timestamp
docker-compose logs backend --timestamps --tail=100

# Tìm error stack trace
docker-compose logs backend | grep -A 20 "Traceback"
```

## 🔧 Useful Commands

### Container Management

```bash
# Xem status tất cả containers
docker-compose ps

# Restart một service
docker-compose restart backend

# Xem resource usage
docker stats

# Vào shell của backend container
docker exec -it ragchat-backend bash

# Xem environment variables
docker exec ragchat-backend env | grep -E "DATABASE|OLLAMA"
```

### Database Commands

```bash
# Kết nối PostgreSQL
docker exec -it ragchat-postgres psql -U raguser -d ragdb

# Trong psql:
\dt                          # List tables
\d users                     # Describe users table
SELECT * FROM users;         # List all users
SELECT COUNT(*) FROM users;  # Count users
```

### Log Management

```bash
# Clear all logs
docker-compose down
docker system prune -f

# Restart fresh
docker-compose up -d

# Tail logs của nhiều services
docker-compose logs -f backend nginx postgres
```

## 📊 Monitoring

### Check System Resources

```bash
# Disk space
df -h

# Memory usage
free -h

# Docker disk usage
docker system df
```

### Monitor Logs Live

```bash
# Terminal 1: Backend logs
docker-compose logs -f backend

# Terminal 2: Nginx logs
docker-compose logs -f nginx

# Terminal 3: Database logs
docker-compose logs -f postgres
```

## ✅ Test Checklist

Sau khi deploy, test các endpoint sau:

1. **Health Check**
   - [ ] `curl http://194.59.165.202:81/api/health`
   - Expect: `{"status": "healthy", ...}`

2. **Register**
   - [ ] Vào http://194.59.165.202:81/login
   - [ ] Click "Register"
   - [ ] Điền thông tin và submit
   - Expect: Redirect to dashboard

3. **Login**
   - [ ] Login với `admin` / `admin123`
   - Expect: Redirect to dashboard với user info

4. **Protected Routes**
   - [ ] Truy cập /documents
   - [ ] Truy cập /chat
   - Expect: Load thành công, không bị redirect về login

## 🚨 Emergency Rollback

Nếu có vấn đề nghiêm trọng:

```bash
# Stop tất cả
docker-compose down

# Rollback code (nếu cần)
git reset --hard HEAD~1
git pull origin main

# Rebuild từ đầu
docker-compose build --no-cache
docker-compose up -d
```

## 📞 Get Help

Nếu vẫn gặp vấn đề, gửi output của các lệnh sau:

```bash
# 1. Container status
docker-compose ps

# 2. Backend logs (50 dòng cuối)
docker-compose logs backend --tail=50

# 3. Health check
curl http://localhost:8001/api/health

# 4. Database connection
docker exec -it ragchat-postgres psql -U raguser -d ragdb -c "SELECT version()"
```
