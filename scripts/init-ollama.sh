#!/bin/bash
# Ollama model initialization script
# Waits for Ollama to be ready, then pulls required models

set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODELS="${OLLAMA_MODELS:-llama3.1 llava}"

echo "=== Ollama Model Initializer ==="
echo "Host: $OLLAMA_HOST"
echo "Models: $MODELS"

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
MAX_RETRIES=60
RETRY=0
until curl -sf "$OLLAMA_HOST/" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "ERROR: Ollama not ready after ${MAX_RETRIES} attempts"
        exit 1
    fi
    echo "  Attempt $RETRY/$MAX_RETRIES - waiting 5s..."
    sleep 5
done
echo "Ollama is ready!"

# Pull each model
for MODEL in $MODELS; do
    echo ""
    echo "--- Checking model: $MODEL ---"
    
    # Check if model already exists
    if curl -sf "$OLLAMA_HOST/api/tags" 2>/dev/null | grep -q "\"$MODEL"; then
        echo "Model $MODEL already exists, skipping."
    else
        echo "Pulling model: $MODEL (this may take several minutes)..."
        curl -sf "$OLLAMA_HOST/api/pull" -d "{\"name\": \"$MODEL\", \"stream\": false}" \
            --max-time 3600 || {
            echo "WARNING: Failed to pull $MODEL, retrying..."
            sleep 5
            curl -sf "$OLLAMA_HOST/api/pull" -d "{\"name\": \"$MODEL\", \"stream\": false}" \
                --max-time 3600 || echo "ERROR: Could not pull $MODEL"
        }
        echo "Model $MODEL pulled successfully!"
    fi
done

echo ""
echo "=== All models ready ==="
curl -sf "$OLLAMA_HOST/api/tags" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for m in data.get('models', []):
        size_gb = m.get('size', 0) / (1024**3)
        print(f\"  - {m['name']} ({size_gb:.1f} GB)\")
except: pass
" 2>/dev/null || true

echo ""
echo "=== Init complete! ==="
