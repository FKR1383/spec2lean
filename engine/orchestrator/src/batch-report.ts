import { loadBatch } from "./batch-store.js"
import { benchmarkGateParking, waitingGateForStage } from "./gate-runtime.js"
import { loadRun } from "./run-store.js"

function percentile(values: readonly number[], quantile: number): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((left, right) => left - right)
  const index = Math.min(sorted.length - 1, Math.ceil(sorted.length * quantile) - 1)
  return sorted[Math.max(0, index)]!
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

const batchId = argument("--batch")
if (!batchId) throw new Error("Missing required argument: --batch")

const batch = await loadBatch(batchId)
const runs = await Promise.all(batch.runs.map(async (entry) => {
  const run = await loadRun(entry.runId)
  const parking = await benchmarkGateParking(run)
  const executions = run.executions ?? []
  const proofContinuations = executions.filter(
    (execution) => execution.progress?.kind === "PROOF_BATCH_CONTINUATION",
  ).length
  const status = entry.lastStatus ?? (
    entry.lastError !== undefined
      ? "STOPPED"
      : run.stage === "ACCEPTED" || run.stage === "BENCHMARK_COMPLETE"
        ? "COMPLETE"
        : run.stage === "BLOCKED" || run.stage === "FAILED"
          ? "BLOCKED"
          : parking !== undefined
            ? "PARKED_SEMANTIC_REVIEW"
            : waitingGateForStage(run.stage) !== undefined
              ? "WAITING_HUMAN"
              : "NO_RUNNABLE_WORK"
  )
  return {
    unit: entry.unit,
    runId: entry.runId,
    stage: run.stage,
    status,
    blockingIssues: entry.blockingIssues ?? parking?.issues ?? [],
    wallClockSeconds: Number(((Date.parse(run.updatedAt) - Date.parse(run.createdAt)) / 1000).toFixed(1)),
    agentExecutions: executions.length,
    revisions: executions.filter((execution) => execution.outcome === "REVISE").length,
    retries: executions.filter(
      (execution) => execution.outcome === "RETRY" && execution.progress === undefined,
    ).length,
    proofContinuations,
    providerRetryBudgetFailures: executions.filter(
      (execution) => execution.failureClass === "PROVIDER_RETRY_BUDGET_EXCEEDED",
    ).length,
    executionModels: executions.reduce<Record<string, number>>((counts, execution) => {
      const model = execution.model ?? "unrecorded"
      counts[model] = (counts[model] ?? 0) + 1
      return counts
    }, {}),
    traceabilityManifests: executions.filter(
      (execution) => execution.traceability !== undefined,
    ).length,
    traceabilityGenerationSeconds: Number((executions.reduce(
      (total, execution) => total + (execution.traceability?.generationMs ?? 0),
      0,
    ) / 1000).toFixed(3)),
    unresolvedTraceabilityReferences: executions.reduce(
      (total, execution) =>
        total + (execution.traceability?.unresolvedReferences ?? 0),
      0,
    ),
  }
}))

const startedAt = Date.parse(batch.createdAt)
const finishedAt = Date.parse(batch.lastRunFinishedAt ?? batch.updatedAt)
const wallClockMs = Math.max(0, finishedAt - startedAt)
const jobs = batch.pipeline?.jobs ?? []
const stageMetrics = Object.values(jobs.reduce<Record<string, {
  stage: string
  jobs: number
  serviceMs: number[]
  queueWaitMs: number[]
  errors: number
}>>((groups, job) => {
  const group = groups[job.fromStage] ?? {
    stage: job.fromStage,
    jobs: 0,
    serviceMs: [],
    queueWaitMs: [],
    errors: 0,
  }
  group.jobs += 1
  group.serviceMs.push(job.serviceMs)
  group.queueWaitMs.push(job.queueWaitMs)
  if (job.error !== undefined) group.errors += 1
  groups[job.fromStage] = group
  return groups
}, {})).map((group) => ({
  stage: group.stage,
  jobs: group.jobs,
  serviceSeconds: Number((group.serviceMs.reduce((sum, value) => sum + value, 0) / 1000).toFixed(1)),
  meanServiceSeconds: Number((group.serviceMs.reduce((sum, value) => sum + value, 0) / group.jobs / 1000).toFixed(1)),
  p95ServiceSeconds: Number((percentile(group.serviceMs, 0.95) / 1000).toFixed(1)),
  meanQueueWaitSeconds: Number((group.queueWaitMs.reduce((sum, value) => sum + value, 0) / group.jobs / 1000).toFixed(1)),
  p95QueueWaitSeconds: Number((percentile(group.queueWaitMs, 0.95) / 1000).toFixed(1)),
  errors: group.errors,
})).sort((left, right) => right.serviceSeconds - left.serviceSeconds)
const agentMetrics = Object.values(jobs.reduce<Record<string, {
  agent: string
  jobs: number
  serviceMs: number[]
  queueWaitMs: number[]
  retries: number
  revisions: number
  continuations: number
  errors: number
}>>((groups, job) => {
  const group = groups[job.agent] ?? {
    agent: job.agent,
    jobs: 0,
    serviceMs: [],
    queueWaitMs: [],
    retries: 0,
    revisions: 0,
    continuations: 0,
    errors: 0,
  }
  group.jobs += 1
  group.serviceMs.push(job.serviceMs)
  group.queueWaitMs.push(job.queueWaitMs)
  if (job.outcome === "RETRY" && job.productiveProgress !== true) group.retries += 1
  if (job.productiveProgress === true) group.continuations += 1
  if (job.outcome === "REVISE") group.revisions += 1
  if (job.error !== undefined) group.errors += 1
  groups[job.agent] = group
  return groups
}, {})).map((group) => ({
  agent: group.agent,
  jobs: group.jobs,
  serviceSeconds: Number((group.serviceMs.reduce((sum, value) => sum + value, 0) / 1000).toFixed(1)),
  meanServiceSeconds: Number((group.serviceMs.reduce((sum, value) => sum + value, 0) / group.jobs / 1000).toFixed(1)),
  p95ServiceSeconds: Number((percentile(group.serviceMs, 0.95) / 1000).toFixed(1)),
  meanQueueWaitSeconds: Number((group.queueWaitMs.reduce((sum, value) => sum + value, 0) / group.jobs / 1000).toFixed(1)),
  p95QueueWaitSeconds: Number((percentile(group.queueWaitMs, 0.95) / 1000).toFixed(1)),
  retries: group.retries,
  revisions: group.revisions,
  continuations: group.continuations,
  errors: group.errors,
})).sort((left, right) => right.serviceSeconds - left.serviceSeconds)
const totalServiceMs = jobs.reduce((sum, job) => sum + job.serviceMs, 0)
const completedUnits = runs.filter(
  (run) => run.stage === "ACCEPTED" || run.stage === "BENCHMARK_COMPLETE",
).length
const workerUtilization = Object.entries(jobs.reduce<Record<string, number>>(
  (totals, job) => {
    totals[job.workerId] = (totals[job.workerId] ?? 0) + job.serviceMs
    return totals
  },
  {},
)).map(([workerId, serviceMs]) => ({
  workerId,
  serviceSeconds: Number((serviceMs / 1000).toFixed(1)),
  utilization: wallClockMs === 0 ? 0 : Number((serviceMs / wallClockMs).toFixed(3)),
})).sort((left, right) => left.workerId.localeCompare(right.workerId))
const unitLatenciesMs = runs.map((run) => run.wallClockSeconds * 1000)
const totalAgentExecutions = runs.reduce((total, run) => total + run.agentExecutions, 0)
const totalRetries = runs.reduce((total, run) => total + run.retries, 0)
const totalProofContinuations = runs.reduce(
  (total, run) => total + run.proofContinuations,
  0,
)
const statusCounts = runs.reduce<Record<string, number>>((counts, run) => {
  counts[run.status] = (counts[run.status] ?? 0) + 1
  return counts
}, {})
console.log(JSON.stringify({
  batchId: batch.batchId,
  language: batch.language,
  specVersion: batch.specVersion,
  autoApprove: batch.autoApprove,
  concurrency: batch.concurrency,
  executionMode: batch.executionMode ?? "RUN_PARALLEL",
  batchWallClockSeconds: Number(((finishedAt - startedAt) / 1000).toFixed(1)),
  totals: {
    units: runs.length,
    statusCounts,
    agentExecutions: runs.reduce((total, run) => total + run.agentExecutions, 0),
    revisions: runs.reduce((total, run) => total + run.revisions, 0),
    retries: runs.reduce((total, run) => total + run.retries, 0),
    proofContinuations: totalProofContinuations,
    providerRetryBudgetFailures: runs.reduce(
      (total, run) => total + run.providerRetryBudgetFailures,
      0,
    ),
    traceabilityManifests: runs.reduce(
      (total, run) => total + run.traceabilityManifests,
      0,
    ),
    traceabilityGenerationSeconds: Number(runs.reduce(
      (total, run) => total + run.traceabilityGenerationSeconds,
      0,
    ).toFixed(3)),
    unresolvedTraceabilityReferences: runs.reduce(
      (total, run) => total + run.unresolvedTraceabilityReferences,
      0,
    ),
  },
  pipeline: batch.pipeline === undefined ? undefined : {
    globalWorkers: batch.pipeline.globalWorkers,
    schedulingMode: batch.pipeline.schedulingMode,
    agentCaps: batch.pipeline.agentCaps,
    pinnedDependencies: batch.pipeline.dependencies,
    jobs: jobs.length,
    throughputUnitsPerHour: wallClockMs === 0
      ? 0
      : Number((completedUnits * 3_600_000 / wallClockMs).toFixed(2)),
    aggregateWorkerUtilization: wallClockMs === 0
      ? 0
      : Number((totalServiceMs / (wallClockMs * batch.pipeline.globalWorkers)).toFixed(3)),
    workerUtilization,
    unitLatencySeconds: {
      p50: Number((percentile(unitLatenciesMs, 0.50) / 1000).toFixed(1)),
      p95: Number((percentile(unitLatenciesMs, 0.95) / 1000).toFixed(1)),
    },
    retryRate: totalAgentExecutions === 0
      ? 0
      : Number((totalRetries / totalAgentExecutions).toFixed(3)),
    reworkFraction: jobs.length === 0
      ? 0
      : Number((jobs.filter(
          (job) =>
            (job.outcome === "RETRY" && job.productiveProgress !== true) ||
            job.outcome === "REVISE",
        ).length / jobs.length).toFixed(3)),
    manifestProducingJobs: jobs.filter(
      (job) => job.manifestCountAfter > job.manifestCountBefore,
    ).length,
    manifestGenerationIncludedInStageServiceTime: true,
    criticalStageByServiceTime: stageMetrics[0]?.stage,
    stageMetrics,
    criticalAgentByServiceTime: agentMetrics[0]?.agent,
    agentMetrics,
  },
  runs,
}, null, 2))
