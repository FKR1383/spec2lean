import { loadRun } from "./run-store.js"
import { semanticV2Telemetry } from "./semantic-v2-telemetry.js"

type Metric = {
  milliseconds: number
  agentMilliseconds: number
  unmeasuredExecutions: number
  transitions: number
  executions: number
  retries: number
  proofContinuations: number
  providerRetries: number
}

export async function buildPerfReport(runId: string): Promise<Record<string, unknown>> {
  const run = await loadRun(runId)
  const metrics = new Map<string, Metric>()
  const metric = (stage: string): Metric => {
    let value = metrics.get(stage)
    if (!value) {
      value = {
        milliseconds: 0,
        agentMilliseconds: 0,
        unmeasuredExecutions: 0,
        transitions: 0,
        executions: 0,
        retries: 0,
        proofContinuations: 0,
        providerRetries: 0,
      }
      metrics.set(stage, value)
    }
    return value
  }

  let enteredAt = Date.parse(run.createdAt)
  for (const event of run.history) {
    const at = Date.parse(event.at)
    if (event.from !== null) {
      const current = metric(event.from)
      current.milliseconds += Math.max(0, at - enteredAt)
      current.transitions += 1
    }
    enteredAt = at
  }
  for (const execution of run.executions ?? []) {
    const current = metric(execution.stage)
    current.executions += 1
    const startedAt = execution.startedAt === undefined ? Number.NaN : Date.parse(execution.startedAt)
    const finishedAt = Date.parse(execution.at)
    if (Number.isFinite(startedAt) && Number.isFinite(finishedAt)) {
      current.agentMilliseconds += Math.max(0, finishedAt - startedAt)
    } else {
      current.unmeasuredExecutions += 1
    }
    if (execution.progress?.kind === "PROOF_BATCH_CONTINUATION") {
      current.proofContinuations += 1
    } else if (execution.outcome === "RETRY") current.retries += 1
    if (["PROVIDER_FAILURE", "PROVIDER_RETRY_BUDGET_EXCEEDED"]
      .includes(execution.failureClass ?? "")) current.providerRetries += 1
  }

  const stages = [...metrics.entries()].map(([stage, current]) => ({
    stage,
    seconds: Number((current.milliseconds / 1000).toFixed(1)),
    activeAgentSeconds: Number((current.agentMilliseconds / 1000).toFixed(1)),
    unmeasuredExecutions: current.unmeasuredExecutions,
    executions: current.executions,
    retries: current.retries,
    proofContinuations: current.proofContinuations,
    providerRetries: current.providerRetries,
    transitions: current.transitions,
  })).sort((left, right) => right.seconds - left.seconds)

  return {
    runId: run.runId,
    language: run.language,
    specificationVersion: run.specVersion,
    unit: run.unit,
    stage: run.stage,
    benchmark: run.benchmark?.autoApprove === true
      ? { autoApprove: true, humanApproved: false, promotable: false }
      : undefined,
    sourceAcquisition: run.sourceAcquisition,
    endToEndWallClockSeconds: Number((
      (Date.parse(run.updatedAt) - Date.parse(run.sourceAcquisition?.startedAtUtc ?? run.createdAt)) / 1000
    ).toFixed(1)),
    wallClockSeconds: Number(((Date.parse(run.updatedAt) - Date.parse(run.createdAt)) / 1000).toFixed(1)),
    agentExecutions: (run.executions ?? []).length,
    retryExecutions: (run.executions ?? []).filter(
      (execution) => execution.outcome === "RETRY" && execution.progress === undefined,
    ).length,
    proofContinuationExecutions: (run.executions ?? []).filter(
      (execution) => execution.progress?.kind === "PROOF_BATCH_CONTINUATION",
    ).length,
    revisionExecutions: (run.executions ?? []).filter((execution) => execution.outcome === "REVISE").length,
    activeAgentSeconds: Number((
      [...metrics.values()].reduce((total, stage) => total + stage.agentMilliseconds, 0) / 1000
    ).toFixed(1)),
    unmeasuredAgentExecutions: [...metrics.values()].reduce(
      (total, stage) => total + stage.unmeasuredExecutions,
      0,
    ),
    providerRetryExecutions: (run.executions ?? []).filter(
      (execution) => ["PROVIDER_FAILURE", "PROVIDER_RETRY_BUDGET_EXCEEDED"]
        .includes(execution.failureClass ?? ""),
    ).length,
    outputLengthExecutions: (run.executions ?? []).filter(
      (execution) => execution.failureClass === "OUTPUT_LENGTH_EXCEEDED",
    ).length,
    retryFailureClasses: Object.fromEntries(
      [...new Set((run.executions ?? [])
        .filter((execution) => execution.outcome === "RETRY")
        .map((execution) => execution.failureClass ?? "UNCLASSIFIED_LEGACY_RETRY"))]
        .sort()
        .map((failureClass) => [
          failureClass,
          (run.executions ?? []).filter(
            (execution) => execution.outcome === "RETRY" &&
              (execution.failureClass ?? "UNCLASSIFIED_LEGACY_RETRY") === failureClass,
          ).length,
        ]),
    ),
    semanticV2: semanticV2Telemetry(run),
    executionModels: Object.fromEntries(
      [...new Set((run.executions ?? []).map((execution) => execution.model ?? "unrecorded"))]
        .sort()
        .map((model) => [
          model,
          (run.executions ?? []).filter(
            (execution) => (execution.model ?? "unrecorded") === model,
          ).length,
        ]),
    ),
    stages,
  }
}
