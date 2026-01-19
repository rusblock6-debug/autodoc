# AutoDoc AI System - Production Dockerfile
# ===========================================

# Stage 1: Builder with GPU support
FROM nvidia/cuda:12.2-devel-ubuntu22.04 AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3-venv \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3.10 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# CRITICAL: Install llama-cpp-python с CUDA поддержкой для GPU
# Без этого библиотека установится как CPU-only и будет работать медленно!
RUN CMAKE_ARGS="-DLLAMA_CUBLAS=ON" pip install --no-cache-dir --force-reinstall llama-cpp-python

# Install Whisper model dependencies
RUN pip install --no-cache-dir openai-whisper

# Stage 2: Production image
FROM nvidia/cuda:12.2-runtime-ubuntu22.04 AS production

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN groupadd -r autodoc && useradd -r -g autodoc autodoc
RUN mkdir -p /workspace/autodoc_ai && chown -R autodoc:autodoc /workspace/autodoc_ai
WORKDIR /workspace/autodoc_ai

# Copy application code
COPY --chown=autodoc:autodoc . .

# Switch to non-root user
USER autodoc

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NVIDIA_VISIBLE_DEVICES=all

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Development Dockerfile
FROM python:3.10-slim AS development

WORKDIR /workspace/autodoc_ai

# Install system dependencies (FFmpeg and libraries for OpenCV/video processing + weasyprint)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libfontconfig1 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install development dependencies
RUN pip install --no-cache-dir pytest-asyncio black isort mypy

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
