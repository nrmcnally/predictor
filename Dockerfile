# FIGHT IQ — single-container serve image.
# Builds the React frontend, then serves it AND the FastAPI API from one process
# (same origin, no CORS config needed). The SQLite DB + model artifacts are NOT
# baked in — they live on a mounted volume, populated by deploy/make_bundle.py
# (see DEPLOY.md). The Playwright-based scraper never runs here; data updates run
# on your PC and get pushed.

# --- Stage 1: build the frontend --------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: serve ----------------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app/backend

# Serving deps only — Playwright (scraper-only, needs Chromium) is excluded.
COPY backend/requirements.txt ./
RUN grep -viE '^playwright' requirements.txt > /tmp/requirements-serve.txt \
    && pip install --no-cache-dir -r /tmp/requirements-serve.txt

COPY backend/app ./app
COPY --from=frontend /build/dist /app/frontend_dist
COPY deploy/start.sh deploy/update_from_bundle.sh /app/deploy/

# Hosted defaults: strict auth wall + fail-fast without AUTH_SECRET, proxy-aware
# rate limiting. AUTH_SECRET / ADMIN_EMAIL / ADMIN_PASSWORD come from the host's
# secret store — never bake them into the image.
ENV FRONTEND_DIST=/app/frontend_dist \
    FIGHTIQ_HOSTED=1 \
    TRUST_PROXY=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["sh", "/app/deploy/start.sh"]
