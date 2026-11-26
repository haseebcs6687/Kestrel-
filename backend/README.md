# Backend — Kestrel AI Control Center

## Purpose
FastAPI application and background worker process providing telemetry ingestion, health monitoring, operational alerts, and analytical query interfaces for LLM-powered applications.

## Folder Layout
```
backend/
  app/
    __init__.py
    main.py                 # Application factory create_app() and entrypoint
    core/
      __init__.py
      config.py             # Pydantic Settings loading from env and root .env
      db.py                 # Lazy SQLAlchemy engine, sessionmaker, and get_db dependency
      logging.py            # Structlog configuration (JSON for prod, console for dev)
      middleware.py         # Request-ID tracking and structured access logging
    modules/
      __init__.py
      platform/             # Liveness (/health) and readiness (/health/ready) probes
        __init__.py
        router.py
        schemas.py
  tests/
    __init__.py
    conftest.py             # TestClient fixtures and isolation teardown
    test_config.py          # Configuration loading and secret masking tests
    test_health.py          # /health and /health/ready liveness and readiness tests
    test_request_id.py      # X-Request-ID propagation, validation, and generation tests
  pyproject.toml            # Project definition, runtime/dev dependencies, ruff, and pytest config
  uv.lock                   # Deterministic dependency lockfile
```

## Commands & Workflows
All commands run from the `backend/` directory using `uv`:
- **Install dependencies**: `uv sync`
- **Run development server**: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- **Run automated test suite**: `uv run pytest -v`
- **Lint codebase**: `uv run ruff check .`
- **Format check**: `uv run ruff format --check .`
- **Format codebase**: `uv run ruff format .`

## Endpoints
| Method | Path | Description | Versioning | Auth |
|---|---|---|---|---|
| `GET` | `/health` | Liveness probe returning `200 {"status": "ok"}` | Unversioned root | Public |
| `GET` | `/health/ready` | Readiness probe verifying DB ping via `SELECT 1` | Unversioned root | Public |
| `GET` | `/docs` | Interactive Swagger API documentation (disabled in prod) | Unversioned root | Public |
| `GET` | `/openapi.json`| OpenAPI 3.1 specification schema (disabled in prod) | Unversioned root | Public |

> [!NOTE]
> Infrastructure health and readiness probes are unversioned at the root (`/health`, `/health/ready`), whereas domain product APIs will reside under `/api/v1` in upcoming milestones.
