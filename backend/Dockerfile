# Dockerfile — Task Manager FastAPI Backend
# ─────────────────────────────────────────────────────────────────────────────
# Pinned to Python 3.11-slim to avoid pydantic-core Rust compile failure
# that occurs on Python 3.14 (current Render default as of 2026).
#
# Build:   docker build -t task-manager-api .
# Run:     docker run -p 8000:8000 -e DATABASE_URL=postgresql://... task-manager-api
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

LABEL description="Task Manager FastAPI backend" version="2.0.0"

# System dependencies
# libpq-dev → required by psycopg2-binary at runtime
# curl      → used by the HEALTHCHECK below
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer — only invalidated when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Run as non-root user for security
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser

# Default environment (override at runtime)
ENV LOG_LEVEL=INFO
ENV ALLOWED_ORIGINS=*
# DATABASE_URL must be supplied at runtime — not hardcoded here

EXPOSE 8000
EXPOSE 10000

# Health check — hits the lightweight / endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/ || exit 1

# PORT env var lets the same image run locally (8000) and on Render (10000)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
