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

A ready-made `fly.toml` is in the repo root (1GB VM, `/data` volume, auto-sleep when
idle so you mostly pay only while someone's using it). One-time setup:

```powershell
# 1. Install the CLI + sign up (fly.io — requires a card; a small app like this
#    runs a few dollars/month, and the machine sleeps when idle)
iwr https://fly.io/install.ps1 -useb | iex
fly auth signup        # or: fly auth login

# 2. Create the app from the repo root (keeps the committed fly.toml; rename if taken)
fly launch --no-deploy --copy-config

# 3. Persistent storage + secrets
fly volumes create fightiq_data --size 3
python -c "import secrets; print(secrets.token_urlsafe(48))"   # -> AUTH_SECRET below
fly secrets set AUTH_SECRET=<paste> ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=<strong>

# 4. Build + deploy (image builds on Fly's servers — no local Docker needed)
fly deploy --remote-only

# 5. Push the data/model bundle and install it
python deploy/make_bundle.py
fly ssh sftp put deploy/deploy_bundle.tar.gz /data/bundle.tar.gz
fly ssh console -C "sh /app/deploy/update_from_bundle.sh"
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
# push the bundle into the volume and install it:
docker cp deploy/deploy_bundle.tar.gz $(docker compose -f deploy/docker-compose.yml ps -q fightiq):/data/bundle.tar.gz
docker compose -f deploy/docker-compose.yml exec fightiq sh /app/deploy/update_from_bundle.sh
```

Put Caddy/nginx in front for TLS (`reverse_proxy localhost:8000` is all Caddy needs).

## 3. After first boot — checklist

- [ ] `GET /health` returns `{"status": "ok", "mode": "prod"}`
- [ ] Anonymous `GET /future-cards` returns **401** (the auth wall is on)
- [ ] Log in as the seeded admin; **change the password**
- [ ] Friends register (or you register for them), then set `ALLOW_REGISTRATION=0`
- [ ] Lost password? Admin → Users → **Reset password** hands out a one-time temp

## Updating later — two separate flows

**Code changes** (new features, fixes):

```bash
fly deploy --remote-only        # rebuilds the image from your working tree and rolls it out
```

The volume (DB + models) is untouched — friends' accounts and picks survive deploys.

**Data/model refreshes** (after running Data Ops locally) — one command:

```bash
python deploy/push_update.py https://yourapp.fly.dev
```

It builds the bundle, logs in with your admin account (password prompted), and
uploads it over HTTPS to `POST /admin/data/upload-bundle`. No SSH/CLI tooling needed
— works from any machine. The server side is **merge-aware**: it replaces the shared
data (results, upcoming cards, odds, saved model predictions) and overwrites the
model files, but **never touches accounts, picks, or friendships created on the
server**. Changed files hot-reload automatically — no restart.

<details>
<summary>Fallback: SSH route (first boot, or the ~450MB <code>--full</code> bundle)</summary>

```bash
python deploy/make_bundle.py            # add --full for the Evaluation deep-dives
fly ssh sftp put deploy/deploy_bundle.tar.gz /data/bundle.tar.gz
fly ssh console -C "sh /app/deploy/update_from_bundle.sh"
```
</details>
