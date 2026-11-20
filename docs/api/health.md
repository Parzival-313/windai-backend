# Health — `/health`

Checks that the API, the database (with PostGIS) and Redis are reachable. No auth. It is not
under `/api/v1`, so monitoring tools can call it without knowing the API version.

| Endpoint | Postman request | Auth |
|---|---|---|
| `GET /health` | Health Check | none |

Postman: folder **Health** in `docs/postman/AEOLUS.postman_collection.json`.

## Health Check — `GET /health`

Response `200` when everything is up:

```json
{ "status": "ok", "db": "ok", "redis": "ok", "version": "0.1.0" }
```

Response `503` when a dependency is down:

```json
{ "status": "degraded", "db": "ok", "redis": "down", "version": "0.1.0" }
```

Every response also carries an `X-Request-ID` header. Send your own `X-Request-ID` and it is echoed
back, which makes it easy to find the matching line in `docker compose logs api`.

## Manual test checklist

| # | Do this | Expect |
|---|---|---|
| 1 | `docker compose up --build`, send Health Check | 200, `db` and `redis` are `ok` |
| 2 | `docker compose stop redis`, send Health Check | 503, `redis: "down"` |
| 3 | `docker compose start redis`, send Health Check | 200 again |
| 4 | Send any unknown URL, e.g. `GET {{baseUrl}}/api/v1/does-not-exist` | 404 with `{"error": {"code": "NOT_FOUND", …}}` |

## Automated tests

```powershell
docker compose run --rm api pytest tests/test_health.py tests/test_errors.py
```

## Code map

| Layer | File |
|---|---|
| Route | `app/api/routers/health.py` |
| Checks | `app/services/health_service.py` |
| Error shape | `app/core/errors.py` |
