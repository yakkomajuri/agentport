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

Configuration lives at `~/.config/agent-port/config.json` and is managed by the CLI so you shouldn't have to manually edit it. It stores the server URL, the chosen auth mode (currently `api_key`), the API key, and your default output format.

The default server URL is `https://app.agentport.sh`. Override it with the `AGENT_PORT_URL` environment variable, or persist a different instance with:

```sh
ap auth set-instance-url https://ap.example.com
```

Switching instances clears any stored credentials, so you'll need to re-run `ap auth login`.

## Skills

You should really install the [AgentPort Skills](/connect/skills) for your agent to use the AgentPort CLI most efficiently.

## Authentication

The CLI authenticates with an API key issued from the AgentPort UI (Settings → API Keys):

```sh
ap auth login --api-key ap_...
```

> Browser OAuth is temporarily unavailable: MCP-audience OAuth tokens no longer unlock the REST API (security audit finding 09), and the CLI does not yet have a REST-scoped OAuth issuer. API keys are the supported CLI credential until that lands.

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
| `ap auth login --api-key <key>` | Store an API key issued from the UI as the CLI credential. |
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
| `ap tools call --integration <id> --tool <name> --args <json>` | Execute a tool. Pass `--info <text>` to record intent for reviewers, or `--wait` to keep waiting through approval gates and retry automatically. |
| `ap tools await-approval --request-id <id>` | Wait for an approval decision. You can pass `--approval-url <url>` instead of `--request-id` if that's what you have. |

Examples:

```sh
ap tools list --integration github -o json
ap tools describe --integration github --tool create_issue -o json
ap tools call --integration github --tool create_issue \
  --args '{"repo":"yakkomajuri/agent-port","title":"docs: typo"}' \
  --info "Filing the typo Sam noticed in the README." \
  -o json
ap tools call --integration github --tool create_issue \
  --args '{"repo":"yakkomajuri/agent-port","title":"docs: typo"}' \
  --info "Filing the typo Sam noticed in the README." \
  --wait --wait-timeout 600 \
  -o json
ap tools await-approval \
  --approval-url https://app.agentport.sh/approve/550e8400-e29b-41d4-a716-446655440000 \
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
| `1` | Error, denial, or a non-awaitable approval state. Message on stderr. | Stop. Don't retry, don't try a different tool to reach the same outcome. |
| `2` | Approval required, or still pending after `--wait-timeout`. Stderr contains `Approval required: <url>` or `Approval still pending: <url>`. | Surface the URL to the human. Either use `ap tools call --wait`, or wait separately with `ap tools await-approval` and then retry the **identical** command. |

See [Tool Approvals](/tool-approvals) for how the approval flow works on the server side.

`ap tools await-approval` also uses exit codes:

| Exit code | Meaning | What to do |
|-----------|---------|------------|
| `0` | Approved. Stdout includes `status: "approved"`. | Retry the original `ap tools call` if you did not use `--wait`. |
| `1` | Denied, expired, consumed, or invalid request. | Stop and surface the status. |
| `2` | Still pending at the requested timeout. | Keep waiting or ask the human to decide. |

### Quick reference

| Goal | Command |
|------|---------|
| Am I logged in? | `ap auth status -o json` |
| What's installed? | `ap integrations list --installed -o json` |
| What's available? | `ap integrations list --available -o json` |
| What tools does X expose? | `ap tools list --integration <id> -o json` |
| What does tool Y take? | `ap tools describe --integration <id> --tool <name> -o json` |
| Run tool Y | `ap tools call --integration <id> --tool <name> --args '<json>' --info '<why>' -o json` |
| Run tool Y and wait through approvals | `ap tools call --integration <id> --tool <name> --args '<json>' --info '<why>' --wait -o json` |
| Wait on an approval gate | `ap tools await-approval --approval-url '<url>' -o json` |

---

## Related

- [MCP Aggregation Endpoint](/connect/mcp) — the other way into the gateway.
- [Skills](/connect/skills) — drop-in skills that teach coding agents how to drive AgentPort.
- [Tool Approvals](/tool-approvals) — how `require_approval` calls are routed to a human.
