import { loadRun } from "./run-store.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

const run = await loadRun(required("--run"))

type Metric = {
  milliseconds: number
  agentMilliseconds: number
  unmeasuredExecutions: number
  transitions: number
  executions: number
  retries: number
  providerRetries: number
}

const metrics = new Map<string, Metric>()

function metric(stage: string): Metric {
  let value = metrics.get(stage)
  if (!value) {
    value = {
      milliseconds: 0,
      agentMilliseconds: 0,
      unmeasuredExecutions: 0,
      transitions: 0,
      executions: 0,
      retries: 0,
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
    const value = metric(event.from)
    value.milliseconds += Math.max(0, at - enteredAt)
    value.transitions += 1
  }
  enteredAt = at
}

for (const execution of run.executions ?? []) {
  const value = metric(execution.stage)
  value.executions += 1
  const startedAt = execution.startedAt === undefined
    ? Number.NaN
    : Date.parse(execution.startedAt)
  const finishedAt = Date.parse(execution.at)
  if (Number.isFinite(startedAt) && Number.isFinite(finishedAt)) {
    value.agentMilliseconds += Math.max(0, finishedAt - startedAt)
  } else {
    value.unmeasuredExecutions += 1
  }
  if (execution.outcome === "RETRY") value.retries += 1
  if (execution.failureClass === "PROVIDER_RETRY_BUDGET_EXCEEDED") {
    value.providerRetries += 1
  }
}

const stages = [...metrics.entries()]
  .map(([stage, value]) => ({
    stage,
    seconds: Number((value.milliseconds / 1000).toFixed(1)),
    activeAgentSeconds: Number((value.agentMilliseconds / 1000).toFixed(1)),
    unmeasuredExecutions: value.unmeasuredExecutions,
    executions: value.executions,
    retries: value.retries,
    providerRetries: value.providerRetries,
    transitions: value.transitions,
  }))
  .sort((left, right) => right.seconds - left.seconds)

console.log(JSON.stringify({
  runId: run.runId,
  unit: run.unit,
  stage: run.stage,
  wallClockSeconds: Number(
    ((Date.parse(run.updatedAt) - Date.parse(run.createdAt)) / 1000).toFixed(1),
  ),
  agentExecutions: (run.executions ?? []).length,
  retryExecutions: (run.executions ?? [])
    .filter((execution) => execution.outcome === "RETRY")
    .length,
  activeAgentSeconds: Number((
    [...metrics.values()].reduce(
      (total, stage) => total + stage.agentMilliseconds,
      0,
    ) / 1000
  ).toFixed(1)),
  unmeasuredAgentExecutions: [...metrics.values()].reduce(
    (total, stage) => total + stage.unmeasuredExecutions,
    0,
  ),
  providerRetryExecutions: (run.executions ?? [])
    .filter((execution) => execution.failureClass === "PROVIDER_RETRY_BUDGET_EXCEEDED")
    .length,
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
}, null, 2))
