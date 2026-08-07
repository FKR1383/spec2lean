import { spawn } from "node:child_process"

import { loadRun } from "./run-store.js"
import type { FormalizationStage } from "./workflow.js"

const HUMAN_WAIT_STAGES = new Set<FormalizationStage>([
  "WAITING_GATE_A",
  "WAITING_GATE_B",
  "WAITING_GATE_C",
  "WAITING_THEOREM_STRENGTH_APPROVAL",
  "WAITING_FINAL_APPROVAL",
])

const TERMINAL_STAGES = new Set<FormalizationStage>([
  "ACCEPTED",
  "BLOCKED",
  "FAILED",
])

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function integerArgument(name: string, fallback: number): number {
  const raw = argument(name)
  if (raw === undefined) return fallback
  const value = Number(raw)
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`Invalid positive integer for ${name}: ${raw}`)
  }
  return value
}

async function runTick(runId: string): Promise<number> {
  return await new Promise((resolve, reject) => {
    const child = spawn(
      "npm",
      ["run", "tick", "--", "--run", runId],
      { stdio: "inherit", shell: false },
    )
    child.once("error", reject)
    child.once("exit", (code: number | null) => resolve(code ?? 1))
  })
}

async function main(): Promise<void> {
  const runId = required("--run")
  const maxTicks = integerArgument("--max-ticks", 25)
  const maxStageRetries = integerArgument("--max-stage-retries", 4)
  let ticks = 0
  let consecutiveRetries = 0
  let retryStage: FormalizationStage | undefined

  while (true) {
    const before = await loadRun(runId)
    console.log(`[spec2lean] run=${runId} stage=${before.stage} revision=${before.revision}`)

    if (HUMAN_WAIT_STAGES.has(before.stage)) {
      console.log(JSON.stringify({
        ok: true,
        stopped: true,
        reason: "HUMAN_APPROVAL_REQUIRED",
        runId,
        stage: before.stage,
        ticks,
      }, null, 2))
      return
    }

    if (TERMINAL_STAGES.has(before.stage)) {
      const accepted = before.stage === "ACCEPTED"
      console.log(JSON.stringify({
        ok: accepted,
        stopped: true,
        reason: before.stage,
        runId,
        stage: before.stage,
        ticks,
      }, null, 2))
      if (!accepted) process.exitCode = 2
      return
    }

    if (ticks >= maxTicks) {
      console.log(JSON.stringify({
        ok: false,
        stopped: true,
        reason: "MAX_TICKS_REACHED",
        runId,
        stage: before.stage,
        ticks,
      }, null, 2))
      process.exitCode = 2
      return
    }

    const code = await runTick(runId)
    if (code !== 0) {
      const current = await loadRun(runId)
      console.log(JSON.stringify({
        ok: false,
        stopped: true,
        reason: "TICK_PROCESS_FAILED",
        runId,
        stage: current.stage,
        activeExecution: current.activeExecution ?? null,
        exitCode: code,
      }, null, 2))
      process.exitCode = code
      return
    }

    ticks += 1
    const after = await loadRun(runId)

    if (after.revision <= before.revision) {
      console.log(JSON.stringify({
        ok: false,
        stopped: true,
        reason: "RUN_REVISION_DID_NOT_ADVANCE",
        runId,
        beforeRevision: before.revision,
        afterRevision: after.revision,
      }, null, 2))
      process.exitCode = 2
      return
    }

    const last = after.executions?.at(-1)
    const retried = after.stage === before.stage && last?.outcome === "RETRY"

    if (retried) {
      if (retryStage === after.stage) consecutiveRetries += 1
      else {
        retryStage = after.stage
        consecutiveRetries = 1
      }
    } else {
      retryStage = undefined
      consecutiveRetries = 0
    }

    console.log(`[spec2lean] transition ${before.stage} -> ${after.stage}`)

    if (consecutiveRetries >= maxStageRetries) {
      console.log(JSON.stringify({
        ok: false,
        stopped: true,
        reason: "STAGE_RETRY_LIMIT_REACHED",
        runId,
        stage: after.stage,
        consecutiveRetries,
        hint: `Run npm run doctor -- --run ${runId}`,
      }, null, 2))
      process.exitCode = 2
      return
    }
  }
}

await main()
