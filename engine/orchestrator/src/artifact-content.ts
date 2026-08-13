import { validateTheoremObligationDocument } from "./theorem-contract.js"
import {
  reviewDispositionCounts,
  reviewExplicitlyReady,
  reviewExplicitlyRequiresRevision,
} from "./critic-disposition.js"
import { leanDeclarationNamespace, leanLanguageName } from "./lean-language.js"
import { validateArchitectureIndex } from "./provenance-catalog.js"
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
    const documentIds = new Set<string>()
    for (const [index, source] of document.source_documents.entries()) {
      if (!isRecord(source)) {
        issues.push(`source document ${index} must be an object`)
        continue
      }
      if (document.schema_version === 2) {
        if (!nonEmptyString(source.document_id)) {
          issues.push(`source document ${index} has no document_id`)
        } else if (documentIds.has(source.document_id)) {
          issues.push(`duplicate source document_id: ${source.document_id}`)
        } else documentIds.add(source.document_id)
        if (!nonEmptyString(source.publisher)) issues.push(`source document ${index} has no publisher`)
      }
      if (document.schema_version === 2 && !["PDF", "HTML"].includes(String(source.kind))) {
        issues.push(`source document ${index} has invalid kind; expected PDF|HTML`)
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
  if (document.schema_version === 2) {
    for (const field of ["bundle_id", "language", "specification_version", "unit"] as const) {
      if (!nonEmptyString(document[field])) issues.push(`source bundle v2 has no ${field}`)
    }
    if (!Array.isArray(document.fragments) || document.fragments.length === 0) {
      issues.push("source bundle v2 must contain a non-empty fragments array")
    } else {
      const fragmentIds = new Set<string>()
      for (const [index, fragment] of document.fragments.entries()) {
        if (!isRecord(fragment)) {
          issues.push(`source bundle fragment ${index} must be an object`)
          continue
        }
        if (!nonEmptyString(fragment.fragment_id)) {
          issues.push(`source bundle fragment ${index} has no fragment_id`)
        } else if (fragmentIds.has(fragment.fragment_id)) {
          issues.push(`duplicate source bundle fragment_id: ${fragment.fragment_id}`)
        } else fragmentIds.add(fragment.fragment_id)
        if (!nonEmptyString(fragment.document_id)) issues.push(`fragment ${index} has no document_id`)
        if (!["PDF", "HTML"].includes(String(fragment.source_kind))) {
          issues.push(`fragment ${index} has invalid source_kind; expected PDF|HTML`)
        }
        if (!nonEmptyString(fragment.exact_quote)) issues.push(`fragment ${index} has no exact_quote`)
        if (!nonEmptyString(fragment.source_sha256) || !/^[a-f0-9]{64}$/i.test(fragment.source_sha256)) {
          issues.push(`fragment ${index} has no valid source_sha256`)
        }
        if (!nonEmptyString(fragment.reason_for_inclusion)) {
          issues.push(`fragment ${index} has no reason_for_inclusion`)
        }
        if (!isRecord(fragment.locator) || Object.keys(fragment.locator).length === 0) {
          issues.push(`fragment ${index} has no non-empty locator`)
        }
      }
    }
    if (!Array.isArray(document.evidence_gaps)) {
      issues.push("source bundle v2 must contain an evidence_gaps array")
    } else {
      for (const [index, gap] of document.evidence_gaps.entries()) {
        if (!isRecord(gap) || !nonEmptyString(gap.gap_id) ||
          !["LOAD_BEARING", "NON_LOAD_BEARING"].includes(String(gap.impact))) {
          issues.push(`evidence gap ${index} must have gap_id and LOAD_BEARING|NON_LOAD_BEARING impact`)
        }
      }
    }
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
  const canonicalClaims = Array.isArray(document.semanticClaims)
    ? document.semanticClaims.filter(isRecord)
    : []
  const claims = canonicalClaims.length > 0 ? canonicalClaims : semanticClaims(document)
  if (claims.length === 0) issues.push("semantic artifact contains no semantic claims")
  for (const [index, claim] of claims.entries()) {
    const id = claim.claim_id ?? claim.semanticId ?? claim.dependency_id ?? claim.id
    if (!nonEmptyString(id)) issues.push(`semantic claim ${index} has no stable ID`)
    if (!CLASSIFICATIONS.has(String(claim.classification))) {
      issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has invalid classification`)
    }
    if (!nonEmptyString(claim.statement)) {
      issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has no statement`)
    }
    const evidenceIds = [
      ...evidenceIdsForClaim(claim),
      ...(Array.isArray(claim.evidenceIds) ? claim.evidenceIds.filter(nonEmptyString) : []),
    ]
    if (claim.classification === "SOURCE_FACT" && evidenceIds.length === 0) {
      issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} SOURCE_FACT has no evidence IDs`)
    }
    if (canonicalClaims.length > 0) {
      if (!Array.isArray(claim.dependencyIds) || !claim.dependencyIds.every(nonEmptyString)) {
        issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has invalid dependencyIds`)
      }
      if (claim.classification === "DERIVED_INTERPRETATION" &&
        Array.isArray(claim.dependencyIds) && claim.dependencyIds.length === 0) {
        issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} DERIVED_INTERPRETATION has no dependencies`)
      }
      if (!Array.isArray(claim.humanApprovalDependencies) ||
        !claim.humanApprovalDependencies.every(nonEmptyString)) {
        issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has invalid humanApprovalDependencies`)
      } else if (claim.classification === "ASSUMPTION" && claim.humanApprovalDependencies.length === 0) {
        issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} ASSUMPTION has no human approval dependency`)
      }
      if (typeof claim.stateAffecting !== "boolean") {
        issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has no stateAffecting boolean`)
      }
      if (!isRecord(claim.lifecycle) ||
        !["ACTIVE", "SUPERSEDED", "INVALIDATED"].includes(String(claim.lifecycle.status))) {
        issues.push(`${nonEmptyString(id) ? id : `semantic claim ${index}`} has invalid lifecycle`)
      }
    }
  }
  if (document.schemaVersion === 2) {
    if (document.documentType !== "spec2lean_full_semantics") {
      issues.push("full semantics v2 has invalid documentType")
    }
    if (canonicalClaims.length === 0) {
      issues.push("full semantics v2 must use the canonical semanticClaims array")
    }
    for (const field of ["syntaxForms", "operands", "stateEffects", "preconditions", "proofFamilies"] as const) {
      if (!Array.isArray(document[field])) issues.push(`full semantics v2 has no ${field} array`)
    }
    if (!isRecord(document.operation)) issues.push("full semantics v2 has no operation object")
  }
  return issues
}

function validateCriticMarkdown(source: string): string[] {
  const issues: string[] = []
  const counts = reviewDispositionCounts(source)
  if (counts === undefined) {
    issues.push("critic artifact must report numeric BLOCKER, MAJOR, MINOR, and NOTE counts")
  }
  const ready = reviewExplicitlyReady(source)
  const requiresRevision = reviewExplicitlyRequiresRevision(source)
  if (!/PRE_GATE_REVISION_REQUIRED\s*:\s*(?:true|false)\b/i.test(source)) {
    issues.push("critic artifact must end with PRE_GATE_REVISION_REQUIRED: true|false")
  }
  if (counts !== undefined) {
    const hasBlockingFinding = counts.BLOCKER > 0 || counts.MAJOR > 0
    if (hasBlockingFinding === ready || hasBlockingFinding !== requiresRevision) {
      issues.push(
        "critic revision marker must be true exactly when BLOCKER or MAJOR count is non-zero",
      )
    }
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
  issues.push(...validateArchitectureIndex(source))
  return issues
}

function validateLeanNamespace(run: RunState, source: string): string[] {
  const languageName = leanLanguageName(run)
  const expected = leanDeclarationNamespace(run)
  const dotted = new RegExp(`\\bnamespace\\s+Spec2Lean\\.${languageName}\\.${run.leanModuleName}\\b`)
  const nested = new RegExp(
    `\\bnamespace\\s+Spec2Lean\\s+namespace\\s+${languageName}\\s+namespace\\s+${run.leanModuleName}\\b`,
    "s",
  )
  return dotted.test(source) || nested.test(source)
    ? []
    : [`Lean mapping must use namespace ${expected}`]
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
