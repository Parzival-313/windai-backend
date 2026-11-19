# AEOLUS backend image — used by both the `api` and `worker` compose services.
FROM python:3.12-slim-bookworm

# uv: fast Python package manager (replaces pip + venv). Pinned by minor version.
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Keep the virtualenv outside /app so the dev bind-mount of the repo does not hide it.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (cached layer; only rebuilt when pyproject/uv.lock change).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Application code
COPY . .

# Non-root runtime user; it owns the data directories mounted as volumes.
RUN useradd --create-home --uid 1000 aeolus \
    && mkdir -p /data/raw /data/cache /data/models /data/artifacts \
    && chown -R aeolus:aeolus /data /app
USER aeolus

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
