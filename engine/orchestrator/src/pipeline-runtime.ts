import { randomUUID } from "node:crypto"
import { readdir } from "node:fs/promises"
import { resolve } from "node:path"

import {
  loadBatch,
  saveBatch,
  type FormalizationBatch,
  type PipelineJobMetric,
  type PipelineLease,
  type PipelineAgent,
} from "./batch-store.js"
import { advanceBenchmarkGate, waitingGateForStage } from "./gate-runtime.js"
import { startOpenCode, type Spec2LeanOpenCode } from "./opencode.js"
import {
  pipelineAgentForRun,
  pipelineAgentWorkerLayout,
  poolForStage,
  selectPipelineCandidate,
} from "./pipeline-config.js"
import { verifyPipelineDependencies } from "./pipeline-dependencies.js"
import { proofTargetSummary } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { withRepositoryLock } from "./repository-lock.js"
import { executeTick } from "./runner.js"
import { loadRun, saveRun } from "./run-store.js"
import { prepareSemanticV2Run } from "./semantic-v2.js"
import type { FormalizationStage, RunState } from "./workflow.js"

const TERMINAL_STAGES = new Set<FormalizationStage>([
  "BENCHMARK_COMPLETE",
  "ACCEPTED",
  "BLOCKED",
  "FAILED",
])

export type PipelineRuntimeOptions = {
  globalWorkers: number
  maxTicks: number
  maxStageRetries: number
  maxStageRevisions: number
  providerRetryBudgetSeconds: number
}

type WorkerSlot = {
  id: string
  agent: PipelineAgent
  busy: boolean
}

type PipelineJobResult = {
  worker: WorkerSlot
  lease: PipelineLease
  before: RunState
  after: RunState
  metric: PipelineJobMetric
  proofMadeProgress: boolean
  infrastructureRetry?: boolean
  error?: string
}

function isSharedRuntimeTransportError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return [
    "fetch failed",
    "ECONNREFUSED",
    "ECONNRESET",
    "EPIPE",
    "socket hang up",
    "server closed",
  ].some((fragment) => message.toLowerCase().includes(fragment.toLowerCase()))
}

function processIsAlive(pid: number): boolean {
  try {
    process.kill(pid, 0)
    return true
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM"
  }
}

async function loadRunForPipelineRouting(runId: string): Promise<RunState> {
  let run = await loadRun(runId)
  if (run.stage === "SEMANTIC_EXTRACTION") {
    const prepared = await prepareSemanticV2Run(run)
    if (prepared !== run) {
      await saveRun(prepared)
      run = prepared
    }
  }
  return run
}

async function claimController(batchId: string): Promise<FormalizationBatch> {
  return await withRepositoryLock(`pipeline-${batchId}-claim`, async () => {
    const batch = await loadBatch(batchId)
    if (batch.pipeline === undefined) throw new Error("Batch has no stage-pipeline state")
    const controller = batch.pipeline.controller
    if (
      controller !== undefined &&
      controller.pid !== process.pid &&
      processIsAlive(controller.pid)
    ) {
      throw new Error(
        `Pipeline batch ${batchId} is already controlled by live PID ${controller.pid}`,
      )
    }
    batch.pipeline.controller = {
      pid: process.pid,
      claimedAt: new Date().toISOString(),
    }
    // Leases owned by a dead controller are recoverable because executeTick
    // persists activeExecution in the unit run before submitting a session.
    batch.pipeline.leases = {}
    batch.pipeline.updatedAt = new Date().toISOString()
    batch.updatedAt = batch.pipeline.updatedAt
    await saveBatch(batch)
    return batch
  })
}

async function releaseController(batch: FormalizationBatch): Promise<void> {
  if (batch.pipeline?.controller?.pid !== process.pid) return
  batch.pipeline.controller = undefined
  batch.pipeline.leases = {}
  batch.pipeline.updatedAt = new Date().toISOString()
  batch.updatedAt = batch.pipeline.updatedAt
  await saveBatch(batch)
}

async function manifestCount(runId: string): Promise<number> {
  const directory = resolve(REPO_ROOT, `runs/${runId}/traceability`)
  try {
    return (await readdir(directory)).filter(
      (name) => /^evidence-[a-f0-9]{64}\.json$/.test(name),
    ).length
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return 0
    throw error
  }
}

async function runPipelineJob(
  worker: WorkerSlot,
  lease: PipelineLease,
  queuedAt: string,
  providerRetryBudgetSeconds: number,
  ensureRuntime: () => Promise<Spec2LeanOpenCode>,
  invalidateRuntime: (runtime: Spec2LeanOpenCode) => Promise<boolean>,
): Promise<PipelineJobResult> {
  const before = await loadRunForPipelineRouting(lease.runId)
  const selectedAgent = pipelineAgentForRun(before)
  if (selectedAgent !== worker.agent || lease.agent !== worker.agent) {
    throw new Error(
      `Agent-pinned worker ${worker.id}/${worker.agent} cannot execute ` +
      `${before.stage} routed to ${selectedAgent ?? "no-agent"}`,
    )
  }
  const beforeManifestCount = await manifestCount(lease.runId)
  const beforeProofDeclared = before.stage === "PROOF_GENERATION"
    ? (await proofTargetSummary(before)).declared
    : undefined
  const startedAt = new Date().toISOString()
  let error: string | undefined
  let infrastructureRetry = false
  let runtime: Spec2LeanOpenCode | undefined

  try {
    runtime = await ensureRuntime()
    await executeTick(lease.runId, {
      runtime,
      providerRetryBudgetMs: providerRetryBudgetSeconds * 1000,
    })
  } catch (caught) {
    error = caught instanceof Error ? caught.message : String(caught)
    infrastructureRetry = isSharedRuntimeTransportError(caught)
    if (infrastructureRetry && runtime !== undefined) {
      await invalidateRuntime(runtime)
    }
  }

  const after = await loadRun(lease.runId)
  const afterManifestCount = await manifestCount(lease.runId)
  const afterProofDeclared = after.stage === "PROOF_GENERATION"
    ? (await proofTargetSummary(after)).declared
    : undefined
  const finishedAt = new Date().toISOString()
  const last = after.executions?.at(-1)
  const metric: PipelineJobMetric = {
    leaseId: lease.leaseId,
    workerId: worker.id,
    runId: lease.runId,
    unit: lease.unit,
    pool: lease.pool,
    agent: lease.agent,
    fromStage: before.stage,
    toStage: after.stage,
    queuedAt,
    startedAt,
    finishedAt,
    queueWaitMs: Math.max(0, Date.parse(startedAt) - Date.parse(queuedAt)),
    serviceMs: Math.max(0, Date.parse(finishedAt) - Date.parse(startedAt)),
    outcome:
      after.revision > before.revision && last?.stage === before.stage
        ? last.outcome
        : undefined,
    manifestCountBefore: beforeManifestCount,
    manifestCountAfter: afterManifestCount,
    manifestGenerationIncludedInServiceMs: true,
    error,
  }

  return {
    worker,
    lease,
    before,
    after,
    metric,
    infrastructureRetry,
    proofMadeProgress:
      before.stage === "PROOF_GENERATION" &&
      after.stage === "PROOF_GENERATION" &&
      beforeProofDeclared !== undefined &&
      afterProofDeclared !== undefined &&
      afterProofDeclared > beforeProofDeclared,
    error,
  }
}

async function failedPipelineJob(
  worker: WorkerSlot,
  lease: PipelineLease,
  queuedAt: string,
  before: RunState,
  caught: unknown,
): Promise<PipelineJobResult> {
  const error = caught instanceof Error ? caught.message : String(caught)
  const finishedAt = new Date().toISOString()
  const after = await loadRun(lease.runId).catch(() => before)
  const count = await manifestCount(lease.runId).catch(() => 0)
  return {
    worker,
    lease,
    before,
    after,
    proofMadeProgress: false,
    error,
    metric: {
      leaseId: lease.leaseId,
      workerId: worker.id,
      runId: lease.runId,
      unit: lease.unit,
      pool: lease.pool,
      agent: lease.agent,
      fromStage: before.stage,
      toStage: after.stage,
      queuedAt,
      startedAt: lease.leasedAt,
      finishedAt,
      queueWaitMs: Math.max(0, Date.parse(lease.leasedAt) - Date.parse(queuedAt)),
      serviceMs: Math.max(0, Date.parse(finishedAt) - Date.parse(lease.leasedAt)),
      manifestCountBefore: count,
      manifestCountAfter: count,
      manifestGenerationIncludedInServiceMs: true,
      error,
    },
  }
}

function stageRevisionCount(run: RunState): number {
  const last = run.executions?.at(-1)
  if (last?.outcome !== "REVISE") return 0
  return (run.executions ?? []).filter(
    (execution) => execution.stage === last.stage && execution.outcome === "REVISE",
  ).length
}

function batchStatus(runs: readonly RunState[], stopped: ReadonlyMap<string, string>): string {
  if (runs.every((run) => run.stage === "ACCEPTED" || run.stage === "BENCHMARK_COMPLETE")) {
    return "COMPLETE"
  }
  if (
    stopped.size > 0 ||
    runs.some((run) => run.stage === "BLOCKED" || run.stage === "FAILED")
  ) return "INCOMPLETE"
  if (runs.some((run) => waitingGateForStage(run.stage) !== undefined)) {
    return "WAITING_HUMAN"
  }
  return "INCOMPLETE"
}

export async function runPipelinedBatch(
  initialBatch: FormalizationBatch,
  options: PipelineRuntimeOptions,
): Promise<{ batch: FormalizationBatch; exitCode: number; status: string }> {
  let batch = await claimController(initialBatch.batchId)
  if (batch.pipeline === undefined) throw new Error("Batch has no stage-pipeline state")
  const dependencyIssues = await verifyPipelineDependencies(batch.pipeline.dependencies)
  if (dependencyIssues.length > 0) {
    await releaseController(batch)
    throw new Error(
      "Pinned pipeline language-front-end changed; create a new batch or explicitly rebuild it: " +
      dependencyIssues.join(" | "),
    )
  }

  batch.pipeline.globalWorkers = options.globalWorkers
  const workers: WorkerSlot[] = pipelineAgentWorkerLayout(
    batch.pipeline.agentCaps,
  ).map((worker) => ({ ...worker, busy: false }))
  const active = new Map<string, Promise<PipelineJobResult>>()
  const invocationTicks = new Map<string, number>()
  const stopped = new Map<string, string>()
  let runtimeRestartAttempts = 0
  let sharedRuntime: Spec2LeanOpenCode | undefined
  let sharedRuntimeStartup: Promise<Spec2LeanOpenCode> | undefined
  const ensureRuntime = async (): Promise<Spec2LeanOpenCode> => {
    if (sharedRuntime !== undefined) return sharedRuntime
    sharedRuntimeStartup ??= startOpenCode().catch((error) => {
      runtimeRestartAttempts += 1
      sharedRuntimeStartup = undefined
      throw error
    })
    sharedRuntime = await sharedRuntimeStartup
    return sharedRuntime
  }
  const invalidateRuntime = async (runtime: Spec2LeanOpenCode): Promise<boolean> => {
    if (sharedRuntime !== runtime) return false
    runtime.runtime.server.close()
    sharedRuntime = undefined
    sharedRuntimeStartup = undefined
    runtimeRestartAttempts += 1
    return true
  }

  try {
    while (true) {
      let runs = await Promise.all(
        batch.runs.map((entry) => loadRunForPipelineRouting(entry.runId)),
      )
      let gateAdvanced = false
      for (const run of runs) {
        const advanced = await advanceBenchmarkGate(run)
        if (advanced === undefined) continue
        gateAdvanced = true
        console.log(
          `[pipeline] unit=${run.unit} gate=${advanced.gate} ` +
          `benchmark-auto-advance ${run.stage} -> ${advanced.run.stage}`,
        )
      }
      if (gateAdvanced) {
        runs = await Promise.all(
          batch.runs.map((entry) => loadRunForPipelineRouting(entry.runId)),
        )
      }

      const now = new Date().toISOString()
      for (const run of runs) {
        const state = batch.pipeline.runs[run.runId] ?? {
          totalTicks: 0,
          consecutiveRetries: 0,
        }
        const pool = poolForStage(run.stage)
        if (pool === undefined || TERMINAL_STAGES.has(run.stage)) {
          state.readyStage = undefined
          state.readySince = undefined
        } else if (state.readyStage !== run.stage) {
          state.readyStage = run.stage
          state.readySince = now
        }
        batch.pipeline.runs[run.runId] = state
      }

      let dispatched = false
      while (active.size < options.globalWorkers) {
        const candidates = runs.flatMap((run) => {
          const pool = poolForStage(run.stage)
          const agent = pipelineAgentForRun(run)
          const state = batch.pipeline!.runs[run.runId]
          if (
            pool === undefined ||
            agent === undefined ||
            stopped.has(run.runId) ||
            batch.pipeline!.leases[run.runId] !== undefined ||
            (invocationTicks.get(run.runId) ?? 0) >= options.maxTicks
          ) return []
          return [{
            value: run,
            pool,
            agent,
            readySince: state?.readySince ?? now,
            stableKey: run.unit,
          }]
        })
        const proposals = workers.flatMap((worker) => {
          if (worker.busy) return []
          const candidate = selectPipelineCandidate(candidates, worker.agent)
          return candidate === undefined ? [] : [{ worker, candidate }]
        }).sort((left, right) =>
          Date.parse(left.candidate.readySince) - Date.parse(right.candidate.readySince) ||
          left.candidate.stableKey.localeCompare(right.candidate.stableKey) ||
          left.worker.id.localeCompare(right.worker.id)
        )
        const proposal = proposals[0]
        if (proposal === undefined) break
        const { worker, candidate: selected } = proposal

        const lease: PipelineLease = {
          leaseId: randomUUID(),
          workerId: worker.id,
          runId: selected.value.runId,
          unit: selected.value.unit,
          stage: selected.value.stage,
          pool: selected.pool,
          agent: selected.agent,
          leasedAt: new Date().toISOString(),
        }
        batch.pipeline.leases[selected.value.runId] = lease
        worker.busy = true
        dispatched = true
        batch.pipeline.updatedAt = new Date().toISOString()
        batch.updatedAt = batch.pipeline.updatedAt
        await saveBatch(batch)
        console.log(
          `[pipeline] dispatch worker=${worker.id} agent=${worker.agent} pool=${selected.pool} ` +
          `unit=${selected.value.unit} stage=${selected.value.stage}`,
        )
        active.set(
          worker.id,
          runPipelineJob(
            worker,
            lease,
            selected.readySince,
            options.providerRetryBudgetSeconds,
            ensureRuntime,
            invalidateRuntime,
          ).catch((error) => failedPipelineJob(
            worker,
            lease,
            selected.readySince,
            selected.value,
            error,
          )),
        )
      }

      if (active.size === 0) {
        const disabled = runs.filter((run) => {
          const agent = pipelineAgentForRun(run)
          return agent !== undefined && batch.pipeline!.agentCaps[agent] === 0
        })
        for (const run of disabled) {
          stopped.set(
            run.runId,
            `NO_WORKER_FOR_AGENT:${pipelineAgentForRun(run) ?? "unknown"}`,
          )
        }
        const status = batchStatus(runs, stopped)
        batch.lastRunFinishedAt = new Date().toISOString()
        for (const entry of batch.runs) {
          const run = runs.find((item) => item.runId === entry.runId)!
          entry.lastObservedStage = run.stage
          entry.lastError = stopped.get(run.runId)
          entry.lastExitCode = stopped.has(run.runId) ? 2 : 0
        }
        batch.pipeline.updatedAt = batch.lastRunFinishedAt
        batch.updatedAt = batch.lastRunFinishedAt
        await saveBatch(batch)
        return {
          batch,
          status,
          exitCode: status === "COMPLETE" || status === "WAITING_HUMAN" ? 0 : 2,
        }
      }

      if (!dispatched || workers.every((worker) => worker.busy)) {
        const result = await Promise.race(active.values())
        active.delete(result.worker.id)
        result.worker.busy = false
        delete batch.pipeline.leases[result.lease.runId]
        batch.pipeline.jobs.push(result.metric)
        const state = batch.pipeline.runs[result.lease.runId]!
        if (!result.infrastructureRetry) {
          state.totalTicks += 1
          invocationTicks.set(
            result.lease.runId,
            (invocationTicks.get(result.lease.runId) ?? 0) + 1,
          )
        }

        const last = result.after.executions?.at(-1)
        const retried =
          result.after.stage === result.before.stage && last?.outcome === "RETRY"
        if (result.proofMadeProgress) {
          state.consecutiveRetries = 0
          state.retryStage = undefined
        } else if (retried) {
          state.consecutiveRetries = state.retryStage === result.after.stage
            ? state.consecutiveRetries + 1
            : 1
          state.retryStage = result.after.stage
        } else {
          state.consecutiveRetries = 0
          state.retryStage = undefined
        }
        state.readyStage = undefined
        state.readySince = undefined

        let stopReason = result.infrastructureRetry
          ? runtimeRestartAttempts > 3
            ? "SHARED_RUNTIME_RESTART_LIMIT_REACHED"
            : undefined
          : result.error
        if (stopReason === undefined && result.after.revision <= result.before.revision) {
          if (!result.infrastructureRetry) stopReason = "RUN_REVISION_DID_NOT_ADVANCE"
        }
        if (
          stopReason === undefined &&
          stageRevisionCount(result.after) >= options.maxStageRevisions
        ) stopReason = "STAGE_REVISION_LIMIT_REACHED"
        if (
          stopReason === undefined &&
          state.consecutiveRetries >= options.maxStageRetries
        ) stopReason = "STAGE_RETRY_LIMIT_REACHED"
        if (
          stopReason === undefined &&
          (invocationTicks.get(result.lease.runId) ?? 0) >= options.maxTicks &&
          !TERMINAL_STAGES.has(result.after.stage) &&
          waitingGateForStage(result.after.stage) === undefined
        ) stopReason = "MAX_TICKS_REACHED"
        if (stopReason !== undefined) stopped.set(result.lease.runId, stopReason)

        const entry = batch.runs.find((item) => item.runId === result.lease.runId)!
        entry.lastObservedStage = result.after.stage
        entry.lastError = stopReason
        entry.lastExitCode = stopReason === undefined ? 0 : 2
        batch.pipeline.updatedAt = new Date().toISOString()
        batch.updatedAt = batch.pipeline.updatedAt
        await saveBatch(batch)
        console.log(
          `[pipeline] complete worker=${result.worker.id} agent=${result.worker.agent} pool=${result.lease.pool} ` +
          `unit=${result.lease.unit} ${result.before.stage} -> ${result.after.stage} ` +
          `service=${result.metric.serviceMs}ms` +
          (result.infrastructureRetry && stopReason === undefined
            ? " shared-runtime-restart=rescheduled"
            : "") +
          (stopReason === undefined ? "" : ` stopped=${stopReason}`),
        )
      }
    }
  } finally {
    sharedRuntime?.runtime.server.close()
    await releaseController(batch)
  }
}
