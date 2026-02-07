#!/bin/bash
###############################################################################
#  LocalAIChatBox - Fully Automated Setup Script
#  Run on a fresh Ubuntu 22.04+ / Debian 12+ server:
#    chmod +x setup.sh && ./setup.sh
#
#  This script will:
#  1. Install all system dependencies (Docker, Docker Compose, Git)
#  2. Create required directories
#  3. Generate a secure SECRET_KEY
#  4. Build and start all Docker containers
#  5. Download Ollama LLM models
#  6. Display access information
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
  echo -e "${BLUE}[$1/$TOTAL_STEPS]${NC} $2"
}

print_ok() {
  echo -e "  ${GREEN}OK${NC} $1"
}

print_warn() {
  echo -e "  ${YELLOW}WARNING${NC} $1"
}

# Detect total steps
TOTAL_STEPS=9

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}  LocalAIChatBox - Automated Server Setup${NC}"
echo -e "${GREEN}  RAG Chat + Deep Research System${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""

# ==================== Step 1: System Update ====================
print_step 1 "Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
sudo apt-get install -y -qq curl wget git ca-certificates gnupg lsb-release
print_ok "System updated"

# ==================== Step 2: Install Docker ====================
print_step 2 "Installing Docker..."
if command -v docker &> /dev/null; then
  print_ok "Docker already installed ($(docker --version))"
else
  # Install Docker using official script
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  rm /tmp/get-docker.sh

  # Add current user to docker group
  sudo usermod -aG docker "$USER"
  print_ok "Docker installed"
fi

# Ensure Docker is running
sudo systemctl enable docker 2>/dev/null || true
sudo systemctl start docker 2>/dev/null || true

# ==================== Step 3: Install Docker Compose ====================
print_step 3 "Installing Docker Compose..."
if command -v docker-compose &> /dev/null; then
  print_ok "Docker Compose already installed"
elif docker compose version &> /dev/null; then
  print_ok "Docker Compose plugin already available"
  # Create alias for docker-compose
  if ! command -v docker-compose &> /dev/null; then
    sudo ln -sf "$(which docker)" /usr/local/bin/docker-compose-redirect 2>/dev/null || true
  fi
else
  # Install Docker Compose plugin
  sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || \
    sudo apt-get install -y -qq docker-compose 2>/dev/null || {
      # Manual install as fallback
      COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -oP '"tag_name": "\K(.*)(?=")')
      sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
      sudo chmod +x /usr/local/bin/docker-compose
    }
  print_ok "Docker Compose installed"
fi

# Determine which compose command to use
if command -v docker-compose &> /dev/null; then
  COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
  COMPOSE_CMD="docker compose"
else
  echo -e "${RED}ERROR: Docker Compose not found. Please install it manually.${NC}"
  exit 1
fi

print_ok "Using compose command: $COMPOSE_CMD"

# ==================== Step 4: Create Directories ====================
print_step 4 "Creating project directories..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p data/documents
mkdir -p data/vector_store
mkdir -p data/database
mkdir -p searxng

# Ensure SearXNG settings exist
if [ ! -f "searxng/settings.yml" ]; then
  cat > searxng/settings.yml << 'SEARXNG_EOF'
use_default_settings: true

general:
  instance_name: "LocalAIChatBox Search"

server:
  bind_address: "0.0.0.0"
  secret_key: "change-this-to-a-random-string"
  image_proxy: false

search:
  safe_search: 0
  autocomplete: ""

ui:
  static_use_hash: true

engines:
  - name: duckduckgo
    engine: duckduckgo
    shortcut: ddg
    disabled: false

  - name: wikipedia
    engine: wikipedia
    shortcut: wp
    disabled: false

  - name: google
    engine: google
    shortcut: g
    disabled: false

limiter: false
SEARXNG_EOF
  print_ok "SearXNG configuration created"
fi

print_ok "Directories created"

# ==================== Step 5: Generate Secure SECRET_KEY ====================
print_step 5 "Configuring security..."
ENV_FILE="$SCRIPT_DIR/backend/.env"

if [ -f "$ENV_FILE" ]; then
  # Generate a random SECRET_KEY and replace the default one
  NEW_SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 64)

  if grep -q "your-super-secret-key-change-this-in-production" "$ENV_FILE"; then
    sed -i "s/your-super-secret-key-change-this-in-production/$NEW_SECRET/" "$ENV_FILE"
    print_ok "Generated secure SECRET_KEY"
  else
    print_ok "SECRET_KEY already customized"
  fi
else
  print_warn "backend/.env not found, skipping SECRET_KEY generation"
fi

# ==================== Step 6: Build and Start Containers ====================
print_step 6 "Building and starting Docker containers (this may take several minutes)..."

# Use sudo if user is not in docker group yet (first run)
if groups "$USER" | grep -q docker; then
  $COMPOSE_CMD up -d --build
else
  sudo $COMPOSE_CMD up -d --build
fi

print_ok "All containers started"

# ==================== Step 7: Wait and Download Models ====================
print_step 7 "Downloading AI models (this may take 10-30 minutes depending on internet speed)..."

echo "  Waiting for Ollama container to be ready..."
OLLAMA_READY=false
for i in $(seq 1 60); do
  if sudo docker exec ragchat-ollama ollama list &>/dev/null; then
    OLLAMA_READY=true
    break
  fi
  sleep 2
done

if [ "$OLLAMA_READY" = true ]; then
  echo "  Downloading llama3.1 (main LLM model)..."
  sudo docker exec ragchat-ollama ollama pull llama3.1

  print_ok "AI models downloaded"
else
  print_warn "Ollama not ready. Download models manually later with:"
  echo "    docker exec -it ragchat-ollama ollama pull llama3.1"
fi

# ==================== Step 8: Verify SearXNG ====================
print_step 8 "Verifying SearXNG search engine..."

SEARXNG_HEALTHY=false
for i in $(seq 1 15); do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null | grep -qE "200|302" 2>/dev/null; then
    SEARXNG_HEALTHY=true
    break
  fi
  sleep 2
done

if [ "$SEARXNG_HEALTHY" = true ]; then
  print_ok "SearXNG search engine is running"
else
  print_warn "SearXNG not responding yet - it may still be starting up"
fi

# ==================== Step 9: Verify Services ====================
print_step 9 "Verifying services..."

echo "  Waiting for backend to initialize..."
sleep 10

# Check backend health
BACKEND_HEALTHY=false
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/api/health | grep -q "healthy" 2>/dev/null; then
    BACKEND_HEALTHY=true
    break
  fi
  sleep 2
done

if [ "$BACKEND_HEALTHY" = true ]; then
  print_ok "Backend API is healthy"
else
  print_warn "Backend not responding yet - it may still be starting up"
fi

# Check frontend
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200" 2>/dev/null; then
  print_ok "Frontend is running"
fi

# Check nginx
if curl -s -o /dev/null -w "%{http_code}" http://localhost 2>/dev/null | grep -qE "200|301|302" 2>/dev/null; then
  print_ok "Nginx reverse proxy is running"
fi

# ==================== Complete ====================
SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_SERVER_IP")

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "  ${BLUE}Web UI:${NC}        http://${SERVER_IP}"
echo -e "  ${BLUE}API Docs:${NC}      http://${SERVER_IP}/docs"
echo -e "  ${BLUE}SearXNG:${NC}       http://${SERVER_IP}:8080"
echo -e "  ${BLUE}Default Login:${NC} admin / admin123"
echo ""
echo -e "  ${YELLOW}Features:${NC}"
echo "    - Multi-user RAG Chat with Knowledge Graph"
echo "    - Deep Research with iterative AI search"
echo "    - Automated report generation"
echo "    - Document upload (PDF, DOCX, TXT, MD)"
echo "    - Automatic entity & relationship extraction"
echo "    - Knowledge Graph explorer"
echo "    - SearXNG meta-search engine"
echo "    - Offline embeddings (sentence-transformers)"
echo "    - Admin dashboard & system settings"
echo ""
echo -e "  ${YELLOW}LAN Access:${NC}"
echo "    Other computers can access at: http://${SERVER_IP}"
echo ""
echo -e "  ${RED}IMPORTANT:${NC} Change the admin password after first login!"
echo ""
echo -e "  ${BLUE}Useful Commands:${NC}"
echo "    $COMPOSE_CMD logs -f        # View logs"
echo "    $COMPOSE_CMD restart        # Restart services"
echo "    $COMPOSE_CMD down           # Stop services"
echo "    $COMPOSE_CMD down -v        # Stop and delete all data"
echo -e "${GREEN}=================================================${NC}"
