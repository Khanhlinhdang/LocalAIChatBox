#!/bin/bash

# 🧹 Script dọn dẹp Docker khi gặp lỗi "No space left on device"
# Run on VPS Ubuntu

echo "=================================================="
echo "🧹 DOCKER CLEANUP - FIX DISK SPACE ERROR"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 Step 1: Check disk space BEFORE cleanup${NC}"
echo ""
df -h
echo ""

echo -e "${YELLOW}⚠️  WARNING: This will remove:${NC}"
echo "  - All stopped containers"
echo "  - All unused networks"
echo "  - All dangling images"
echo "  - All build cache"
echo ""
echo -e "${YELLOW}Docker volumes will NOT be deleted (your data is safe)${NC}"
echo ""

read -p "Continue? (y/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

echo ""
echo -e "${YELLOW}Step 2: Stop all running containers...${NC}"
docker-compose down
echo -e "${GREEN}✓ Containers stopped${NC}"
echo ""

echo -e "${YELLOW}Step 3: Remove stopped containers...${NC}"
REMOVED_CONTAINERS=$(docker container prune -f)
echo "$REMOVED_CONTAINERS"
echo -e "${GREEN}✓ Stopped containers removed${NC}"
echo ""

echo -e "${YELLOW}Step 4: Remove unused images...${NC}"
REMOVED_IMAGES=$(docker image prune -a -f)
echo "$REMOVED_IMAGES"
echo -e "${GREEN}✓ Unused images removed${NC}"
echo ""

echo -e "${YELLOW}Step 5: Remove build cache...${NC}"
REMOVED_CACHE=$(docker builder prune -a -f)
echo "$REMOVED_CACHE"
echo -e "${GREEN}✓ Build cache removed${NC}"
echo ""

echo -e "${YELLOW}Step 6: Remove unused networks...${NC}"
REMOVED_NETWORKS=$(docker network prune -f)
echo "$REMOVED_NETWORKS"
echo -e "${GREEN}✓ Unused networks removed${NC}"
echo ""

echo -e "${BLUE}📊 Step 7: Check disk space AFTER cleanup${NC}"
echo ""
df -h
echo ""

echo "=================================================="
echo -e "${GREEN}✅ CLEANUP COMPLETE!${NC}"
echo "=================================================="
echo ""

# Calculate freed space (approximate)
echo -e "${BLUE}📈 Summary:${NC}"
docker system df
echo ""

echo -e "${YELLOW}Now you can rebuild:${NC}"
echo "  docker-compose build --no-cache backend"
echo "  docker-compose up -d"
echo ""
echo "=================================================="
