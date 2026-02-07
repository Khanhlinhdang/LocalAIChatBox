#!/bin/bash
# Backend entrypoint - waits for dependencies, init data dirs, then starts server
set -e

echo "=== LocalAIChatBox Backend Startup ==="

# ---- 1. Ensure data directories exist with correct permissions ----
echo "[1/4] Checking data directories..."
for dir in /app/data/vector_store /app/data/documents /app/data/parser_output; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "  Created: $dir"
    fi
done

# ---- 2. Wait for PostgreSQL ----
echo "[2/4] Waiting for PostgreSQL..."
MAX_RETRIES=30
RETRY=0
until python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
conn.close()
print('  PostgreSQL ready!')
" 2>/dev/null; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "  ERROR: PostgreSQL not ready after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "  Attempt $RETRY/$MAX_RETRIES..."
    sleep 2
done

# ---- 3. Wait for Ollama ----
echo "[3/4] Waiting for Ollama..."
OLLAMA_HOST="${OLLAMA_HOST:-http://ollama:11434}"
RETRY=0
until curl -sf "$OLLAMA_HOST/" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "  WARNING: Ollama not reachable (non-fatal, continuing)"
        break
    fi
    echo "  Attempt $RETRY/$MAX_RETRIES..."
    sleep 3
done

# Check if required models are available
REQUIRED_MODEL="${OLLAMA_LLM_MODEL:-llama3.1}"
echo "  Checking for model: $REQUIRED_MODEL"
MODEL_READY=false
for i in $(seq 1 120); do
    if curl -sf "$OLLAMA_HOST/api/tags" 2>/dev/null | grep -q "$REQUIRED_MODEL"; then
        echo "  Model $REQUIRED_MODEL is available!"
        MODEL_READY=true
        break
    fi
    if [ $((i % 10)) -eq 0 ]; then
        echo "  Waiting for model $REQUIRED_MODEL... (${i}s)"
    fi
    sleep 5
done

if [ "$MODEL_READY" = false ]; then
    echo "  WARNING: Model $REQUIRED_MODEL not found yet (backend will retry on first request)"
fi

# ---- 4. Start the server ----
echo "[4/4] Starting FastAPI server..."
echo ""
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
