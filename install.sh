#!/usr/bin/env sh
# AgentPort production install.
#
# One-liner usage (fresh host):
#   curl -fsSL https://raw.githubusercontent.com/yakkomajuri/agent-port/main/install.sh | sh
#
# Or clone first and run ./install.sh. Either way:
#   1. Ensures Docker + Compose are present.
#   2. Clones the repo (if not already in it) into ./agentport.
#   3. Prompts for domain + Let's Encrypt email.
#   4. Shows this host's public IP and waits until the domain resolves to it.
#   5. Brings up the Caddy + AgentPort stack.
#
# Environment overrides:
#   AGENTPORT_REPO     git URL to clone from (default: upstream)
#   AGENTPORT_BRANCH   branch to check out   (default: main)
#   AGENTPORT_DIR      target directory      (default: ./agentport)
#   SKIP_DNS_CHECK=1   skip the DNS-propagation wait

set -eu

REPO_URL="${AGENTPORT_REPO:-https://github.com/yakkomajuri/agent-port.git}"
BRANCH="${AGENTPORT_BRANCH:-main}"
TARGET_DIR="${AGENTPORT_DIR:-agentport}"
FORCE=0

for arg in "$@"; do
	case "$arg" in
		--force) FORCE=1 ;;
		-h|--help)
			sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
			exit 0
			;;
	esac
done

# ── prereqs ──────────────────────────────────────────────────────────────────
need() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "error: '$1' not found. $2" >&2
		exit 1
	}
}

need git    "Install it with your package manager (e.g. apt-get install -y git)."
need curl   "Install it with your package manager (e.g. apt-get install -y curl)."
need docker "Install Docker Engine: https://docs.docker.com/engine/install/"

if ! docker compose version >/dev/null 2>&1; then
	echo "error: 'docker compose' plugin not found. Install Docker Compose v2." >&2
	exit 1
fi

# ── clone / cd into repo ─────────────────────────────────────────────────────
if [ ! -f docker-compose.prod.yml ]; then
	if [ -d "$TARGET_DIR/.git" ]; then
		echo "• updating existing clone at ./$TARGET_DIR"
		cd "$TARGET_DIR"
		git fetch --depth 1 origin "$BRANCH"
		git checkout "$BRANCH"
		git reset --hard "origin/$BRANCH"
	else
		echo "• cloning $REPO_URL into ./$TARGET_DIR"
		git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
		cd "$TARGET_DIR"
	fi
fi

# ── .env helpers ─────────────────────────────────────────────────────────────
[ -f .env ] || : > .env

get_env() {
	grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2- || true
}

set_env() {
	tmp=$(mktemp)
	grep -v -E "^$1=" .env > "$tmp" 2>/dev/null || true
	printf '%s=%s\n' "$1" "$2" >> "$tmp"
	mv "$tmp" .env
}

prompt() {
	var=$1; label=$2
	current=$(get_env "$var")
	if [ -n "$current" ] && [ "$FORCE" -ne 1 ]; then
		echo "• $var already set (keeping existing value — use --force to change)"
		return
	fi
	# Read from /dev/tty so this works under `curl | sh`.
	printf "%s: " "$label" > /dev/tty
	read -r value < /dev/tty
	if [ -z "$value" ]; then
		echo "error: $var is required" >&2
		exit 1
	fi
	set_env "$var" "$value"
}

# ── detect this host's public IP ─────────────────────────────────────────────
public_ip() {
	for svc in https://api.ipify.org https://ifconfig.me https://icanhazip.com; do
		ip=$(curl -fsSL --max-time 5 "$svc" 2>/dev/null | tr -d '[:space:]') || true
		if [ -n "${ip:-}" ]; then
			printf '%s' "$ip"
			return 0
		fi
	done
	return 1
}

# ── resolve a hostname's A record via Cloudflare DoH (bypasses local cache) ──
resolve_a() {
	host=$1
	curl -fsSL --max-time 5 \
		-H "accept: application/dns-json" \
		"https://cloudflare-dns.com/dns-query?name=${host}&type=A" 2>/dev/null \
		| tr ',' '\n' \
		| grep -oE '"data":"[0-9.]+"' \
		| cut -d'"' -f4 \
		| head -n1
}

# ── interactive setup ────────────────────────────────────────────────────────
echo "AgentPort production install"
echo "─────────────────────────────"

HOST_IP=$(public_ip) || {
	echo "warning: couldn't detect this host's public IP. You'll need to look it up manually." >&2
	HOST_IP=""
}

if [ -n "$HOST_IP" ]; then
	echo "• this host's public IP is $HOST_IP"
	echo "  → point an A record for your domain at $HOST_IP before continuing"
	echo
fi

prompt DOMAIN            "Domain (e.g. agentport.example.com)"
prompt LETSENCRYPT_EMAIL "Contact email for Let's Encrypt"

DOMAIN=$(get_env DOMAIN)

# ── wait for DNS to point at us ──────────────────────────────────────────────
if [ "${SKIP_DNS_CHECK:-0}" != "1" ] && [ -n "$HOST_IP" ]; then
	echo
	echo "Waiting for $DOMAIN to resolve to $HOST_IP…"
	echo "(ctrl-c to abort; set SKIP_DNS_CHECK=1 to skip this check)"

	attempt=0
	while :; do
		attempt=$((attempt + 1))
		resolved=$(resolve_a "$DOMAIN" || true)
		if [ "$resolved" = "$HOST_IP" ]; then
			echo "• $DOMAIN → $HOST_IP ✓"
			break
		fi
		if [ -n "$resolved" ]; then
			printf "\r• attempt %d: %s resolves to %s (want %s)        " \
				"$attempt" "$DOMAIN" "$resolved" "$HOST_IP"
		else
			printf "\r• attempt %d: %s does not resolve yet         " \
				"$attempt" "$DOMAIN"
		fi
		sleep 10
	done
	echo
fi

# ── generate JWT secret ──────────────────────────────────────────────────────
if [ -z "$(get_env JWT_SECRET_KEY)" ]; then
	if command -v openssl >/dev/null 2>&1; then
		set_env JWT_SECRET_KEY "$(openssl rand -hex 32)"
	else
		set_env JWT_SECRET_KEY "$(head -c 32 /dev/urandom | od -A n -t x1 | tr -d ' \n')"
	fi
	echo "• generated JWT_SECRET_KEY"
fi

chmod 600 .env

# ── bring up the stack ───────────────────────────────────────────────────────
echo
echo "Building and starting containers…"
docker compose -f docker-compose.prod.yml up -d --build

cat <<EOF

Done. AgentPort will be at https://$DOMAIN once Caddy finishes provisioning
the TLS certificate (usually under a minute on first boot).

Logs:   docker compose -f docker-compose.prod.yml logs -f
Stop:   docker compose -f docker-compose.prod.yml down
Update: cd $(pwd) && git pull && docker compose -f docker-compose.prod.yml up -d --build
EOF
