import { Command } from "commander";
import { authCommand } from "./commands/auth.js";
import { integrationsCommand } from "./commands/integrations.js";
import { outputCommand } from "./commands/output.js";
import { toolsCommand } from "./commands/tools.js";

declare const __VERSION__: string;

const program = new Command();

program
  .name("ap")
  .description("AgentPort CLI — manage integrations and call tools")
  .version(__VERSION__);

program.addCommand(authCommand);
program.addCommand(integrationsCommand);
program.addCommand(outputCommand);
program.addCommand(toolsCommand);

program.parse();
