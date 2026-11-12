# Web app build (static files only; nothing from node ends up running).
FROM node:22-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

# One Python image for both `updater` (regteia-ingest) and `server` (regteia-server).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages ./packages
RUN uv sync --frozen --all-packages --no-dev
COPY upstreams.toml ./
COPY db ./db
COPY --from=web /web/dist ./apps/web/dist
ENV REGTEIA_WEB_DIST=/app/apps/web/dist
