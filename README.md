# windai-backend (AEOLUS)

Backend for **AEOLUS**, a browser-based wind-farm screening tool and 3D digital twin for
Bangladesh: long-term ERA5 wind resource, generic-turbine energy yield with wakes,
P50/P75/P90, an optional ENSO + IOD climate adjustment and a PDF report.
Outputs are **screening-level, not bankable**.

- Design / source of truth: [docs/AEOLUS_Backend_Design_and_Handoff.md](docs/AEOLUS_Backend_Design_and_Handoff.md)
- Frontend reference copy: [frontend/AeolusAi.html](frontend/AeolusAi.html)

## Stack

FastAPI · PostgreSQL 16 + PostGIS · SQLAlchemy 2 + Alembic · Celery + Redis · Docker Compose · `uv`

## Run locally (Docker Desktop)

1. Copy the env template and fill in at least `JWT_SECRET` (≥ 32 chars) and `POSTGRES_PASSWORD`:

   ```powershell
   Copy-Item .env.example .env
   ```

   Generate a secret:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

2. Build and start everything (`db`, `redis`, `api`, `worker`):

   ```powershell
   docker compose up --build
   ```

   The API runs migrations on start, then serves on <http://localhost:8000>
   (Swagger: <http://localhost:8000/docs>). Code under `app/` reloads automatically.

3. Stop: `docker compose down` (add `-v` to also wipe the database volume).

### Database: local Docker or Neon

`DATABASE_URL` in `.env` decides:

- **empty** → the local `db` container (default; use this for development and tests)
- **a hosted URL** → e.g. Neon: copy *Connection string* (pooling off) and paste it as one line:
  `DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx.REGION.aws.neon.tech/neondb?sslmode=require`

Then restart: `docker compose up -d --force-recreate api worker`. Migrations (incl. PostGIS)
run on API start; `GET /health` shows `db: ok` when connected.

Host ports: API `8000`, Postgres `5433` (not 5432, to avoid a local Postgres), Redis `6379`.
Change them in `.env` (`API_HOST_PORT`, `DB_HOST_PORT`, `REDIS_HOST_PORT`).

## Admin user (single user, no sign-up)

Create it once, interactively (the password is never echoed or passed as a flag):

```powershell
docker compose exec api python -m app.cli create-admin
```

Forgot the password? `docker compose exec api python -m app.cli create-admin --reset-password`
(also logs out every device). Alternative for a fresh Docker setup: set `ADMIN_EMAIL` and
`ADMIN_PASSWORD` in `.env`; the API creates the admin on start if none exists — then delete
`ADMIN_PASSWORD` from `.env`.

Log in with `POST /api/v1/auth/login`, then use the `accessToken` as `Authorization: Bearer …`
(Swagger: **Authorize** button).

## Manual testing with Postman

Import both files from [docs/postman/](docs/postman/):

- `AEOLUS.postman_collection.json` — one folder per build step
- `AEOLUS.local.postman_environment.json` — select the **AEOLUS local** environment

## Automated tests

```powershell
docker compose run --rm api pytest
```

Tests always use a separate local database, `<POSTGRES_DB>_test` in the `db` container
(`TEST_DATABASE_URL`, set by compose) — never `DATABASE_URL`/Neon. It is created and
migrated automatically, and emptied before each DB test.

Lint:

```powershell
docker compose run --rm api ruff check .
```

## Database migrations (Alembic)

```powershell
docker compose run --rm api alembic upgrade head
```

```powershell
docker compose run --rm api alembic revision --autogenerate -m "describe change"
```

## Layout

```
app/           main.py · core/ · db/ · models/ · schemas/ · api/ · services/ · physics/ · data/ · ml/ · worker/ · reports/
alembic/       migrations
tests/         pytest
docs/          design documents, PROGRESS.md
docs/api/      one markdown per API domain (endpoints, errors, manual-test steps)
docs/postman/  Postman collection + environment
frontend/      AeolusAi.html (reference copy)
data/          default mount for raw datasets (git-ignored)
```
