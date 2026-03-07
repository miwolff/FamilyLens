# FamilyLens

Local-first intelligent photo search — query your personal photo library using natural language.

## Architecture

Three Docker containers orchestrated via Docker Compose:

| Service | Tech | Purpose |
|---------|------|---------|
| **qdrant** | Qdrant v1.13.2 | Vector database for image embeddings |
| **api** | FastAPI + CLIP ViT-B/32 | Encodes images & queries, serves REST API |
| **web** | React (Vite) + nginx | Search UI with photo gallery |

**How it works:**
1. **Index**: CLIP encodes each photo into a 512-dim vector, stored in Qdrant
2. **Search**: Your text query is encoded by CLIP's text encoder, then matched against image vectors via cosine similarity
3. **Results**: Photos ranked by similarity score, displayed in a responsive grid

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Setup

1. Clone the repo and create your `.env` file:

```bash
cp .env.example .env
```

2. Edit `.env` to point to your photos folder:

```
PHOTOS_DIR=/path/to/your/photos
```

3. Start all services:

```bash
docker compose up --build
```

4. Open the web UI at **http://localhost:3000**

5. Click **"Index Photos"** to scan and index your photo folder

6. Type a natural language query (e.g., "birthday party", "beach sunset") and hit **Search**

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/index` | Index photos from the configured folder |
| `POST` | `/api/search` | Search photos by text query |
| `GET` | `/api/photos/{path}` | Serve a photo file |
| `GET` | `/api/status` | Get indexing status |
| `GET` | `/health` | Health check |

**Example — search:**
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "photos at the beach", "limit": 10}'
```

**Example — index:**
```bash
curl -X POST http://localhost:8000/api/index
```

## Development

### Backend (Python)

Install dependencies with **uv**:

```bash
uv sync
```

**Code quality:**

Format code with ruff:
```bash
uv run ruff format backend/
```

Run linting checks:
```bash
uv run ruff check backend/
```

Auto-fix linting issues:
```bash
uv run ruff check backend/ --fix
```

Run tests (uses mocked ML dependencies, runs in ~4s):

```bash
uv run pytest backend/tests/ --rootdir backend/ -v
```

### Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

## System Requirements

- **Testing**: MacBook Air with 8 GB RAM (~2.5 GB used by the stack)
- **Production**: PC with 8 GB GPU for ~30,000 photos

## Supported Formats

JPEG (`.jpg`, `.jpeg`) and PNG (`.png`)
