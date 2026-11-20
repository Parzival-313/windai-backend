# Authentication — `/api/v1/auth`

One admin account for the whole team, with no sign-up. Every other domain needs the access token
from **Login** in an `Authorization: Bearer <accessToken>` header.

| Endpoint | Postman request | Auth |
|---|---|---|
| `POST /api/v1/auth/login` | Login | none (rate-limited) |
| `POST /api/v1/auth/refresh` | Refresh Token | none |
| `GET /api/v1/auth/me` | Get Current User | Bearer |
| `POST /api/v1/auth/change-password` | Change Password | Bearer (rate-limited) |
| `POST /api/v1/auth/logout` | Logout | Bearer |

Postman: folder **Authentication** in `docs/postman/AEOLUS.postman_collection.json`.

---

## 1. Before you start: create the admin

There is **no endpoint** that creates a user. If there were one, whoever reached the API first
could make themselves the admin. Create the admin once from a terminal while the stack is running:

```powershell
docker compose exec api python -m app.cli create-admin
```

It asks for an email, then the password twice (6–128 characters, not shown while typing).
If an admin already exists it refuses.

Forgot the password?

```powershell
docker compose exec api python -m app.cli create-admin --reset-password
```

This sets a new password and logs out every device.

**Alternative for a fresh Docker setup:** put `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`. The API
creates the admin on start if no user exists yet. Remove `ADMIN_PASSWORD` from `.env` afterwards.

## 2. Postman setup

1. Import both files from `docs/postman/` and select the **AEOLUS local** environment.
2. In the environment, fill **current values** (never commit them):
   - `adminEmail`, `adminPassword`: the admin you created.
   - `newAdminPassword`: only needed for **Change Password**.
3. Send **Login**. Its script saves `accessToken` and `refreshToken` to the environment, and every
   other request uses them automatically (the collection's auth is `Bearer {{accessToken}}`).

## 3. Tokens

| Token | Lifetime | What it is |
|---|---|---|
| `accessToken` | 30 min (`ACCESS_TOKEN_MINUTES`) | Signed JWT. Sent as `Authorization: Bearer …`. |
| `refreshToken` | 7 days (`REFRESH_TOKEN_DAYS`) | Random string, stored only as a hash. **One use**: each refresh returns a new one. |

- When the access token expires (`401 TOKEN_EXPIRED`), send **Refresh Token** to get a new pair.
- If a refresh token that was already used is sent again, the API assumes it was stolen and
  revokes the whole chain. Log in again.
- Logout and Change Password revoke refresh tokens. An access token that was already issued keeps
  working until it expires (at most 30 min).

---

## 4. Endpoints

### Login — `POST /api/v1/auth/login`

No auth. Limited to **5 attempts per minute per IP** (`LOGIN_RATE_LIMIT`), successful or not.

Request:

```json
{ "email": "admin@example.com", "password": "your-password" }
```

The email is not case-sensitive.

Response `200`:

```json
{
  "accessToken": "eyJhbGciOi…",
  "refreshToken": "q3V0…",
  "tokenType": "bearer",
  "expiresIn": 1800
}
```

`expiresIn` is the access-token lifetime in seconds.

Errors:

| Status | `error.code` | When |
|---|---|---|
| 401 | `INVALID_CREDENTIALS` | Wrong email or password, or inactive user. Same message for all, on purpose. |
| 422 | `VALIDATION_ERROR` | Missing or empty field. |
| 429 | `RATE_LIMITED` | More than 5 attempts in a minute. Wait 60 s (`Retry-After: 60`). |

### Refresh Token — `POST /api/v1/auth/refresh`

No auth (the access token may already be expired).

Request:

```json
{ "refreshToken": "q3V0…" }
```

Response `200`: a new pair, same shape as Login. The refresh token you sent stops working.

Errors: `401 INVALID_REFRESH_TOKEN` when the token is unknown, expired, revoked or reused.

### Get Current User — `GET /api/v1/auth/me`

Bearer token required. No body.

Response `200`:

```json
{
  "id": "6f1c…",
  "email": "admin@example.com",
  "createdAt": "2026-11-20T10:15:00Z",
  "lastLoginAt": "2026-11-20T10:20:31Z"
}
```

Errors (same on every protected endpoint of every domain):

| Status | `error.code` | When |
|---|---|---|
| 401 | `NOT_AUTHENTICATED` | No `Authorization` header. |
| 401 | `TOKEN_EXPIRED` | Access token is older than 30 min. Use Refresh Token. |
| 401 | `INVALID_TOKEN` | Token is malformed, has a bad signature, or the user no longer exists. |

### Change Password — `POST /api/v1/auth/change-password`

Bearer token required. Limited to 5 per minute per IP.

Request:

```json
{ "currentPassword": "old-password", "newPassword": "new-password" }
```

Response `204` (no body). **Every refresh token is revoked**, so every device must log in again.
After this, copy the new password into `adminPassword` in Postman.

Errors:

| Status | `error.code` | When |
|---|---|---|
| 400 | `INVALID_CURRENT_PASSWORD` | `currentPassword` is wrong. (400, not 401: you are still logged in.) |
| 400 | `PASSWORD_UNCHANGED` | New password equals the current one. |
| 422 | `VALIDATION_ERROR` | `newPassword` shorter than 6 or longer than 128 characters. |
| 429 | `RATE_LIMITED` | Too many attempts. |

### Logout — `POST /api/v1/auth/logout`

Bearer token required.

Request: the refresh token to revoke (the one from your latest Login or Refresh).

```json
{ "refreshToken": "q3V0…" }
```

Response `204` (no body). That refresh token can no longer be used. Calling Logout again with the
same token still returns `204`.

---

## 5. Manual test checklist

Run in this order. Use **Login** again whenever a step leaves you without a valid token.

| # | Do this in Postman | Expect |
|---|---|---|
| 1 | Login with a wrong password | 401 `INVALID_CREDENTIALS` |
| 2 | Login | 200, tokens saved |
| 3 | Get Current User | 200 with your email |
| 4 | Get Current User with Auth set to *No Auth* | 401 `NOT_AUTHENTICATED` |
| 5 | Copy `refreshToken`, send Refresh Token, then send the copied old token again | 200, then 401 `INVALID_REFRESH_TOKEN` |
| 6 | Login, Logout, then Refresh Token | 204, then 401 |
| 7 | Login, Change Password, then Refresh Token with the token from before the change | 204, then 401 |
| 8 | Login with the new password | 200 |
| 9 | Login with a wrong password 6 times within a minute | 6th answer is 429 `RATE_LIMITED` |

## 6. Automated tests

```powershell
docker compose run --rm api pytest tests/test_auth_api.py tests/test_admin_setup.py tests/test_security.py
```

## 7. Code map

| Layer | File |
|---|---|
| Routes | `app/api/routers/auth.py` |
| `get_current_user` (`CurrentUser`) dependency | `app/api/deps.py` |
| Logic | `app/services/auth_service.py` |
| Hashing, JWT, refresh-token helpers | `app/core/security.py` |
| Rate limit | `app/core/rate_limit.py` |
| Tables `users`, `refresh_tokens` | `app/models/user.py`, migration `0002` |
| CLI `create-admin` | `app/cli.py` |
