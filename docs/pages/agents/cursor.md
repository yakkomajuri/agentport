---
title: Cursor
nav_title: Cursor
---

# Cursor

This page walks through wiring [Cursor](https://cursor.com) to AgentPort over MCP, installing the `agentport-skills` plugin so Cursor's agent uses the gateway correctly, and turning on auto-run so Cursor doesn't prompt you on top of AgentPort's own approval flow. For the broader MCP picture see [Connecting via MCP](/connect/mcp).

## Prerequisites

- Cursor installed.
- An AgentPort account — either the cloud deployment at `https://app.agentport.sh` or a self-hosted instance (default `http://localhost:4747`).

In the steps below, use whichever MCP URL applies:

| Deployment | MCP URL |
|------------|---------|
| Cloud | `https://app.agentport.sh/mcp` |
| Self-hosted | `http://localhost:4747/mcp` |

## Step 1: Add the MCP server

Open (or create) `~/.cursor/mcp.json` and add an `agentport` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "agentport": {
      "url": "https://app.agentport.sh/mcp"
    }
  }
}
```

For a local self-hosted instance, swap the URL:

```json
{
  "mcpServers": {
    "agentport": {
      "url": "http://localhost:4747/mcp"
    }
  }
}
```

If `~/.cursor/mcp.json` already exists, merge the `agentport` entry into the existing `mcpServers` object rather than overwriting the file.

Cursor handles authentication via the MCP server's OAuth flow — there's no API key to paste. After saving the file, open Cursor's Settings, find the MCP panel, and you'll see `agentport` listed. Click it to start the OAuth handshake; Cursor will open your browser, you sign in to AgentPort, and the panel updates to show the connection as authenticated. The `agentport__*` tools will then be available in chat.

## Step 2: Install the AgentPort skills

```bash
npx skills add yakkomajuri/agentport-skills
```

This installs the [`agentport-skills`](/connect/skills) plugin into `.cursor-plugin/`, which teaches Cursor's agent the conventions of the gateway — how the `agentport__*` meta-tools fit together, how to surface approval URLs, and how to long-poll `await_approval` in the same turn.

## Step 3: Enable auto-approval

AgentPort gates approvals itself: every tool call routes through your configured policy and, when needed, asks you for explicit approval via the AgentPort UI. There's no benefit to Cursor also prompting you before it forwards the call — you'd end up confirming the same action twice.

Enable "Auto-run mode" in Cursor Settings → Chat. With auto-run on, Cursor will fire `agentport__*` tools without an in-editor prompt, and AgentPort's [tool approvals](/tool-approvals) become the single, authoritative gate.

## Verifying it works

Open a Cursor chat and ask:

> List my AgentPort integrations.

Cursor should call `agentport__list_installed_integrations` and report back. If you have nothing installed yet, ask it to install one — for example, "install the GitHub integration on AgentPort" — and watch the approval flow play out.

## Troubleshooting

- **`agentport` doesn't appear in the MCP panel.** Confirm `~/.cursor/mcp.json` is valid JSON and that the `agentport` entry sits inside `mcpServers`. Reopen Cursor after editing the file so it re-reads the config.
- **OAuth fails or the panel keeps showing "not authenticated".** Click the entry in the MCP panel again to retry the flow, and make sure the URL in `mcp.json` ends with `/mcp` and points at a reachable AgentPort instance (cloud or your self-hosted host/port).
- **Auto-run isn't engaging for `agentport__*` tools.** Double-check that "Auto-run mode" is on under Settings → Chat, and that you don't have a per-tool deny rule overriding it. With auto-run off, Cursor will still prompt you — that's a Cursor-side setting, not an AgentPort one.

## See also

- [Connecting via MCP](/connect/mcp) — endpoint, transport, and other clients.
- [Agent Skills](/connect/skills) — what the `agentport-skills` plugin does and how to update it.
- [Tool Approvals](/tool-approvals) — how AgentPort decides when to prompt you.
