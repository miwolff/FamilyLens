FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev libpng-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

# Install PyTorch CPU-only first, then remaining deps
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir .

COPY app/ app/

# Run as non-root user
RUN adduser --system --no-create-home appuser && \
    mkdir -p /app/.cache && \
    chown appuser /app/.cache
USER appuser

# Set model cache directory to app-writable location
ENV TRANSFORMERS_CACHE=/app/.cache
ENV HF_HOME=/app/.cache

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
