# ─── Stage 1: build the UI ───────────────────────────────────────────────────
FROM node:22-slim AS ui-builder

ARG IS_CLOUD=false
ARG VITE_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
ENV VITE_IS_CLOUD=$IS_CLOUD
ENV VITE_PUBLIC_POSTHOG_HOST=$VITE_PUBLIC_POSTHOG_HOST

WORKDIR /app/ui

RUN corepack enable

COPY ui/package.json ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY ui/ ./
RUN pnpm build

# ─── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM python:3.12-slim

# libpq-dev is required to compile psycopg2 from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/agent_port.db

WORKDIR /app/server

# Install dependencies before copying source for better layer caching.
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra postgres --extra aws

# Copy source and install the project itself.
COPY server/src ./src
COPY server/alembic ./alembic
COPY server/alembic.ini ./
RUN uv sync --frozen --no-dev --extra postgres --extra aws

# Copy built UI so FastAPI can serve it.
COPY --from=ui-builder /app/ui/dist ./ui_dist

# Volume mount point for SQLite data.
RUN mkdir -p /data

COPY server/start.sh ./start.sh
RUN chmod +x ./start.sh

EXPOSE 4747

CMD ["./start.sh"]
