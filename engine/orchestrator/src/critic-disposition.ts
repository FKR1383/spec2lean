import type { AgentResult } from "./agent-result.js"
import type { FormalizationStage } from "./workflow.js"

export type FindingSeverity = "BLOCKER" | "MAJOR" | "MINOR" | "NOTE"

export type ReviewDispositionCounts = Record<FindingSeverity, number>

function explicitSeverityCount(review: string, severity: FindingSeverity): number | undefined {
  const patterns = [
    new RegExp(`\\b${severity}(?:\\s+count)?\\s*[:=]\\s*(\\d+)\\b`, "i"),
    new RegExp(`\\|\\s*${severity}\\s*\\|\\s*(\\d+)\\s*\\|`, "i"),
    new RegExp(`\\b(\\d+)\\s+${severity}\\b`, "i"),
  ]
  for (const pattern of patterns) {
    const match = review.match(pattern)
    if (match?.[1] !== undefined) return Number(match[1])
  }
  return undefined
}

export function reviewDispositionCounts(review: string): ReviewDispositionCounts | undefined {
  const entries = (["BLOCKER", "MAJOR", "MINOR", "NOTE"] as const).map(
    (severity) => [severity, explicitSeverityCount(review, severity)] as const,
  )
  if (entries.some(([, count]) => count === undefined)) return undefined
  return Object.fromEntries(entries) as ReviewDispositionCounts
}

export function reviewExplicitlyReady(review: string): boolean {
  const marker = review.match(/PRE_GATE_REVISION_REQUIRED\s*:\s*(true|false)\b/i)
  if (marker?.[1] !== undefined) return marker[1].toLowerCase() === "false"
  return !/\bnot\s+ready\b/i.test(review) &&
    /\bready\s+for\s+(?:human\s+)?(?:gate|approval|review)\b/i.test(review)
}

export function reviewExplicitlyRequiresRevision(review: string): boolean {
  return /PRE_GATE_REVISION_REQUIRED\s*:\s*true\b/i.test(review)
}

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
  const counts = reviewDispositionCounts(review)
  if (
    (severities.length === 0 && counts === undefined) ||
    severities.some((severity) => severity === "BLOCKER" || severity === "MAJOR") ||
    (counts !== undefined && (counts.BLOCKER > 0 || counts.MAJOR > 0))
  ) {
    return result
  }

  return {
    outcome: "SUCCESS",
    nextStage: successStage,
    summary:
      `Critic disposition normalized deterministically: the review contains ` +
      `${severities.length || ((counts?.MINOR ?? 0) + (counts?.NOTE ?? 0))} explicit finding(s), all MINOR/NOTE and therefore ` +
      `non-blocking under the review policy. Original summary: ${result.summary}`,
  }
}
