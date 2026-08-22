import { createHash } from "node:crypto"
import { mkdir, readFile, rm, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"

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
import { canonicalSemanticDeltaForRun } from "./semantic-delta-authoring.js"

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

  const canonicalRoot = "candidates/self-test/semantic-delta-authoring"
  const canonicalBundlePath = `${canonicalRoot}/source-bundle.json`
  const sourceDocuments = new Map<string, {
    document_id: string
    kind: string
    local_path: string
    sha256: string
  }>()
  const fragments = delta.evidence.map((record, index) => {
    const existingDocument = sourceDocuments.get(record.source.documentPath)
    const documentId = existingDocument?.document_id ?? `document-${sourceDocuments.size + 1}`
    if (existingDocument === undefined) {
      sourceDocuments.set(record.source.documentPath, {
        document_id: documentId,
        kind: record.source.kind.toUpperCase(),
        local_path: record.source.documentPath,
        sha256: record.source.documentSha256,
      })
    }
    return {
      fragment_id: record.sourceBundleEvidenceId!,
      document_id: documentId,
      source_kind: record.source.kind.toUpperCase(),
      source_sha256: record.source.documentSha256,
      exact_quote: record.quotation ?? "synthetic exact source quotation",
      locator: {
        ...record.locator,
        start_line: record.locator.startLine,
        end_line: record.locator.endLine,
      },
      reason_for_inclusion: "structured delta writer regression fixture",
    }
  })
  const canonicalBundle = {
    schema_version: 3,
    language: "ptx",
    specification_version: "9.3",
    unit: "and.b32",
    source_documents: [...sourceDocuments.values()],
    fragments,
  }
  const canonicalBundleText = `${JSON.stringify(canonicalBundle, null, 2)}\n`
  await mkdir(dirname(resolve(REPO_ROOT, canonicalBundlePath)), { recursive: true })
  await writeFile(resolve(REPO_ROOT, canonicalBundlePath), canonicalBundleText)
  const canonicalBundleSha256 = createHash("sha256").update(canonicalBundleText).digest("hex")
  const canonicalRun: RunState = {
    ...fastRun,
    revision: 9,
    semanticV2: {
      ...fastRun.semanticV2!,
      profilePath: "language_packs/ptx/9.3/semantic-profile.json",
    },
    executions: [{
      at: "2026-01-01T00:00:01.000Z",
      stage: "SOURCE_CURATION",
      agent: "source-curator",
      sessionId: "semantic-delta-source-fixture",
      outcome: "SUCCESS",
      nextStage: "SEMANTIC_EXTRACTION",
      response: "fixture",
      publishedArtifacts: [{
        role: "SOURCE_BUNDLE",
        path: canonicalBundlePath,
        sha256: canonicalBundleSha256,
        sizeBytes: Buffer.byteLength(canonicalBundleText),
        stage: "SOURCE_CURATION",
        producingExecution: {
          agent: "source-curator",
          sessionId: "semantic-delta-source-fixture",
        },
        runRevision: 8,
      }],
    }],
  }
  const malformedShapes = [
    {
      name: "clz/brev missing canonical evidence and lifecycle fields",
      make: (): unknown => {
        const value = clone(delta) as unknown as Record<string, unknown>
        value.evidence = delta.evidence.map((record) => ({
          sourceBundleEvidenceId: record.sourceBundleEvidenceId,
          fragmentId: record.sourceBundleEvidenceId,
          statement: record.quotation ?? "agent summary",
        }))
        value.claims = delta.claims.map(({ lifecycle: _lifecycle, humanApprovalDependencies: _approval, ...claim }) => ({
          ...claim,
          evidenceIds: claim.evidenceIds.map((id) =>
            delta.evidence.find((item) => item.evidenceId === id)?.sourceBundleEvidenceId ?? id),
          status: "RESOLVED",
        }))
        return value
      },
    },
    {
      name: "shl unknown source-manifest hash",
      make: (): unknown => {
        const value = clone(delta)
        for (const record of value.evidence) record.source.sourceManifestSha256 = "unknown"
        return value
      },
    },
  ]
  try {
    for (const fixture of malformedShapes) {
      const canonical = await canonicalSemanticDeltaForRun(
        canonicalRun,
        fixture.make(),
        { agent: "semantic-extractor-delta", sessionId: "structured-writer-fixture" },
      )
      assert(
        canonical.unit.language.toLowerCase() === canonicalRun.language.toLowerCase() &&
          canonical.unit.unit === canonicalRun.unit &&
          canonical.provenance.sourceBundle.path === canonicalBundlePath &&
          canonical.evidence.every((item) =>
            /^[a-f0-9]{64}$/.test(item.source.sourceManifestSha256) &&
            item.specificationVersion === canonicalRun.specVersion &&
            item.locator !== undefined) &&
          canonical.claims.every((claim) =>
            claim.lifecycle.status === "ACTIVE" &&
            claim.lifecycle.introducedInRevision === canonicalRun.revision &&
            Array.isArray(claim.humanApprovalDependencies)),
        `structured writer canonicalizes ${fixture.name}`,
      )
      const canonicalEvaluation = evaluateSemanticDeltaDocuments(shared, canonical)
      assert(
        canonicalEvaluation.ok,
        `structured writer output validates after repairing ${fixture.name}: ${canonicalEvaluation.issues.join(" | ")}`,
      )
    }
  } finally {
    await rm(resolve(REPO_ROOT, canonicalRoot), { recursive: true, force: true })
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
