export const CLAIM_CLASSIFICATIONS = [
  "SOURCE_FACT",
  "DERIVED_INTERPRETATION",
  "DESIGN_DEPENDENCY",
  "ASSUMPTION",
  "OPEN_QUESTION",
] as const

export type ClaimClassification =
  (typeof CLAIM_CLASSIFICATIONS)[number]

export const REVIEW_STATUSES = [
  "DRAFT",
  "READY_FOR_HUMAN_REVIEW",
  "HUMAN_APPROVED",
] as const

export type ReviewStatus = (typeof REVIEW_STATUSES)[number]

export type ContentFingerprint = {
  path: string
  sha256: string
}

export type EvidenceRecord = {
  evidenceId: string
  sourceBundleEvidenceId?: string
  specificationVersion: string
  source: {
    kind: "html" | "pdf" | "artifact"
    documentPath: string
    documentSha256: string
    sourceManifestPath: string
    sourceManifestSha256: string
  }
  locator: {
    section?: string
    heading?: string
    anchor?: string
    startLine?: number
    endLine?: number
    page?: number
  }
  quotation?: string
  quotationSha256?: string
}

export type SemanticClaim = {
  semanticId: string
  classification: ClaimClassification
  statement: string
  evidenceIds: string[]
  dependencyIds: string[]
  stateAffecting: boolean
  humanApprovalDependencies: string[]
  lifecycle: {
    status: "ACTIVE" | "SUPERSEDED" | "INVALIDATED"
    introducedInRevision: number
    supersedes?: string[]
    invalidatedBy?: string
  }
}

export type SharedSemanticEntry = SemanticClaim & {
  specificationVersion: string
  scope: string
  provenance: {
    originatingArtifacts: ContentFingerprint[]
    reviewRecords: ContentFingerprint[]
    acceptedUnitSupport: Array<{
      unit: string
      acceptedEvidenceIds: string[]
      artifacts: ContentFingerprint[]
      reviewRecords: ContentFingerprint[]
    }>
  }
  review: {
    status: ReviewStatus
    confidence?: "LOW" | "MEDIUM" | "HIGH"
  }
}

export type SharedSemanticEnvironment = {
  schemaVersion: 1
  environmentId: string
  language: string
  specificationVersion: string
  revision: number
  scope: {
    scopeId: string
    statement: string
    eligibilityRequirements: string[]
    excludedFeatures: string[]
    outsideScopeAction: "DEEP_REVIEW_OR_LEGACY_FALLBACK"
  }
  review: {
    status: ReviewStatus
    records: ContentFingerprint[]
  }
  sourceManifests: ContentFingerprint[]
  evidence: EvidenceRecord[]
  entries: SharedSemanticEntry[]
}

export type SemanticUnitIdentity = {
  language: string
  specificationVersion: string
  unit: string
  unitSlug: string
}

export type SharedSemanticReference = {
  semanticId: string
  usage: "DEPENDENCY" | "INSTANTIATION"
  rationale: string
}

export type SemanticRefinement = SemanticClaim & {
  targetSharedSemanticId: string
  kind: "REFINES" | "OVERRIDES"
  rationale: string
}

export type SyntaxForm = {
  syntaxId: string
  form: string
  semanticClaimIds: string[]
}

export type OperandDefinition = {
  operandId: string
  name: string
  position: number
  role: "DESTINATION" | "SOURCE" | "GUARD" | "MODIFIER" | "OTHER"
  legalForms: string[]
  typeDomains?: string[]
  coercions?: string[]
  semanticClaimIds: string[]
}

export type StateEffect = {
  effectId: string
  component: string
  mode: "READ" | "WRITE"
  condition: string
  semanticClaimIds: string[]
}

export type Precondition = {
  preconditionId: string
  kind: "STATIC" | "DYNAMIC"
  statement: string
  semanticClaimIds: string[]
}

export type ProofFamily = {
  proofFamilyId: string
  description: string
  semanticClaimIds: string[]
  blockedBySemanticIds: string[]
}

export type InstructionSemanticDelta = {
  schemaVersion: 1
  deltaId: string
  unit: SemanticUnitIdentity
  sharedEnvironment: {
    environmentId: string
    revision: number
    sha256: string
  }
  provenance: {
    sourceBundle: ContentFingerprint
    generatedBy: string
    migrationStatus?: "NON_AUTHORITATIVE_FIXTURE" | "AGENT_GENERATED"
  }
  sharedReferences: SharedSemanticReference[]
  evidence: EvidenceRecord[]
  claims: SemanticClaim[]
  refinements: SemanticRefinement[]
  syntaxForms: SyntaxForm[]
  operands: OperandDefinition[]
  operation: {
    operationId: string
    normalizedMeaning: string
    pseudocode?: string
    inputDomains?: string[]
    outputDomain?: string
    branches?: Array<{
      branchId: string
      condition: string
      result: string
      semanticClaimIds: string[]
    }>
    edgeCases?: Array<{
      caseId: string
      inputClass: string
      behavior: string
      semanticClaimIds: string[]
    }>
    semanticClaimIds: string[]
  }
  stateEffects: StateEffect[]
  preconditions: Precondition[]
  proofFamilies: ProofFamily[]
  scopeStatus?: "FULL_INSTRUCTION" | "PARTIAL_EXPLICIT"
  coverage?: Array<{
    dimension: string
    status: "COVERED" | "NOT_APPLICABLE" | "EXCLUDED_BY_ENCODED_PRECONDITION"
    semanticClaimIds: string[]
    encodedPreconditionIds: string[]
    rationale: string
  }>
  proofRequirements?: Array<{
    requirementId: string
    correctnessKind: string
    semanticClaimIds: string[]
    rationale: string
  }>
  languageCore?: {
    status: "REUSED_APPROVED"
    path: string
    sha256: string
  }
}

export type MaterializedClaim = SemanticClaim & {
  origin:
    | { kind: "SHARED"; environmentId: string; revision: number }
    | { kind: "DELTA"; deltaId: string }
    | {
        kind: "REFINEMENT"
        deltaId: string
        targetSharedSemanticId: string
        refinementKind: "REFINES" | "OVERRIDES"
        rationale: string
      }
  provenance?: SharedSemanticEntry["provenance"]
  sharedReview?: SharedSemanticEntry["review"]
}

export type MaterializedSemanticView = {
  schemaVersion: 1
  viewId: string
  unit: SemanticUnitIdentity
  generatedFrom: {
    sharedEnvironmentId: string
    sharedEnvironmentRevision: number
    sharedEnvironmentSha256: string
    deltaId: string
    deltaSha256: string
    deltaProvenance: InstructionSemanticDelta["provenance"]
  }
  evidence: Array<EvidenceRecord & { origin: "SHARED" | "DELTA" }>
  claims: MaterializedClaim[]
  syntaxForms: SyntaxForm[]
  operands: OperandDefinition[]
  operation: InstructionSemanticDelta["operation"]
  stateEffects: StateEffect[]
  preconditions: Precondition[]
  proofFamilies: ProofFamily[]
  unresolvedStateAffectingSemanticIds: string[]
  scopeStatus?: "FULL_INSTRUCTION" | "PARTIAL_EXPLICIT"
  coverage?: InstructionSemanticDelta["coverage"]
  proofRequirements?: InstructionSemanticDelta["proofRequirements"]
  languageCore?: {
    status: "REUSED_APPROVED"
    path?: string
    environmentId: string
    revision: number
    sha256: string
  }
}

export type ValidationIssue = {
  code: string
  path: string
  message: string
}

export type ValidationResult<T> = {
  ok: boolean
  value?: T
  issues: ValidationIssue[]
  unresolvedStateAffectingSemanticIds: string[]
}
