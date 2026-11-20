# AEOLUS backend — progress log

Updated at the end of every step. Design: `docs/AEOLUS_Backend_Design_and_Handoff.md` §11.

## Step status

| Step | Name | Status |
|---|---|---|
| 0 | setup | ✅ Passed (manual Postman test + 17 pytest) — 2026-11-19 |
| 1 | auth | ✅ Passed (manual Postman test + 68 pytest) — 2026-11-20 |
| 2 | turbines | ⏭ Next |
| 3 | sites | — |
| 4 | datasets | — |
| 5 | resource | — |
| 6 | assessments | — |
| 7 | climate | — |
| 8 | reports | — |
| 9 | integrate | — |

## Step 0 — setup (done)
- Docker Compose: `db` (postgis/postgis:16-3.5), `redis` (7-alpine), `api` (uvicorn --reload, runs `alembic upgrade head` on start), `worker` (Celery, no-op `aeolus.ping` task).
- Python 3.12 + `uv` (`pyproject.toml`, `uv.lock`); venv at `/opt/venv` inside the image so the `.:/app` bind mount doesn't hide it.
- `app/core/config.py` (pydantic-settings; `JWT_SECRET` ≥ 32 chars required; `CORS_ORIGINS` comma-separated, `*` rejected; `postgresql://` auto-switched to `postgresql+psycopg://`).
- `app/core/errors.py` (unified error shape), `app/core/logging.py` (JSON lines + `X-Request-ID`).
- Alembic migration `0001` enables PostGIS; `env.py` ignores PostGIS-owned tables (tiger/topology, `spatial_ref_sys`).
- `GET /health` → `{status, db, redis, version}`; 503 + `degraded` when a dependency is down.
- Tests: `tests/test_health.py`, `test_errors.py`, `test_config.py`.

## Step 1 — auth (done)
- Deps: `pwdlib[argon2]` (Argon2id), `pyjwt`, `slowapi`.
- Tables (migration `0002`): `users` (email unique, stored lower-case), `refresh_tokens` (SHA-256 hash only, `family_id`, `replaced_by_id`, `expires_at`, `revoked_at`).
- `app/core/security.py` (hash/verify, HS256 access JWT with `iss`/`type`, refresh-token helpers), `app/core/rate_limit.py`, `app/services/auth_service.py`, `app/api/deps.py` (`get_current_user`, `CurrentUser`, `DbSession`), `app/api/routers/auth.py`, `app/cli.py` (`create-admin [--reset-password] [--email]`).
- Endpoints `/api/v1/auth`: `POST /login`, `POST /refresh`, `POST /logout` (bearer + `{refreshToken}`, 204), `GET /me`, `POST /change-password` (204).
- First-start bootstrap from `ADMIN_EMAIL`/`ADMIN_PASSWORD` in the API lifespan; blank values = unset.
- Tests: `test_security.py`, `test_auth_api.py`, `test_admin_setup.py`, `test_migrations.py` (models ↔ migrations in sync). Postman folder `Authentication` (temporary test requests removed after the user's test). Docs: `docs/api/auth.md`.

## Decisions made after the design doc
- **Manual testing in Postman** (`docs/postman/`), one folder per domain, one cleanly named request per endpoint — replaces the design's `http/*.http` files.
- **API docs per domain** in `docs/api/<domain>.md` (`health.md`, `auth.md` so far), written in the step that builds the domain.
- **Database:** `DATABASE_URL` in `.env` chooses it. Empty → local Docker `db`; set → hosted (user plans **Neon**, using the *direct* URL without `-pooler`). Pooler not needed for v0.1; if ever added, use a separate direct `MIGRATION_DATABASE_URL` for Alembic and `prepare_threshold=None`.
- **Tests use the local Docker DB**, never Neon: `TEST_DATABASE_URL` (compose) → `<POSTGRES_DB>_test` in the `db` container; `tests/conftest.py` overrides `DATABASE_URL`, refuses any non-local or non-`_test` DB, auto-creates + migrates it, truncates before each DB test.
- **Auth details (Step 1):** table names `users` / `refresh_tokens` (`user` is reserved in PG). Refresh tokens are opaque random strings (not JWTs). Rotation with **reuse detection** — replaying a rotated token revokes its whole family. Rotation slides the 7-day expiry. Logout and change-password revoke refresh tokens only; an already-issued access JWT stays valid until it expires (≤ 30 min). Wrong current password on change-password → **400** `INVALID_CURRENT_PASSWORD` (not 401, so clients don't treat it as logged-out). Password policy **6–128 chars** (team decision 2026-11-20; design §9 said ≥ 12 — lowered for convenience, login rate limit is the main guard against guessing). Error codes: `INVALID_CREDENTIALS`, `NOT_AUTHENTICATED`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `INVALID_REFRESH_TOKEN`, `PASSWORD_UNCHANGED`, `RATE_LIMITED` (+ `Retry-After: 60`).
- **Rate limit** `LOGIN_RATE_LIMIT=5/minute` per IP on login and change-password; in-memory storage (single API process; counters reset on restart). Switch slowapi to Redis storage if the API ever runs multiple processes.
- **Local Docker DB published on host port 5433** (a local Postgres already uses 5432).
- **No object storage (S3/R2) in v0.1** — files live in Docker volumes (`/data/cache`, `/data/models`, `/data/artifacts`); raw datasets bind-mounted read-only from `HOST_DATA_DIR`.
- Frontend reference copy in `frontend/AeolusAi.html`; original frontend handoff in `docs/AEOLUS_frontend_handoff.md` (where it conflicts with the design doc — e.g. nested assessment routes, backend forecast proxy — the design doc wins).
- New-site defaults for Step 3 (not in design): frontend's `addSite` values — radius 1800, count 12, model `g45`, layoutDir 270.

## Open questions (ask when the step arrives)
- Step 3: Cox's Bazar radius / count / class to match the sample report.
- Step 4: dataset folder path (`HOST_DATA_DIR`), formats, variables, years, grid, bbox.
- Step 7: length of ERA5 record available for climate training.
- Step 9: real frontend origin for `CORS_ORIGINS`.
