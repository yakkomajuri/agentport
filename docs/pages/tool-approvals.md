---
title: Tool Approvals
---
# Tool Approvals

Agent Port is safe by default: every tool call requires explicit approval before execution.

## How it works

1. **Default deny** — All discovered tools start in `require_approval` mode. Nothing runs unless explicitly allowed.

2. **Per-tool modes** — Each tool on an installed integration has a fallback execution mode:
   - `require_approval` (default) — calls are blocked until approved
   - `allow` — calls execute immediately without approval
   - `deny` — calls are always blocked and can never execute

   This mode is the **fallback**: it applies only when no conditional rule (below) matches the call.

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

## Conditional rules (granular policy)

The fallback mode decides what happens to *every* call to a tool. Conditional rules let you make the decision depend on the **arguments** of the call. A tool's effective policy is therefore:

> **rules first (if any match), otherwise the fallback mode.**

Each rule belongs to one (org, integration, tool) and has:

- a **priority** (integer; lower numbers are evaluated first)
- an **effect**: `allow`, `require_approval`, or `deny`
- an **enabled** flag (disabled rules are ignored)
- one or more **conditions**

### Conditions and operators

A condition tests a single named parameter of the call:

| Operator | Matches when the parameter… |
|----------|------------------------------|
| `equals` | equals one of the values exactly |
| `contains` | contains one of the values as a substring |
| `starts_with` | starts with one of the values |
| `ends_with` | ends with one of the values |

No regular expressions and no negation in the current version.

Matching semantics:

- **Values inside one condition are OR-ed** — `to ends_with [@useskald.com, @example.com]` matches either domain.
- **An array-valued parameter is OR-ed across its elements** — if `to` is a list of recipients, the condition matches when *any* recipient matches.
- **Conditions inside one rule are AND-ed** — every condition must match for the rule to apply.
- **A missing parameter never matches.**

### Evaluation order (precedence)

For each tool call:

1. Collect the **enabled** rules for the org + integration + tool.
2. Consider only the rules that **match** the call's arguments.
3. Pick the matching rule(s) with the **lowest priority number**.
4. If several rules tie on priority, effect precedence decides: **`deny` > `require_approval` > `allow`**.
5. If **no rule matches**, fall back to the tool's `ToolExecutionSetting.mode`.
6. If there is **no setting** either, the call requires approval (`require_approval`).

The matched rule's id is recorded on the resulting log entry and approval request for auditing.

### Example: `send_email`

Suppose `send_email` should run freely to your own domains, but always pause for review when the subject looks sensitive. With a fallback of **Ask for approval**:

| Priority | Rule | If param | Operator | Values | Then |
|----------|------|----------|----------|--------|------|
| 100 | Allow known recipients | `to` | ends with | `@useskald.com`, `@example.com` | Allow |
| 100 | Review sensitive subjects | `subject` | contains | `password`, `secret` | Ask |

A mail to `ops@useskald.com` with subject `"weekly report"` matches only the first rule → **allowed**. A mail to `ops@useskald.com` with subject `"your password"` matches both rules at priority 100 → `require_approval` wins over `allow` → **asks for approval**. A mail to `someone@gmail.com` matches neither rule → falls back to **Ask for approval**.

### Second factor for allow rules

Just like escalating the fallback mode to `allow`, **creating or updating a rule whose effect is `allow`** (or enabling such a rule) requires a fresh TOTP code when the user has two-factor enabled.

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
1. Evaluate the tool's enabled **conditional rules** against the call arguments (see [Conditional rules](#conditional-rules-granular-policy)). The winning rule's effect decides the outcome.
2. If no rule matches, use the tool's fallback execution setting → if `allow`, execute; if `deny`, block permanently.
3. Otherwise → block and create/reuse an approval request.

## API endpoints

See [API Reference](api.md) for full details:
- `PUT /api/tool-settings/{integration}/{tool}` — set the fallback execution mode
- `GET /api/tool-settings/{integration}/{tool}/rules` — list conditional rules
- `POST /api/tool-settings/{integration}/{tool}/rules` — create a rule
- `PATCH /api/tool-settings/{integration}/{tool}/rules/{rule_id}` — update a rule
- `DELETE /api/tool-settings/{integration}/{tool}/rules/{rule_id}` — delete a rule
- `POST /api/tool-settings/{integration}/{tool}/rules/test` — test args against the current policy
- `GET /api/tool-approvals/requests` — list approval requests
- `POST /api/tool-approvals/requests/{id}/await` — long-poll for a decision
- `POST /api/tool-approvals/requests/{id}/approve-once` — one-time approval
- `POST /api/tool-approvals/requests/{id}/allow-tool` — allow the tool without future approvals
- `POST /api/tool-approvals/requests/{id}/deny` — deny request
- `GET /api/org-settings` / `PATCH /api/org-settings` — read or change the org's approval expiry window

## Logging

All blocked calls generate log entries with `outcome: "approval_required"` and a reference to the approval request ID. Successful calls log `outcome: "executed"`. When the decision came from a conditional rule, the log entry and the approval request both record the `matched_rule_id`.
