import type { FormalizationBatch } from "./batch-store.js"
import { saveBatch } from "./batch-store.js"
import { runLoopProcess } from "./loop-client.js"
import { loadRun } from "./run-store.js"
import type { FormalizationStage } from "./workflow.js"

const TERMINAL_STAGES = new Set<FormalizationStage>([
  "BENCHMARK_COMPLETE",
  "ACCEPTED",
  "BLOCKED",
  "FAILED",
])

export async function mapWithConcurrency<T, R>(
  values: readonly T[],
  concurrency: number,
  operation: (value: T, index: number) => Promise<R>,
): Promise<R[]> {
  if (!Number.isInteger(concurrency) || concurrency < 1) {
    throw new Error(`Concurrency must be a positive integer: ${concurrency}`)
  }

  const results = new Array<R>(values.length)
  let nextIndex = 0

  const worker = async (): Promise<void> => {
    while (true) {
      const index = nextIndex
      nextIndex += 1
      if (index >= values.length) return
      results[index] = await operation(values[index]!, index)
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(concurrency, values.length) }, worker),
  )
  return results
}

export type BatchRuntimeOptions = {
  concurrency: number
  maxTicks: number
  maxStageRetries: number
  maxStageRevisions: number
  providerRetryBudgetSeconds: number
}

export async function runBatch(
  batch: FormalizationBatch,
  options: BatchRuntimeOptions,
): Promise<{ batch: FormalizationBatch; exitCode: number; status: string }> {
  const runnable = []
  for (const entry of batch.runs) {
    const run = await loadRun(entry.runId)
    entry.lastObservedStage = run.stage
    if (!TERMINAL_STAGES.has(run.stage)) runnable.push(entry)
  }

  const results = await mapWithConcurrency(
    runnable,
    options.concurrency,
    async (entry) => {
      try {
        const exitCode = await runLoopProcess(entry.runId, {
          maxTicks: options.maxTicks,
          maxStageRetries: options.maxStageRetries,
          maxStageRevisions: options.maxStageRevisions,
          providerRetryBudgetSeconds: options.providerRetryBudgetSeconds,
          outputPrefix: entry.unit,
        })
        return { entry, exitCode }
      } catch (error) {
        return {
          entry,
          exitCode: 1,
          error: error instanceof Error ? error.message : String(error),
        }
      }
    },
  )

  for (const result of results) {
    result.entry.lastExitCode = result.exitCode
    result.entry.lastError = result.error
    result.entry.lastObservedStage = (await loadRun(result.entry.runId)).stage
  }

  const stages = await Promise.all(
    batch.runs.map(async (entry) => (await loadRun(entry.runId)).stage),
  )
  const hasFailure = results.some((result) => result.exitCode !== 0) ||
    stages.some((stage) => stage === "BLOCKED" || stage === "FAILED")
  const allComplete = stages.every(
    (stage) => stage === "BENCHMARK_COMPLETE" || stage === "ACCEPTED",
  )
  const waitingHuman = stages.some((stage) => stage.startsWith("WAITING_"))
  const status = hasFailure
    ? "INCOMPLETE"
    : allComplete
      ? "COMPLETE"
      : waitingHuman
        ? "WAITING_HUMAN"
        : "INCOMPLETE"

  const now = new Date().toISOString()
  batch.updatedAt = now
  batch.lastRunFinishedAt = now
  await saveBatch(batch)

  return { batch, exitCode: hasFailure ? 2 : 0, status }
}
