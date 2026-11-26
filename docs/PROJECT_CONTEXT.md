# Project Context — Kestrel AI Control Center

## Current State
- **Current Phase**: Phase 1 implementation underway.
- **Completed Milestones**:
  - Milestone 0: Repository bootstrap and documentation system.
  - Milestone 1: Docker Compose PostgreSQL 17 environment (Tag: `m1-docker-postgres`).
  - Milestone 2: FastAPI backend skeleton, configuration, logging, request IDs, database connectivity, and health probes (Tag: `m2-backend-skeleton`).
  - Milestone 3: Database schema design, Alembic migrations, `workspaces` and `users` models, and dedicated test databases (Tag: `m3-alembic-identity`).
- **Current Milestone**: Milestone 3 complete; preparing Milestone 4.
- **Known Bugs**: None.
- **Next Action**: Milestone 4 (Auth & User Management / Ingestion API).

## Development Workflow
- **Direct-to-Main**: Development proceeds directly on branch `main` using Conventional Commits. No feature branch overhead or pull request delays for solo implementation.
- **Milestone Tags**: Each completed milestone is tagged on `main` (e.g. `m1-docker-postgres`, `m2-backend-skeleton`) to provide immutable rollback points.
- **Pre-Push Quality Gate**: Before pushing to `main`, four automated checks must pass:
  1. `uv run ruff check .`
  2. `uv run ruff format --check .`
  3. `uv run pytest -v` (against real PostgreSQL container)
  4. Secret audit (`git grep -F` for real database password and regex for key patterns `sk-`, `AIza`, `gsk_`).

## Architecture & Technology Summary
1. Modular monolith architecture with a separate worker process sharing database models and code.
2. Ingest-API-first telemetry model (`POST /ingest/events`) using workspace API key authentication.
3. Backend powered by Python 3.13, FastAPI, SQLAlchemy 2.0 (synchronous), Alembic, and PostgreSQL 17.
4. Dependency management driven by `uv` using `pyproject.toml` and `uv.lock`.
5. Frontend single-page application built with React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, and Apache ECharts.
6. Observability driven by Prometheus metrics scraping (`/metrics`) and Grafana operational dashboards.

## Backend Structure
```
backend/
  app/
    main.py                 # Application factory create_app() and entrypoint
    core/
      base.py               # DeclarativeBase, naming conventions, and common mixins
      config.py             # Pydantic Settings loading from env and root .env
      db.py                 # Lazy SQLAlchemy engine, sessionmaker, and get_db dependency
      logging.py            # Structlog configuration (JSON for prod, console for dev)
      middleware.py         # Request-ID tracking and structured access logging
      models_registry.py    # Centralized model registry for Alembic discovery
    modules/
      auth/                 # User model, authentication and role definitions
        models.py
      platform/             # Liveness (/health) and readiness (/health/ready) probes
        router.py
        schemas.py
      workspaces/           # Workspace model and multi-tenant management
        models.py
  migrations/               # Alembic database migrations environment
    env.py
    script.py.mako
    versions/
      0001_create_workspaces_and_users.py
  tests/
    conftest.py             # TestClient, kestrel_test DB engine, and savepoint fixtures
    test_config.py          # Configuration loading and secret masking tests
    test_docs_exposure.py   # Swagger/OpenAPI exposure tests across environments
    test_health.py          # /health and /health/ready liveness and readiness tests
    test_migrations.py      # Alembic upgrade/downgrade/upgrade lifecycle and drift tests
    test_models_workspaces_users.py # Workspace and User ORM models & constraint tests
    test_request_id.py      # X-Request-ID propagation, validation, and generation tests
  alembic.ini
  pyproject.toml
  uv.lock
```

## Developer & Execution Environment
- **Host OS**: Windows 11 (PowerShell) with WSL 2 backend
- **Runtimes & Tools**: Python 3.13.15, Node 24, Git 2.55, `uv` 0.13.10
- **Docker**: Docker version 29.9.3 (build 5457199), Docker Compose version v5.7.1
- **Primary Locked Dependencies**: FastAPI 0.165.0, Uvicorn 0.54.0, SQLAlchemy 2.1.9, Alembic 1.20.1, Psycopg 3.3.9, Pydantic 2.14.4, Structlog 26.1.0, Pytest 9.2.0, Ruff 0.17.6
- **Database Configuration**: Container `kestrel-postgres-1` (PostgreSQL 17.12), Port 5432 bound to `127.0.0.1`
- **Git Remote**: `https://github.com/haseebcs6687/Kestrel-.git` (Public repository)
