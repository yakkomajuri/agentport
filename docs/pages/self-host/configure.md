---
title: Configuration
nav_title: Configuration
---

# Configuring a self-hosted AgentPort

Everything below is configured via environment variables, most commonly set in the `.env` file next to `docker-compose.prod.yml`. After editing `.env`, apply changes with:

```sh
docker compose -f docker-compose.prod.yml up -d
```

## Core environment variables

| Variable | Default | Notes |
|---|---|---|
| `DOMAIN` | *(required)* | The hostname Caddy serves and requests a cert for. |
| `LETSENCRYPT_EMAIL` | *(required)* | Contact email Let's Encrypt uses for expiry warnings. |
| `JWT_SECRET_KEY` | auto-generated on first boot | Signs session JWTs. If unset, the container writes one to `/data/jwt_secret` and reuses it across restarts. Set it explicitly if you want to pin or rotate it. |
| `DATABASE_URL` | `sqlite:////data/agent_port.db` | See [Postgres](#using-postgres) below to point at a separate database. |
| `SKIP_EMAIL_VERIFICATION` | `true` (in prod compose) | Leave as-is if you haven't configured email; set to `false` once `RESEND_API_KEY` is set. |
| `BASE_URL` / `UI_BASE_URL` | `https://${DOMAIN}` | Usually don't touch — the compose file derives these from `DOMAIN`. |
| `OAUTH_CALLBACK_URL` | `https://${DOMAIN}/api/auth/callback` | Must exactly match the redirect URI registered in each OAuth app. |
| `POSTHOG_HOST` | `https://us.i.posthog.com` | Optional. PostHog ingestion host for server-side analytics. Set `https://eu.i.posthog.com` for EU projects. |
| `VITE_PUBLIC_POSTHOG_HOST` | `https://us.i.posthog.com` | Optional. PostHog ingestion host baked into the frontend bundle at build time. Set it to the same region as `POSTHOG_HOST`. |

## Backups

AgentPort's persistent state lives in two Docker volumes:

- `agentport_data` — SQLite database, generated JWT secret, and anything else the server writes to `/data`.
- `caddy_data` — Let's Encrypt account key and issued certificates. Losing it only means Caddy will request fresh certs on next boot (subject to Let's Encrypt's rate limits).

### Backing up SQLite

Use `sqlite3`'s online backup so you don't risk a half-written file:

```sh
docker compose -f docker-compose.prod.yml exec agentport \
  sqlite3 /data/agent_port.db ".backup /data/backup.db"

docker compose -f docker-compose.prod.yml cp \
  agentport:/data/backup.db ./backup-$(date +%Y%m%d).db
```

A cron on the host that runs this daily and ships the file off-box (S3, rsync, restic) is the minimum viable strategy.

### Restoring

```sh
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml cp \
  ./backup-20260422.db agentport:/data/agent_port.db
docker compose -f docker-compose.prod.yml up -d
```

## Using Postgres

SQLite is fine for small installs, but it's single-writer and lives on whatever disk the container's volume is on. But for more serious usage, consider pointing AgentPort at a separate Postgres instance.

### Managed Postgres (recommended)

Create a database on PlanetScale, Supabase, Neon, Fly Postgres, etc. Then set:

```end
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:5432/agentport?sslmode=require
```

And restart:

```sh
docker compose -f docker-compose.prod.yml up -d
```

Migrations run automatically on boot (`alembic upgrade head`). The first start against an empty Postgres database will create all tables.

### Postgres in the same compose

If you'd rather run Postgres alongside AgentPort, add a service to `docker-compose.prod.yml`:

```yaml
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: agentport
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env}
      POSTGRES_DB: agentport
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agentport"]
      interval: 10s

# ... then under the `agentport` service:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql+psycopg2://agentport:${POSTGRES_PASSWORD}@postgres:5432/agentport

# ... and at the bottom:
volumes:
  postgres_data:
```

### Migrating from SQLite to Postgres

There's no in-place migration. The typical path is:

1. Export data from the SQLite file (`sqlite3 agent_port.db .dump > dump.sql`).
2. Hand-translate the schema differences or restore from Alembic (run migrations on an empty Postgres, then load just the data rows).
3. Point `DATABASE_URL` at Postgres and restart.

For most installs it's simpler to start on Postgres from the beginning if you know you'll want it later.


## Log rotation

Docker's default JSON log driver grows unbounded. Add a `logging:` block to both services in `docker-compose.prod.yml`:

```yaml
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

That caps each container's logs at ~30 MB on disk.

## Resource limits

On a shared host you want a runaway not to OOM the whole machine. Add under the `agentport` service:

```yaml
    deploy:
      resources:
        limits:
          memory: 1g
          cpus: "1.0"
```

(The `deploy:` key is honored by `docker compose up` as of Compose v2 when not running under Swarm.)


## Google sign-in

Completely independent from the Google integration (Gmail, Calendar). This is only if you want users to log into AgentPort itself via Google:

```env
GOOGLE_LOGIN_CLIENT_ID=...
GOOGLE_LOGIN_CLIENT_SECRET=...
```

Without these set, the "Continue with Google" button still renders on the login page but returns an error when clicked.

## PostHog analytics

If you want AgentPort to send product analytics, set your PostHog project token and optionally override the host:

```env
POSTHOG_PROJECT_TOKEN=...
POSTHOG_HOST=https://us.i.posthog.com
VITE_PUBLIC_POSTHOG_HOST=https://us.i.posthog.com
```

If you omit either host, AgentPort defaults to US ingestion. Use `https://eu.i.posthog.com` for EU-hosted PostHog projects, and keep `POSTHOG_HOST` and `VITE_PUBLIC_POSTHOG_HOST` aligned.

Because `VITE_PUBLIC_POSTHOG_HOST` is compiled into the UI bundle, changing it requires a rebuild:

```sh
docker compose -f docker-compose.prod.yml up -d --build
```

## OAuth credentials for integrations

Integrations that use OAuth (GitHub, Google, Notion, etc.) each need their own client ID / secret registered in that provider's developer console, with a redirect URI matching `OAUTH_CALLBACK_URL`. Convention:

```env
OAUTH_GITHUB_CLIENT_ID=...
OAUTH_GITHUB_CLIENT_SECRET=...
OAUTH_GOOGLE_CLIENT_ID=...
OAUTH_GOOGLE_CLIENT_SECRET=...
```

See [Google OAuth setup](/self-host/google-oauth-setup) for the full walk-through on the Google side (the same app covers both Gmail and Calendar).

## Rotating the JWT secret

Setting a new `JWT_SECRET_KEY` invalidates every existing session — all users have to log in again. Useful if you suspect the secret has leaked.

```sh
# Generate a new one
openssl rand -hex 32

# Put it in .env as JWT_SECRET_KEY=...
docker compose -f docker-compose.prod.yml up -d
```

If you want to keep the auto-generated secret but force a rotation, delete `/data/jwt_secret` inside the volume and restart — a new one will be generated.
