import { spawn } from "node:child_process"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const ORCHESTRATOR_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")

export async function runLoopProcess(
  runId: string,
  options?: { maxTicks?: number; maxStageRetries?: number },
): Promise<number> {
  const maxTicks = options?.maxTicks ?? 50
  const maxStageRetries = options?.maxStageRetries ?? 4

  return await new Promise((resolvePromise, reject) => {
    const child = spawn(
      "npm",
      [
        "run", "loop", "--",
        "--run", runId,
        "--max-ticks", String(maxTicks),
        "--max-stage-retries", String(maxStageRetries),
      ],
      {
        cwd: ORCHESTRATOR_ROOT,
        stdio: "inherit",
        shell: false,
      },
    )

    child.once("error", reject)
    child.once("exit", (code: number | null) => resolvePromise(code ?? 1))
  })
}
