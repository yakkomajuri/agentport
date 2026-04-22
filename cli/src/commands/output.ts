import { Command } from "commander";
import { readConfig, writeConfig } from "../config.js";
import { print, resolveFormat, validateFormat } from "../output.js";

export const outputCommand = new Command("output")
  .description("Set the default output format")
  .argument("<format>", "Output format: human, json, toon")
  .option("-o, --output <format>", "Output format for the confirmation")
  .action((format: string, opts: { output: string }) => {
    const validated = validateFormat(format);
    const config = readConfig();
    config.output_format = validated;
    writeConfig(config);
    const display = resolveFormat(opts.output);
    print({ output_format: validated }, display);
  });
