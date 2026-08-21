import { createHash, randomUUID } from "node:crypto"
import { mkdir, readFile, readdir, rm, unlink, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { normalizeAgentDecision } from "./agent-decision.js"
import { recoverResultFromVerifiedArtifact } from "./artifact-recovery.js"
import {
  artifactBudgetIssues,
  MAX_ARCHITECTURE_BYTES,
} from "./artifact-limits.js"
import {
  sourceBundleIdentityIssues,
  validateArtifactContent,
} from "./artifact-content.js"
import {
  architectureQuestionTriageRequiresRevision,
  validateArchitectureQuestionTriage,
} from "./architecture-review.js"
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
  stageAttempt,
} from "./artifact-contract.js"
import { normalizeExpectedArtifactContent } from "./artifact-normalization.js"
import { mapWithConcurrency } from "./batch-runtime.js"
import {
  PIPELINE_AGENTS,
  saveBatch,
  type FormalizationBatch,
} from "./batch-store.js"
import { parseBatchUnits, resolveWorkerCount } from "./formalize-batch.js"
import {
  DEFAULT_PIPELINE_AGENT_CAPS,
  parsePipelineAgentCaps,
  pipelineAgentCapsIssues,
  pipelineAgentForRun,
  pipelineAgentWorkerLayout,
  poolForStage,
  selectPipelineCandidate,
} from "./pipeline-config.js"
import { stageRevisionCount } from "./pipeline-runtime.js"
import {
  normalizeCriticResultFromReview,
  reviewFindingAccountabilityIssues,
  reviewDispositionCounts,
  reviewExplicitlyReady,
  reviewExplicitlyRequiresRevision,
} from "./critic-disposition.js"
import { criticStageOwnershipIssues } from "./stage-ownership.js"
import { duplicateJsonKeyIssues } from "./json-integrity.js"
import { candidateReplacementIssue } from "./artifact-immutability.js"
import {
  artifactPathsForGate,
  verifyHumanDecisionRecord,
  writeHumanDecisionRecord,
} from "./human-decision-record.js"
import { advanceBenchmarkGate } from "./gate-runtime.js"
import { verifyLeanFile } from "./lean-local.js"
import { packageTransform } from "./lean-package.js"
import {
  leanDeclarationNamespace,
  leanPackagePath,
  makeLeanLanguageName,
} from "./lean-language.js"
import { validateSourceProposal } from "./source-bootstrap.js"
import { ensureSourceIndex, htmlSections } from "./source-index.js"
import { STAGE_PLANS } from "./stage-plan.js"
import {
  proofTargets,
  theoremDeclarationNames,
  verifiedProofArtifactPath,
} from "./proof-plan.js"
import { reconcileProofStageResult } from "./proof-stage-result.js"
import { runPipelinedBatch } from "./pipeline-runtime.js"
import { resolvePtxInstructionSection } from "./ptx-section-resolver.js"
import {
  collectArchitectureProvenanceClaims,
  collectSemanticProvenanceClaims,
  validateArchitectureIndex,
} from "./provenance-catalog.js"
import {
  agentWaitBudgetMs,
  buildGeneralPrompt,
  buildTheoremStrengthContractContext,
  executionAgentForRun,
  normalizeFastPathTerminalResult,
  recoverNonAuthoritativeSemanticBlock,
  recoverNonAuthoritativeSourceBlock,
  semanticExtractionBlockAuthority,
  sourceCurationBlockAuthority,
  shouldPreflightExistingSemanticEvidence,
  shouldRecoverStaleSemanticPreflight,
} from "./runner.js"
import {
  buildStageInputContext,
  stageInputArtifactAreas,
} from "./stage-context.js"
import {
  artifactChainCompletenessIssues,
  architectureCompletenessIssues,
  COMPLETENESS_DIMENSIONS,
  FULL_INSTRUCTION_REQUIRED_PROOF_KINDS,
  leanModelContractIssues,
  semanticCompletenessIssues,
  sharedProofDischargeIssues,
  sourceBundleCompletenessIssues,
  theoremSemanticCoverageIssues,
} from "./quality-contract.js"
import {
  leanBehaviorBranches,
  theoremBehaviorAuditIssues,
} from "./theorem-behavior-audit.js"
import {
  compareProofWithApprovedTheorems,
  normalizeLeanStatementSurfaceSyntax,
  theoremContractEncodingIssues,
  theoremStrengthReviewAuditIssues,
  validateTheoremObligationDocument,
} from "./theorem-contract.js"
import { theoremElaborationIssues, theoremTypeExpression } from "./theorem-elaboration.js"
import { loadAgentModel, loadProjectModel, REPO_ROOT } from "./repo.js"
import { saveRun } from "./run-store.js"
import { withRepositoryLock } from "./repository-lock.js"
import {
  consecutiveOutputLengthFailureCount,
  isProviderAvailabilityFailure,
  noProgressRetryCount,
  noProgressRetryLimitReached,
  outputLengthRetryLimitReached,
  semanticRetryState,
} from "./retry-policy.js"
import { runSemanticIrSelfTests } from "./semantic-ir-self-test.js"
import { runSemanticV2SelfTests } from "./semantic-v2-self-test.js"
import {
  buildTraceabilityManifest,
  manifestEntryForLine,
  parseLeanDeclarations,
  traceabilityManifestPath,
  unresolvedReferenceTokens,
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
assert(makeLeanLanguageName("ecmascript") === "ECMAScript", "ECMAScript Lean namespace")

const qualityDimensions = COMPLETENESS_DIMENSIONS.map((dimension) => ({
  dimension,
  status: "COVERED",
  semanticIds: ["SEM-COMPLETE"],
  encodedBy: [],
  rationale: `${dimension} is represented`,
}))
const qualityArchitecture = [
  "<!-- SPEC2LEAN_COMPLETENESS_CONTRACT",
  JSON.stringify({
    schemaVersion: 1,
    scopeStatus: "FULL_INSTRUCTION",
    languageCore: {
      status: "REUSED_APPROVED",
      path: "language_packs/test/1/language-core.json",
      sha256: "a".repeat(64),
    },
    dimensions: qualityDimensions,
  }),
  "-->",
].join("\n")
assert(architectureCompletenessIssues(qualityArchitecture).length === 0, "full architecture quality contract")

const qualitySourceBundle = {
  schema_version: 3,
  source_documents: [{
    document_id: "DOC-HTML",
    kind: "HTML",
    sha256: "b".repeat(64),
  }],
  fragments: [{
    fragment_id: "FRAGMENT-1",
    document_id: "DOC-HTML",
    source_kind: "HTML",
    source_sha256: "b".repeat(64),
    locator: { anchor: "unit" },
  }],
  evidence_gaps: [],
  coverage_matrix: COMPLETENESS_DIMENSIONS.map((dimension) => ({
    dimension,
    status: "COVERED",
    fragment_ids: ["FRAGMENT-1"],
    gap_ids: [],
    rationale: `${dimension} evidence is closed`,
  })),
}
assert(sourceBundleCompletenessIssues(qualitySourceBundle).length === 0, "source evidence closure contract")
const mandatoryProofRequirements = FULL_INSTRUCTION_REQUIRED_PROOF_KINDS.map((correctnessKind, index) => ({
  requirementId: `REQ-${index + 1}`,
  correctnessKind,
  semanticClaimIds: ["SEM-COMPLETE"],
  rationale: `${correctnessKind} independently checks the approved behavior`,
}))
const qualitySemantics = {
  schemaVersion: 3,
  documentType: "spec2lean_full_semantics",
  scopeStatus: "FULL_INSTRUCTION",
  languageCore: {
    status: "REUSED_APPROVED",
    path: "language_packs/test/1/language-core.json",
    sha256: "a".repeat(64),
  },
  semanticClaims: [{ semanticId: "SEM-COMPLETE" }],
  syntaxForms: [{ syntaxId: "SYNTAX-1", form: "op d, a", semanticClaimIds: ["SEM-COMPLETE"] }],
  operands: [{
    operandId: "OPERAND-1",
    name: "a",
    position: 0,
    role: "SOURCE",
    legalForms: ["value"],
    typeDomains: ["Word"],
    coercions: [],
    semanticClaimIds: ["SEM-COMPLETE"],
  }],
  operation: {
    operationId: "OPERATION-1",
    normalizedMeaning: "identity",
    inputDomains: ["Word"],
    outputDomain: "Word",
    branches: [{ branchId: "BRANCH-1", condition: "always", result: "a", semanticClaimIds: ["SEM-COMPLETE"] }],
    edgeCases: [{ caseId: "EDGE-1", inputClass: "boundary", behavior: "identity", semanticClaimIds: ["SEM-COMPLETE"] }],
    semanticClaimIds: ["SEM-COMPLETE"],
  },
  stateEffects: [{ effectId: "EFFECT-1", component: "result", mode: "WRITE", condition: "always", semanticClaimIds: ["SEM-COMPLETE"] }],
  preconditions: [],
  coverage: COMPLETENESS_DIMENSIONS.map((dimension) => ({
    dimension,
    status: "COVERED",
    semanticClaimIds: ["SEM-COMPLETE"],
    encodedPreconditionIds: [],
    rationale: `${dimension} is represented`,
  })),
  proofRequirements: mandatoryProofRequirements,
}
assert(semanticCompletenessIssues(qualitySemantics).length === 0, "semantic completeness and proof contract")
const inheritedRequirementId = mandatoryProofRequirements.find((item) => item.correctnessKind === "GUARD_BEHAVIOR")!.requirementId
const inheritedSemantics = {
  ...qualitySemantics,
  claims: [{ semanticId: "SEM-COMPLETE", origin: { kind: "SHARED", environmentId: "test", revision: 1 } }],
  proofRequirements: mandatoryProofRequirements.map((item) => item.requirementId === inheritedRequirementId
    ? { ...item, disposition: "INHERITED_FROM_SHARED_ENVIRONMENT", coreDischargeId: "CORE-GUARD" }
    : { ...item, disposition: "LOCAL" }),
}
const inheritedCore = {
  proofDischarges: [{
    dischargeId: "CORE-GUARD",
    correctnessKind: "GUARD_BEHAVIOR",
    semanticIds: ["SEM-COMPLETE"],
    theoremDeclarations: ["Spec2Lean.Test.CoreProofs.guard_noop"],
  }],
}
assert(sharedProofDischargeIssues(inheritedSemantics, inheritedCore).length === 0,
  "reviewed shared proof discharge satisfies inherited requirement")
assert(sharedProofDischargeIssues(inheritedSemantics, { proofDischarges: [] })
  .some((issue) => issue.includes("unknown approved core proof discharge")),
"inherited requirement without approved core discharge is rejected")
assert(
  artifactChainCompletenessIssues(qualityArchitecture, qualitySourceBundle, qualitySemantics).length === 0,
  "architecture/source/semantics correspondence",
)
const sharedGuardSourceBundle = {
  ...qualitySourceBundle,
  coverage_matrix: qualitySourceBundle.coverage_matrix.map((row) =>
    row.dimension === "GUARDS"
      ? {
          ...row,
          status: "NOT_APPLICABLE",
          fragment_ids: [],
          rationale: "the unit section has no separate guard clause",
        }
      : row),
}
assert(
  artifactChainCompletenessIssues(
    qualityArchitecture,
    sharedGuardSourceBundle,
    qualitySemantics,
  ).length === 0,
  "instruction-local NOT_APPLICABLE does not veto shared-core semantic coverage",
)
const badLeanDomain = [
  "import Spec2Lean.Basic",
  "abbrev S32 := Int",
  "def sourceSpec (x : S32) := x",
  "def implementation (x : S32) := x",
  "def execute (x : S32) := x",
  "def Step (x y : S32) := y = x",
  "/- SPEC2LEAN_LEAN_MODEL_CONTRACT",
  JSON.stringify({
    schemaVersion: 1,
    scopeStatus: "FULL_INSTRUCTION",
    languageCoreStatus: "BOOTSTRAP_CANDIDATE",
    languageCoreImport: "",
    domainBindings: [{
      semanticDomainId: "SEM-COMPLETE",
      leanType: "S32",
      representation: "FIXED_WIDTH",
      widthBits: 32,
      providedByLanguageCore: false,
    }],
    encodedExclusions: [],
    executableDefinitions: ["execute"],
    relationalDefinitions: ["Step"],
  }),
  "-/",
].join("\n")
const forbiddenInheritedObligation = {
  schema_version: 3,
  theorem_obligations: [{
    obligation_id: "OBL-INHERITED",
    proof_requirement_ids: [inheritedRequirementId],
    correctness_kind: "GUARD_BEHAVIOR",
    semantic_claim_ids: ["SEM-COMPLETE"],
    independent_specification_symbols: [],
    implementation_symbols: ["execute"],
    lean_statement_sketch: "theorem inherited_guard (x : S32) : execute x = x",
  }],
}
assert(theoremSemanticCoverageIssues(forbiddenInheritedObligation, inheritedSemantics, badLeanDomain)
  .some((issue) => issue.includes("must not regenerate non-local proof requirement")),
"theorem generation cannot duplicate an inherited proof requirement")
assert(
  leanModelContractIssues(badLeanDomain, qualitySemantics).some((issue) => issue.includes("unbounded Int")),
  "fixed-width domains reject unconstrained Int",
)
const tautologicalObligation = {
  schema_version: 3,
  theorem_obligations: [{
    obligation_id: "OBL-TAUTOLOGY",
    proof_requirement_ids: ["REQ-1"],
    correctness_kind: "OPERATION_FIDELITY",
    semantic_claim_ids: ["SEM-COMPLETE"],
    independent_specification_symbols: ["sourceSpec"],
    implementation_symbols: ["implementation"],
    lean_statement_sketch: "theorem tautology (x : S32) : implementation x = implementation x",
  }],
}
assert(
  theoremSemanticCoverageIssues(tautologicalObligation, qualitySemantics, badLeanDomain)
    .some((issue) => issue.includes("reflexive tautology")),
  "tautological implementation theorem is rejected",
)
const acquisitionProfile = {
  schemaVersion: 1,
  language: "ecmascript",
  specificationVersion: "2025",
  publisher: "Ecma International",
  documentTitle: "ECMAScript 2025 Language Specification",
  allowedUrlPrefixes: ["https://262.ecma-international.org/16.0/"],
  requiredKinds: ["html"],
  maxArtifacts: 2,
} as Parameters<typeof validateSourceProposal>[1]
const sourceProposal = {
  schema_version: 1,
  language: "ecmascript",
  specification_version: "2025",
  publisher: "Ecma International",
  document_title: "ECMAScript 2025 Language Specification",
  sources: [{
    kind: "html",
    url: "https://262.ecma-international.org/16.0/",
    authority_reason: "Versioned specification on the publisher-owned ECMA-262 host.",
  }],
} as Parameters<typeof validateSourceProposal>[0]
validateSourceProposal(sourceProposal, acquisitionProfile)
let unofficialSourceRejected = false
try {
  validateSourceProposal({
    ...sourceProposal,
    sources: [{
      ...sourceProposal.sources[0]!,
      url: "https://example.com/ecmascript.html",
    }],
  }, acquisitionProfile)
} catch {
  unofficialSourceRejected = true
}
assert(unofficialSourceRejected, "source acquisition rejects URLs outside the approved publisher scope")
const ecmaSections = htmlSections([
  '<emu-clause id="sec-toboolean">',
  "<h1>ToBoolean ( argument )</h1>",
  "<p>The abstract operation ToBoolean returns a Boolean.</p>",
  "</emu-clause>",
])
assert(
  ecmaSections.length === 1 &&
    ecmaSections[0]?.anchor === "sec-toboolean" &&
    ecmaSections[0]?.searchText.includes("returns a Boolean"),
  "generic HTML ingestion indexes ECMA emu-clause anchors",
)
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
assert(poolForStage("SOURCE_CURATION") === "evidence", "source curation uses evidence pool")
assert(poolForStage("PROOF_GENERATION") === "proof", "proof generation uses proof pool")
assert(poolForStage("WAITING_GATE_B") === undefined, "human gates consume no pipeline worker")
assert(
  parsePipelineAgentCaps("proof-engineer=2,source-curator-fast=1")["proof-engineer"] === 2 &&
    parsePipelineAgentCaps("proof-engineer=2,source-curator-fast=1")["lean-formalizer"] ===
      DEFAULT_PIPELINE_AGENT_CAPS["lean-formalizer"],
  "agent worker overrides preserve unspecified dedicated workers",
)
let invalidPipelineAgentRejected = false
try {
  parsePipelineAgentCaps("unknown=2")
} catch {
  invalidPipelineAgentRejected = true
}
assert(invalidPipelineAgentRejected, "unknown pipeline agents are rejected")
assert(
  pipelineAgentCapsIssues(DEFAULT_PIPELINE_AGENT_CAPS).length === 0 &&
    pipelineAgentCapsIssues({ ...DEFAULT_PIPELINE_AGENT_CAPS, "proof-engineer": -1 })
      .some((issue) => issue.includes("proof-engineer")),
  "persisted agent worker configuration is validated before scheduling",
)
const defaultAgentWorkers = pipelineAgentWorkerLayout(DEFAULT_PIPELINE_AGENT_CAPS)
assert(
  defaultAgentWorkers.length === 13 &&
    new Set(defaultAgentWorkers.map((worker) => worker.agent)).size === 13 &&
    defaultAgentWorkers.every((worker) => worker.id === `${worker.agent}-1`),
  "default pipeline creates exactly one persistent worker identity per executable sub-agent",
)
assert(
  Object.values(STAGE_PLANS).every((plan) =>
    PIPELINE_AGENTS.some((agent) => agent === plan.agent)
  ),
  "every base stage agent has a registered dedicated pipeline worker",
)
const selectedPipelineCandidate = selectPipelineCandidate(
  [
    { value: "other-agent", pool: "evidence", agent: "source-curator", readySince: "2026-01-01T00:00:00.000Z", stableKey: "a" },
    { value: "own-agent", pool: "proof", agent: "proof-engineer", readySince: "2026-01-02T00:00:00.000Z", stableKey: "b" },
  ],
  "proof-engineer",
)
assert(
  selectedPipelineCandidate?.value === "own-agent",
  "agent-pinned worker cannot consume another agent queue",
)

const theoremContract = validateTheoremObligationDocument({
  schema_version: 1,
  theorem_obligations: [{
    obligation_id: "T-1",
    lean_statement_sketch: "theorem exact_contract (n : Nat) : n = n",
  }],
})
assert(theoremContract.issues.length === 0, "complete theorem contract validates")
assert(
  theoremTypeExpression(theoremContract.declarations[0]!) === "(∀ (n : Nat), n = n)",
  "theorem headers are converted to proof-free proposition checks",
)
const correctnessTheoremContract = validateTheoremObligationDocument({
  schema_version: 2,
  source_faithfulness_boundary:
    "These proofs establish that Lean implements the approved semantic IR; source specification prose remains evidence-reviewed authority.",
  theorem_obligations: [
    {
      obligation_id: "T-OPERATION",
      correctness_kind: "OPERATION_FIDELITY",
      correctness_rationale: "Connects the core Lean value function to the approved operation claim.",
      semantic_claim_ids: ["SEM-OP"],
      lean_statement_sketch: "theorem operation_fidelity (n : Nat) : n = n",
    },
    {
      obligation_id: "T-EXECUTION",
      correctness_kind: "EXECUTION_CORRESPONDENCE",
      correctness_rationale: "Connects executable evaluation to the approved relational execution semantics.",
      semantic_claim_ids: ["SEM-STEP"],
      lean_statement_sketch: "theorem execution_correspondence (n : Nat) : n = n",
    },
  ],
})
assert(
  correctnessTheoremContract.issues.length === 0,
  "schema v2 requires semantic operation fidelity and execution correspondence",
)
assert(
  validateTheoremObligationDocument({
    schema_version: 2,
    source_faithfulness_boundary:
      "These proofs implement approved semantic IR while source specification prose remains evidence-reviewed authority.",
    theorem_obligations: [{
      obligation_id: "T-STYLE-ONLY",
      correctness_kind: "SCOPE_BOUNDARY",
      correctness_rationale: "This theorem only records a boundary and does not prove the instruction operation.",
      semantic_claim_ids: ["SEM-SCOPE"],
      lean_statement_sketch: "theorem style_only (n : Nat) : n = n",
    }],
  }).issues.some((issue) => issue.includes("OPERATION_FIDELITY")) &&
    validateTheoremObligationDocument({
      schema_version: 2,
      source_faithfulness_boundary:
        "These proofs implement approved semantic IR while source specification prose remains evidence-reviewed authority.",
      theorem_obligations: [{
        obligation_id: "T-STYLE-ONLY",
        correctness_kind: "SCOPE_BOUNDARY",
        correctness_rationale: "This theorem only records a boundary and does not prove the instruction operation.",
        semantic_claim_ids: ["SEM-SCOPE"],
        lean_statement_sketch: "theorem style_only (n : Nat) : n = n",
      }],
    }).issues.some((issue) => issue.includes("EXECUTION_CORRESPONDENCE")),
  "schema v2 rejects theorem sets that prove only syntax or scope",
)
assert(
  compareProofWithApprovedTheorems(
    theoremContract.declarations,
    "theorem exact_contract (n : Nat) : n = n := by rfl",
  ).length === 0,
  "proof preserves the exact approved theorem statement",
)
const escapedOperatorInput = {
  schema_version: 1,
  theorem_obligations: [{
    obligation_id: "T-ESCAPED",
    lean_statement_sketch: String.raw`theorem escaped_or (p q : Prop) : p \u2228 q -> p \u2228 q`,
  }],
}
const escapedOperatorContract = validateTheoremObligationDocument(escapedOperatorInput)
assert(
  escapedOperatorContract.issues.length === 0 &&
    compareProofWithApprovedTheorems(
      escapedOperatorContract.declarations,
      String.raw`theorem escaped_or (p q : Prop) : p \/ q → p ∨ q := by intro h; exact h`,
    ).length === 0 &&
    normalizeLeanStatementSurfaceSyntax(String.raw`p \u2228 q`) === "p ∨ q",
  "theorem contract canonicalizes JSON escapes and parser-equivalent Lean operators",
)
const layoutOnlyContract = validateTheoremObligationDocument({
  schema_version: 1,
  theorem_obligations: [{
    obligation_id: "T-LAYOUT",
    lean_statement_sketch: [
      "theorem layout_only (n : Nat) :",
      "  n = (let x := n",
      "       x)",
    ].join("\n"),
  }],
})
assert(
  layoutOnlyContract.issues.length === 0 &&
    compareProofWithApprovedTheorems(
      layoutOnlyContract.declarations,
      [
        "theorem layout_only (n : Nat) : n = (",
        "  let x := n",
        "  x",
        ") := by rfl",
      ].join("\n"),
    ).length === 0,
  "theorem contract ignores parser-equivalent whitespace next to delimiters",
)
assert(
  theoremContractEncodingIssues(escapedOperatorInput).some((issue) =>
    issue.includes("literal \\uXXXX escape")
  ),
  "candidate theorem writer can reject literal double-escaped Unicode before review",
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

const semanticCriticOwnershipRun = {
  stage: "SEMANTIC_CRITIQUE",
  artifactRoot: "candidates/ptx/9.3/units/fixture-b32",
} as RunState
assert(
  !stageInputArtifactAreas("SEMANTIC_CRITIQUE").includes("lean") &&
    !stageInputArtifactAreas("SEMANTIC_CRITIQUE").includes("theorems") &&
    criticStageOwnershipIssues(
      semanticCriticOwnershipRun,
      "Affected: candidates/ptx/9.3/units/fixture-b32/lean/FixtureB32-v1.lean",
    ).some((issue) => issue.includes("downstream/out-of-scope")) &&
    criticStageOwnershipIssues(
      semanticCriticOwnershipRun,
      "Affected: candidates/ptx/9.3/units/fixture-b32/semantics/semantics-v1.json",
    ).length === 0,
  "semantic critics cannot route semantic repair against stale downstream Lean/theorem artifacts",
)

const behaviorFixture = [
  "def exec (guard : Bool) (value : Bool) : Bool :=",
  "  match guard, value with",
  "  | true, true => true",
  "  | true, false => false",
  "  | false, _ => true",
].join("\n")
const behaviorBranches = leanBehaviorBranches(behaviorFixture)
const behaviorTarget = {
  name: "exec_guard_behavior",
  statement: "theorem exec_guard_behavior (g v : Bool) : exec g v = true",
  correctnessKind: "GUARD_BEHAVIOR" as const,
}
const completeBehaviorAudit = [
  "MAJOR: 0",
  "<!-- SPEC2LEAN_THEOREM_BEHAVIOR_AUDIT",
  JSON.stringify({
    schemaVersion: 1,
    entries: [{
      name: behaviorTarget.name,
      correctnessKind: behaviorTarget.correctnessKind,
      status: "PASS",
      branchIdsChecked: behaviorBranches.map((branch) => branch.branchId),
      counterexample: "NONE_FOUND",
    }],
  }),
  "-->",
].join("\n")
assert(
  behaviorBranches.length === 3 &&
    theoremBehaviorAuditIssues(
      completeBehaviorAudit,
      [behaviorTarget],
      behaviorBranches,
    ).length === 0 &&
    theoremBehaviorAuditIssues(
      completeBehaviorAudit.replace(behaviorBranches[0]!.branchId, "OMITTED-BRANCH"),
      [behaviorTarget],
      behaviorBranches,
    ).some((issue) => issue.includes("behavior audit omitted")),
  "theorem-strength review must account for every explicit branch of referenced Lean definitions",
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
const pipelineFixtureId = `pipeline-self-test-${randomUUID()}`
const pipelineRun = (suffix: string, stage: RunState["stage"]): RunState => ({
  schemaVersion: 1,
  runId: `${pipelineFixtureId}-${suffix}`,
  mode: "formalization",
  language: "ptx",
  specVersion: "9.3",
  unit: `${suffix}.b32`,
  unitSlug: `${suffix}-b32`,
  leanModuleName: `${suffix[0]!.toUpperCase()}${suffix.slice(1)}B32`,
  sourceManifest: "documents/sources/nvidia/ptx/9.3/source-manifest.json",
  artifactRoot: `candidates/pipeline-self-tests/${pipelineFixtureId}/${suffix}`,
  stage,
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
  revision: 1,
  gates: { A: "pending", B: "pending", C: "pending", THEOREM_STRENGTH: "pending", FINAL: "pending" },
  history: [{ at: "2026-01-01T00:00:00.000Z", from: "ARCHITECTURE_CRITIQUE", to: stage, reason: "pipeline scheduler fixture" }],
})
const metadataRun: RunState = {
  ...pipelineRun("identity", "SOURCE_CURATION"),
  qualityContractVersion: 1,
}
const normalizedMetadata = await normalizeExpectedArtifactContent(
  metadataRun,
  artifactContractForRun(metadataRun).outputPath,
  JSON.stringify({
    schema_version: 2,
    bundle_id: "fixture",
    language: "PTX",
    specification_version: "wrong",
    unit: "wrong.b32",
    semantic_payload: { statement: "must remain byte-for-byte as JSON data" },
  }),
  "source-curator",
)
const normalizedMetadataDocument = JSON.parse(normalizedMetadata.content) as Record<string, unknown>
assert(normalizedMetadataDocument.language === metadataRun.language &&
  normalizedMetadataDocument.specification_version === metadataRun.specVersion &&
  normalizedMetadataDocument.unit === metadataRun.unit &&
  normalizedMetadataDocument.schema_version === 3,
"orchestrator normalizes exact source artifact identity and schema metadata")
assert(JSON.stringify(normalizedMetadataDocument.semantic_payload) === JSON.stringify({ statement: "must remain byte-for-byte as JSON data" }),
  "deterministic metadata normalization does not modify semantic payload")
assert((await normalizeExpectedArtifactContent(metadataRun, "candidates/unrelated.json", "{}", "source-curator"))
  .normalizedFields.length === 0,
"deterministic metadata normalization applies only to the exact active artifact path")
const parkedRuns = [
  pipelineRun("left", "WAITING_GATE_A"),
  pipelineRun("right", "WAITING_GATE_B"),
]
const sourceManifestData = await readFile(
  resolve(REPO_ROOT, "documents/sources/nvidia/ptx/9.3/source-manifest.json"),
)
const pipelineBatch: FormalizationBatch = {
  schemaVersion: 1,
  batchId: pipelineFixtureId,
  language: "ptx",
  specVersion: "9.3",
  sourceManifest: parkedRuns[0]!.sourceManifest,
  autoApprove: false,
  concurrency: 2,
  executionMode: "STAGE_PIPELINE",
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
  runs: parkedRuns.map((run) => ({ unit: run.unit, runId: run.runId })),
  pipeline: {
    schemaVersion: 2,
    schedulingMode: "AGENT_PINNED",
    globalWorkers: 2,
    agentCaps: DEFAULT_PIPELINE_AGENT_CAPS,
    dependencies: [{
      role: "SOURCE_MANIFEST",
      path: parkedRuns[0]!.sourceManifest,
      sha256: createHash("sha256").update(sourceManifestData).digest("hex"),
    }],
    startedAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    leases: {},
    runs: Object.fromEntries(parkedRuns.map((run) => [run.runId, {
      totalTicks: 0,
      consecutiveRetries: 0,
    }])),
    jobs: [],
  },
}
try {
  await Promise.all(parkedRuns.map(saveRun))
  await saveBatch(pipelineBatch)
  const parkedResult = await runPipelinedBatch(pipelineBatch, {
    globalWorkers: 2,
    maxTicks: 1,
    maxStageRetries: 1,
    maxStageRevisions: 1,
    providerRetryBudgetSeconds: 1,
  })
  assert(
    parkedResult.status === "WAITING_HUMAN" &&
      parkedResult.batch.pipeline?.jobs.length === 0 &&
      parkedResult.batch.pipeline.controller === undefined,
    "pipeline parks independent human gates without starting a worker",
  )
} finally {
  await rm(resolve(REPO_ROOT, `runs/batches/${pipelineFixtureId}.json`), { force: true })
  await Promise.all(parkedRuns.map((run) =>
    rm(resolve(REPO_ROOT, `runs/${run.runId}`), { recursive: true, force: true })
  ))
}
const semanticParkFixtureId = `pipeline-semantic-park-${randomUUID()}`
const semanticParkRun: RunState = {
  ...pipelineRun("semantic", "WAITING_GATE_A"),
  runId: `${semanticParkFixtureId}-run`,
  artifactRoot: `candidates/pipeline-self-tests/${semanticParkFixtureId}/semantic`,
  benchmark: { autoApprove: true, startedAtUtc: "2026-01-01T00:00:00.000Z" },
}
const semanticParkArchitecture = [
  "# Semantic park fixture",
  "## Official source facts",
  "- OQ-1 is a test-only unresolved question.",
  "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
  JSON.stringify({
    schemaVersion: 1,
    entries: [{
      semanticId: "OQ-1",
      classification: "OPEN_QUESTION",
      statement: "A load-bearing state question requires human review.",
      evidenceIds: [],
      dependencyIds: [],
      stateAffecting: true,
      status: "OPEN",
    }],
  }),
  "-->",
].join("\n")
const semanticParkReview = [
  "# Architecture critique",
  "BLOCKER: 0",
  "MAJOR: 0",
  "MINOR: 0",
  "NOTE: 0",
  "PRE_GATE_REVISION_REQUIRED: false",
  "<!-- SPEC2LEAN_GATE_A_OQ_TRIAGE",
  JSON.stringify({
    schemaVersion: 1,
    entries: [{
      semanticId: "OQ-1",
      disposition: "GENUINE_HUMAN_REVIEW",
      rationale: "The bounded state transition cannot be selected without human semantics.",
    }],
  }),
  "-->",
].join("\n")
const semanticWaiverLocation = benchmarkDecisionLocation(semanticParkRun, "A")
try {
  await mkdir(resolve(REPO_ROOT, `${semanticParkRun.artifactRoot}/architecture`), { recursive: true })
  await mkdir(resolve(REPO_ROOT, `${semanticParkRun.artifactRoot}/reviews`), { recursive: true })
  await writeFile(
    resolve(REPO_ROOT, `${semanticParkRun.artifactRoot}/architecture/foundation-v1.md`),
    semanticParkArchitecture,
  )
  await writeFile(
    resolve(REPO_ROOT, `${semanticParkRun.artifactRoot}/reviews/architecture-critic-v1.md`),
    semanticParkReview,
  )
  semanticParkRun.executions = [
    {
      at: "2026-01-01T00:00:00.000Z",
      stage: "ARCHITECTURE",
      agent: "spec-architect",
      sessionId: "self-test-architecture",
      outcome: "SUCCESS",
      nextStage: "ARCHITECTURE_CRITIQUE",
      response: "self-test",
      publishedArtifacts: [{
        role: "ARCHITECTURE",
        path: `${semanticParkRun.artifactRoot}/architecture/foundation-v1.md`,
        sha256: createHash("sha256").update(semanticParkArchitecture).digest("hex"),
        sizeBytes: Buffer.byteLength(semanticParkArchitecture),
        stage: "ARCHITECTURE",
        producingExecution: { agent: "spec-architect", sessionId: "self-test-architecture" },
        runRevision: 2,
      }],
    },
    {
      at: "2026-01-01T00:00:01.000Z",
      stage: "ARCHITECTURE_CRITIQUE",
      agent: "architecture-critic",
      sessionId: "self-test-critic",
      outcome: "SUCCESS",
      nextStage: "WAITING_GATE_A",
      response: "self-test",
      publishedArtifacts: [{
        role: "ARCHITECTURE_REVIEW",
        path: `${semanticParkRun.artifactRoot}/reviews/architecture-critic-v1.md`,
        sha256: createHash("sha256").update(semanticParkReview).digest("hex"),
        sizeBytes: Buffer.byteLength(semanticParkReview),
        stage: "ARCHITECTURE_CRITIQUE",
        producingExecution: { agent: "architecture-critic", sessionId: "self-test-critic" },
        runRevision: 3,
      }],
    },
  ]
  await saveRun(semanticParkRun)
  const semanticAdvance = await advanceBenchmarkGate(semanticParkRun)
  assert(semanticAdvance !== undefined, "benchmark gate advances with a semantic waiver")
  const semanticWaiver = JSON.parse(
    await readFile(resolve(REPO_ROOT, semanticAdvance.reviewPath), "utf8"),
  ) as {
    semanticAssumptions?: Array<{
      semanticId?: string
      policy?: string
      unresolved?: boolean
      humanApproved?: boolean
    }>
  }
  assert(
    semanticAdvance.run.stage === "SOURCE_CURATION" &&
      semanticWaiver.semanticAssumptions?.[0]?.semanticId === "OQ-1" &&
      semanticWaiver.semanticAssumptions[0]?.policy === "CONSERVATIVE_BOUNDED_SCOPE" &&
      semanticWaiver.semanticAssumptions[0]?.unresolved === true &&
      semanticWaiver.semanticAssumptions[0]?.humanApproved === false,
    "benchmark continuation records an unresolved conservative non-human semantic waiver",
  )
} finally {
  await unlink(resolve(REPO_ROOT, semanticWaiverLocation.reviewPath)).catch(() => undefined)
  await rm(resolve(REPO_ROOT, `runs/${semanticParkRun.runId}`), { recursive: true, force: true })
  await rm(
    resolve(REPO_ROOT, `candidates/pipeline-self-tests/${semanticParkFixtureId}`),
    { recursive: true, force: true },
  )
}
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
  [
    "Severity: MINOR",
    "Severity: NOTE",
    "BLOCKER: 0",
    "MAJOR: 0",
    "MINOR: 1",
    "NOTE: 1",
    "PRE_GATE_REVISION_REQUIRED: false",
  ].join("\n"),
  "WAITING_GATE_A",
  "ARCHITECTURE",
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
  [
    "Severity: MAJOR",
    "BLOCKER: 0",
    "MAJOR: 1",
    "MINOR: 0",
    "NOTE: 0",
    "PRE_GATE_REVISION_REQUIRED: true",
  ].join("\n"),
  "WAITING_GATE_A",
  "ARCHITECTURE",
)
assert(
  majorCriticResult.outcome === "REVISE",
  "BLOCKER/MAJOR critic reviews still require revision",
)
const criticSuccessWithMajor = normalizeCriticResultFromReview(
  {
    outcome: "SUCCESS",
    nextStage: "WAITING_GATE_B",
    summary: "incorrect success",
  },
  [
    "Severity: MAJOR",
    "BLOCKER: 0",
    "MAJOR: 1",
    "MINOR: 0",
    "NOTE: 0",
    "PRE_GATE_REVISION_REQUIRED: true",
  ].join("\n"),
  "WAITING_GATE_B",
  "SEMANTIC_EXTRACTION",
)
assert(
  criticSuccessWithMajor.outcome === "REVISE" &&
    criticSuccessWithMajor.nextStage === "SEMANTIC_EXTRACTION",
  "blocking review counts override an inconsistent critic SUCCESS",
)
const criticRetryWithReadyArtifact = normalizeCriticResultFromReview(
  {
    outcome: "RETRY",
    nextStage: "SEMANTIC_CRITIQUE",
    summary: "terminal result disagrees with durable review",
  },
  [
    "BLOCKER: 0",
    "MAJOR: 0",
    "MINOR: 0",
    "NOTE: 0",
    "PRE_GATE_REVISION_REQUIRED: false",
  ].join("\n"),
  "WAITING_GATE_B",
  "SEMANTIC_EXTRACTION",
)
assert(
  criticRetryWithReadyArtifact.outcome === "REVISE" &&
    criticRetryWithReadyArtifact.nextStage === "SEMANTIC_EXTRACTION",
  "complete critic artifact/result conflicts route upstream instead of retrying the critic",
)
const machineReadableReview = [
  "Finding 1",
  "Severity: MINOR",
  "Finding 2",
  "Severity: MINOR",
  "Finding 3",
  "Severity: NOTE",
  "BLOCKER: 0",
  "MAJOR: 0",
  "MINOR: 2",
  "NOTE: 1",
  "PRE_GATE_REVISION_REQUIRED: false",
].join("\n")
const machineReadableCounts = reviewDispositionCounts(machineReadableReview)
assert(
  machineReadableCounts?.BLOCKER === 0 &&
    machineReadableCounts.MAJOR === 0 &&
    machineReadableCounts.MINOR === 2 &&
    machineReadableCounts.NOTE === 1 &&
    reviewExplicitlyReady(machineReadableReview) &&
    !reviewExplicitlyRequiresRevision(machineReadableReview),
  "critic disposition block is machine-readable and explicitly ready",
)
assert(
  reviewFindingAccountabilityIssues(machineReadableReview).length === 0 &&
    reviewFindingAccountabilityIssues(
      machineReadableReview.replace("Severity: NOTE\n", ""),
    ).some((issue) => issue.includes("NOTE count is 1")),
  "critic review must describe every nonzero counted finding explicitly",
)
assert(
  duplicateJsonKeyIssues(
    '{"semanticClaims":[{"lifecycle":{"status":"ACTIVE","status":"ACTIVE"}}]}',
  ).some((issue) => issue.includes("$.semanticClaims[0].lifecycle")),
  "JSON integrity validation rejects duplicate keys instead of silently keeping the last value",
)
assert(
  !reviewExplicitlyReady("Not ready for human gate") &&
    !reviewExplicitlyReady("PRE_GATE_REVISION_REQUIRED: true\nReady for review") &&
    reviewExplicitlyRequiresRevision("PRE_GATE_REVISION_REQUIRED: true"),
  "critic readiness cannot be inferred from negated or contradictory prose",
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
  canTransition("LEAN_FORMALIZATION", "SOURCE_CURATION") &&
    canTransition("PROOF_GENERATION", "SOURCE_CURATION") &&
    canTransition("LEAN_FORMALIZATION", "SEMANTIC_EXTRACTION") &&
    canTransition("PROOF_GENERATION", "SEMANTIC_EXTRACTION"),
  "downstream deterministic provenance failures can return to semantic or source ownership",
)
assert(
  !shouldPreflightExistingSemanticEvidence({
    stage: "SEMANTIC_EXTRACTION",
    semanticV2: { mode: "LEGACY_FALLBACK" },
  }) &&
    shouldPreflightExistingSemanticEvidence({
      stage: "LEAN_FORMALIZATION",
      semanticV2: { mode: "LEGACY_FALLBACK" },
    }),
  "fresh source bundles reach the semantic producer before stale-semantics evidence validation",
)
assert(
  stageRevisionCount({
    executions: [
      {
        at: "2026-01-01T00:00:00.000Z",
        stage: "SEMANTIC_EXTRACTION",
        agent: "orchestrator-evidence-preflight",
        sessionId: "local",
        outcome: "REVISE",
        nextStage: "SOURCE_CURATION",
        response: "stale semantics fixture",
      },
      {
        at: "2026-01-01T00:00:01.000Z",
        stage: "SEMANTIC_EXTRACTION",
        agent: "orchestrator-evidence-preflight",
        sessionId: "local",
        outcome: "REVISE",
        nextStage: "SOURCE_CURATION",
        response: "stale semantics fixture",
      },
    ],
  } as RunState) === 0,
  "deterministic evidence routing does not consume semantic critic revision budget",
)
const stalePreflightRun = pipelineRun("stale", "SOURCE_CURATION")
stalePreflightRun.executions = [
  {
    at: "2026-01-01T00:00:00.000Z",
    stage: "SOURCE_CURATION",
    agent: "source-curator-fast",
    sessionId: "fixture",
    outcome: "SUCCESS",
    nextStage: "SEMANTIC_EXTRACTION",
    response: "validated replacement source bundle",
  },
  {
    at: "2026-01-01T00:00:01.000Z",
    stage: "SEMANTIC_EXTRACTION",
    agent: "orchestrator-evidence-preflight",
    sessionId: "local",
    outcome: "REVISE",
    nextStage: "SOURCE_CURATION",
    response: "semantic SOURCE_FACT references old fragment IDs",
  },
]
stalePreflightRun.history = [{
  at: "2026-01-01T00:00:01.000Z",
  from: "SEMANTIC_EXTRACTION",
  to: "SOURCE_CURATION",
  reason: "deterministic evidence preflight routed the repair to source curation: stale fixture",
}]
assert(
  shouldRecoverStaleSemanticPreflight(stalePreflightRun),
  "runs stranded by the old stale-semantics preflight resume at the semantic producer without another source rewrite",
)
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
const elaborationMappingPath = "candidates/ptx/9.3/units/or-b32/lean/OrB32-v7.lean"
const elaborationObligations = JSON.parse(await readFile(
  resolve(REPO_ROOT, "candidates/ptx/9.3/units/or-b32/theorems/obligations-v5.json"),
  "utf8",
)) as unknown
assert(
  (await theoremElaborationIssues(baseArtifactRun, elaborationObligations, elaborationMappingPath)).length === 0,
  "approved theorem headers elaborate in the transformed intended Lean module context",
)
assert(
  (await theoremElaborationIssues(baseArtifactRun, {
    schema_version: 1,
    theorem_obligations: [{
      obligation_id: "BROKEN-ELABORATION",
      lean_statement_sketch: "theorem broken_elaboration (x : TypeThatDoesNotExist) : True",
    }],
  }, elaborationMappingPath)).some((issue) => issue.includes("do not elaborate")),
  "unknown theorem types are rejected deterministically before theorem-strength critique",
)
const ecmaArtifactRun: RunState = {
  ...baseArtifactRun,
  runId: "ecmascript-2025-ToBoolean-self-test",
  language: "ecmascript",
  specVersion: "2025",
  unit: "ToBoolean",
  unitSlug: "toboolean",
  leanModuleName: "ToBoolean",
  sourceManifest: "documents/sources/ecmascript/2025/source-manifest.json",
  artifactRoot: "candidates/ecmascript/2025/units/toboolean",
  stage: "LEAN_FORMALIZATION",
}
const artifactRecoveryRoot = `candidates/self-test/artifact-recovery-${randomUUID()}`
try {
  const architectureRecoveryRun: RunState = {
    ...baseArtifactRun,
    runId: `artifact-recovery-${randomUUID()}`,
    artifactRoot: artifactRecoveryRoot,
    stage: "ARCHITECTURE",
  }
  const architecturePath = artifactContractForRun(architectureRecoveryRun).outputPath
  await mkdir(resolve(REPO_ROOT, dirname(architecturePath)), { recursive: true })
  await writeFile(
    resolve(REPO_ROOT, architecturePath),
    [
      "# Bounded scope",
      "Official source facts and evidence are recorded here.",
      "Project design dependency is explicit.",
      "Assumptions, ambiguities, and open questions remain visible.",
      "Gate A review checklist.",
      "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
      '{"schemaVersion":1,"entries":[{"semanticId":"D-1","classification":"DESIGN_DEPENDENCY","statement":"bounded test design","evidenceIds":[],"dependencyIds":[],"stateAffecting":false,"status":"RESOLVED"}]}',
      "-->",
    ].join("\n"),
  )
  const recoveredArchitecture = await recoverResultFromVerifiedArtifact(architectureRecoveryRun)
  assert(
    recoveredArchitecture?.outcome === "SUCCESS" &&
      recoveredArchitecture.nextStage === "ARCHITECTURE_CRITIQUE",
    "valid written artifact recovers a lost terminal protocol response",
  )

  const criticRecoveryRun: RunState = {
    ...architectureRecoveryRun,
    stage: "ARCHITECTURE_CRITIQUE",
  }
  const architectureRecoveryData = await readFile(resolve(REPO_ROOT, architecturePath))
  criticRecoveryRun.executions = [{
    at: "2026-01-01T00:00:00.000Z",
    stage: "ARCHITECTURE",
    agent: "spec-architect",
    sessionId: "self-test-recovery",
    outcome: "SUCCESS",
    nextStage: "ARCHITECTURE_CRITIQUE",
    response: "self-test",
    publishedArtifacts: [{
      role: "ARCHITECTURE",
      path: architecturePath,
      sha256: createHash("sha256").update(architectureRecoveryData).digest("hex"),
      sizeBytes: architectureRecoveryData.length,
      stage: "ARCHITECTURE",
      producingExecution: { agent: "spec-architect", sessionId: "self-test-recovery" },
      runRevision: 2,
    }],
  }]
  const criticPath = artifactContractForRun(criticRecoveryRun).outputPath
  await mkdir(resolve(REPO_ROOT, dirname(criticPath)), { recursive: true })
  await writeFile(
    resolve(REPO_ROOT, criticPath),
    [
      "# Architecture review",
      "Finding 1",
      "Severity: MINOR",
      "A bounded non-blocking documentation observation.",
      "BLOCKER: 0",
      "MAJOR: 0",
      "MINOR: 1",
      "NOTE: 0",
      "PRE_GATE_REVISION_REQUIRED: false",
      "<!-- SPEC2LEAN_GATE_A_OQ_TRIAGE",
      '{"schemaVersion":1,"entries":[]}',
      "-->",
    ].join("\n"),
  )
  const recoveredCritic = await recoverResultFromVerifiedArtifact(criticRecoveryRun)
  assert(
    recoveredCritic?.outcome === "SUCCESS" &&
      recoveredCritic.nextStage === "WAITING_GATE_A",
    "critic recovery requires a valid explicit zero-blocker disposition",
  )
} finally {
  await rm(resolve(REPO_ROOT, artifactRecoveryRoot), { recursive: true, force: true })
}
assert(
  leanDeclarationNamespace(ecmaArtifactRun) === "Spec2Lean.ECMAScript.ToBoolean" &&
    leanPackagePath(ecmaArtifactRun) === "lean/Spec2Lean/ECMAScript/ToBoolean.lean" &&
    leanPackagePath(ecmaArtifactRun, true) === "lean/Spec2Lean/ECMAScript/ToBooleanProofs.lean",
  "non-PTX runs receive language-scoped Lean namespaces and package paths",
)
assert(
  buildGeneralPrompt(ecmaArtifactRun).includes(
    "Required Lean namespace: Spec2Lean.ECMAScript.ToBoolean",
  ),
  "non-PTX agents receive the exact language-scoped namespace contract",
)
assert(
  executionAgentForRun(
    { ...ecmaArtifactRun, stage: "SOURCE_CURATION" },
    "source-curator",
  ) === "source-curator",
  "non-PTX source curation uses the generic curator instead of the PTX fast path",
)
const fastCuratorRun: RunState = {
  ...baseArtifactRun,
  stage: "SOURCE_CURATION",
}
const fastCuratorBindings = await Promise.all([
  ["ARCHITECTURE" as const, "ARCHITECTURE" as const, "spec-architect", `${fastCuratorRun.artifactRoot}/architecture/foundation-v4.md`],
  ["ARCHITECTURE_REVIEW" as const, "ARCHITECTURE_CRITIQUE" as const, "architecture-critic", `${fastCuratorRun.artifactRoot}/reviews/architecture-critic-v4.md`],
] as const).then((entries) => Promise.all(entries.map(async ([role, stage, agent, path], index) => {
  const data = await readFile(resolve(REPO_ROOT, path))
  const sessionId = `fast-curator-input-${index}`
  return {
    at: `2026-01-01T00:00:0${index}.000Z`,
    stage,
    agent,
    sessionId,
    outcome: "SUCCESS",
    nextStage: stage === "ARCHITECTURE" ? "ARCHITECTURE_CRITIQUE" as const : "WAITING_GATE_A" as const,
    response: "self-test",
    publishedArtifacts: [{
      role,
      path,
      sha256: createHash("sha256").update(data).digest("hex"),
      sizeBytes: data.length,
      stage,
      producingExecution: { agent, sessionId },
      runRevision: index + 2,
    }],
  }
})))
fastCuratorRun.executions = fastCuratorBindings
const sourceCurationPrompt = await buildStageInputContext(fastCuratorRun)
assert(
  sourceCurationPrompt.includes("additionalProperties=false") &&
    sourceCurationPrompt.includes('language="ptx", specification_version="9.3"') &&
    sourceCurationPrompt.includes('Canonical source document shape: {"document_id"') &&
    sourceCurationPrompt.includes('Canonical fragment shape: {"fragment_id"') &&
    sourceCurationPrompt.includes("fragment_ids and gap_ids are mandatory arrays"),
  "source curators receive the exact canonical v3 object shapes instead of inferring schema layout",
)
assert(
  pipelineAgentForRun(fastCuratorRun) === "source-curator-fast",
  "first PTX source pass is routed to its dedicated fast-curator worker",
)
assert(
  pipelineAgentForRun({
    ...fastCuratorRun,
    executions: [{
      at: "2026-01-01T00:00:01.000Z",
      stage: "SOURCE_CURATION",
      agent: "source-curator-fast",
      sessionId: "fixture",
      outcome: "RETRY",
      nextStage: "SOURCE_CURATION",
      response: "bounded fast path unavailable",
    }],
  }) === "source-curator",
  "PTX source fallback moves to the separate full-curator worker",
)
const fastCuratorBlocked: RunState = {
  ...fastCuratorRun,
  stage: "BLOCKED",
  executions: [{
    at: "2026-01-01T00:00:01.000Z",
    stage: "SOURCE_CURATION",
    agent: "source-curator-fast",
    sessionId: "fixture",
    outcome: "BLOCKED",
    nextStage: "BLOCKED",
    response: "schema repair failed",
    artifactProduced: true,
  }],
}
const recoveredFastCurator = await recoverNonAuthoritativeSourceBlock(fastCuratorBlocked)
assert(
  recoveredFastCurator?.stage === "SOURCE_CURATION" &&
    pipelineAgentForRun(recoveredFastCurator) === "source-curator",
  "a legacy fast-curator BLOCKED run resumes through the authoritative full curator",
)
const normalizedFastBlock = normalizeFastPathTerminalResult(
  fastCuratorRun,
  "source-curator-fast",
  {
    outcome: "BLOCKED",
    nextStage: "BLOCKED",
    summary: "candidate schema mismatch",
  },
)
assert(
  normalizedFastBlock.outcome === "RETRY" &&
    normalizedFastBlock.nextStage === "SOURCE_CURATION",
  "a fast curator cannot turn structural failure into a terminal semantic block",
)
assert(
  stageAttempt(fastCuratorBlocked, "SOURCE_CURATION") === 2,
  "a produced BLOCKED artifact remains immutable and advances the next artifact version",
)
assert(
  semanticExtractionBlockAuthority({
    semanticClaims: [{
      semanticId: "OQ-STATE",
      classification: "OPEN_QUESTION",
      stateAffecting: true,
      lifecycle: { status: "ACTIVE" },
    }],
  }).includes("OQ-STATE") &&
    semanticExtractionBlockAuthority({
      semanticClaims: [{
        semanticId: "OQ-NOTE",
        classification: "OPEN_QUESTION",
        stateAffecting: false,
        lifecycle: { status: "ACTIVE" },
      }],
    }).length === 0,
  "semantic terminal BLOCKED is reserved for active state-affecting open questions",
)
const structuralSemanticRoot = `candidates/pipeline-self-tests/${pipelineFixtureId}/semantic-block`
const structuralSemanticPath = `${structuralSemanticRoot}/semantics/semantics-v1.json`
const straySemanticPath = `${structuralSemanticRoot}/semantics/semantics-v999.json`
const structuralSemanticSource = JSON.stringify({ semanticClaims: [] })
await mkdir(dirname(resolve(REPO_ROOT, structuralSemanticPath)), { recursive: true })
await writeFile(resolve(REPO_ROOT, structuralSemanticPath), structuralSemanticSource)
await writeFile(resolve(REPO_ROOT, straySemanticPath), JSON.stringify({
  semanticClaims: [{
    semanticId: "STRAY-OQ",
    classification: "OPEN_QUESTION",
    stateAffecting: true,
    lifecycle: { status: "ACTIVE" },
  }],
}))
const structuralSemanticBlock: RunState = {
  ...baseArtifactRun,
  stage: "BLOCKED",
  artifactRoot: structuralSemanticRoot,
  executions: [{
    at: "2026-01-01T00:00:01.000Z",
    stage: "SEMANTIC_EXTRACTION",
    agent: "semantic-extractor",
    sessionId: "fixture",
    outcome: "BLOCKED",
    nextStage: "BLOCKED",
    response: "coverage validator mismatch",
    artifactProduced: true,
    artifactPath: structuralSemanticPath,
    artifactAfterSha256: createHash("sha256").update(structuralSemanticSource).digest("hex"),
  }],
}
assert(
  (await recoverNonAuthoritativeSemanticBlock(structuralSemanticBlock))?.stage === "SEMANTIC_EXTRACTION",
  "blocked recovery uses the exact execution artifact rather than a stray higher version",
)
await writeFile(resolve(REPO_ROOT, structuralSemanticPath), JSON.stringify({ semanticClaims: [{ semanticId: "mutated" }] }))
assert(
  await recoverNonAuthoritativeSemanticBlock(structuralSemanticBlock) === undefined,
  "blocked recovery fails closed when the exact recorded artifact hash changes",
)
await rm(resolve(REPO_ROOT, structuralSemanticRoot), { recursive: true, force: true })
const legacyRevisionRun: RunState = {
  ...baseArtifactRun,
  stage: "SEMANTIC_EXTRACTION",
  semanticV2: {
    profilePath: "fixture-profile.json",
    sharedEnvironmentPath: "fixture-environment.json",
    mode: "LEGACY_FALLBACK",
    missingRequiredSemanticIds: [],
    current: {
      attempt: 2,
      deltaPath: "fixture/semantic-delta-v2.json",
      materializedPath: "fixture/semantics-v2.json",
      criticPacketPath: "fixture/critic-v2.json",
    },
    events: [],
  },
  executions: [
    {
      at: "2026-01-01T00:00:01.000Z",
      stage: "SEMANTIC_EXTRACTION",
      agent: "semantic-extractor-delta",
      sessionId: "delta",
      outcome: "RETRY",
      nextStage: "SEMANTIC_EXTRACTION",
      response: "invalid delta",
      artifactProduced: true,
    },
    {
      at: "2026-01-01T00:00:02.000Z",
      stage: "SEMANTIC_EXTRACTION",
      agent: "semantic-extractor",
      sessionId: "full",
      outcome: "BLOCKED",
      nextStage: "BLOCKED",
      response: "repairable coverage mismatch",
      artifactProduced: true,
    },
  ],
}
assert(
  artifactContractForRun(legacyRevisionRun).outputPath.endsWith("semantics-v4.json"),
  "legacy semantic repair advances beyond reserved delta and existing full-semantic revisions",
)
assert(
  sourceBundleIdentityIssues(fastCuratorRun, {
    language: "PTX",
    specification_version: "9.3",
    unit: "cnot.b32",
  }).join("\n").includes('expected "ptx", received "PTX"'),
  "source identity diagnostics expose exact case-sensitive expected and received values",
)
const explicitLoadBearingGapBundle = {
  evidence_gaps: [{ gap_id: "GAP-1", impact: "LOAD_BEARING" }],
  coverage_matrix: [{ status: "GAP", gap_ids: ["GAP-1"] }],
}
assert(
  sourceCurationBlockAuthority(explicitLoadBearingGapBundle, [
    "source bundle has unresolved LOAD_BEARING evidence gap: GAP-1",
  ]) &&
    !sourceCurationBlockAuthority(explicitLoadBearingGapBundle, [
      "source bundle has unresolved LOAD_BEARING evidence gap: GAP-1",
      'source bundle identity mismatch for language: expected "ptx", received "PTX"',
    ]),
  "terminal source BLOCKED requires an explicit coverage-linked load-bearing gap and no structural/identity defect",
)
assert(
  pipelineAgentForRun({
    ...baseArtifactRun,
    semanticV2: {
      profilePath: "fixture-profile.json",
      sharedEnvironmentPath: "fixture-environment.json",
      mode: "DELTA_FAST_PATH",
      missingRequiredSemanticIds: [],
      events: [],
    },
  }) === "semantic-extractor-delta",
  "semantic delta work has a dedicated extractor worker",
)
assert(
  pipelineAgentForRun({ ...baseArtifactRun, stage: "LEAN_FORMALIZATION" }) ===
    "lean-formalizer" &&
    pipelineAgentForRun({ ...baseArtifactRun, stage: "THEOREM_GENERATION" }) ===
      "theorem-designer",
  "Lean implementation and theorem design use distinct bounded sub-agent queues",
)
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
const benchmarkGateArtifacts = [
  {
    role: "ARCHITECTURE" as const,
    path: `${benchmarkRun.artifactRoot}/architecture/foundation-v4.md`,
    stage: "ARCHITECTURE" as const,
    agent: "spec-architect",
  },
  {
    role: "ARCHITECTURE_REVIEW" as const,
    path: `${benchmarkRun.artifactRoot}/reviews/architecture-critic-v4.md`,
    stage: "ARCHITECTURE_CRITIQUE" as const,
    agent: "architecture-critic",
  },
]
benchmarkRun.executions = await Promise.all(benchmarkGateArtifacts.map(async (artifact, index) => {
  const data = await readFile(resolve(REPO_ROOT, artifact.path))
  const sessionId = `benchmark-self-test-${index}`
  return {
    at: `2026-01-01T00:00:0${index}.000Z`,
    stage: artifact.stage,
    agent: artifact.agent,
    sessionId,
    outcome: "SUCCESS",
    nextStage: artifact.stage === "ARCHITECTURE" ? "ARCHITECTURE_CRITIQUE" as const : "WAITING_GATE_A" as const,
    response: "self-test",
    publishedArtifacts: [{
      role: artifact.role,
      path: artifact.path,
      sha256: createHash("sha256").update(data).digest("hex"),
      sizeBytes: data.length,
      stage: artifact.stage,
      producingExecution: { agent: artifact.agent, sessionId },
      runRevision: index + 2,
    }],
  }
}))
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

const benchmarkReentryId = `benchmark-reentry-self-test-${randomUUID()}`
const benchmarkReentryRoot = `candidates/self-test/${benchmarkReentryId}`
const benchmarkReentryRun: RunState = {
  ...benchmarkRun,
  runId: benchmarkReentryId,
  unit: "benchmark.reentry",
  unitSlug: benchmarkReentryId,
  artifactRoot: benchmarkReentryRoot,
}
const benchmarkReentryV1 = benchmarkDecisionLocation(benchmarkReentryRun, "A", 1)
const benchmarkReentryV2 = benchmarkDecisionLocation(benchmarkReentryRun, "A", 2)
try {
  await mkdir(resolve(REPO_ROOT, `${benchmarkReentryRoot}/architecture`), { recursive: true })
  await mkdir(resolve(REPO_ROOT, `${benchmarkReentryRoot}/reviews`), { recursive: true })
  await writeFile(resolve(REPO_ROOT, `${benchmarkReentryRoot}/architecture/foundation-v1.md`), "first architecture\n")
  await writeFile(resolve(REPO_ROOT, `${benchmarkReentryRoot}/reviews/architecture-critic-v1.md`), "first review\n")
  const bindBenchmarkReentry = async (version: number): Promise<void> => {
    const architecturePath = `${benchmarkReentryRoot}/architecture/foundation-v${version}.md`
    const reviewPath = `${benchmarkReentryRoot}/reviews/architecture-critic-v${version}.md`
    const [architectureData, reviewData] = await Promise.all([
      readFile(resolve(REPO_ROOT, architecturePath)),
      readFile(resolve(REPO_ROOT, reviewPath)),
    ])
    benchmarkReentryRun.executions = [
      {
        at: `2026-01-01T00:00:0${version}.000Z`,
        stage: "ARCHITECTURE",
        agent: "spec-architect",
        sessionId: `reentry-architecture-${version}`,
        outcome: "SUCCESS",
        nextStage: "ARCHITECTURE_CRITIQUE",
        response: "self-test",
        publishedArtifacts: [{
          role: "ARCHITECTURE",
          path: architecturePath,
          sha256: createHash("sha256").update(architectureData).digest("hex"),
          sizeBytes: architectureData.length,
          stage: "ARCHITECTURE",
          producingExecution: { agent: "spec-architect", sessionId: `reentry-architecture-${version}` },
          runRevision: version * 2,
        }],
      },
      {
        at: `2026-01-01T00:00:0${version + 1}.000Z`,
        stage: "ARCHITECTURE_CRITIQUE",
        agent: "architecture-critic",
        sessionId: `reentry-review-${version}`,
        outcome: "SUCCESS",
        nextStage: "WAITING_GATE_A",
        response: "self-test",
        publishedArtifacts: [{
          role: "ARCHITECTURE_REVIEW",
          path: reviewPath,
          sha256: createHash("sha256").update(reviewData).digest("hex"),
          sizeBytes: reviewData.length,
          stage: "ARCHITECTURE_CRITIQUE",
          producingExecution: { agent: "architecture-critic", sessionId: `reentry-review-${version}` },
          runRevision: version * 2 + 1,
        }],
      },
    ]
  }
  await bindBenchmarkReentry(1)
  const first = await recordBenchmarkAutoAdvance(benchmarkReentryRun, "A")
  await writeFile(resolve(REPO_ROOT, `${benchmarkReentryRoot}/architecture/foundation-v2.md`), "revised architecture\n")
  await writeFile(resolve(REPO_ROOT, `${benchmarkReentryRoot}/reviews/architecture-critic-v2.md`), "revised review\n")
  await bindBenchmarkReentry(2)
  await writeFile(resolve(REPO_ROOT, `${benchmarkReentryRoot}/architecture/foundation-v999.md`), "stray architecture\n")
  await writeFile(resolve(REPO_ROOT, `${benchmarkReentryRoot}/reviews/architecture-critic-v999.md`), "stray review\n")
  const revised = await recordBenchmarkAutoAdvance(benchmarkReentryRun, "A")
  const recoveredRevised = await recordBenchmarkAutoAdvance(benchmarkReentryRun, "A")
  assert(
    first.reviewPath === benchmarkReentryV1.reviewPath && !first.recovered &&
      revised.reviewPath === benchmarkReentryV2.reviewPath && !revised.recovered &&
      recoveredRevised.reviewPath === benchmarkReentryV2.reviewPath && recoveredRevised.recovered,
    "benchmark gate uses the recorded successful artifacts and ignores later stray vN files",
  )
} finally {
  await rm(resolve(REPO_ROOT, benchmarkReentryRoot), { recursive: true, force: true })
  await rm(
    resolve(REPO_ROOT, `reviews/${benchmarkReentryRun.language}-${benchmarkReentryRun.unitSlug}`),
    { recursive: true, force: true },
  )
}

const immutabilityId = `artifact-immutability-self-test-${randomUUID()}`
const immutabilityPath = `candidates/self-test/${immutabilityId}/architecture/foundation-v1.md`
const immutabilityReviewPath = `reviews/tool-tests/${immutabilityId}.json`
const immutabilitySession = `session-${immutabilityId}`
const immutabilityRun: RunState = {
  ...baseArtifactRun,
  runId: immutabilityId,
  artifactRoot: `candidates/self-test/${immutabilityId}`,
  stage: "ARCHITECTURE",
  activeExecution: {
    startedAt: "2026-01-01T00:00:00.000Z",
    stage: "ARCHITECTURE",
    agent: "spec-architect",
    sessionId: immutabilitySession,
    expectedArtifact: immutabilityPath,
  },
}
try {
  await mkdir(resolve(REPO_ROOT, dirname(immutabilityPath)), { recursive: true })
  const reviewedBody = "reviewed immutable architecture\n"
  await writeFile(resolve(REPO_ROOT, immutabilityPath), reviewedBody)
  await saveRun(immutabilityRun)
  assert(
    await candidateReplacementIssue(immutabilityPath, immutabilitySession) === undefined,
    "an active producing session may repair its unpublished artifact",
  )
  await mkdir(resolve(REPO_ROOT, dirname(immutabilityReviewPath)), { recursive: true })
  await writeFile(resolve(REPO_ROOT, immutabilityReviewPath), JSON.stringify({
    artifacts: [{
      relativePath: immutabilityPath,
      sha256: createHash("sha256").update(reviewedBody).digest("hex"),
      sizeBytes: Buffer.byteLength(reviewedBody),
    }],
  }))
  assert(
    (await candidateReplacementIssue(immutabilityPath, immutabilitySession))
      ?.includes("review record") === true,
    "a hash-reviewed artifact cannot be replaced even by the former producing session",
  )
} finally {
  await rm(resolve(REPO_ROOT, `runs/${immutabilityId}`), { recursive: true, force: true })
  await rm(resolve(REPO_ROOT, `candidates/self-test/${immutabilityId}`), { recursive: true, force: true })
  await unlink(resolve(REPO_ROOT, immutabilityReviewPath)).catch(() => undefined)
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

const productionSourceIndex = await ensureSourceIndex({
  language: "ptx",
  specificationVersion: "9.3",
  sourceManifest: "documents/sources/nvidia/ptx/9.3/source-manifest.json",
})
assert(
  productionSourceIndex.status === "READY" &&
    productionSourceIndex.path === ".spec2lean-cache/ptx/9.3/source-index-v2.json",
  "self-test deterministically prepares the production multi-rendition source index",
)
const ptxSourceIndex = JSON.parse(
  await readFile(resolve(REPO_ROOT, ".spec2lean-cache/ptx/9.3/source-index-v2.json"), "utf8"),
) as {
  schemaVersion: number
  sections: Array<{
    anchor: string
    startLine: number
    endLine: number
    heading: string
    searchText?: string
  }>
  renditions: Array<{ kind: "html" | "pdf"; sections: unknown[] }>
}
assert(ptxSourceIndex.schemaVersion === 2, "production source index uses the multi-rendition schema")
assert(
  ptxSourceIndex.renditions.some((item) => item.kind === "html" && item.sections.length > 0) &&
    ptxSourceIndex.renditions.some((item) => item.kind === "pdf" && item.sections.length > 0),
  "production source index contains searchable HTML and PDF renditions",
)
for (const [unit, expectedAnchor] of [
  ["add.u64", "integer-arithmetic-instructions-add"],
  ["add.f32", "floating-point-instructions-add"],
  ["add.f16", "half-precision-floating-point-instructions-add"],
  ["add.f32.f16", "mixed-precision-floating-point-instructions-add"],
  ["neg.s32", "integer-arithmetic-instructions-neg"],
] as const) {
  const resolution = resolvePtxInstructionSection(ptxSourceIndex.sections, unit)
  assert(
    resolution.status === "FOUND" && resolution.section.anchor === expectedAnchor,
    `typed PTX resolver selects ${expectedAnchor} for ${unit}`,
  )
}

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
  (retrievalProfile.context as { architectureTargetMaxLines?: number })
    ?.architectureTargetMaxLines === 80,
  "PTX architecture retrieval has a smaller deterministic target budget",
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
const gateRuntimeSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/gate-runtime.ts"),
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
  runLoopSource.includes("advanceBenchmarkGate") &&
    gateRuntimeSource.includes("recordBenchmarkAutoAdvance") &&
    gateRuntimeSource.includes('"BENCHMARK_COMPLETE"'),
  "single-run and pipeline controllers share deterministic benchmark gate decisions",
)
const pipelineRuntimeSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/pipeline-runtime.ts"),
  "utf8",
)
assert(
  pipelineRuntimeSource.includes("verifyPipelineDependencies") &&
    pipelineRuntimeSource.includes("sharedRuntimeStartup ??= startOpenCode()") &&
    pipelineRuntimeSource.includes("sharedRuntime?.runtime.server.close()") &&
    pipelineRuntimeSource.includes("selectedAgent !== worker.agent") &&
    pipelineRuntimeSource.includes("selectPipelineCandidate(candidates, worker.agent)") &&
    pipelineRuntimeSource.includes("loadRunForPipelineRouting") &&
    pipelineRuntimeSource.includes("prepareSemanticV2Run(run)") &&
    pipelineRuntimeSource.includes("await executeTick(lease.runId") &&
    pipelineRuntimeSource.includes("manifestGenerationIncludedInServiceMs: true") &&
    pipelineRuntimeSource.includes('"PARKED_SEMANTIC_REVIEW"'),
  "pipeline pins language inputs, isolates agent queues over one shared runtime, executes bounded ticks, and measures manifest work",
)
const runnerSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/runner.ts"),
  "utf8",
)
assert(
  runnerSource.includes("architectureQuestionTriageRequiresRevision") &&
    runnerSource.includes('nextStage: "ARCHITECTURE"'),
  "architecture critic SUCCESS cannot bypass deterministic remove/reclassify triage",
)
assert(
  runnerSource.includes("run.activeExecution.model === executionModel.full") &&
    runnerSource.match(/model: executionModel\.full/g)?.length === 2,
  "active-session recovery is pinned to explicit model provenance",
)
assert(
  runnerSource.includes('run.stage === "LEAN_FORMALIZATION"') &&
    runnerSource.includes('generateVerifiedTraceability(run, "SEMANTICS")') &&
    runnerSource.includes("generationMs: Date.now() - startedAt") &&
    runnerSource.includes("writeTraceabilityManifest(manifest)"),
  "verified Lean formalization automatically emits and times its evidence manifest",
)
assert(
  runnerSource.match(/generateVerifiedTraceability\(run, "PROOFS"\)/g)?.length === 2 &&
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
  (await loadAgentModel("proof-engineer")).full === "openai/gpt-5.4-mini",
  "proof engineer uses the configured GPT-5.4 mini model",
)
assert(
  agentWaitBudgetMs("SEMANTIC_EXTRACTION", "semantic-extractor-delta") === 4 * 60 * 1000,
  "semantic delta extraction has a bounded four-minute wait budget",
)
assert(
  agentWaitBudgetMs("LEAN_FORMALIZATION", "lean-formalizer") === 8 * 60 * 1000,
  "ordinary agent stages retain an eight-minute wait budget",
)
for (const criticAgent of [
  "architecture-critic",
  "semantics-critic",
  "lean-mapping-critic",
  "theorem-strength-critic",
  "final-critic",
]) {
  const prompt = await readFile(
    resolve(REPO_ROOT, `.opencode/agents/${criticAgent}.md`),
    "utf8",
  )
  assert(
    ["BLOCKER: <number>", "MAJOR: <number>", "MINOR: <number>", "NOTE: <number>",
      "PRE_GATE_REVISION_REQUIRED: <true|false>"].every((line) => prompt.includes(line)),
    `${criticAgent} emits the deterministic critic disposition block`,
  )
}
for (const pipelineAgent of PIPELINE_AGENTS) {
  const prompt = await readFile(
    resolve(REPO_ROOT, `.opencode/agents/${pipelineAgent}.md`),
    "utf8",
  )
  assert(
    prompt.includes("candidate_validate: allow") &&
      prompt.includes("candidate_validate"),
    `${pipelineAgent} can run and is instructed to run same-session deterministic validation`,
  )
}
const architectPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/spec-architect.md"),
  "utf8",
)
assert(
  architectPrompt.includes("steps: 24") &&
    ["read: deny", "glob: deny", "grep: deny", "list: deny"].every(
      (permission) => architectPrompt.includes(permission),
    ) &&
    architectPrompt.includes('purpose="architecture"') &&
    architectPrompt.includes("candidate_architecture_write: allow") &&
    architectPrompt.includes("candidate_write: deny") &&
    architectPrompt.includes("at most one bounded replacement") &&
    architectPrompt.includes("Specification silence about every imaginable flag") &&
    architectPrompt.includes("SOURCE_FACT is an index root"),
  "architecture agent has bounded retrieval, exploration, and repair contracts",
)
const architectureCriticPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/architecture-critic.md"),
  "utf8",
)
assert(
  architectureCriticPrompt.includes("steps: 24") &&
  architectureCriticPrompt.includes("read: deny") &&
    architectureCriticPrompt.includes("internal index roots") &&
    architectureCriticPrompt.includes("Lack of source support alone is not a defect") &&
    architectureCriticPrompt.includes("Do not manufacture an OPEN_QUESTION") &&
    architectureCriticPrompt.includes("SPEC2LEAN_GATE_A_OQ_TRIAGE") &&
    architectureCriticPrompt.includes("REMOVE_OR_RECLASSIFY"),
  "architecture critic shares the architect classification and applicability policy",
)
for (const generatingAgent of [
  "spec-architect",
  "source-curator",
  "semantic-extractor",
  "lean-formalizer",
]) {
  const prompt = await readFile(
    resolve(REPO_ROOT, `.opencode/agents/${generatingAgent}.md`),
    "utf8",
  )
  assert(
    prompt.includes("candidate_validate") &&
      prompt.toLowerCase().includes("write") &&
      prompt.toLowerCase().includes("early"),
    `${generatingAgent} executes and persists before emitting the protocol result`,
  )
}
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
  theoremStrengthCriticPrompt.includes("constructor/branch coverage") &&
    theoremStrengthCriticPrompt.includes("counterexample") &&
    ["BLOCKER: <number>", "MAJOR: <number>", "MINOR: <number>", "NOTE: <number>"].every(
      (token) => theoremStrengthCriticPrompt.includes(token),
    ),
  "stage-specific theorem critic checks truth and has deterministic disposition output",
)
const leanFormalizerPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/lean-formalizer.md"),
  "utf8",
)
assert(
  leanFormalizerPrompt.includes("-- spec2lean: EXACT-ID-1") &&
    leanFormalizerPrompt.includes("candidate_validate") &&
    leanFormalizerPrompt.includes("Semantic preservation"),
  "Lean formalizer pins workflow protocol and traceability IDs",
)
const proofEngineerPrompt = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/proof-engineer.md"),
  "utf8",
)
assert(
  proofEngineerPrompt.includes("frozen theorem declarations") &&
    runnerSource.includes("# Exact frozen theorem declarations") &&
    runnerSource.includes("contractRepairTargets = await proofTargets(run)"),
  "proof repair receives exact approved declarations instead of reconstructing theorem headers",
)

const candidateTool = await readFile(
  resolve(REPO_ROOT, ".opencode/tools/candidate.ts"),
  "utf8",
)
assert(
  candidateTool.includes("JSON.parse(args.content)") &&
    candidateTool.includes("invalid JSON; artifact was not written") &&
    candidateTool.includes("candidate_architecture_write") &&
    candidateTool.includes("MAX_ARCHITECTURE_BYTES") &&
    candidateTool.includes("candidate_validate") &&
    candidateTool.includes("verifyTraceabilityManifest") &&
    candidateTool.includes("source bundle is missing the exact hash-bound official"),
  "candidate tools validate JSON, required source renditions, and same-session stage/traceability checks",
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

const ecmaCandidate = [
  "import Spec2Lean.Basic",
  "namespace Spec2Lean.ECMAScript.ToBoolean",
  "def marker := true",
  "end Spec2Lean.ECMAScript.ToBoolean",
  "",
].join("\n")
const ecmaPackage = packageTransform(ecmaCandidate, "ToBoolean", "ECMAScript")
assert(
  ecmaPackage.text === ecmaCandidate && ecmaPackage.isolatedNamespace === false,
  "Lean packaging accepts a non-PTX language namespace",
)

const deltaAgent = await readFile(
  resolve(REPO_ROOT, ".opencode/agents/semantic-extractor-delta.md"),
  "utf8",
)
assert(
  deltaAgent.includes("sourceBundleEvidenceId") &&
    deltaAgent.includes("explicit legacy fallback") &&
    deltaAgent.includes("copy shared entries into local claims"),
  "delta extractor preserves grounding, reuse, and fallback boundaries",
)

const normalizedLegacyClaims = collectSemanticProvenanceClaims({
  semantic_claims: [{
    claim_id: "SF-1",
    classification: "SOURCE_FACT",
    statement: "fact",
    evidence_fragment_ids: ["E-1"],
  }],
  design_dependencies: [{
    dependency_id: "D-MUL-1",
    classification: "DESIGN_DEPENDENCY",
    statement: "design",
    source_facts: ["SF-1"],
  }],
}, "fixture.json")
assert(
  normalizedLegacyClaims.some((claim) => claim.semanticId === "D-MUL-1") &&
    normalizedLegacyClaims.some((claim) => claim.semanticId === "SF-1"),
  "provenance catalog normalizes historical claim_id and dependency_id layouts",
)
const normalizedLegacyArchitecture = collectArchitectureProvenanceClaims([
  "- SOURCE FACT (SF-MUL-1): exact fact",
  "- DESIGN CHOICE (D-1): bounded design",
  "- **OQ-1:** unresolved question",
  "| SF-MUL-1 | D-1 |",
].join("\n"), "fixture.md")
assert(
  normalizedLegacyArchitecture.map((claim) => claim.semanticId).join(",") ===
    "D-1,OQ-1,SF-MUL-1",
  "architecture compatibility reader accepts definition bullets but not dependency-table references",
)
assert(
  validateArchitectureIndex([
    "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
    '{"schemaVersion":1,"entries":[{"semanticId":"D-1","classification":"DESIGN_DEPENDENCY","statement":"design","evidenceIds":["SF-MISSING"],"dependencyIds":[],"stateAffecting":false,"status":"RESOLVED"}]}',
    "-->",
  ].join("\n")).some((issue) => issue.includes("unknown evidenceId")),
  "canonical architecture index rejects invented provenance references",
)
const boundedStateArchitectureIndex = [
  "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
  JSON.stringify({
    schemaVersion: 1,
    entries: [
      {
        semanticId: "SF-1",
        classification: "SOURCE_FACT",
        statement: "The instruction writes its destination.",
        evidenceIds: [],
        dependencyIds: [],
        stateAffecting: true,
        status: "RESOLVED",
      },
      {
        semanticId: "OQ-1",
        classification: "OPEN_QUESTION",
        statement: "The source does not decide an applicable external state question.",
        evidenceIds: ["SF-1"],
        dependencyIds: ["SF-1"],
        stateAffecting: true,
        status: "OPEN",
      },
      {
        semanticId: "D-1",
        classification: "DESIGN_DEPENDENCY",
        statement: "The bounded project model contains only the destination state.",
        evidenceIds: ["SF-1"],
        dependencyIds: ["SF-1", "OQ-1"],
        stateAffecting: true,
        status: "RESOLVED",
      },
    ],
  }),
  "-->",
].join("\n")
assert(
  validateArchitectureIndex(boundedStateArchitectureIndex).length === 0,
  "architecture index permits an explicit project boundary without resolving its source question",
)
const genuineQuestionReview = [
  "BLOCKER: 0",
  "MAJOR: 0",
  "MINOR: 0",
  "NOTE: 0",
  "PRE_GATE_REVISION_REQUIRED: false",
  "<!-- SPEC2LEAN_GATE_A_OQ_TRIAGE",
  JSON.stringify({
    schemaVersion: 1,
    entries: [{
      semanticId: "OQ-1",
      disposition: "GENUINE_HUMAN_REVIEW",
      rationale: "The source-level question is applicable and remains load-bearing.",
    }],
  }),
  "-->",
].join("\n")
assert(
  validateArchitectureQuestionTriage(
    boundedStateArchitectureIndex,
    genuineQuestionReview,
  ).length === 0 &&
    !architectureQuestionTriageRequiresRevision(genuineQuestionReview),
  "Gate-A triage preserves a genuine state-affecting human semantic boundary",
)
const removableQuestionReview = genuineQuestionReview
  .replace("MAJOR: 0", "MAJOR: 1")
  .replace("PRE_GATE_REVISION_REQUIRED: false", "PRE_GATE_REVISION_REQUIRED: true")
  .replace("GENUINE_HUMAN_REVIEW", "REMOVE_OR_RECLASSIFY")
assert(
  validateArchitectureQuestionTriage(
    boundedStateArchitectureIndex,
    removableQuestionReview,
  ).length === 0 &&
    architectureQuestionTriageRequiresRevision(removableQuestionReview),
  "Gate-A triage deterministically routes speculative or misclassified questions back to architecture",
)
assert(
  validateArchitectureQuestionTriage(
    boundedStateArchitectureIndex,
    genuineQuestionReview.replace("OQ-1", "OQ-UNKNOWN"),
  ).some((issue) => issue.includes("unknown or non-state-affecting")),
  "Gate-A triage rejects invented open-question IDs",
)
const invalidArchitectureRelations = [
  "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
  JSON.stringify({
    schemaVersion: 1,
    entries: [
      {
        semanticId: "SF-1",
        classification: "SOURCE_FACT",
        statement: "fact",
        evidenceIds: ["SF-1"],
        dependencyIds: [],
        stateAffecting: true,
        status: "RESOLVED",
      },
      {
        semanticId: "OQ-1",
        classification: "OPEN_QUESTION",
        statement: "question",
        evidenceIds: [],
        dependencyIds: [],
        stateAffecting: true,
        status: "OPEN",
      },
      {
        semanticId: "DI-1",
        classification: "DERIVED_INTERPRETATION",
        statement: "derived",
        evidenceIds: ["OQ-1"],
        dependencyIds: ["OQ-1"],
        stateAffecting: true,
        status: "RESOLVED",
      },
    ],
  }),
  "-->",
].join("\n")
const invalidArchitectureIssues = validateArchitectureIndex(invalidArchitectureRelations)
assert(
  invalidArchitectureIssues.some((issue) => issue.includes("SOURCE_FACT must be an internal")) &&
    invalidArchitectureIssues.some((issue) => issue.includes("depends on open entry")) &&
    invalidArchitectureIssues.some((issue) => issue.includes("evidenceId is not a SOURCE_FACT")),
  "architecture validator rejects root misuse and resolved derivations from open questions",
)
const compactArchitectureFixture = [
  "# Fixture",
  "## Bounded scope and exclusions",
  "## Official source facts",
  "## Design dependencies",
  "## Fact-to-design mapping",
  "## Assumptions and open questions",
  "## Behavior and state effects",
  "## Validation and theorem families",
  "## Gate A checklist",
  "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
  '{"schemaVersion":1,"entries":[]}',
  "-->",
].join("\n")
assert(
  validateArtifactContent({ stage: "ARCHITECTURE" } as RunState, compactArchitectureFixture).length === 0,
  "architecture validator accepts the exact plural Design dependencies heading",
)
const sourceBundleWithoutPdfFragment = {
  schema_version: 2,
  bundle_id: "fixture",
  language: "ptx",
  specification_version: "9.3",
  unit: "fixture.b32",
  source_documents: [
    {
      document_id: "html",
      publisher: "NVIDIA",
      kind: "HTML",
      local_path: "documents/fixture.html",
      sha256: "a".repeat(64),
    },
    {
      document_id: "pdf",
      publisher: "NVIDIA",
      kind: "PDF",
      local_path: "documents/fixture.pdf",
      sha256: "b".repeat(64),
    },
  ],
  fragments: [{
    fragment_id: "F-HTML",
    document_id: "html",
    source_kind: "HTML",
    source_sha256: "a".repeat(64),
    exact_quote: "four stable source tokens",
    reason_for_inclusion: "fixture",
    locator: { anchor: "fixture" },
  }],
  evidence_gaps: [],
}
assert(
  validateArtifactContent(
    { stage: "SOURCE_CURATION" } as RunState,
    JSON.stringify(sourceBundleWithoutPdfFragment),
    sourceBundleWithoutPdfFragment,
  ).some((issue) => issue.includes("contains no PDF evidence fragment")),
  "source bundle cannot claim an official rendition without any evidence from it",
)
assert(
  artifactBudgetIssues(
    "ARCHITECTURE",
    "x".repeat(MAX_ARCHITECTURE_BYTES + 1),
  ).some((issue) => issue.includes("byte budget")),
  "architecture artifact byte budget is deterministic",
)
const leanQualityIssues = validateArtifactContent({
  stage: "LEAN_FORMALIZATION",
  language: "ptx",
  unit: "quality.b32",
  leanModuleName: "QualityB32",
} as RunState, [
  "import Spec2Lean.Basic",
  "namespace Spec2Lean",
  "namespace PTX",
  "namespace QualityB32",
  "-- spec2lean: SF-1",
  "def deadHelper := true",
].join("\n"))
assert(leanQualityIssues.some((issue) => issue.includes("module doc header")) &&
  leanQualityIssues.some((issue) => issue.includes("unused Lean declaration deadHelper")), "Lean quality validation rejects undocumented scope and dead helpers")
const outputLengthExecutions = [
  { failureClass: "OUTPUT_LENGTH_EXCEEDED" },
  { failureClass: "OUTPUT_LENGTH_EXCEEDED" },
] as RunState["executions"]
assert(
  outputLengthExecutions !== undefined &&
    consecutiveOutputLengthFailureCount(outputLengthExecutions, 0) === 0 &&
    consecutiveOutputLengthFailureCount(outputLengthExecutions, 1) === 1 &&
    outputLengthRetryLimitReached(outputLengthExecutions, 2),
  "output-length recovery permits one bounded retry and then stops unchanged repetition",
)
const providerRetryExecutions = [
  {
    stage: "SEMANTIC_EXTRACTION",
    outcome: "RETRY",
    failureClass: "PROVIDER_RETRY_BUDGET_EXCEEDED",
  },
  {
    stage: "SEMANTIC_EXTRACTION",
    outcome: "RETRY",
    failureClass: "PROVIDER_RETRY_BUDGET_EXCEEDED",
  },
] as RunState["executions"]
assert(
  providerRetryExecutions !== undefined &&
    isProviderAvailabilityFailure(providerRetryExecutions.at(-1)) &&
    semanticRetryState(providerRetryExecutions, "SEMANTIC_EXTRACTION")
      .consecutiveRetries === 0,
  "provider availability failures do not consume semantic retry budget",
)
const mixedRetryExecutions = [
  {
    stage: "SEMANTIC_CRITIQUE",
    outcome: "RETRY",
  },
  ...(providerRetryExecutions ?? []).map((execution) => ({
    ...execution,
    stage: "SEMANTIC_CRITIQUE" as const,
  })),
] as RunState["executions"]
assert(
  mixedRetryExecutions !== undefined &&
    semanticRetryState(mixedRetryExecutions, "SEMANTIC_CRITIQUE")
      .consecutiveRetries === 1,
  "durable retry reconstruction skips provider failures but preserves real critic retries",
)
const repeatedNoProgressExecutions = [
  {
    stage: "PROOF_GENERATION",
    outcome: "RETRY",
    artifactProduced: true,
    failureFingerprint: "same-lean-diagnostic",
  },
  {
    stage: "PROOF_GENERATION",
    outcome: "RETRY",
    artifactProduced: true,
    failureFingerprint: "same-lean-diagnostic",
  },
] as RunState["executions"]
assert(
  repeatedNoProgressExecutions !== undefined &&
    noProgressRetryCount(repeatedNoProgressExecutions, "PROOF_GENERATION") === 2 &&
    noProgressRetryLimitReached(repeatedNoProgressExecutions, "PROOF_GENERATION") &&
    noProgressRetryCount([
      ...repeatedNoProgressExecutions,
      {
        ...repeatedNoProgressExecutions[1]!,
        failureFingerprint: "new-lean-diagnostic",
      },
    ], "PROOF_GENERATION") === 1,
  "identical diagnostics stop after one bounded repair while a changed diagnostic resets the no-progress count",
)
const blankSeparatedDeclaration = parseLeanDeclarations([
  "-- spec2lean: SF-1",
  "",
  "def traced := true",
].join("\n"))[0]
assert(
  blankSeparatedDeclaration?.comment.includes("spec2lean: SF-1") &&
    unresolvedReferenceTokens("PTX 9.3 text", new Set()).length === 0 &&
    unresolvedReferenceTokens("traceability: SF-UNKNOWN-1", new Set()).includes("SF-UNKNOWN-1"),
  "Lean provenance tolerates one formatting blank and flags only explicit provenance tokens",
)
const attributedDeclarations = parseLeanDeclarations([
  "-- spec2lean: SF-1",
  "@[inline] def attributedDef := true",
  "-- spec2lean: SF-1",
  "@[simp] theorem attributedTheorem : True := by trivial",
  "-- spec2lean: SF-1",
  "@[reducible]",
  "private def privateAttributed := true",
  "-- spec2lean: SF-1",
  "structure TracedStructure where value : Nat",
  "-- spec2lean: SF-1",
  "inductive TracedInductive where | value",
  "-- spec2lean: SF-1",
  "instance : Inhabited TracedStructure := ⟨{ value := 0 }⟩",
].join("\n"))
assert(
  attributedDeclarations.map((item) => item.kind).join(",") ===
    "def,theorem,def,structure,inductive,instance" &&
    attributedDeclarations.every((item) => item.comment.includes("spec2lean: SF-1")),
  "traceability discovers attributed, private, structure, inductive, and anonymous instance declarations",
)

const traceabilityManifest = await buildTraceabilityManifest({
  runId: "ptx-9.3-or.b32-b870f055",
  leanPath: "candidates/ptx/9.3/units/or-b32/lean/OrB32-v7.lean",
  semanticPath: "candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json",
  architecturePath: "candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md",
  sourceBundlePaths: ["candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v2.json"],
})
const traceabilityIssues = await verifyTraceabilityManifest(traceabilityManifest)
assert(
  traceabilityIssues.some((issue) => issue.includes("b32DomainSize")) &&
    traceabilityIssues.some((issue) => issue.includes("PredId")),
  "traceability validation exposes legacy unlinked declarations instead of silently passing",
)
const orValueEntry = traceabilityManifest.entries.find((entry) => entry.declarationName === "orValue")
assert(
  orValueEntry !== undefined &&
    orValueEntry.semanticIds.includes("PTX-OR-SEM1-005") &&
    orValueEntry.evidence.some((evidence) => evidence.evidenceId === "PTX-9.3-OR-005"),
  "traceability generator resolves Lean claim comments to exact source fragments",
)
const proofTraceabilityManifest = await buildTraceabilityManifest({
  runId: "ptx-9.3-or.b32-b870f055",
  documentRole: "PROOFS",
  leanPath: "candidates/ptx/9.3/units/or-b32/lean/OrB32Proofs-v1.lean",
  semanticPath: "candidates/ptx/9.3/units/or-b32/semantics/semantics-v1.json",
  architecturePath: "candidates/ptx/9.3/units/or-b32/architecture/foundation-v4.md",
  sourceBundlePaths: ["candidates/ptx/9.3/units/or-b32/source-bundles/source-bundle-v2.json"],
  theoremPath: "candidates/ptx/9.3/units/or-b32/theorems/obligations-v5.json",
})
const proofTraceabilityIssues = await verifyTraceabilityManifest(proofTraceabilityManifest)
assert(
  proofTraceabilityIssues.length === 0,
  `proof traceability manifest verifies: ${proofTraceabilityIssues.join(", ")}`,
)
const deterministicTheorem = proofTraceabilityManifest.entries.find(
  (entry) => entry.declarationName === "OrB32_OrB32Step_deterministic",
)
assert(
  deterministicTheorem !== undefined &&
    deterministicTheorem.theoremObligationIds.length === 1 &&
    deterministicTheorem.semanticIds.length > 0 &&
    deterministicTheorem.evidence.length > 0,
  "proof traceability resolves theorem obligations through semantic claims to evidence",
)
const bitBucketTheorem = proofTraceabilityManifest.entries.find(
  (entry) => entry.declarationName === "OrB32_OrB32Step_bitBucket_noop",
)
assert(
  bitBucketTheorem !== undefined &&
    ["D-2", "D-6", "AMB-OR-2"].every((id) => bitBucketTheorem.semanticIds.includes(id)) &&
    bitBucketTheorem.unresolvedReferences.length === 0 &&
    bitBucketTheorem.evidence.some((item) => item.sourceKind === "ARTIFACT"),
  "traceability resolves reviewed architecture-design dependencies instead of treating them as NVIDIA facts",
)
assert(
  proofTraceabilityManifest.leanDocument.path ===
    "candidates/ptx/9.3/units/or-b32/lean/OrB32Proofs-v1.lean",
  "proof traceability selects the completed artifact contract, not a higher stale candidate version",
)
const completedOrRun = JSON.parse(await readFile(
  resolve(REPO_ROOT, "runs/ptx-9.3-or.b32-b870f055/run.json"),
  "utf8",
)) as RunState
assert(
  verifiedProofArtifactPath(completedOrRun) ===
    "candidates/ptx/9.3/units/or-b32/lean/OrB32Proofs-v1.lean",
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
    pdfAlignment: { eligible: 1, matched: 1, ambiguous: [], unmatched: [], coverageRatio: 1 },
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
