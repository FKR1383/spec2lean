import { reviewDispositionCounts } from "./critic-disposition.js"
import { parseArchitectureIndex } from "./provenance-catalog.js"

export const ARCHITECTURE_QUESTION_DISPOSITIONS = [
  "GENUINE_HUMAN_REVIEW",
  "REMOVE_OR_RECLASSIFY",
] as const

export type ArchitectureQuestionDisposition =
  (typeof ARCHITECTURE_QUESTION_DISPOSITIONS)[number]

export type ArchitectureQuestionTriageEntry = {
  semanticId: string
  disposition: ArchitectureQuestionDisposition
  rationale: string
}

export type ArchitectureQuestionTriage = {
  schemaVersion: 1
  entries: ArchitectureQuestionTriageEntry[]
}

const TRIAGE_PATTERN =
  /<!--\s*SPEC2LEAN_GATE_A_OQ_TRIAGE\s*([\s\S]*?)\s*-->/gm

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

export function architectureStateAffectingOpenQuestions(
  architecture: string,
): Array<{ semanticId: string; statement: string }> {
  const index = parseArchitectureIndex(architecture)
  if (index === undefined) return []
  return index.entries.flatMap((entry) =>
    entry.classification === "OPEN_QUESTION" &&
    entry.stateAffecting === true &&
    entry.status === "OPEN"
      ? [{ semanticId: entry.semanticId, statement: entry.statement }]
      : [],
  )
}

export function parseArchitectureQuestionTriage(
  review: string,
): ArchitectureQuestionTriage | undefined {
  const matches = [...review.matchAll(TRIAGE_PATTERN)]
  if (matches.length !== 1 || matches[0]?.[1] === undefined) return undefined
  try {
    return JSON.parse(matches[0][1]) as ArchitectureQuestionTriage
  } catch {
    return undefined
  }
}

export function architectureQuestionTriageRequiresRevision(
  review: string,
): boolean {
  return parseArchitectureQuestionTriage(review)?.entries.some(
    (entry) => entry.disposition === "REMOVE_OR_RECLASSIFY",
  ) ?? false
}

export function validateArchitectureQuestionTriage(
  architecture: string,
  review: string,
): string[] {
  const issues: string[] = []
  const matches = [...review.matchAll(TRIAGE_PATTERN)]
  if (matches.length !== 1) {
    return [
      `architecture critique must contain exactly one SPEC2LEAN_GATE_A_OQ_TRIAGE block; found ${matches.length}`,
    ]
  }
  const triage = parseArchitectureQuestionTriage(review)
  if (triage === undefined) {
    return ["architecture critique has invalid SPEC2LEAN_GATE_A_OQ_TRIAGE JSON"]
  }
  if (triage.schemaVersion !== 1 || !Array.isArray(triage.entries)) {
    return ["architecture question triage must have schemaVersion=1 and an entries array"]
  }

  const expected = new Map(
    architectureStateAffectingOpenQuestions(architecture).map((entry) => [
      entry.semanticId,
      entry.statement,
    ]),
  )
  const seen = new Set<string>()
  let revisionRequired = false
  for (const [position, entry] of triage.entries.entries()) {
    const path = `architecture question triage entry ${position}`
    if (typeof entry !== "object" || entry === null) {
      issues.push(`${path} must be an object`)
      continue
    }
    if (!nonEmptyString(entry.semanticId)) {
      issues.push(`${path} has no semanticId`)
      continue
    }
    if (seen.has(entry.semanticId)) {
      issues.push(`duplicate architecture question triage semanticId: ${entry.semanticId}`)
    }
    seen.add(entry.semanticId)
    if (!expected.has(entry.semanticId)) {
      issues.push(`architecture question triage references unknown or non-state-affecting open entry: ${entry.semanticId}`)
    }
    if (!ARCHITECTURE_QUESTION_DISPOSITIONS.includes(entry.disposition as never)) {
      issues.push(`${entry.semanticId} has invalid architecture question disposition`)
    }
    if (!nonEmptyString(entry.rationale)) {
      issues.push(`${entry.semanticId} has no triage rationale`)
    }
    if (entry.disposition === "REMOVE_OR_RECLASSIFY") revisionRequired = true
  }
  for (const semanticId of expected.keys()) {
    if (!seen.has(semanticId)) {
      issues.push(`architecture question triage is missing state-affecting open entry: ${semanticId}`)
    }
  }

  if (revisionRequired) {
    const counts = reviewDispositionCounts(review)
    if (counts === undefined || (counts.BLOCKER === 0 && counts.MAJOR === 0)) {
      issues.push(
        "REMOVE_OR_RECLASSIFY requires at least one BLOCKER/MAJOR finding and pre-gate revision",
      )
    }
  }
  return issues
}
