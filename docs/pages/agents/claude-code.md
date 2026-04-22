---
title: Claude Code
nav_title: Claude Code
---

# Claude Code

This page walks through wiring [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic's CLI) to AgentPort over MCP, installing the `agentport-skills` plugin so the agent uses the gateway correctly, and configuring auto-approval so Claude Code doesn't prompt you on top of AgentPort's own approval flow. For the broader MCP picture see [Connecting via MCP](/connect/mcp).

## Prerequisites

- Claude Code installed and on your `PATH` (`claude --version` works).
- An AgentPort account — either the cloud deployment at `https://app.agentport.sh` or a self-hosted instance (default `http://localhost:4747`).

In the steps below, replace `<mcpUrl>` with whichever applies:

| Deployment | MCP URL |
|------------|---------|
| Cloud | `https://app.agentport.sh/mcp` |
| Self-hosted | `http://localhost:4747/mcp` |

## Step 1: Add the MCP server

Run the following command to connect to the AgentPort MCP server:

```bash
# change app.agentport.sh for your domain if self-hosting
claude mcp add agentport -s user --transport http https://app.agentport.sh/mcp
```


## Step 2: Install the AgentPort skills

```bash
npx skills add yakkomajuri/agentport-skills
```

This installs the [`agentport-skills`](/connect/skills) plugin, which teaches Claude Code the conventions of the gateway, such as how the `agentport__*` tools fit together, how to surface approval URLs, and how to long-poll `await_approval` in the same turn.

## Step 3: Auto-approve AgentPort tool calls

AgentPort gates approvals itself: every tool call routes through your configured policy and, when needed, asks you for explicit approval via the AgentPort UI. There's no benefit to Claude Code also prompting you before it forwards the call as you'd end up confirming the same action twice, so you can allow AgentPort MCP tool calls by default. If you're running Claude Code in a sandboxed enviroment, AgentPort let's you connect third-party integrations and still run in "bypass permissions" mode.

Add the following to `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["mcp__agentport__*"]
  }
}
```

## Step 4: Authenticate

Start a Claude Code session and run:

```
/mcp
```

Pick `agentport` from the list and follow the OAuth flow. Once it completes, Claude Code will list the `agentport__*` tools alongside any others you have configured.

## Verifying it works

In a Claude Code session, ask:

> List my AgentPort integrations.

Claude Code should call `agentport__list_installed_integrations` and report back. If you have nothing installed yet, ask it to install one — for example, "install the GitHub integration on AgentPort" and watch the approval flow play out.

## Troubleshooting

- **`agentport` doesn't appear in `/mcp`.** Re-run `claude mcp list` to confirm the server is registered. If it's missing, repeat Step 1 — make sure you used `-s user` and the URL ends in `/mcp`.
- **`401 Unauthorized` from the MCP endpoint.** The OAuth session has expired or never completed. Run `/mcp` again and walk through the auth flow.
- **An approval URL isn't shown in chat.** This usually means the `agentport-skills` plugin isn't installed or didn't load. Re-run `npx skills add yakkomajuri/agentport-skills` from the project directory and restart Claude Code.

## See also

- [Connecting via MCP](/connect/mcp) — endpoint, transport, and other clients.
- [Agent Skills](/connect/skills) — what the `agentport-skills` plugin does and how to update it.
- [Tool Approvals](/tool-approvals) — how AgentPort decides when to prompt you.
