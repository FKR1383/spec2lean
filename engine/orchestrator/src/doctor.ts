import { access } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun } from "./artifact-contract.js"
import { prepareLeanPackage } from "./lean-package.js"
import { prohibitedLeanTokens, verifyLeanFile } from "./lean-local.js"
import { proofArtifactPath, proofTargetSummary } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { loadRun } from "./run-store.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

const runId = argument("--run")
if (!runId) throw new Error("Usage: doctor.ts --run <run-id>")
const run = await loadRun(runId)

const report: Record<string, unknown> = {
  ok: true,
  runId,
  stage: run.stage,
  revision: run.revision,
  gates: run.gates,
  activeExecution: run.activeExecution ?? null,
  expectedArtifact: (() => {
    try { return artifactContractForRun(run).outputPath } catch { return null }
  })(),
  lastExecution: run.executions?.at(-1) ?? null,
}

if (run.stage === "PROOF_GENERATION" || run.stage === "FINAL_CRITIQUE" || run.stage === "WAITING_FINAL_APPROVAL") {
  try {
    report.leanPackage = await prepareLeanPackage(run)
  } catch (error) {
    report.ok = false
    report.leanPackageError = String(error)
  }

  const proofPath = proofArtifactPath(run)
  let exists = true
  try { await access(resolve(REPO_ROOT, proofPath)) } catch { exists = false }
  report.proofArtifact = { path: proofPath, exists }
  report.proofProgress = await proofTargetSummary(run)

  if (exists) {
    report.proofBannedTokens = await prohibitedLeanTokens(proofPath)
    const check = await verifyLeanFile(proofPath, 90_000)
    report.proofLean = {
      success: check.success,
      exitCode: check.exitCode,
      timedOut: check.timedOut,
      tail: check.output.slice(-5000),
    }
  }
}

console.log(JSON.stringify(report, null, 2))
