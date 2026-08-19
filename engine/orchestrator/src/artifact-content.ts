import { validateTheoremObligationDocument } from "./theorem-contract.js"
import { artifactBudgetIssues } from "./artifact-limits.js"
import {
  reviewFindingAccountabilityIssues,
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
      const declaredKinds = new Set(
        (Array.isArray(document.source_documents) ? document.source_documents : [])
          .filter(isRecord)
          .map((source) => String(source.kind ?? "").toUpperCase())
          .filter((kind) => kind === "HTML" || kind === "PDF"),
      )
      const evidencedKinds = new Set<string>()
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
        const sourceDocument = (Array.isArray(document.source_documents) ? document.source_documents : [])
          .filter(isRecord)
          .find((source) => source.document_id === fragment.document_id)
        if (sourceDocument === undefined) {
          issues.push(`fragment ${index} references unknown document_id: ${String(fragment.document_id)}`)
        } else {
          if (sourceDocument.kind !== fragment.source_kind) {
            issues.push(`fragment ${index} source_kind does not match its source document`)
          }
          if (sourceDocument.sha256 !== fragment.source_sha256) {
            issues.push(`fragment ${index} source_sha256 does not match its source document`)
          }
        }
        const quoteTokens = nonEmptyString(fragment.exact_quote)
          ? fragment.exact_quote.trim().split(/\s+/).filter(Boolean) : []
        if (quoteTokens.length < 4) {
          issues.push(`fragment ${index} exact_quote is too short to be reliable evidence`)
        }
        if (isRecord(fragment.locator)) {
          if (fragment.source_kind === "HTML" && !nonEmptyString(fragment.locator.anchor) &&
            !Number.isInteger(fragment.locator.start_line)) {
            issues.push(`HTML fragment ${index} needs an anchor or start_line locator`)
          }
          if (fragment.source_kind === "PDF" && !Number.isInteger(fragment.locator.page)) {
            issues.push(`PDF fragment ${index} needs a page locator`)
          }
        }
        if (!["PDF", "HTML"].includes(String(fragment.source_kind))) {
          issues.push(`fragment ${index} has invalid source_kind; expected PDF|HTML`)
        } else {
          evidencedKinds.add(String(fragment.source_kind))
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
      for (const kind of declaredKinds) {
        if (!evidencedKinds.has(kind)) {
          issues.push(`source bundle declares an official ${kind} rendition but contains no ${kind} evidence fragment`)
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
        if (isRecord(gap) && gap.impact === "LOAD_BEARING") {
          issues.push(`source bundle has unresolved LOAD_BEARING evidence gap: ${String(gap.gap_id)}`)
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
    const claimIds = new Set<string>()
    for (const [index, claim] of canonicalClaims.entries()) {
      const id = claim.semanticId
      if (!nonEmptyString(id)) continue
      if (claimIds.has(id)) issues.push(`duplicate semanticId: ${id}`)
      else claimIds.add(id)
    }
    for (const claim of canonicalClaims) {
      const id = nonEmptyString(claim.semanticId) ? claim.semanticId : "unknown semantic claim"
      const dependencies = Array.isArray(claim.dependencyIds) ? claim.dependencyIds.filter(nonEmptyString) : []
      for (const dependencyId of dependencies) {
        if (!claimIds.has(dependencyId)) issues.push(`${id} references unknown dependencyId: ${dependencyId}`)
      }
    }
    const visitSemanticReferences = (value: unknown): void => {
      if (Array.isArray(value)) {
        for (const item of value) visitSemanticReferences(item)
        return
      }
      if (!isRecord(value)) return
      const references = Array.isArray(value.semanticClaimIds) ? value.semanticClaimIds.filter(nonEmptyString) : []
      for (const semanticId of references) {
        if (!claimIds.has(semanticId)) issues.push(`semantic surface references unknown semanticId: ${semanticId}`)
      }
      for (const child of Object.values(value)) visitSemanticReferences(child)
    }
    for (const field of ["syntaxForms", "operands", "operation", "stateEffects", "preconditions", "proofFamilies"]) {
      visitSemanticReferences(document[field])
  }
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
    issues.push(...reviewFindingAccountabilityIssues(source))
  }
  return issues
}

function validateArchitectureMarkdown(source: string): string[] {
  const issues: string[] = []
  for (const [label, pattern] of [
    ["scope", /scope|bounded/i],
    ["source facts", /source fact|evidence/i],
    ["design dependencies", /design dependenc(?:y|ies)|design choice|architecture decision/i],
    ["assumptions/open questions", /assumption|open question|ambiguit/i],
    ["Gate A", /gate\s*a/i],
  ] as const) {
    if (!pattern.test(source)) issues.push(`architecture artifact is missing ${label}`)
  }
  issues.push(...artifactBudgetIssues("ARCHITECTURE", source))
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
      return [...validateLeanNamespace(run, source), ...validateLeanModuleQuality(run, source)]
    case "THEOREM_GENERATION":
      return validateTheoremObligationDocument(parsedJson).issues
    default:
      return []
  }
}

function validateLeanModuleQuality(run: RunState, source: string): string[] {
  const issues: string[] = []
  const header = source.match(/\/-!([\s\S]*?)-\//)?.[1]
  if (header === undefined) {
    issues.push("Lean mapping lacks a module doc header (`/-! ... -/`)")
  } else {
    const required = [
      ["unit", new RegExp(`\\bUnit\\s*:\\s*${run.unit.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")}\\b`, "i")],
      ["semantic authority", /\bSemantic authority\s*:\s*\S+/i],
      ["architecture authority", /\bArchitecture authority\s*:\s*\S+/i],
      ["scope status", /\bScope status\s*:\s*(?:BOUNDED_COMPLETE|BOUNDED_PARTIAL)\b/i],
      ["supported forms", /\bSupported forms\s*:\s*\S+/i],
      ["excluded forms", /\bExcluded forms\s*:\s*\S+/i],
      ["evidence policy", /\bEvidence policy\s*:\s*\S+/i],
    ] as const
    for (const [label, pattern] of required) {
      if (!pattern.test(header)) issues.push(`Lean module header lacks ${label}`)
    }
  }
  if (/\b(?:theorem|lemma)\b[^\n]*!=/.test(source)) {
    issues.push("Lean theorem statements must use propositional `≠`, not Boolean `!=`")
  }

  const declarationPattern = /^\s*(?:private\s+)?(?:def|abbrev)\s+([A-Za-z_][A-Za-z0-9_']*)/gm
  for (const match of source.matchAll(declarationPattern)) {
    const name = match[1]
    if (name === undefined) continue
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    const references = source.match(new RegExp(`\\b${escaped}\\b`, "g"))?.length ?? 0
    if (references <= 1 && !new RegExp(`spec2lean-keep\\s*:\\s*${escaped}\\b`, "i").test(source)) {
      issues.push(
        `unused Lean declaration ${name}; remove it, use it, or add ` +
        `\`-- spec2lean-keep: ${name} — <theorem/API rationale>\``,
      )
    }
  }
  return issues
}
