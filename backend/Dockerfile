FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for Pillow
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev libpng-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install PyTorch CPU-only first, then remaining deps
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
