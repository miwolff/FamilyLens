# FamilyLens

Local-first intelligent photo search — query your personal photo library using natural language and browse visually similar image clusters.

## Architecture

Three Docker containers orchestrated via Docker Compose:

| Service | Tech | Purpose |
|---------|------|---------|
| **qdrant** | Qdrant v1.13.2 | Vector database for image embeddings |
| **api** | FastAPI + CLIP ViT-B/32 + MiniBatchKMeans | Encodes images, rebuilds clusters, serves REST API |
| **web** | React (Vite) + nginx | Search UI with gallery and cluster browser |

**How it works:**
1. **Index**: CLIP encodes each photo into a 512-dim vector, stored in Qdrant
2. **Cluster**: After each indexing run, the backend groups nearby image embeddings into visual clusters
3. **Search**: Your text query is encoded by CLIP's text encoder, then matched against image vectors via cosine similarity
4. **Browse**: Search results and cluster galleries are displayed in the web UI

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/) to create .venv if needed for development

### Setup

1. Clone the repo and create your `.env` file:

```bash
cp .env.example .env
```

2. Edit `.env` to point to your photos folder:

```
PHOTOS_DIR=/path/to/your/photos
```

You can give up to 5 photo directories in the `.env` file that all will be mounted into child folders of the `photos` directory of the api container. See .env.example and docker-compose.yml.

Optional backend tuning values such as cluster count, search limit, and log level
are documented in `.env.example`.

3. Start all services:

```bash
docker compose up --build
```

4. Open the web UI at **http://localhost:3000**

5. Click **"Index Photos"** to scan and index your photo folder

6. Type a natural language query (e.g., "birthday party", "beach sunset") and hit **Search**

7. Open **Clusters** to browse the largest visual groups in your library

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/index` | Index photos from the configured folder |
| `GET` | `/api/index/status` | Get live indexing progress |
| `POST` | `/api/index/cancel` | Cancel the active indexing run |
| `POST` | `/api/search` | Search photos by text query |
| `GET` | `/api/clusters` | List image clusters from largest to smallest |
| `GET` | `/api/clusters/{cluster_id}` | Get one cluster gallery |
| `GET` | `/api/photos/{path}` | Serve a photo file |
| `GET` | `/api/status` | Get indexed photo count and collection name |
| `GET` | `/health` | Dependency-aware health check |

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

**Example — live indexing status:**
```bash
curl http://localhost:8000/api/index/status
```

**Example — clusters:**
```bash
curl http://localhost:8000/api/clusters
```

## Project Structure

```
FamilyLens/
├── docker-compose.yml          # Container orchestration
├── README.md
├── backend/
│   ├── pyproject.toml          # Python dependencies & build config
│   ├── Dockerfile              # FastAPI backend container
│   ├── .dockerignore           # Excludes tests, cache, etc. from Docker build
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py            # FastAPI app, lifespan, endpoints
│   │   ├── config.py          # Environment configuration
│   │   ├── routers/           # API endpoints (index, search, clusters)
│   │   └── services/          # CLIP, clustering, and Qdrant clients
│   └── tests/
├── frontend/
│   ├── Dockerfile              # React + nginx container
│   ├── .dockerignore
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/         # SearchBar, PhotoGrid, etc.
│   │   ├── pages/              # Search and cluster pages
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   └── nginx.conf             # Reverse proxy config
└── photos/                     # Local photos directory (mounted at runtime)
```

**Key notes:**
- `pyproject.toml` is in the `backend/` folder (along with the FastAPI code)
- Each `Dockerfile` has a matching `.dockerignore` to exclude unnecessary files
- Docker Compose builds backend from `./backend` context, frontend from `./frontend` context

## Development

### Backend (Python)

The following commands are all run in the `backend` folder.

```bash
cd backend
```

Install dependencies with **uv**:

```bash
uv sync
```

**Code quality:**

Format code with ruff:
```bash
uv run ruff format
```

Run linting checks:
```bash
uv run ruff check
```

Auto-fix linting issues:
```bash
uv run ruff check --fix
```

Run tests (uses mocked ML dependencies, runs in ~4s):

```bash
uv run pytest tests/ -v
```

To upgrade all locked dependencies within the version constraints in
`pyproject.toml`, run:

```bash
uv lock --upgrade
uv sync
```

The `[tool.uv]` setting `exclude-newer = "7 days"` in `pyproject.toml`
excludes package releases uploaded less than seven days ago. This updates
`uv.lock` but does not change the declared dependency constraints.

### Frontend (React)

```bash
cd frontend
npm ci
npm run dev
```

To upgrade dependencies within the version ranges in `package.json`, run:

```bash
npm update
```

The project `.npmrc` sets `min-release-age=7`, so npm 11 or newer excludes
package releases published less than seven days ago when resolving updates.
This updates `package-lock.json` but does not change the declared version
ranges. Use `npm ci` to install the versions recorded in the lockfile.

## Configuration

Backend configuration is read from environment variables with the
`FAMILYLENS_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `FAMILYLENS_CLUSTER_COUNT` | `12` | Default number of clusters to rebuild after indexing |
| `FAMILYLENS_MAX_CLUSTER_COUNT` | `1000` | Upper bound the API accepts for client-supplied cluster counts |
| `FAMILYLENS_SEARCH_DEFAULT_LIMIT` | `20` | Default search result limit |
| `FAMILYLENS_LOG_LEVEL` | `INFO` | Backend log verbosity |

The index API can optionally target a subfolder, but it is restricted to paths
inside the configured `/photos` mount tree. Requests outside that root are
rejected.

## Health And Storage

- `/health` now reports dependency status for the CLIP model and Qdrant. It
  returns HTTP 200 only when both are ready, and HTTP 503 when the API is
  degraded.
- Docker Compose waits for Qdrant's `/readyz` endpoint before starting the API.
- Indexed vectors are stored in the `qdrant_storage` Docker volume. If that
  volume is removed, the index can be rebuilt from the source photo folders by
  running indexing again.

## System Requirements

- **Testing**: MacBook Air with 8 GB RAM (~2.5 GB used by the stack)
- **Production**: PC with 8 GB GPU for ~30,000 photos

## Clusters

- Clusters are rebuilt automatically after each indexing run.
- The cluster browser sorts clusters by size so the largest one appears first.
- Each cluster view opens directly into the full gallery for that cluster, with the strongest matches shown first.

## Supported Formats

JPEG (`.jpg`, `.jpeg`), PNG (`.png`), Adobe DNG (`.dng`), and Nikon
NEF (`.nef`)

## License

This project is licensed under the [MIT License](LICENSE).
