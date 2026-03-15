import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

const frontendRoot = process.cwd();
const repoRoot = resolve(frontendRoot, "..");
const outputPath = resolve(frontendRoot, "openapi.json");

const schema = execFileSync(
  "uv",
  [
    "run",
    "python",
    "-c",
    [
      "import json",
      "from backend.app.main import create_app",
      "print(json.dumps(create_app().openapi(), indent=2))",
    ].join("; "),
  ],
  {
    cwd: repoRoot,
    encoding: "utf-8",
  },
);

writeFileSync(outputPath, schema, "utf-8");
