# AEOLUS backend — instructions for Claude

Read these first, every session:
1. `docs/AEOLUS_Backend_Design_and_Handoff.md` — single source of truth (design, data model, API, build steps §11).
2. `docs/PROGRESS.md` — which steps are done, decisions made since the design, open questions.
3. `frontend/AeolusAi.html` — authority on product behaviour (field names, limits, formulas). Do not modify it before Step 9.

## Working rules
- Build **one step at a time** (design §11). Start a step by restating its goal + endpoints; end it by stopping with: files/endpoints/tables built, Postman manual-test instructions, and the pytest command. Wait for the user to say "pass" before the next step.
- At the end of every step, update `docs/PROGRESS.md`.
- The user is learning Python/FastAPI, coming from Go/Gin + PostgreSQL: explain new concepts briefly with Go analogies, tied to AEOLUS.
- **Never switch git branches.** Commit only when asked. Never commit `.env`, datasets, PDFs or model binaries.
- Do not invent results: missing data or unvalidated models → explicit `not_available` with a reason.
- No time estimates, no features outside the current step.

## Running and testing (Docker Desktop)
- Start: `docker compose up --build` (services: `db`, `redis`, `api`, `worker`). API on http://localhost:8000, Swagger at `/docs`.
- Tests: `docker compose run --rm api pytest` · Lint: `docker compose run --rm api ruff check .` and `ruff format .`
- Migrations: `docker compose run --rm api alembic revision --autogenerate -m "..."`; the API runs `alembic upgrade head` on start.
- Manual testing is in **Postman**, not `.http` files: `docs/postman/AEOLUS.postman_collection.json` + `docs/postman/AEOLUS.local.postman_environment.json` (`{{baseUrl}}`, `{{accessToken}}`). One folder per domain, named plainly (`Authentication`, `Sites`…), with **one cleanly named request per endpoint** (`Login`, `Get Current User`, `Refresh Token`). Each step's scenario requests (negative cases, flows) go in a subfolder `Step N Tests (temporary)` and are **removed only after the user says testing is done** — never before. Never commit values in the environment file.
- **API docs:** one markdown per domain in `docs/api/<domain>.md` (`health.md`, `auth.md`, …): prerequisites first, then endpoints (method, path, auth, request, response, error codes), Postman request names, a manual-test checklist, the pytest command and a code map. Write/update it in the same step as the domain.
- `uv` is not installed on the host; regenerate `uv.lock` with:
  `docker run --rm -v "D:/Projects/AEOLUS/windai-backend:/src" -w /src ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim uv lock`
  (in Git Bash prefix with `MSYS_NO_PATHCONV=1`), then `docker compose build`.

## Conventions
- Layering: router (HTTP, auth, validation) → service (logic) → repository/DB; `app/physics/` holds pure, unit-tested functions.
- JSON is camelCase via `app.schemas.base.CamelModel`; Python stays snake_case.
- Errors: raise `AppError` subclasses from `app/core/errors.py`; shape `{"error": {"code", "message", "details"}}`.
- Settings only via `app/core/config.py` (`get_settings()`); never hard-code credentials.
- Domain routers mount under `/api/v1` (`API_PREFIX` in `app/main.py`).
