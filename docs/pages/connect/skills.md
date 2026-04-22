---
title: Agent Skills
nav_title: Skills
---

# Agent Skills

`agentport-skills` is a collection of [Agent Skills](https://agentskills.io) that teach AI coding agents how to drive AgentPort correctly. It ships as a single plugin for Claude Code, Cursor, and OpenAI Codex.

A tool gateway has rules a coding agent cannot infer from the tool list alone — how approval-required responses are surfaced, how to wait for a human decision, how upstream tools are namespaced behind the `agentport__*` meta-tools, when to ask the human before installing an integration, and what to put in the audit-log `--info` / `additional_info` field. These skills give the agent that context, on demand, only when it is relevant.

The source repo is on GitHub: [yakkomajuri/agentport-skills](https://github.com/yakkomajuri/agentport-skills).

---

## Install

```bash
npx skills add yakkomajuri/agentport-skills
```

The same command works in any project. The installer detects which agent is running and writes the skills into the right plugin directory:

| Agent | Plugin layout |
|-------|---------------|
| Claude Code | `.claude-plugin/` |
| Cursor | `.cursor-plugin/` |
| OpenAI Codex | `.codex-plugin/` |

You can install in more than one — the same skills source serves all three platforms.

---

## Updating

```bash
npx skills check    # see if updates are available
npx skills update   # pull the latest version
```

Run `check` periodically; the upstream skills evolve as AgentPort changes (new meta-tools, refined approval flow, etc.).

---

## What's in the bundle

There are three skills. All three are installed together; the agent decides which to load based on the task at hand.

### `agentport-overview`

The foundation skill. It explains the **tool gateway** concept, the three possible outcomes of any tool call (**allowed**, **approval required**, **denied**), and exactly what the agent must do when it hits an approval gate — share the URL with the human in full, wait, then retry the identical call once approval lands.

**When it triggers:** whenever the agent needs to understand how AgentPort works, or whenever the user asks for something that might involve a third-party integration (GitHub, Slack, Stripe, PostHog, email, …). It runs before either of the interface-specific skills below, so the agent always has the gateway model in its head before it picks a transport.

### `agentport-mcp`

The skill for agents wired in as a **native MCP client**. It documents the Streamable HTTP endpoint at `https://app.agentport.sh/mcp` (or the self-hosted URL), transport-layer authentication via `X-API-Key` or `Authorization: Bearer`, and the deliberately narrow `agentport__*` meta-tool surface — `list_installed_integrations`, `list_integration_tools`, `describe_tool`, `call_tool`, `await_approval`, plus install/lifecycle helpers.

It also covers the MCP-specific shape of approval-required responses and the **call-then-`await_approval`-in-the-same-turn** pattern, so the agent doesn't sit waiting for the human to type something in chat before it starts the long poll.

**When it triggers:** the agent's runtime speaks MCP and is connected to AgentPort directly — Claude Desktop, Cursor, any MCP-capable framework. See [MCP Server](/mcp-server) for the server side.

### `agentport-cli`

The skill for code-running agents that **don't speak MCP** but can shell out. It teaches the `ap` command-line workflow end-to-end: check `ap auth status`, list installed integrations with `ap integrations list --installed`, list and describe tools, then call them with `ap tools call --integration … --tool … --args '<json>' --info '<why>'`.

It also pins down the exit-code contract — `0` for success, `2` plus `Approval required: <url>` on stderr for an approval gate, `1` plus `Denied: …` for a hard block — so the agent can branch on outcomes reliably. Always passing `-o json` for stable, machine-readable output is treated as non-negotiable.

**When it triggers:** the agent is running inside a code execution environment with shell access (sandboxes, CI, scripted automations) and reaches AgentPort through the `ap` binary. See [CLI](/connect/cli) for the CLI itself.

---

## Which skill fires when

- The agent always loads **`agentport-overview`** first — it's the prerequisite for the other two and explains the gateway model the rest of the rules depend on.
- If the runtime is a native MCP client, **`agentport-mcp`** loads on top.
- If the runtime drives AgentPort by shelling out to `ap`, **`agentport-cli`** loads on top.

The two interface skills are mutually exclusive in practice — an agent reaches AgentPort through one surface or the other, not both at once.

---

## Related

- [MCP Server](/mcp-server) — the server-side transport the `agentport-mcp` skill targets.
- [CLI](/connect/cli) — the `ap` command surface the `agentport-cli` skill drives.
- [yakkomajuri/agentport-skills on GitHub](https://github.com/yakkomajuri/agentport-skills) — source for the skills themselves.
