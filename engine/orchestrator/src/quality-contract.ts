import type { CorrectnessKind } from "./theorem-contract.js"
import { parseMachineJsonBlock } from "./machine-block.js"

type UnknownRecord = Record<string, unknown>

export const COMPLETENESS_DIMENSIONS = [
  "SYNTAX",
  "OPERANDS",
  "TYPES",
  "OPERATION_BRANCHES",
  "EDGE_CASES",
  "GUARDS",
  "STATE_EFFECTS",
  "ERRORS",
  "VERSION_APPLICABILITY",
] as const

export type CompletenessDimension = typeof COMPLETENESS_DIMENSIONS[number]

export const EXTENDED_CORRECTNESS_KINDS = [
  "ALGORITHM_FIDELITY",
  "RESULT_RANGE",
  "EDGE_CASE_BEHAVIOR",
  "TYPE_DOMAIN",
] as const

export type ExtendedCorrectnessKind =
  | CorrectnessKind
  | typeof EXTENDED_CORRECTNESS_KINDS[number]

export const FULL_INSTRUCTION_REQUIRED_PROOF_KINDS = [
  "OPERATION_FIDELITY",
  "ALGORITHM_FIDELITY",
  "RESULT_RANGE",
  "GUARD_BEHAVIOR",
  "STATE_UPDATE",
  "FRAME_PROPERTY",
  "EXECUTION_CORRESPONDENCE",
] as const

export type ProofRequirementDisposition =
  | "LOCAL"
  | "INHERITED_FROM_SHARED_ENVIRONMENT"
  | "NOT_APPLICABLE"

function proofRequirementDisposition(requirement: UnknownRecord): ProofRequirementDisposition | undefined {
  const value = requirement.disposition ?? "LOCAL"
  return ["LOCAL", "INHERITED_FROM_SHARED_ENVIRONMENT", "NOT_APPLICABLE"].includes(String(value))
    ? value as ProofRequirementDisposition
    : undefined
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function nonEmpty(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter(nonEmpty) : []
}

function machineBlock(source: string, name: string): UnknownRecord | undefined {
  return parseMachineJsonBlock(source, name).value
}

export function architectureCompletenessContract(source: string): UnknownRecord | undefined {
  return machineBlock(source, "SPEC2LEAN_COMPLETENESS_CONTRACT")
}

function exactDimensionRecords(
  value: unknown,
  path: string,
  issues: string[],
): Map<CompletenessDimension, UnknownRecord> {
  const result = new Map<CompletenessDimension, UnknownRecord>()
  if (!Array.isArray(value)) {
    issues.push(`${path} must be an array covering every completeness dimension`)
    return result
  }
  for (const [index, item] of value.entries()) {
    if (!isRecord(item) || !COMPLETENESS_DIMENSIONS.includes(item.dimension as never)) {
      issues.push(`${path}[${index}] has an invalid dimension`)
      continue
    }
    const dimension = item.dimension as CompletenessDimension
    if (result.has(dimension)) issues.push(`${path} duplicates dimension ${dimension}`)
    else result.set(dimension, item)
  }
  for (const dimension of COMPLETENESS_DIMENSIONS) {
    if (!result.has(dimension)) issues.push(`${path} is missing dimension ${dimension}`)
  }
  return result
}

export function architectureCompletenessIssues(source: string): string[] {
  const issues: string[] = []
  const parsed = parseMachineJsonBlock(source, "SPEC2LEAN_COMPLETENESS_CONTRACT")
  if (parsed.status !== "OK" || parsed.value === undefined) return [parsed.issue!]
  const contract = parsed.value
  if (contract.schemaVersion !== 1) issues.push("architecture completeness schemaVersion must be 1")
  if (!['FULL_INSTRUCTION', 'PARTIAL_EXPLICIT'].includes(String(contract.scopeStatus))) {
    issues.push("architecture completeness scopeStatus must be FULL_INSTRUCTION or PARTIAL_EXPLICIT")
  }
  const dimensions = exactDimensionRecords(contract.dimensions, "architecture completeness dimensions", issues)
  for (const [dimension, item] of dimensions) {
    if (!['COVERED', 'NOT_APPLICABLE', 'EXCLUDED_BY_ENCODED_PRECONDITION'].includes(String(item.status))) {
      issues.push(`architecture dimension ${dimension} has an invalid status`)
    }
    if (strings(item.semanticIds).length === 0 && item.status === 'COVERED') {
      issues.push(`architecture dimension ${dimension} is COVERED without semanticIds`)
    }
    if (!nonEmpty(item.rationale)) issues.push(`architecture dimension ${dimension} lacks rationale`)
    if (item.status === 'EXCLUDED_BY_ENCODED_PRECONDITION' && strings(item.encodedBy).length === 0) {
      issues.push(`architecture dimension ${dimension} exclusion has no encodedBy precondition ID`)
    }
    if (contract.scopeStatus === 'FULL_INSTRUCTION' && item.status === 'EXCLUDED_BY_ENCODED_PRECONDITION') {
      issues.push(`FULL_INSTRUCTION architecture may not exclude ${dimension}`)
    }
  }
  if (!isRecord(contract.languageCore) ||
    !['REUSED_APPROVED', 'BOOTSTRAP_CANDIDATE'].includes(String(contract.languageCore.status))) {
    issues.push("architecture completeness contract lacks a valid languageCore status")
  } else if (contract.languageCore.status === 'REUSED_APPROVED') {
    if (!nonEmpty(contract.languageCore.path) || !/^[a-f0-9]{64}$/.test(String(contract.languageCore.sha256))) {
      issues.push("REUSED_APPROVED language core requires a path and SHA-256")
    }
  } else if (!nonEmpty(contract.languageCore.candidateCoreId) ||
    !nonEmpty(contract.languageCore.scopeStatement) ||
    strings(contract.languageCore.proposedSemanticIds).length === 0) {
    issues.push("BOOTSTRAP_CANDIDATE architecture requires candidateCoreId, scopeStatement, and proposedSemanticIds")
  }
  return issues
}

export function sourceBundleCompletenessIssues(document: unknown): string[] {
  if (!isRecord(document) || document.schema_version !== 3) {
    return ["new source bundles must use schema_version 3 with a completeness coverage_matrix"]
  }
  const issues: string[] = []
  const documents = new Map(
    (Array.isArray(document.source_documents) ? document.source_documents : [])
      .filter(isRecord)
      .flatMap((item) => nonEmpty(item.document_id) ? [[item.document_id, item] as const] : []),
  )
  const fragmentRecords = (Array.isArray(document.fragments) ? document.fragments : []).filter(isRecord)
  const fragments = new Set(fragmentRecords.flatMap((item) =>
    nonEmpty(item.fragment_id) ? [item.fragment_id] : []
  ))
  for (const [index, fragment] of fragmentRecords.entries()) {
    const sourceDocument = nonEmpty(fragment.document_id) ? documents.get(fragment.document_id) : undefined
    if (sourceDocument === undefined) {
      issues.push(`source fragment ${index} references an unknown document_id`)
      continue
    }
    if (fragment.source_kind !== sourceDocument.kind) {
      issues.push(`source fragment ${String(fragment.fragment_id)} kind does not match its document`)
    }
    if (fragment.source_sha256 !== sourceDocument.sha256) {
      issues.push(`source fragment ${String(fragment.fragment_id)} SHA-256 does not match its document`)
    }
    if (!isRecord(fragment.locator)) {
      issues.push(`source fragment ${String(fragment.fragment_id)} lacks a locator`)
    } else if (fragment.source_kind === "PDF" && !Number.isInteger(fragment.locator.page)) {
      issues.push(`PDF fragment ${String(fragment.fragment_id)} lacks an exact page`)
    } else if (fragment.source_kind === "HTML" &&
      !nonEmpty(fragment.locator.anchor) &&
      !(Number.isInteger(fragment.locator.start_line) && Number.isInteger(fragment.locator.end_line))) {
      issues.push(`HTML fragment ${String(fragment.fragment_id)} lacks an anchor or exact line range`)
    }
  }
  const gaps = new Map(
    (Array.isArray(document.evidence_gaps) ? document.evidence_gaps : [])
      .filter(isRecord)
      .flatMap((item) => nonEmpty(item.gap_id) ? [[item.gap_id, item] as const] : []),
  )
  const dimensions = exactDimensionRecords(document.coverage_matrix, "source coverage_matrix", issues)
  for (const [dimension, item] of dimensions) {
    if (!['COVERED', 'NOT_APPLICABLE', 'GAP'].includes(String(item.status))) {
      issues.push(`source coverage ${dimension} has an invalid status`)
    }
    if (!nonEmpty(item.rationale)) issues.push(`source coverage ${dimension} lacks rationale`)
    const fragmentIds = strings(item.fragment_ids)
    const gapIds = strings(item.gap_ids)
    if (item.status === 'COVERED' && fragmentIds.length === 0) {
      issues.push(`source coverage ${dimension} is COVERED without a fragment`)
    }
    for (const id of fragmentIds) {
      if (!fragments.has(id)) issues.push(`source coverage ${dimension} references unknown fragment ${id}`)
    }
    for (const id of gapIds) {
      if (!gaps.has(id)) issues.push(`source coverage ${dimension} references unknown gap ${id}`)
    }
    if (item.status === 'GAP' && gapIds.length === 0) {
      issues.push(`source coverage ${dimension} is GAP without a gap ID`)
    }
    if (["OPERANDS", "TYPES", "EDGE_CASES"].includes(dimension) && item.status === "GAP") {
      issues.push(`source evidence closure is mandatory for ${dimension}; GAP cannot advance`)
    }
    if (item.status === 'NOT_APPLICABLE' && (fragmentIds.length > 0 || gapIds.length > 0)) {
      issues.push(`source coverage ${dimension} is NOT_APPLICABLE but cites fragments or gaps`)
    }
  }
  return issues
}

function coverageStatuses(value: unknown, path: string, issues: string[]): Map<CompletenessDimension, string> {
  return new Map(
    [...exactDimensionRecords(value, path, issues)]
      .map(([dimension, item]) => [dimension, String(item.status)]),
  )
}

/** Deterministic architecture -> source -> semantics completeness correspondence. */
export function artifactChainCompletenessIssues(
  architectureSource: string,
  sourceBundle: unknown,
  semantics: unknown,
): string[] {
  const issues: string[] = []
  const architecture = machineBlock(architectureSource, "SPEC2LEAN_COMPLETENESS_CONTRACT")
  if (architecture === undefined || !isRecord(sourceBundle) || !isRecord(semantics)) {
    return ["cannot construct architecture/source/semantics completeness correspondence"]
  }
  if (architecture.scopeStatus !== semantics.scopeStatus) {
    issues.push(`architecture scope ${String(architecture.scopeStatus)} does not match semantics ${String(semantics.scopeStatus)}`)
  }
  const architectureStatuses = coverageStatuses(
    architecture.dimensions,
    "architecture completeness dimensions",
    issues,
  )
  const sourceStatuses = coverageStatuses(
    sourceBundle.coverage_matrix,
    "source coverage_matrix",
    issues,
  )
  const semanticStatuses = coverageStatuses(
    semantics.coverage,
    "semantic coverage",
    issues,
  )
  const gaps = new Map(
    (Array.isArray(sourceBundle.evidence_gaps) ? sourceBundle.evidence_gaps : [])
      .filter(isRecord)
      .flatMap((gap) => nonEmpty(gap.gap_id) ? [[gap.gap_id, gap] as const] : []),
  )
  const sourceCoverage = new Map(
    (Array.isArray(sourceBundle.coverage_matrix) ? sourceBundle.coverage_matrix : [])
      .filter(isRecord)
      .flatMap((item) => COMPLETENESS_DIMENSIONS.includes(item.dimension as never)
        ? [[item.dimension as CompletenessDimension, item] as const]
        : []),
  )
  for (const dimension of COMPLETENESS_DIMENSIONS) {
    const architectureStatus = architectureStatuses.get(dimension)
    const sourceStatus = sourceStatuses.get(dimension)
    const semanticStatus = semanticStatuses.get(dimension)
    if (architectureStatus !== semanticStatus) {
      issues.push(`${dimension} coverage diverges between architecture (${architectureStatus}) and semantics (${semanticStatus})`)
    }
    if (sourceStatus === "COVERED" && semanticStatus !== "COVERED") {
      issues.push(`${dimension} is source-covered but not semantically covered`)
    }
    // Source coverage is deliberately unit-local: NOT_APPLICABLE means that
    // the instruction's own section has no separate clause for this
    // dimension. Integrated semantics may still cover it through the
    // hash-bound shared language core or a grounded derivation (for example,
    // PTX predication). Architecture/semantics equality above remains the
    // authority for that integrated decision; claim grounding is checked
    // separately. Therefore NOT_APPLICABLE is not a negative fact that can
    // veto inherited semantic coverage.
    if (sourceStatus === "GAP") {
      const coverage = sourceCoverage.get(dimension)
      const loadBearing = strings(coverage?.gap_ids).some((id) => gaps.get(id)?.impact === "LOAD_BEARING")
      if (loadBearing) issues.push(`${dimension} has a load-bearing evidence gap`)
      if (semanticStatus !== "EXCLUDED_BY_ENCODED_PRECONDITION") {
        issues.push(`${dimension} evidence gap is not represented by an encoded semantic exclusion`)
      }
    }
  }
  return [...new Set(issues)]
}

export function semanticCompletenessIssues(document: unknown): string[] {
  if (!isRecord(document) || document.schemaVersion !== 3 ||
    document.documentType !== "spec2lean_full_semantics") {
    return ["new full semantics must use schemaVersion 3 and the completeness contract"]
  }
  const issues: string[] = []
  if (!['FULL_INSTRUCTION', 'PARTIAL_EXPLICIT'].includes(String(document.scopeStatus))) {
    issues.push("semantic scopeStatus must be FULL_INSTRUCTION or PARTIAL_EXPLICIT")
  }
  const claimIds = new Set(
    (Array.isArray(document.semanticClaims) ? document.semanticClaims : [])
      .filter(isRecord)
      .flatMap((claim) => nonEmpty(claim.semanticId) ? [claim.semanticId] : []),
  )
  const preconditionIds = new Set(
    (Array.isArray(document.preconditions) ? document.preconditions : [])
      .filter(isRecord)
      .flatMap((precondition) => {
        const id = precondition.preconditionId ?? precondition.semanticId ?? precondition.id
        return nonEmpty(id) ? [id] : []
      }),
  )
  const dimensions = exactDimensionRecords(document.coverage, "semantic coverage", issues)
  for (const [dimension, item] of dimensions) {
    if (!['COVERED', 'NOT_APPLICABLE', 'EXCLUDED_BY_ENCODED_PRECONDITION'].includes(String(item.status))) {
      issues.push(`semantic coverage ${dimension} has an invalid status`)
    }
    if (!nonEmpty(item.rationale)) issues.push(`semantic coverage ${dimension} lacks rationale`)
    const semanticIds = strings(item.semanticClaimIds)
    if (item.status === 'COVERED' && semanticIds.length === 0) {
      issues.push(`semantic coverage ${dimension} is COVERED without semanticClaimIds`)
    }
    for (const id of semanticIds) {
      if (!claimIds.has(id)) issues.push(`semantic coverage ${dimension} references unknown claim ${id}`)
    }
    const encoded = strings(item.encodedPreconditionIds)
    if (item.status === 'EXCLUDED_BY_ENCODED_PRECONDITION' && encoded.length === 0) {
      issues.push(`semantic coverage ${dimension} exclusion lacks encodedPreconditionIds`)
    }
    for (const id of encoded) {
      if (!preconditionIds.has(id)) issues.push(`semantic coverage ${dimension} references unknown precondition ${id}`)
    }
    if (document.scopeStatus === 'FULL_INSTRUCTION' && item.status === 'EXCLUDED_BY_ENCODED_PRECONDITION') {
      issues.push(`FULL_INSTRUCTION semantics may not exclude ${dimension}`)
    }
  }
  const status = (dimension: CompletenessDimension): string | undefined =>
    dimensions.get(dimension)?.status as string | undefined
  if (status("SYNTAX") === "COVERED" &&
    (!Array.isArray(document.syntaxForms) || document.syntaxForms.length === 0)) {
    issues.push("semantic SYNTAX coverage has no syntaxForms")
  }
  const operands = Array.isArray(document.operands) ? document.operands.filter(isRecord) : []
  if (status("OPERANDS") === "COVERED" && operands.length === 0) {
    issues.push("semantic OPERANDS coverage has no operands")
  }
  const operandPositions = new Set<number>()
  for (const [index, operand] of operands.entries()) {
    if (!Array.isArray(operand.legalForms) || strings(operand.legalForms).length === 0) {
      issues.push(`semantic operand ${index} has no legalForms`)
    }
    if (!Array.isArray(operand.typeDomains) || strings(operand.typeDomains).length === 0) {
      issues.push(`semantic operand ${index} has no typeDomains`)
    }
    if (!Number.isInteger(operand.position) || operandPositions.has(Number(operand.position))) {
      issues.push(`semantic operand ${index} has an invalid or duplicate position`)
    } else operandPositions.add(Number(operand.position))
  }
  const operation = isRecord(document.operation) ? document.operation : undefined
  if (operation === undefined || strings(operation.inputDomains).length === 0 ||
    !nonEmpty(operation.outputDomain)) {
    issues.push("semantic operation lacks exact inputDomains or outputDomain")
  }
  if (status("OPERATION_BRANCHES") === "COVERED" &&
    (!Array.isArray(operation?.branches) || operation.branches.length === 0)) {
    issues.push("semantic OPERATION_BRANCHES coverage has no explicit operation branches")
  }
  if (status("EDGE_CASES") === "COVERED" &&
    (!Array.isArray(operation?.edgeCases) || operation.edgeCases.length === 0)) {
    issues.push("semantic EDGE_CASES coverage has no explicit edgeCases")
  }
  if (status("STATE_EFFECTS") === "COVERED" &&
    (!Array.isArray(document.stateEffects) || document.stateEffects.length === 0)) {
    issues.push("semantic STATE_EFFECTS coverage has no stateEffects")
  }
  if (!isRecord(document.languageCore) ||
    !['REUSED_APPROVED', 'BOOTSTRAP_CANDIDATE'].includes(String(document.languageCore.status))) {
    issues.push("semantics lacks a languageCore binding")
  } else if (document.languageCore.status === "REUSED_APPROVED" &&
    (!nonEmpty(document.languageCore.path) ||
      !/^[a-f0-9]{64}$/.test(String(document.languageCore.sha256)))) {
    issues.push("REUSED_APPROVED semantics requires the exact language-core path and SHA-256")
  } else if (document.languageCore.status === "BOOTSTRAP_CANDIDATE") {
    if (!nonEmpty(document.languageCore.candidateCoreId) ||
      !nonEmpty(document.languageCore.scopeStatement) ||
      strings(document.languageCore.eligibilityRequirements).length === 0 ||
      strings(document.languageCore.reusableSemanticClaimIds).length === 0 ||
      !Array.isArray(document.languageCore.proposedModelRoles) ||
      document.languageCore.proposedModelRoles.length === 0) {
      issues.push("BOOTSTRAP_CANDIDATE must define core ID, scope, eligibility, reusable semantic IDs, and model roles")
    }
    for (const semanticId of strings(document.languageCore.reusableSemanticClaimIds)) {
      if (!claimIds.has(semanticId)) issues.push(`language-core candidate references unknown claim ${semanticId}`)
    }
    for (const [index, role] of (Array.isArray(document.languageCore.proposedModelRoles)
      ? document.languageCore.proposedModelRoles.filter(isRecord)
      : []).entries()) {
      if (!nonEmpty(role.role) || strings(role.semanticClaimIds).length === 0) {
        issues.push(`language-core candidate model role ${index} is incomplete`)
      }
      for (const semanticId of strings(role.semanticClaimIds)) {
        if (!claimIds.has(semanticId)) issues.push(`language-core candidate role references unknown claim ${semanticId}`)
      }
    }
  }
  if (!Array.isArray(document.proofRequirements) || document.proofRequirements.length === 0) {
    issues.push("semantics must define non-empty proofRequirements")
  } else {
    const seen = new Set<string>()
    for (const [index, requirement] of document.proofRequirements.entries()) {
      if (!isRecord(requirement) || !nonEmpty(requirement.requirementId)) {
        issues.push(`proofRequirements[${index}] lacks requirementId`)
        continue
      }
      if (seen.has(requirement.requirementId)) issues.push(`duplicate proof requirement ${requirement.requirementId}`)
      seen.add(requirement.requirementId)
      if (!nonEmpty(requirement.correctnessKind)) issues.push(`${requirement.requirementId} lacks correctnessKind`)
      if (strings(requirement.semanticClaimIds).length === 0) issues.push(`${requirement.requirementId} lacks semanticClaimIds`)
      if (!nonEmpty(requirement.rationale)) issues.push(`${requirement.requirementId} lacks rationale`)
      const disposition = proofRequirementDisposition(requirement)
      if (disposition === undefined) issues.push(`${requirement.requirementId} has invalid disposition`)
      if (disposition === "INHERITED_FROM_SHARED_ENVIRONMENT" && !nonEmpty(requirement.coreDischargeId)) {
        issues.push(`${requirement.requirementId} inherited requirement lacks coreDischargeId`)
      }
      if (disposition !== "INHERITED_FROM_SHARED_ENVIRONMENT" && requirement.coreDischargeId !== undefined) {
        issues.push(`${requirement.requirementId} may use coreDischargeId only when inherited`)
      }
      if (disposition !== undefined && disposition !== "LOCAL" &&
        ["OPERATION_FIDELITY", "EXECUTION_CORRESPONDENCE"].includes(String(requirement.correctnessKind))) {
        issues.push(`${requirement.requirementId} must keep unit-specific ${String(requirement.correctnessKind)} LOCAL`)
      }
    }
    const kinds = new Set(document.proofRequirements.filter(isRecord).flatMap((item) =>
      nonEmpty(item.correctnessKind) ? [item.correctnessKind] : []
    ))
    for (const kind of FULL_INSTRUCTION_REQUIRED_PROOF_KINDS) {
      if (!kinds.has(kind)) issues.push(`semantics lacks mandatory proof requirement ${kind}`)
    }
  }
  return issues
}

/** Completeness fields carried by a fast-path delta before materialization. */
export function semanticDeltaCompletenessIssues(document: unknown): string[] {
  if (!isRecord(document)) return ["semantic delta must be an object"]
  const referencedIds = new Set<string>()
  for (const value of [document.coverage, document.proofRequirements]) {
    if (!Array.isArray(value)) continue
    for (const item of value.filter(isRecord)) {
      for (const id of strings(item.semanticClaimIds)) referencedIds.add(id)
    }
  }
  const projected = {
    schemaVersion: 3,
    documentType: "spec2lean_full_semantics",
    scopeStatus: document.scopeStatus,
    coverage: document.coverage,
    proofRequirements: document.proofRequirements,
    languageCore: document.languageCore,
    semanticClaims: [
      ...(Array.isArray(document.claims) ? document.claims : []),
      ...(Array.isArray(document.refinements) ? document.refinements : []),
      ...[...referencedIds].map((semanticId) => ({ semanticId })),
    ],
    preconditions: document.preconditions,
    syntaxForms: document.syntaxForms,
    operands: document.operands,
    operation: document.operation,
    stateEffects: document.stateEffects,
  }
  return semanticCompletenessIssues(projected)
}

export type LeanModelContract = {
  scopeStatus: string
  languageCoreStatus: string
  languageCoreImport: string
  languageCoreCandidate?: UnknownRecord
  domainBindings: UnknownRecord[]
  encodedExclusions: UnknownRecord[]
  operationBranchBindings: UnknownRecord[]
  edgeCaseBindings: UnknownRecord[]
  specificationDefinitions: string[]
  executableDefinitions: string[]
  relationalDefinitions: string[]
}

export function parseLeanModelContract(source: string): LeanModelContract | undefined {
  const value = machineBlock(source, "SPEC2LEAN_LEAN_MODEL_CONTRACT")
  if (value === undefined || value.schemaVersion !== 1) return undefined
  return {
    scopeStatus: String(value.scopeStatus ?? ""),
    languageCoreStatus: String(value.languageCoreStatus ?? ""),
    languageCoreImport: String(value.languageCoreImport ?? ""),
    languageCoreCandidate: isRecord(value.languageCoreCandidate) ? value.languageCoreCandidate : undefined,
    domainBindings: Array.isArray(value.domainBindings) ? value.domainBindings.filter(isRecord) : [],
    encodedExclusions: Array.isArray(value.encodedExclusions) ? value.encodedExclusions.filter(isRecord) : [],
    operationBranchBindings: Array.isArray(value.operationBranchBindings) ? value.operationBranchBindings.filter(isRecord) : [],
    edgeCaseBindings: Array.isArray(value.edgeCaseBindings) ? value.edgeCaseBindings.filter(isRecord) : [],
    specificationDefinitions: strings(value.specificationDefinitions),
    executableDefinitions: strings(value.executableDefinitions),
    relationalDefinitions: strings(value.relationalDefinitions),
  }
}

function declarationExists(source: string, name: string): boolean {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  return new RegExp(`\\b(?:def|abbrev|inductive|structure|class)\\s+${escaped}\\b`).test(source)
}

function declarationBlock(source: string, name: string): string {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const start = new RegExp(`^\\s*(?:def|abbrev|inductive|structure)\\s+${escaped}\\b`, "m").exec(source)
  if (start?.index === undefined) return ""
  const remainder = source.slice(start.index)
  const next = /^\s*(?:def|abbrev|inductive|structure|theorem|lemma|namespace|end)\s+/gm
  next.lastIndex = remainder.indexOf("\n") + 1
  const end = next.exec(remainder)?.index ?? remainder.length
  return remainder.slice(0, end)
}

export function leanModelContractIssues(
  source: string,
  semantics?: unknown,
  expectedLanguageCoreImport?: string,
): string[] {
  const contract = parseLeanModelContract(source)
  if (contract === undefined) return ["Lean mapping lacks SPEC2LEAN_LEAN_MODEL_CONTRACT"]
  const issues: string[] = []
  if (!['FULL_INSTRUCTION', 'PARTIAL_EXPLICIT'].includes(contract.scopeStatus)) {
    issues.push("Lean model contract has invalid scopeStatus")
  }
  if (!['REUSED_APPROVED', 'BOOTSTRAP_CANDIDATE'].includes(contract.languageCoreStatus)) {
    issues.push("Lean model contract has invalid languageCoreStatus")
  }
  if (contract.languageCoreStatus === 'REUSED_APPROVED') {
    if (!nonEmpty(contract.languageCoreImport)) {
      issues.push("REUSED_APPROVED Lean model contract lacks languageCoreImport")
    } else if (!new RegExp(`^\\s*import\\s+${contract.languageCoreImport.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*$`, "m").test(source)) {
      issues.push(`Lean mapping does not import declared language core ${contract.languageCoreImport}`)
    }
    if (expectedLanguageCoreImport !== undefined && contract.languageCoreImport !== expectedLanguageCoreImport) {
      issues.push(`Lean mapping imports ${contract.languageCoreImport}, expected hash-bound core ${expectedLanguageCoreImport}`)
    }
  } else if (contract.languageCoreStatus === 'BOOTSTRAP_CANDIDATE') {
    const candidate = contract.languageCoreCandidate
    const reusableDeclarations = strings(candidate?.reusableDeclarations)
    const roleBindings = Array.isArray(candidate?.modelRoleBindings)
      ? candidate.modelRoleBindings.filter(isRecord)
      : []
    if (!isRecord(candidate) || !nonEmpty(candidate.candidateCoreId) ||
      reusableDeclarations.length === 0 || roleBindings.length === 0) {
      issues.push("BOOTSTRAP_CANDIDATE Lean contract lacks candidateCoreId, reusableDeclarations, or modelRoleBindings")
    }
    for (const name of reusableDeclarations) {
      if (!declarationExists(source, name)) issues.push(`language-core candidate names missing Lean declaration ${name}`)
    }
    for (const [index, binding] of roleBindings.entries()) {
      if (!nonEmpty(binding.role) || strings(binding.leanSymbols).length === 0) {
        issues.push(`language-core candidate Lean role binding ${index} is incomplete`)
      }
      for (const name of strings(binding.leanSymbols)) {
        if (!declarationExists(source, name)) issues.push(`language-core candidate role names missing Lean declaration ${name}`)
      }
    }
  }
  if (contract.domainBindings.length === 0) issues.push("Lean model contract has no domainBindings")
  for (const [index, binding] of contract.domainBindings.entries()) {
    const leanType = binding.leanType
    if (!nonEmpty(binding.semanticDomainId) || !nonEmpty(leanType) || !nonEmpty(binding.representation)) {
      issues.push(`Lean domain binding ${index} lacks semanticDomainId, leanType, or representation`)
      continue
    }
    if (binding.providedByLanguageCore === true) {
      if (contract.languageCoreStatus !== 'REUSED_APPROVED') {
        issues.push(`Lean domain binding ${leanType} claims an unavailable language core`)
      }
    } else if (!declarationExists(source, leanType)) {
      issues.push(`Lean domain binding ${leanType} names no local declaration`)
    }
    if (binding.representation === 'FIXED_WIDTH') {
      if (!Number.isInteger(binding.widthBits) || Number(binding.widthBits) < 1) {
        issues.push(`fixed-width Lean domain ${leanType} lacks a positive widthBits`)
      }
      const declaration = binding.providedByLanguageCore === true ? "" : declarationBlock(source, leanType)
      if (/\b(?:Int|Nat)\b/.test(declaration) && !/BitVec|Fin|Subtype|UInt/.test(declaration)) {
        if (!nonEmpty(binding.invariantDeclaration) || !declarationExists(source, binding.invariantDeclaration)) {
          issues.push(`fixed-width Lean domain ${leanType} is represented by unbounded Int/Nat without a checked invariant declaration`)
        }
      }
    }
  }
  for (const name of [
    ...contract.specificationDefinitions,
    ...contract.executableDefinitions,
    ...contract.relationalDefinitions,
  ]) {
    if (!declarationExists(source, name)) issues.push(`Lean model contract names missing definition ${name}`)
  }
  if (contract.executableDefinitions.length === 0) issues.push("Lean model contract has no executableDefinitions")
  if (contract.relationalDefinitions.length === 0) issues.push("Lean model contract has no relationalDefinitions")
  if (contract.specificationDefinitions.length === 0) issues.push("Lean model contract has no independent specificationDefinitions")
  for (const [index, exclusion] of contract.encodedExclusions.entries()) {
    if (!nonEmpty(exclusion.semanticDimension) || !nonEmpty(exclusion.preconditionDeclaration)) {
      issues.push(`Lean encoded exclusion ${index} lacks semanticDimension or preconditionDeclaration`)
    } else if (!declarationExists(source, exclusion.preconditionDeclaration)) {
      issues.push(`Lean encoded exclusion references missing precondition ${exclusion.preconditionDeclaration}`)
    } else {
      const escaped = exclusion.preconditionDeclaration.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      const withoutContract = source
        .replace(/<!--\s*SPEC2LEAN_LEAN_MODEL_CONTRACT[\s\S]*?-->/gi, "")
        .replace(/\/\-\s*SPEC2LEAN_LEAN_MODEL_CONTRACT[\s\S]*?\-\//gi, "")
      const uses = withoutContract.match(new RegExp(`\\b${escaped}\\b`, "g"))?.length ?? 0
      if (uses < 2) {
        issues.push(`encoded exclusion precondition ${exclusion.preconditionDeclaration} is declared but does not guard executable code`)
      }
    }
  }
  const validateBindings = (
    label: string,
    expectedIds: string[],
    bindings: UnknownRecord[],
    idField: string,
  ): void => {
    const counts = new Map<string, number>()
    for (const [index, binding] of bindings.entries()) {
      const id = binding[idField]
      const symbols = strings(binding.leanSymbols)
      if (!nonEmpty(id) || symbols.length === 0) {
        issues.push(`Lean ${label} binding ${index} lacks ${idField} or leanSymbols`)
        continue
      }
      counts.set(id, (counts.get(id) ?? 0) + 1)
      for (const symbol of symbols) {
        if (!declarationExists(source, symbol)) issues.push(`Lean ${label} binding ${id} names missing symbol ${symbol}`)
      }
    }
    for (const id of expectedIds) {
      if ((counts.get(id) ?? 0) !== 1) issues.push(`semantic ${label} ${id} must have exactly one Lean binding`)
    }
    for (const id of counts.keys()) {
      if (!expectedIds.includes(id)) issues.push(`Lean ${label} binding references unknown semantic ID ${id}`)
    }
  }
  if (isRecord(semantics) && isRecord(semantics.operation)) {
    const operationBranches = (Array.isArray(semantics.operation.branches) ? semantics.operation.branches : [])
      .filter(isRecord).flatMap((item) => nonEmpty(item.branchId) ? [item.branchId] : [])
    const edgeCases = (Array.isArray(semantics.operation.edgeCases) ? semantics.operation.edgeCases : [])
      .filter(isRecord).flatMap((item) => nonEmpty(item.caseId) ? [item.caseId] : [])
    validateBindings("operation branch", operationBranches, contract.operationBranchBindings, "semanticBranchId")
    validateBindings("edge case", edgeCases, contract.edgeCaseBindings, "semanticCaseId")
  }
  if (isRecord(semantics) && semantics.scopeStatus !== contract.scopeStatus) {
    issues.push(`Lean scopeStatus ${contract.scopeStatus} does not match semantics ${String(semantics.scopeStatus)}`)
  }
  if (isRecord(semantics) && isRecord(semantics.languageCore) &&
    semantics.languageCore.status !== contract.languageCoreStatus) {
    issues.push(`Lean languageCoreStatus ${contract.languageCoreStatus} does not match semantics ${String(semantics.languageCore.status)}`)
  }
  if (contract.languageCoreStatus === "BOOTSTRAP_CANDIDATE" &&
    isRecord(semantics) && isRecord(semantics.languageCore) &&
    contract.languageCoreCandidate?.candidateCoreId !== semantics.languageCore.candidateCoreId) {
    issues.push("Lean language-core candidate ID does not match semantics")
  }
  if (isRecord(semantics) && Array.isArray(semantics.coverage)) {
    const requiredExclusions = semantics.coverage.filter(isRecord).filter((item) =>
      item.status === 'EXCLUDED_BY_ENCODED_PRECONDITION'
    )
    for (const item of requiredExclusions) {
      if (!contract.encodedExclusions.some((entry) => entry.semanticDimension === item.dimension)) {
        issues.push(`Lean model contract does not encode semantic exclusion ${String(item.dimension)}`)
      }
    }
    const sourceWithoutContract = source
      .replace(/<!--\s*SPEC2LEAN_LEAN_MODEL_CONTRACT[\s\S]*?-->/gi, "")
      .replace(/\/\-\s*SPEC2LEAN_LEAN_MODEL_CONTRACT[\s\S]*?\-\//gi, "")
    const referencedSemanticIds = new Set(
      [...sourceWithoutContract.matchAll(/^\s*--\s*spec2lean:\s*(.+)$/gmi)]
        .flatMap((match) => (match[1] ?? "").split(",").map((id) => id.trim()).filter(Boolean)),
    )
    for (const item of semantics.coverage.filter(isRecord)) {
      if (item.status !== "COVERED") continue
      for (const semanticId of strings(item.semanticClaimIds)) {
        if (!referencedSemanticIds.has(semanticId)) {
          issues.push(`covered semantic claim ${semanticId} is not bound to any Lean declaration comment`)
        }
      }
    }
  }
  return issues
}

export function requiredProofKinds(semantics: unknown): Set<string> {
  if (!isRecord(semantics) || !Array.isArray(semantics.proofRequirements)) return new Set()
  return new Set(semantics.proofRequirements.filter(isRecord).flatMap((item) =>
    proofRequirementDisposition(item) === "LOCAL" && nonEmpty(item.correctnessKind)
      ? [item.correctnessKind]
      : []
  ))
}

export function sharedProofDischargeIssues(
  semantics: unknown,
  core: { proofDischarges?: Array<{
    dischargeId: string
    correctnessKind: string
    semanticIds: string[]
    theoremDeclarations: string[]
  }> },
): string[] {
  if (!isRecord(semantics) || !Array.isArray(semantics.proofRequirements)) return []
  const discharges = new Map((core.proofDischarges ?? []).map((item) => [item.dischargeId, item]))
  const issues: string[] = []
  const semanticClaims = new Map<string, UnknownRecord>(
    (Array.isArray(semantics.claims)
      ? semantics.claims
      : Array.isArray(semantics.semanticClaims)
        ? semantics.semanticClaims
        : [])
      .filter(isRecord)
      .flatMap((claim) => nonEmpty(claim.semanticId) ? [[claim.semanticId, claim] as const] : []),
  )
  for (const requirement of semantics.proofRequirements.filter(isRecord)) {
    if (proofRequirementDisposition(requirement) !== "INHERITED_FROM_SHARED_ENVIRONMENT") continue
    const id = String(requirement.requirementId ?? "UNKNOWN")
    const discharge = nonEmpty(requirement.coreDischargeId)
      ? discharges.get(requirement.coreDischargeId)
      : undefined
    if (discharge === undefined) {
      issues.push(`${id} references an unknown approved core proof discharge`)
      continue
    }
    if (discharge.correctnessKind !== requirement.correctnessKind) {
      issues.push(`${id} correctnessKind does not match core discharge ${discharge.dischargeId}`)
    }
    const dischargedIds = new Set(discharge.semanticIds)
    for (const semanticId of strings(requirement.semanticClaimIds)) {
      if (!dischargedIds.has(semanticId)) {
        issues.push(`${id} semantic claim ${semanticId} is not discharged by ${discharge.dischargeId}`)
      }
      const claim = semanticClaims.get(semanticId)
      if (claim === undefined || !isRecord(claim.origin) || claim.origin.kind !== "SHARED") {
        issues.push(`${id} inherited semantic claim ${semanticId} is not materialized from the approved shared environment`)
      }
    }
    if (discharge.theoremDeclarations.length === 0) {
      issues.push(`${id} core discharge ${discharge.dischargeId} has no theorem declaration`)
    }
  }
  return issues
}

export function theoremSemanticCoverageIssues(
  obligations: unknown,
  semantics: unknown,
  leanSource: string,
): string[] {
  if (!isRecord(obligations) || !Array.isArray(obligations.theorem_obligations)) {
    return ["theorem artifact has no theorem_obligations"]
  }
  const issues: string[] = []
  const presentKinds = new Set<string>()
  const leanContract = parseLeanModelContract(leanSource)
  const allRequirements = new Map(
    (isRecord(semantics) && Array.isArray(semantics.proofRequirements)
      ? semantics.proofRequirements
      : [])
      .filter(isRecord)
      .flatMap((item) => nonEmpty(item.requirementId)
        ? [[item.requirementId, item] as const]
        : []),
  )
  const requirements = new Map([...allRequirements].filter(([, requirement]) =>
    proofRequirementDisposition(requirement) === "LOCAL"
  ))
  const requirementCoverage = new Map<string, number>()
  for (const [index, item] of obligations.theorem_obligations.entries()) {
    if (!isRecord(item)) continue
    const id = nonEmpty(item.obligation_id) ? item.obligation_id : `obligation ${index}`
    if (nonEmpty(item.correctness_kind)) presentKinds.add(item.correctness_kind)
    const proofRequirementIds = strings(item.proof_requirement_ids)
    if (proofRequirementIds.length !== 1) {
      issues.push(`${id} must bind exactly one proof_requirement_id so each required property has an independent theorem`)
    }
    for (const requirementId of proofRequirementIds) {
      const requirement = allRequirements.get(requirementId)
      if (requirement === undefined) {
        issues.push(`${id} references unknown proof requirement ${requirementId}`)
        continue
      }
      if (proofRequirementDisposition(requirement) !== "LOCAL") {
        issues.push(`${id} must not regenerate non-local proof requirement ${requirementId}`)
        continue
      }
      requirementCoverage.set(requirementId, (requirementCoverage.get(requirementId) ?? 0) + 1)
      if (requirement.correctnessKind !== item.correctness_kind) {
        issues.push(`${id} correctness kind does not match proof requirement ${requirementId}`)
      }
      const obligationClaims = new Set(strings(item.semantic_claim_ids))
      for (const semanticId of strings(requirement.semanticClaimIds)) {
        if (!obligationClaims.has(semanticId)) {
          issues.push(`${id} omits ${requirementId} semantic claim ${semanticId}`)
        }
      }
    }
    if (!Array.isArray(item.independent_specification_symbols) ||
      !Array.isArray(item.implementation_symbols)) {
      issues.push(`${id} lacks independent_specification_symbols or implementation_symbols`)
      continue
    }
    const specSymbols = strings(item.independent_specification_symbols)
    const implementationSymbols = strings(item.implementation_symbols)
    const statement = String(item.lean_statement_sketch ?? "")
    if (['OPERATION_FIDELITY', 'ALGORITHM_FIDELITY', 'RESULT_RANGE', 'EDGE_CASE_BEHAVIOR'].includes(String(item.correctness_kind))) {
      if (specSymbols.length === 0 || implementationSymbols.length === 0) {
        issues.push(`${id} must compare an independent specification symbol with an implementation symbol`)
      }
      for (const symbol of specSymbols) {
        if (!(leanContract?.specificationDefinitions ?? []).includes(symbol)) {
          issues.push(`${id} independent symbol ${symbol} is not declared by the Lean model contract as a specification definition`)
        }
      }
      if (specSymbols.some((symbol) => implementationSymbols.includes(symbol))) {
        issues.push(`${id} uses the same symbol as specification and implementation`)
      }
      for (const specificationSymbol of specSymbols) {
        const specificationDeclaration = declarationBlock(leanSource, specificationSymbol)
        for (const implementationSymbol of implementationSymbols) {
          const escaped = implementationSymbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
          if (new RegExp(`\\b${escaped}\\b`).test(specificationDeclaration)) {
            issues.push(`${id} specification symbol ${specificationSymbol} depends on implementation symbol ${implementationSymbol}`)
          }
        }
      }
    }
    if (item.correctness_kind === 'EXECUTION_CORRESPONDENCE') {
      const executable = leanContract?.executableDefinitions ?? []
      const relational = leanContract?.relationalDefinitions ?? []
      if (!executable.some((name) => statement.includes(name)) ||
        !relational.some((name) => statement.includes(name))) {
        issues.push(`${id} EXECUTION_CORRESPONDENCE must mention both executable and relational definitions`)
      }
    }
    for (const symbol of [...specSymbols, ...implementationSymbols]) {
      if (!statement.includes(symbol)) issues.push(`${id} declaration does not mention declared symbol ${symbol}`)
      if (!declarationExists(leanSource, symbol)) issues.push(`${id} names missing Lean symbol ${symbol}`)
    }
    const normalized = statement.replace(/\s+/g, " ")
    const reflexive = normalized.match(/:\s*([A-Za-z_][A-Za-z0-9_'.]*(?:\s+[^=↔]+)?)\s*=\s*\1\s*(?::=|$)/)
    if (reflexive !== null) issues.push(`${id} is a reflexive tautology rather than an independent correctness claim`)
  }
  for (const kind of requiredProofKinds(semantics)) {
    if (!presentKinds.has(kind)) issues.push(`theorem contract does not cover semantic proof requirement ${kind}`)
  }
  for (const requirementId of requirements.keys()) {
    const count = requirementCoverage.get(requirementId) ?? 0
    if (count !== 1) issues.push(`proof requirement ${requirementId} must map to exactly one theorem; found ${count}`)
  }
  return issues
}
