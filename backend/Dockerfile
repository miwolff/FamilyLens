FROM python:3.13-slim

# Build argument for model selection
ARG CLIP_MODEL_NAME=clip-ViT-B-32

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/app/.cache

WORKDIR /app

# Install exactly the versions pinned in uv.lock (CPU-only PyTorch on Linux).
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

# Download the CLIP model at build time so container startup is fast and
# no network access is needed at runtime.
COPY scripts/ scripts/
RUN FAMILYLENS_CLIP_MODEL_NAME=$CLIP_MODEL_NAME \
    python -m scripts.download_models

# The model is baked into the image; never contact the Hugging Face Hub at
# runtime (local-first: no network calls beyond Qdrant).
ENV HF_HUB_OFFLINE=1

COPY app/ app/

# Run as non-root user
RUN adduser --system --no-create-home appuser && \
    chown -R appuser /app/.cache
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
