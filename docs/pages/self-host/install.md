---
title: Install
nav_title: Install
---

# Installing AgentPort

AgentPort self-hosts as two containers: a Caddy reverse proxy that handles TLS automatically, and the AgentPort server (FastAPI + the built UI, backed by SQLite on disk). Everything runs under Docker Compose.

## Requirements

- A Linux host with a public IP (any cloud VM is fine — 1 vCPU / 1 GB RAM is plenty to start).
- A domain name you can edit DNS for.
- Ports **80** and **443** open to the internet (Let's Encrypt needs 80 for HTTP-01 challenges).
- [Docker Engine](https://docs.docker.com/engine/install/) with the Compose v2 plugin.
- `git` and `curl`.

## One-line install

SSH into the host and run:

```sh
curl -fsSL https://raw.githubusercontent.com/yakkomajuri/agent-port/main/install.sh | sh
```

The script will:

1. Clone the repo into `./agentport`.
2. Print this host's public IP and ask you to point your domain's **A record** at it.
3. Prompt for the **domain** and an **email address** for Let's Encrypt.
4. Poll DNS (via Cloudflare DoH, so it bypasses your local resolver's cache) until the domain resolves to this host.
5. Generate a `JWT_SECRET_KEY`, write `.env`, and bring up the stack with `docker compose -f docker-compose.prod.yml up -d --build`.

Caddy provisions the TLS certificate on the first HTTPS request — usually within a minute of the containers starting.

## Manual install

If you'd rather do it yourself:

```sh
git clone https://github.com/yakkomajuri/agent-port.git
cd agent-port

cat > .env <<EOF
DOMAIN=agentport.example.com
LETSENCRYPT_EMAIL=you@example.com
JWT_SECRET_KEY=$(openssl rand -hex 32)
EOF
chmod 600 .env

docker compose -f docker-compose.prod.yml up -d --build
```

Before this will work, the DNS A record for `DOMAIN` must already resolve to the host's public IP — otherwise Let's Encrypt's HTTP-01 challenge fails.

## Verifying it's up

```sh
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
curl -sSf https://agentport.example.com/health
```

Then open the domain in a browser and create your first account. Once you've done that, set `BLOCK_SIGNUPS=true` in `.env` and re-run `docker compose -f docker-compose.prod.yml up -d` to lock down new registrations (see [Configuration](/self-host/configure)).

## Updating

```sh
cd agentport
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically on container start.

## Uninstalling

```sh
docker compose -f docker-compose.prod.yml down
```

Data lives in the `agentport_data` and `caddy_data` Docker volumes — back them up first if you want to keep anything. See [Configuration → Backups](/self-host/configure#backups).

## Next steps

- [Configuration](/self-host/configure) — environment variables, Postgres, backups, email, log rotation, resource limits.
- [Google OAuth setup](/self-host/google-oauth-setup) — required to enable the Gmail and Google Calendar integrations.
