# syntax=docker/dockerfile:1
# SharkSight images (D-053). Build context = repo root; .dockerignore is an allowlist (no raw data, data/ or .env).
#   target prod (default): API + built PM app in one container, APP_ENV=production
#   target dev:            API with auto-reload; source is bind-mounted by compose.yaml (profile dev)
# The layout mirrors the repo (/app/backend, /app/frontend, /app/research) so bmw_req.config.ROOT resolves to /app.

# ---------------------------------------------------------------- frontend build
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- python base
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
COPY backend/scripts ./scripts
RUN uv sync --frozen --no-dev
COPY research/checkpoints/checkpoints.json /app/research/checkpoints/checkpoints.json
# inside the container the server must listen on all interfaces; compose publishes it on the host's 127.0.0.1 only
ENV API_HOST=0.0.0.0 API_PORT=8600 DATA_DIR=/app/data
EXPOSE 8600
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8600/api/health', timeout=4)"
CMD ["python", "-m", "api"]

# ---------------------------------------------------------------- dev: + pytest, reload
FROM base AS dev
RUN uv sync --frozen
ENV APP_ENV=development

# ---------------------------------------------------------------- prod (default)
FROM base AS prod
COPY --from=web /app/frontend/dist /app/frontend/dist
ENV APP_ENV=production
