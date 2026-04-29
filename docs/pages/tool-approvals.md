---
title: Tool Approvals
---
# Tool Approvals

Agent Port is safe by default: every tool call requires explicit approval before execution.

## How it works

1. **Default deny** — All discovered tools start in `require_approval` mode. Nothing runs unless explicitly allowed.

2. **Per-tool modes** — Each tool on an installed integration has an execution mode:
   - `require_approval` (default) — calls are blocked until approved
   - `allow` — calls execute immediately without approval

3. **Approval flow** — When a blocked call happens:
   - Agent Port creates a pending approval request
   - Returns a `403` (REST) or an approval-required text response (MCP) with an `approval_url` and the `approval_request_id`
   - The agent presents the link to the user
   - The user reviews and decides in the UI
   - The agent either retries the call, long-polls `/api/tool-approvals/requests/{id}/await`, uses `ap tools await-approval`, or uses `ap tools call --wait` / `agentport__await_approval(request_id)` depending on the transport

4. **MCP long-poll flow** — Over the MCP surface, the agent should call `agentport__await_approval(request_id)` immediately after sharing the approval URL with the human, instead of waiting for a chat reply. The meta-tool blocks until the human approves, denies, or the server's long-poll budget (`approval_long_poll_timeout_seconds`, default 240 s) elapses. On approve it returns the real upstream tool result — no retry needed. On timeout it returns a "still pending" message so the agent can loop back in without human intervention.

5. **CLI / REST await flow** — Over the CLI and REST surfaces, the same long-poll budget is available at `POST /api/tool-approvals/requests/{id}/await`. `ap tools await-approval` wraps that endpoint directly, and `ap tools call --wait` uses it under the hood before retrying the original tool call automatically.

6. **Decision options**:
   - **Approve once** — allows this exact call one time; the agent must retry to consume it
   - **Allow tool forever** — sets this tool to `allow`, so future calls to the same integration + tool run without approval regardless of parameters
   - **Deny** — rejects the request

7. **Optional second factor (TOTP)** — Users who turn on two-factor in Settings must enter a 6-digit authenticator code (or a recovery code) alongside every decision. Recovery codes are single-use.

## Tool-level allow policies

When a user chooses "allow tool forever", Agent Port updates that tool's execution mode to `allow`. Future calls with the **same integration and tool** are allowed automatically, regardless of arguments.

## Request lifecycle

```
pending → approved (approve_once) → consumed (on retry)
pending → approved (allow_tool_forever) → tool mode set to allow
pending → denied
pending → expired (after the configured expiry window)
```

Duplicate blocked calls with the same arguments reuse the same pending request.

## Approval expiration

Pending approval requests expire after a configurable window. The instance default is set by `APPROVAL_EXPIRY_MINUTES` (defaults to 10 minutes). Each org can override this in **Settings → Approvals**, or via the API (1–1440 minutes):

- `GET /api/org-settings` — read the current value and instance default
- `PATCH /api/org-settings` — set `approval_expiry_minutes` (or `null` to revert to the default)

The override applies to newly created requests; in-flight pending requests keep their original expiry.

## Policy evaluation order

For each tool call:
1. Check the tool's execution setting → if `allow`, execute
2. Otherwise → block and create/reuse approval request

## API endpoints

See [API Reference](api.md) for full details:
- `PUT /api/tool-settings/{integration}/{tool}` — set execution mode
- `GET /api/tool-approvals/requests` — list approval requests
- `POST /api/tool-approvals/requests/{id}/await` — long-poll for a decision
- `POST /api/tool-approvals/requests/{id}/approve-once` — one-time approval
- `POST /api/tool-approvals/requests/{id}/allow-tool` — allow the tool without future approvals
- `POST /api/tool-approvals/requests/{id}/deny` — deny request
- `GET /api/org-settings` / `PATCH /api/org-settings` — read or change the org's approval expiry window

## Logging

All blocked calls generate log entries with `outcome: "approval_required"` and a reference to the approval request ID. Successful calls log `outcome: "executed"`.
