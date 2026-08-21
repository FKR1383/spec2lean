import { startOpenCode } from "./opencode.js"
import {
  advanceBenchmarkGate,
  benchmarkGateParking,
  waitingGateForStage,
} from "./gate-runtime.js"
import { loadRun, saveRun } from "./run-store.js"
import {
  consecutiveOutputLengthFailureCount,
  isProviderAvailabilityFailure,
  noProgressRetryCount,
  noProgressRetryLimitReached,
  outputLengthRetryLimitReached,
} from "./retry-policy.js"
import { proofTargetSummary } from "./proof-plan.js"
import {
  executeTick,
  recoverNonAuthoritativeSemanticBlock,
  recoverNonAuthoritativeSourceBlock,
} from "./runner.js"
import type { FormalizationStage } from "./workflow.js"

const TERMINAL_STAGES = new Set<FormalizationStage>([
  "BENCHMARK_COMPLETE",
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
  const maxStageRevisions = integerArgument("--max-stage-revisions", 3)
  const providerRetryBudgetSeconds =
    integerArgument("--provider-retry-budget-seconds", 60)
  let ticks = 0
  let consecutiveRetries = 0
  let retryStage: FormalizationStage | undefined
  let runtime: Awaited<ReturnType<typeof startOpenCode>> | undefined

  try {
    while (true) {
      let before = await loadRun(runId)
      console.log(`[spec2lean] run=${runId} stage=${before.stage} revision=${before.revision}`)

      const recoveredSourceBlock = await recoverNonAuthoritativeSourceBlock(before)
      if (recoveredSourceBlock !== undefined) {
        await saveRun(recoveredSourceBlock)
        console.log(JSON.stringify({
          ok: true,
          deterministic: true,
          recovered: true,
          runId,
          fromStage: before.stage,
          toStage: recoveredSourceBlock.stage,
          revision: recoveredSourceBlock.revision,
          summary: recoveredSourceBlock.history.at(-1)?.reason,
        }, null, 2))
        before = recoveredSourceBlock
      }

      const recoveredSemanticBlock = await recoverNonAuthoritativeSemanticBlock(before)
      if (recoveredSemanticBlock !== undefined) {
        await saveRun(recoveredSemanticBlock)
        console.log(JSON.stringify({
          ok: true,
          deterministic: true,
          recovered: true,
          runId,
          fromStage: before.stage,
          toStage: recoveredSemanticBlock.stage,
          revision: recoveredSemanticBlock.revision,
          summary: recoveredSemanticBlock.history.at(-1)?.reason,
        }, null, 2))
        before = recoveredSemanticBlock
      }

      const waitingGate = waitingGateForStage(before.stage)
      const autoAdvance = await advanceBenchmarkGate(before)
      if (autoAdvance !== undefined) {
        const next = autoAdvance.run
        console.log(JSON.stringify({
          ok: true,
          deterministic: true,
          benchmarkOnly: true,
          humanConfirmationRecorded: false,
          runId,
          gate: autoAdvance.gate,
          reviewPath: autoAdvance.reviewPath,
          semanticAssumptions: autoAdvance.semanticAssumptions,
          fromStage: before.stage,
          toStage: next.stage,
          revision: next.revision,
        }, null, 2))
        continue
      }

      if (waitingGate !== undefined) {
        const parking = await benchmarkGateParking(before)
        console.log(JSON.stringify({
          ok: parking === undefined,
          stopped: true,
          reason: parking?.reason ?? "HUMAN_APPROVAL_REQUIRED",
          runId,
          stage: before.stage,
          gate: waitingGate,
          ticks,
          ...(parking === undefined ? {} : { issues: parking.issues }),
        }, null, 2))
        if (parking !== undefined) process.exitCode = 2
        return
      }

      if (TERMINAL_STAGES.has(before.stage)) {
        const accepted = before.stage === "ACCEPTED" || before.stage === "BENCHMARK_COMPLETE"
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

      const after = await loadRun(runId)
      const last = after.executions?.at(-1)

      if (isProviderAvailabilityFailure(last)) {
        console.log(JSON.stringify({
          ok: false,
          stopped: true,
          resumable: true,
          reason: "PROVIDER_UNAVAILABLE",
          runId,
          stage: after.stage,
          ticks,
          hint: `Provider capacity was unavailable; resume ${runId} later without spending semantic retry budget.`,
        }, null, 2))
        process.exitCode = 2
        return
      }

      ticks += 1

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

      const stageRevisionCount = last?.outcome === "REVISE"
        ? (after.executions ?? []).filter(
            (execution) =>
              execution.stage === last.stage && execution.outcome === "REVISE",
          ).length
        : 0

      if (stageRevisionCount >= maxStageRevisions) {
        console.log(JSON.stringify({
          ok: false,
          stopped: true,
          reason: "STAGE_REVISION_LIMIT_REACHED",
          runId,
          criticStage: last?.stage,
          revisionTarget: after.stage,
          revisionExecutions: stageRevisionCount,
          hint: `Inspect the latest critic artifact, then explicitly resume ${runId} if another bounded repair cycle is justified.`,
        }, null, 2))
        process.exitCode = 2
        return
      }

      const consecutiveOutputLengthFailures = consecutiveOutputLengthFailureCount(
        after.executions ?? [],
        consecutiveRetries,
      )
      if (outputLengthRetryLimitReached(after.executions ?? [], consecutiveRetries)) {
        console.log(JSON.stringify({
          ok: false,
          stopped: true,
          reason: "OUTPUT_LENGTH_RETRY_LIMIT_REACHED",
          runId,
          stage: after.stage,
          consecutiveOutputLengthFailures,
          hint: "The bounded recovery attempt also exhausted model output. Inspect the stage prompt/tool trace; do not retry unchanged.",
        }, null, 2))
        process.exitCode = 2
        return
      }

      const repeatedNoProgressRetries = noProgressRetryCount(
        after.executions ?? [],
        after.stage,
      )
      if (noProgressRetryLimitReached(after.executions ?? [], after.stage)) {
        console.log(JSON.stringify({
          ok: false,
          stopped: true,
          reason: "NO_PROGRESS_RETRY_LIMIT_REACHED",
          runId,
          stage: after.stage,
          repeatedNoProgressRetries,
          failureFingerprint: last?.failureFingerprint,
          hint: "The bounded repair repeated the same diagnostic without artifact or proof-declaration progress; inspect or change the repair route/model instead of resuming unchanged.",
        }, null, 2))
        process.exitCode = 2
        return
      }

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
