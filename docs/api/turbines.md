# Turbine Classes — `/api/v1/turbine-classes`

The three generic turbine classes (`g36`, `g45`, `g62`) and their power curves. The values are the
frontend's `MODELS` object in `frontend/AeolusAi.html`, and the power formula is its `powerKW`
function. The data is read-only: it is created by a migration and cannot be changed through the API.

> **Placeholder values.** The frontend's numbers are dummies (its design is correct, its numbers
> are not), so the three classes below are **placeholders**, not real turbine specifications.
> Decision 2026-11-20: keep them for Step 2 and replace them with a new migration before Step 5,
> which is the first step that uses hub height for real results. The table, endpoints and
> field names stay the same.

| Endpoint | Postman request | Auth |
|---|---|---|
| `GET /api/v1/turbine-classes` | List Turbine Classes | Bearer |
| `GET /api/v1/turbine-classes/{id}` | Get Turbine Class | Bearer |
| `GET /api/v1/turbine-classes/{id}/power-curve` | Get Power Curve | Bearer |

Postman: folder **Turbine Classes** in `docs/postman/postman_collection.json`.

---

## 1. Before you start

1. **Apply the migration.** The table `turbine_classes` and its three rows come from migration
   `0003`. The API runs `alembic upgrade head` when it starts, so restart it once:

   ```powershell
   docker compose restart api
   ```

   This migrates whichever database `DATABASE_URL` in `.env` points to (Neon if it is set).
   Check with `docker compose exec api alembic current`, which should print `0003 (head)`.
2. **Log in.** Every endpoint needs a bearer token: send **Login** in the *Authentication* folder
   first (see `docs/api/auth.md`).

## 2. The classes

| id | name | D (m) | H (m) | rated (kW) | vin | vr | vout (m/s) | rpm min–max |
|---|---|---|---|---|---|---|---|---|
| g36 | 3.6 MW class | 120 | 90 | 3600 | 3 | 11.5 | 25 | 5.5–14.9 |
| g45 | 4.5 MW class | 145 | 105 | 4500 | 3 | 11 | 25 | 4.8–12.3 |
| g62 | 6.2 MW class | 170 | 125 | 6200 | 3 | 10.5 | 25 | 4.0–10.6 |

**Power curve** (same as the frontend's `powerKW`):

```
P(v) = 0                                          if v < vin or v >= vout
     = rated                                      if v >= vr
     = rated * (v³ − vin³) / (vr³ − vin³)         otherwise
```

**Thrust coefficient `ct`** (used by the wake model in Step 6). The frontend has no thrust
curve, so this is a generic assumption from the design: `0.8` from `vin` up to `vr`, then
`0.8 · (vr / v)³` (never below `0.05`) up to `vout`, and `0` when the turbine is not running
(`v < vin` or `v >= vout`).

---

## 3. Endpoints

Errors shared by every endpoint here:

| Status | `error.code` | When |
|---|---|---|
| 401 | `NOT_AUTHENTICATED` | No `Authorization` header. |
| 401 | `TOKEN_EXPIRED` | Access token is older than 30 min. Send **Refresh Token**. |
| 401 | `INVALID_TOKEN` | Token is malformed or has a bad signature. |

### List Turbine Classes — `GET /api/v1/turbine-classes`

No body. Response `200`, smallest class first:

```json
[
  { "id": "g36", "name": "3.6 MW class", "D": 120, "H": 90,  "rated": 3600, "vin": 3.0, "vr": 11.5, "vout": 25.0, "rpmMin": 5.5, "rpmMax": 14.9 },
  { "id": "g45", "name": "4.5 MW class", "D": 145, "H": 105, "rated": 4500, "vin": 3.0, "vr": 11.0, "vout": 25.0, "rpmMin": 4.8, "rpmMax": 12.3 },
  { "id": "g62", "name": "6.2 MW class", "D": 170, "H": 125, "rated": 6200, "vin": 3.0, "vr": 10.5, "vout": 25.0, "rpmMin": 4.0, "rpmMax": 10.6 }
]
```

The field names are the frontend's own `MODELS` keys, so in Step 9 the browser can use these
objects in place of its hard-coded `MODELS`:

| JSON field | Meaning | Unit |
|---|---|---|
| `D` | rotor diameter | m |
| `H` | hub height | m |
| `rated` | rated power | kW |
| `vin` / `vr` / `vout` | cut-in / rated / cut-out wind speed | m/s |
| `rpmMin` / `rpmMax` | rotor speed range | rpm |

### Get Turbine Class — `GET /api/v1/turbine-classes/{id}`

`id` is `g36`, `g45` or `g62`. It is case-sensitive: `G45` is not found.

Response `200`: one object, same shape as a list item.

| Status | `error.code` | When |
|---|---|---|
| 404 | `TURBINE_CLASS_NOT_FOUND` | Unknown id. `details` is `{"id": "<what you sent>"}`. |

### Get Power Curve — `GET /api/v1/turbine-classes/{id}/power-curve?step=0.5`

| Query | Default | Allowed | Meaning |
|---|---|---|---|
| `step` | `0.5` | 0.1 – 5 | Speed step in m/s. |

Speeds are `0, step, 2·step, …` up to 30 m/s. 30 is included when it is a multiple of `step`
(`step=0.5` gives 61 points, `step=0.1` gives 301; `step=0.7` stops at 29.4).

Response `200`:

```json
[
  { "speed": 0.0,  "powerKw": 0.0,              "ct": 0.0 },
  { "speed": 3.0,  "powerKw": 0.0,              "ct": 0.8 },
  { "speed": 7.0,  "powerKw": 1090.4907975460123, "ct": 0.8 },
  { "speed": 11.0, "powerKw": 4500.0,           "ct": 0.8 },
  { "speed": 12.0, "powerKw": 4500.0,           "ct": 0.6162037037037037 },
  { "speed": 25.0, "powerKw": 0.0,              "ct": 0.0 }
]
```

(Excerpt for `g45`. The real response has every step.) At exactly `vin` the power is 0, because
`v³ − vin³ = 0`, but the turbine counts as running, so `ct` is 0.8.

| Status | `error.code` | When |
|---|---|---|
| 404 | `TURBINE_CLASS_NOT_FOUND` | Unknown id. |
| 422 | `VALIDATION_ERROR` | `step` is not a number, below 0.1 or above 5 (`details.fields[0].field` = `query.step`). |

---

## 4. Manual test checklist

Send **Login** first. Change the `id` path variable or the `step` query in the request to try
the other cases.

| # | Do this in Postman | Expect |
|---|---|---|
| 1 | List Turbine Classes | 200, three classes with the numbers in the table in §2 |
| 2 | List Turbine Classes with Auth set to *No Auth* | 401 `NOT_AUTHENTICATED` |
| 3 | Get Turbine Class (id `g45`) | 200, `D` 145, `H` 105, `rated` 4500 |
| 4 | Get Power Curve (id `g45`), look at speeds 3, 7, 11, 25 | 0, 1090.49, 4500, 0 kW |
| 5 | Get Power Curve with `step=0.1` | 301 points |
| 6 | Get Power Curve with `step=0.05`, then `step=6` | 422 `VALIDATION_ERROR` |
| 7 | Get Turbine Class with id `g99`, then `G45` | 404 `TURBINE_CLASS_NOT_FOUND` |

## 5. Automated tests

```powershell
docker compose run --rm api pytest tests/test_power.py tests/test_turbines_api.py
```

`test_power.py` checks `power_kw` against `tests/fixtures/turbine_classes_js.json`, which Node
generates by running the frontend's own `MODELS` and `powerKW` code. A test also fails if that
code in `AeolusAi.html` changes after the fixture was made. To regenerate it (host, Node 18+):

```powershell
node tests/fixtures/make_turbine_fixture.mjs
```

If the `MODELS` values themselves change, also add a new migration that updates `turbine_classes`.

## 6. Code map

| Layer | File |
|---|---|
| Routes | `app/api/routers/turbines.py` |
| Logic (lookup, 404, curve sampling) | `app/services/turbine_service.py` |
| `power_kw`, `ct`, `curve_speeds` (pure functions) | `app/physics/power.py` |
| Response schemas (frontend field names) | `app/schemas/turbines.py` |
| Table `turbine_classes` | `app/models/turbine_class.py`, migration `0003` (creates and seeds it) |
| JS parity fixture + generator | `tests/fixtures/turbine_classes_js.json`, `tests/fixtures/make_turbine_fixture.mjs` |
