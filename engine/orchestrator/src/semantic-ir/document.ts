import { canonicalSha256 } from "./canonical.js"
import type {
  ContentFingerprint,
  EvidenceRecord,
  InstructionSemanticDelta,
  SemanticClaim,
  SharedSemanticEntry,
  SharedSemanticEnvironment,
} from "./types.js"

function sortedStrings(values: string[]): string[] {
  return [...values].sort((left, right) => left.localeCompare(right))
}

function sortedFingerprints(values: ContentFingerprint[]): ContentFingerprint[] {
  return [...values].sort((left, right) =>
    left.path.localeCompare(right.path) || left.sha256.localeCompare(right.sha256),
  )
}

function normalizeClaim<T extends SemanticClaim>(claim: T): T {
  return {
    ...claim,
    evidenceIds: sortedStrings(claim.evidenceIds),
    dependencyIds: sortedStrings(claim.dependencyIds),
    humanApprovalDependencies: sortedStrings(claim.humanApprovalDependencies),
    lifecycle: {
      ...claim.lifecycle,
      supersedes:
        claim.lifecycle.supersedes === undefined
          ? undefined
          : sortedStrings(claim.lifecycle.supersedes),
    },
  }
}

function normalizeEvidence(evidence: EvidenceRecord): EvidenceRecord {
  return { ...evidence, locator: { ...evidence.locator }, source: { ...evidence.source } }
}

function normalizeSharedEntry(entry: SharedSemanticEntry): SharedSemanticEntry {
  return {
    ...normalizeClaim(entry),
    provenance: {
      originatingArtifacts: sortedFingerprints(entry.provenance.originatingArtifacts),
      reviewRecords: sortedFingerprints(entry.provenance.reviewRecords),
    },
  }
}

/** Normalize semantically unordered collections before hashing or materializing. */
export function normalizeSharedEnvironment(
  environment: SharedSemanticEnvironment,
): SharedSemanticEnvironment {
  return {
    ...environment,
    review: {
      ...environment.review,
      records: sortedFingerprints(environment.review.records),
    },
    sourceManifests: sortedFingerprints(environment.sourceManifests),
    evidence: environment.evidence
      .map(normalizeEvidence)
      .sort((left, right) => left.evidenceId.localeCompare(right.evidenceId)),
    entries: environment.entries
      .map(normalizeSharedEntry)
      .sort((left, right) => left.semanticId.localeCompare(right.semanticId)),
  }
}

export function sharedEnvironmentSha256(
  environment: SharedSemanticEnvironment,
): string {
  return canonicalSha256(normalizeSharedEnvironment(environment))
}

function withSortedClaimIds<T extends { semanticClaimIds: string[] }>(value: T): T {
  return { ...value, semanticClaimIds: sortedStrings(value.semanticClaimIds) }
}

export function normalizeInstructionSemanticDelta(
  delta: InstructionSemanticDelta,
): InstructionSemanticDelta {
  return {
    ...delta,
    sharedReferences: [...delta.sharedReferences].sort((left, right) =>
      left.semanticId.localeCompare(right.semanticId),
    ),
    evidence: delta.evidence
      .map(normalizeEvidence)
      .sort((left, right) => left.evidenceId.localeCompare(right.evidenceId)),
    claims: delta.claims
      .map(normalizeClaim)
      .sort((left, right) => left.semanticId.localeCompare(right.semanticId)),
    refinements: delta.refinements
      .map(normalizeClaim)
      .sort((left, right) => left.semanticId.localeCompare(right.semanticId)),
    syntaxForms: delta.syntaxForms
      .map(withSortedClaimIds)
      .sort((left, right) => left.syntaxId.localeCompare(right.syntaxId)),
    operands: delta.operands
      .map((operand) => ({
        ...withSortedClaimIds(operand),
        legalForms: sortedStrings(operand.legalForms),
      }))
      .sort((left, right) =>
        left.position - right.position || left.operandId.localeCompare(right.operandId),
      ),
    operation: withSortedClaimIds(delta.operation),
    stateEffects: delta.stateEffects
      .map(withSortedClaimIds)
      .sort((left, right) => left.effectId.localeCompare(right.effectId)),
    preconditions: delta.preconditions
      .map(withSortedClaimIds)
      .sort((left, right) => left.preconditionId.localeCompare(right.preconditionId)),
    proofFamilies: delta.proofFamilies
      .map((family) => ({
        ...withSortedClaimIds(family),
        blockedBySemanticIds: sortedStrings(family.blockedBySemanticIds),
      }))
      .sort((left, right) => left.proofFamilyId.localeCompare(right.proofFamilyId)),
  }
}

export function semanticDeltaSha256(delta: InstructionSemanticDelta): string {
  return canonicalSha256(normalizeInstructionSemanticDelta(delta))
}
