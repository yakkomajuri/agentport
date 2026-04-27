import { Command } from "commander";
import chalk from "chalk";
import { request, ApprovalRequiredError, ToolDeniedError } from "../client.js";
import { print, printError, resolveFormat } from "../output.js";

interface ToolRow {
  name: string;
  description?: string;
  execution_mode?: string;
  category?: string;
  inputSchema?: {
    type?: string;
    properties?: Record<string, Record<string, unknown>>;
    required?: string[];
  };
}

interface AwaitApprovalStatus {
  approval_request_id: string;
  integration_id: string;
  tool_name: string;
  status: string;
  message: string;
  expires_at: string;
  decision_mode?: string | null;
}

function parseTimeoutSeconds(raw: string, flag: string): number {
  const timeoutSeconds = Number.parseInt(raw, 10);
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 0) {
    printError(`${flag} must be a non-negative integer number of seconds.`, 1);
  }
  return timeoutSeconds;
}

function extractRequestId(approvalUrl: string): string {
  try {
    const parsed = new URL(approvalUrl, "https://agentport.invalid");
    const parts = parsed.pathname.replace(/\/+$/, "").split("/");
    const requestId = parts.at(-1);
    if (!requestId) {
      throw new Error("missing request id");
    }
    return requestId;
  } catch {
    printError(`Invalid approval URL: ${approvalUrl}`, 1);
  }
}

function resolveRequestId(opts: {
  requestId?: string;
  approvalUrl?: string;
}): string {
  if (opts.requestId && opts.approvalUrl) {
    printError("Pass exactly one of --request-id or --approval-url.", 1);
  }
  if (!opts.requestId && !opts.approvalUrl) {
    printError("Missing approval reference. Pass --request-id or --approval-url.", 1);
  }
  return opts.requestId ?? extractRequestId(opts.approvalUrl!);
}

async function awaitApprovalDecision(
  requestId: string,
  timeoutSeconds: number,
): Promise<AwaitApprovalStatus> {
  const deadline = timeoutSeconds > 0 ? Date.now() + timeoutSeconds * 1000 : null;
  let lastPending: AwaitApprovalStatus | null = null;

  while (true) {
    let body: { timeout_seconds: number } | undefined;
    if (deadline !== null) {
      const remainingSeconds = Math.ceil((deadline - Date.now()) / 1000);
      if (remainingSeconds <= 0 && lastPending) {
        return lastPending;
      }
      body = { timeout_seconds: Math.max(1, remainingSeconds) };
    }

    const result = await request<AwaitApprovalStatus>(
      `/api/tool-approvals/requests/${encodeURIComponent(requestId)}/await`,
      {
        method: "POST",
        body,
      },
    );

    if (result.status !== "pending") {
      return result;
    }
    lastPending = result;
    if (deadline !== null && Date.now() >= deadline) {
      return result;
    }
  }
}

function printToolHuman(tool: ToolRow, integrationId: string): void {
  console.log(`${chalk.bold("integration")}: ${integrationId}`);
  console.log(`${chalk.bold("tool")}: ${tool.name}`);
  if (tool.description) {
    console.log(`${chalk.bold("description")}: ${tool.description}`);
  }
  if (tool.execution_mode) {
    console.log(`${chalk.bold("execution_mode")}: ${tool.execution_mode}`);
  }
  if (tool.category) {
    console.log(`${chalk.bold("category")}: ${tool.category}`);
  }

  const properties = tool.inputSchema?.properties ?? {};
  const required = new Set(tool.inputSchema?.required ?? []);
  const names = Object.keys(properties);

  console.log();
  console.log(chalk.bold("params:"));
  if (names.length === 0) {
    console.log(chalk.dim("  (none)"));
    return;
  }

  for (const name of names) {
    const schema = properties[name] ?? {};
    const type = (schema.type as string) ?? "any";
    const isRequired = required.has(name);
    const suffix = isRequired ? chalk.red(" required") : chalk.dim(" optional");
    console.log(`  ${chalk.bold(name)} (${type})${suffix}`);
    if (typeof schema.description === "string") {
      console.log(`    ${schema.description}`);
    }
    if (Array.isArray(schema.enum)) {
      console.log(chalk.dim(`    enum: ${schema.enum.join(", ")}`));
    }
    if (schema.default !== undefined) {
      console.log(chalk.dim(`    default: ${JSON.stringify(schema.default)}`));
    }
  }
}

export const toolsCommand = new Command("tools").description(
  "List and call tools",
);

toolsCommand
  .command("list")
  .description("List available tools")
  .option("--integration <id>", "Filter by integration ID")
  .option("-o, --output <format>", "Output format")
  .action(async (opts: { integration?: string; output: string }) => {
    const format = resolveFormat(opts.output);
    try {
      const path = opts.integration
        ? `/api/tools/${encodeURIComponent(opts.integration)}`
        : "/api/tools";
      const data = await request<unknown[]>(path);
      const rows = (data as Record<string, unknown>[]).map((t) => ({
        integration: (t.integration_id as string) ?? opts.integration ?? "",
        tool_name: t.name,
        description: t.description,
        mode: t.execution_mode,
      }));
      print(rows, format);
    } catch (e) {
      printError((e as Error).message, 1);
    }
  });

toolsCommand
  .command("describe")
  .description("Show parameters and metadata for a specific tool")
  .requiredOption("--integration <id>", "Integration ID")
  .requiredOption("--tool <tool>", "Tool name")
  .option("-o, --output <format>", "Output format")
  .action(
    async (opts: { integration: string; tool: string; output: string }) => {
      const format = resolveFormat(opts.output);
      try {
        const tools = await request<ToolRow[]>(
          `/api/tools/${encodeURIComponent(opts.integration)}`,
        );
        const match = tools.find((t) => t.name === opts.tool);
        if (!match) {
          printError(
            `Tool '${opts.tool}' not found in integration '${opts.integration}'.`,
            1,
          );
        }
        if (format === "human") {
          printToolHuman(match!, opts.integration);
          return;
        }
        print(match, format);
      } catch (e) {
        printError((e as Error).message, 1);
      }
    },
  );

toolsCommand
  .command("call")
  .description("Call a tool")
  .requiredOption("--integration <id>", "Integration ID")
  .requiredOption("--tool <tool>", "Tool name")
  .option("--args <json>", "Tool arguments as JSON", "{}")
  .option("--wait", "Wait for approval and retry automatically")
  .option(
    "--wait-timeout <seconds>",
    "Maximum seconds to keep waiting when --wait is used (0 = no client-side limit)",
    "0",
  )
  .option(
    "--info <text>",
    "Optional explanation of why this call is being made (shown to human reviewers)",
  )
  .option("-o, --output <format>", "Output format")
  .action(
    async (opts: {
      integration: string;
      tool: string;
      args: string;
      wait?: boolean;
      waitTimeout: string;
      info?: string;
      output: string;
    }) => {
      const format = resolveFormat(opts.output);
      const waitTimeoutSeconds = parseTimeoutSeconds(
        opts.waitTimeout,
        "--wait-timeout",
      );
      let parsedArgs: unknown;
      try {
        parsedArgs = JSON.parse(opts.args);
      } catch {
        printError(`Invalid JSON in --args: ${opts.args}`, 1);
      }

      const body: Record<string, unknown> = {
        tool_name: opts.tool,
        args: parsedArgs,
      };
      if (opts.info) body.additional_info = opts.info;

      try {
        const data = await request(
          `/api/tools/${encodeURIComponent(opts.integration)}/call`,
          {
            method: "POST",
            body,
          },
        );
        print(data, format);
      } catch (e) {
        if (e instanceof ApprovalRequiredError) {
          if (!opts.wait) {
            printError(`Approval required: ${e.approvalUrl}`, 2);
          }

          process.stderr.write(`Approval required: ${e.approvalUrl}\n`);
          process.stderr.write("Waiting for a human decision...\n");

          try {
            const waitResult = await awaitApprovalDecision(
              e.requestId,
              waitTimeoutSeconds,
            );

            if (waitResult.status === "approved") {
              const data = await request(
                `/api/tools/${encodeURIComponent(opts.integration)}/call`,
                {
                  method: "POST",
                  body,
                },
              );
              print(data, format);
              return;
            }

            if (waitResult.status === "pending") {
              printError(`Approval still pending: ${e.approvalUrl}`, 2);
            }

            if (waitResult.status === "denied") {
              printError(`Denied: ${waitResult.message}`, 1);
            }

            printError(waitResult.message, 1);
          } catch (waitError) {
            if (waitError instanceof ToolDeniedError) {
              printError(`Denied: ${waitError.message}`, 1);
            }
            if (waitError instanceof ApprovalRequiredError) {
              printError(`Approval required: ${waitError.approvalUrl}`, 2);
            }
            printError((waitError as Error).message, 1);
          }
        } else if (e instanceof ToolDeniedError) {
          printError(`Denied: ${e.message}`, 1);
        } else {
          printError((e as Error).message, 1);
        }
      }
    },
  );

toolsCommand
  .command("await-approval")
  .description("Wait for a decision on an approval request")
  .option("--request-id <id>", "Approval request ID")
  .option("--approval-url <url>", "Approval URL returned by a blocked tool call")
  .option(
    "--timeout <seconds>",
    "Maximum seconds to wait before returning pending (0 = no client-side limit)",
    "0",
  )
  .option("-o, --output <format>", "Output format")
  .action(
    async (opts: {
      requestId?: string;
      approvalUrl?: string;
      timeout: string;
      output: string;
    }) => {
      const format = resolveFormat(opts.output);
      const requestId = resolveRequestId(opts);
      const timeoutSeconds = parseTimeoutSeconds(opts.timeout, "--timeout");

      try {
        const result = await awaitApprovalDecision(requestId, timeoutSeconds);
        print(result, format);

        if (result.status === "approved") {
          return;
        }
        if (result.status === "pending") {
          process.exitCode = 2;
          return;
        }
        process.exitCode = 1;
      } catch (e) {
        printError((e as Error).message, 1);
      }
    },
  );
