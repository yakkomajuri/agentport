The custom API feature introduces security issues around stored token reuse and dispatch-time URL safety, and it also has update semantics that break auth mode changes and description clearing. These should be fixed before considering the patch correct.

Full review comments:

- [P1] Keep stored test tokens on the saved endpoint — /workspace/server/src/agent_port/api/custom_api.py:401-406
  When `integration_db_id` is supplied and the override token is blank, this copies the installed secret into `token` before the request still uses caller-supplied `base_url`, `token_header`, and `token_format` below. A caller can set `base_url` to a public domain they control and omit `token` to have AgentPort send the stored API token to that domain, despite the UI/API never revealing the secret. Only reuse the stored token when the tested target/auth config matches the saved integration, or require an explicit override token for arbitrary test URLs.

- [P1] Revalidate custom API targets when dispatching — /workspace/server/src/agent_port/api_client.py:233-240
  For installed custom API tool calls, this helper streams to the constructed `url` without the safety check used when the definition was saved/tested. If a user-controlled hostname passes validation and later DNS-rebinds to loopback, RFC1918, or metadata IPs, normal `/api/tools`/MCP calls will resolve it at request time and reach the blocked network. Re-run the safe-URL check for the full URL at dispatch time and/or pin the validated address for the actual connection.

- [P2] Validate auth changes after merging both fields — /workspace/server/src/agent_port/api/custom_api.py:331-337
  When switching an existing custom API between token auth and No auth, the PATCH payload contains both new values, but these branches validate each field against the other field's old value. For example changing to No auth first checks `('', 'Bearer {token}')` and returns 400, so the auth preset cannot be changed even though the final pair `('', '')` is valid. Compute the final header/format pair and validate it once before assigning.

- [P3] Allow clearing custom API descriptions — /workspace/server/src/agent_port/api/custom_api.py:324-325
  The builder sends `description: null` when a user deletes the optional description, but this guard treats explicit null the same as an omitted field and leaves the old description in the database. As a result, a saved description cannot be removed; distinguish field presence from null before deciding whether to assign `row.description`.
