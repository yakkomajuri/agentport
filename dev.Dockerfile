FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/agentport

WORKDIR /app/server

# Install dependencies before copying source for better layer caching.
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra postgres-binary

# Copy source and install the project itself.
COPY server/src ./src
COPY server/alembic ./alembic
COPY server/alembic.ini ./
RUN uv sync --frozen --no-dev --extra postgres-binary

EXPOSE 4747

# Run migrations then start with --reload for hot reloading.
# Mount server/src into /app/server/src at runtime for changes to take effect:
#   docker run -v $(pwd)/server/src:/app/server/src ...
CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn agent_port.main:app --host 0.0.0.0 --port 4747 --reload"]
