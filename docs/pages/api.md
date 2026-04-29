---
title: API Reference
---
# API Reference

The server runs on port `4747` by default. Interactive docs (Swagger UI) are available at `http://localhost:4747/docs`.

All endpoints except `/api/users/register`, `POST /api/auth/token`, `GET /api/auth/verify-email`, `POST /api/auth/verify-email-code`, `POST /api/auth/resend-verification-code`, `POST /api/auth/resend-verification-by-email`, `GET /api/auth/callback`, `GET /api/auth/google/login`, `GET /api/auth/google/callback`, and `GET /api/integrations` require authentication. Pass a bearer token in every request:

```
Authorization: Bearer <token>
```

---

## Users

### `POST /api/users/register`

Create a new user. Automatically creates an organization and makes the user its owner. No auth required.

When `IS_SELF_HOSTED=true`, the first successful registration becomes the admin (`is_admin=true`) and
all subsequent registrations return `409` (one org per self-hosted instance).

**Body:**
```json
{
  "email": "alice@example.com",
  "password": "s3cr3t",
  "org_name": "Acme Corp"
}
```

**Response `201`:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "org_id":  "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "email":   "alice@example.com",
  "email_verification_required": true,
  "verification_token": "eyJhbGciOiJIUzI1NiIs...",
  "resend_available_at": "2026-04-17T20:20:07.149028+00:00"
}
```

---

## Auth

### `POST /api/auth/token`

Log in and get a JWT bearer token. Uses OAuth2 password form encoding (`application/x-www-form-urlencoded`). No auth required.

**Form fields:**
- `username` — the user's email address
- `password` — the user's password

**Response `200`:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

**Response `403` when email verification is still pending:**
```json
{
  "detail": {
    "error": "email_verification_required",
    "message": "Enter the 6-digit verification code we sent to your email.",
    "email": "alice@example.com",
    "verification_token": "eyJhbGciOiJIUzI1NiIs...",
    "resend_available_at": "2026-04-17T20:20:07.149028+00:00"
  }
}
```

### `GET /api/auth/verify-email`

Verify an email from the link sent by email. No auth required.

**Query params:** `token`

**Response `200`:**
```json
{
  "message": "Email verified successfully",
  "email": "alice@example.com"
}
```

### `POST /api/auth/verify-email-code`

Verify an email using the 6-digit code plus the temporary `verification_token` returned by signup or unverified login. No auth required.

After 5 wrong code attempts the current code is burned: further submissions (including the correct code) will fail until a new code is requested via `POST /api/auth/resend-verification-code`. Both `GET /api/auth/verify-email` and `POST /api/auth/verify-email-code` are additionally capped at 10 requests per minute per client IP — excess requests receive `429 Too Many Requests`.

**Body:**
```json
{
  "code": "123456",
  "verification_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response `200`:**
```json
{
  "message": "Email verified successfully",
  "access_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

### `POST /api/auth/resend-verification-code`

Resend the verification email using the temporary `verification_token`. No auth required.

You can only resend once every 10 minutes — unless the previously issued code was burned by too many wrong attempts, in which case the cooldown is bypassed so the user can recover.

**Body:**
```json
{
  "verification_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response `200`:**
```json
{
  "message": "Verification email sent",
  "resend_available_at": "2026-04-17T20:30:07.149028+00:00"
}
```

**Response `429`:**
```json
{
  "detail": {
    "error": "verification_email_rate_limited",
    "message": "Verification email already sent recently. Try again later.",
    "resend_available_at": "2026-04-17T20:30:07.149028+00:00"
  }
}
```

### `POST /api/auth/{integration_id}/start`

Begin an OAuth flow for an installed integration. Requires auth.

**Response:**
```json
{
  "authorization_url": "https://app.posthog.com/oauth/authorize?...",
  "state": "abc123"
}
```

Open `authorization_url` in a browser. After the user authorizes, the provider redirects to the callback URL and tokens are stored automatically.

### `GET /api/auth/callback`

OAuth redirect target. Handled automatically by the server — do not call directly.
On success, the browser is redirected to the integration detail page in the UI at `/integrations/{integration_id}`.

**Query params:** `code`, `state` (set by the OAuth provider)

### `GET /api/auth/google/login`

Begin a "Sign in with Google" flow for a user logging in to agent-port itself. No auth required.
Completely independent from the Google integration's OAuth — set `GOOGLE_LOGIN_CLIENT_ID` and
`GOOGLE_LOGIN_CLIENT_SECRET` to enable.

**Response `200`:**
```json
{ "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
```

The UI redirects the browser to `authorization_url`. Returns `503` if Google login is not configured.

### `GET /api/auth/google/callback`

Google redirects here after the user approves. Handled automatically — do not call directly.
On success, the browser is redirected to `${UI_BASE_URL}/login/google/callback#access_token=<jwt>&token_type=bearer`.
On failure, the browser is redirected to `${UI_BASE_URL}/login?google_error=<code>`.

**Query params:** `code`, `state`, `error` (set by Google)

If a user with the returned Google account's email already exists, that account is linked (and kept signed
in with their existing password if any). Otherwise a new user + org are created, subject to
`BLOCK_SIGNUPS` and `IS_SELF_HOSTED` rules.

---

## Public Config

### `GET /api/config`

Returns non-sensitive runtime config used by the UI. Public — no auth required.

**Response `200`:**
```json
{
  "is_self_hosted": true,
  "billing_enabled": false
}
```

---

## Integrations

Browse the catalog of bundled integrations. Public — no auth required.

### `GET /api/integrations`

List all available bundled integrations.

**Query params:**
- `type` — filter by integration type (`remote_mcp`, `api`)

**Response:**
```json
[
  {
    "id": "posthog",
    "name": "PostHog",
    "type": "remote_mcp",
    "description": "Product analytics and feature flags",
    "docs_url": "https://posthog.com/docs/model-context-protocol",
    "url": "https://mcp.posthog.com/mcp",
    "auth": [
      { "method": "oauth" },
      { "method": "token", "label": "PostHog Personal API Key", "header": "Authorization", "format": "Bearer {token}" }
    ]
  }
]
```

### `GET /api/integrations/{id}`

Get a single bundled integration by ID (e.g. `github`, `posthog`).

---

## Installed integrations

Manage configured instances of integrations, scoped to your organization.

### `GET /api/installed`

List all installed integrations for your org.

### `POST /api/installed`

Install an integration.

**Body:**
```json
{
  "integration_id": "posthog",
  "auth_method": "token",
  "token": "phx_..."
}
```

- `auth_method` — `"token"` or `"oauth"`
- `token` — required when `auth_method` is `"token"`

**Response:** `201` with the installed integration object.

### `DELETE /api/installed/{integration_id}`

Remove an installed integration by ID.

---

## Tools

### `GET /api/tools`

List tools across all installed integrations in your org. Each tool includes an `execution_mode` field indicating whether it can be called freely or requires approval.

**Response:**
```json
[
  {
    "integration_id": "posthog",
    "name": "get_events",
    "description": "...",
    "input_schema": {},
    "execution_mode": "require_approval"
  }
]
```

### `GET /api/tools/{integration_id}`

List tools for a single installed integration. Each tool includes its `execution_mode`.

### `POST /api/tools/{integration_id}/call`

Call a tool on an installed integration.

**Body:**
```json
{
  "tool_name": "get_events",
  "args": {
    "project_id": 1234,
    "event": "$pageview"
  },
  "additional_info": "Checking recent pageviews to decide whether to roll out the new landing page."
}
```

- `additional_info` — optional free-text explanation the agent can attach to justify the call. Shown to humans reviewing the approval request and persisted on the log entry. It is **never** forwarded to the upstream tool, so it cannot conflict with tool argument schemas. Omit the field entirely when not needed.

When calling tools via the MCP endpoint (`/mcp`), pass the same value as an `additional_info` property inside the tool-call `arguments`; the server strips it from the arguments before forwarding.

**Response `200` (allowed):**
```json
{
  "content": [ { "type": "text", "text": "..." } ],
  "isError": false
}
```

**Response `403` (approval required):**

When a tool requires approval and no matching policy exists, the call is blocked:

```json
{
  "error": "approval_required",
  "approval_request_id": "550e8400-...",
  "approval_url": "/approve/550e8400-...",
  "message": "Tool call requires approval before execution.",
  "integration_id": "posthog",
  "tool_name": "get_events"
}
```

The agent should present the `approval_url` to the user. After the user approves, the agent retries the same call.

If you want the server to hold the wait instead of sleeping in the client, use
`POST /api/tool-approvals/requests/{request_id}/await`. The CLI wraps this as
`ap tools await-approval`, and `ap tools call --wait` uses it automatically.

---

## Tool Settings

Manage per-tool execution modes. By default, all tools require approval (`require_approval`).

### `GET /api/tool-settings/{integration_id}`

List execution settings for tools on the given installed integration.

**Response:**
```json
[
  {
    "id": "...",
    "org_id": "...",
    "integration_id": "github",
    "tool_name": "create_issue",
    "mode": "allow",
    "updated_by_user_id": "...",
    "updated_at": "2026-04-09T12:00:00"
  }
]
```

### `PUT /api/tool-settings/{integration_id}/{tool_name}`

Set execution mode for a specific tool.

**Body:**
```json
{
  "mode": "allow"
}
```

Valid modes: `allow`, `require_approval`.

---

## Org Settings

Per-org runtime settings.

### `GET /api/org-settings`

Read the current org's settings.

**Response:**
```json
{
  "approval_expiry_minutes": 30,
  "approval_expiry_minutes_default": 10,
  "approval_expiry_minutes_override": 30
}
```

`approval_expiry_minutes_override` is `null` when the org is using the instance default.

### `PATCH /api/org-settings`

Update the org's settings. Pass `null` to revert a field to the instance default.

**Body:**
```json
{
  "approval_expiry_minutes": 30
}
```

`approval_expiry_minutes` must be between 1 and 1440. The new value applies to approval requests created after the change; existing pending requests keep their original expiry.

---

## Tool Approvals

Manage approval requests for blocked tool calls.

### `GET /api/tool-approvals/requests`

List approval requests for your org.

**Query params:**
- `status` — filter by status (`pending`, `approved`, `denied`, `expired`, `consumed`)
- `integration_id` — filter by integration
- `tool_name` — filter by tool
- `limit` — max results (default `50`, max `500`)
- `offset` — pagination offset (default `0`)

### `GET /api/tool-approvals/requests/{request_id}`

Get a single approval request by ID.

**Response:**
```json
{
  "id": "550e8400-...",
  "org_id": "...",
  "integration_id": "github",
  "tool_name": "create_issue",
  "args_json": "{\"title\":\"Bug report\"}",
  "args_hash": "a1b2c3...",
  "summary_text": "Run github.create_issue with arguments ...",
  "status": "pending",
  "requested_at": "2026-04-09T12:00:00",
  "expires_at": "2026-04-10T12:00:00",
  "decision_mode": null,
  "decided_at": null,
  "additional_info": "Opening this issue to track the auth regression I just reproduced."
}
```

`additional_info` is the optional rationale supplied by the caller at the time of the tool call, or `null`.

### `POST /api/tool-approvals/requests/{request_id}/await`

Agent-facing long-poll endpoint for approval decisions. This is the REST equivalent of the MCP
`agentport__await_approval` flow, except it returns the current approval status and lets the caller
retry the original tool call once the status becomes `approved`.

**Body (optional):**
```json
{ "timeout_seconds": 30 }
```

If omitted, the server waits for up to `approval_long_poll_timeout_seconds` (default `240`).
Larger requested values are capped to that server-side maximum.

**Response:**
```json
{
  "approval_request_id": "550e8400-...",
  "integration_id": "github",
  "tool_name": "create_issue",
  "status": "approved",
  "message": "Approved. Retry the original tool call to execute it.",
  "expires_at": "2026-04-10T12:00:00",
  "decision_mode": "approve_once"
}
```

Possible `status` values include `pending`, `approved`, `denied`, `expired`, `consumed`, and `auto_approved`.

### `POST /api/tool-approvals/requests/{request_id}/approve-once`

Approve a pending request for one-time use. The agent must retry the call to consume the approval.

**Body:**
```json
{ "totp_code": "123456" }
```
`totp_code` is only required when the approving user has TOTP enabled (see `/api/users/me/totp`). Pass either a 6-digit authenticator code or an unused recovery code.

**Response:** The updated approval request with `status: "approved"` and `decision_mode: "approve_once"`.

Returns `409` if already decided. Returns `410` if expired. Returns `403` with `{"detail": {"error": "totp_required" | "totp_invalid", ...}}` when the user has TOTP enabled and the code is missing or wrong.

### `POST /api/tool-approvals/requests/{request_id}/allow-tool`

Approve a pending request and allow all future calls to this tool regardless of arguments.

Accepts the same optional `totp_code` body as `approve-once`.

**Response:** The updated approval request with `decision_mode: "allow_tool_forever"`.

### `POST /api/tool-approvals/requests/{request_id}/deny`

Deny a pending request.

Accepts the same optional `totp_code` body as `approve-once`.

**Response:** The updated approval request with `status: "denied"`.

---

## Two-factor authentication (TOTP)

When enabled, every approval decision (approve-once, allow-tool, deny) requires a fresh authenticator code from the approving user. The secret persists across disable/re-enable, so turning it back on does not require rescanning the QR.

### `GET /api/users/me/totp/status`

Returns `{ "enabled": bool, "configured": bool }`. `configured` is `true` once the user has completed the setup flow at least once.

### `POST /api/users/me/totp/setup`

Generate a new shared secret and 10 recovery codes. Returns:

```json
{
  "secret": "BASE32SECRET",
  "otpauth_uri": "otpauth://totp/AgentPort:you@example.com?secret=...&issuer=AgentPort",
  "qr_data_url": "data:image/png;base64,...",
  "recovery_codes": ["xxxxx-xxxxx", "..."]
}
```

Recovery codes are only returned here — the server stores them as bcrypt hashes. Returns `409` if TOTP is already confirmed.

### `POST /api/users/me/totp/enable`

Verify a code from the authenticator and turn on 2FA.

**Body:** `{ "code": "123456" }`

**Response:** `{ "enabled": true, "configured": true }`. Returns `400` with an invalid code.

### `POST /api/users/me/totp/re-enable`

Re-enable TOTP after a prior disable. Only works if the user previously confirmed setup — otherwise returns `409`.

**Body:** `{ "code": "123456" }`

Requires a current authenticator code or an unused recovery code. Returns `403` if the code is missing or wrong.

### `POST /api/users/me/totp/disable`

Stop requiring codes on approvals. The secret and remaining recovery codes stay on file.

**Body:** `{ "code": "123456" }`

Requires a current authenticator code or an unused recovery code. Returns `403` if the code is missing or wrong.

---

## Logs

### `GET /api/logs`

Query tool call logs for your org.

**Query params:**
- `integration` — filter by integration ID
- `tool` — filter by tool name
- `limit` — max results (default `50`, max `500`)
- `offset` — pagination offset (default `0`)

**Response:**
```json
[
  {
    "id": 1,
    "org_id": "6ba7b810-...",
    "timestamp": "2026-04-09T12:00:00",
    "integration_id": "posthog",
    "tool_name": "get_events",
    "args_json": "{}",
    "result_json": "...",
    "error": null,
    "duration_ms": 342,
    "outcome": "executed",
    "approval_request_id": null,
    "args_hash": null,
    "additional_info": null
  }
]
```

The `outcome` field can be: `executed`, `approval_required`, `denied`, or `error`.

`additional_info` carries the agent's optional explanation for the call (if any was supplied).

---

## OAuth 2.0 Authorization Server

MCP clients can authenticate to `/mcp` using the OAuth 2.0 Authorization Code + PKCE flow. The following endpoints are provided by the MCP SDK and AgentPort's OAuth provider.

### Discovery

#### `GET /.well-known/oauth-authorization-server`

Returns RFC 8414 OAuth Authorization Server Metadata. No auth required.

#### `GET /.well-known/oauth-protected-resource/mcp`

Returns RFC 9728 Protected Resource Metadata for the `/mcp` endpoint. No auth required.

### Dynamic Client Registration

#### `POST /register`

Register an OAuth client (RFC 7591 Dynamic Client Registration). No auth required.

**Body:** `OAuthClientMetadata` JSON (redirect_uris, client_name, etc.)

**Response `200`:** `OAuthClientInformationFull` with generated `client_id` and `client_secret`.

### Authorization

#### `GET /authorize` or `POST /authorize`

Start the authorization flow. Redirects to the UI at `/oauth/authorize?session=<token>` for user approval.

**Query params:** `client_id`, `redirect_uri`, `response_type=code`, `code_challenge`, `code_challenge_method=S256`, `scope`, `state`, `resource`

### Token

#### `POST /token`

Exchange an authorization code or refresh token for access/refresh tokens.

**Form fields (authorization_code grant):** `grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier`, `client_id`, `client_secret`

**Form fields (refresh_token grant):** `grant_type=refresh_token`, `refresh_token`, `client_id`, `client_secret`, `scope`

**Response `200`:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer",
  "expires_in": 604800,
  "refresh_token": "eyJhbGci...",
  "scope": "..."
}
```

### Revocation

#### `POST /revoke`

Revoke an access or refresh token. Requires client authentication.

**Form fields:** `token`, `client_id`, `client_secret`

### OAuth UI Backend

These endpoints support the frontend OAuth authorization screen.

#### `GET /api/oauth/authorize/session?session=<token>`

Returns metadata about a pending authorization session for the UI to display. No auth required.

**Response `200`:**
```json
{
  "client_id": "...",
  "client_name": "My MCP Client",
  "redirect_uri": "http://localhost:3000/callback",
  "scope": "...",
  "resource": "...",
  "expires_at": 1234567890
}
```

#### `POST /api/oauth/authorize/approve`

Approve the authorization request. Requires user authentication.

**Body:**
```json
{ "session_token": "..." }
```

**Response `200`:**
```json
{ "redirect_url": "http://localhost:3000/callback?code=...&state=..." }
```

#### `POST /api/oauth/authorize/deny`

Deny the authorization request. No auth required.

**Body:**
```json
{ "session_token": "..." }
```

**Response `200`:**
```json
{ "redirect_url": "http://localhost:3000/callback?error=access_denied&state=..." }
```

---

## Health

### `GET /health`

```json
{ "status": "ok" }
```
