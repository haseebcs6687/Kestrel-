# Engineering Learning Notes

## Standard Note Format
Each entry follows: Concept | Definition | Why it matters | How we used it | Architecture | Important terminology | Example | Interview questions (3-5) | Practical mistakes | Revision summary.

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
