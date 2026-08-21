import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun } from "./artifact-contract.js"
import { buildGeneralPrompt } from "./runner.js"
import {
  assessSemanticFastPath,
  assessSemanticFastPathDocuments,
  evaluateSemanticDeltaDocuments,
  markSemanticV2Fallback,
  prepareSemanticV2Run,
  type SemanticProfile,
} from "./semantic-v2.js"
import type {
  InstructionSemanticDelta,
  SharedSemanticEnvironment,
} from "./semantic-ir/types.js"
import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"
import { semanticV2Telemetry } from "./semantic-v2-telemetry.js"

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`SEMANTIC_V2_SELF_TEST_FAILED: ${message}`)
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function testRun(stage: RunState["stage"]): RunState {
  return {
    schemaVersion: 1,
    runId: "semantic-v2-self-test",
    mode: "formalization",
    language: "ptx",
    specVersion: "9.3",
    unit: "and.b32",
    unitSlug: "and-b32-self-test",
    leanModuleName: "AndB32SelfTest",
    sourceManifest: "documents/sources/nvidia/ptx/9.3/source-manifest.json",
    artifactRoot: "tests/fixtures/semantic-v2/output",
    stage,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    revision: 1,
    gates: {
      A: "approved",
      B: "pending",
      C: "pending",
      THEOREM_STRENGTH: "pending",
      FINAL: "pending",
    },
    history: [
      {
        at: "2026-01-01T00:00:00.000Z",
        from: "SOURCE_CURATION",
        to: stage,
        reason: "synthetic semantic v2 integration fixture",
      },
    ],
  }
}

function fixtureProfile(shared: SharedSemanticEnvironment): SemanticProfile {
  return {
    schemaVersion: 1,
    language: "PTX",
    specificationVersion: "9.3",
    languageCorePath: "language_packs/ptx/9.3/language-core.json",
    strategy: "DELTA_PREFERRED_WITH_LEGACY_FALLBACK",
    sharedEnvironmentPath: "tests/fixtures/semantic-ir/shared-environment.valid.json",
    supportedUnitPatterns: ["^and\\.b32$"],
    requiredSharedSemanticIds: [
      "ptx.fixture.guard.noop",
      "ptx.fixture.register.lookup-design",
    ],
    requiredSharedClassifications: {
      "ptx.fixture.guard.noop": "DERIVED_INTERPRETATION",
      "ptx.fixture.register.lookup-design": "DESIGN_DEPENDENCY",
    },
    approval: {
      reviewCandidatePath: "tests/fixtures/semantic-v2/review-candidate.json",
      humanReviewPacketPath: "tests/fixtures/semantic-v2/review-packet.md",
      approvedEnvironmentPath: "tests/fixtures/semantic-v2/approved-environment.json",
      approvalRecordPath: "tests/fixtures/semantic-v2/approval-record.json",
    },
    safety: {
      requireHumanApprovedEnvironment: true,
      requireActiveApprovedEntries: true,
      blockStateAffectingOpenQuestions: true,
      verifySourceBundleFingerprint: true,
      verifyOfficialEvidenceFingerprints: true,
    },
    fallback: {
      enabled: true,
      mode: "LEGACY_FULL_SEMANTICS",
      description: `Synthetic fast-path profile for ${shared.environmentId}`,
    },
  }
}

export async function runSemanticV2SelfTests(): Promise<{
  productionMode: string
  productionEligibility: string
  missingSharedSemanticIds: number
}> {
  const fixtureRoot = resolve(REPO_ROOT, "tests/fixtures/semantic-ir")
  const shared = JSON.parse(
    await readFile(resolve(fixtureRoot, "shared-environment.valid.json"), "utf8"),
  ) as SharedSemanticEnvironment
  const delta = JSON.parse(
    await readFile(resolve(fixtureRoot, "instruction-delta.valid.json"), "utf8"),
  ) as InstructionSemanticDelta
  const extractionRun = testRun("SEMANTIC_EXTRACTION")

  const eligibility = assessSemanticFastPathDocuments(
    extractionRun,
    "tests/fixtures/semantic-v2/profile.json",
    fixtureProfile(shared),
    shared,
  )
  assert(eligibility.eligible, "approved fixture environment enables bounded fast path")

  const fastRun: RunState = {
    ...extractionRun,
    semanticV2: {
      profilePath: eligibility.profilePath,
      sharedEnvironmentPath: eligibility.sharedEnvironmentPath,
      mode: "DELTA_FAST_PATH",
      environment: {
        environmentId: shared.environmentId,
        revision: shared.revision,
        sha256: eligibility.environmentSha256!,
        reviewStatus: shared.review.status,
      },
      missingRequiredSemanticIds: [],
      current: {
        attempt: 1,
        deltaPath: `${extractionRun.artifactRoot}/semantics/semantic-delta-v1.json`,
        materializedPath: `${extractionRun.artifactRoot}/semantics/semantics-v1.json`,
        criticPacketPath: `${extractionRun.artifactRoot}/reviews/semantic-delta-critic-packet-v1.json`,
      },
      events: [],
    },
  }
  assert(
    artifactContractForRun(fastRun).outputPath.endsWith("semantic-delta-v1.json"),
    "fast extraction contract requests a delta",
  )
  const repairRun = await prepareSemanticV2Run({
    ...fastRun,
    executions: [{
      startedAt: "2026-01-01T00:00:01.000Z",
      at: "2026-01-01T00:00:02.000Z",
      stage: "SEMANTIC_EXTRACTION",
      agent: "semantic-extractor-delta",
      sessionId: "semantic-v2-repair-fixture",
      outcome: "RETRY",
      nextStage: "SEMANTIC_EXTRACTION",
      response: "mandatory proof requirement missing",
      artifactProduced: true,
    }],
  })
  assert(
    repairRun.semanticV2?.current?.attempt === 2 &&
      repairRun.semanticV2.current.deltaPath.endsWith("semantic-delta-v2.json") &&
      repairRun.semanticV2.events.at(-1)?.kind === "REPAIR_ATTEMPT",
    "failed delta validation advances to a new immutable repair revision",
  )
  const fastPrompt = buildGeneralPrompt(fastRun)
  assert(
    fastPrompt.includes("Generate ONLY the typed instruction-specific semantic delta"),
    "fast extractor receives delta-only contract",
  )

  const valid = evaluateSemanticDeltaDocuments(shared, delta)
  assert(valid.ok && valid.view !== undefined && valid.packet !== undefined, "valid delta fast path succeeds")
  assert(
    valid.packet.packetKind === "SEMANTIC_DELTA_CRITIC" &&
      valid.packet.fallback.kind === "MATERIALIZED_FULL_VIEW",
    "fast path constructs compact packet with full-view fallback",
  )

  const critiqueRun: RunState = { ...fastRun, stage: "SEMANTIC_CRITIQUE" }
  const criticPrompt = buildGeneralPrompt(critiqueRun)
  assert(
    criticPrompt.includes(fastRun.semanticV2!.current!.criticPacketPath) &&
      criticPrompt.includes("Read the compact packet first") &&
      criticPrompt.includes(fastRun.semanticV2!.current!.materializedPath),
    "Semantic Critic receives compact packet and full fallback path",
  )

  const invalidDelta = clone(delta)
  invalidDelta.claims[0]!.evidenceIds = []
  const invalid = evaluateSemanticDeltaDocuments(shared, invalidDelta)
  assert(!invalid.ok && invalid.issues.some((issue) => issue.includes("SOURCE_FACT_MISSING_EVIDENCE")), "invalid delta cannot pass fast validation")

  const ungroundedDelta = clone(delta)
  delete ungroundedDelta.evidence[0]!.sourceBundleEvidenceId
  const ungrounded = evaluateSemanticDeltaDocuments(shared, ungroundedDelta)
  assert(
    !ungrounded.ok &&
      ungrounded.issues.some((issue) => issue.includes("SOURCE_FACT_MISSING_BUNDLE_TRACE")),
    "SOURCE_FACT without bounded-bundle grounding cannot pass fast validation",
  )

  const missingDependency = clone(delta)
  missingDependency.sharedReferences[0]!.semanticId = "ptx.fixture.not-present"
  const missing = evaluateSemanticDeltaDocuments(shared, missingDependency)
  assert(!missing.ok && missing.issues.some((issue) => issue.includes("UNKNOWN_SHARED_SEMANTIC_ID")), "missing shared dependency cannot silently pass")

  const stateQuestion = clone(delta)
  stateQuestion.claims.push({
    semanticId: "ptx.fixture.fast-path-state-question",
    classification: "OPEN_QUESTION",
    statement: "Synthetic unresolved state-affecting question.",
    evidenceIds: [],
    dependencyIds: [],
    stateAffecting: true,
    humanApprovalDependencies: [],
    lifecycle: { status: "ACTIVE", introducedInRevision: 1 },
  })
  const stateBlocked = evaluateSemanticDeltaDocuments(shared, stateQuestion)
  assert(
    !stateBlocked.ok &&
      stateBlocked.unresolvedStateAffectingSemanticIds.includes("ptx.fixture.fast-path-state-question"),
    "state-affecting OPEN_QUESTION blocks fast acceptance",
  )

  const fallbackRun = markSemanticV2Fallback(
    fastRun,
    "TEST_INVALID_DELTA",
    "synthetic validation failure",
  )
  assert(
    fallbackRun.semanticV2?.mode === "LEGACY_FALLBACK" &&
      artifactContractForRun(fallbackRun).outputPath.endsWith("semantics-v2.json"),
    "invalid fast path explicitly restores legacy artifact contract",
  )
  const fallbackPrompt = buildGeneralPrompt(fallbackRun)
  assert(
    fallbackPrompt.includes("Explicit Semantic v3 Full-Semantics Fallback") &&
      fallbackPrompt.includes("complete schemaVersion=3 full-instruction semantics"),
    "full-semantics v3 fallback remains executable",
  )
  const fallbackTelemetry = semanticV2Telemetry(fallbackRun)
  assert(
    fallbackTelemetry.mode === "LEGACY_FALLBACK" &&
      typeof fallbackTelemetry.fallbackReason === "string",
    "v2 telemetry exposes fallback without reporting fast-path success",
  )

  const productionAssessment = await assessSemanticFastPath(extractionRun)
  assert(
    productionAssessment.eligible &&
      productionAssessment.code === "DELTA_FAST_PATH_ELIGIBLE",
    "approved production environment deterministically enables fast path",
  )
  assert(
    productionAssessment.missingRequiredSemanticIds.length === 0,
    "approved production environment satisfies every required shared semantic dependency",
  )
  const productionRun = await prepareSemanticV2Run(extractionRun)
  assert(
    productionRun.semanticV2?.mode === "DELTA_FAST_PATH" &&
      artifactContractForRun(productionRun).outputPath.endsWith("semantic-delta-v1.json") &&
      buildGeneralPrompt(productionRun).includes("Semantic Architecture v3 — LANGUAGE-CORE DELTA FAST PATH"),
    "current production profile executes the bounded delta semantic path",
  )

  return {
    productionMode: "DELTA_FAST_PATH",
    productionEligibility: `${productionAssessment.code}: ${productionAssessment.detail}`,
    missingSharedSemanticIds: productionAssessment.missingRequiredSemanticIds.length,
  }
}
