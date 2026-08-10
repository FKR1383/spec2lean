import { loadRun } from "./run-store.js"
import { semanticV2Telemetry } from "./semantic-v2-telemetry.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

const runId = argument("--run")
if (runId === undefined) throw new Error("Missing required argument: --run")
const run = await loadRun(runId)

console.log(JSON.stringify({
  runId: run.runId,
  unit: run.unit,
  stage: run.stage,
  semanticV2: semanticV2Telemetry(run),
}, null, 2))
