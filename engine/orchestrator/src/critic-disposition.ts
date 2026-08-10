import type { AgentResult } from "./agent-result.js"
import type { FormalizationStage } from "./workflow.js"

export type FindingSeverity = "BLOCKER" | "MAJOR" | "MINOR" | "NOTE"

export function reviewFindingSeverities(review: string): FindingSeverity[] {
  return [...review.matchAll(/\*{0,2}Severity:\*{0,2}\s*(BLOCKER|MAJOR|MINOR|NOTE)\b/gi)]
    .map((match) => match[1]!.toUpperCase() as FindingSeverity)
}

/**
 * Enforce the critic prompt's severity/disposition contract without making a
 * semantic judgement of our own. The critic still classifies every finding;
 * the orchestrator only prevents an internally inconsistent MINOR/NOTE-only
 * review from causing another model revision cycle.
 */
export function normalizeCriticResultFromReview(
  result: AgentResult,
  review: string,
  successStage: FormalizationStage,
): AgentResult {
  if (result.outcome !== "REVISE") return result

  const severities = reviewFindingSeverities(review)
  if (
    severities.length === 0 ||
    severities.some((severity) => severity === "BLOCKER" || severity === "MAJOR")
  ) {
    return result
  }

  return {
    outcome: "SUCCESS",
    nextStage: successStage,
    summary:
      `Critic disposition normalized deterministically: the review contains ` +
      `${severities.length} explicit finding(s), all MINOR/NOTE and therefore ` +
      `non-blocking under the review policy. Original summary: ${result.summary}`,
  }
}
