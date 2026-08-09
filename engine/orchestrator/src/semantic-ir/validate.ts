import {
  CLAIM_CLASSIFICATIONS,
  REVIEW_STATUSES,
  type EvidenceRecord,
  type InstructionSemanticDelta,
  type SemanticClaim,
  type SharedSemanticEnvironment,
  type ValidationIssue,
  type ValidationResult,
} from "./types.js"
import { sharedEnvironmentSha256 } from "./document.js"

type JsonObject = Record<string, unknown>

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function stringValue(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => stringValue(item))
}

function hashValue(value: unknown): value is string {
  return typeof value === "string" && /^[a-f0-9]{64}$/.test(value)
}

function add(
  issues: ValidationIssue[],
  code: string,
  path: string,
  message: string,
): void {
  issues.push({ code, path, message })
}

function duplicateIds(
  values: unknown[],
  key: string,
  path: string,
  issues: ValidationIssue[],
  code: string,
): Set<string> {
  const seen = new Set<string>()
  const duplicates = new Set<string>()

  for (const [index, value] of values.entries()) {
    if (!isObject(value) || !stringValue(value[key])) {
      add(issues, "MISSING_ID", `${path}[${index}].${key}`, "ID must be a non-empty string")
      continue
    }
    const id = value[key]
    if (seen.has(id)) duplicates.add(id)
    seen.add(id)
  }

  for (const id of duplicates) {
    add(issues, code, path, `Duplicate ID: ${id}`)
  }
  return seen
}

function validateFingerprint(
  value: unknown,
  path: string,
  issues: ValidationIssue[],
): void {
  if (!isObject(value)) {
    add(issues, "INVALID_FINGERPRINT", path, "Fingerprint must be an object")
    return
  }
  if (!stringValue(value.path)) {
    add(issues, "INVALID_PATH", `${path}.path`, "Path must be a non-empty string")
  }
  if (!hashValue(value.sha256)) {
    add(issues, "INVALID_SHA256", `${path}.sha256`, "SHA-256 must contain 64 lowercase hex characters")
  }
}

function validateFingerprintList(
  value: unknown,
  path: string,
  issues: ValidationIssue[],
  requireNonEmpty = false,
): void {
  if (!Array.isArray(value)) {
    add(issues, "INVALID_FINGERPRINT_LIST", path, "Expected an array of content fingerprints")
    return
  }
  if (requireNonEmpty && value.length === 0) {
    add(issues, "MISSING_FINGERPRINT", path, "At least one content fingerprint is required")
  }
  value.forEach((item, index) => validateFingerprint(item, `${path}[${index}]`, issues))
}

function validateEvidence(
  value: unknown,
  path: string,
  specificationVersion: string | undefined,
  issues: ValidationIssue[],
): void {
  if (!isObject(value)) {
    add(issues, "INVALID_EVIDENCE", path, "Evidence must be an object")
    return
  }
  if (!stringValue(value.evidenceId)) {
    add(issues, "MISSING_EVIDENCE_ID", `${path}.evidenceId`, "Evidence ID is required")
  }
  if (value.specificationVersion !== specificationVersion) {
    add(issues, "EVIDENCE_VERSION_MISMATCH", `${path}.specificationVersion`, "Evidence version must match its semantic document")
  }
  if (!isObject(value.source)) {
    add(issues, "INVALID_EVIDENCE_SOURCE", `${path}.source`, "Evidence source is required")
  } else {
    if (!["html", "pdf", "artifact"].includes(String(value.source.kind))) {
      add(issues, "INVALID_EVIDENCE_KIND", `${path}.source.kind`, "Evidence kind must be html, pdf, or artifact")
    }
    for (const field of ["documentPath", "sourceManifestPath"] as const) {
      if (!stringValue(value.source[field])) {
        add(issues, "INVALID_PATH", `${path}.source.${field}`, `${field} is required`)
      }
    }
    for (const field of ["documentSha256", "sourceManifestSha256"] as const) {
      if (!hashValue(value.source[field])) {
        add(issues, "INVALID_SHA256", `${path}.source.${field}`, `${field} must be a SHA-256 hash`)
      }
    }
  }
  if (!isObject(value.locator)) {
    add(issues, "INVALID_EVIDENCE_LOCATOR", `${path}.locator`, "Evidence locator is required")
  } else if (Object.keys(value.locator).length === 0) {
    add(issues, "INVALID_EVIDENCE_LOCATOR", `${path}.locator`, "Evidence locator must identify at least one source location")
  }
  if (value.quotationSha256 !== undefined && !hashValue(value.quotationSha256)) {
    add(issues, "INVALID_SHA256", `${path}.quotationSha256`, "Quotation hash must be a SHA-256 hash")
  }
}

function validateClaimShape(
  value: unknown,
  path: string,
  issues: ValidationIssue[],
): void {
  if (!isObject(value)) {
    add(issues, "INVALID_SEMANTIC_CLAIM", path, "Semantic claim must be an object")
    return
  }
  if (!stringValue(value.semanticId)) {
    add(issues, "MISSING_ID", `${path}.semanticId`, "Semantic ID is required")
  }
  if (!CLAIM_CLASSIFICATIONS.includes(value.classification as never)) {
    add(issues, "INVALID_CLASSIFICATION", `${path}.classification`, `Invalid semantic classification: ${String(value.classification)}`)
  }
  if (!stringValue(value.statement)) {
    add(issues, "MISSING_STATEMENT", `${path}.statement`, "Semantic statement is required")
  }
  for (const field of ["evidenceIds", "dependencyIds", "humanApprovalDependencies"] as const) {
    if (!stringArray(value[field])) {
      add(issues, "INVALID_ID_LIST", `${path}.${field}`, `${field} must be an array of non-empty strings`)
    } else if (new Set(value[field]).size !== value[field].length) {
      add(issues, "DUPLICATE_ID_IN_LIST", `${path}.${field}`, `${field} must not contain duplicate IDs`)
    }
  }
  if (typeof value.stateAffecting !== "boolean") {
    add(issues, "INVALID_STATE_AFFECTING", `${path}.stateAffecting`, "stateAffecting must be boolean")
  }
  if (!isObject(value.lifecycle)) {
    add(issues, "INVALID_LIFECYCLE", `${path}.lifecycle`, "Claim lifecycle is required")
  } else {
    if (!["ACTIVE", "SUPERSEDED", "INVALIDATED"].includes(String(value.lifecycle.status))) {
      add(issues, "INVALID_LIFECYCLE", `${path}.lifecycle.status`, "Invalid lifecycle status")
    }
    if (!Number.isInteger(value.lifecycle.introducedInRevision) || Number(value.lifecycle.introducedInRevision) < 1) {
      add(issues, "INVALID_REVISION", `${path}.lifecycle.introducedInRevision`, "Introduced revision must be a positive integer")
    }
    if (value.lifecycle.status === "INVALIDATED" && !stringValue(value.lifecycle.invalidatedBy)) {
      add(issues, "MISSING_INVALIDATION", `${path}.lifecycle.invalidatedBy`, "Invalidated claims require invalidatedBy")
    }
    if (value.lifecycle.supersedes !== undefined && !stringArray(value.lifecycle.supersedes)) {
      add(issues, "INVALID_LIFECYCLE", `${path}.lifecycle.supersedes`, "supersedes must be an array of semantic IDs")
    }
  }
  if (
    value.classification === "ASSUMPTION" &&
    (!Array.isArray(value.humanApprovalDependencies) || value.humanApprovalDependencies.length === 0)
  ) {
    add(issues, "ASSUMPTION_MISSING_HUMAN_APPROVAL", `${path}.humanApprovalDependencies`, "Assumptions require an explicit human approval dependency")
  }
}

function validateClaimLinks(
  claim: unknown,
  path: string,
  semanticIds: Set<string>,
  evidence: Map<string, EvidenceRecord>,
  issues: ValidationIssue[],
): void {
  if (!isObject(claim)) return
  const evidenceIds = stringArray(claim.evidenceIds) ? claim.evidenceIds : []
  const dependencyIds = stringArray(claim.dependencyIds) ? claim.dependencyIds : []

  if (claim.classification === "SOURCE_FACT" && evidenceIds.length === 0) {
    add(issues, "SOURCE_FACT_MISSING_EVIDENCE", `${path}.evidenceIds`, "SOURCE_FACT requires official evidence")
  }

  let officialEvidence = false
  for (const evidenceId of evidenceIds) {
    const record = evidence.get(evidenceId)
    if (record === undefined) {
      add(issues, "UNKNOWN_EVIDENCE_ID", `${path}.evidenceIds`, `Unknown evidence ID: ${evidenceId}`)
    } else if (record.source.kind === "html" || record.source.kind === "pdf") {
      officialEvidence = true
    }
  }
  if (claim.classification === "SOURCE_FACT" && evidenceIds.length > 0 && !officialEvidence) {
    add(issues, "SOURCE_FACT_NON_OFFICIAL_EVIDENCE", `${path}.evidenceIds`, "SOURCE_FACT requires at least one official HTML or PDF evidence record")
  }

  for (const dependencyId of dependencyIds) {
    if (!semanticIds.has(dependencyId)) {
      add(issues, "UNKNOWN_SEMANTIC_DEPENDENCY", `${path}.dependencyIds`, `Unknown semantic dependency: ${dependencyId}`)
    }
  }
}

function findCycles(
  claims: unknown[],
  issues: ValidationIssue[],
): void {
  const graph = new Map<string, string[]>()
  for (const claim of claims) {
    if (isObject(claim) && stringValue(claim.semanticId)) {
      graph.set(claim.semanticId, stringArray(claim.dependencyIds) ? claim.dependencyIds : [])
    }
  }

  const visiting = new Set<string>()
  const visited = new Set<string>()
  const visit = (id: string): void => {
    if (visiting.has(id)) {
      add(issues, "SEMANTIC_DEPENDENCY_CYCLE", "$.claims", `Dependency cycle includes ${id}`)
      return
    }
    if (visited.has(id)) return
    visiting.add(id)
    for (const dependency of graph.get(id) ?? []) {
      if (graph.has(dependency)) visit(dependency)
    }
    visiting.delete(id)
    visited.add(id)
  }
  for (const id of graph.keys()) visit(id)
}

function unresolvedStateAffecting(claims: unknown[]): string[] {
  return claims.flatMap((claim) =>
    isObject(claim) &&
    stringValue(claim.semanticId) &&
    claim.classification === "OPEN_QUESTION" &&
    claim.stateAffecting === true &&
    isObject(claim.lifecycle) &&
    claim.lifecycle.status === "ACTIVE"
      ? [claim.semanticId]
      : [],
  ).sort()
}

function evidenceMap(values: unknown[]): Map<string, EvidenceRecord> {
  const map = new Map<string, EvidenceRecord>()
  for (const value of values) {
    if (isObject(value) && stringValue(value.evidenceId) && !map.has(value.evidenceId)) {
      map.set(value.evidenceId, value as EvidenceRecord)
    }
  }
  return map
}

export function validateSharedSemanticEnvironment(
  input: unknown,
): ValidationResult<SharedSemanticEnvironment> {
  const issues: ValidationIssue[] = []
  if (!isObject(input)) {
    return {
      ok: false,
      issues: [{ code: "INVALID_DOCUMENT", path: "$", message: "Shared semantic environment must be an object" }],
      unresolvedStateAffectingSemanticIds: [],
    }
  }

  if (input.schemaVersion !== 1) add(issues, "INVALID_SCHEMA_VERSION", "$.schemaVersion", "Expected schemaVersion=1")
  for (const field of ["environmentId", "language", "specificationVersion"] as const) {
    if (!stringValue(input[field])) add(issues, "MISSING_IDENTITY", `$.${field}`, `${field} is required`)
  }
  if (!Number.isInteger(input.revision) || Number(input.revision) < 1) {
    add(issues, "INVALID_REVISION", "$.revision", "Environment revision must be a positive integer")
  }

  const sourceManifests = Array.isArray(input.sourceManifests) ? input.sourceManifests : []
  if (!Array.isArray(input.sourceManifests) || sourceManifests.length === 0) {
    add(issues, "MISSING_SOURCE_MANIFEST", "$.sourceManifests", "At least one source manifest fingerprint is required")
  }
  sourceManifests.forEach((value, index) => validateFingerprint(value, `$.sourceManifests[${index}]`, issues))

  if (!isObject(input.review) || !REVIEW_STATUSES.includes(input.review.status as never)) {
    add(issues, "INVALID_REVIEW_STATUS", "$.review", "A valid review status is required")
  } else {
    const records = Array.isArray(input.review.records) ? input.review.records : []
    records.forEach((value, index) => validateFingerprint(value, `$.review.records[${index}]`, issues))
    if (input.review.status === "HUMAN_APPROVED" && records.length === 0) {
      add(issues, "MISSING_REVIEW_RECORD", "$.review.records", "HUMAN_APPROVED environment requires a review record fingerprint")
    }
  }

  const evidence = Array.isArray(input.evidence) ? input.evidence : []
  const entries = Array.isArray(input.entries) ? input.entries : []
  if (!Array.isArray(input.evidence)) add(issues, "INVALID_EVIDENCE_LIST", "$.evidence", "Evidence must be an array")
  if (!Array.isArray(input.entries)) add(issues, "INVALID_ENTRY_LIST", "$.entries", "Entries must be an array")
  duplicateIds(evidence, "evidenceId", "$.evidence", issues, "DUPLICATE_EVIDENCE_ID")
  const semanticIds = duplicateIds(entries, "semanticId", "$.entries", issues, "DUPLICATE_SEMANTIC_ID")

  evidence.forEach((value, index) => validateEvidence(value, `$.evidence[${index}]`, stringValue(input.specificationVersion) ? input.specificationVersion : undefined, issues))
  const evidenceById = evidenceMap(evidence)
  entries.forEach((value, index) => {
    const path = `$.entries[${index}]`
    validateClaimShape(value, path, issues)
    validateClaimLinks(value, path, semanticIds, evidenceById, issues)
    if (isObject(value) && value.specificationVersion !== input.specificationVersion) {
      add(issues, "SEMANTIC_VERSION_MISMATCH", `${path}.specificationVersion`, "Shared entry version must match the environment")
    }
    if (isObject(value) && value.scope !== "PTX_9_3_SHARED") {
      add(issues, "INVALID_SHARED_SCOPE", `${path}.scope`, "Shared entry must use PTX_9_3_SHARED scope")
    }
    if (
      isObject(value) &&
      isObject(value.lifecycle) &&
      Number.isInteger(value.lifecycle.introducedInRevision) &&
      Number.isInteger(input.revision) &&
      Number(value.lifecycle.introducedInRevision) > Number(input.revision)
    ) {
      add(issues, "FUTURE_ENTRY_REVISION", `${path}.lifecycle.introducedInRevision`, "Entry cannot be introduced after the environment revision")
    }
    if (!isObject(value) || !isObject(value.provenance)) {
      add(issues, "INVALID_PROVENANCE", `${path}.provenance`, "Shared entry provenance is required")
    } else {
      validateFingerprintList(
        value.provenance.originatingArtifacts,
        `${path}.provenance.originatingArtifacts`,
        issues,
        true,
      )
      validateFingerprintList(
        value.provenance.reviewRecords,
        `${path}.provenance.reviewRecords`,
        issues,
        isObject(input.review) && input.review.status === "HUMAN_APPROVED",
      )
    }
    if (!isObject(value) || !isObject(value.review)) {
      add(issues, "INVALID_ENTRY_REVIEW", `${path}.review`, "Shared entry review state is required")
    } else {
      if (!REVIEW_STATUSES.includes(value.review.status as never)) {
        add(issues, "INVALID_ENTRY_REVIEW", `${path}.review.status`, "Shared entry review status is invalid")
      }
      if (
        value.review.confidence !== undefined &&
        !["LOW", "MEDIUM", "HIGH"].includes(String(value.review.confidence))
      ) {
        add(issues, "INVALID_CONFIDENCE", `${path}.review.confidence`, "Confidence must be LOW, MEDIUM, or HIGH")
      }
      if (
        isObject(input.review) &&
        input.review.status === "HUMAN_APPROVED" &&
        value.review.status !== "HUMAN_APPROVED"
      ) {
        add(issues, "UNREVIEWED_SHARED_ENTRY", `${path}.review.status`, "A human-approved environment cannot contain an unapproved entry")
      }
    }
  })
  const entryById = new Map(
    entries.flatMap((entry) =>
      isObject(entry) && stringValue(entry.semanticId)
        ? [[entry.semanticId, entry] as const]
        : [],
    ),
  )
  entries.forEach((entry, index) => {
    if (
      !isObject(entry) ||
      !isObject(entry.lifecycle) ||
      entry.lifecycle.status !== "ACTIVE" ||
      !stringArray(entry.dependencyIds)
    ) return
    for (const dependencyId of entry.dependencyIds) {
      const dependency = entryById.get(dependencyId)
      if (
        dependency !== undefined &&
        isObject(dependency.lifecycle) &&
        dependency.lifecycle.status !== "ACTIVE"
      ) {
        add(issues, "ACTIVE_DEPENDS_ON_INACTIVE", `$.entries[${index}].dependencyIds`, `Active entry depends on inactive entry: ${dependencyId}`)
      }
    }
  })
  findCycles(entries, issues)

  const unresolved = unresolvedStateAffecting(entries)
  return {
    ok: issues.length === 0,
    value: issues.length === 0 ? input as SharedSemanticEnvironment : undefined,
    issues,
    unresolvedStateAffectingSemanticIds: unresolved,
  }
}

function validateClaimReferences(
  values: unknown,
  path: string,
  knownClaims: Set<string>,
  issues: ValidationIssue[],
): void {
  if (!Array.isArray(values)) {
    add(issues, "INVALID_LIST", path, "Expected an array")
    return
  }
  for (const [index, value] of values.entries()) {
    if (!isObject(value) || !stringArray(value.semanticClaimIds)) {
      add(issues, "INVALID_CLAIM_REFERENCES", `${path}[${index}].semanticClaimIds`, "semanticClaimIds must be an array")
      continue
    }
    for (const id of value.semanticClaimIds) {
      if (!knownClaims.has(id)) add(issues, "UNKNOWN_SEMANTIC_REFERENCE", `${path}[${index}].semanticClaimIds`, `Unknown semantic ID: ${id}`)
    }
  }
}

function structuredReferenceIds(values: unknown): string[] {
  if (!Array.isArray(values)) return []
  return values.flatMap((value) =>
    isObject(value) && stringArray(value.semanticClaimIds)
      ? value.semanticClaimIds
      : [],
  )
}

function validateStructuredList(
  values: unknown,
  path: string,
  idKey: string,
  requiredStringFields: string[],
  knownClaims: Set<string>,
  issues: ValidationIssue[],
): void {
  if (!Array.isArray(values)) {
    add(issues, "INVALID_LIST", path, "Expected an array")
    return
  }
  duplicateIds(values, idKey, path, issues, "DUPLICATE_STRUCTURED_ID")
  validateClaimReferences(values, path, knownClaims, issues)
  for (const [index, value] of values.entries()) {
    if (!isObject(value)) continue
    for (const field of requiredStringFields) {
      if (!stringValue(value[field])) {
        add(issues, "INVALID_STRUCTURED_FIELD", `${path}[${index}].${field}`, `${field} is required`)
      }
    }
  }
}

export function validateInstructionSemanticDelta(
  input: unknown,
  sharedInput: unknown,
): ValidationResult<InstructionSemanticDelta> {
  const issues: ValidationIssue[] = []
  const sharedResult = validateSharedSemanticEnvironment(sharedInput)
  if (!sharedResult.ok || sharedResult.value === undefined) {
    return {
      ok: false,
      issues: sharedResult.issues.map((issue) => ({ ...issue, path: `shared${issue.path}` })),
      unresolvedStateAffectingSemanticIds: sharedResult.unresolvedStateAffectingSemanticIds,
    }
  }
  const shared = sharedResult.value

  if (!isObject(input)) {
    return {
      ok: false,
      issues: [{ code: "INVALID_DOCUMENT", path: "$", message: "Semantic delta must be an object" }],
      unresolvedStateAffectingSemanticIds: [],
    }
  }
  if (input.schemaVersion !== 1) add(issues, "INVALID_SCHEMA_VERSION", "$.schemaVersion", "Expected schemaVersion=1")
  if (!stringValue(input.deltaId)) add(issues, "MISSING_IDENTITY", "$.deltaId", "deltaId is required")
  if (!isObject(input.unit)) {
    add(issues, "INVALID_UNIT_IDENTITY", "$.unit", "Unit identity is required")
  } else {
    for (const field of ["language", "specificationVersion", "unit", "unitSlug"] as const) {
      if (!stringValue(input.unit[field])) add(issues, "INVALID_UNIT_IDENTITY", `$.unit.${field}`, `${field} is required`)
    }
    if (input.unit.language !== shared.language || input.unit.specificationVersion !== shared.specificationVersion) {
      add(issues, "UNIT_VERSION_MISMATCH", "$.unit", "Unit language/version must match shared environment")
    }
  }

  if (!isObject(input.sharedEnvironment)) {
    add(issues, "INVALID_SHARED_PIN", "$.sharedEnvironment", "Shared environment pin is required")
  } else {
    if (input.sharedEnvironment.environmentId !== shared.environmentId || input.sharedEnvironment.revision !== shared.revision) {
      add(issues, "SHARED_ENVIRONMENT_IDENTITY_MISMATCH", "$.sharedEnvironment", "Shared environment identity/revision mismatch")
    }
    if (!hashValue(input.sharedEnvironment.sha256)) {
      add(issues, "INVALID_SHA256", "$.sharedEnvironment.sha256", "Shared environment hash is invalid")
    } else {
      const actualHash = sharedEnvironmentSha256(shared)
      if (input.sharedEnvironment.sha256 !== actualHash) {
        add(
          issues,
          "SHARED_ENVIRONMENT_HASH_MISMATCH",
          "$.sharedEnvironment.sha256",
          `Pinned shared environment hash does not match revision ${shared.revision}`,
        )
      }
    }
  }

  if (!isObject(input.provenance) || !isObject(input.provenance.sourceBundle)) {
    add(issues, "INVALID_PROVENANCE", "$.provenance", "Source-bundle provenance is required")
  } else {
    validateFingerprint(input.provenance.sourceBundle, "$.provenance.sourceBundle", issues)
    if (!stringValue(input.provenance.generatedBy)) add(issues, "INVALID_PROVENANCE", "$.provenance.generatedBy", "generatedBy is required")
  }

  const sharedReferences = Array.isArray(input.sharedReferences) ? input.sharedReferences : []
  const localEvidence = Array.isArray(input.evidence) ? input.evidence : []
  const claims = Array.isArray(input.claims) ? input.claims : []
  const refinements = Array.isArray(input.refinements) ? input.refinements : []
  for (const [field, value] of [["sharedReferences", input.sharedReferences], ["evidence", input.evidence], ["claims", input.claims], ["refinements", input.refinements]] as const) {
    if (!Array.isArray(value)) add(issues, "INVALID_LIST", `$.${field}`, `${field} must be an array`)
  }

  const sharedIds = new Set(shared.entries.map((entry) => entry.semanticId))
  const referencedSharedIds = new Set<string>()
  for (const [index, reference] of sharedReferences.entries()) {
    if (!isObject(reference) || !stringValue(reference.semanticId)) {
      add(issues, "INVALID_SHARED_REFERENCE", `$.sharedReferences[${index}]`, "Shared reference requires semanticId")
      continue
    }
    if (referencedSharedIds.has(reference.semanticId)) add(issues, "DUPLICATE_SHARED_REFERENCE", "$.sharedReferences", `Duplicate shared reference: ${reference.semanticId}`)
    referencedSharedIds.add(reference.semanticId)
    if (!["DEPENDENCY", "INSTANTIATION"].includes(String(reference.usage))) {
      add(issues, "INVALID_SHARED_REFERENCE_USAGE", `$.sharedReferences[${index}].usage`, "Shared reference usage must be DEPENDENCY or INSTANTIATION")
    }
    if (!stringValue(reference.rationale)) {
      add(issues, "MISSING_SHARED_REFERENCE_RATIONALE", `$.sharedReferences[${index}].rationale`, "Shared reference rationale is required")
    }
    const target = shared.entries.find((entry) => entry.semanticId === reference.semanticId)
    if (target === undefined) {
      add(issues, "UNKNOWN_SHARED_SEMANTIC_ID", `$.sharedReferences[${index}].semanticId`, `Unknown shared semantic ID: ${reference.semanticId}`)
    } else if (target.lifecycle.status !== "ACTIVE") {
      add(issues, "INACTIVE_SHARED_SEMANTIC_ID", `$.sharedReferences[${index}].semanticId`, `Shared semantic ID is not active: ${reference.semanticId}`)
    }
  }

  duplicateIds(localEvidence, "evidenceId", "$.evidence", issues, "DUPLICATE_EVIDENCE_ID")
  localEvidence.forEach((value, index) => validateEvidence(value, `$.evidence[${index}]`, shared.specificationVersion, issues))
  const allEvidence = [...shared.evidence, ...localEvidence]
  duplicateIds(allEvidence, "evidenceId", "$.combinedEvidence", issues, "DUPLICATE_EVIDENCE_ID")
  const evidenceById = evidenceMap(allEvidence)

  const deltaSemanticIds = duplicateIds([...claims, ...refinements], "semanticId", "$.claimsAndRefinements", issues, "DUPLICATE_SEMANTIC_ID")
  for (const id of deltaSemanticIds) {
    if (sharedIds.has(id)) add(issues, "SEMANTIC_ID_COLLIDES_WITH_SHARED", "$.claimsAndRefinements", `Delta semantic ID collides with shared ID: ${id}`)
  }
  const allSemanticIds = new Set([...sharedIds, ...deltaSemanticIds])

  claims.forEach((claim, index) => {
    const path = `$.claims[${index}]`
    validateClaimShape(claim, path, issues)
    validateClaimLinks(claim, path, allSemanticIds, evidenceById, issues)
  })
  refinements.forEach((refinement, index) => {
    const path = `$.refinements[${index}]`
    validateClaimShape(refinement, path, issues)
    validateClaimLinks(refinement, path, allSemanticIds, evidenceById, issues)
    if (!isObject(refinement) || !stringValue(refinement.targetSharedSemanticId) || !sharedIds.has(refinement.targetSharedSemanticId)) {
      add(issues, "INVALID_REFINEMENT_TARGET", `${path}.targetSharedSemanticId`, "Refinement target must be an existing shared semantic ID")
    } else if (!referencedSharedIds.has(refinement.targetSharedSemanticId)) {
      add(issues, "UNREFERENCED_REFINEMENT_TARGET", `${path}.targetSharedSemanticId`, "Refinement target must also be an explicit shared reference")
    }
    if (!isObject(refinement) || !["REFINES", "OVERRIDES"].includes(String(refinement.kind))) {
      add(issues, "INVALID_REFINEMENT_KIND", `${path}.kind`, "Refinement kind must be REFINES or OVERRIDES")
    }
    if (!isObject(refinement) || !stringValue(refinement.rationale)) {
      add(issues, "MISSING_REFINEMENT_RATIONALE", `${path}.rationale`, "Refinement rationale is required")
    }
  })
  findCycles([...shared.entries, ...claims, ...refinements], issues)

  validateStructuredList(input.syntaxForms, "$.syntaxForms", "syntaxId", ["form"], allSemanticIds, issues)
  validateStructuredList(input.operands, "$.operands", "operandId", ["name"], allSemanticIds, issues)
  validateStructuredList(input.stateEffects, "$.stateEffects", "effectId", ["component", "condition"], allSemanticIds, issues)
  validateStructuredList(input.preconditions, "$.preconditions", "preconditionId", ["statement"], allSemanticIds, issues)
  validateStructuredList(input.proofFamilies, "$.proofFamilies", "proofFamilyId", ["description"], allSemanticIds, issues)

  if (Array.isArray(input.operands)) {
    input.operands.forEach((operand, index) => {
      if (!isObject(operand)) return
      if (!Number.isInteger(operand.position) || Number(operand.position) < 0) {
        add(issues, "INVALID_OPERAND_POSITION", `$.operands[${index}].position`, "Operand position must be a non-negative integer")
      }
      if (!["DESTINATION", "SOURCE", "GUARD", "MODIFIER", "OTHER"].includes(String(operand.role))) {
        add(issues, "INVALID_OPERAND_ROLE", `$.operands[${index}].role`, "Operand role is invalid")
      }
      if (!stringArray(operand.legalForms) || operand.legalForms.length === 0) {
        add(issues, "INVALID_OPERAND_LEGAL_FORMS", `$.operands[${index}].legalForms`, "At least one legal operand form is required")
      }
    })
  }
  if (Array.isArray(input.stateEffects)) {
    input.stateEffects.forEach((effect, index) => {
      if (isObject(effect) && !["READ", "WRITE"].includes(String(effect.mode))) {
        add(issues, "INVALID_STATE_EFFECT_MODE", `$.stateEffects[${index}].mode`, "State effect mode must be READ or WRITE")
      }
    })
  }
  if (Array.isArray(input.preconditions)) {
    input.preconditions.forEach((precondition, index) => {
      if (isObject(precondition) && !["STATIC", "DYNAMIC"].includes(String(precondition.kind))) {
        add(issues, "INVALID_PRECONDITION_KIND", `$.preconditions[${index}].kind`, "Precondition kind must be STATIC or DYNAMIC")
      }
    })
  }
  if (Array.isArray(input.proofFamilies)) {
    input.proofFamilies.forEach((family, index) => {
      if (!isObject(family) || !stringArray(family.blockedBySemanticIds)) {
        add(issues, "INVALID_BLOCKER_LIST", `$.proofFamilies[${index}].blockedBySemanticIds`, "blockedBySemanticIds must be an array")
        return
      }
      for (const id of family.blockedBySemanticIds) {
        if (!allSemanticIds.has(id)) {
          add(issues, "UNKNOWN_SEMANTIC_REFERENCE", `$.proofFamilies[${index}].blockedBySemanticIds`, `Unknown semantic ID: ${id}`)
        }
      }
    })
  }
  if (!isObject(input.operation) || !stringArray(input.operation.semanticClaimIds)) {
    add(issues, "INVALID_OPERATION", "$.operation", "Operation and semanticClaimIds are required")
  } else {
    for (const id of input.operation.semanticClaimIds) {
      if (!allSemanticIds.has(id)) add(issues, "UNKNOWN_SEMANTIC_REFERENCE", "$.operation.semanticClaimIds", `Unknown semantic ID: ${id}`)
    }
  }

  if (isObject(input.operation)) {
    if (!stringValue(input.operation.operationId)) add(issues, "INVALID_OPERATION", "$.operation.operationId", "operationId is required")
    if (!stringValue(input.operation.normalizedMeaning)) add(issues, "INVALID_OPERATION", "$.operation.normalizedMeaning", "normalizedMeaning is required")
  }

  const directlyUsedSharedIds = new Set([
    ...claims.flatMap((claim) =>
      isObject(claim) && stringArray(claim.dependencyIds)
        ? claim.dependencyIds.filter((id) => sharedIds.has(id))
        : [],
    ),
    ...refinements.flatMap((claim) =>
      isObject(claim) && stringArray(claim.dependencyIds)
        ? claim.dependencyIds.filter((id) => sharedIds.has(id))
        : [],
    ),
    ...structuredReferenceIds(input.syntaxForms).filter((id) => sharedIds.has(id)),
    ...structuredReferenceIds(input.operands).filter((id) => sharedIds.has(id)),
    ...structuredReferenceIds(input.stateEffects).filter((id) => sharedIds.has(id)),
    ...structuredReferenceIds(input.preconditions).filter((id) => sharedIds.has(id)),
    ...structuredReferenceIds(input.proofFamilies).filter((id) => sharedIds.has(id)),
    ...(Array.isArray(input.proofFamilies)
      ? input.proofFamilies.flatMap((family) =>
          isObject(family) && stringArray(family.blockedBySemanticIds)
            ? family.blockedBySemanticIds.filter((id) => sharedIds.has(id))
            : [],
        )
      : []),
    ...(isObject(input.operation) && stringArray(input.operation.semanticClaimIds)
      ? input.operation.semanticClaimIds.filter((id) => sharedIds.has(id))
      : []),
  ])
  for (const semanticId of directlyUsedSharedIds) {
    if (!referencedSharedIds.has(semanticId)) {
      add(
        issues,
        "UNDECLARED_SHARED_SEMANTIC_DEPENDENCY",
        "$.sharedReferences",
        `Directly used shared semantic ID must be declared: ${semanticId}`,
      )
    }
  }

  const selectedSharedIds = new Set(referencedSharedIds)
  const pendingSharedIds = [...selectedSharedIds]
  const sharedById = new Map(shared.entries.map((entry) => [entry.semanticId, entry]))
  while (pendingSharedIds.length > 0) {
    const semanticId = pendingSharedIds.pop()
    if (semanticId === undefined) continue
    for (const dependencyId of sharedById.get(semanticId)?.dependencyIds ?? []) {
      if (!selectedSharedIds.has(dependencyId)) {
        selectedSharedIds.add(dependencyId)
        pendingSharedIds.push(dependencyId)
      }
    }
  }

  const unresolved = unresolvedStateAffecting([
    ...shared.entries.filter((entry) => selectedSharedIds.has(entry.semanticId)),
    ...claims,
    ...refinements,
  ])

  return {
    ok: issues.length === 0,
    value: issues.length === 0 ? input as InstructionSemanticDelta : undefined,
    issues,
    unresolvedStateAffectingSemanticIds: unresolved,
  }
}
