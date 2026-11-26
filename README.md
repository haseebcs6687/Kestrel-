# Kestrel AI Control Center

[![CI](https://github.com/haseebcs6687/Kestrel-/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/haseebcs6687/Kestrel-/actions/workflows/ci.yml)

Kestrel AI Control Center is an observability and operations dashboard for LLM-powered applications. It tracks usage, token consumption, cost, latency, errors, provider health, and operational alerts across AI systems, providing engineering teams with centralized visibility and control over their LLM integrations.

**Status: in development — Milestone 6**

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL, Argon2id, PyJWT |
| **Frontend** | React 18+, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Apache ECharts |
| **Worker** | Python 3.13, APScheduler, httpx (async outbound) |
| **Infrastructure & Ops** | Docker Compose, Nginx, Prometheus, Grafana, GitHub Actions |
| **Testing** | pytest, Vitest, Playwright |

## Project Documentation

- [Engineering Roadmap](docs/ROADMAP.md) — 19-milestone phased breakdown and architecture philosophy.
- [Product Requirements Document (PRD)](docs/PRD.md) — Product vision, user roles, functional and non-functional requirements.
- [System Architecture](docs/ARCHITECTURE.md) — Process topology, architectural invariants, backend modules, and provider adapter design.
- [Security Architecture & Policies](docs/SECURITY.md) — Authentication architecture, Argon2id, JWT token claims, session rotation, audit logging, and tenant isolation.
- [Database Schema Design](docs/DATABASE_SCHEMA.md) — Catalog of 12 relational tables, conventions, constraints, and Mermaid ERD.
- [Architecture Decisions (ADRs)](docs/ARCHITECTURE_DECISIONS.md) — 26 Architecture Decision Records documenting key engineering trade-offs.
- [Learning Notes](docs/LEARNING_NOTES.md) — Key conceptual definitions, operational rationale, and interview takeaways.
- [Project Context](docs/PROJECT_CONTEXT.md) — Compact context for agent continuity, environment state, and direct-to-main workflow.
- [Project Status](docs/PROJECT_STATUS.md) — Current milestone status matrix and implementation tracking.
- [Implementation Log](docs/IMPLEMENTATION_LOG.md) — Chronological log of milestones and modifications.
- [TODO](docs/TODO.md) — Remaining planning specs and upcoming milestones.

## Implementation Status

**Implemented**: Repository skeleton, documentation system, Docker Compose PostgreSQL 17 development environment, FastAPI backend skeleton with configuration, structured logging, request-ID middleware, database connection module, `/health` and `/health/ready` probes, database schema design, Alembic migrations (`0001`, `0002`, and `0003`), SQLAlchemy 2.0 `workspaces`, `users`, `refresh_tokens`, and canonical `audit_logs` models, Argon2id password hashing, JWT bearer token authentication, HttpOnly refresh token rotation with reuse detection, `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`, `/api/v1/auth/me`, workspace-scoped repository multi-tenant isolation (`WorkspaceScopedRepository`), `/api/v1/users` role-based access control, `/api/v1/audit-logs` administrative endpoint, and GitHub Actions CI workflow (PostgreSQL 17 service container, uv sync, linting, migration check, pytest suite, in-repo secret scan, Gitleaks, and advisory dependency audit). Tested with 112 automated unit and integration tests running against PostgreSQL.

## Continuous Integration

Every push to `main` and pull request triggers automated CI checks defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):
1. **Backend (`backend`)**: Runs on Ubuntu with a real PostgreSQL 17 service container. Performs `uv run ruff check .`, `uv run ruff format --check .`, `uv run alembic upgrade head`, `uv run alembic check` (schema drift detection), and `uv run pytest -ra` (112 tests).
2. **Secret Scan (`secrets`)**: Full repository scan using the in-repo script `scripts/secret_scan.py` followed by `gitleaks/gitleaks-action@v3`.
3. **Dependency Audit (`dependency-audit`)**: Exports locked dependencies and runs `pip-audit` via `uvx` (advisory, non-blocking).

### Running Pre-Push Checks Locally
Run the exact quality gate locally before committing or pushing:
```bash
# Backend checks
cd backend
uv run ruff check .
uv run ruff format --check .
uv run alembic upgrade head
uv run alembic check
uv run pytest -ra
cd ..

# Repository secret scan
python scripts/secret_scan.py
```

## Local Development

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows with WSL 2 backend)
- [Python 3.13](https://www.python.org/)
- [`uv`](https://docs.astral.sh/uv/) package and tool manager

### Starting the Database
1. Copy the environment template to create your local `.env`:
   ```bash
   cp .env.example .env
   ```
2. In `.env`, set a strong local `POSTGRES_PASSWORD`.
3. Start PostgreSQL in the background:
   ```bash
   docker compose up -d
   ```
4. Verify container health:
   ```bash
   docker compose ps
   ```
5. Stop containers while preserving database data:
   ```bash
   docker compose down
   ```
   > [!WARNING]
   > Running `docker compose down -v` removes the named volume and **permanently deletes** all local database data.

### Database Migrations
1. Apply migrations to the local PostgreSQL database:
   ```bash
   cd backend
   uv run alembic upgrade head
   ```
2. Verify migration state and check for schema drift:
   ```bash
   uv run alembic current
   uv run alembic check
   ```

### Running the Backend API
1. Ensure the PostgreSQL container is running (`docker compose up -d`).
2. Navigate to the backend directory:
   ```bash
   cd backend
   ```
3. Install dependencies using uv:
   ```bash
   uv sync
   ```
4. Start the development server:
   ```bash
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
5. Run tests:
   ```bash
   uv run pytest -v
   ```
