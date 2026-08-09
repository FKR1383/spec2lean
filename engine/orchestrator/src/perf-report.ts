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
  transitions: number
  executions: number
  retries: number
}

const metrics = new Map<string, Metric>()

function metric(stage: string): Metric {
  let value = metrics.get(stage)
  if (!value) {
    value = {
      milliseconds: 0,
      transitions: 0,
      executions: 0,
      retries: 0,
    }
    metrics.set(stage, value)
  }
  return value
}

let enteredAt = Date.parse(run.createdAt)

for (const event of run.history) {
  const at = Date.parse(event.at)

  if (event.from !== null) {
    const m = metric(event.from)
    m.milliseconds += Math.max(0, at - enteredAt)
    m.transitions += 1
  }

  enteredAt = at
}

for (const execution of run.executions ?? []) {
  const m = metric(execution.stage)
  m.executions += 1
  if (execution.outcome === "RETRY") m.retries += 1
}

const stages = [...metrics.entries()]
  .map(([stage, m]) => ({
    stage,
    seconds: Number((m.milliseconds / 1000).toFixed(1)),
    executions: m.executions,
    retries: m.retries,
    transitions: m.transitions,
  }))
  .sort((a, b) => b.seconds - a.seconds)

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
  stages,
}, null, 2))
