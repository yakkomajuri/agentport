---
title: AgentPort CLI
nav_title: CLI
---

# AgentPort CLI

```sh
npm install -g agentport-cli
```

`ap` is the command-line interface to AgentPort. It is the second of the two ways into the gateway, with the other being our [MCP server](/connect/mcp).

Both surface the same integrations, the same tools, and run through the same approval policies. Pick whichever fits your agent best (some can only run one or the other).


## Installation

The CLI ships as the `agentport-cli` npm package and exposes two binaries: `agentport` and the short alias `ap`.

```sh
npm install -g agentport-cli
```


## Configuration

Configuration lives at `~/.config/agent-port/config.json` and is managed by the CLI so you shouldn't have to manually edit it. It stores the server URL, the chosen auth mode (`oauth` or `api_key`), tokens, and your default output format.

The default server URL is `https://app.agentport.sh`. Override it with the `AGENT_PORT_URL` environment variable, or persist a different instance with:

```sh
ap auth set-instance-url https://ap.example.com
```

Switching instances clears any stored credentials, so you'll need to re-run `ap auth login`.

## Skills

You should really install the [AgentPort Skills](/connect/skills) for your agent to use the AgentPort CLI most efficiently.

## Authentication

### Browser OAuth (default)

```sh
ap auth login
```

This:

1. Spins up a one-shot loopback HTTP server on `127.0.0.1`.
2. Discovers the AgentPort OAuth metadata at `/.well-known/oauth-authorization-server`.
3. Performs dynamic client registration.
4. Opens the authorization URL in your browser (PKCE, `S256`).
5. Waits up to 180 seconds for the redirect, exchanges the code, and writes the access and refresh tokens to your config.

The CLI refreshes the access token automatically when it's about to expire, so you usually only run `login` once per machine.

Useful flags:

| Flag | Purpose |
|------|---------|
| `--no-open` | Print the URL but don't try to open a browser (for headless environments). |
| `--timeout <seconds>` | Adjust the callback timeout (default `180`). |
| `--api-key <key>` | Skip OAuth entirely and store an API key. |

### API key

For non-interactive environments (CI, agent runtimes, servers):

```sh
ap auth login --api-key ap_...
```

API keys are issued from the AgentPort UI.

### Status and logout

```sh
ap auth status   # show the configured URL, auth mode, masked tokens, and your email
ap auth logout   # wipe stored credentials
```

---

## Output formats

Every command takes `-o <format>` where `<format>` is one of:

- `human` — pretty tables and key/value pairs (default, not safe to parse).
- `json` — stable, machine-readable JSON.
- `toon` — TOON-encoded output for token-efficient consumption by LLMs.

To change the default for every command:

```sh
ap output json
```

## Command reference

There are four command groups: `auth`, `integrations`, `tools`, and `output`.

### `ap auth`

Manage CLI credentials and the target instance.

| Command | Purpose |
|---------|---------|
| `ap auth login` | OAuth login via the browser, or `--api-key <key>` for non-interactive auth. |
| `ap auth logout` | Remove stored credentials. |
| `ap auth status` | Show the configured URL, auth mode, masked tokens, and your account email. |
| `ap auth set-instance-url <url>` | Point the CLI at a different AgentPort instance. Clears credentials. |

Example:

```sh
ap auth status -o json
```

### `ap integrations`

List, install, and remove integrations.

| Command | Purpose |
|---------|---------|
| `ap integrations list` | List integrations. Defaults to all; use `--installed` or `--available` to filter. |
| `ap integrations add <integration>` | Install an integration. Pick auth with `--auth token\|oauth`; pass `--token <token>` for token auth. |
| `ap integrations remove <integration>` | Uninstall an integration. |

`ap integrations add` is interactive: for `--auth token` it will prompt for the secret if you don't pass `--token`, and for `--auth oauth` it opens the upstream OAuth URL in a browser and polls for completion (timeout configurable with `--timeout <seconds>`, default `180`). Use `--no-open` in headless environments to print the URL instead of opening it.

If the integration declares only one auth method, you can omit `--auth`.

Examples:

```sh
ap integrations list --installed -o json
ap integrations add github --auth oauth
ap integrations add resend --auth token --token re_...
ap integrations remove linear
```

### `ap tools`

List, describe, and call tools across installed integrations.

| Command | Purpose |
|---------|---------|
| `ap tools list` | List all tools. Use `--integration <id>` to scope to one integration. |
| `ap tools describe --integration <id> --tool <name>` | Show the tool's description, execution mode, and full `inputSchema`. |
| `ap tools call --integration <id> --tool <name> --args <json>` | Execute a tool. Pass `--info <text>` to record intent for reviewers. |

Examples:

```sh
ap tools list --integration github -o json
ap tools describe --integration github --tool create_issue -o json
ap tools call --integration github --tool create_issue \
  --args '{"repo":"yakkomajuri/agent-port","title":"docs: typo"}' \
  --info "Filing the typo Sam noticed in the README." \
  -o json
```

### `ap output`

Set the persisted default output format.

```sh
ap output json    # subsequent commands default to JSON
ap output human   # back to the pretty default
ap output toon
```


### Exit codes

`ap tools call` distinguishes outcomes via exit code:

| Exit code | Meaning | What to do |
|-----------|---------|------------|
| `0` | Success. Tool result on stdout. | Parse and use. |
| `1` | Error or denied. Message on stderr (e.g. `Denied: ...`). | Stop. Don't retry, don't try a different tool to reach the same outcome. |
| `2` | Approval required. Stderr contains `Approval required: <url>`. | Surface the URL to the human, wait for them to approve, then retry the **identical** command — changing `--args` invalidates the pending approval. |

See [Tool Approvals](/tool-approvals) for how the approval flow works on the server side.

### Quick reference

| Goal | Command |
|------|---------|
| Am I logged in? | `ap auth status -o json` |
| What's installed? | `ap integrations list --installed -o json` |
| What's available? | `ap integrations list --available -o json` |
| What tools does X expose? | `ap tools list --integration <id> -o json` |
| What does tool Y take? | `ap tools describe --integration <id> --tool <name> -o json` |
| Run tool Y | `ap tools call --integration <id> --tool <name> --args '<json>' --info '<why>' -o json` |

---

## Related

- [MCP Aggregation Endpoint](/connect/mcp) — the other way into the gateway.
- [Skills](/connect/skills) — drop-in skills that teach coding agents how to drive AgentPort.
- [Tool Approvals](/tool-approvals) — how `require_approval` calls are routed to a human.
