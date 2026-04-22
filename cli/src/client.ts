import { readConfig, writeConfig, type Config } from "./config.js";
import { getJwtExpiry, refreshOAuthAccessToken } from "./oauth.js";

export class ApprovalRequiredError extends Error {
  approvalUrl: string;
  requestId: string;

  constructor(approvalUrl: string, requestId: string) {
    super("Approval required");
    this.name = "ApprovalRequiredError";
    this.approvalUrl = approvalUrl;
    this.requestId = requestId;
  }
}

export class ToolDeniedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ToolDeniedError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, string>;
}

function buildHeaders(config: Config, hasBody: boolean): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };

  if (config.auth_mode === "oauth" && config.access_token) {
    headers["Authorization"] = `Bearer ${config.access_token}`;
  } else if (config.auth_mode === "api_key" && config.api_key) {
    headers["X-API-Key"] = config.api_key;
  }

  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
}

function shouldRefreshAccessToken(token: string): boolean {
  const exp = getJwtExpiry(token);
  if (exp === null) return false;
  return exp <= Math.floor(Date.now() / 1000) + 60;
}

async function tryRefreshConfig(config: Config): Promise<Config> {
  if (!config.refresh_token || !config.oauth_client_id) {
    return config;
  }

  try {
    const refreshed = await refreshOAuthAccessToken(
      config.url,
      config.oauth_client_id,
      config.refresh_token,
    );
    const nextConfig: Config = {
      ...config,
      access_token: refreshed.access_token,
      refresh_token: refreshed.refresh_token ?? config.refresh_token,
    };
    writeConfig(nextConfig);
    return nextConfig;
  } catch {
    return config;
  }
}

async function performRequest(
  config: Config,
  url: string,
  method: string,
  body: unknown,
): Promise<Response> {
  return await fetch(url, {
    method,
    headers: buildHeaders(config, body !== undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function request<T = unknown>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  let config = readConfig();
  const { method = "GET", body, params } = opts;

  const baseUrl = config.url.replace(/\/+$/, "");
  let url = `${baseUrl}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }

  if (config.access_token && shouldRefreshAccessToken(config.access_token)) {
    config = await tryRefreshConfig(config);
  }

  let res: Response;
  try {
    res = await performRequest(config, url, method, body);
  } catch (e) {
    const msg = (e as Error).message;
    if (msg.includes("fetch failed") || msg.includes("ECONNREFUSED")) {
      throw new Error(
        `Could not connect to server at ${baseUrl} — is it running?`,
      );
    }
    throw new Error(`Request to ${baseUrl} failed: ${msg}`);
  }

  if (
    res.status === 401 &&
    config.access_token &&
    config.refresh_token &&
    config.oauth_client_id
  ) {
    const refreshedConfig = await tryRefreshConfig(config);
    if (refreshedConfig.access_token && refreshedConfig.access_token !== config.access_token) {
      res = await performRequest(refreshedConfig, url, method, body);
      config = refreshedConfig;
    }
  }

  if (res.status === 204) return undefined as T;

  const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;

  if (res.status === 403) {
    if (json.error === "approval_required") {
      throw new ApprovalRequiredError(
        json.approval_url as string,
        json.approval_request_id as string,
      );
    }
    if (json.error === "denied") {
      throw new ToolDeniedError(
        formatDetail(json.message) || "Tool denied",
      );
    }
  }

  if (!res.ok) {
    throw new Error(
      formatDetail(json.detail) || `HTTP ${res.status}: ${res.statusText}`,
    );
  }

  return json as T;
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map(
        (e: any) =>
          `${(e.loc ?? []).slice(1).join(".") || "body"}: ${e.msg}`,
      )
      .join("; ");
  }
  if (detail !== undefined && detail !== null) return JSON.stringify(detail);
  return "";
}
