import chalk from "chalk";
import { encode } from "@toon-format/toon";
import { readConfig, type OutputFormat } from "./config.js";

export type { OutputFormat };

const VALID_FORMATS: ReadonlySet<string> = new Set(["human", "json", "toon"]);

export function validateFormat(format: string): OutputFormat {
  if (!VALID_FORMATS.has(format)) {
    printError(
      `Unknown output format '${format}'. Valid formats: human, json, toon`,
      1,
    );
  }
  return format as OutputFormat;
}

/**
 * Resolve the output format for a command: explicit `-o` flag wins,
 * otherwise fall back to the stored default in config.
 */
export function resolveFormat(explicit: string | undefined): OutputFormat {
  if (explicit !== undefined) return validateFormat(explicit);
  return readConfig().output_format || "human";
}

export function print(data: unknown, format: OutputFormat): void {
  switch (format) {
    case "json":
      console.log(JSON.stringify(data, null, 2));
      break;
    case "toon":
      console.log(encode(data));
      break;
    case "human":
      printHuman(data);
      break;
  }
}

const MAX_CELL_WIDTH = 80;

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

function printHuman(data: unknown): void {
  if (Array.isArray(data)) {
    if (data.length === 0) {
      console.log(chalk.dim("(empty)"));
      return;
    }
    const keys = Object.keys(data[0] as Record<string, unknown>);
    const rows = data.map((item) =>
      keys.map((k) =>
        truncate(
          formatCell((item as Record<string, unknown>)[k]),
          MAX_CELL_WIDTH,
        ),
      ),
    );

    const widths = keys.map((k, i) =>
      Math.max(k.length, ...rows.map((r) => r[i].length)),
    );

    const header = keys.map((k, i) => k.padEnd(widths[i])).join("  ");
    const sep = widths.map((w) => "─".repeat(w)).join("──");

    console.log(chalk.bold(header));
    console.log(chalk.dim(sep));
    for (const row of rows) {
      console.log(row.map((c, i) => c.padEnd(widths[i])).join("  "));
    }
  } else if (data && typeof data === "object") {
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      console.log(`${chalk.bold(k)}: ${formatCell(v)}`);
    }
  } else {
    console.log(String(data));
  }
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function printError(msg: string, exitCode: number): never {
  process.stderr.write(msg + "\n");
  process.exit(exitCode);
}
