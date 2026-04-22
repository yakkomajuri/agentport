---
title: Codex
nav_title: Codex
---

# Connecting OpenAI Codex CLI

This page walks through wiring [OpenAI Codex CLI](https://github.com/openai/codex) to AgentPort over MCP, installing the `agentport-skills` plugin so Codex uses the gateway correctly, and configuring auto-approval so AgentPort owns the human-in-the-loop step.

## Prerequisites

- Codex CLI installed and signed in (`codex --version` works).
- An AgentPort account, either on the [cloud](https://app.agentport.sh) or your own [self-hosted](/self-host) instance.
- An AgentPort API key. Generate one from the **Connect** page in the AgentPort UI under **API Keys**.

## Step 1: Add the AgentPort MCP server

Codex stores MCP server entries in `~/.codex/config.toml`. The easiest way to add one is the `codex mcp add` command.

For AgentPort Cloud:

```bash
# change app.agentport.sh for your domain if self-hosting
codex mcp add agentport --url https://app.agentport.sh/mcp
```

After this completes, `codex mcp list` should show an `agentport` entry pointing at the URL above.

## Step 2: Install the AgentPort skills

The MCP tool list alone doesn't tell Codex everything it needs to know — how to handle approval-required responses, when to call `await_approval`, what to put in `additional_info`, and so on. The `agentport-skills` plugin teaches Codex these conventions on demand.

Install it from the same machine:

```bash
npx skills add yakkomajuri/agentport-skills
```

The installer detects Codex and writes the skills into the right plugin directory automatically. See the [Skills page](/connect/skills) for what's in the bundle and how to keep it updated.

## Step 3: Auto-approve AgentPort tool calls in Codex

Codex has its own per-tool approval prompt. Without this step, every AgentPort tool call gets gated twice once by Codex, once by AgentPort. Since AgentPort is the side that knows the integration, the parameters, and your approval policy, it should be the only gate. If you're running Codex in a sandboxed enviroment, AgentPort let's you connect third-party integrations and still use YOLO mode.

Add the following to `~/.codex/config.toml`:

```toml
[mcp_servers.agentport]
default_tools_approval_mode = "approve"
```

This tells Codex to pass AgentPort tool calls through without prompting. AgentPort still enforces your per-tool policy — auto-approve, ask-for-approval, or deny — exactly as configured in the UI.

## Authentication

AgentPort's MCP endpoint accepts either OAuth or an API key sent as `X-API-Key` (or `Authorization: Bearer ...`). If your `codex mcp add` command above didn't prompt for credentials, open `~/.codex/config.toml` and add the header to the server entry. The conventional shape looks like this:

```toml
[mcp_servers.agentport]
url = "https://app.agentport.sh/mcp"
default_tools_approval_mode = "approve"

[mcp_servers.agentport.headers]
X-API-Key = "ap_your_key_here"
```

If your version of Codex names the headers field differently, run `codex mcp add --help` for the exact key — the standard MCP pattern is to attach an `X-API-Key` or `Authorization` header to the server config. The [Codex docs](https://github.com/openai/codex) are the authoritative reference for the current TOML schema.

## Verifying it works

Open a new Codex session and ask:

> List my AgentPort integrations.

Codex should call `agentport__list_installed_integrations` (and load the `agentport-overview` skill on the way in). You should see whatever integrations you've installed in the AgentPort UI come back as a list. If the list is empty, install one from the **Integrations** page first and try again.

## Troubleshooting

- **`agentport__*` tools don't show up.** Confirm `codex mcp list` shows the server, then check that the URL ends in `/mcp` and that the API key header is set. Restart the Codex session after editing `config.toml`.
- **Every tool call still asks Codex for approval.** The `default_tools_approval_mode = "approve"` block must sit under the exact `[mcp_servers.agentport]` section name (matching the name you passed to `codex mcp add`). A typo in the section header silently disables it.
- **Approval-required tools hang.** That's working as intended — AgentPort returned an approval URL. The `agentport-mcp` skill teaches Codex to share the URL and start `agentport__await_approval` in the same turn. If Codex doesn't, re-run `npx skills update` to make sure the skill bundle is current.

## See also

- [Connecting via MCP](/connect/mcp) — endpoint, auth, and the full meta-tool surface.
- [Agent Skills](/connect/skills) — what `agentport-skills` installs and how to update it.
- [Tool Approvals](/tool-approvals) — how AgentPort's approval policies work.
