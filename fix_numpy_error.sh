#!/bin/bash

# 🚀 Script tự động fix NumPy & Bcrypt compatibility errors trên VPS
# Chạy script này trên VPS Ubuntu

set -e  # Exit on error

echo "=================================================="
echo "🔧 FIX NUMPY & BCRYPT COMPATIBILITY ERRORS"
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
    echo "Example: cd ~/LocalAIChatBox && bash fix_numpy_error.sh"
    exit 1
fi

echo -e "${YELLOW}Step 1/6: Stopping containers...${NC}"
docker-compose down
echo -e "${GREEN}✓ Containers stopped${NC}"
echo ""

echo -e "${YELLOW}Step 2/6: Pulling latest code from GitHub...${NC}"
git pull origin main
echo -e "${GREEN}✓ Code updated${NC}"
echo ""

echo -e "${YELLOW}Step 3/6: Checking requirements.txt...${NC}"
CHROMADB_VERSION=$(grep "chromadb==" backend/requirements.txt | cut -d'=' -f3)
echo "ChromaDB version in requirements.txt: $CHROMADB_VERSION"

if [ "$CHROMADB_VERSION" != "0.5.3" ]; then
    echo -e "${RED}⚠️  Warning: ChromaDB version is not 0.5.3${NC}"
    echo "Expected: chromadb==0.5.3"
    echo "Found: chromadb==$CHROMADB_VERSION"
    echo ""
fi
echo ""

echo -e "${YELLOW}Step 4/6: Rebuilding backend (This will take 5-7 minutes)...${NC}"
echo "Using --no-cache to remove old ChromaDB 0.4.22 layers"
docker-compose build --no-cache backend
echo -e "${GREEN}✓ Backend rebuilt successfully${NC}"
echo ""

echo -e "${YELLOW}Step 5/6: Starting all services...${NC}"
docker-compose up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

echo -e "${YELLOW}Step 6/6: Waiting for backend to start (15 seconds)...${NC}"
sleep 15
echo -e "${GREEN}✓ Wait complete${NC}"
echo ""

echo "=================================================="
echo "📊 VERIFICATION"
echo "=================================================="
echo ""

# Check backend status
echo -e "${YELLOW}Checking backend container status...${NC}"
BACKEND_STATUS=$(docker-compose ps backend | grep ragchat-backend | awk '{print $3}')
if [[ "$BACKEND_STATUS" == *"Up"* ]]; then
    echo -e "${GREEN}✓ Backend is running${NC}"
else
    echo -e "${RED}❌ Backend is not running properly${NC}"
    echo "Status: $BACKEND_STATUS"
fi
echo ""

# Check ChromaDB version inside container
echo -e "${YELLOW}Checking ChromaDB version in container...${NC}"
CHROMA_VERSION=$(docker-compose exec -T backend pip show chromadb 2>/dev/null | grep "Version:" | awk '{print $2}')
if [ -z "$CHROMA_VERSION" ]; then
    echo -e "${RED}❌ Could not get ChromaDB version${NC}"
else
    echo "ChromaDB version: $CHROMA_VERSION"
    if [ "$CHROMA_VERSION" = "0.4.22" ]; then
        echo -e "${GREEN}✓ ChromaDB version is correct (0.4.22)${NC}"
    else
        echo -e "${YELLOW}⚠️  ChromaDB version is $CHROMA_VERSION (expected 0.4.22)${NC}"
    fi
fi
echo ""

# Check NumPy version
echo -e "${YELLOW}Checking NumPy version in container...${NC}"
NUMPY_VERSION=$(docker-compose exec -T backend pip show numpy 2>/dev/null | grep "Version:" | awk '{print $2}')
if [ -z "$NUMPY_VERSION" ]; then
    echo -e "${RED}❌ Could not get NumPy version${NC}"
else
    echo "NumPy version: $NUMPY_VERSION"
    if [[ "$NUMPY_VERSION" == 1.* ]]; then
        echo -e "${GREEN}✓ NumPy version is 1.x (compatible)${NC}"
    else
        echo -e "${YELLOW}⚠️  NumPy version is $NUMPY_VERSION${NC}"
    fi
fi
echo ""

# Check bcrypt version
echo -e "${YELLOW}Checking bcrypt version in container...${NC}"
BCRYPT_VERSION=$(docker-compose exec -T backend pip show bcrypt 2>/dev/null | grep "Version:" | awk '{print $2}')
if [ -z "$BCRYPT_VERSION" ]; then
    echo -e "${RED}❌ Could not get bcrypt version${NC}"
else
    echo "bcrypt version: $BCRYPT_VERSION"
    if [ "$BCRYPT_VERSION" = "3.2.2" ]; then
        echo -e "${GREEN}✓ bcrypt version is correct (3.2.2)${NC}"
    elif [[ "$BCRYPT_VERSION" == 3.* ]]; then
        echo -e "${GREEN}✓ bcrypt version is 3.x (compatible)${NC}"
    else
        echo -e "${YELLOW}⚠️  bcrypt version is $BCRYPT_VERSION (may have issues)${NC}"
    fi
fi
echo ""

# Check backend logs for errors
echo -e "${YELLOW}Checking backend logs for errors...${NC}"
LOGS=$(docker-compose logs backend --tail=30 2>&1)

if echo "$LOGS" | grep -q "np.float_"; then
    echo -e "${RED}❌ NumPy error still present in logs!${NC}"
    echo "Please check logs manually: docker-compose logs backend"
elif echo "$LOGS" | grep -q "__about__"; then
    echo -e "${RED}❌ bcrypt compatibility error still present!${NC}"
    echo "Please check logs manually: docker-compose logs backend"
elif echo "$LOGS" | grep -q "Uvicorn running"; then
    echo -e "${GREEN}✓ Backend started successfully!${NC}"
else
    echo -e "${YELLOW}⚠️  Backend may still be starting...${NC}"
    echo "Check logs manually: docker-compose logs backend -f"
fi

if echo "$LOGS" | grep -q "ERROR"; then
    echo -e "${RED}⚠️  Errors detected in logs${NC}"
    echo "Run: docker-compose logs backend --tail=50"
fi
echo ""

echo "=================================================="
echo "🎯 TESTING"
echo "=================================================="
echo ""

# Test health endpoint
echo -e "${YELLOW}Testing health endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8001/api/health 2>&1 || echo "connection_failed")

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health check passed!${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
    echo ""
    echo "Backend may still be starting. Wait 10 more seconds and try:"
    echo "  curl http://localhost:8001/api/health"
fi
echo ""

echo "=================================================="
echo "✅ FIX COMPLETE!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Test frontend: http://194.59.165.202:81"
echo "2. Login with: admin / admin123"
echo "3. Upload documents and test RAG functionality"
echo ""
echo "View logs: docker-compose logs backend -f"
echo "Check status: docker-compose ps"
echo ""
echo "If you still encounter errors, read:"
echo "  - QUICK_FIX.md"
echo "  - FIX_NUMPY_ERROR_EXPLAINED.md"
echo "=================================================="
