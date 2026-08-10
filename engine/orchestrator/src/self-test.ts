import { createHash, randomUUID } from "node:crypto"
import { readFile, readdir, unlink } from "node:fs/promises"
import { resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { normalizeAgentDecision } from "./agent-decision.js"
import {
  DEFAULT_PROVIDER_RETRY_BUDGET_MS,
  ProviderRetryBudgetExceededError,
  findCompletedResponse,
  providerRetryBudgetExceeded,
} from "./async-session.js"
import {
  artifactContractForRun,
  makeLeanModuleName,
  makeUnitSlug,
} from "./artifact-contract.js"
import {
  artifactPathsForGate,
  verifyHumanDecisionRecord,
  writeHumanDecisionRecord,
} from "./human-decision-record.js"
import { verifyLeanFile } from "./lean-local.js"
import { packageTransform } from "./lean-package.js"
import { proofTargets, theoremDeclarationNames } from "./proof-plan.js"
import { loadProjectModel, REPO_ROOT } from "./repo.js"
import { runSemanticIrSelfTests } from "./semantic-ir-self-test.js"
import { runSemanticV2SelfTests } from "./semantic-v2-self-test.js"
import {
  buildApprovedSharedEnvironment,
  sharedApprovalCandidateIssues,
  verifySharedApprovalCandidateFiles,
} from "./shared-environment-approval.js"
import { validProfile, type SemanticProfile } from "./semantic-v2.js"
import type { SharedSemanticEnvironment } from "./semantic-ir/types.js"
import { canTransition, type RunState } from "./workflow.js"

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`SELF_TEST_FAILED: ${message}`)
}

async function protectedTreeFingerprint(relativeRoot: string): Promise<string> {
  const hash = createHash("sha256")
  const visit = async (relativeDirectory: string): Promise<void> => {
    const entries = await readdir(resolve(REPO_ROOT, relativeDirectory), {
      withFileTypes: true,
    })
    for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
      const relativePath = `${relativeDirectory}/${entry.name}`
      if (entry.isDirectory()) {
        await visit(relativePath)
      } else if (entry.isFile()) {
        hash.update(relativePath)
        hash.update(await readFile(resolve(REPO_ROOT, relativePath)))
      }
    }
  }
  await visit(relativeRoot)
  return hash.digest("hex")
}

const protectedTreesBefore = {
  accepted: await protectedTreeFingerprint("accepted"),
  candidates: await protectedTreeFingerprint("candidates"),
}

assert(makeUnitSlug("mov.b32") === "mov-b32", "unit slug")
assert(makeLeanModuleName("mov.b32") === "MovB32", "Lean module name")
assert(canTransition("ARCHITECTURE_CRITIQUE", "WAITING_GATE_A"), "Gate A transition")
assert(!canTransition("ARCHITECTURE", "LEAN_FORMALIZATION"), "illegal stage skip rejected")
assert(
  !providerRetryBudgetExceeded(1_000, 60_999, DEFAULT_PROVIDER_RETRY_BUDGET_MS),
  "provider retry remains active before the bounded budget",
)
assert(
  providerRetryBudgetExceeded(1_000, 61_000, DEFAULT_PROVIDER_RETRY_BUDGET_MS),
  "provider retry stops at the bounded budget",
)
const providerRetryError = new ProviderRetryBudgetExceededError({
  attempt: 2,
  providerMessage: "rate limited",
  nextRetryAt: 70_000,
  retryElapsedMs: DEFAULT_PROVIDER_RETRY_BUDGET_MS,
  retryBudgetMs: DEFAULT_PROVIDER_RETRY_BUDGET_MS,
})
assert(
  providerRetryError.attempt === 2 &&
    providerRetryError.providerMessage === "rate limited",
  "provider retry diagnostics preserve structured status",
)
assert(
  findCompletedResponse([{
    info: { role: "assistant" },
    parts: [
      {
        type: "text",
        text: 'compaction copy: SPEC2LEAN_RESULT {"outcome":"BLOCKED","nextStage":"BLOCKED","summary":"stale"}',
      },
      { type: "step-finish", reason: "tool-calls" },
    ],
  }]) === undefined,
  "tool-call and compaction turns cannot masquerade as terminal protocol output",
)
assert(
  findCompletedResponse([{
    info: { role: "assistant" },
    parts: [
      {
        type: "text",
        text: 'SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"ARCHITECTURE_CRITIQUE","summary":"done"}',
      },
      { type: "step-finish", reason: "stop" },
    ],
  }])?.includes('"outcome":"SUCCESS"'),
  "terminal assistant turn supplies protocol output",
)

const baseArtifactRun: RunState = {
  schemaVersion: 1,
  runId: "artifact-retry-self-test",
  mode: "formalization",
  language: "ptx",
  specVersion: "9.3",
  unit: "or.b32",
  unitSlug: "or-b32",
  leanModuleName: "OrB32",
  sourceManifest: "documents/sources/nvidia/ptx/9.3/source-manifest.json",
  artifactRoot: "candidates/ptx/9.3/units/or-b32",
  stage: "SEMANTIC_EXTRACTION",
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
  history: [],
}
const normalizedInvalidDecision = normalizeAgentDecision(baseArtifactRun, {
  outcome: "BLOCKED",
  nextStage: "ARCHITECTURE",
  summary: "invalid target",
})
assert(
  normalizedInvalidDecision.outcome === "RETRY" &&
    normalizedInvalidDecision.nextStage === "SEMANTIC_EXTRACTION",
  "invalid agent workflow decisions become safe retries",
)
assert(
  artifactContractForRun(baseArtifactRun).outputPath.endsWith("semantics-v1.json"),
  "first semantic attempt uses v1",
)
const afterMalformedArtifactRetry: RunState = {
  ...baseArtifactRun,
  executions: [{
    at: "2026-01-01T00:01:00.000Z",
    stage: "SEMANTIC_EXTRACTION",
    agent: "semantic-extractor",
    sessionId: "self-test-session",
    outcome: "RETRY",
    nextStage: "SEMANTIC_EXTRACTION",
    response: "invalid JSON",
  }],
}
assert(
  artifactContractForRun(afterMalformedArtifactRetry).outputPath.endsWith("semantics-v2.json"),
  "retry advances immutable semantic artifact revision",
)
assert(
  artifactContractForRun({
    ...afterMalformedArtifactRetry,
    stage: "PROOF_GENERATION",
    executions: [{
      ...afterMalformedArtifactRetry.executions![0]!,
      stage: "PROOF_GENERATION",
      nextStage: "PROOF_GENERATION",
    }],
  }).outputPath.endsWith("OrB32Proofs-v1.lean"),
  "incremental proof retry retains its progress artifact",
)
assert(
  theoremDeclarationNames([
    "theorem AtColumnZero : True := by trivial",
    " theorem WithLeadingSpace : True := by trivial",
    "\ttheorem WithLeadingTab : True := by trivial",
  ].join("\n")).size === 3,
  "proof progress recognizes indented top-level theorem declarations",
)

const semanticIrMetrics = await runSemanticIrSelfTests()
const semanticV2Metrics = await runSemanticV2SelfTests()

const productionSemanticProfileInput = JSON.parse(
  await readFile(resolve(REPO_ROOT, "language_packs/ptx/9.3/semantic-profile.json"), "utf8"),
) as unknown
assert(validProfile(productionSemanticProfileInput), "production semantic profile is structurally valid")
const productionSemanticProfile = productionSemanticProfileInput as SemanticProfile
const sharedReviewCandidate = JSON.parse(
  await readFile(resolve(REPO_ROOT, productionSemanticProfile.approval.reviewCandidatePath), "utf8"),
) as SharedSemanticEnvironment
const sharedReviewPacket = await readFile(
  resolve(REPO_ROOT, productionSemanticProfile.approval.humanReviewPacketPath),
  "utf8",
)
assert(
  sharedApprovalCandidateIssues(productionSemanticProfile, sharedReviewCandidate).length === 0,
  "shared-environment human-review candidate matches the typed production profile",
)
await verifySharedApprovalCandidateFiles(sharedReviewCandidate)
assert(
  sharedReviewPacket.includes("NOT HUMAN APPROVED") &&
    sharedReviewPacket.includes(createHash("sha256").update(
      await readFile(resolve(REPO_ROOT, productionSemanticProfile.approval.reviewCandidatePath)),
    ).digest("hex")),
  "shared human-review packet identifies the exact unapproved candidate",
)
const syntheticApprovedEnvironment = buildApprovedSharedEnvironment(sharedReviewCandidate, {
  path: productionSemanticProfile.approval.approvalRecordPath,
  sha256: "0".repeat(64),
})
assert(
  syntheticApprovedEnvironment.review.status === "HUMAN_APPROVED" &&
    syntheticApprovedEnvironment.entries.every((entry) => entry.review.status === "HUMAN_APPROVED"),
  "shared approval derivation changes only explicit review state and binds the approval record",
)

const parsed = parseAgentResult(
  'prefix\nSPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"ARCHITECTURE_CRITIQUE","summary":"ok"}',
)
assert(parsed.outcome === "SUCCESS", "result parsing")

const retrievalProfile = JSON.parse(
  await readFile(
    resolve(
      REPO_ROOT,
      "language_packs/ptx/9.3/retrieval-profile.json",
    ),
    "utf8",
  ),
) as {
  specificationVersion?: string
  context?: { sharedSections?: unknown[] }
  policy?: {
    interpretationPerformed?: boolean
    humanApprovalImplied?: boolean
  }
}
assert(
  retrievalProfile.specificationVersion === "9.3",
  "PTX retrieval profile version",
)
assert(
  retrievalProfile.context?.sharedSections?.length === 7,
  "PTX shared retrieval sections",
)
assert(
  retrievalProfile.policy?.interpretationPerformed === false &&
    retrievalProfile.policy?.humanApprovalImplied === false,
  "retrieval profile does not claim semantic approval",
)

const runPath = resolve(REPO_ROOT, "runs/ptx-9.3-mov.b32-f910feea/run.json")
try {
  const run = JSON.parse(await readFile(runPath, "utf8")) as RunState
  const targets = await proofTargets(run)
  assert(targets.length === 16, "mov.b32 proof target extraction")
  assert(new Set(targets.map((x) => x.name)).size === targets.length, "proof target names unique")

  const proofPath = resolve(REPO_ROOT, "candidates/ptx/9.3/units/mov-b32/lean/MovB32Proofs-v1.lean")
  try {
    const proof = await readFile(proofPath, "utf8")
    assert(proof.includes("namespace MovB32"), "mov.b32 proof namespace isolated")
    for (const target of targets) {
      assert(proof.includes(`theorem ${target.name}`), `seed proof contains ${target.name}`)
    }
  } catch (error) {
    if ((error as { code?: string }).code !== "ENOENT") throw error
  }

  const gateArtifacts = await artifactPathsForGate(run, "B")
  assert(
    gateArtifacts[0] ===
      "candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json",
    "deterministic Gate B candidate selection",
  )
  assert(
    gateArtifacts[1] ===
      "candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md",
    "deterministic Gate B critic selection",
  )

  await verifyHumanDecisionRecord({
    run,
    gate: "B",
    decision: "approved",
    reviewId: "ptx-mov-b32-b-approval-v1",
    reviewPath:
      "reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json",
    reviewer: "Human reviewer",
    rationale: "Existing record compatibility check.",
  })

  const reviewId = `controller-decision-self-test-${randomUUID()}`
  const reviewPath = `reviews/tool-tests/${reviewId}.json`
  const decisionInput = {
    run,
    gate: "B" as const,
    decision: "approved" as const,
    reviewId,
    reviewPath,
    reviewer: "Self-test reviewer",
    rationale: "Self-test of deterministic hash-bound human decision recording.",
  }

  try {
    await writeHumanDecisionRecord(decisionInput)
    await verifyHumanDecisionRecord(decisionInput)
    const record = JSON.parse(
      await readFile(resolve(REPO_ROOT, reviewPath), "utf8"),
    ) as { provenance?: { controller?: string }; artifacts?: unknown[] }
    assert(
      record.provenance?.controller === "spec2lean-cli",
      "deterministic decision provenance",
    )
    assert(record.artifacts?.length === 2, "decision artifact fingerprints")
  } finally {
    await unlink(resolve(REPO_ROOT, reviewPath)).catch(() => undefined)
  }
} catch (error) {
  if ((error as { code?: string }).code !== "ENOENT") throw error
}

for (const controller of ["approve", "reject"]) {
  const text = await readFile(
    resolve(REPO_ROOT, `engine/orchestrator/src/${controller}.ts`),
    "utf8",
  )
  assert(!text.includes("startOpenCode"), `${controller} does not start OpenCode`)
  assert(
    text.includes("writeHumanDecisionRecord"),
    `${controller} records decisions deterministically`,
  )
}

const sharedApprovalController = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/approve-shared.ts"),
  "utf8",
)
assert(!sharedApprovalController.includes("startOpenCode"), "shared approval does not start OpenCode")

const runLoopSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/run-loop.ts"),
  "utf8",
)
assert(!runLoopSource.includes("npm\""), "run loop does not spawn npm ticks")
assert(!runLoopSource.includes("spawn("), "run loop executes ticks in-process")
assert(
  runLoopSource.includes("runtime ??= await startOpenCode()"),
  "run loop reuses one lazy OpenCode runtime",
)
assert(
  runLoopSource.includes("providerRetryBudgetMs: providerRetryBudgetSeconds * 1000"),
  "run loop passes the shared runtime and bounded provider retry policy into each tick",
)
const runnerSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/runner.ts"),
  "utf8",
)
assert(
  runnerSource.includes("run.activeExecution.model === runtime.model.full") &&
    runnerSource.match(/model: runtime\.model\.full/g)?.length === 2,
  "active-session recovery is pinned to explicit model provenance",
)

const projectModel = await loadProjectModel()
const projectConfig = JSON.parse(
  await readFile(resolve(REPO_ROOT, "opencode.json"), "utf8"),
) as { enabled_providers?: unknown[] }
assert(
  projectConfig.enabled_providers?.includes(projectModel.providerID),
  "project model provider is explicitly enabled",
)
const agentFiles = (await readdir(resolve(REPO_ROOT, ".opencode/agents")))
  .filter((name) => name.endsWith(".md"))
for (const agentFile of agentFiles) {
  const text = await readFile(resolve(REPO_ROOT, `.opencode/agents/${agentFile}`), "utf8")
  assert(
    text.includes(`model: ${projectModel.full}`),
    `${agentFile} model matches the project model`,
  )
  assert(!text.includes("# First Formalization Unit"), `${agentFile} obsolete first-unit block removed`)
  assert(!text.includes("Do not formalize another PTX instruction."), `${agentFile} no stale unit lock`)
  assert(!text.includes("Do not prove properties for another PTX instruction."), `${agentFile} no stale proof lock`)
}

const candidateTool = await readFile(
  resolve(REPO_ROOT, ".opencode/tools/candidate.ts"),
  "utf8",
)
assert(
  candidateTool.includes("JSON.parse(args.content)") &&
    candidateTool.includes("invalid JSON; artifact was not written"),
  "candidate_write validates JSON before the atomic write",
)

const leanVerifierSmoke = await verifyLeanFile("lean/Spec2Lean/PTX/MovB32.lean")
assert(
  leanVerifierSmoke.success,
  `Lean verifier prepares project imports: ${leanVerifierSmoke.output}`,
)

const dottedNamespaceCandidate = [
  "import Spec2Lean.Basic",
  "namespace Spec2Lean.PTX.OrB32",
  "def marker := true",
  "end Spec2Lean.PTX.OrB32",
  "",
].join("\n")
const dottedPackage = packageTransform(dottedNamespaceCandidate, "OrB32")
assert(
  dottedPackage.text === dottedNamespaceCandidate &&
    dottedPackage.isolatedNamespace === false,
  "Lean packaging accepts an already-isolated dotted unit namespace",
)

const nestedBaseCandidate = [
  "import Spec2Lean.Basic",
  "namespace Spec2Lean",
  "namespace PTX",
  "def marker := true",
  "end PTX",
  "end Spec2Lean",
  "",
].join("\n")
const nestedPackage = packageTransform(nestedBaseCandidate, "TestUnit")
assert(
  nestedPackage.text.includes("namespace TestUnit") &&
    nestedPackage.text.includes("end TestUnit") &&
    nestedPackage.isolatedNamespace === true,
  "Lean packaging still isolates legacy nested PTX candidates",
)

const deltaAgent = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/semantic-extractor-delta.md"),
  "utf8",
)
assert(
  deltaAgent.includes("sourceBundleEvidenceId") &&
    deltaAgent.includes("The orchestrator will record the failure") &&
    deltaAgent.includes("Do not copy shared entries into local claims"),
  "delta extractor preserves grounding, reuse, and fallback boundaries",
)

const protectedTreesAfter = {
  accepted: await protectedTreeFingerprint("accepted"),
  candidates: await protectedTreeFingerprint("candidates"),
}
assert(
  protectedTreesBefore.accepted === protectedTreesAfter.accepted,
  "self-tests do not modify accepted artifacts",
)
assert(
  protectedTreesBefore.candidates === protectedTreesAfter.candidates,
  "self-tests do not modify candidate artifacts",
)

console.log(JSON.stringify({
  ok: true,
  test: "orchestrator-self-test",
  semanticIr: semanticIrMetrics,
  semanticV2: semanticV2Metrics,
}, null, 2))
