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

export function reviewFindingAccountabilityIssues(review: string): string[] {
  const counts = reviewDispositionCounts(review)
  if (counts === undefined) return []
  const severities = reviewFindingSeverities(review)
  const tagged = (severity: FindingSeverity): number =>
    severities.filter((item) => item === severity).length
  const issues: string[] = []
  for (const severity of ["BLOCKER", "MAJOR", "MINOR", "NOTE"] as const) {
    const actual = tagged(severity)
    if (actual !== counts[severity]) {
      issues.push(
        `${severity} count is ${counts[severity]} but ${actual} explicit ` +
        `Severity: ${severity} finding entries were provided`,
      )
    }
  }
  return issues
}

/**
 * Enforce the critic prompt's severity/disposition contract without making a
 * semantic judgement of our own. The structured review is the critic's
 * durable decision: blocking findings route upstream, non-blocking findings
 * proceed, and a RETRY paired with a complete review is conservatively routed
 * upstream rather than spinning the critic on an artifact/result conflict.
 */
export function normalizeCriticResultFromReview(
  result: AgentResult,
  review: string,
  successStage: FormalizationStage,
  defaultRevisionStage?: FormalizationStage,
): AgentResult {
  const severities = reviewFindingSeverities(review)
  const counts = reviewDispositionCounts(review)
  if (counts === undefined) return result

  const blocking =
    severities.some((severity) => severity === "BLOCKER" || severity === "MAJOR") ||
    counts.BLOCKER > 0 ||
    counts.MAJOR > 0 ||
    reviewExplicitlyRequiresRevision(review)

  if (blocking) {
    if (result.outcome === "BLOCKED") return result
    const nextStage = result.outcome === "REVISE"
      ? result.nextStage
      : defaultRevisionStage
    if (nextStage === undefined) return result
    return {
      outcome: "REVISE",
      nextStage,
      summary:
        `Critic disposition normalized deterministically: the review records ` +
        `${counts.BLOCKER} BLOCKER and ${counts.MAJOR} MAJOR finding(s), so the ` +
        `producer must revise the artifact. Original summary: ${result.summary}`,
    }
  }

  if (!reviewExplicitlyReady(review)) return result

  if (result.outcome === "SUCCESS") return result
  if (result.outcome === "BLOCKED") return result

  if (result.outcome === "RETRY") {
    if (defaultRevisionStage === undefined) return result
    return {
      outcome: "REVISE",
      nextStage: defaultRevisionStage,
      summary:
        `Critic artifact/result conflict resolved conservatively: the complete ` +
        `review is ready but the terminal result requested RETRY. The producer ` +
        `must receive one bounded revision rather than repeating the critic. ` +
        `Original summary: ${result.summary}`,
    }
  }

  if (result.outcome !== "REVISE") {
    return result
  }

  return {
    outcome: "SUCCESS",
    nextStage: successStage,
    summary:
      `Critic disposition normalized deterministically: the review contains ` +
      `${severities.length || (counts.MINOR + counts.NOTE)} explicit finding(s), all MINOR/NOTE and therefore ` +
      `non-blocking under the review policy. Original summary: ${result.summary}`,
  }
}
