# Architecture Decision Records (ADRs)

### ADR 001: Modular Monolith Architecture
- **Status**: Accepted
- **Context**: Kestrel needs clear domain boundaries (auth, ingest, analytics, providers) developed, tested, and maintained by a single engineer without the operational complexity of distributed microservices.
- **Decision**: Build Kestrel as a modular monolith within a single codebase where modules interact via clean service contracts rather than internal network calls.
- **Consequences**: Greatly simplifies deployment, testing, and debugging; enforces domain encapsulation so any module can be extracted into an independent microservice later if scale demands.

### ADR 002: Ingest-API-First Telemetry Without Gateway Proxy
- **Status**: Accepted
- **Context**: Tracking LLM metrics could be implemented either by proxying every LLM call through a gateway or by having client apps send telemetry directly to an ingest API.
- **Decision**: Implement an ingest-first telemetry API (`POST /ingest/events`) accompanied by a lightweight client wrapper, rather than building an inline proxy gateway.
- **Consequences**: Telemetry records exact client-measured tokens and latency without Kestrel becoming a single point of failure in the inference critical path; Kestrel never needs to store customer provider keys for inference.

### ADR 003: PostgreSQL as Unified Datastore (No Redis or TimescaleDB at MVP)
- **Status**: Accepted
- **Context**: LLM telemetry involves time-series metrics, transactional configuration, and analytical aggregations, which could tempt multi-database architectures.
- **Decision**: Use a single PostgreSQL database leveraging native indexing, `percentile_cont`, and scheduled rollup tables for analytical queries.
- **Consequences**: Minimizes operational overhead and infrastructure complexity during MVP; avoids dual-write synchronization bugs; can revisit TimescaleDB or Redis when measured throughput necessitates.

### ADR 004: Synchronous SQLAlchemy 2.0 with Async HTTPX for Outbound Calls
- **Status**: Accepted
- **Context**: FastAPI supports asynchronous database drivers, but async ORM code increases debugging complexity, connection pool subtleties, and test harness fragility.
- **Decision**: Use synchronous SQLAlchemy 2.0 with Alembic for all database operations, while using async `httpx` for outbound provider health probes and model queries.
- **Consequences**: Delivers reliable, straightforward database transactions and debugging; outbound network I/O remains non-blocking for background tasks.

### ADR 005: Separate Worker Process with APScheduler
- **Status**: Accepted
- **Context**: Periodic tasks (provider health checks, alert rule evaluations, aggregation rollups, data retention) must run reliably without degrading API request throughput.
- **Decision**: Run a separate worker process executing APScheduler, sharing the same domain models and database connection pool with the API process.
- **Consequences**: Isolates scheduled workloads from HTTP API performance without introducing Celery, RabbitMQ, or Redis queue infrastructure; worker failure does not crash the HTTP API.

### ADR 006: Argon2 Password Hashing and Server-Enforced JWT Roles
- **Status**: Accepted
- **Context**: The platform requires secure user authentication and strict authorization separation between administrative operators and read-only viewers.
- **Decision**: Hash passwords with `argon2-cffi` and issue stateless JWT tokens; enforce `admin` and `viewer` permissions server-side on every route and repository query.
- **Consequences**: Robust resistance against GPU-based cracking attacks; client-side role manipulation cannot bypass API authorization boundaries.

### ADR 007: Fernet Symmetric Encryption for Provider Credentials at Rest
- **Status**: Accepted
- **Context**: Users configure upstream provider API keys (Groq, Gemini) for health checks and model discovery that must be kept safe from unauthorized database access.
- **Decision**: Encrypt all stored provider credentials using Fernet symmetric encryption with a master key supplied strictly via environment variables; credentials are never returned by the API or logged.
- **Consequences**: Secures credentials against database snapshot leaks; requires secure management of the master encryption key; prevents frontend exposure after initial submission.

### ADR 008: Metadata-Only Telemetry (Zero Prompt/Response Storage)
- **Status**: Accepted
- **Context**: Logging prompt text and model output text introduces immense data storage overhead, privacy liabilities, and enterprise security compliance hurdles.
- **Decision**: Collect and store only operational metadata (token counts, latency, status codes, error classifications, model names); never store prompt or completion text.
- **Consequences**: Drastically reduces storage requirements, simplifies privacy compliance, and eliminates risk of leaking sensitive user prompts or proprietary IP in telemetry tables.

### ADR 009: Event-Level Price Snapshotting
- **Status**: Accepted
- **Context**: LLM provider token pricing changes over time; calculating historical costs from a mutable current pricing table causes historical reporting to drift retroactively.
- **Decision**: Snapshot the exact effective token price onto each telemetry event record at the time of ingestion.
- **Consequences**: Historical financial analytics and audit trails remain permanently immutable; updates to pricing tables only affect future ingested events.

### ADR 010: React SPA with Tailwind, shadcn/ui, TanStack Query, and ECharts
- **Status**: Accepted
- **Context**: The frontend requires responsive dashboard visualizations, rapid state management, and an accessible, polished user interface.
- **Decision**: Build a React SPA using Vite, TypeScript, Tailwind CSS, shadcn/ui component primitives, TanStack Query for server state, and Apache ECharts; visual direction inspired by Minia's design feel without copying assets.
- **Consequences**: Clean, accessible component system with optimized charting performance; zero licensing risks or third-party proprietary code entanglements.

### ADR 011: Percentiles Computed from Raw Events, Rollups for Counts and Sums
- **Status**: Accepted
- **Context**: Pre-aggregating latency into hourly or daily rollups prevents accurate multi-window percentile calculations (`p50`, `p95`, `p99`) because percentiles cannot be mathematically averaged.
- **Decision**: Retain raw event latency for accurate percentile calculations across arbitrary query windows; restrict rollups exclusively to additive metrics (request counts, token sums, cost totals).
- **Consequences**: Guarantees mathematically accurate latency percentiles; requires scheduled retention pruning of aged raw events once beyond the active detailed query window.

### ADR 012: Docker Compose for Local Dependencies; PostgreSQL 17 Pinned
- **Status**: Accepted
- **Context**: Local development requires a consistent, reproducible PostgreSQL environment that matches target deployment without forcing developers to install native PostgreSQL server instances on Windows host machines.
- **Decision**: Use Docker Compose (`compose.yaml`) with major version pinned to `postgres:17`, binding exclusively to `127.0.0.1:${POSTGRES_PORT:-5432}` and storing database state in a named Docker volume (`kestrel_pgdata`).
- **Consequences**: Ensures predictable database behavior across developer environments; protects database port from external network exposure; persists development data across `docker compose down` while allowing clean resets via `docker compose down -v`.

### ADR 013: uv with pyproject.toml and uv.lock for Python Dependencies
- **Status**: Accepted
- **Context**: Python dependency management must be fast, deterministic, cross-platform, and fully reproducible across local Windows development and CI pipelines without lockfile discrepancy.
- **Decision**: Adopt `uv` with standard PEP 621 `pyproject.toml` and lockfile `uv.lock` for all backend packaging and virtual environments.
- **Consequences**: Delivers sub-second package resolution and installation; eliminates pip-compile divergence; standardizes tool configurations (ruff, pytest) inside a single file.

### ADR 014: API Conventions: Product Endpoints under /api/v1; Probes Unversioned at Root
- **Status**: Accepted
- **Context**: Infrastructure probes (Kubernetes, Compose, reverse proxies) require standard static paths for liveness and readiness, whereas product business APIs evolve with explicit version deprecation lifecycles.
- **Decision**: Expose operational infrastructure probes (`/health`, `/health/ready`) unversioned at the server root; route all application domain endpoints under `/api/v1`.
- **Consequences**: Shields cluster monitoring from product API version deprecations; keeps internal infrastructure probes clean and lightweight.

### ADR 015: Direct-to-Main Workflow with Milestone Tags and a Pre-Push Quality Gate
- **Status**: Accepted
- **Context**: A solo engineering cadence requires eliminating pull request latency while preserving strict repository safety, traceable rollback points, and non-negotiable code quality.
- **Decision**: Commit directly to `main` with Conventional Commits, tagging each completed milestone (e.g. `m1-docker-postgres`, `m2-backend-skeleton`) and enforcing a mandatory pre-push quality gate (`ruff check`, `ruff format --check`, `pytest`, secret scan).
- **Consequences**: Maximizes development velocity without branch sprawl; tags provide exact immutable rollback points; pre-push gates guarantee broken code or secrets never land on `main`.
