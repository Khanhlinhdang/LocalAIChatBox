# API Testing Guide

## 📋 Tổng quan

Có 2 script để test API:

1. **test_api.py** - Script Python chi tiết, chạy từ máy local
2. **test_api_vps.sh** - Bash script nhanh, chạy trực tiếp trên VPS

## 🐍 Test từ máy local (Python)

### Yêu cầu
```bash
pip install requests
```

### Chạy test
```bash
python test_api.py
```

### Tính năng
- ✅ Test health check
- ✅ Test user registration
- ✅ Test user login
- ✅ Test get current user
- ✅ Test admin login
- ✅ Test Nginx proxy
- 🎨 Colored output
- 📊 Detailed summary report

### Cấu hình
Sửa `BASE_URL` trong file `test_api.py`:
```python
BASE_URL = "http://194.59.xxx.xxx:81"  # Your VPS IP and port
```

## 🖥️ Test trực tiếp trên VPS (Bash)

### SSH vào VPS
```bash
ssh root@194.59.xxx.xxx
cd ~/LocalAIChatBox  # Hoặc đường dẫn project của bạn
```

### Pull code mới (nếu chưa có)
```bash
git pull origin main
```

### Phân quyền execute
```bash
chmod +x test_api_vps.sh
```

### Chạy test
```bash
./test_api_vps.sh
```

### Output mẫu
```
========================================
  LocalAIChatBox API Quick Test
========================================

[1/6] Testing Backend Health (Direct)...
✓ Backend Health Check: PASS
{
  "status": "healthy",
  "service": "Company RAG Chat",
  "version": "2.0",
  "services": {
    "database": "ok",
    "ollama": "ok"
  }
}

[2/6] Testing API through Nginx...
✓ Nginx Proxy: PASS

[3/6] Testing Database Connection...
✓ Database Connection: PASS

[4/6] Testing Admin Login...
✓ Admin Login: PASS
Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

[5/6] Testing Get Current User...
✓ Get Current User: PASS
{
  "id": 1,
  "username": "admin",
  "email": "admin@company.local",
  "full_name": "Administrator",
  "is_admin": true
}

[6/6] Testing User Registration...
✓ User Registration: PASS

========================================
  Test Complete
========================================
```

## 🔧 Manual cURL Tests

Nếu không muốn dùng script, test thủ công bằng curl:

### 1. Health Check
```bash
curl http://localhost:8001/api/health | python3 -m json.tool
```

### 2. Admin Login
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### 3. Register New User
```bash
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "new@example.com",
    "full_name": "New User",
    "password": "password123"
  }'
```

### 4. Get Current User (cần token từ login)
```bash
TOKEN="your_jwt_token_here"
curl http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## 🐛 Troubleshooting

### Test failed: Connection refused
**Problem**: Không kết nối được API

**Solutions**:
```bash
# Kiểm tra containers đang chạy
docker-compose ps

# Xem logs backend
docker-compose logs backend --tail=50

# Restart backend
docker-compose restart backend
```

### Test failed: HTTP 500 Internal Server Error
**Problem**: Backend lỗi

**Solutions**:
```bash
# Xem logs chi tiết
docker-compose logs backend --tail=100

# Kiểm tra database
docker exec -it ragchat-postgres psql -U raguser -d ragdb -c "SELECT 1"

# Restart cả stack
docker-compose restart
```

### Test failed: Database connection error
**Problem**: Backend không kết nối được database

**Solutions**:
```bash
# Check postgres running
docker-compose ps postgres

# Check postgres logs
docker-compose logs postgres --tail=50

# Restart postgres và backend
docker-compose restart postgres
sleep 5
docker-compose restart backend
```

### Test failed: Nginx proxy error
**Problem**: Nginx không proxy đúng

**Solutions**:
```bash
# Check nginx config
docker exec ragchat-nginx cat /etc/nginx/conf.d/default.conf

# Check nginx logs
docker-compose logs nginx --tail=50

# Restart nginx
docker-compose restart nginx
```

## 📊 Expected Results

### ✅ All Tests Pass
Nếu tất cả tests pass:
- API đang hoạt động bình thường
- Database kết nối OK
- Auth system hoạt động
- Có thể truy cập frontend và đăng nhập

### ❌ Some Tests Fail

#### Health Check Failed
→ Backend không chạy hoặc crash  
→ Check: `docker-compose logs backend`

#### Database Test Failed
→ PostgreSQL không chạy hoặc connection issue  
→ Check: `docker-compose ps postgres`

#### Login Failed
→ Backend chạy nhưng auth có vấn đề  
→ Check: Backend logs, database có user `admin` không

#### Nginx Test Failed
→ Nginx config sai hoặc backend không accessible  
→ Check: `nginx/nginx.conf`, upstream config

## 🚀 Next Steps

Sau khi tất cả tests pass:

1. **Test từ browser**: Truy cập http://194.59.xxx.xxx:81
2. **Đăng nhập**: Username `admin`, Password `admin123`
3. **Upload document**: Test RAG functionality
4. **Test chat**: Hỏi câu hỏi về documents
5. **Test admin panel**: Quản lý users, rebuild KG

## 📞 Need Help?

Nếu tests vẫn fail sau khi thử troubleshooting:

1. Chụp màn hình output của test script
2. Chạy: `docker-compose logs backend --tail=100 > backend.log`
3. Chạy: `docker-compose ps > containers.log`
4. Gửi các file logs để được hỗ trợ

## 🔄 Continuous Testing

Để monitor API liên tục:

```bash
# Run test every 30 seconds
watch -n 30 ./test_api_vps.sh

# Or create a cron job (run every 5 minutes)
*/5 * * * * /path/to/LocalAIChatBox/test_api_vps.sh > /var/log/api_test.log 2>&1
```
