#!/bin/sh
set -e

exec uv run uvicorn agent_port.main:app --host 0.0.0.0 --port "${PORT:-4747}"
