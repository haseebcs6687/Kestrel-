# Security Architecture & Policies — Kestrel AI Control Center

## 1. Overview
Kestrel AI Control Center is a multi-tenant observability and operations control center for LLM-powered applications. Because it handles organizational usage metrics, provider credentials, and access controls, security invariants are embedded directly into the software architecture and developer workflow.

---

## 2. Authentication & Credential Architecture

### 2.1 Password Hashing (Argon2id)
- **Algorithm**: Argon2id via `argon2-cffi` using RFC 9106 recommended defaults (memory-hard, resistant to GPU/ASIC cracking).
- **Password Policies**: Minimum 12 characters, maximum 128 characters. No arbitrary composition rules that encourage predictable patterns.
- **Timing Attack Mitigation**: When login fails due to a nonexistent email, `authenticate()` performs a dummy verification against a pre-hashed random value (`get_dummy_hash()`). This equalizes CPU execution time and prevents email enumeration.
- **Rehashing**: The system inspects `password_needs_rehash()` on every successful login and automatically updates hashes if algorithm parameters evolve.

### 2.2 Access Tokens (JWT)
- **Signature Algorithm**: HMAC-SHA256 (`HS256`).
- **Security Constants (ADR-020)**:
  - `JWT_ALGORITHM`: `"HS256"` (hardcoded constant in code; never read from user input or token headers).
  - `JWT_ISSUER`: `"kestrel"`.
  - `JWT_AUDIENCE`: `"kestrel-api"`.
- **Claim Design (ADR-021)**: Access tokens contain only:
  - `sub`: User UUID string
  - `iat`: Issued-at Unix timestamp
  - `exp`: Expiration Unix timestamp (default 15 minutes, configurable 1..60)
  - `iss`: Issuer (`kestrel`)
  - `aud`: Audience (`kestrel-api`)
  - `typ`: Token type (`access`)
- **Claim Minimization**: Role, email, and workspace identifier are **deliberately excluded** from the token payload.

### 2.3 Database-Backed Dynamic Authorization (ADR-021)
All authenticated requests decode the user UUID from `sub` and query PostgreSQL directly:
1. Verifies that the user still exists.
2. Verifies that `is_active` is `true`. Deactivated users are blocked immediately, even with unexpired JWTs.
3. Retrieves current `role` (`admin` vs `viewer`) and `workspace_id` fresh from the database.

---

## 3. Multi-Tenant Data Isolation (ADR-022)

Kestrel uses a shared-database, shared-schema multi-tenancy model isolated at the row level via foreign keys to `workspaces(id)`:
- **`WorkspaceScopedRepository`**: All tenant-aware repositories inherit from `app.core.tenancy.WorkspaceScopedRepository`.
- **Automatic Scoping**: Query methods apply `scope(statement, Model)` which binds `Model.workspace_id == self.workspace_id`.
- **Unscoped Exception**: Only initial email login (`get_user_by_email`) and token decoding (`get_user_by_id`) operate unscoped because the requesting workspace is not yet known.
- **Foreign Key Invariant**: Relational models enforce `ON DELETE RESTRICT` on `workspace_id` to prevent cascading multi-tenant deletion accidents.

---

## 4. Input Validation & Mass-Assignment Protection

- **Pydantic Validation**: All request models use Pydantic v2 schemas with `ConfigDict(extra="forbid")`.
- **Mass Assignment Defense**: In `RegisterRequest`, attempting to submit unauthorized fields (`role`, `is_active`, `workspace_id`) triggers an immediate HTTP 422 error.
- **Email Normalization**: Emails are stripped and converted to lowercase before database persistence; enforced at the PostgreSQL layer by `CHECK (email = lower(email))`.

---

## 5. Secret Hygiene & Defense-in-Depth

- **Pydantic `SecretStr`**: Sensitive settings (`postgres_password`, `jwt_secret_key`) use `SecretStr`, which masks output in logs, exceptions, and `repr()`.
- **Secret Scanning Quality Gate**: Every commit and push requires automated regex and literal scans for database passwords, JWT secrets, and provider API key prefixes (`sk-`, `AIza`, `gsk_`).
- **Startup Protection**: If `JWT_SECRET_KEY` is missing, shorter than 32 characters, or contains the placeholder `change_me`, the application refuses to start.
- **No-Cache Headers**: Authentication responses set `Cache-Control: no-store` and `Pragma: no-cache` to prevent reverse proxies or browser caches from storing tokens.

---

## 6. Known Security Gaps & Planned Roadmap

| Area | Current Status | Planned Mitigation | Milestone |
|---|---|---|---|
| **Rate Limiting** | Known gap; no rate limits on `/auth/login` or `/auth/register` | Slowapi / Redis sliding-window rate limiting on public auth endpoints | Milestone 5/6 |
| **Refresh Tokens** | Stateless 15-minute access tokens only; no refresh tokens | Secure HTTP-only cookies with rotating refresh token hashes | Future Session Milestone |
| **Session Revocation** | Immediate account deactivation via DB check | Token blacklist / versioning for instant single-session logout | Future Session Milestone |
| **CORS** | Restrictive default | Configured explicitly when frontend origin is scaffolded | Milestone 8 |
| **API Keys** | Not yet implemented | SHA-256 hashed ingestion keys with prefix display (`kst_live_`) | Milestone 5 |
| **Audit Logs** | Schema planned | Automatic recording of security-critical actions in `audit_logs` | Audit Milestone |
