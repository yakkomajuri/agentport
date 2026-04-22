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
      info?: string;
      output: string;
    }) => {
      const format = resolveFormat(opts.output);
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
          printError(`Approval required: ${e.approvalUrl}`, 2);
        } else if (e instanceof ToolDeniedError) {
          printError(`Denied: ${e.message}`, 1);
        } else {
          printError((e as Error).message, 1);
        }
      }
    },
  );
