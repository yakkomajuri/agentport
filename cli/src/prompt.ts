import * as readline from "node:readline";
import { Writable } from "node:stream";

/**
 * Prompt the user on stderr and read a single line from stdin with echo
 * suppressed — suitable for tokens and other secrets the user pastes in.
 */
export async function promptSecret(question: string): Promise<string> {
  process.stderr.write(question);

  const muted = new Writable({
    write(_chunk, _enc, cb) {
      cb();
    },
  });

  const rl = readline.createInterface({
    input: process.stdin,
    output: muted,
    terminal: true,
  });

  let visibleLength = 0;
  const onData = (chunk: Buffer) => {
    for (const char of chunk.toString("utf8")) {
      if (char === "\r" || char === "\n") continue;
      if (char === "\b" || char === "\x7f") {
        if (visibleLength > 0) {
          process.stderr.write("\b \b");
          visibleLength--;
        }
        continue;
      }
      // Skip other control characters (ctrl-c, arrow keys, etc.)
      if (char.charCodeAt(0) < 0x20) continue;
      process.stderr.write("*");
      visibleLength++;
    }
  };
  process.stdin.on("data", onData);

  return await new Promise<string>((resolve) => {
    rl.question("", (answer) => {
      process.stdin.off("data", onData);
      rl.close();
      process.stderr.write("\n");
      resolve(answer.trim());
    });
  });
}
