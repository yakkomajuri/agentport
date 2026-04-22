export interface OAuthServerMetadata {
  authorization_endpoint: string;
  token_endpoint: string;
  registration_endpoint?: string;
}

export interface OAuthClientRegistration {
  client_id: string;
}

export interface OAuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
  refresh_token?: string;
}

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/+$/, "");
}

function isOAuthServerMetadata(value: unknown): value is OAuthServerMetadata {
  return (
    !!value &&
    typeof value === "object" &&
    typeof (value as { authorization_endpoint?: unknown }).authorization_endpoint ===
      "string" &&
    typeof (value as { token_endpoint?: unknown }).token_endpoint === "string"
  );
}

function isOAuthClientRegistration(value: unknown): value is OAuthClientRegistration {
  return (
    !!value &&
    typeof value === "object" &&
    typeof (value as { client_id?: unknown }).client_id === "string"
  );
}

function isOAuthTokenResponse(value: unknown): value is OAuthTokenResponse {
  return (
    !!value &&
    typeof value === "object" &&
    typeof (value as { access_token?: unknown }).access_token === "string" &&
    typeof (value as { token_type?: unknown }).token_type === "string"
  );
}

async function fetchJson<T>(
  url: string,
  init?: RequestInit,
  validate?: (value: unknown) => value is T,
): Promise<T> {
  const res = await fetch(url, init);
  const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;

  if (!res.ok) {
    throw new Error(
      (typeof json.error_description === "string" && json.error_description) ||
        (typeof json.detail === "string" && json.detail) ||
        `HTTP ${res.status}: ${res.statusText}`,
    );
  }

  if (validate && !validate(json)) {
    throw new Error(`Unexpected response from ${url}`);
  }

  return json as T;
}

export async function discoverOAuthServerMetadata(
  baseUrl: string,
): Promise<OAuthServerMetadata> {
  return await fetchJson(
    `${normalizeBaseUrl(baseUrl)}/.well-known/oauth-authorization-server`,
    { headers: { Accept: "application/json" } },
    isOAuthServerMetadata,
  );
}

export async function registerOAuthClient(
  baseUrl: string,
  redirectUri: string,
): Promise<OAuthClientRegistration> {
  const metadata = await discoverOAuthServerMetadata(baseUrl);
  if (!metadata.registration_endpoint) {
    throw new Error("OAuth server does not support dynamic client registration.");
  }

  return await fetchJson(
    metadata.registration_endpoint,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        redirect_uris: [redirectUri],
        token_endpoint_auth_method: "none",
        grant_types: ["authorization_code", "refresh_token"],
        response_types: ["code"],
        client_name: "AgentPort CLI",
      }),
    },
    isOAuthClientRegistration,
  );
}

export async function exchangeAuthorizationCode(
  baseUrl: string,
  clientId: string,
  code: string,
  redirectUri: string,
  codeVerifier: string,
): Promise<OAuthTokenResponse> {
  const metadata = await discoverOAuthServerMetadata(baseUrl);
  return await fetchJson(
    metadata.token_endpoint,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: clientId,
        code,
        redirect_uri: redirectUri,
        code_verifier: codeVerifier,
      }).toString(),
    },
    isOAuthTokenResponse,
  );
}

export async function refreshOAuthAccessToken(
  baseUrl: string,
  clientId: string,
  refreshToken: string,
): Promise<OAuthTokenResponse> {
  const metadata = await discoverOAuthServerMetadata(baseUrl);
  return await fetchJson(
    metadata.token_endpoint,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        client_id: clientId,
        refresh_token: refreshToken,
      }).toString(),
    },
    isOAuthTokenResponse,
  );
}

export function getJwtExpiry(token: string): number | null {
  const parts = token.split(".");
  if (parts.length < 2) return null;

  try {
    const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8")) as {
      exp?: unknown;
    };
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}
