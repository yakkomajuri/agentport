---
title: Connecting via MCP
nav_title: MCP
---

# Connecting via MCP

AgentPort exposes a single Streamable HTTP MCP endpoint that acts as a gateway to every integration you have installed. Connecting your agent to our MCP allows it to install integrations and call tools on any integrations you have installed, always according to your defined approval policies.

## Endpoint

| Deployment | URL |
|------------|-----|
| Cloud | `https://app.agentport.sh/mcp` |
| Self-hosted | `https://<your_domain>/mcp` |


## Authentication

The MCP can authenticate via OAuth or an API key. We recommend authenticating using OAuth and most clients will automatically walk you through this. 


### Getting an API key

You can get an API key from the "Connect" page in the AgentPort UI. These keys allow installing integrations and calling tools but not updating policies, seeing logs, etc.

## Tools


| Tool | Purpose |
|------|---------|
| `agentport__list_installed_integrations` | List integrations installed for your user |
| `agentport__list_available_integrations` | Show all integrations that are available to be installed |
| `agentport__install_integration` | Start the auth flow to authenticate to the integration and install it |
| `agentport__get_auth_status` | Get auth status for a given integration |
| `agentport__list_integration_tools` | List or search tools across installed integrations |
| `agentport__describe_tool` | Returns input schema and current approval policy for a given tool |
| `agentport__call_tool` | Invoke an upstream tool (Stripe, GitHub, Gmail, ...) |
| `agentport__await_approval` | Long-poll for the human's decision on an approval-gated call |


## Connect your agent

All clients use the same shape: a single `agentport` MCP server pointing at the URL above with the key in an `X-API-Key` header.

### Claude Desktop

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentport": {
      "url": "https://app.agentport.sh/mcp",
      "headers": {
        "X-API-Key": "ap_your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. The `agentport__*` tools will appear in the tool list.

### Claude Code

Edit `.claude/settings.json` (project) or `~/.claude/settings.json` (global):

```json
{
  "mcpServers": {
    "agentport": {
      "url": "https://app.agentport.sh/mcp",
      "headers": {
        "X-API-Key": "ap_your_key_here"
      }
    }
  }
}
```

Pair this with the [agentport-skills plugin](/connect/skills) so Claude Code knows the right way to use the gateway (discovery, approval polling, `additional_info` on every call).

### Cursor

Open Cursor settings, find the MCP section, and add:

```json
{
  "mcpServers": {
    "agentport": {
      "url": "https://app.agentport.sh/mcp",
      "headers": {
        "X-API-Key": "ap_your_key_here"
      }
    }
  }
}
```

### VS Code (Copilot / Continue)

Add to `.vscode/mcp.json` (or your client's equivalent MCP settings file):

```json
{
  "servers": {
    "agentport": {
      "url": "https://app.agentport.sh/mcp",
      "headers": {
        "X-API-Key": "ap_your_key_here"
      }
    }
  }
}
```


## Calling a tool, end to end

A typical sequence the agent runs:

1. `agentport__list_integration_tools(integration_id="github")` to see what's available.
2. `agentport__describe_tool(integration_id="github", tool_name="create_issue")` to get the input schema and the current approval mode.
3. `agentport__call_tool(...)` with the arguments and an `additional_info` string explaining intent.

### Auto-approved tool

The result comes back immediately, just like a normal tool call. Nothing for you to do.

### Approval-required tool

The agent gets a text response that contains an approval URL, e.g.:

```
This tool was marked by a human as needing approval. Share this URL with
a human and explain what you were trying to do:
https://app.agentport.sh/approve/a1b2c3d4-...

Then call agentport__await_approval(request_id="a1b2c3d4-...") to be
notified as soon as they decide.
```

A well-behaved agent will paste that URL into chat for you and immediately start polling `agentport__await_approval` in the same turn. You open the URL, see the exact tool name and parameters (and the agent's `additional_info` note), and approve or deny. The agent's poll returns either the actual tool result, a denial, or "still pending" — in which case it polls again.

You can also tick **Always approve** on the approval screen to auto-approve future calls to that tool.

### Denied tool

The call returns "This tool has been blocked and cannot be executed." A correctly behaved agent will stop and surface this to you rather than try to route around it.

## Helping coding agents do this right

If you're using AgentPort from a coding agent (Claude Code, Cursor, etc.), install the [agentport-skills plugin](/connect/skills). The `agentport-mcp` skill teaches the agent the conventions that aren't obvious from the tool schemas alone:

- Always include a real `additional_info` sentence so approval reviewers have context.
- Make opaque IDs verifiable in `additional_info` (link to the Stripe customer, name the Gmail recipient, etc.).
- Start `await_approval` immediately after sharing an approval URL — don't wait for chat reply.
- Don't retry past a `deny`.

## MCP vs CLI

- **MCP** is the right choice when your AI client speaks MCP natively (Claude Desktop, Claude Code, Cursor, VS Code). The agent gets discovery, calling, and approval polling as first-class tools.
- The **[CLI](/connect/cli)** is for shell-based agents and scripts, or for ad-hoc calls from your terminal. It exposes the same gateway with the same approval behaviour.

Pick whichever your client supports best — both go through the same policy engine and audit log.

## See also

- [MCP Server reference](/mcp-server) — transport, auth, approval flow internals
- [Tool Approvals](/tool-approvals) — how approval policies work
- [agentport-skills](/connect/skills) — agent skills for using the gateway correctly
- [CLI](/connect/cli) — the command-line alternative
