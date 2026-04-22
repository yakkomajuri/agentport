import { Command } from "commander";
import { spawn } from "node:child_process";
import { request } from "../client.js";
import { print, printError, resolveFormat } from "../output.js";
import { promptSecret } from "../prompt.js";

export const integrationsCommand = new Command("integrations").description(
  "Manage integrations",
);

interface InstalledIntegrationRow {
  integration_id: string;
  type: string;
  auth_method: string;
  connected: boolean;
  added_at: string;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function openAuthorizationUrl(url: string): Promise<boolean> {
  const command =
    process.platform === "darwin"
      ? "open"
      : process.platform === "win32"
        ? "start"
        : "xdg-open";

  return await new Promise<boolean>((resolve) => {
    const child = spawn(command, [url], {
      stdio: "ignore",
      shell: process.platform === "win32",
    });

    child.on("error", () => resolve(false));
    child.on("spawn", () => {
      child.unref();
      resolve(true);
    });
  });
}

async function waitForOAuthConnection(
  integration_id: string,
  timeoutSeconds: number,
): Promise<InstalledIntegrationRow | null> {
  const deadline = Date.now() + timeoutSeconds * 1000;

  while (Date.now() < deadline) {
    const installed = await request<InstalledIntegrationRow[]>("/api/installed");
    const match = installed.find((item) => item.integration_id === integration_id);
    if (match?.connected) {
      return match;
    }
    await sleep(1500);
  }

  return null;
}

integrationsCommand
  .command("list")
  .description(
    "List integrations (defaults to all, marking which are installed)",
  )
  .option("--installed", "Show only installed integrations")
  .option("--available", "Show only integrations not yet installed")
  .option("-o, --output <format>", "Output format")
  .action(
    async (opts: { installed?: boolean; available?: boolean; output: string }) => {
      const format = resolveFormat(opts.output);

      if (opts.installed && opts.available) {
        printError("--installed and --available are mutually exclusive.", 1);
      }

      try {
        const [integrations, installed] = await Promise.all([
          request<Record<string, unknown>[]>("/api/integrations"),
          request<InstalledIntegrationRow[]>("/api/installed"),
        ]);

        const installedMap = new Map(
          installed.map((i) => [i.integration_id, i]),
        );

        const rows = integrations
          .map((i) => {
            const methods = (i.auth as { method: string }[]).map(
              (a) => a.method,
            );
            const install = installedMap.get(i.id as string);
            return {
              id: i.id,
              name: i.name,
              type: i.type,
              auth_methods: format === "human" ? methods.join(", ") : methods,
              installed: install !== undefined,
              connected: install?.connected ?? false,
            };
          })
          .filter((r) => {
            if (opts.installed) return r.installed;
            if (opts.available) return !r.installed;
            return true;
          })
          .sort((a, b) => Number(b.installed) - Number(a.installed));

        print(rows, format);
      } catch (e) {
        printError((e as Error).message, 1);
      }
    },
  );

integrationsCommand
  .command("add <integration>")
  .description("Install an integration")
  .option(
    "--auth <method>",
    "Authentication method (token or oauth)",
  )
  .option("--token <token>", "Authentication token")
  .option("--no-open", "Do not try to open the OAuth URL in a browser")
  .option(
    "--timeout <seconds>",
    "Seconds to wait for OAuth completion before returning",
    "180",
  )
  .option("-o, --output <format>", "Output format")
  .action(
    async (
      integration: string,
      opts: {
        auth?: string;
        token?: string;
        open?: boolean;
        timeout: string;
        output: string;
      },
    ) => {
      const format = resolveFormat(opts.output);
      const timeoutSeconds = Number.parseInt(opts.timeout, 10);

      if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
        printError("--timeout must be a positive integer number of seconds.", 1);
      }

      let authMethod = opts.auth ?? (opts.token ? "token" : undefined);

      if (!authMethod) {
        try {
          const definition = await request<{ auth: { method: string }[] }>(
            `/api/integrations/${encodeURIComponent(integration)}`,
          );
          const methods = definition.auth.map((a) => a.method);
          if (methods.length === 1) {
            authMethod = methods[0];
          } else {
            printError(
              `Missing --auth. Integration '${integration}' supports: ${methods.join(", ")}.`,
              1,
            );
          }
        } catch (e) {
          printError((e as Error).message, 1);
        }
      }

      if (authMethod === "token" && !opts.token) {
        if (format === "human" && process.stdin.isTTY) {
          const pasted = await promptSecret(
            `Paste token for '${integration}': `,
          );
          if (!pasted) {
            printError("No token provided.", 1);
          }
          opts.token = pasted;
        } else {
          printError("--token is required when --auth is token.", 1);
        }
      }

      try {
        const body: Record<string, string> = {
          integration_id: integration,
          auth_method: authMethod!,
        };
        if (opts.token) body.token = opts.token;
        const data = (await request<InstalledIntegrationRow>("/api/installed", {
          method: "POST",
          body,
        })) as InstalledIntegrationRow;

        if (authMethod === "oauth") {
          const { authorization_url } = await request<{ authorization_url: string }>(
            `/api/auth/${encodeURIComponent(integration)}/start`,
            { method: "POST" },
          );

          const opened = opts.open
            ? await openAuthorizationUrl(authorization_url)
            : false;

          process.stderr.write(
            `${opened ? "Opened" : "Open"} this URL to complete OAuth for ${integration}:\n${authorization_url}\n`,
          );
          process.stderr.write(
            `Waiting up to ${timeoutSeconds}s for the connection to complete...\n`,
          );

          const connected = await waitForOAuthConnection(integration, timeoutSeconds);
          if (!connected) {
            print(
              {
                integration_id: data.integration_id,
                type: data.type,
                auth_method: data.auth_method,
                connected: false,
                authorization_url,
              },
              format,
            );
            return;
          }

          print(connected, format);
          return;
        }

        const row = {
          integration_id: data.integration_id,
          type: data.type,
          auth_method: data.auth_method,
          connected: data.connected,
        };
        print(row, format);
      } catch (e) {
        printError((e as Error).message, 1);
      }
    },
  );

integrationsCommand
  .command("remove <integration>")
  .description("Remove an installed integration")
  .option("-o, --output <format>", "Output format")
  .action(async (integration: string, opts: { output: string }) => {
    const format = resolveFormat(opts.output);
    try {
      await request(`/api/installed/${encodeURIComponent(integration)}`, {
        method: "DELETE",
      });
      print({ integration_id: integration, removed: true }, format);
    } catch (e) {
      printError((e as Error).message, 1);
    }
  });
