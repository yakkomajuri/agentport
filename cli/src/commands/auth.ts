import { Command } from "commander";
import { readConfig, writeConfig, maskKey, clearCredentials } from "../config.js";
import { request } from "../client.js";
import { print, printError, resolveFormat } from "../output.js";

export const authCommand = new Command("auth").description(
  "Authenticate the CLI with AgentPort",
);

authCommand
  .command("set-instance-url")
  .description("Point the CLI at a different AgentPort instance")
  .argument("<url>", "Server URL (e.g. https://ap.example.com)")
  .option("-o, --output <format>", "Output format")
  .action((url: string, opts: { output: string }) => {
    const format = resolveFormat(opts.output);
    const config = readConfig();
    clearCredentials(config);
    config.url = url;
    writeConfig(config);
    process.stderr.write(
      `Credentials were cleared. Run 'ap auth login' to authenticate against the new instance.\n`,
    );
    print({ url, credentials_cleared: true }, format);
  });

authCommand
  .command("login")
  .description("Authenticate the CLI with an API key (create one at Settings → API Keys)")
  .option("--api-key <key>", "API key to authenticate with")
  .option("-o, --output <format>", "Output format")
  .action((opts: { apiKey?: string; output: string }) => {
    const format = resolveFormat(opts.output);

    if (!opts.apiKey) {
      // Browser-OAuth login was removed alongside the MCP/REST audience split
      // (security audit finding 09): MCP-audience tokens no longer unlock the
      // REST API, and the CLI has no separate REST OAuth issuer yet. API keys
      // are the supported CLI credential until that lands.
      printError(
        "ap auth login now requires --api-key. Create one in the web UI under Settings → API Keys.",
        1,
      );
    }

    const config = readConfig();
    clearCredentials(config);
    config.auth_mode = "api_key";
    config.api_key = opts.apiKey;
    writeConfig(config);
    print(
      {
        url: config.url,
        authenticated: true,
        auth_mode: config.auth_mode,
        api_key: maskKey(config.api_key),
      },
      format,
    );
  });

authCommand
  .command("logout")
  .description("Remove stored credentials (API key)")
  .option("-o, --output <format>", "Output format")
  .action((opts: { output: string }) => {
    const format = resolveFormat(opts.output);
    const config = readConfig();
    clearCredentials(config);
    writeConfig(config);
    print({ authenticated: false }, format);
  });

authCommand
  .command("status")
  .description("Show current CLI authentication status")
  .option("-o, --output <format>", "Output format")
  .action(async (opts: { output: string }) => {
    const format = resolveFormat(opts.output);
    const config = readConfig();
    const authMode = config.auth_mode || "none";

    let email: string | null = null;
    if (authMode !== "none") {
      try {
        const me = await request<{ email: string }>("/api/users/me");
        email = me.email;
      } catch {
        // leave email null — credentials may be stale or server unreachable
      }
    }

    print(
      {
        url: config.url,
        auth_mode: authMode,
        email,
        api_key: maskKey(config.api_key),
      },
      format,
    );
  });
