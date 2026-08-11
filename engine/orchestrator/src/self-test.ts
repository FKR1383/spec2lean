import { createHash, randomUUID } from "node:crypto"
import { readFile, readdir, unlink } from "node:fs/promises"
import { resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { normalizeAgentDecision } from "./agent-decision.js"
import {
  benchmarkDecisionLocation,
  recordBenchmarkAutoAdvance,
} from "./benchmark-decision-record.js"
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
import { mapWithConcurrency } from "./batch-runtime.js"
import { parseBatchUnits, resolveWorkerCount } from "./formalize-batch.js"
import { normalizeCriticResultFromReview } from "./critic-disposition.js"
import {
  artifactPathsForGate,
  verifyHumanDecisionRecord,
  writeHumanDecisionRecord,
} from "./human-decision-record.js"
import { verifyLeanFile } from "./lean-local.js"
import { packageTransform } from "./lean-package.js"
import {
  proofTargets,
  theoremDeclarationNames,
  verifiedProofArtifactPath,
} from "./proof-plan.js"
import { reconcileProofStageResult } from "./proof-stage-result.js"
import { buildTheoremStrengthContractContext } from "./runner.js"
import {
  compareProofWithApprovedTheorems,
  theoremStrengthReviewAuditIssues,
  validateTheoremObligationDocument,
} from "./theorem-contract.js"
import { loadAgentModel, loadProjectModel, REPO_ROOT } from "./repo.js"
import { withRepositoryLock } from "./repository-lock.js"
import { runSemanticIrSelfTests } from "./semantic-ir-self-test.js"
import { runSemanticV2SelfTests } from "./semantic-v2-self-test.js"
import {
  buildTraceabilityManifest,
  manifestEntryForLine,
  traceabilityManifestPath,
  verifyTraceabilityManifest,
} from "./traceability.js"
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
assert(
  parseBatchUnits(["and.b64, or.b64", "xor.b64"]).join(",") ===
    "and.b64,or.b64,xor.b64",
  "batch unit parser accepts comma-separated and repeated groups",
)
let batchCollisionRejected = false
try {
  parseBatchUnits(["a.b,a-b"])
} catch {
  batchCollisionRejected = true
}
assert(batchCollisionRejected, "batch unit parser rejects artifact-path collisions")
assert(resolveWorkerCount("4", undefined, 2) === 4, "--workers controls batch concurrency")
assert(resolveWorkerCount(undefined, "3", 2) === 3, "legacy --concurrency remains supported")
let workerConflictRejected = false
try {
  resolveWorkerCount("2", "3", 2)
} catch {
  workerConflictRejected = true
}
assert(workerConflictRejected, "conflicting worker aliases are rejected")

const theoremContract = validateTheoremObligationDocument({
  schema_version: 1,
  theorem_obligations: [{
    obligation_id: "T-1",
    lean_statement_sketch: "theorem exact_contract (n : Nat) : n = n",
  }],
})
assert(theoremContract.issues.length === 0, "complete theorem contract validates")
assert(
  compareProofWithApprovedTheorems(
    theoremContract.declarations,
    "theorem exact_contract (n : Nat) : n = n := by rfl",
  ).length === 0,
  "proof preserves the exact approved theorem statement",
)
assert(
  compareProofWithApprovedTheorems(
    theoremContract.declarations,
    "theorem exact_contract (n : Nat) (h : n = 0) : n = n := by rfl",
  ).some((issue) => issue.includes("statement changed")),
  "proof contract rejects added assumptions even when Lean would compile",
)
assert(
  validateTheoremObligationDocument({
    schema_version: 1,
    theorem_obligations: [{ obligation_id: "T-2", lean_statement_sketch: "theorem incomplete : ..." }],
  }).issues.length > 0,
  "theorem contract rejects placeholders before human approval",
)
const validTheoremReview = [
  "Validated obligation artifact: `fixtures/obligations-v1.json`",
  "Complete declaration count reviewed: 1",
  "Declaration names reviewed:",
  "- exact_contract",
].join("\n")
assert(
  theoremStrengthReviewAuditIssues(
    validTheoremReview,
    "fixtures/obligations-v1.json",
    theoremContract.declarations,
  ).length === 0,
  "theorem-strength review audit binds exact path, count, and names",
)
assert(
  theoremStrengthReviewAuditIssues(
    validTheoremReview.replace("count reviewed: 1", "count reviewed: 0"),
    "fixtures/obligations-v1.json",
    theoremContract.declarations,
  ).some((issue) => issue.includes("validated obligation contract contains 1")),
  "theorem-strength review audit rejects a false zero-declaration report",
)

let activeBatchOperations = 0
let maximumBatchOperations = 0
await mapWithConcurrency([1, 2, 3, 4], 2, async (value) => {
  activeBatchOperations += 1
  maximumBatchOperations = Math.max(maximumBatchOperations, activeBatchOperations)
  await new Promise<void>((resolvePromise) => setTimeout(resolvePromise, 2))
  activeBatchOperations -= 1
  return value * 2
})
assert(maximumBatchOperations === 2, "batch runtime enforces bounded concurrency")
let activeLockedOperations = 0
let maximumLockedOperations = 0
await mapWithConcurrency([1, 2], 2, async () => {
  await withRepositoryLock("self-test", async () => {
    activeLockedOperations += 1
    maximumLockedOperations = Math.max(maximumLockedOperations, activeLockedOperations)
    await new Promise<void>((resolvePromise) => setTimeout(resolvePromise, 2))
    activeLockedOperations -= 1
  })
})
assert(maximumLockedOperations === 1, "repository lock serializes shared package work")
const nonBlockingCriticResult = normalizeCriticResultFromReview(
  {
    outcome: "REVISE",
    nextStage: "ARCHITECTURE",
    summary: "non-blocking wording changes",
  },
  "- **Severity:** MINOR\n- **Severity:** NOTE\n",
  "WAITING_GATE_A",
)
assert(
  nonBlockingCriticResult.outcome === "SUCCESS" &&
    nonBlockingCriticResult.nextStage === "WAITING_GATE_A",
  "MINOR/NOTE-only critic reviews cannot trigger another revision cycle",
)
const majorCriticResult = normalizeCriticResultFromReview(
  {
    outcome: "REVISE",
    nextStage: "ARCHITECTURE",
    summary: "source-faithfulness defect",
  },
  "- **Severity:** MAJOR\n",
  "WAITING_GATE_A",
)
assert(
  majorCriticResult.outcome === "REVISE",
  "BLOCKER/MAJOR critic reviews still require revision",
)
const blockedProofResult = reconcileProofStageResult(
  {
    outcome: "BLOCKED",
    nextStage: "BLOCKED",
    summary: "approved theorem is false under the installed relation",
  },
  {
    outcome: "RETRY",
    nextStage: "PROOF_GENERATION",
    summary: "proof file does not compile",
  },
)
assert(
  blockedProofResult.outcome === "BLOCKED" &&
    blockedProofResult.nextStage === "BLOCKED",
  "local Lean diagnostics cannot erase a proof agent's semantic BLOCKED result",
)
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
  "legacy retry records conservatively advance immutable semantic artifact revision",
)
assert(
  artifactContractForRun({
    ...afterMalformedArtifactRetry,
    executions: [{ ...afterMalformedArtifactRetry.executions![0]!, artifactProduced: false }],
  }).outputPath.endsWith("semantics-v1.json"),
  "provider/protocol retry without an artifact does not inflate artifact versions",
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

const benchmarkRun: RunState = {
  ...baseArtifactRun,
  runId: `benchmark-auto-self-test-${randomUUID()}`,
  stage: "WAITING_GATE_A",
  benchmark: {
    autoApprove: true,
    startedAtUtc: "2026-01-01T00:00:00.000Z",
  },
}
const benchmarkLocation = benchmarkDecisionLocation(benchmarkRun, "A")
try {
  const recorded = await recordBenchmarkAutoAdvance(benchmarkRun, "A")
  const benchmarkRecord = JSON.parse(
    await readFile(resolve(REPO_ROOT, recorded.reviewPath), "utf8"),
  ) as {
    recordType?: string
    humanConfirmationRecorded?: boolean
    gateApprovalPerformed?: boolean
    promotionPerformed?: boolean
  }
  assert(
    benchmarkRecord.recordType === "benchmark_gate_auto_advance" &&
      benchmarkRecord.humanConfirmationRecorded === false &&
      benchmarkRecord.gateApprovalPerformed === false &&
      benchmarkRecord.promotionPerformed === false,
    "benchmark auto-advance is explicitly non-human and non-promoting",
  )
} finally {
  await unlink(resolve(REPO_ROOT, benchmarkLocation.reviewPath)).catch(() => undefined)
}

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
  const theoremCriticContext = await buildTheoremStrengthContractContext({
    ...run,
    stage: "THEOREM_STRENGTH_CRITIQUE",
  })
  assert(
    theoremCriticContext.includes("Complete declaration count supplied: 16") &&
      theoremCriticContext.includes("No theorem/lemma declarations are expected in the Lean mapping") &&
      targets.every((target) => theoremCriticContext.includes(target.name)),
    "theorem-strength critic receives the deterministic JSON theorem contract",
  )

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

const finalizeController = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/finalize.ts"),
  "utf8",
)
assert(
  finalizeController.includes("Benchmark auto-approve runs are not human-approved"),
  "benchmark runs cannot be finalized or promoted",
)

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
assert(
  runLoopSource.includes("recordBenchmarkAutoAdvance") &&
    runLoopSource.includes('"BENCHMARK_COMPLETE"'),
  "run loop records benchmark decisions and terminates outside human acceptance",
)
const runnerSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/runner.ts"),
  "utf8",
)
assert(
  runnerSource.includes("run.activeExecution.model === executionModel.full") &&
    runnerSource.match(/model: executionModel\.full/g)?.length === 2,
  "active-session recovery is pinned to explicit model provenance",
)
assert(
  runnerSource.includes('run.stage === "LEAN_FORMALIZATION"') &&
    runnerSource.includes('buildPipelineTraceabilityManifest(run, "SEMANTICS")') &&
    runnerSource.includes("writeTraceabilityManifest(manifest)"),
  "verified Lean formalization automatically emits its evidence manifest",
)
assert(
  runnerSource.includes('buildPipelineTraceabilityManifest(run, "PROOFS")') &&
    runnerSource.match(/Deterministic theorem-to-source evidence manifest/g)?.length === 2,
  "verified proof generation automatically emits its theorem evidence manifest",
)
const leanPackageSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/lean-package.ts"),
  "utf8",
)
assert(
  leanPackageSource.includes("const actualSourcePath = proofArtifactPath(run)") &&
    !leanPackageSource.includes("Proofs-v(\\\\d+)") &&
    leanPackageSource.includes("await writeFile(rootPath, previousRoot, \"utf8\")"),
  "proof installation uses the verified canonical artifact rather than the highest filename version",
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
  const agentModel = await loadAgentModel(agentFile.slice(0, -3))
  assert(
    projectConfig.enabled_providers?.includes(agentModel.providerID),
    `${agentFile} model provider is explicitly enabled`,
  )
  assert(!text.includes("# First Formalization Unit"), `${agentFile} obsolete first-unit block removed`)
  assert(!text.includes("Do not formalize another PTX instruction."), `${agentFile} no stale unit lock`)
  assert(!text.includes("Do not prove properties for another PTX instruction."), `${agentFile} no stale proof lock`)
}
assert(
  (await loadAgentModel("proof-engineer")).full === "openai/gpt-5.3-codex-spark",
  "proof engineer uses the bounded DeepSeek migration route",
)
const semanticCriticPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/semantic-critic.md"),
  "utf8",
)
assert(
  semanticCriticPrompt.includes("MINOR` or `NOTE` findings remain") &&
    semanticCriticPrompt.includes("never describe an artifact as \"ready\"") ,
  "semantic critic has a consistent severity-to-disposition contract",
)
const theoremStrengthCriticPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/theorem-strength-critic.md"),
  "utf8",
)
assert(
  theoremStrengthCriticPrompt.includes("constructor overlap") &&
    theoremStrengthCriticPrompt.includes("counterexample/probe") &&
    ["`BLOCKER`", "`MAJOR`", "`MINOR`", "`NOTE`", "counts"].every(
      (token) => theoremStrengthCriticPrompt.includes(token),
    ),
  "stage-specific theorem critic checks truth and has deterministic disposition output",
)
const leanFormalizerPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/lean-formalizer.md"),
  "utf8",
)
assert(
  leanFormalizerPrompt.includes("copy its exact SUCCESS") &&
    leanFormalizerPrompt.includes("exact semantic claim IDs"),
  "Lean formalizer pins workflow protocol and traceability IDs",
)

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

const traceabilityManifest = await buildTraceabilityManifest({
  runId: "ptx-9.3-or.b16-ab7bd730",
})
const traceabilityIssues = await verifyTraceabilityManifest(traceabilityManifest)
assert(
  traceabilityIssues.some((issue) => issue.includes("Lean declaration has no provenance reference")),
  "traceability validation exposes legacy unlinked declarations instead of silently passing",
)
const orValueEntry = traceabilityManifest.entries.find((entry) => entry.declarationName === "orValue")
assert(
  orValueEntry !== undefined &&
    orValueEntry.semanticIds.includes("SF-ORB16-003") &&
    orValueEntry.evidence.some((evidence) => evidence.evidenceId === "PTX-9.3-ORB16-005"),
  "traceability generator resolves Lean claim comments to exact source fragments",
)
const proofTraceabilityManifest = await buildTraceabilityManifest({
  runId: "ptx-9.3-or.b16-ab7bd730",
  documentRole: "PROOFS",
})
const proofTraceabilityIssues = await verifyTraceabilityManifest(proofTraceabilityManifest)
assert(
  proofTraceabilityIssues.length === 0,
  `proof traceability manifest verifies: ${proofTraceabilityIssues.join(", ")}`,
)
const deterministicTheorem = proofTraceabilityManifest.entries.find(
  (entry) => entry.declarationName === "OrB16Step_deterministic",
)
assert(
  deterministicTheorem !== undefined &&
    deterministicTheorem.theoremObligationIds.length === 1 &&
    deterministicTheorem.semanticIds.length > 0 &&
    deterministicTheorem.evidence.length > 0,
  "proof traceability resolves theorem obligations through semantic claims to evidence",
)
const designTraceabilityManifest = await buildTraceabilityManifest({
  runId: "ptx-9.3-or.b32-b870f055",
  documentRole: "PROOFS",
})
const bitBucketTheorem = designTraceabilityManifest.entries.find(
  (entry) => entry.declarationName === "OrB32_OrB32Step_bitBucket_noop",
)
assert(
  bitBucketTheorem !== undefined &&
    ["D-2", "D-6", "AMB-OR-2"].every((id) => bitBucketTheorem.semanticIds.includes(id)) &&
    bitBucketTheorem.unresolvedReferences.length === 0 &&
    bitBucketTheorem.evidence.some((item) => item.sourceKind === "ARTIFACT"),
  "traceability resolves reviewed architecture-design dependencies instead of treating them as NVIDIA facts",
)
const compositeProofTraceabilityManifest = await buildTraceabilityManifest({
  runId: "ptx-9.3-shr.b32-ad159e51",
  documentRole: "PROOFS",
})
assert(
  compositeProofTraceabilityManifest.leanDocument.path ===
    "candidates/ptx/9.3/units/shr-b32/lean/ShrB32Proofs-v1.lean",
  "proof traceability selects the completed artifact contract, not a higher stale candidate version",
)
for (const declarationName of [
  "execShrB32_sound_executed",
  "execShrB32_sound_malformed",
  "shrB32Step_to_exec_correspondence",
]) {
  const entry = compositeProofTraceabilityManifest.entries.find(
    (candidate) => candidate.declarationName === declarationName,
  )
  assert(
    entry !== undefined &&
      entry.theoremObligationIds.includes("PTX-SHR-THM-002") &&
      entry.semanticIds.length > 0 &&
      entry.evidence.length > 0,
    `proof traceability resolves every declaration in a composite theorem obligation: ${declarationName}`,
  )
}
const completedShrRun = JSON.parse(await readFile(
  resolve(REPO_ROOT, "runs/ptx-9.3-shr.b32-ad159e51/run.json"),
  "utf8",
)) as RunState
assert(
  verifiedProofArtifactPath(completedShrRun) ===
    "candidates/ptx/9.3/units/shr-b32/lean/ShrB32Proofs-v1.lean",
  "completed proof artifact path is derived from successful proof-stage history",
)
assert(
  orValueEntry !== undefined &&
    manifestEntryForLine(
      traceabilityManifest,
      traceabilityManifest.leanDocument.path,
      orValueEntry.leanRange.startLine,
    )?.entryId === orValueEntry.entryId,
  "traceability line lookup resolves the current Lean declaration",
)
const pdfViewPath = traceabilityManifestPath({
  ...traceabilityManifest,
  diagnostics: {
    ...traceabilityManifest.diagnostics,
    pdfAlignment: { matched: 1, ambiguous: [], unmatched: [] },
  },
})
assert(
  traceabilityManifestPath(traceabilityManifest) !== pdfViewPath,
  "traceability manifests are content-addressed and optional PDF views never overwrite the base mapping",
)
const invalidTraceabilityIssues = await verifyTraceabilityManifest({
  ...traceabilityManifest,
  leanDocument: {
    ...traceabilityManifest.leanDocument,
    sha256: "0".repeat(64),
  },
  entries: traceabilityManifest.entries.map((entry, index) => index === 0
    ? {
        ...entry,
        evidence: entry.evidence.map((evidence, evidenceIndex) => evidenceIndex === 0
          ? { ...evidence, locator: { ...evidence.locator, bbox: [1.1, 0, 0.1, 0.1] } }
          : evidence),
      }
    : entry),
})
assert(
  invalidTraceabilityIssues.some((issue) => issue.includes("hash mismatch")) &&
    invalidTraceabilityIssues.some((issue) => issue.includes("bbox")),
  "traceability verification rejects stale artifacts and invalid normalized PDF boxes",
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
