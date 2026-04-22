---
title: OpenClaw
nav_title: OpenClaw
---

# Connecting OpenClaw

[OpenClaw](https://github.com/) is a code-running CLI coding agent. Unlike Claude Code, Cursor, or Codex, it does **not** speak MCP natively — but it can run shell commands, which is all it needs to drive AgentPort through the [`ap` CLI](/connect/cli).

This page walks through having OpenClaw set itself up. You generate an API key, paste a short prompt into OpenClaw, and OpenClaw handles the rest — installing the CLI, authenticating it, and pulling in the [agent skills](/connect/skills) that teach it the gateway's conventions.

## Prerequisites

- OpenClaw installed and working in your shell.
- An AgentPort account, either on the [cloud](https://app.agentport.sh) or your own [self-hosted](/self-host) instance.
- An AgentPort API key (see Step 1).

## Step 1: Generate an API key

In the AgentPort UI, open the **Developer** page and scroll to **API Keys**. Generate a new key and copy it somewhere safe.

API keys are the right credential for an unattended agent like OpenClaw — they let it install integrations and call tools, but not change approval policies, view logs, or anything else administrative. The agent gets exactly the surface it needs.

## Step 2: Paste this prompt into OpenClaw

Start an OpenClaw session and paste the following, replacing `<your-api-key>` with the key from Step 1:

```text
Let's install AgentPort for managing third-party integrations.

1. Install the AgentPort CLI from npm with `npm install -g agentport-cli`
2. Authenticate it by running `ap auth login --api-key <your-api-key>`
3. Add the AgentPort skills from https://github.com/yakkomajuri/agentport-skills
```

Each step is something OpenClaw can do entirely on its own from a shell:

1. **Install the CLI.** `npm install -g agentport-cli` puts the `ap` (and `agentport`) binaries on your PATH. Full reference: [CLI](/connect/cli).
2. **Authenticate.** `ap auth login --api-key …` writes the key into `~/.config/agent-port/config.json` so subsequent `ap` calls are authorized. There's no browser flow because there doesn't need to be — the key is already in OpenClaw's hands.
3. **Add the skills.** The [`agentport-skills`](/connect/skills) plugin teaches OpenClaw the parts of the gateway that aren't obvious from the CLI's `--help` text — discovery order, how to handle the approval-required exit code, what to put in `--info`, and so on. The relevant skill for OpenClaw is `agentport-cli`.

## What you can do next

In the same OpenClaw session, ask:

> List my AgentPort integrations.

OpenClaw should run `ap integrations list --installed -o json` and report back what you have connected. If the list is empty, install something from the **Integrations** page in the AgentPort UI and try again. From here, OpenClaw can describe tools, call them, and surface approval URLs to you when a call is gated.

## How OpenClaw uses AgentPort

OpenClaw drives AgentPort by shelling out to the `ap` CLI: `ap auth status` to confirm it's logged in, `ap integrations list --installed` to find what it can use, `ap tools describe` to read a tool's input schema, and `ap tools call --integration <id> --tool <name> --args '<json>' --info '<why>' -o json` to actually execute a tool.

The [`agentport-cli` skill](/connect/skills) is what makes this work end-to-end. It pins down the exit-code contract — `0` for success, `2` plus `Approval required: <url>` on stderr when a tool needs human sign-off, `1` for a hard denial — so OpenClaw can branch on outcomes correctly. When it hits an approval gate, the skill tells it to surface the URL to you in chat and retry the **identical** command once the approval lands.

See the [CLI reference](/connect/cli) for every command and flag, and the [Skills page](/connect/skills) for the full bundle.

## Troubleshooting

- **`ap: command not found` after install.** The npm global install directory isn't on your PATH. Run `npm config get prefix` to find it; the binaries live in `<prefix>/bin`. Add that to your shell's PATH and start a new OpenClaw session so it picks up the change.
- **`ap auth login` fails or `ap auth status` shows `auth_mode: none`.** Re-check the API key — it should start with `ap_` and be pasted in full with no surrounding whitespace. If you're on a self-hosted instance, point the CLI at it first with `ap auth set-instance-url https://<your_domain>` (this clears any previous credentials), then re-run `ap auth login --api-key …`.

## See also

- [AgentPort CLI](/connect/cli) — full command reference for the `ap` binary OpenClaw drives.
- [Agent Skills](/connect/skills) — the `agentport-cli` skill that teaches OpenClaw the gateway's conventions.
- [Tool Approvals](/tool-approvals) — how `require_approval` calls are routed to a human.
