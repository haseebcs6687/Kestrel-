# Project Context — Kestrel AI Control Center

## Current State
- **Current Phase**: Phase 1 planning complete enough to start M0; implementation beginning.
- **Completed Milestones**: None (until Milestone 0 is reviewed and merged into `main`).
- **Current Milestone**: Milestone 0 — Repository bootstrap and documentation system.
- **Known Bugs**: None.
- **Pending Tasks**: Review Milestone 0 pull request and merge into `main`.
- **Next Action**: Milestone 1: Docker install + PostgreSQL + FastAPI skeleton with `/health`.

## Architecture Summary
1. Modular monolith architecture with a separate worker process sharing database models and code.
2. Ingest-API-first telemetry model (`POST /ingest/events`) using workspace API key authentication.
3. Backend powered by Python 3.13, FastAPI, SQLAlchemy 2.0 (synchronous), Alembic, and PostgreSQL.
4. Frontend single-page application built with React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, and Apache ECharts.
5. Observability driven by Prometheus metrics scraping (`/metrics`) and Grafana operational dashboards.

## Important Architectural Decisions
- ADR 001: Modular Monolith Architecture
- ADR 002: Ingest-API-First Telemetry Without Gateway Proxy
- ADR 003: PostgreSQL as Unified Datastore (No Redis or TimescaleDB at MVP)
- ADR 004: Synchronous SQLAlchemy 2.0 with Async HTTPX for Outbound Calls
- ADR 005: Separate Worker Process with APScheduler
- ADR 006: Argon2 Password Hashing and Server-Enforced JWT Roles
- ADR 007: Fernet Symmetric Encryption for Provider Credentials at Rest
- ADR 008: Metadata-Only Telemetry (Zero Prompt/Response Storage)
- ADR 009: Event-Level Price Snapshotting
- ADR 010: React SPA with Tailwind, shadcn/ui, TanStack Query, and ECharts
- ADR 011: Percentiles Computed from Raw Events, Rollups for Counts and Sums

## Repository Structure
- `backend/`: FastAPI API service and APScheduler background worker process.
- `frontend/`: React SPA dashboard, data visualization, and management interface.
- `infra/`: Docker Compose configurations, Nginx proxy, Prometheus, and Grafana specs.
- `docs/`: PRD, Architecture, ADRs, tracking logs, and design reference policies.
- `.github/`: Pull request templates and CI workflow definitions.

## Developer & Execution Environment
- **Host OS**: Windows 11 (PowerShell)
- **Runtimes & Tools**: Python 3.13, Node 24, Git 2.55
- **Docker**: Not installed yet (scheduled for installation in Milestone 1)
- **Git Remote**: `https://github.com/haseebcs6687/Kestrel-.git` (Public repository)

## Development Workflow
The author pastes prompt specifications into Antigravity, then sends execution and verification reports to Claude for peer review before initiating the next prompt.
