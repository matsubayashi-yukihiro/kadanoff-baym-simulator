import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const cwd = process.cwd();
const libRoots = [
  path.join(cwd, ".playwright-system-libs", "usr", "lib", "x86_64-linux-gnu"),
  path.join(cwd, ".playwright-system-libs", "lib", "x86_64-linux-gnu"),
  path.join(cwd, ".playwright-system-libs", "usr", "lib"),
];
const extraLibs = libRoots.filter((entry) => existsSync(entry));

const env = { ...process.env };
if (extraLibs.length > 0) {
  env.LD_LIBRARY_PATH = [...extraLibs, env.LD_LIBRARY_PATH]
    .filter(Boolean)
    .join(path.delimiter);
}

const command = process.platform === "win32" ? "npx.cmd" : "npx";
const child = spawn(command, ["playwright", "test", ...process.argv.slice(2)], {
  cwd,
  env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
