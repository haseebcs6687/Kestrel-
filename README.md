# Kestrel AI Control Center

Kestrel AI Control Center is an observability and operations dashboard for LLM-powered applications. It tracks usage, token consumption, cost, latency, errors, provider health, and operational alerts across AI systems, providing engineering teams with centralized visibility and control over their LLM integrations.

**Status: in development — Milestone 1**

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL |
| **Frontend** | React 18+, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, Apache ECharts |
| **Worker** | Python 3.13, APScheduler, httpx (async outbound) |
| **Infrastructure & Ops** | Docker Compose, Nginx, Prometheus, Grafana, GitHub Actions |
| **Testing** | pytest, Vitest, Playwright |

## Project Documentation

- [Product Requirements Document (PRD)](docs/PRD.md) — Product vision, user roles, functional and non-functional requirements.
- [System Architecture](docs/ARCHITECTURE.md) — Process topology, architectural invariants, backend modules, and provider adapter design.
- [Architecture Decisions (ADRs)](docs/ARCHITECTURE_DECISIONS.md) — 12 Architecture Decision Records documenting key engineering trade-offs.
- [Learning Notes](docs/LEARNING_NOTES.md) — Key conceptual definitions, operational rationale, and interview takeaways.
- [Project Context](docs/PROJECT_CONTEXT.md) — Compact context for agent continuity and environment state.
- [Project Status](docs/PROJECT_STATUS.md) — Current milestone status matrix and implementation tracking.
- [Implementation Log](docs/IMPLEMENTATION_LOG.md) — Chronological log of milestones and modifications.
- [TODO](docs/TODO.md) — Remaining planning specs and upcoming milestones.

## Implementation Status

**Implemented**: Repository skeleton, documentation system, and Docker Compose local development environment with a healthy PostgreSQL 17 database container and persistent volume.

## Local Development

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows with WSL 2 backend)

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
