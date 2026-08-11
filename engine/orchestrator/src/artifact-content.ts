import { validateTheoremObligationDocument } from "./theorem-contract.js"
import type { RunState } from "./workflow.js"

type UnknownRecord = Record<string, unknown>

const CLASSIFICATIONS = new Set([
  "SOURCE_FACT",
  "DERIVED_INTERPRETATION",
  "DESIGN_DEPENDENCY",
  "ASSUMPTION",
  "OPEN_QUESTION",
])

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function sourceEvidenceIds(document: UnknownRecord): Set<string> {
  const ids = new Set<string>()
  const visit = (value: unknown, key = ""): void => {
    if (Array.isArray(value)) {
      for (const item of value) visit(item, key)
      return
    }
    if (!isRecord(value)) {
      if (
        nonEmptyString(value) &&
        ["fragment_id", "fact_id", "evidence_id"].includes(key)
      ) ids.add(value)
      return
    }
    for (const [childKey, child] of Object.entries(value)) {
      if (childKey === "source_documents") continue
      visit(child, childKey)
    }
  }
  visit(document)
  return ids
}

function validateSourceBundle(document: unknown): string[] {
  if (!isRecord(document)) return ["source bundle must be a JSON object"]
  const issues: string[] = []
  if (![1, 2].includes(document.schema_version as number)) {
    issues.push("source bundle schema_version must be 1 or 2")
  }
  if (!Array.isArray(document.source_documents) || document.source_documents.length === 0) {
    issues.push("source bundle must identify at least one source document")
  } else {
    for (const [index, source] of document.source_documents.entries()) {
      if (!isRecord(source)) {
        issues.push(`source document ${index} must be an object`)
        continue
      }
      if (!nonEmptyString(source.local_path)) issues.push(`source document ${index} has no local_path`)
      if (!nonEmptyString(source.sha256) || !/^[a-f0-9]{64}$/i.test(source.sha256)) {
        issues.push(`source document ${index} has no valid sha256`)
      }
    }
  }
  if (sourceEvidenceIds(document).size === 0) {
    issues.push("source bundle contains no stable fragment/fact/evidence identifiers")
  }
  return issues
}

function semanticClaims(document: UnknownRecord): UnknownRecord[] {
  const direct = Array.isArray(document.semantic_claims)
    ? document.semantic_claims.filter(isRecord)
    : []
  if (direct.length > 0) return direct
  return [
    "source_facts",
    "derived_interpretations",
    "design_dependencies",
    "human_approved_assumptions",
    "open_questions",
  ].flatMap((key) => Array.isArray(document[key]) ? document[key].filter(isRecord) : [])
}

function evidenceIdsForClaim(claim: UnknownRecord): string[] {
  for (const key of ["evidence_fragment_ids", "evidence_ids", "source_evidence_ids"]) {
    const value = claim[key]
    if (Array.isArray(value)) return value.filter(nonEmptyString)
  }
  return []
}

function validateLegacySemantics(document: unknown): string[] {
  if (!isRecord(document)) return ["semantic artifact must be a JSON object"]
  const issues: string[] = []
  const claims = semanticClaims(document)
  if (claims.length === 0) issues.push("semantic artifact contains no semantic claims")
  for (const [index, claim] of claims.entries()) {
    const id = claim.claim_id ?? claim.semanticId ?? claim.id
    if (!nonEmptyString(id)) issues.push(`semantic claim ${index} has no stable ID`)
    if (!CLASSIFICATIONS.has(String(claim.classification))) {
      issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has invalid classification`)
    }
    if (!nonEmptyString(claim.statement)) {
      issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has no statement`)
    }
    if (claim.classification === "SOURCE_FACT" && evidenceIdsForClaim(claim).length === 0) {
      issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} SOURCE_FACT has no evidence IDs`)
    }
  }
  return issues
}

function validateCriticMarkdown(source: string): string[] {
  const issues: string[] = []
  const upper = source.toUpperCase()
  if (!upper.includes("BLOCKER") || !upper.includes("MAJOR")) {
    issues.push("critic artifact must explicitly report BLOCKER and MAJOR dispositions")
  }
  if (!/(READY|READINESS|NOT READY|REVISION)/i.test(source)) {
    issues.push("critic artifact must state readiness or required revision")
  }
  return issues
}

function validateArchitectureMarkdown(source: string): string[] {
  const issues: string[] = []
  for (const [label, pattern] of [
    ["scope", /scope|bounded/i],
    ["source facts", /source fact|evidence/i],
    ["design dependencies", /design dependency|design choice|architecture decision/i],
    ["assumptions/open questions", /assumption|open question|ambiguit/i],
    ["Gate A", /gate\s*a/i],
  ] as const) {
    if (!pattern.test(source)) issues.push(`architecture artifact is missing ${label}`)
  }
  return issues
}

function validateLeanNamespace(run: RunState, source: string): string[] {
  const dotted = new RegExp(`\\bnamespace\\s+Spec2Lean\\.PTX\\.${run.leanModuleName}\\b`)
  const nested = new RegExp(
    `\\bnamespace\\s+Spec2Lean\\s+namespace\\s+PTX\\s+namespace\\s+${run.leanModuleName}\\b`,
    "s",
  )
  return dotted.test(source) || nested.test(source)
    ? []
    : [`Lean mapping must use namespace Spec2Lean.PTX.${run.leanModuleName}`]
}

export function validateArtifactContent(
  run: RunState,
  source: string,
  parsedJson?: unknown,
): string[] {
  switch (run.stage) {
    case "ARCHITECTURE":
      return validateArchitectureMarkdown(source)
    case "ARCHITECTURE_CRITIQUE":
    case "SEMANTIC_CRITIQUE":
    case "LEAN_MAPPING_CRITIQUE":
    case "THEOREM_STRENGTH_CRITIQUE":
    case "FINAL_CRITIQUE":
      return validateCriticMarkdown(source)
    case "SOURCE_CURATION":
      return validateSourceBundle(parsedJson)
    case "SEMANTIC_EXTRACTION":
      return run.semanticV2?.mode === "DELTA_FAST_PATH"
        ? []
        : validateLegacySemantics(parsedJson)
    case "LEAN_FORMALIZATION":
      return validateLeanNamespace(run, source)
    case "THEOREM_GENERATION":
      return validateTheoremObligationDocument(parsedJson).issues
    default:
      return []
  }
}
