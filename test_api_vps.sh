#!/bin/bash
# Quick API Test Script for VPS
# Run this on your VPS to test API endpoints

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:8001/api"  # Internal Docker network
NGINX_URL="http://localhost:81/api"  # Through Nginx

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  LocalAIChatBox API Quick Test${NC}"
echo -e "${BLUE}========================================${NC}"

# Test 1: Health Check (Direct Backend)
echo -e "\n${YELLOW}[1/6] Testing Backend Health (Direct)...${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8001/api/health)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✓ Backend Health Check: PASS${NC}"
    echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
else
    echo -e "${RED}✗ Backend Health Check: FAIL (HTTP $HTTP_CODE)${NC}"
    echo "$RESPONSE_BODY"
fi

# Test 2: Health Check (Through Nginx)
echo -e "\n${YELLOW}[2/6] Testing API through Nginx...${NC}"
NGINX_RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:81/api/health)
HTTP_CODE=$(echo "$NGINX_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$NGINX_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✓ Nginx Proxy: PASS${NC}"
    echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
else
    echo -e "${RED}✗ Nginx Proxy: FAIL (HTTP $HTTP_CODE)${NC}"
    echo "$RESPONSE_BODY"
fi

# Test 3: Database Connection Test
echo -e "\n${YELLOW}[3/6] Testing Database Connection...${NC}"
DB_TEST=$(docker exec ragchat-postgres psql -U raguser -d ragdb -c "SELECT 1" 2>&1)
if echo "$DB_TEST" | grep -q "1 row"; then
    echo -e "${GREEN}✓ Database Connection: PASS${NC}"
else
    echo -e "${RED}✗ Database Connection: FAIL${NC}"
    echo "$DB_TEST"
fi

# Test 4: Admin Login
echo -e "\n${YELLOW}[4/6] Testing Admin Login...${NC}"
LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')
HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$LOGIN_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✓ Admin Login: PASS${NC}"
    TOKEN=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
    echo "Token: ${TOKEN:0:50}..."
else
    echo -e "${RED}✗ Admin Login: FAIL (HTTP $HTTP_CODE)${NC}"
    echo "$RESPONSE_BODY"
    TOKEN=""
fi

# Test 5: Get Current User (if login successful)
if [ -n "$TOKEN" ]; then
    echo -e "\n${YELLOW}[5/6] Testing Get Current User...${NC}"
    ME_RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8001/api/auth/me \
      -H "Authorization: Bearer $TOKEN")
    HTTP_CODE=$(echo "$ME_RESPONSE" | tail -n1)
    RESPONSE_BODY=$(echo "$ME_RESPONSE" | head -n-1)
    
    if [ "$HTTP_CODE" == "200" ]; then
        echo -e "${GREEN}✓ Get Current User: PASS${NC}"
        echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
    else
        echo -e "${RED}✗ Get Current User: FAIL (HTTP $HTTP_CODE)${NC}"
        echo "$RESPONSE_BODY"
    fi
else
    echo -e "\n${YELLOW}[5/6] Skipping Get Current User (no token)${NC}"
fi

# Test 6: Test User Registration
echo -e "\n${YELLOW}[6/6] Testing User Registration...${NC}"
TIMESTAMP=$(date +%s)
REG_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"testuser$TIMESTAMP\",\"email\":\"test$TIMESTAMP@example.com\",\"full_name\":\"Test User\",\"password\":\"test123\"}")
HTTP_CODE=$(echo "$REG_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$REG_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✓ User Registration: PASS${NC}"
    echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null | head -n 10
else
    echo -e "${RED}✗ User Registration: FAIL (HTTP $HTTP_CODE)${NC}"
    echo "$RESPONSE_BODY"
fi

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Complete${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}If any tests failed, check:${NC}"
echo "1. Backend logs:    docker-compose logs backend --tail=50"
echo "2. Database logs:   docker-compose logs postgres --tail=30"
echo "3. Nginx logs:      docker-compose logs nginx --tail=30"
echo "4. Container status: docker-compose ps"
echo ""
echo -e "${YELLOW}To restart services:${NC}"
echo "docker-compose restart backend"
echo "docker-compose restart nginx"
