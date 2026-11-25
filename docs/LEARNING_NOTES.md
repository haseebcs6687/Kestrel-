# Engineering Learning Notes

## Standard Note Format
Each entry follows: Concept | Definition | Why it matters | How we used it | Architecture | Important terminology | Example | Interview questions (3-5) | Practical mistakes | Revision summary.

---

## Learning Notes — Milestone 1: Docker & PostgreSQL Containerization

- **Concepts Covered**: Image vs container lifecycle, persistent Docker volumes, localhost-only port binding, container healthchecks, and environment secret hygiene.
- **Definitions & Architecture**:
  - *Image vs Container*: An image (`postgres:17`) is an immutable, read-only template; a container is a stateful, running instance with an ephemeral writable layer.
  - *Named Volumes*: Storage managed by Docker outside the container's root filesystem; preserves database files across container restarts and destructions (`docker compose down`).
  - *Localhost Binding (`127.0.0.1:5432:5432`)*: Explicitly restricts listening sockets to the loopback interface, preventing exposure on local LAN or public networks.
  - *Healthchecks*: Active probes (e.g. `pg_isready`) reporting container readiness to Compose and dependent services before traffic is routed.
- **Terminology**: Image, Container, Named Volume, Daemon, Ephemeral layer, Loopback interface, `pg_isready`, Secret hygiene.
- **Example**: `docker compose down` destroys container instances while preserving `kestrel_pgdata`; `docker compose down -v` destroys both containers and volumes.
- **Interview Questions & Answers**:
  1. *Q: What is the difference between `docker compose down` and `docker compose down -v`?*
     A: `down` stops and removes containers and networks but leaves named volumes intact; `-v` removes volumes as well, resulting in permanent data loss.
  2. *Q: Why bind database ports to `127.0.0.1:5432:5432` instead of `5432:5432`?*
     A: `5432:5432` binds to `0.0.0.0`, exposing the database to the local network or public interfaces; `127.0.0.1` restricts access strictly to the local host machine.
  3. *Q: Why pin PostgreSQL to a specific major version (`postgres:17`) instead of `latest`?*
     A: Major database versions introduce breaking storage engine changes and require explicit migration tools (`pg_upgrade`); `latest` risks inadvertent breakage upon updates.
  4. *Q: How does `pg_isready` prevent race conditions in Docker Compose orchestration?*
     A: It verifies that the Postgres server is actively accepting connections rather than merely confirming that the container process has booted.
- **Practical Mistakes**: Forgetting `-v` deletes volumes or accidentally running `-v` in production; committing `.env` containing live secrets; binding database ports to `0.0.0.0`.
- **Revision Summary**: Milestone 1 establishes a reproducible, isolated PostgreSQL 17 environment with proven volume persistence and zero-secret exposure.

---

## Learning Notes — Milestone 0: Bootstrap & Foundations

- **Concepts Covered**: Monorepo layout, Git & secret hygiene, Conventional Commits with PR flow, and Architecture Decision Records (ADRs).
- **Definitions & Architecture**:
  - *Monorepo*: Single repository containing multiple co-evolving packages (`backend`, `frontend`, `infra`). Simplifies coordinated atomic PRs and shared types.
  - *Secret Hygiene*: Strict exclusion of credentials via `.gitignore`, pre-commit verification, and regex auditing. Crucial to prevent credential leaks to public GitHub.
  - *Branch & PR Flow*: Branch protection on `main`, isolated milestone branches (`milestone/00-bootstrap`), atomic PRs with checklist verification.
  - *ADRs*: Light, version-controlled records capturing context, decisions, and consequences for architectural choices.
- **Terminology**: Monorepo, Fernet, `percentile_cont`, JWT, Conventional Commits, Root commit.
- **Example**: Git pre-push check: `git check-ignore -v .env` returns `.gitignore:2:.env`, preventing accidental leak.
- **Interview Questions & Answers**:
  1. *Q: Why choose an ingest API over an LLM gateway proxy?*
     A: Telemetry records exact client-measured tokens and latency without putting our service in the inference critical path or holding provider keys.
  2. *Q: Why store prices directly on telemetry events instead of joining with a pricing table?*
     A: Snapshotting guarantees that historical cost analytics remain immutable even when providers change token prices later.
  3. *Q: Why can't latency percentiles (p50/p95/p99) be calculated from pre-aggregated rollups?*
     A: Percentiles cannot be mathematically averaged across time buckets; raw latency samples must be retained for accurate quantile queries.
  4. *Q: How do you enforce tenant isolation in a shared database?*
     A: Centralize all database operations in workspace-scoped repositories that mandate `workspace_id` parameters on every query.
- **Practical Mistakes**: Committing `.env` before configuring `.gitignore`; averaging p95 percentiles across hourly rollups; storing raw prompts containing PII/keys.
- **Revision Summary**: Milestone 0 establishes repository scaffolding, documentation invariants, and zero-secret git discipline before writing code.
