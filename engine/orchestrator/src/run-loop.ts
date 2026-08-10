import { startOpenCode } from "./opencode.js"
import { loadRun } from "./run-store.js"
import { proofTargetSummary } from "./proof-plan.js"
import { executeTick } from "./runner.js"
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

async function main(): Promise<void> {
  const runId = required("--run")
  const maxTicks = integerArgument("--max-ticks", 25)
  const maxStageRetries = integerArgument("--max-stage-retries", 4)
  const providerRetryBudgetSeconds =
    integerArgument("--provider-retry-budget-seconds", 60)
  let ticks = 0
  let consecutiveRetries = 0
  let retryStage: FormalizationStage | undefined
  let runtime: Awaited<ReturnType<typeof startOpenCode>> | undefined

  try {
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

      const beforeProofDeclared =
        before.stage === "PROOF_GENERATION"
          ? (await proofTargetSummary(before)).declared
          : undefined

      runtime ??= await startOpenCode()
      try {
        await executeTick(runId, {
          runtime,
          providerRetryBudgetMs: providerRetryBudgetSeconds * 1000,
        })
      } catch (error) {
        const current = await loadRun(runId)
        console.log(JSON.stringify({
          ok: false,
          stopped: true,
          reason: "TICK_EXECUTION_FAILED",
          runId,
          stage: current.stage,
          activeExecution: current.activeExecution ?? null,
          error: error instanceof Error ? error.message : String(error),
        }, null, 2))
        process.exitCode = 1
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
      const retried =
        after.stage === before.stage &&
        last?.outcome === "RETRY"

      const afterProofDeclared =
        after.stage === "PROOF_GENERATION"
          ? (await proofTargetSummary(after)).declared
          : undefined

      const proofMadeProgress =
        before.stage === "PROOF_GENERATION" &&
        after.stage === "PROOF_GENERATION" &&
        beforeProofDeclared !== undefined &&
        afterProofDeclared !== undefined &&
        afterProofDeclared > beforeProofDeclared

      if (proofMadeProgress) {
        console.log(
          `[spec2lean] proof progress ${beforeProofDeclared}/${(await proofTargetSummary(before)).total} -> ${afterProofDeclared}/${(await proofTargetSummary(after)).total}; stall counter reset`,
        )

        retryStage = undefined
        consecutiveRetries = 0
      } else if (retried) {
        if (retryStage === after.stage) {
          consecutiveRetries += 1
        } else {
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
  } finally {
    runtime?.runtime.server.close()
  }
}

await main()
