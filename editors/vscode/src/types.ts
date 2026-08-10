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
  alignmentMethod?: "EXACT_QUOTE_TOKEN_MATCH"
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
}

export type EvidenceManifest = {
  schemaVersion: 1 | 2
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
  sourceBundle?: ArtifactFingerprint
  sourceBundles?: ArtifactFingerprint[]
  theoremDocument?: ArtifactFingerprint
  entries: EvidenceEntry[]
  diagnostics: {
    declarationsWithoutReferences: string[]
    unresolvedReferences: string[]
    pdfAlignment?: {
      matched: number
      ambiguous: string[]
      unmatched: string[]
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
  evidence: Array<Evidence & {
    sourceUri: string
    sourceVerified: boolean
    sourceProblem?: string
    excerpt?: string
  }>
}
