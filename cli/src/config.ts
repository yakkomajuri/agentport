import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

export type AuthMode = "" | "oauth" | "api_key";
export type OutputFormat = "human" | "json" | "toon";

export interface Config {
  url: string;
  auth_mode: AuthMode;
  output_format: OutputFormat;
  api_key: string;
  access_token: string;
  refresh_token: string;
  oauth_client_id: string;
}

const CONFIG_DIR = join(homedir(), ".config", "agent-port");
const CONFIG_PATH = join(CONFIG_DIR, "config.json");

const DEFAULT_URL = process.env.AGENT_PORT_URL || "https://app.agentport.sh";

const DEFAULTS: Config = {
  url: DEFAULT_URL,
  auth_mode: "",
  output_format: "human",
  api_key: "",
  access_token: "",
  refresh_token: "",
  oauth_client_id: "",
};

export function readConfig(): Config {
  try {
    const raw = readFileSync(CONFIG_PATH, "utf-8");
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function writeConfig(config: Config): void {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2) + "\n");
}

/**
 * Wipe every credential field. Call this before switching auth modes so stale
 * state from the prior mode can't leak into the new session.
 */
export function clearCredentials(config: Config): void {
  config.auth_mode = "";
  config.api_key = "";
  config.access_token = "";
  config.refresh_token = "";
  config.oauth_client_id = "";
}

export function maskKey(key: string): string {
  if (!key) return "";
  if (key.length <= 8) return key.slice(0, 3) + "***";
  return key.slice(0, 6) + "..." + key.slice(-4);
}
