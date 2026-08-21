export type ArtifactFingerprint = {
  path: string
  sha256: string
}

export type EvidenceLocator = {
  section?: string
  heading?: string
  anchor?: string
  startLine?: number
  endLine?: number
  page?: number
  bbox?: [number, number, number, number]
}

export type Evidence = {
  evidenceId: string
  sourceKind: "HTML" | "PDF" | "ARTIFACT"
  documentPath: string
  documentSha256: string
  locator: EvidenceLocator
  quotation?: string
  alignedFromEvidenceId?: string
  alignmentMethod?: "EXACT_QUOTE_TOKEN_MATCH" | "PAGE_HINTED_EXACT_QUOTE_TOKEN_MATCH" | "DISTINCTIVE_TOKEN_WINDOW_MATCH"
}

export type Claim = {
  semanticId: string
  classification:
    | "SOURCE_FACT"
    | "DERIVED_INTERPRETATION"
    | "DESIGN_DEPENDENCY"
    | "ASSUMPTION"
    | "OPEN_QUESTION"
  statement: string
  evidenceIds: string[]
  dependencyIds?: string[]
  humanApprovalDependencies?: string[]
  origin?: "SEMANTICS" | "ARCHITECTURE"
  stateAffecting?: boolean
}

export type SemanticUncertainty = {
  semanticId: string
  statement: string
  origin: "SEMANTICS" | "ARCHITECTURE"
  stateAffecting?: boolean
  unresolved: true
  benchmarkDisposition?: {
    mode: "AUTO_APPROVE"
    policy: "CONSERVATIVE_BOUNDED_SCOPE"
    humanApproved: false
  }
}

export type EvidenceEntry = {
  entryId: string
  declarationKind: string
  declarationName: string
  leanRange: { startLine: number; endLine: number }
  semanticIds: string[]
  theoremObligationIds?: string[]
  claims: Claim[]
  evidence: Evidence[]
  unresolvedReferences: string[]
  coverage?: {
    directClaimIds: string[]
    transitiveClaimIds: string[]
    sourceFactIds: string[]
    projectBoundaryIds: string[]
    officialEvidenceIds: string[]
    pdfEvidenceIds: string[]
    projectEvidenceIds: string[]
    unresolvedDependencyIds: string[]
  }
}

export type EvidenceManifest = {
  schemaVersion: 1 | 2 | 3 | 4 | 5 | 6
  manifestType: "spec2lean_evidence_manifest"
  generator: string
  runId: string
  language: string
  specificationVersion: string
  unit: string
  documentRole?: "SEMANTICS" | "PROOFS"
  sourceManifest: ArtifactFingerprint
  leanDocument: ArtifactFingerprint
  semanticDocument: ArtifactFingerprint
  architectureDocument?: ArtifactFingerprint
  sourceBundle?: ArtifactFingerprint
  sourceBundles?: ArtifactFingerprint[]
  theoremDocument?: ArtifactFingerprint
  entries: EvidenceEntry[]
  semanticUncertainties?: SemanticUncertainty[]
  qualityContract?: {
    scopeStatus: string
    languageCoreStatus: string
    coverage: Array<{ dimension: string; status: string; rationale: string }>
    encodedExclusions: string[]
    proofRequirementKinds: string[]
  }
  diagnostics: {
    requiredOfficialRenditions?: Array<"HTML" | "PDF">
    declarationsWithoutReferences: string[]
    unresolvedReferences: string[]
    declarationsWithoutEvidencePath?: string[]
    claimsWithoutDependencyPath?: string[]
    sourceFactsWithoutOfficialEvidence?: string[]
    sourceFactsWithoutHtmlEvidence?: string[]
    sourceFactsWithoutPdfEvidence?: string[]
    assumptionsWithoutApprovalDependency?: string[]
    unresolvedOpenQuestions?: string[]
    declarationDiscovery?: {
      source: "LEAN_ELABORATOR"
      leanDerivedRangeCount: number
      manifestDeclarationCount: number
      leanDeclarationsNotInManifest: string[]
      manifestDeclarationsNotConfirmedByLean: string[]
    }
    pdfAlignment?: {
      eligible?: number
      matched: number
      ambiguous: string[]
      unmatched: string[]
      coverageRatio?: number
      failure?: string
    }
  }
}

export type IndexedManifest = {
  manifestPath: string
  manifest: EvidenceManifest
}

export type EvidenceViewModel = {
  manifestPath: string
  runId: string
  unit: string
  leanPath: string
  entry: EvidenceEntry
  diagnostics: EvidenceManifest["diagnostics"]
  qualityContract?: EvidenceManifest["qualityContract"]
  semanticUncertainties: SemanticUncertainty[]
  evidence: Array<Evidence & {
    sourceUri: string
    sourceVerified: boolean
    sourceProblem?: string
    excerpt?: string
  }>
}
