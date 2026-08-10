import { spawn } from "node:child_process"
import { createInterface } from "node:readline"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const ORCHESTRATOR_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..")

export async function runLoopProcess(
  runId: string,
  options?: {
    maxTicks?: number
    maxStageRetries?: number
    maxStageRevisions?: number
    providerRetryBudgetSeconds?: number
    outputPrefix?: string
  },
): Promise<number> {
  const maxTicks = options?.maxTicks ?? 50
  const maxStageRetries = options?.maxStageRetries ?? 4
  const maxStageRevisions = options?.maxStageRevisions ?? 3
  const providerRetryBudgetSeconds =
    options?.providerRetryBudgetSeconds ?? 60

  return await new Promise((resolvePromise, reject) => {
    const child = spawn(
      "npm",
      [
        "run", "loop", "--",
        "--run", runId,
        "--max-ticks", String(maxTicks),
        "--max-stage-retries", String(maxStageRetries),
        "--max-stage-revisions", String(maxStageRevisions),
        "--provider-retry-budget-seconds", String(providerRetryBudgetSeconds),
      ],
      {
        cwd: ORCHESTRATOR_ROOT,
        stdio: options?.outputPrefix === undefined
          ? "inherit"
          : ["ignore", "pipe", "pipe"],
        shell: false,
      },
    )

    if (options?.outputPrefix !== undefined) {
      const prefix = `[${options.outputPrefix}]`
      if (child.stdout) {
        createInterface({ input: child.stdout }).on("line", (line) => {
          process.stdout.write(`${prefix} ${line}\n`)
        })
      }
      if (child.stderr) {
        createInterface({ input: child.stderr }).on("line", (line) => {
          process.stderr.write(`${prefix} ${line}\n`)
        })
      }
    }

    child.once("error", reject)
    child.once("exit", (code: number | null) => resolvePromise(code ?? 1))
  })
}
