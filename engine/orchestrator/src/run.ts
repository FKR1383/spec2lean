import { createRun } from "./run-service.js"
import { loadRun, saveRun } from "./run-store.js"
import { transitionRun, type RunState, type WorkflowMode } from "./workflow.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

async function init(): Promise<void> {
  const mode = (argument("--mode") ?? "formalization") as WorkflowMode
  const run = await createRun({
    mode,
    language: required("--language"),
    specVersion: required("--version"),
    unit: required("--unit"),
    sourceManifest: required("--source-manifest"),
  })
  console.log(JSON.stringify(run, null, 2))
}

async function show(): Promise<void> {
  console.log(JSON.stringify(await loadRun(required("--run")), null, 2))
}

async function advance(): Promise<void> {
  const runId = required("--run")
  const run = await loadRun(runId)
  const next = transitionRun(
    run,
    required("--to") as RunState["stage"],
    argument("--reason") ?? "manual orchestrator transition",
  )
  await saveRun(next)
  console.log(JSON.stringify(next, null, 2))
}

switch (process.argv[2]) {
  case "init":
    await init()
    break
  case "show":
    await show()
    break
  case "advance":
    await advance()
    break
  default:
    throw new Error([
      "Usage:",
      "  run.ts init --language ptx --version 9.3 --unit mov.b32 --source-manifest <path>",
      "  run.ts show --run <run-id>",
      "  run.ts advance --run <run-id> --to ARCHITECTURE",
    ].join("\n"))
}
