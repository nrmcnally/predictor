#!/bin/sh
# Container entrypoint: link the code's data/models paths onto the mounted volume,
# then serve. The volume (default /data) is populated by extracting the artifact
# bundle from deploy/make_bundle.py — see DEPLOY.md.
set -e

DATA_ROOT="${DATA_ROOT:-/data}"
mkdir -p "$DATA_ROOT/data" "$DATA_ROOT/models"

# The app resolves data/ and models/ relative to the backend dir; point both at
# the volume so artifacts survive restarts and redeploys.
rm -rf /app/backend/data /app/backend/models
ln -sfn "$DATA_ROOT/data" /app/backend/data
ln -sfn "$DATA_ROOT/models" /app/backend/models

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
