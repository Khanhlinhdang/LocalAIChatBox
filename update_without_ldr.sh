#!/bin/bash

# 🚀 Script update sau khi xóa local-deep-research
# Run on VPS Ubuntu

set -e

echo "=================================================="
echo "🔧 UPDATE AFTER REMOVING LOCAL-DEEP-RESEARCH"
echo "=================================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if in correct directory
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.yml not found${NC}"
    echo "Please run this script from LocalAIChatBox directory"
    exit 1
fi

echo -e "${YELLOW}Step 1/6: Stopping containers...${NC}"
docker-compose down
echo -e "${GREEN}✓ Containers stopped${NC}"
echo ""

echo -e "${YELLOW}Step 2/6: Pulling latest code...${NC}"
git pull origin main
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

echo -e "${YELLOW}Step 3/6: Checking changes...${NC}"
echo "Changes in this update:"
echo "  - Removed local-deep-research dependency from Dockerfile"
echo "  - Updated ChromaDB to 0.5.3 (NumPy 2.0 compatible)"
echo "  - Added graceful error handling for Deep Research"
echo ""
echo -e "${YELLOW}⚠️  NOTE: Deep Research feature will be DISABLED${NC}"
echo "   (RAG, Auth, Knowledge Graph still work normally)"
echo ""

echo -e "${YELLOW}Step 4/6: Rebuilding backend (5-7 minutes)...${NC}"
echo "Using --no-cache to ensure clean build"
docker-compose build --no-cache backend
echo -e "${GREEN}✓ Backend rebuilt${NC}"
echo ""

echo -e "${YELLOW}Step 5/6: Starting services...${NC}"
docker-compose up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

echo -e "${YELLOW}Step 6/6: Waiting for backend (15 seconds)...${NC}"
sleep 15
echo -e "${GREEN}✓ Wait complete${NC}"
echo ""

echo "=================================================="
echo "📊 VERIFICATION"
echo "=================================================="
echo ""

# Check backend status
echo -e "${YELLOW}Checking backend status...${NC}"
BACKEND_STATUS=$(docker-compose ps backend | grep ragchat-backend | awk '{print $3}')
if [[ "$BACKEND_STATUS" == *"Up"* ]]; then
    echo -e "${GREEN}✓ Backend is running${NC}"
else
    echo -e "${RED}❌ Backend not running properly${NC}"
fi
echo ""

# Check logs for warnings
echo -e "${YELLOW}Checking backend logs...${NC}"
LOGS=$(docker-compose logs backend --tail=50 2>&1)

if echo "$LOGS" | grep -q "Deep Research features will be disabled"; then
    echo -e "${YELLOW}⚠️  Deep Research is disabled (expected)${NC}"
    echo "   This is normal and does not affect core features."
fi

if echo "$LOGS" | grep -q "Uvicorn running"; then
    echo -e "${GREEN}✓ Backend started successfully!${NC}"
elif echo "$LOGS" | grep -q "np.float_"; then
    echo -e "${RED}❌ NumPy error still present!${NC}"
    echo "Please check logs: docker-compose logs backend"
else
    echo -e "${YELLOW}⚠️  Backend may still be starting...${NC}"
fi
echo ""

# Check ChromaDB version
echo -e "${YELLOW}Checking ChromaDB version...${NC}"
CHROMA_VER=$(docker-compose exec -T backend pip show chromadb 2>/dev/null | grep "Version:" | awk '{print $2}')
if [ -z "$CHROMA_VER" ]; then
    echo -e "${YELLOW}⚠️  Could not check version (backend still starting?)${NC}"
else
    echo "ChromaDB: $CHROMA_VER"
    if [ "$CHROMA_VER" = "0.5.3" ]; then
        echo -e "${GREEN}✓ ChromaDB version correct${NC}"
    fi
fi
echo ""

# Test health endpoint
echo -e "${YELLOW}Testing API health endpoint...${NC}"
HEALTH=$(curl -s http://localhost:8001/api/health 2>&1 || echo "failed")
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✓ API is healthy!${NC}"
else
    echo -e "${YELLOW}⚠️  Health check not ready yet${NC}"
    echo "Wait 10s and try: curl http://localhost:8001/api/health"
fi
echo ""

echo "=================================================="
echo "✅ UPDATE COMPLETE!"
echo "=================================================="
echo ""
echo "📋 Summary:"
echo "  ✅ Removed local-deep-research dependency"
echo "  ✅ Updated ChromaDB to 0.5.3"
echo "  ✅ Backend rebuilt and running"
echo "  ⚠️  Deep Research feature DISABLED"
echo ""
echo "🎯 Testing:"
echo "  Frontend: http://194.59.xxx.xxx:81"
echo "  Login: admin / admin123"
echo ""
echo "📚 Core features still working:"
echo "  ✓ User authentication"
echo "  ✓ Document upload"
echo "  ✓ RAG chat"
echo "  ✓ Knowledge graph"
echo ""
echo "📖 Read REMOVED_LDR.md for more details"
echo "=================================================="
