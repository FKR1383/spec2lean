import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { canonicalJson } from "./semantic-ir/canonical.js"
import {
  materializeSemanticView,
  SemanticIrValidationError,
} from "./semantic-ir/materialize.js"
import { createDeltaCriticPacket } from "./semantic-ir/review-packet.js"
import type {
  InstructionSemanticDelta,
  SharedSemanticEnvironment,
} from "./semantic-ir/types.js"
import {
  validateInstructionSemanticDelta,
  validateSharedSemanticEnvironment,
} from "./semantic-ir/validate.js"
import { REPO_ROOT } from "./repo.js"

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`SEMANTIC_IR_SELF_TEST_FAILED: ${message}`)
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function hasCode(
  result: ReturnType<typeof validateInstructionSemanticDelta>,
  code: string,
): boolean {
  return result.issues.some((issue) => issue.code === code)
}

function reverseSemanticCollections(shared: SharedSemanticEnvironment): void {
  shared.scope.eligibilityRequirements.reverse()
  shared.scope.excludedFeatures.reverse()
  shared.entries.reverse()
  shared.evidence.reverse()
  shared.sourceManifests.reverse()
  shared.review.records.reverse()
  for (const entry of shared.entries) {
    entry.evidenceIds.reverse()
    entry.dependencyIds.reverse()
    entry.humanApprovalDependencies.reverse()
    entry.provenance.originatingArtifacts.reverse()
    entry.provenance.reviewRecords.reverse()
    entry.provenance.acceptedUnitSupport.reverse()
    for (const support of entry.provenance.acceptedUnitSupport) {
      support.acceptedEvidenceIds.reverse()
      support.artifacts.reverse()
      support.reviewRecords.reverse()
    }
  }
}

function reverseDeltaCollections(delta: InstructionSemanticDelta): void {
  delta.sharedReferences.reverse()
  delta.evidence.reverse()
  delta.claims.reverse()
  delta.refinements.reverse()
  delta.syntaxForms.reverse()
  delta.operands.reverse()
  delta.stateEffects.reverse()
  delta.preconditions.reverse()
  delta.proofFamilies.reverse()
  for (const claim of [...delta.claims, ...delta.refinements]) {
    claim.evidenceIds.reverse()
    claim.dependencyIds.reverse()
    claim.humanApprovalDependencies.reverse()
  }
  for (const value of [
    ...delta.syntaxForms,
    ...delta.operands,
    delta.operation,
    ...delta.stateEffects,
    ...delta.preconditions,
    ...delta.proofFamilies,
  ]) {
    value.semanticClaimIds.reverse()
  }
  for (const operand of delta.operands) operand.legalForms.reverse()
  for (const family of delta.proofFamilies) family.blockedBySemanticIds.reverse()
}

export async function runSemanticIrSelfTests(): Promise<{
  deltaBytes: number
  materializedBytes: number
  criticPacketBytes: number
  legacyAcceptedBytes: number
}> {
  for (const schema of [
    "common.schema.json",
    "shared-environment.schema.json",
    "instruction-delta.schema.json",
    "full-semantics.schema.json",
    "language-core.schema.json",
    "semantic-profile.schema.json",
  ]) {
    JSON.parse(
      await readFile(resolve(REPO_ROOT, "ir/semantic", schema), "utf8"),
    )
  }
  const productionShell = JSON.parse(
    await readFile(
      resolve(
        REPO_ROOT,
        "language_packs/ptx/9.3/semantic/shared-environment-draft-v1.json",
      ),
      "utf8",
    ),
  ) as SharedSemanticEnvironment
  const shellResult = validateSharedSemanticEnvironment(productionShell)
  assert(shellResult.ok, "production shared-environment shell is structurally valid")
  assert(
    productionShell.review.status === "DRAFT" && productionShell.entries.length === 0,
    "production shell does not imply shared semantic approval",
  )

  const fixtureRoot = resolve(REPO_ROOT, "tests/fixtures/semantic-ir")
  const sharedText = await readFile(
    resolve(fixtureRoot, "shared-environment.valid.json"),
    "utf8",
  )
  const deltaText = await readFile(
    resolve(fixtureRoot, "instruction-delta.valid.json"),
    "utf8",
  )
  const shared = JSON.parse(sharedText) as SharedSemanticEnvironment
  const delta = JSON.parse(deltaText) as InstructionSemanticDelta

  const validShared = validateSharedSemanticEnvironment(shared)
  assert(validShared.ok, "valid shared semantic environment")

  const missingShared = clone(delta)
  missingShared.sharedReferences[0]!.semanticId = "ptx.fixture.missing"
  assert(
    hasCode(
      validateInstructionSemanticDelta(missingShared, shared),
      "UNKNOWN_SHARED_SEMANTIC_ID",
    ),
    "missing shared semantic reference",
  )

  const sourceFactWithoutEvidence = clone(delta)
  sourceFactWithoutEvidence.claims[0]!.evidenceIds = []
  assert(
    hasCode(
      validateInstructionSemanticDelta(sourceFactWithoutEvidence, shared),
      "SOURCE_FACT_MISSING_EVIDENCE",
    ),
    "SOURCE_FACT missing evidence",
  )

  const invalidClassification = clone(delta) as unknown as {
    claims: Array<{ classification: string }>
  }
  invalidClassification.claims[0]!.classification = "MODEL_FACT"
  assert(
    hasCode(
      validateInstructionSemanticDelta(invalidClassification, shared),
      "INVALID_CLASSIFICATION",
    ),
    "invalid claim classification",
  )

  const duplicateIds = clone(delta)
  duplicateIds.claims.push(clone(duplicateIds.claims[0]!))
  assert(
    hasCode(
      validateInstructionSemanticDelta(duplicateIds, shared),
      "DUPLICATE_SEMANTIC_ID",
    ),
    "duplicate semantic IDs",
  )

  const stateGap = clone(delta)
  stateGap.claims.push({
    semanticId: "ptx.and-b32.fixture.unresolved-state-gap",
    classification: "OPEN_QUESTION",
    statement: "Fixture unresolved state-affecting question.",
    evidenceIds: [],
    dependencyIds: [],
    stateAffecting: true,
    humanApprovalDependencies: [],
    lifecycle: { status: "ACTIVE", introducedInRevision: 1 },
  })
  const stateGapResult = validateInstructionSemanticDelta(stateGap, shared)
  assert(stateGapResult.ok, "state gap remains structurally reviewable")
  assert(
    stateGapResult.unresolvedStateAffectingSemanticIds.includes(
      "ptx.and-b32.fixture.unresolved-state-gap",
    ),
    "unresolved state-affecting open question detected",
  )

  const validDelta = validateInstructionSemanticDelta(delta, shared)
  assert(validDelta.ok, "valid simple semantic delta")
  assert(
    validDelta.unresolvedStateAffectingSemanticIds.length === 0,
    "valid delta has no state-affecting gaps",
  )

  const firstView = materializeSemanticView(shared, delta)
  const secondView = materializeSemanticView(shared, delta)
  assert(
    canonicalJson(firstView) === canonicalJson(secondView),
    "deterministic materialization",
  )
  assert(
    firstView.claims.some(
      (claim) =>
        claim.semanticId === "ptx.fixture.guard.syntax" &&
        claim.origin.kind === "SHARED",
    ),
    "transitive shared dependency materialized",
  )
  assert(
    firstView.claims.some(
      (claim) =>
        claim.classification === "SOURCE_FACT" && claim.origin.kind === "DELTA",
    ) &&
      firstView.claims.some(
        (claim) =>
          claim.classification === "DERIVED_INTERPRETATION" &&
          claim.origin.kind === "REFINEMENT",
      ),
    "classification and origin remain separate",
  )
  let draftRejected = false
  try {
    materializeSemanticView(productionShell, delta)
  } catch (error) {
    draftRejected =
      error instanceof SemanticIrValidationError &&
      error.codes.includes("SHARED_ENVIRONMENT_NOT_HUMAN_APPROVED")
  }
  assert(draftRejected, "production materialization rejects an unapproved environment")

  const reorderedShared = clone(shared)
  const reorderedDelta = clone(delta)
  reverseSemanticCollections(reorderedShared)
  reverseDeltaCollections(reorderedDelta)
  const reorderedView = materializeSemanticView(reorderedShared, reorderedDelta)
  assert(
    canonicalJson(firstView) === canonicalJson(reorderedView),
    "materialization reproducibility and stable ordering",
  )

  const changedEnvironment = clone(shared)
  changedEnvironment.entries[0]!.statement += " Changed after pinning."
  assert(
    hasCode(
      validateInstructionSemanticDelta(delta, changedEnvironment),
      "SHARED_ENVIRONMENT_HASH_MISMATCH",
    ),
    "shared semantic content change invalidates delta pin",
  )
  const changedProvenance = clone(shared)
  changedProvenance.sourceManifests[0]!.sha256 = "0".repeat(64)
  assert(
    hasCode(
      validateInstructionSemanticDelta(delta, changedProvenance),
      "SHARED_ENVIRONMENT_HASH_MISMATCH",
    ),
    "shared provenance change invalidates delta pin",
  )

  const implicitAssumption = clone(delta)
  implicitAssumption.claims.push({
    semanticId: "ptx.and-b32.fixture.unapproved-assumption",
    classification: "ASSUMPTION",
    statement: "Fixture invalid implicit assumption.",
    evidenceIds: [],
    dependencyIds: [],
    stateAffecting: true,
    humanApprovalDependencies: [],
    lifecycle: { status: "ACTIVE", introducedInRevision: 1 },
  })
  assert(
    hasCode(
      validateInstructionSemanticDelta(implicitAssumption, shared),
      "ASSUMPTION_MISSING_HUMAN_APPROVAL",
    ),
    "assumptions require explicit human approval dependency",
  )

  const invalidRefinement = clone(delta)
  invalidRefinement.refinements[0]!.targetSharedSemanticId = "ptx.fixture.missing"
  assert(
    hasCode(
      validateInstructionSemanticDelta(invalidRefinement, shared),
      "INVALID_REFINEMENT_TARGET",
    ),
    "override/refinement target validation",
  )

  const criticPacket = createDeltaCriticPacket(shared, delta)
  assert(
    criticPacket.deltaByClassification.SOURCE_FACT.length === 1 &&
      criticPacket.sharedDependencies.length === 3,
    "compact critic packet separates delta from shared dependencies",
  )
  assert(
    criticPacket.fallback.deterministicViewId === firstView.viewId,
    "full-view fallback remains available",
  )

  const legacyAcceptedText = await readFile(
    resolve(
      REPO_ROOT,
      "accepted/ptx/9.3/and-b32/semantics/semantics-v2.json",
    ),
    "utf8",
  )
  return {
    deltaBytes: Buffer.byteLength(deltaText, "utf8"),
    materializedBytes: Buffer.byteLength(canonicalJson(firstView), "utf8"),
    criticPacketBytes: Buffer.byteLength(canonicalJson(criticPacket), "utf8"),
    legacyAcceptedBytes: Buffer.byteLength(legacyAcceptedText, "utf8"),
  }
}
