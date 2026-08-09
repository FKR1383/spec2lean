import { canonicalJson } from "./canonical.js"
import { semanticDeltaSha256, sharedEnvironmentSha256 } from "./document.js"
import { materializeSemanticView } from "./materialize.js"
import type {
  ClaimClassification,
  InstructionSemanticDelta,
  MaterializedClaim,
  SharedSemanticEnvironment,
} from "./types.js"

type ReviewClaim = Pick<
  MaterializedClaim,
  | "semanticId"
  | "classification"
  | "statement"
  | "evidenceIds"
  | "dependencyIds"
  | "stateAffecting"
  | "humanApprovalDependencies"
  | "origin"
>

export type DeltaCriticPacket = {
  schemaVersion: 1
  packetKind: "SEMANTIC_DELTA_CRITIC"
  unit: InstructionSemanticDelta["unit"]
  pins: {
    sharedEnvironmentId: string
    sharedEnvironmentRevision: number
    sharedEnvironmentSha256: string
    deltaId: string
    deltaSha256: string
    deltaSourceBundle: InstructionSemanticDelta["provenance"]["sourceBundle"]
  }
  sharedDependencies: Array<{
    semanticId: string
    classification: ClaimClassification
    statement: string
    environmentReviewStatus: SharedSemanticEnvironment["review"]["status"]
  }>
  deltaByClassification: Record<ClaimClassification, ReviewClaim[]>
  refinements: Array<{
    semanticId: string
    targetSharedSemanticId: string
    kind: "REFINES" | "OVERRIDES"
    rationale: string
  }>
  unresolvedStateAffectingSemanticIds: string[]
  fallback: {
    kind: "MATERIALIZED_FULL_VIEW"
    deterministicViewId: string
    canonicalBytes: number
  }
}

export function createDeltaCriticPacket(
  shared: SharedSemanticEnvironment,
  delta: InstructionSemanticDelta,
): DeltaCriticPacket {
  const fullView = materializeSemanticView(shared, delta)
  const deltaClaims = fullView.claims.filter((claim) => claim.origin.kind !== "SHARED")
  const byClassification = (classification: ClaimClassification): ReviewClaim[] =>
    deltaClaims.filter((claim) => claim.classification === classification)
  const deltaByClassification: DeltaCriticPacket["deltaByClassification"] = {
    SOURCE_FACT: byClassification("SOURCE_FACT"),
    DERIVED_INTERPRETATION: byClassification("DERIVED_INTERPRETATION"),
    DESIGN_DEPENDENCY: byClassification("DESIGN_DEPENDENCY"),
    ASSUMPTION: byClassification("ASSUMPTION"),
    OPEN_QUESTION: byClassification("OPEN_QUESTION"),
  }

  return {
    schemaVersion: 1,
    packetKind: "SEMANTIC_DELTA_CRITIC",
    unit: fullView.unit,
    pins: {
      sharedEnvironmentId: shared.environmentId,
      sharedEnvironmentRevision: shared.revision,
      sharedEnvironmentSha256: sharedEnvironmentSha256(shared),
      deltaId: delta.deltaId,
      deltaSha256: semanticDeltaSha256(delta),
      deltaSourceBundle: { ...delta.provenance.sourceBundle },
    },
    sharedDependencies: fullView.claims
      .filter((claim) => claim.origin.kind === "SHARED")
      .map((claim) => ({
        semanticId: claim.semanticId,
        classification: claim.classification,
        statement: claim.statement,
        environmentReviewStatus: shared.review.status,
      })),
    deltaByClassification,
    refinements: [...delta.refinements]
      .sort((left, right) => left.semanticId.localeCompare(right.semanticId))
      .map((refinement) => ({
        semanticId: refinement.semanticId,
        targetSharedSemanticId: refinement.targetSharedSemanticId,
        kind: refinement.kind,
        rationale: refinement.rationale,
      })),
    unresolvedStateAffectingSemanticIds:
      fullView.unresolvedStateAffectingSemanticIds,
    fallback: {
      kind: "MATERIALIZED_FULL_VIEW",
      deterministicViewId: fullView.viewId,
      canonicalBytes: Buffer.byteLength(canonicalJson(fullView), "utf8"),
    },
  }
}
