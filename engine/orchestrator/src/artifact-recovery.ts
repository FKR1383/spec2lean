import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import type { AgentResult } from "./agent-result.js"
import { artifactContractForRun } from "./artifact-contract.js"
import { verifyExpectedArtifact } from "./artifact-verify.js"
import {
  reviewDispositionCounts,
  reviewExplicitlyReady,
} from "./critic-disposition.js"
import { REPO_ROOT } from "./repo.js"
import { planForRun } from "./stage-plan.js"
import type { RunState } from "./workflow.js"

const CRITIC_STAGES = new Set([
  "ARCHITECTURE_CRITIQUE",
  "SEMANTIC_CRITIQUE",
  "LEAN_MAPPING_CRITIQUE",
  "THEOREM_STRENGTH_CRITIQUE",
  "FINAL_CRITIQUE",
])

/**
 * Recover a completed stage when OpenCode loses only the terminal text after
 * writing a deterministically valid artifact. Critic recovery is deliberately
 * one-way: only an explicit zero-BLOCKER/zero-MAJOR ready disposition can be
 * recovered. Revision routing is never inferred from prose.
 */
export async function recoverResultFromVerifiedArtifact(
  run: RunState,
): Promise<AgentResult | undefined> {
  const verification = await verifyExpectedArtifact(run)
  if (!verification.ok) return undefined
  const plan = planForRun(run)

  if (CRITIC_STAGES.has(run.stage)) {
    const path = artifactContractForRun(run).outputPath
    const review = await readFile(resolve(REPO_ROOT, path), "utf8")
    const counts = reviewDispositionCounts(review)
    if (
      counts === undefined ||
      counts.BLOCKER !== 0 ||
      counts.MAJOR !== 0 ||
      !reviewExplicitlyReady(review)
    ) return undefined
  }

  return {
    outcome: "SUCCESS",
    nextStage: plan.successStage,
    summary:
      `Recovered completion from deterministically verified stage artifact ` +
      `${verification.path}; OpenCode terminal protocol text was unavailable.`,
  }
}
