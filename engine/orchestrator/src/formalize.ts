import { access } from "node:fs/promises"
import { resolve } from "node:path"

import { runLoopProcess } from "./loop-client.js"
import { REPO_ROOT } from "./repo.js"
import { createRun } from "./run-service.js"
import { saveRun } from "./run-store.js"
import { verifySourceManifest } from "./source-manifest.js"
import { transitionRun } from "./workflow.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}


const language = required("--language")
const specVersion = required("--version")
const inferredManifest = language.toLowerCase() === "ptx"
  ? `documents/sources/nvidia/ptx/${specVersion}/source-manifest.json`
  : undefined
const sourceManifest = argument("--source-manifest") ?? inferredManifest
if (!sourceManifest) {
  throw new Error("--source-manifest is required for this language")
}

try {
  await access(resolve(REPO_ROOT, sourceManifest))
} catch {
  throw new Error(`Source manifest does not exist: ${sourceManifest}`)
}
await verifySourceManifest(resolve(REPO_ROOT, sourceManifest))

const run = await createRun({
  language,
  specVersion,
  unit: required("--unit"),
  sourceManifest,
})

const started = transitionRun(run, "ARCHITECTURE", "one-command formalization start")
await saveRun(started)

console.log(JSON.stringify({
  ok: true,
  runId: started.runId,
  stage: started.stage,
  artifactRoot: started.artifactRoot,
}, null, 2))

const code = await runLoopProcess(started.runId, {
  maxTicks: Number(argument("--max-ticks") ?? "50"),
  maxStageRetries: Number(argument("--max-stage-retries") ?? "4"),
  providerRetryBudgetSeconds: Number(
    argument("--provider-retry-budget-seconds") ?? "60",
  ),
})
process.exitCode = code
