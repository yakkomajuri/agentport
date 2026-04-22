import { randomBytes, createHash } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { spawn } from "node:child_process";
import { Command } from "commander";
import {
  discoverOAuthServerMetadata,
  exchangeAuthorizationCode,
  registerOAuthClient,
} from "../oauth.js";
import { readConfig, writeConfig, maskKey, clearCredentials } from "../config.js";
import { request } from "../client.js";
import { print, printError, resolveFormat } from "../output.js";

interface CallbackPayload {
  code: string;
  state: string;
}

interface CallbackServer {
  redirectUri: string;
  waitForCallback: Promise<CallbackPayload>;
  close: () => Promise<void>;
}

function makeRandomBase64Url(bytes: number): string {
  return randomBytes(bytes).toString("base64url");
}

function makePkceChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
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

function renderCallbackPage(message: string): string {
  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>AgentPort CLI login</title>
    <style>
      body {
        font-family: sans-serif;
        background: #0f172a;
        color: #e2e8f0;
        display: grid;
        place-items: center;
        min-height: 100vh;
        margin: 0;
      }
      main {
        max-width: 420px;
        padding: 24px;
        border: 1px solid #334155;
        border-radius: 12px;
        background: #111827;
        text-align: center;
      }
      p {
        margin: 0;
        line-height: 1.5;
      }
    </style>
  </head>
  <body>
    <main>
      <p>${message}</p>
    </main>
  </body>
</html>`;
}

function createCallbackServer(timeoutSeconds: number): Promise<CallbackServer> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let timeoutId: NodeJS.Timeout | null = null;
    let finishResolve: ((value: CallbackPayload) => void) | null = null;
    let finishReject: ((reason?: unknown) => void) | null = null;

    const waitForCallback = new Promise<CallbackPayload>((innerResolve, innerReject) => {
      finishResolve = innerResolve;
      finishReject = innerReject;
    });

    const close = async (): Promise<void> =>
      await new Promise((innerResolve) => {
        if (!server.listening) {
          innerResolve();
          return;
        }
        server.close(() => innerResolve());
      });

    const settleSuccess = (payload: CallbackPayload) => {
      if (settled) return;
      settled = true;
      if (timeoutId) clearTimeout(timeoutId);
      finishResolve?.(payload);
    };

    const settleError = (error: Error) => {
      if (settled) return;
      settled = true;
      if (timeoutId) clearTimeout(timeoutId);
      finishReject?.(error);
    };

    const handleCallback = (req: IncomingMessage, res: ServerResponse) => {
      const url = new URL(req.url ?? "/", `http://${req.headers.host}`);
      if (url.pathname !== "/callback") {
        res.statusCode = 404;
        res.end("Not found");
        return;
      }

      const error = url.searchParams.get("error");
      const errorDescription = url.searchParams.get("error_description");
      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");

      res.setHeader("Content-Type", "text/html; charset=utf-8");

      if (error) {
        res.statusCode = 400;
        res.end(
          renderCallbackPage(
            "Authorization failed. You can return to the terminal for details.",
          ),
        );
        settleError(
          new Error(
            errorDescription
              ? `OAuth authorization failed: ${errorDescription}`
              : `OAuth authorization failed: ${error}`,
          ),
        );
      } else if (!code || !state) {
        res.statusCode = 400;
        res.end(
          renderCallbackPage(
            "Authorization response was missing required parameters.",
          ),
        );
        settleError(new Error("OAuth callback did not include code and state."));
      } else {
        res.statusCode = 200;
        res.end(
          renderCallbackPage(
            "AgentPort CLI login completed. You can close this window.",
          ),
        );
        settleSuccess({ code, state });
      }

      setTimeout(() => {
        server.close();
      }, 0);
    };

    const server = createServer(handleCallback);

    server.on("error", (error) => {
      settleError(error as Error);
      reject(error);
    });

    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("Could not determine local OAuth callback port."));
        return;
      }

      timeoutId = setTimeout(() => {
        settleError(
          new Error(
            `Timed out waiting for OAuth callback after ${timeoutSeconds} seconds.`,
          ),
        );
        server.close();
      }, timeoutSeconds * 1000);

      resolve({
        redirectUri: `http://127.0.0.1:${address.port}/callback`,
        waitForCallback,
        close,
      });
    });
  });
}

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
  .description("Log in via browser OAuth (or --api-key for non-interactive auth)")
  .option("--api-key <key>", "Authenticate with an API key instead of OAuth")
  .option("--no-open", "Do not try to open the OAuth URL in a browser")
  .option(
    "--timeout <seconds>",
    "Seconds to wait for the browser callback before failing",
    "180",
  )
  .option("-o, --output <format>", "Output format")
  .action(
    async (opts: {
      apiKey?: string;
      open?: boolean;
      timeout: string;
      output: string;
    }) => {
      const format = resolveFormat(opts.output);

      if (opts.apiKey) {
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
        return;
      }

      const timeoutSeconds = Number.parseInt(opts.timeout, 10);
      if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
        printError("--timeout must be a positive integer number of seconds.", 1);
      }

      const config = readConfig();
      let callbackServer: CallbackServer | null = null;

      try {
        callbackServer = await createCallbackServer(timeoutSeconds);
        const metadata = await discoverOAuthServerMetadata(config.url);
        const registration = await registerOAuthClient(
          config.url,
          callbackServer.redirectUri,
        );

        const codeVerifier = makeRandomBase64Url(64);
        const codeChallenge = makePkceChallenge(codeVerifier);
        const state = makeRandomBase64Url(32);

        const authorizationUrl = new URL(metadata.authorization_endpoint);
        authorizationUrl.searchParams.set("response_type", "code");
        authorizationUrl.searchParams.set("client_id", registration.client_id);
        authorizationUrl.searchParams.set("redirect_uri", callbackServer.redirectUri);
        authorizationUrl.searchParams.set("code_challenge", codeChallenge);
        authorizationUrl.searchParams.set("code_challenge_method", "S256");
        authorizationUrl.searchParams.set("state", state);

        const opened = opts.open
          ? await openAuthorizationUrl(authorizationUrl.toString())
          : false;

        process.stderr.write(
          `${opened ? "Opened" : "Open"} this URL to authenticate the CLI:\n${authorizationUrl}\n`,
        );
        process.stderr.write(
          `Waiting up to ${timeoutSeconds}s for the browser callback...\n`,
        );

        const callback = await callbackServer.waitForCallback;
        if (callback.state !== state) {
          printError("OAuth state mismatch. Refusing to use the callback.", 1);
        }

        const token = await exchangeAuthorizationCode(
          config.url,
          registration.client_id,
          callback.code,
          callbackServer.redirectUri,
          codeVerifier,
        );

        clearCredentials(config);
        config.auth_mode = "oauth";
        config.access_token = token.access_token;
        config.refresh_token = token.refresh_token ?? "";
        config.oauth_client_id = registration.client_id;
        writeConfig(config);

        print(
          {
            url: config.url,
            authenticated: true,
            auth_mode: config.auth_mode,
            oauth_client_id: config.oauth_client_id,
            access_token: maskKey(config.access_token),
            has_refresh_token: Boolean(config.refresh_token),
          },
          format,
        );
      } catch (e) {
        printError((e as Error).message, 1);
      } finally {
        if (callbackServer) {
          await callbackServer.close();
        }
      }
    },
  );

authCommand
  .command("logout")
  .description("Remove stored credentials (OAuth tokens and API key)")
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
        oauth_client_id: config.oauth_client_id,
        access_token: maskKey(config.access_token),
        has_refresh_token: Boolean(config.refresh_token),
        api_key: maskKey(config.api_key),
      },
      format,
    );
  });
