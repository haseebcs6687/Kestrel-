# Security Architecture & Policies — Kestrel AI Control Center

## 1. Overview
Kestrel AI Control Center is a multi-tenant observability and operations control center for LLM-powered applications. Because it handles organizational usage metrics, provider credentials, and access controls, security invariants are embedded directly into the software architecture and developer workflow.

---

## 2. Authentication & Credential Architecture

### 2.1 Password Hashing (Argon2id)
- **Algorithm**: Argon2id via `argon2-cffi` using RFC 9106 recommended defaults (memory-hard, resistant to GPU/ASIC cracking).
- **Password Policies**: Minimum 12 characters, maximum 128 characters. No arbitrary composition rules that encourage predictable patterns.
- **Timing Attack Mitigation**: When login fails due to a nonexistent email, `authenticate()` performs a dummy verification against a pre-hashed random value (`get_dummy_hash()`). This equalizes CPU execution time and prevents email enumeration (ADR-023).
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

### 2.4 Sessions & Refresh Token Rotation (ADR-024, ADR-026)
- **Cryptographic Storage**: Refresh tokens are 288-bit URL-safe random strings generated via `secrets.token_urlsafe(48)`. Only deterministic SHA-256 digests (`token_hash`) are persisted in PostgreSQL; plaintext tokens are never stored.
- **HttpOnly Cookie Delivery**: Refresh tokens are transmitted exclusively via an `HttpOnly`, `Path=/api/v1/auth`, `SameSite=Strict`, `Secure` (auto-enabled in production) cookie (`kestrel_refresh`). JavaScript has no programmatic access to the token.
- **Strict Rotation**: On every `/refresh` call, the presented refresh token is revoked, its `replaced_by_id` pointer is set to the successor token, and a fresh access/refresh pair is issued.
- **Automatic Reuse Detection**: If an already revoked refresh token is presented, Kestrel treats it as active session theft. The entire rotation family (`family_id`) is instantly revoked in a committed transaction, an audit alert is recorded (`auth.refresh_reuse_detected`), and the client receives a generic 401 with a cleared cookie.
- **Cookie Clearance**: Logging out or encountering an expired, invalid, or reused refresh token automatically instructs the browser to delete the cookie (`Max-Age=0`).

---

## 3. Operational & Security Audit Trail (ADR-025, ADR-027)

- **PostgreSQL Audit Log**: Immutable append-only operational history stored in `audit_logs` table with primary key `BIGINT GENERATED ALWAYS AS IDENTITY`, foreign key `ON DELETE RESTRICT` on `workspace_id` to guarantee audit trail permanence, `ON DELETE SET NULL` on `actor_user_id`, and composite index `(workspace_id, created_at DESC)`.
- **Recorded Security Events**:
  - `auth.register`: User and organization account initialization.
  - `auth.login`: User authentication success.
  - `auth.refresh`: Session rotation and access token reissue.
  - `auth.refresh_reuse_detected`: Security alarm triggering token family invalidation.
  - `auth.logout`: Session family revocation and cookie cleanup.
- **Request-ID Correlation**: Automatically binds the active `structlog` request UUID to audit rows (`VARCHAR(64)` supporting full 64-character IDs) for cross-tier log and trace correlation.
- **Omission of Unvalidated IP/User-Agent**: Client IP address and User-Agent headers are deliberately omitted from audit rows pending an explicit reverse-proxy trusted-header derivation design.
- **Defense-in-Depth Sanitization**: Audit recording service validates all `details` payload dictionaries, throwing an exception if any sensitive security keys or substrings (`password`, `token`, `secret`, `cookie`, `authorization`, `hash`) are detected. Details default to `{}` when not provided.
- **Transactional Consistency**: Standard audit events flush within the caller's database transaction, rolling back automatically if the business operation aborts. Security violations (e.g. reuse detection) execute in an explicit committed transaction to ensure immediate revocation.

---

## 4. Multi-Tenant Data Isolation (ADR-022)

Kestrel uses a shared-database, shared-schema multi-tenancy model isolated at the row level via foreign keys to `workspaces(id)`:
- **`WorkspaceScopedRepository`**: All tenant-aware repositories inherit from `app.core.tenancy.WorkspaceScopedRepository`.
- **Automatic Scoping**: Query methods apply `scope(statement, Model)` which binds `Model.workspace_id == self.workspace_id`.
- **Unscoped Exception**: Only initial email login (`get_user_by_email`) and token decoding (`get_user_by_id`) operate unscoped because the requesting workspace is not yet known.
- **Foreign Key Invariant**: Relational models enforce `ON DELETE RESTRICT` on workspace associations for core accounts and audit logs, with cascading session cleanups.

---

## 5. User Management Security Architecture (ADR-030, ADR-031)

### 5.1 Admin Trust Model
- Workspace administrators (`role = 'admin'`) hold full administrative authority over their tenant workspace: provisioning new users (`POST /api/v1/users`), reading user details (`GET /api/v1/users/{user_id}`), modifying roles and active states (`PATCH /api/v1/users/{user_id}`), and resetting user passwords (`PUT /api/v1/users/{user_id}/password`).
- Viewers (`role = 'viewer'`) possess strictly read-only access to monitoring dashboards and cannot access user management endpoints (enforced via `AdminUser` dependency returning HTTP 403 Forbidden).

### 5.2 Deactivation Instead of Deletion (ADR-030)
- User accounts are **never hard-deleted** from PostgreSQL.
- Offboarding is accomplished exclusively by setting `is_active = false`.
- **Audit Preservation**: Soft deactivation ensures historical audit records (`audit_logs.actor_user_id`) remain intact, relational foreign keys remain valid, and forensic attribution is preserved indefinitely.
- **Immediate Rejection**: `get_current_user` evaluates `user.is_active` on every authenticated request, instantly rejecting deactivated users with HTTP 401 Unauthorized regardless of JWT expiration.

### 5.3 Last-Active-Admin Invariant & Concurrency Protection (ADR-030)
- A tenant workspace must never become orphaned without an active administrator.
- `update_user` strictly forbids demoting or deactivating a workspace's sole remaining active admin, returning HTTP 409 Conflict (`Cannot remove the last active admin`).
- **Workspace Row Lock**: To eliminate race conditions where two administrators simultaneously demote or deactivate each other, the operation acquires an exclusive row lock on the workspace (`SELECT id FROM workspaces WHERE id = :workspace_id FOR UPDATE` via `lock_workspace(db, workspace_id)`) before evaluating the count of active administrators.

### 5.4 Multi-Tenant 404 Isolation (ADR-030)
- To prevent cross-tenant user ID enumeration, any request targeting a `user_id` outside the authenticated caller's workspace returns HTTP 404 Not Found, never HTTP 403 Forbidden.
- An administrator cannot discern whether a user ID belongs to another tenant or does not exist at all.

### 5.5 Session Revocation & Password Lifecycle (ADR-031)
- **Session Termination on Lifecycle Events**: Whenever a user is deactivated, has their password reset by an admin, or changes their own password, all active refresh tokens for that user across all session families are immediately revoked (`revoke_all_user_tokens(db, user_id)`).
- **Self-Service Password Change**: `POST /api/v1/auth/change-password` requires verification of `current_password`, clears the caller's refresh token cookie, and records an `auth.password_change` audit event. Submitting an incorrect current password returns HTTP 400 Bad Request, distinguishing input validation errors from missing/invalid JWTs (HTTP 401). Submitting the same password is also rejected with HTTP 400.

---

## 6. Frontend Security Contract

- **Access Token In-Memory Only (ADR-018)**: Short-lived access tokens (15-minute lifespan) are retained strictly in JavaScript application memory (React state/context). They must **never** be written to `localStorage`, `sessionStorage`, or client-side storage.
- **Cookie Handling**: Browsers manage the `kestrel_refresh` cookie automatically. The client application code cannot and should not attempt to read or modify it.
- **CSRF Defense-in-Depth**: Because refresh cookies use `SameSite=Strict`, cross-site requests are blocked by modern browsers. For defense-in-depth, `/api/v1/auth/refresh` and `/api/v1/auth/logout` require the custom header `X-Kestrel-Client: web`. Cross-origin HTML forms and scripts cannot set custom headers without CORS preflight approval.
- **Silent Refresh Strategy**: The frontend schedules silent background refreshes at 80–90% of token lifespan (e.g., at minute 13 of a 15-minute token) by querying `/api/v1/auth/refresh`.
- **Logout Flow**: Calling `/api/v1/auth/logout` drops the in-memory access token, revokes the server-side session family, and receives a cookie deletion instruction.

---

## 7. Input Validation & Mass-Assignment Protection

- **Pydantic Validation**: All request models use Pydantic v2 schemas with `ConfigDict(extra="forbid")`.
- **Mass Assignment Defense**: In `RegisterRequest` and user management schemas, attempting to submit unauthorized fields (`role`, `is_active`, `workspace_id`) triggers an immediate HTTP 422 error.
- **Email Normalization**: Emails are stripped and converted to lowercase before database persistence; enforced at the PostgreSQL layer by `CHECK (email = lower(email))`.

---

## 8. Secret Hygiene & Defense-in-Depth

- **Pydantic `SecretStr`**: Sensitive settings (`postgres_password`, `jwt_secret_key`) use `SecretStr`, which masks output in logs, exceptions, and `repr()`.
- **Secret Scanning Quality Gate (ADR-029)**: Every commit and push requires automated regex and literal scans via `python scripts/secret_scan.py` for database passwords, JWT secrets, forbidden `.env*` files, private keys, and provider API key prefixes (`sk-`, `AIza`, `gsk_`). In CI, this is backed up by `gitleaks/gitleaks-action@v3`.
- **Startup Protection**: If `JWT_SECRET_KEY` is missing, shorter than 32 characters, or contains the placeholder `change_me`, the application refuses to start.
- **No-Cache Headers**: Authentication responses set `Cache-Control: no-store` and `Pragma: no-cache` to prevent reverse proxies or browser caches from storing tokens.

---

## 9. Known Security Gaps & Planned Roadmap

| Area | Current Status | Planned Mitigation | Milestone |
|---|---|---|---|
| **Rate Limiting** | Known gap; no rate limits on `/auth/login`, `/auth/register`, `/auth/change-password`, or `/users` | Slowapi / Redis sliding-window rate limiting on auth and user routes | Milestone 13 |
| **Email Disclosure at Creation** | Known trade-off; 409 Conflict reveals registered email existence | User creation is admin-restricted; accepted trade-off for direct provisioning | Milestone 7 |
| **JWT Lifespan after Password Change** | Known trade-off; unexpired JWT (<= 15 min) remains valid until expiry; all refresh tokens revoked immediately | Acceptable for short-lived JWTs (15 min); instant deactivation blocks all requests | Milestone 7 |
| **Forced Password Reset** | Not yet implemented; temporary admin-set passwords have no forced reset flag | Add `must_change_password` boolean on user model requiring immediate reset | Future Milestone |
| **Email Invitations & Verification** | Not yet implemented; direct admin provisioning only | Asynchronous email dispatch with signed, expiring invitation tokens | Future Milestone |
| **Refresh Tokens** | **Resolved** (Milestone 5) | HttpOnly rotating cookies with reuse detection (ADR-024, ADR-026) | Milestone 5 |
| **Session Revocation** | **Resolved** (Milestone 5, 7) | Family invalidation on logout, reuse detection, deactivation, and password change | Milestone 5 / 7 |
| **Audit Logs** | **Resolved** (Milestone 5b, 7) | Canonical `audit_logs` (migration 0003), 64-char request-ID, recursive sanitization | Milestone 5b / 7 |
| **User Management & RBAC** | **Resolved** (Milestone 7) | Admin CRUD, workspace row lock on last admin, 404 tenant isolation (ADR-030/031) | Milestone 7 |
| **Secret Scanning** | **Resolved** (Milestone 6) | In-repo `scripts/secret_scan.py` pre-push gate + Gitleaks action in CI (ADR-029) | Milestone 6 |
| **Dependency Vulnerability Scanning** | **Resolved (Advisory in CI)** (Milestone 6) | `uv export` + `uvx pip-audit` advisory job in GitHub Actions CI (ADR-029) | Milestone 6 |
| **CORS** | Restrictive default (same-origin) | Configured explicitly when frontend origin is scaffolded | Milestone 13/14 |
| **API Keys** | Not yet implemented | SHA-256 hashed ingestion keys with prefix display (`kst_live_`) | Milestone 8 |
| **CI Action Pinning** | Planned | Pin third-party GitHub Actions to full immutable commit SHAs | Future Milestone |
| **Automated Dependency Updates** | Planned | Dependabot or Renovate for automated pull requests on vulnerable dependencies | Future Milestone |
| **Self-Service Password Reset via Email**| Not yet implemented | Time-limited signed reset tokens dispatched via email service | Future Milestone |
