---
title: VS Code
nav_title: VS Code
---

# Connecting VS Code to AgentPort

This page walks through wiring **Visual Studio Code** to AgentPort over MCP, so the agent that lives inside VS Code can discover and call tools across every integration you have installed — gated by your approval policies.

VS Code has native MCP support through **GitHub Copilot Chat** (agent mode). If you don't use Copilot, the **Continue** extension also speaks MCP and works the same way.

## Prerequisites

- VS Code (recent version with MCP support — Copilot's agent mode requires a current VS Code release).
- One of:
  - **GitHub Copilot Chat** extension installed and a Copilot subscription that includes agent mode, or
  - The **Continue** extension installed.
- An AgentPort API key. Grab one from the **Connect** page in the AgentPort UI (see [MCP](/connect/mcp#getting-an-api-key)).
- The AgentPort MCP endpoint:
  - Cloud: `https://app.agentport.sh/mcp`
  - Self-hosted: `https://<your-domain>/mcp`

---

## Approach A: GitHub Copilot Chat (recommended)

Copilot Chat reads MCP server definitions from one of two places:

| Scope | File |
|-------|------|
| Workspace | `.vscode/mcp.json` in the project root |
| User (global) | the `mcp` block in your VS Code user `settings.json` |

Workspace config is best when you want the AgentPort server to follow a particular repo. User config is best when you want it available everywhere.

### 1. Create `.vscode/mcp.json`

From the project root:

```json
{
  "servers": {
    "agentport": {
      "type": "http",
      "url": "https://app.agentport.sh/mcp",
      "headers": {
        "X-API-Key": "${input:agentportApiKey}"
      }
    }
  },
  "inputs": [
    {
      "id": "agentportApiKey",
      "type": "promptString",
      "password": true,
      "description": "AgentPort API key"
    }
  ]
}
```

A few things to note about this shape:

- The top-level key is `servers` (not `mcpServers` — VS Code uses its own variant of the schema).
- `type: "http"` tells VS Code to use Streamable HTTP, which is what AgentPort speaks. Don't omit it; the default isn't always HTTP.
- `${input:agentportApiKey}` references the entry in the `inputs` array, so VS Code prompts for the key on first use and stores it in its secret storage instead of writing it to disk in plain text.
- For a self-hosted deployment, swap the `url` for `https://<your-domain>/mcp`.

If you'd rather hardcode the key (don't, but if you must — e.g. for a one-off machine), replace the `headers` block with:

```json
"headers": { "X-API-Key": "ap_your_key_here" }
```

and drop the `inputs` array entirely.

### 2. Start the server in VS Code

Open the Command Palette (`Cmd/Ctrl+Shift+P`) and run **MCP: List Servers**. Pick `agentport` and choose **Start**. VS Code will prompt for the API key the first time and cache it in its secret storage.

### 3. Switch Copilot Chat into agent mode

Open the Copilot Chat panel and switch the mode dropdown from **Ask** to **Agent**. Only agent mode can call MCP tools. The `agentport__*` tools should now show up in the tool picker.

---

## Approach B: Continue extension

If you don't have Copilot, the Continue extension supports MCP servers from its own config. Continue defines MCP servers in `config.yaml` (or as standalone files under `.continue/mcpServers/`):

```yaml
mcpServers:
  - name: agentport
    type: streamable-http
    url: https://app.agentport.sh/mcp
```

Continue's published schema covers `name`, `type`, and `url` for remote servers. Custom-header support varies by version; check the [Continue MCP docs](https://docs.continue.dev/customize/deep-dives/mcp) for the exact field name in your version, or use a self-hosted deployment that accepts the API key via the URL or an OAuth flow.

MCP only fires inside Continue's **agent** mode, same as Copilot.

---

## A note on `agentport-skills`

The [`agentport-skills`](/connect/skills) plugin teaches coding agents the conventions of the gateway — when to ask before installing an integration, how to surface approval URLs, what to put in `additional_info`, how to poll for approvals.

It currently ships installers for **Claude Code, Cursor, and OpenAI Codex**. There is no first-class installer for VS Code Copilot or Continue. The agent will still work without the skills (the meta-tools are self-describing), but it won't have the same out-of-the-box etiquette around approval flows. If your team mostly drives AgentPort from VS Code, lean on the [MCP](/connect/mcp#calling-a-tool-end-to-end) page to learn the expected pattern, and feel free to paste it into a workspace instruction file.

---

## Verifying it works

1. Open Copilot Chat (or Continue) in **agent mode**.
2. Ask: *"List my installed AgentPort integrations."*
3. The agent should call `agentport__list_installed_integrations` and report what it finds.

If you have nothing installed yet, ask it to install one — *"Install the GitHub integration via AgentPort"* — and walk through the OAuth flow it surfaces.

---

## Troubleshooting

**`agentport` server shows as failed in MCP: List Servers.** Open the server's output panel (right-click the entry, **Show Output**). The most common causes are an unreachable `url` (typo, or self-hosted server not running) and a missing or wrong `type` field — for AgentPort this must be `"http"`.

**Agent doesn't see any `agentport__*` tools.** Confirm Copilot Chat is in **Agent** mode, not Ask. Tools from MCP servers are only visible in agent mode. Also re-check the tool picker in Copilot Chat — tools can be toggled off per chat.

**`401 Unauthorized` on every call.** The API key prompt was either skipped or the wrong value was saved. Run **MCP: Reset Cached Tokens** (or delete and re-enter the input) and start the server again. Verify the key works with a quick `curl -H 'X-API-Key: ap_...' https://app.agentport.sh/mcp` — see [MCP Server](/mcp-server#authentication).

---

## See also

- [MCP](/connect/mcp) — how the gateway works end to end, including the call → approval → poll cycle.
- [Tool Approvals](/tool-approvals) — the approval policy model behind every tool call.
- [MCP Server reference](/mcp-server) — transport, auth, and approval internals.
