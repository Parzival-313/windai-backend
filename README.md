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

Host ports: API `8000`, Postgres `5433` (not 5432, to avoid a local Postgres), Redis `6379`.
Change them in `.env` (`API_HOST_PORT`, `DB_HOST_PORT`, `REDIS_HOST_PORT`).

## Manual testing with Postman

Import both files from [postman/](postman/):

- `AEOLUS.postman_collection.json` — one folder per build step
- `AEOLUS.local.postman_environment.json` — select the **AEOLUS local** environment

## Automated tests

```powershell
docker compose run --rm api pytest
```

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
app/        main.py · core/ · db/ · models/ · schemas/ · api/ · services/ · physics/ · data/ · ml/ · worker/ · reports/
alembic/    migrations
tests/      pytest
postman/    Postman collection + environment
frontend/   AeolusAi.html (reference copy)
docs/       design documents
data/       default mount for raw datasets (git-ignored)
```
