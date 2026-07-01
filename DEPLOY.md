# FIGHT IQ — Deployment Guide

One container serves everything: the FastAPI backend also serves the built React
frontend (same origin — no CORS setup). The SQLite DB and model artifacts are **not**
in the image; they live on a persistent volume, populated by an artifact bundle you
build locally. Data updates keep running on your PC (Data Ops), then you push a fresh
bundle — the server hot-reloads changed model/data files, no redeploy needed.

```
 your PC                              host (Fly / Railway / VPS)
 ┌──────────────────────┐             ┌──────────────────────────────┐
 │ Data Ops (scraper +  │   bundle    │  container                   │
 │ retrain, Playwright) ├────────────►│   uvicorn ── API + frontend  │
 │ deploy/make_bundle   │  tar.gz     │   /data volume ── db, models │
 └──────────────────────┘             └──────────────────────────────┘
```

## Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `AUTH_SECRET` | **yes** | Token signing key. The app **refuses to boot** in hosted mode without a real one. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | first boot | Seeds the admin account. Change the password after first login. |
| `ALLOW_REGISTRATION` | no (default `1`) | Set `0` to close signups once your friends have accounts. |
| `FIGHTIQ_HOSTED` | baked into image (`1`) | Turns on the strict hosted behavior (auth wall, secret check). |
| `REQUIRE_AUTH` | no | Defaults on in hosted mode: every endpoint except `/health`, login/register, and the frontend files needs a logged-in account. |
| `TRUST_PROXY` | baked into image (`1`) | Rate limiting uses the client IP from `X-Forwarded-For` (all hosts here put a proxy in front). |
| `RATE_LIMIT_PER_MINUTE` / `AUTH_RATE_LIMIT_PER_MINUTE` | no | Defaults 240 / 15. |
| `CORS_ORIGINS` | no | Only needed if the frontend is ever served from a *different* origin. |

## 1. Build the artifact bundle (on your PC)

```powershell
python deploy/make_bundle.py          # serving core, ~44MB compressed
python deploy/make_bundle.py --full   # + winner_models & training matchups
                                      #   (enables the Evaluation tab's deep-dives)
```

Re-run and re-push after every local Data Ops update.

## 2a. Fly.io

```bash
fly launch --no-deploy               # answer prompts; keep the generated app name
fly volumes create fightiq_data --size 3
fly secrets set AUTH_SECRET=<generated> ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=<strong>
fly deploy                           # builds the Docker image remotely
```

Add to the generated `fly.toml` if `fly launch` didn't:

```toml
[mounts]
  source = "fightiq_data"
  destination = "/data"

[http_service]
  internal_port = 8000
```

Push the bundle:

```bash
fly ssh sftp put deploy/deploy_bundle.tar.gz /data/bundle.tar.gz
fly ssh console -C "tar -xzf /data/bundle.tar.gz -C /data && rm /data/bundle.tar.gz"
```

Then open `https://<app>.fly.dev` — log in with the admin account.

## 2b. Railway

1. New project → Deploy from GitHub repo (it detects the root `Dockerfile`).
2. Add a **volume** mounted at `/data`.
3. Set the env vars from the table in the service settings.
4. Push the bundle from your PC: `railway ssh` into the service, or temporarily
   `railway run bash` with the volume attached, then upload + `tar -xzf ... -C /data`.

## 2c. Your own VPS

```bash
cp deploy/.env.example deploy/.env       # fill in AUTH_SECRET etc.
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
# push the bundle into the volume:
docker cp deploy/deploy_bundle.tar.gz $(docker compose -f deploy/docker-compose.yml ps -q fightiq):/data/
docker compose -f deploy/docker-compose.yml exec fightiq sh -c "tar -xzf /data/deploy_bundle.tar.gz -C /data && rm /data/deploy_bundle.tar.gz"
```

Put Caddy/nginx in front for TLS (`reverse_proxy localhost:8000` is all Caddy needs).

## 3. After first boot — checklist

- [ ] `GET /health` returns `{"status": "ok", "mode": "prod"}`
- [ ] Anonymous `GET /future-cards` returns **401** (the auth wall is on)
- [ ] Log in as the seeded admin; **change the password**
- [ ] Friends register (or you register for them), then set `ALLOW_REGISTRATION=0`
- [ ] Lost password? Admin → Users → **Reset password** hands out a one-time temp

## Updating data/models later

1. Run Data Ops locally (or the incremental pipeline).
2. `python deploy/make_bundle.py`
3. Push + extract the bundle (same command as step 2 for your host).
4. Done — the server's `file_aware_cache` reloads changed model/data files
   automatically. Restart the app only if something looks stale.
