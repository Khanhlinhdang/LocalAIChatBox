# ==================== BUILDER STAGE ====================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY backend/requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir --prefix=/build/python-deps -r requirements.txt

# Copy and install local-deep-research
COPY local-deep-research /build/local-deep-research
RUN pip install --no-cache-dir --prefix=/build/python-deps -e /build/local-deep-research

# Pre-download sentence-transformers model to install location
ENV SENTENCE_TRANSFORMERS_HOME=/build/models
RUN python -c "import sys; sys.path.insert(0, '/build/python-deps/lib/python3.11/site-packages'); from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || true

# ==================== RUNTIME STAGE ====================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /build/python-deps /usr/local
COPY --from=builder /build/local-deep-research /app/local-deep-research

# Create non-root user early for proper permissions
RUN useradd -m -u 1000 -s /bin/bash appuser

# Copy sentence-transformers models to user cache directory
COPY --from=builder --chown=appuser:appuser /build/models /home/appuser/.cache/torch/sentence_transformers

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=UTF-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy backend application code
COPY backend/app /app/app

# Create data directories with proper permissions
RUN mkdir -p /app/data/documents /app/data/vector_store && \
    chmod -R 755 /app/data && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
