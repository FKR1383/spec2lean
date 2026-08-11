import { access, readFile, stat } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun } from "./artifact-contract.js"
import { validateArtifactContent } from "./artifact-content.js"
import { prohibitedLeanTokens, verifyLeanFile } from "./lean-local.js"
import { latestObligationPath, proofTargets } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { theoremStrengthReviewAuditIssues } from "./theorem-contract.js"
import type { RunState } from "./workflow.js"

export type ArtifactVerification = {
  ok: boolean
  path: string
  issues: string[]
}

export async function verifyExpectedArtifact(run: RunState): Promise<ArtifactVerification> {
  const path = artifactContractForRun(run).outputPath
  const absolute = resolve(REPO_ROOT, path)
  const issues: string[] = []

  try {
    await access(absolute)
  } catch {
    return { ok: false, path, issues: ["expected artifact does not exist"] }
  }

  const fileStat = await stat(absolute)
  if (fileStat.size === 0) issues.push("artifact is empty")
  const source = await readFile(absolute, "utf8")
  let parsedJson: unknown

  if (path.endsWith(".json")) {
    try {
      parsedJson = JSON.parse(source)
    } catch (error) {
      issues.push(`invalid JSON: ${String(error)}`)
    }
  }

  issues.push(...validateArtifactContent(run, source, parsedJson))

  if (run.stage === "THEOREM_STRENGTH_CRITIQUE") {
    try {
      const obligationPath = await latestObligationPath(run)
      const targets = await proofTargets(run)
      issues.push(...theoremStrengthReviewAuditIssues(source, obligationPath, targets))
    } catch (error) {
      issues.push(
        `could not validate theorem-strength review against its obligation contract: ${String(error)}`,
      )
    }
  }

  if (path.endsWith(".lean")) {
    const banned = await prohibitedLeanTokens(path)
    if (banned.length > 0) {
      issues.push(`prohibited Lean tokens in code: ${banned.join(", ")}`)
    }

    const check = await verifyLeanFile(path)
    if (!check.success) {
      issues.push(`Lean check failed: ${check.output.slice(-6000)}`)
    }
  }

  return { ok: issues.length === 0, path, issues }
}
