import {
  normalizeInstructionSemanticDelta,
  normalizeSharedEnvironment,
  semanticDeltaSha256,
  sharedEnvironmentSha256,
} from "./document.js"
import type {
  EvidenceRecord,
  InstructionSemanticDelta,
  MaterializedClaim,
  MaterializedSemanticView,
  SharedSemanticEntry,
  SharedSemanticEnvironment,
} from "./types.js"
import {
  validateInstructionSemanticDelta,
  validateSharedSemanticEnvironment,
} from "./validate.js"

export class SemanticIrValidationError extends Error {
  constructor(readonly codes: string[]) {
    super(`Semantic IR validation failed: ${codes.join(", ")}`)
    this.name = "SemanticIrValidationError"
  }
}

function selectedSharedEntries(
  environment: SharedSemanticEnvironment,
  delta: InstructionSemanticDelta,
): SharedSemanticEntry[] {
  const byId = new Map(environment.entries.map((entry) => [entry.semanticId, entry]))
  const selected = new Set(delta.sharedReferences.map((reference) => reference.semanticId))
  const pending = [...selected]
  while (pending.length > 0) {
    const id = pending.pop()
    if (id === undefined) continue
    for (const dependencyId of byId.get(id)?.dependencyIds ?? []) {
      if (!selected.has(dependencyId)) {
        selected.add(dependencyId)
        pending.push(dependencyId)
      }
    }
  }
  return [...selected]
    .map((id) => byId.get(id))
    .filter((entry): entry is SharedSemanticEntry => entry !== undefined)
    .sort((left, right) => left.semanticId.localeCompare(right.semanticId))
}

function materializedSharedClaim(
  entry: SharedSemanticEntry,
  environment: SharedSemanticEnvironment,
): MaterializedClaim {
  const {
    specificationVersion: _specificationVersion,
    scope: _scope,
    review,
    ...claim
  } = entry
  return {
    ...claim,
    origin: {
      kind: "SHARED",
      environmentId: environment.environmentId,
      revision: environment.revision,
    },
    sharedReview: review,
  }
}

/**
 * Compose a complete instruction view without mutating or silently replacing
 * shared claims. Overrides and refinements remain explicit, independently
 * classified claims linked to their reviewed target.
 */
export function materializeSemanticView(
  sharedInput: unknown,
  deltaInput: unknown,
  options: { requireHumanApprovedEnvironment?: boolean } = {},
): MaterializedSemanticView {
  const sharedResult = validateSharedSemanticEnvironment(sharedInput)
  if (!sharedResult.ok || sharedResult.value === undefined) {
    throw new SemanticIrValidationError(sharedResult.issues.map((issue) => issue.code))
  }
  const shared = normalizeSharedEnvironment(sharedResult.value)
  if (
    options.requireHumanApprovedEnvironment !== false &&
    shared.review.status !== "HUMAN_APPROVED"
  ) {
    throw new SemanticIrValidationError(["SHARED_ENVIRONMENT_NOT_HUMAN_APPROVED"])
  }

  const deltaResult = validateInstructionSemanticDelta(deltaInput, shared)
  if (!deltaResult.ok || deltaResult.value === undefined) {
    throw new SemanticIrValidationError(deltaResult.issues.map((issue) => issue.code))
  }
  const delta = normalizeInstructionSemanticDelta(deltaResult.value)
  const sharedEntries = selectedSharedEntries(shared, delta)
  const sharedClaims = sharedEntries.map((entry) => materializedSharedClaim(entry, shared))
  const deltaClaims: MaterializedClaim[] = delta.claims.map((claim) => ({
    ...claim,
    origin: { kind: "DELTA", deltaId: delta.deltaId },
  }))
  const refinementClaims: MaterializedClaim[] = delta.refinements.map((refinement) => {
    const { targetSharedSemanticId, kind, rationale, ...claim } = refinement
    return {
      ...claim,
      origin: {
        kind: "REFINEMENT",
        deltaId: delta.deltaId,
        targetSharedSemanticId,
        refinementKind: kind,
        rationale,
      },
    }
  })
  const claims = [...sharedClaims, ...deltaClaims, ...refinementClaims].sort(
    (left, right) => left.semanticId.localeCompare(right.semanticId),
  )

  const localClaimEvidenceIds = new Set(
    [...delta.claims, ...delta.refinements].flatMap((claim) => claim.evidenceIds),
  )
  const sharedEvidenceIds = new Set([
    ...sharedEntries.flatMap((entry) => entry.evidenceIds),
    ...shared.evidence
      .filter((record) => localClaimEvidenceIds.has(record.evidenceId))
      .map((record) => record.evidenceId),
  ])
  const deltaEvidenceIds = new Set(
    [...delta.claims, ...delta.refinements].flatMap((claim) => claim.evidenceIds),
  )
  const evidence: Array<EvidenceRecord & { origin: "SHARED" | "DELTA" }> = [
    ...shared.evidence
      .filter((record) => sharedEvidenceIds.has(record.evidenceId))
      .map((record) => ({ ...record, origin: "SHARED" as const })),
    ...delta.evidence
      .filter((record) => deltaEvidenceIds.has(record.evidenceId))
      .map((record) => ({ ...record, origin: "DELTA" as const })),
  ].sort((left, right) => left.evidenceId.localeCompare(right.evidenceId))

  const unresolvedStateAffectingSemanticIds = claims
    .filter(
      (claim) =>
        claim.classification === "OPEN_QUESTION" &&
        claim.stateAffecting &&
        claim.lifecycle.status === "ACTIVE",
    )
    .map((claim) => claim.semanticId)
    .sort((left, right) => left.localeCompare(right))

  return {
    schemaVersion: 1,
    viewId: `${delta.deltaId}@${shared.environmentId}:r${shared.revision}`,
    unit: { ...delta.unit },
    generatedFrom: {
      sharedEnvironmentId: shared.environmentId,
      sharedEnvironmentRevision: shared.revision,
      sharedEnvironmentSha256: sharedEnvironmentSha256(shared),
      deltaId: delta.deltaId,
      deltaSha256: semanticDeltaSha256(delta),
      deltaProvenance: { ...delta.provenance },
    },
    evidence,
    claims,
    syntaxForms: delta.syntaxForms,
    operands: delta.operands,
    operation: delta.operation,
    stateEffects: delta.stateEffects,
    preconditions: delta.preconditions,
    proofFamilies: delta.proofFamilies,
    unresolvedStateAffectingSemanticIds,
  }
}
