#!/bin/sh
set -e

# Run pending Alembic migrations before starting the server.
# Idempotent: alembic skips already-applied revisions.
alembic upgrade head

# Replace the shell with uvicorn so it receives signals directly (clean shutdown).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
