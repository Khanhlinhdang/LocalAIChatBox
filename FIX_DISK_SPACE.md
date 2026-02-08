# 💾 Fix: No Space Left On Device Error

## ❌ Lỗi gặp phải:
```
ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device
```

## 🔍 Nguyên nhân:
- Docker build cache chiếm quá nhiều disk space
- Các images cũ không được dọn dẹp
- VPS hết dung lượng ổ đĩa

## ✅ Giải pháp NHANH:

### Option 1: Script tự động (Recommended) ⚡

```bash
ssh root@194.59.xxx.xxx
cd ~/LocalAIChatBox
git pull origin main

# Chạy script cleanup
bash cleanup_docker.sh
```

**Script sẽ tự động:**
- ✅ Kiểm tra dung lượng disk
- ✅ Stop containers
- ✅ Xóa stopped containers
- ✅ Xóa unused images
- ✅ Xóa ALL build cache
- ✅ Xóa unused networks
- ✅ Hiển thị dung lượng đã giải phóng

### Option 2: Manual cleanup (Step by step)

```bash
ssh root@194.59.xxx.xxx

# 1. Kiểm tra dung lượng hiện tại
df -h

# 2. Kiểm tra Docker đang dùng bao nhiêu
docker system df

# 3. Stop containers
cd ~/LocalAIChatBox
docker-compose down

# 4. Xóa tất cả unused data (images, containers, cache)
docker system prune -a -f --volumes

# 5. Kiểm tra lại dung lượng
df -h
docker system df
```

### Option 3: Aggressive cleanup (Nếu vẫn không đủ)

```bash
# Xóa TOÀN BỘ Docker data (cẩn thận!)
docker system prune -a -f --volumes

# Xóa build cache riêng
docker builder prune -a -f

# Nếu vẫn không đủ, xóa log files
sudo journalctl --vacuum-size=100M

# Xóa apt cache
sudo apt-get clean
sudo apt-get autoremove
```

## 📊 Kiểm tra disk space:

```bash
# Kiểm tra tổng quan
df -h

# Kiểm tra thư mục lớn nhất
du -sh /* | sort -rh | head -10

# Kiểm tra Docker sử dụng bao nhiêu
docker system df -v
```

## 🚀 Sau khi cleanup:

```bash
cd ~/LocalAIChatBox

# Pull code mới nhất
git pull origin main

# Rebuild với --no-cache
docker-compose build --no-cache backend

# Start lại
docker-compose up -d

# Kiểm tra logs
docker-compose logs backend --tail=50
```

## 💡 Tips để tránh lỗi này trong tương lai:

### 1. Cleanup định kỳ (Hàng tuần)

```bash
# Thêm vào crontab để tự động chạy mỗi tuần
0 2 * * 0 docker system prune -a -f
```

### 2. Giới hạn Docker log size

Tạo file `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:
```bash
sudo systemctl restart docker
```

### 3. Monitor disk space

```bash
# Thêm vào crontab để nhận cảnh báo khi disk > 80%
0 */6 * * * df -h | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{ print $5 " " $1 }' | while read output; do usage=$(echo $output | awk '{print $1}' | sed 's/%//g'); if [ $usage -ge 80 ]; then echo "WARNING: Disk usage $usage% on $(echo $output | awk '{print $2}')"; fi; done
```

## 🔍 Debug: Tìm file/folder lớn nhất

```bash
# Top 20 thư mục lớn nhất
du -ah / 2>/dev/null | sort -rh | head -20

# Kiểm tra /var/log
du -sh /var/log/*

# Kiểm tra /var/lib/docker
du -sh /var/lib/docker/*

# Tìm file lớn hơn 100MB
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -rh | head -20
```

## ⚠️ Cảnh báo:

### KHÔNG XÓA:
- ❌ `/var/lib/docker/volumes/` - Chứa database và data quan trọng
- ❌ `~/LocalAIChatBox/data/` - Document uploads và vector store

### CÓ THỂ XÓA:
- ✅ Docker build cache
- ✅ Stopped containers
- ✅ Unused images
- ✅ Dangling images
- ✅ `/var/log/` old logs
- ✅ `/tmp/` temporary files

## 📈 Expected disk usage sau cleanup:

| Item | Before | After |
|------|--------|-------|
| **Docker Images** | 5-10 GB | 1-2 GB |
| **Build Cache** | 2-5 GB | 0 GB |
| **Containers** | 500 MB | 100 MB |
| **Total freed** | - | 7-15 GB |

## 🎯 Minimum disk requirements:

- **Backend build**: ~3 GB
- **All images**: ~2 GB
- **Runtime**: ~500 MB
- **Recommended free**: **>5 GB**

## 🆘 Nếu vẫn gặp lỗi:

### 1. Nâng cấp VPS storage
Contact VPS provider để tăng disk space

### 2. Sử dụng external volume
Mount external storage cho Docker

### 3. Tối ưu dependencies
Xem xét bỏ dependencies không cần thiết

### 4. Multi-stage build optimization
Dockerfile đã dùng multi-stage build (optimal)

## 📞 Quick Commands:

```bash
# Check disk space
df -h

# Docker space
docker system df

# Full cleanup
docker system prune -a -f --volumes

# Rebuild
cd ~/LocalAIChatBox
docker-compose build --no-cache backend
docker-compose up -d
```

---

**TL;DR**: Chạy `bash cleanup_docker.sh` để tự động dọn dẹp và giải phóng 5-15 GB disk space!
