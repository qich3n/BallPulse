# Multi-stage Dockerfile for BallPulse

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# System deps (for building some Python packages and basic tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ===== Builder stage =====
FROM base AS builder

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip wheel --wheel-dir=/wheels -r requirements.txt

# ===== Runtime stage =====
FROM base AS runtime

# Create non-root user
RUN useradd -m appuser

# Copy wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --upgrade pip && \
    pip install --no-index --find-links=/wheels /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY src ./src
COPY static ./static
COPY clear_cache.py ./clear_cache.py
COPY pytest.ini ./pytest.ini

# Environment
ENV LOG_LEVEL=INFO \
    PORT=8000

EXPOSE 8000

USER appuser

# Default command: run Uvicorn
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
