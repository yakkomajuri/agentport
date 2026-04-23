---
title: Install
nav_title: Install
---

# Installing AgentPort

You can deploy AgentPort in just a few minutes on a VPS using Docker Compose.

We'll provision everything for you, including setting up reverse proxying with TLS certificates for a domain you choose.

The vast majority of integrations will work out of the box without any extra config. Only a few like Google will require some extra work from you.

## Requirements

- A Linux host with a public IP. We recommend at least 1 vCPU and 2GB RAM.
- A domain name.
- Ports **80** and **443** open to the internet (Let's Encrypt needs 80 for HTTP-01 challenges).
- Docker installed ([docs](https)://docs.docker.com/engine/install/).
- `git` and `curl`.

## One-line install

SSH into the instance and run:

```sh
curl -fsSL https://install.agentport.sh | sh
```

The script will:

1. Clone the repo into `./agentport`.
2. Print this host's public IP and ask you to point your domain's **A record** at it.
3. Prompt for the **domain** and an **email address** for Let's Encrypt.
4. Poll DNS (via Cloudflare DoH, so it bypasses your local resolver's cache) until the domain resolves to this host.
5. Generate a `JWT_SECRET_KEY`, write `.env`, and bring up the stack with `docker compose -f docker-compose.prod.yml up -d --build`.

Caddy provisions the TLS certificate on the first HTTPS request, usually within a minute of the containers starting.

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

Note that for this to work the DNS A record for `DOMAIN` must already resolve to the host's public IP.

## Verifying it's up

From the `agentport` directory, run:

```sh
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
curl -sSf https://agentport.example.com/health
```

Then open the domain in a browser and create your account. We automatically block any other signups after the first signup on self-hosted deploys. 

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
