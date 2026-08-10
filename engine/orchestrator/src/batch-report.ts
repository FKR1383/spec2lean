import { loadBatch } from "./batch-store.js"
import { loadRun } from "./run-store.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

const batchId = argument("--batch")
if (!batchId) throw new Error("Missing required argument: --batch")

const batch = await loadBatch(batchId)
const runs = await Promise.all(batch.runs.map(async (entry) => {
  const run = await loadRun(entry.runId)
  const executions = run.executions ?? []
  return {
    unit: entry.unit,
    runId: entry.runId,
    stage: run.stage,
    wallClockSeconds: Number(((Date.parse(run.updatedAt) - Date.parse(run.createdAt)) / 1000).toFixed(1)),
    agentExecutions: executions.length,
    revisions: executions.filter((execution) => execution.outcome === "REVISE").length,
    retries: executions.filter((execution) => execution.outcome === "RETRY").length,
    providerRetryBudgetFailures: executions.filter(
      (execution) => execution.failureClass === "PROVIDER_RETRY_BUDGET_EXCEEDED",
    ).length,
  }
}))

const startedAt = Date.parse(batch.createdAt)
const finishedAt = Date.parse(batch.lastRunFinishedAt ?? batch.updatedAt)
console.log(JSON.stringify({
  batchId: batch.batchId,
  language: batch.language,
  specVersion: batch.specVersion,
  autoApprove: batch.autoApprove,
  concurrency: batch.concurrency,
  batchWallClockSeconds: Number(((finishedAt - startedAt) / 1000).toFixed(1)),
  totals: {
    units: runs.length,
    agentExecutions: runs.reduce((total, run) => total + run.agentExecutions, 0),
    revisions: runs.reduce((total, run) => total + run.revisions, 0),
    retries: runs.reduce((total, run) => total + run.retries, 0),
    providerRetryBudgetFailures: runs.reduce(
      (total, run) => total + run.providerRetryBudgetFailures,
      0,
    ),
  },
  runs,
}, null, 2))
