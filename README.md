# Kestrel AI Control Center

Kestrel AI Control Center is an observability and operations dashboard for LLM-powered applications. It tracks usage, token consumption, cost, latency, errors, provider health, and operational alerts across AI systems, providing engineering teams with centralized visibility and control over their LLM integrations.

**Status: in development — Milestone 4**

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL, Argon2id, PyJWT |
| **Frontend** | React 18+, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Apache ECharts |
| **Worker** | Python 3.13, APScheduler, httpx (async outbound) |
| **Infrastructure & Ops** | Docker Compose, Nginx, Prometheus, Grafana, GitHub Actions |
| **Testing** | pytest, Vitest, Playwright |

## Project Documentation

- [Product Requirements Document (PRD)](docs/PRD.md) — Product vision, user roles, functional and non-functional requirements.
- [System Architecture](docs/ARCHITECTURE.md) — Process topology, architectural invariants, backend modules, and provider adapter design.
- [Security Architecture & Policies](docs/SECURITY.md) — Authentication architecture, Argon2id, JWT token claims, tenant isolation, and security invariants.
- [Database Schema Design](docs/DATABASE_SCHEMA.md) — Catalog of 11 relational tables, conventions, constraints, and Mermaid ERD.
- [Architecture Decisions (ADRs)](docs/ARCHITECTURE_DECISIONS.md) — 22 Architecture Decision Records documenting key engineering trade-offs.
- [Learning Notes](docs/LEARNING_NOTES.md) — Key conceptual definitions, operational rationale, and interview takeaways.
- [Project Context](docs/PROJECT_CONTEXT.md) — Compact context for agent continuity, environment state, and direct-to-main workflow.
- [Project Status](docs/PROJECT_STATUS.md) — Current milestone status matrix and implementation tracking.
- [Implementation Log](docs/IMPLEMENTATION_LOG.md) — Chronological log of milestones and modifications.
- [TODO](docs/TODO.md) — Remaining planning specs and upcoming milestones.

## Implementation Status

**Implemented**: Repository skeleton, documentation system, Docker Compose PostgreSQL 17 development environment, FastAPI backend skeleton with configuration, structured logging, request-ID middleware, database connection module, `/health` and `/health/ready` probes, database schema design, Alembic migrations, SQLAlchemy 2.0 `workspaces` and `users` models, Argon2id password hashing, JWT bearer token authentication, `/api/v1/auth/register`, `/api/v1/auth/login`, `/api/v1/auth/me`, workspace-scoped repository multi-tenant isolation (`WorkspaceScopedRepository`), and `/api/v1/users` role-based access. Tested with 53 automated unit and integration tests running against PostgreSQL.

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
