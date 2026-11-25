# Project Context — Kestrel AI Control Center

## Current State
- **Current Phase**: Phase 1 implementation underway.
- **Completed Milestones**: Milestone 0 (merged into `main` via PR #1).
- **Current Milestone**: Milestone 1 — Docker environment and PostgreSQL development database via Docker Compose.
- **Known Bugs**: None.
- **Pending Tasks**: Review Milestone 1 pull request and merge into `main`.
- **Next Action**: Milestone 2: FastAPI skeleton, config, `/health`, and database connectivity check.

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
- ADR 012: Docker Compose for Local Dependencies; PostgreSQL 17 Pinned

## Repository Structure
- `backend/`: FastAPI API service and APScheduler background worker process.
- `frontend/`: React SPA dashboard, data visualization, and management interface.
- `infra/`: Docker Compose configurations, Nginx proxy, Prometheus, and Grafana specs.
- `docs/`: PRD, Architecture, ADRs, tracking logs, and design reference policies.
- `.github/`: Pull request templates and CI workflow definitions.
- `compose.yaml`: Local development Docker Compose service definition for PostgreSQL 17.
- `.env.example`: Committed template for environment variables and secrets.

## Developer & Execution Environment
- **Host OS**: Windows 11 (PowerShell) with WSL 2 backend
- **Runtimes & Tools**: Python 3.13, Node 24, Git 2.55
- **Docker**: Docker version 29.9.3 (build 5457199), Docker Compose version v5.7.1
- **Compose Service**: `compose.yaml` at repository root
- **Database Configuration**: Database `kestrel`, User `kestrel`, Host port `5432` bound to `127.0.0.1`
- **Named Volume**: `kestrel_pgdata`
- **Git Remote**: `https://github.com/haseebcs6687/Kestrel-.git` (Public repository)

## Development Workflow
The author pastes prompt specifications into Antigravity, then sends execution and verification reports to Claude for peer review before initiating the next prompt.
