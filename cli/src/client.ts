import { readConfig, type Config } from "./config.js";

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

  if (config.auth_mode === "api_key" && config.api_key) {
    headers["X-API-Key"] = config.api_key;
  }

  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
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
  const config = readConfig();
  const { method = "GET", body, params } = opts;

  const baseUrl = config.url.replace(/\/+$/, "");
  let url = `${baseUrl}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
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
