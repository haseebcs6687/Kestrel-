# Kestrel AI Control Center

Kestrel AI Control Center is an observability and operations dashboard for LLM-powered applications. It tracks usage, token consumption, cost, latency, errors, provider health, and operational alerts across AI systems, providing engineering teams with centralized visibility and control over their LLM integrations.

**Status: in development — Milestone 0**

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
- [Architecture Decisions (ADRs)](docs/ARCHITECTURE_DECISIONS.md) — 11 Architecture Decision Records documenting key engineering trade-offs.
- [Learning Notes](docs/LEARNING_NOTES.md) — Key conceptual definitions, operational rationale, and interview takeaways.
- [Project Context](docs/PROJECT_CONTEXT.md) — Compact context for agent continuity and environment state.
- [Project Status](docs/PROJECT_STATUS.md) — Current milestone status matrix and implementation tracking.
- [Implementation Log](docs/IMPLEMENTATION_LOG.md) — Chronological log of milestones and modifications.
- [TODO](docs/TODO.md) — Remaining planning specs and upcoming milestones.

## Implementation Status

**Implemented**: Repository skeleton and documentation only. No application code, dependency installations, or Docker services have been scaffolded yet.

## Run Instructions

Coming in Milestone 1 (Docker Compose environment and FastAPI skeleton with `/health`).
