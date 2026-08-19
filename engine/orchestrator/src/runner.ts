import { createHash } from "node:crypto"
import { access, readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

import {
  parseAgentResult,
  type AgentResult,
} from "./agent-result.js"
import {
  normalizeAgentDecision,
  validateAgentDecision,
} from "./agent-decision.js"
import { artifactContractForRun } from "./artifact-contract.js"
import { verifyExpectedArtifact } from "./artifact-verify.js"
import { recoverResultFromVerifiedArtifact } from "./artifact-recovery.js"
import { normalizeCriticResultFromReview } from "./critic-disposition.js"
import { architectureQuestionTriageRequiresRevision } from "./architecture-review.js"
import {
  abortSession,
  ProviderRetryBudgetExceededError,
  sendPromptAsync,
  waitForAgentResult,
} from "./async-session.js"
import { installProofPackage, prepareLeanPackage, type LeanPackageInfo } from "./lean-package.js"
import { leanDeclarationNamespace, leanPackagePath } from "./lean-language.js"
import { prohibitedLeanTokens, verifyLeanFile } from "./lean-local.js"
import { startOpenCode, unwrap } from "./opencode.js"
import {
  latestObligationPath,
  proofArtifactPath,
  proofStatementContractIssues,
  proofTargets,
  proofTargetSummary,
  type ProofTarget,
} from "./proof-plan.js"
import { reconcileProofStageResult } from "./proof-stage-result.js"
import { loadAgentModel, REPO_ROOT } from "./repo.js"
import { loadRun, saveRun } from "./run-store.js"
import {
  markSemanticV2Fallback,
  materializeSemanticDeltaForRun,
  prepareSemanticV2Run,
  verifySemanticV2CriticPreflight,
} from "./semantic-v2.js"
import { planForRun } from "./stage-plan.js"
import { buildStageInputContext } from "./stage-context.js"
import {
  buildTraceabilityManifest,
  semanticEvidenceRenditionIssues,
  verifyTraceabilityManifest,
  writeTraceabilityManifest,
} from "./traceability.js"
import {
  retryRun,
  transitionRun,
  type AgentFailureClass,
  type FormalizationStage,
  type RunState,
} from "./workflow.js"

type Agent = { name: string }
type Session = { id: string }

async function buildPipelineTraceabilityManifest(
  run: RunState,
  documentRole: "SEMANTICS" | "PROOFS",
) {
  return await buildTraceabilityManifest({
    runId: run.runId,
    documentRole,
    includePdfRenditions: true,
  })
}

type TraceabilityExecutionMetrics = NonNullable<
  NonNullable<RunState["executions"]>[number]["traceability"]
>

function resetGatesAfterSourceRepair(run: RunState): RunState {
  return {
    ...run,
    gates: {
      ...run.gates,
      B: "pending",
      C: "pending",
      THEOREM_STRENGTH: "pending",
      FINAL: "pending",
    },
  }
}

function isOfficialRenditionIssue(issue: string): boolean {
  return issue.startsWith("semantic SOURCE_FACT lacks required official HTML evidence:") ||
    issue.startsWith("semantic SOURCE_FACT lacks required official PDF evidence:") ||
    issue.startsWith("semantic SOURCE_FACT has no official HTML/PDF evidence:") ||
    issue.startsWith("official PDF alignment failed:")
}

async function generateVerifiedTraceability(
  run: RunState,
  documentRole: "SEMANTICS" | "PROOFS",
): Promise<TraceabilityExecutionMetrics> {
  const startedAt = Date.now()
  const manifest = await buildPipelineTraceabilityManifest(run, documentRole)
  const issues = await verifyTraceabilityManifest(manifest)
  if (issues.length > 0) throw new Error(issues.join(" | "))
  const manifestPath = await writeTraceabilityManifest(manifest)
  return {
    documentRole,
    manifestPath,
    generationMs: Date.now() - startedAt,
    entries: manifest.entries.length,
    unresolvedReferences: manifest.diagnostics.unresolvedReferences.length,
  }
}

const FAST_FIRST_AGENTS:
  Partial<Record<FormalizationStage, string>> = {
    SOURCE_CURATION: "source-curator-fast",
  }

export function executionAgentForRun(
  run: RunState,
  fallbackAgent: string,
): string {
  if (
    run.stage === "SEMANTIC_EXTRACTION" &&
    run.semanticV2?.mode === "DELTA_FAST_PATH"
  ) {
    return "semantic-extractor-delta"
  }

  const fastAgent = run.language.toLowerCase() === "ptx"
    ? FAST_FIRST_AGENTS[run.stage]
    : undefined

  if (!fastAgent) return fallbackAgent

  // Fast-first is scoped to the CURRENT ENTRY into a stage, not the entire
  // lifetime of the run. A legitimate semantic revision may route
  // SEMANTIC_EXTRACTION -> SOURCE_CURATION -> SEMANTIC_EXTRACTION again.
  // That new entry deserves a fresh fast-path attempt.
  const latestEntry = [...run.history]
    .reverse()
    .find(
      (event) =>
        event.to === run.stage &&
        event.from !== run.stage,
    )

  const enteredAt =
    latestEntry?.at ?? run.createdAt

  const fastAlreadyAttemptedThisEntry =
    (run.executions ?? []).some(
      (execution) =>
        execution.stage === run.stage &&
        execution.agent === fastAgent &&
        Date.parse(execution.at) >= Date.parse(enteredAt),
    )

  return fastAlreadyAttemptedThisEntry
    ? fallbackAgent
    : fastAgent
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

async function fileExists(repoRelativePath: string): Promise<boolean> {
  try {
    await access(resolve(REPO_ROOT, repoRelativePath))
    return true
  } catch {
    return false
  }
}

type ArtifactFingerprint = {
  exists: boolean
  sha256?: string
}

async function artifactFingerprint(
  repoRelativePath: string,
): Promise<ArtifactFingerprint> {
  try {
    const content = await readFile(resolve(REPO_ROOT, repoRelativePath))
    return {
      exists: true,
      sha256: createHash("sha256").update(content).digest("hex"),
    }
  } catch {
    return { exists: false }
  }
}

function artifactChanged(
  before: ArtifactFingerprint | undefined,
  after: ArtifactFingerprint,
): boolean {
  if (before === undefined) return after.exists
  return after.exists && (!before.exists || before.sha256 !== after.sha256)
}

function repairContractLines(run: RunState): string[] {
  const repairContract: Partial<Record<FormalizationStage, {
    pattern: string
    from: readonly FormalizationStage[]
  }>> = {
    ARCHITECTURE: {
      pattern: `${run.artifactRoot}/reviews/architecture-critic-v*.md`,
      from: ["ARCHITECTURE_CRITIQUE", "WAITING_GATE_A", "BLOCKED"],
    },
    SOURCE_CURATION: {
      pattern: `${run.artifactRoot}/reviews/semantics-critic-v*.md`,
      from: [
        "SEMANTIC_EXTRACTION",
        "SEMANTIC_CRITIQUE",
        "WAITING_GATE_B",
        "LEAN_FORMALIZATION",
        "PROOF_GENERATION",
        "BLOCKED",
      ],
    },
    SEMANTIC_EXTRACTION: {
      pattern: `${run.artifactRoot}/reviews/semantics-critic-v*.md`,
      from: ["SEMANTIC_CRITIQUE", "WAITING_GATE_B", "BLOCKED"],
    },
    LEAN_FORMALIZATION: {
      pattern: `${run.artifactRoot}/reviews/lean-mapping-critic-v*.md`,
      from: ["LEAN_MAPPING_CRITIQUE", "WAITING_GATE_C", "FINAL_CRITIQUE", "BLOCKED"],
    },
    THEOREM_GENERATION: {
      pattern: `${run.artifactRoot}/reviews/theorem-strength-critic-v*.md`,
      from: [
        "THEOREM_STRENGTH_CRITIQUE",
        "WAITING_THEOREM_STRENGTH_APPROVAL",
        "FINAL_CRITIQUE",
        "BLOCKED",
      ],
    },
    PROOF_GENERATION: {
      pattern: `${run.artifactRoot}/reviews/final-critic-v*.md`,
      from: ["FINAL_CRITIQUE", "BLOCKED"],
    },
    FINAL_CRITIQUE: {
      pattern: `${run.artifactRoot}/reviews/final-critic-v*.md`,
      from: ["FINAL_CRITIQUE", "WAITING_FINAL_APPROVAL", "BLOCKED"],
    },
  }
  const contract = repairContract[run.stage]
  const latestEntry = run.history.at(-1)

  if (
    contract === undefined ||
    latestEntry?.to !== run.stage ||
    latestEntry.from === null ||
    !contract.from.includes(latestEntry.from)
  ) {
    return []
  }

  return [
    "",
    "# Exact Repair Contract",
    "",
    `This stage was re-entered from ${latestEntry.from}.`,
    `Read the highest-version existing review matching ${contract.pattern} before editing.`,
    `Routing summary: ${latestEntry.reason}`,
    "Resolve every BLOCKER/MAJOR finding in that review, preserve unaffected content, and make no unrelated scope expansion.",
    "A human rejection reason, when present, is also binding and must not be paraphrased into a broader task.",
  ]
}

export function buildGeneralPrompt(
  run: RunState,
  supplementalStageContext = "",
): string {
  const plan = planForRun(run)
  const artifact = artifactContractForRun(run)
  const revisionTargets =
    plan.revisionStages.length === 0 ? "(none)" : plan.revisionStages.join(", ")
  const latestEvent = run.history.at(-1)
  const latestSubstantiveRetry = [...(run.executions ?? [])]
    .reverse()
    .find((execution) =>
      execution.stage === run.stage &&
      execution.outcome === "RETRY" &&
      execution.failureClass !== "PROVIDER_RETRY_BUDGET_EXCEEDED"
    )
  const currentRetryReason = latestSubstantiveRetry?.response.slice(-4_000) ??
    (latestEvent?.from === run.stage && latestEvent.to === run.stage &&
      !latestEvent.reason.includes("provider retry exceeded")
      ? latestEvent.reason
      : undefined)

  return [
    "# Spec2Lean Automated Agentic Run",
    "",
    `Run ID: ${run.runId}`,
    `Mode: ${run.mode}`,
    `Language: ${run.language}`,
    `Specification version: ${run.specVersion}`,
    `Unit: ${run.unit}`,
    `Unit slug: ${run.unitSlug}`,
    `Lean module base name: ${run.leanModuleName}`,
    `Required Lean namespace: ${leanDeclarationNamespace(run)}`,
    `Source manifest: ${run.sourceManifest}`,
    `Artifact root: ${run.artifactRoot}`,
    `Current stage: ${run.stage}`,
    `Stage attempt: ${artifact.attempt}`,
    `Run revision: ${run.revision}`,
    "",
    "# Required Stage Artifact",
    "",
    `Create exactly: ${artifact.outputPath}`,
    "",
    "Use a new immutable revision artifact; do not overwrite an older revision.",
    "Read earlier artifacts under the artifact root only when they are inputs to this stage.",
    "If the required output path already exists because a previous execution was interrupted after writing it, do not overwrite it.",
    "Instead read and verify it; if it already completes the stage, return SUCCESS.",
    "If it is incomplete only because execution was interrupted, return RETRY.",
    "",
    "# Stage Task",
    "",
    plan.task,
    ...(plan.agent.endsWith("-critic")
      ? [
          "",
          "# Machine-checkable finding accountability",
          "",
          "Every nonzero BLOCKER/MAJOR/MINOR/NOTE count must have exactly one explicit finding entry per counted item.",
          "Each entry must contain its own line `Severity: BLOCKER|MAJOR|MINOR|NOTE` followed by a concrete description and affected artifact/claim/declaration.",
          "The number of Severity lines for each class must exactly equal the final numeric disposition count.",
          "Do not report a nonzero count whose finding is left implicit in surrounding prose.",
          "If BLOCKER or MAJOR is nonzero, return REVISE to one of the exact allowed producer revision stages; do not RETRY the critic.",
          "If BLOCKER and MAJOR are zero and PRE_GATE_REVISION_REQUIRED is false, return SUCCESS to the exact success stage.",
          "RETRY is reserved for a technical inability to write or validate the review artifact, never for repairing an upstream semantic/Lean/theorem artifact.",
          "The review artifact, numeric disposition, PRE_GATE marker, and SPEC2LEAN_RESULT must agree exactly.",
        ]
      : []),
    ...(currentRetryReason === undefined
      ? []
      : [
          "",
          "# Binding Same-Stage Retry Diagnostic",
          "",
          currentRetryReason,
          "Repair this exact failure in the new immutable artifact. Do not repeat an already-failed output unchanged.",
        ]),
    ...repairContractLines(run),
    ...(run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode === "DELTA_FAST_PATH"
      ? [
          "",
          "# Semantic Architecture v2 — DELTA FAST PATH",
          "",
          `Shared environment: ${run.semanticV2.sharedEnvironmentPath}`,
          `Shared environment hash: ${run.semanticV2.environment?.sha256 ?? "missing"}`,
          `Delta output: ${run.semanticV2.current?.deltaPath ?? artifact.outputPath}`,
          `Deterministic materialized view: ${run.semanticV2.current?.materializedPath ?? "assigned after validation"}`,
          `Deterministic critic packet: ${run.semanticV2.current?.criticPacketPath ?? "assigned after validation"}`,
          "Generate ONLY the typed instruction-specific semantic delta.",
          "Do not reproduce shared claims as local claims.",
          "Read ir/semantic/instruction-delta.schema.json and the shared environment before writing.",
          "Every new SOURCE_FACT must use local official evidence with sourceBundleEvidenceId set to an exact fragment_id from the latest bounded source bundle.",
          "Pin the exact latest source-bundle path/hash and shared environment ID/revision/hash.",
          "The orchestrator will validate grounding, block state-affecting open questions, materialize the full view, and construct the critic packet.",
          "If a needed shared semantic ID is unavailable or the instruction exceeds the environment, return RETRY at SEMANTIC_EXTRACTION and state that full fallback is required. Do not invent the missing shared fact.",
        ]
      : []),
    ...(run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode === "LEGACY_FALLBACK"
      ? [
          "",
          "# Explicit Semantic v2 Fallback",
          "",
          `Fallback reason: ${run.semanticV2.fallbackReason ?? "delta path unavailable"}`,
          "Produce the existing complete legacy semantic interpretation at the required semantics-vN.json path.",
          "Do not report or imply that the delta fast path succeeded.",
        ]
      : []),
    ...(run.stage === "SEMANTIC_CRITIQUE" && run.semanticV2?.mode === "DELTA_FAST_PATH" && run.semanticV2.current !== undefined
      ? [
          "",
          "# Semantic Architecture v2 — COMPACT CRITIC PATH",
          "",
          `Compact critic packet: ${run.semanticV2.current.criticPacketPath}`,
          `Instruction delta: ${run.semanticV2.current.deltaPath}`,
          `Deterministic full view fallback: ${run.semanticV2.current.materializedPath}`,
          `Hash-bound shared environment: ${run.semanticV2.sharedEnvironmentPath}`,
          "Read the compact packet first. Deeply review all new SOURCE_FACT, DERIVED_INTERPRETATION, DESIGN_DEPENDENCY, ASSUMPTION, OPEN_QUESTION, refinement, and risky shared-dependency entries.",
          "Independently compare new source facts with the bounded source bundle and official evidence as needed.",
          "The deterministic validator establishes structure only; it does not establish interpretive correctness.",
          "If the packet is insufficient or a broader full review is required, return REVISE to SEMANTIC_EXTRACTION or SOURCE_CURATION and begin the summary with FULL_REVIEW_REQUIRED:.",
          "The full materialized view remains available; never convert insufficient review scope into SUCCESS.",
        ]
      : []),
    ...(run.semanticV2?.mode === "DELTA_FAST_PATH" &&
      run.semanticV2.current !== undefined &&
      !["SEMANTIC_EXTRACTION", "SEMANTIC_CRITIQUE"].includes(run.stage)
      ? [
          "",
          "# Gate-B Semantic v2 Input",
          "",
          `The complete semantic artifact is the deterministic materialized view at ${run.semanticV2.current.materializedPath}.`,
          `Its instruction-specific provenance delta is ${run.semanticV2.current.deltaPath}.`,
          "Treat the Gate-B-authorized materialized view as the semantic authority for this run while preserving claim classifications and origin IDs in traceability.",
          "The deterministic stage-input contract states whether that authorization is human approval or benchmark-only auto-advance.",
          "Do not expect the legacy hand-authored semantics JSON layout and do not regenerate semantic content.",
        ]
      : []),
    ...(run.stage === "FINAL_CRITIQUE"
      ? [
          "",
          "# Installed Lean package artifacts",
          "",
          `Semantics: ${leanPackagePath(run)}`,
          `Proofs: ${leanPackagePath(run, true)}`,
          "The final critique must independently verify both and the root Lean package.",
          "",
          "IMPORTANT FINAL-ARTIFACT RULE:",
          `You MUST create ${artifact.outputPath} using candidate_write before returning SUCCESS.`,
          `After writing it, use candidate_read to verify ${artifact.outputPath}.`,
          "A textual SUCCESS response without that artifact is invalid.",
          "Do not spend the session re-performing already-completed source research.",
        ]
      : []),
    ...(supplementalStageContext.length === 0
      ? []
      : ["", supplementalStageContext]),
    "",
    "# Safety Rules",
    "",
    "- Follow AGENTS.md and your role definition.",
    "- The current run metadata in this prompt is authoritative; ignore any obsolete case-study/unit notes elsewhere.",
    "- Do not approve a human gate.",
    "- Do not promote anything to accepted/.",
    "- Do not skip stages.",
    "- Do not invent source evidence.",
    "- Do not silently weaken semantics or theorem statements.",
    "- Do not use sorry, admit, new axioms, or unsafe.",
    "",
    "# Orchestrator Result Protocol",
    "",
    "Your LAST non-empty line must be exactly:",
    'SPEC2LEAN_RESULT {"outcome":"SUCCESS|REVISE|RETRY|BLOCKED","nextStage":"STAGE","summary":"short summary"}',
    "",
    `For SUCCESS, nextStage MUST be: ${plan.successStage}`,
    `Copy that exact SUCCESS stage literal; do not substitute a remembered or plausible alias.`,
    `Allowed REVISE nextStage values: ${revisionTargets}`,
    `For RETRY, nextStage MUST remain: ${run.stage}`,
    "Use RETRY for step/time/tool/context/resource exhaustion or interrupted work.",
    "For BLOCKED, nextStage MUST be: BLOCKED.",
    "Do not put the result line in a Markdown fence.",
  ].join("\n")
}

export async function buildTheoremStrengthContractContext(
  run: RunState,
): Promise<string> {
  if (run.stage !== "THEOREM_STRENGTH_CRITIQUE") return ""

  const obligationPath = await latestObligationPath(run)
  const targets = await proofTargets(run)
  return [
    "# Deterministically Validated Theorem Contract Input",
    "",
    `Validated obligation artifact: \`${obligationPath}\``,
    `Complete declaration count supplied: ${targets.length}`,
    "The declarations below were structurally validated by the orchestrator.",
    "They intentionally live in theorem_obligations[].lean_statement_sketch in the JSON contract.",
    "No theorem/lemma declarations are expected in the Lean mapping before PROOF_GENERATION.",
    "Review these exact statements for truth, strength, non-vacuity, and coverage.",
    "Do not revise merely because the mapping .lean file contains definitions only.",
    "",
    "Your review artifact MUST contain this audit block with the exact path/count and every name:",
    `Validated obligation artifact: \`${obligationPath}\``,
    `Complete declaration count reviewed: ${targets.length}`,
    "Declaration names reviewed:",
    ...targets.map((target) => `- ${target.name}`),
    "",
    "# Exact declarations to review",
    "",
    ...targets.flatMap((target) => [
      `## ${target.obligationId}: ${target.name}`,
      `Correctness kind: ${target.correctnessKind ?? "LEGACY_UNCLASSIFIED"}`,
      `Semantic claims: ${target.semanticIds.join(", ") || "NONE"}`,
      target.statement,
      ...(target.strengthRisks.length === 0
        ? []
        : ["Strength caveats:", ...target.strengthRisks.map((risk) => `- ${risk}`)]),
      "",
    ]),
  ].join("\n")
}

type ProofPromptContext = {
  packageInfo: LeanPackageInfo
  target?: ProofTarget
  proofPath: string
  diagnostics?: string
  existingCompiles: boolean
  remaining: number
  total: number
}

const MAX_PROOF_TARGETS_PER_AGENT_TURN = 8
const MAX_PROOF_TARGET_STATEMENT_CHARACTERS = 20_000

async function buildProofPrompt(
  run: RunState,
  preflightDiagnostics?: string,
): Promise<ProofPromptContext & { prompt: string }> {
  const packageInfo = await prepareLeanPackage(run)
  const proofPath = proofArtifactPath(run)
  const summary = await proofTargetSummary(run)
  const exists = await fileExists(proofPath)
  let diagnostics: string | undefined
  let existingCompiles = false
  let contractRepairTargets: ProofTarget[] = []

  if (exists) {
    const banned = await prohibitedLeanTokens(proofPath)
    if (banned.length > 0) {
      diagnostics = `Prohibited tokens in Lean code: ${banned.join(", ")}`
    } else {
      const statementIssues = await proofStatementContractIssues(run)
      if (statementIssues.length > 0) {
        contractRepairTargets = await proofTargets(run)
        diagnostics = [
          "The proof file does not preserve the exact theorem contract authorized at the theorem-strength boundary:",
          ...statementIssues.map((issue) => `- ${issue}`),
        ].join("\n")
      } else {
        const check = await verifyLeanFile(proofPath, 90_000)
        existingCompiles = check.success
        if (!check.success) diagnostics = check.output.slice(-12_000)
      }
    }
  }

  if (preflightDiagnostics !== undefined) {
    diagnostics = preflightDiagnostics
    existingCompiles = false
  }

  const repairMode = exists && !existingCompiles
  const batchTargets: ProofTarget[] = []
  if (!repairMode) {
    let statementCharacters = 0
    for (const item of summary.missing) {
      if (batchTargets.length >= MAX_PROOF_TARGETS_PER_AGENT_TURN) break
      if (
        batchTargets.length > 0 &&
        statementCharacters + item.statement.length > MAX_PROOF_TARGET_STATEMENT_CHARACTERS
      ) break
      batchTargets.push(item)
      statementCharacters += item.statement.length
    }
  }

  const target: ProofTarget | undefined =
    batchTargets.length === 0
      ? undefined
      : {
          obligationId: batchTargets.map((item) => item.obligationId).join(", "),
          name: `${batchTargets.length} remaining authorized theorem declarations`,
          statement: batchTargets
            .map((item, index) => [
              `-- TARGET ${index + 1}: ${item.obligationId} / ${item.name}`,
              item.statement,
              ...(item.strengthRisks.length > 0
                ? [
                    "-- Strength caveats:",
                    ...item.strengthRisks.map((risk) => `-- - ${risk}`),
                  ]
                : []),
            ].join("\n"))
            .join("\n\n"),
          strengthRisks: [...new Set(batchTargets.flatMap((item) => item.strengthRisks))],
          semanticIds: [...new Set(batchTargets.flatMap((item) => item.semanticIds))],
        }

  const mode = repairMode ? "REPAIR" : "PROVE_BATCH"

  const prompt = [
    "# Spec2Lean Proof Subtask",
    "",
    `Run ID: ${run.runId}`,
    `Unit: ${run.unit}`,
    `Proof artifact: ${proofPath}`,
    `Installed semantics module: ${packageInfo.moduleImport}`,
    `Installed declaration namespace: ${packageInfo.declarationNamespace}`,
    `Proof progress: ${summary.declared}/${summary.total} theorem declarations present`,
    `Mode: ${mode}`,
    "",
    "# Hard constraints",
    "",
    "- Do not re-read official source files, architecture, or semantic claim bundles during this subtask.",
    "- The theorem-strength-authorized statements below are authoritative for this run.",
    "- The orchestrator already extracted the frozen statements; do not re-read the obligation JSON or theorem-strength review.",
    "- Do not weaken it, add semantic preconditions, or change semantics.",
    "- Do not use sorry, admit, new axiom, or unsafe.",
    "- Write/edit the proof artifact EARLY, then use Lean diagnostics; do not mentally plan the whole proof set.",
    "- Prove exactly the bounded current batch below; later missing declarations are separate resumable batches.",
    "- Do not stop after the first successful theorem.",
    "- If the proof file already exists, preserve all previously compiling theorem declarations.",
    "- Every helper declaration must have an immediately preceding `-- spec2lean: ID` comment citing the supplied allowlist; theorem declarations are bound deterministically by obligation ID/name.",
    "- Use candidate_write create only if the proof file does not exist; otherwise use candidate_write replace with its exact current SHA-256.",
    "- Import only the installed semantics module and required standard/project modules.",
    "",
    ...(diagnostics
      ? [
          "# Current concrete Lean diagnostics",
          "",
          diagnostics,
          "",
          "Repair only these concrete elaboration/proof failures. Do not add new theorem declarations until the file compiles.",
          ...(contractRepairTargets.length === 0
            ? []
            : [
                "",
                "# Exact frozen theorem declarations",
                "",
                "Replace mismatching theorem headers with these exact authorized declarations; do not reconstruct them from memory:",
                "",
                ...contractRepairTargets.flatMap((item) => [
                  `## ${item.obligationId}: ${item.name}`,
                  item.statement,
                  "",
                ]),
              ]),
          "After EVERY candidate_write, immediately run lean_check_file. Never finish after an unchecked write; reserve tool steps for the final compile check.",
        ]
      : target
        ? [
            "# Current theorem target",
            "",
            `Obligation: ${target.obligationId}`,
            `Theorem: ${target.name}`,
            "",
            target.statement,
            "",
            ...(target.strengthRisks.length > 0
              ? ["Strength caveats:", ...target.strengthRisks.map((risk) => `- ${risk}`), ""]
              : []),
            ...(target.semanticIds.length > 0
              ? ["Authorized semantic IDs available for helper traceability:", ...target.semanticIds.map((id) => `- ${id}`), ""]
              : []),
            "Create or extend the proof file with every theorem declaration in this bounded batch.",
            "Then immediately run lean_check_file.",
            "Repair concrete diagnostics in the SAME session until the complete batch compiles or a genuine theorem/semantic conflict is found.",
          ]
        : [
            "All authorized theorem declarations are already present. Only verify the proof file with Lean and report SUCCESS if it compiles cleanly.",
          ]),
    "# Result protocol",
    "",
    "After the final candidate_write and Lean check, call candidate_validate for this run and proof path; repair provenance issues in this same session.",
    `If the proof artifact compiles after this subtask, use RETRY/${run.stage} unless every authorized theorem is present; the orchestrator will decide final completion itself.`,
    'Your LAST non-empty line must be: SPEC2LEAN_RESULT {"outcome":"RETRY","nextStage":"PROOF_GENERATION","summary":"short factual summary"}',
    "If a genuine theorem/semantic conflict is discovered, use BLOCKED/BLOCKED instead.",
  ].join("\n")

  return {
    packageInfo,
    target,
    proofPath,
    diagnostics,
    existingCompiles,
    remaining: summary.remaining,
    total: summary.total,
    prompt,
  }
}

async function finalizeProofStageLocally(run: RunState): Promise<AgentResult | undefined> {
  const proofPath = proofArtifactPath(run)
  if (!(await fileExists(proofPath))) return undefined

  const banned = await prohibitedLeanTokens(proofPath)
  if (banned.length > 0) {
    return {
      outcome: "RETRY",
      nextStage: "PROOF_GENERATION",
      summary: `Proof artifact contains prohibited Lean code tokens: ${banned.join(", ")}`,
    }
  }

  const statementIssues = await proofStatementContractIssues(run)
  if (statementIssues.length > 0) {
    return {
      outcome: "RETRY",
      nextStage: "PROOF_GENERATION",
      summary: `Proof artifact changed or omitted the approved theorem contract: ${statementIssues.join(" | ")}`,
    }
  }

  const check = await verifyLeanFile(proofPath, 90_000)
  const summary = await proofTargetSummary(run)

  if (!check.success) {
    return {
      outcome: "RETRY",
      nextStage: "PROOF_GENERATION",
      summary: `Proof artifact exists but Lean still reports errors; ${summary.remaining} theorem declarations remain or need repair.`,
    }
  }

  if (summary.remaining === 0) {
    return {
      outcome: "SUCCESS",
      nextStage: "FINAL_CRITIQUE",
      summary: `All ${summary.total} approved theorem declarations are present and the proof artifact compiles cleanly with no prohibited verification bypass.`,
    }
  }

  return {
    outcome: "RETRY",
    nextStage: "PROOF_GENERATION",
    summary: `Proof artifact compiles; ${summary.declared}/${summary.total} approved theorem declarations are present. Continue with exactly the next missing theorem.`,
  }
}

export type TickOptions = {
  dryRun?: boolean
  runtime?: Awaited<ReturnType<typeof startOpenCode>>
  providerRetryBudgetMs?: number
}

export async function executeTick(
  runId: string,
  options: TickOptions = {},
): Promise<void> {
  const dryRun = options.dryRun ?? false
  let run = await loadRun(runId)

  if (
    run.semanticV2?.mode !== "DELTA_FAST_PATH" &&
    ["SEMANTIC_EXTRACTION", "LEAN_FORMALIZATION", "PROOF_GENERATION"].includes(run.stage)
  ) {
    let evidenceIssues: string[] = []
    try {
      evidenceIssues = await semanticEvidenceRenditionIssues({ runId: run.runId })
    } catch {
      // A fresh semantic stage has no semantic artifact yet. Normal stage
      // validation remains authoritative once the producer writes one.
    }
    if (evidenceIssues.length > 0) {
      const fromStage = run.stage
      const detail = evidenceIssues.join(" | ")
      if (dryRun) {
        console.log(JSON.stringify({
          dryRun: true,
          runId: run.runId,
          stage: fromStage,
          localRepairTo: "SOURCE_CURATION",
          issues: evidenceIssues,
        }, null, 2))
        return
      }
      let next = transitionRun(
        run,
        "SOURCE_CURATION",
        `deterministic evidence preflight routed the repair to source curation: ${detail}`,
      )
      next = resetGatesAfterSourceRepair(next)
      next = {
        ...next,
        activeExecution: undefined,
        executions: [
          ...(run.executions ?? []),
          {
            at: new Date().toISOString(),
            stage: fromStage,
            agent: "orchestrator-evidence-preflight",
            sessionId: "local",
            outcome: "REVISE",
            nextStage: "SOURCE_CURATION",
            response: detail,
          },
        ],
      }
      await saveRun(next)
      console.log(JSON.stringify({
        ok: true,
        runId: next.runId,
        agent: "orchestrator-evidence-preflight",
        outcome: "REVISE",
        fromStage,
        toStage: "SOURCE_CURATION",
        revision: next.revision,
        summary: detail,
      }, null, 2))
      return
    }
  }

  if (run.stage === "SEMANTIC_EXTRACTION") {
    const prepared = await prepareSemanticV2Run(run)
    if (prepared !== run) {
      run = prepared
      if (!dryRun) await saveRun(run)
    }
  }
  if (
    run.stage === "SEMANTIC_CRITIQUE" &&
    run.semanticV2?.mode === "DELTA_FAST_PATH"
  ) {
    const preflight = await verifySemanticV2CriticPreflight(run)
    if (!preflight.ok) {
      const detail = preflight.issues.join(" | ")
      run = markSemanticV2Fallback(
        run,
        "SEMANTIC_V2_CRITIC_PREFLIGHT_FAILED",
        detail,
        "CRITIC_FALLBACK",
      )
      if (dryRun) {
        console.log(JSON.stringify({
          dryRun: true,
          runId: run.runId,
          stage: "SEMANTIC_CRITIQUE",
          localFallbackTo: "SEMANTIC_EXTRACTION",
          issues: preflight.issues,
        }, null, 2))
        return
      }
      let next = transitionRun(
        run,
        "SEMANTIC_EXTRACTION",
        `orchestrator semantic-v2 preflight fallback: ${detail}`,
      )
      next = {
        ...next,
        activeExecution: undefined,
        executions: [
          ...(run.executions ?? []),
          {
            at: new Date().toISOString(),
            stage: "SEMANTIC_CRITIQUE",
            agent: "orchestrator-semantic-v2-preflight",
            sessionId: "local",
            outcome: "REVISE",
            nextStage: "SEMANTIC_EXTRACTION",
            response: detail,
          },
        ],
      }
      await saveRun(next)
      console.log(JSON.stringify({
        ok: true,
        runId: next.runId,
        agent: "orchestrator-semantic-v2-preflight",
        outcome: "REVISE",
        fromStage: "SEMANTIC_CRITIQUE",
        toStage: "SEMANTIC_EXTRACTION",
        revision: next.revision,
        summary: detail,
      }, null, 2))
      return
    }
  }

  const basePlan = planForRun(run)
  const plan = {
    ...basePlan,
    agent: executionAgentForRun(run, basePlan.agent),
  }

  const artifact = artifactContractForRun(run)

  let prompt: string
  let proofContext: Awaited<ReturnType<typeof buildProofPrompt>> | undefined

  if (run.stage === "PROOF_GENERATION") {
    // Fast path: a previous/interrupted proof attempt may already have completed.
    await prepareLeanPackage(run)
    const local = await finalizeProofStageLocally(run)
    let proofPreflightDiagnostics: string | undefined
    if (local?.outcome === "SUCCESS") {
      await installProofPackage(run)
      try {
        const traceability = await generateVerifiedTraceability(run, "PROOFS")
        const localSummary = `${local.summary} Deterministic theorem-to-source evidence manifest: ${traceability.manifestPath}.`
        const next = transitionRun(run, "FINAL_CRITIQUE", `local Lean verification: ${localSummary}`)
        const saved = {
          ...next,
          activeExecution: undefined,
          executions: [
            ...(run.executions ?? []),
            {
              at: new Date().toISOString(),
              stage: run.stage,
              agent: "orchestrator-local-lean",
              sessionId: "local",
              outcome: local.outcome,
              nextStage: local.nextStage,
              response: localSummary,
              traceability,
            },
          ],
        }
        await saveRun(saved)
        console.log(JSON.stringify({
          ok: true,
          runId,
          agent: "orchestrator-local-lean",
          outcome: "SUCCESS",
          fromStage: run.stage,
          toStage: saved.stage,
          revision: saved.revision,
          summary: localSummary,
        }, null, 2))
        return
      } catch (error) {
        proofPreflightDiagnostics =
          `The proof file compiles and preserves the approved theorem contract, but ` +
          `deterministic traceability validation failed:\n` +
          `${error instanceof Error ? error.message : String(error)}\n` +
          `Repair only the immediately preceding provenance comments/helper attribution. ` +
          `Do not change any theorem header or proof body unless Lean requires it after the comment-only repair.`
      }
    }

    proofContext = await buildProofPrompt(run, proofPreflightDiagnostics)
    prompt = `${proofContext.prompt}\n\n${await buildStageInputContext(run)}`
  } else {
    const theoremStrengthContext = await buildTheoremStrengthContractContext(run)
    const stageInputContext = await buildStageInputContext(run)
    prompt = buildGeneralPrompt(
      run,
      [stageInputContext, theoremStrengthContext].filter(Boolean).join("\n\n"),
    )
  }

  if (dryRun) {
    console.log(JSON.stringify({
      dryRun: true,
      runId: run.runId,
      stage: run.stage,
      agent: plan.agent,
      successStage: plan.successStage,
      revisionStages: plan.revisionStages,
      expectedArtifact: artifact.outputPath,
      prompt,
    }, null, 2))
    return
  }

  const runtime = options.runtime ?? await startOpenCode()
  const ownsRuntime = options.runtime === undefined
  const executionModel = await loadAgentModel(plan.agent)

  try {
    const agents = unwrap<Agent[]>(await runtime.runtime.client.app.agents())
    if (!agents.some((agent) => agent.name === plan.agent)) {
      throw new Error(`Required agent not found: ${plan.agent}`)
    }

    let sessionId: string
    let submitted = false

    const resumableActiveExecution =
      run.activeExecution !== undefined &&
      run.activeExecution.stage === run.stage &&
      run.activeExecution.agent === plan.agent &&
      run.activeExecution.model === executionModel.full

    if (run.activeExecution !== undefined && !resumableActiveExecution) {
      const stale = run.activeExecution
      await abortSession(runtime.runtime.server.url, stale.sessionId).catch(() => {})
      console.log(
        `[spec2lean] abandoning stale active session=${stale.sessionId} ` +
        `agent=${stale.agent} model=${stale.model ?? "unrecorded"}; ` +
        `current-agent=${plan.agent} current-model=${executionModel.full}`,
      )
      run = {
        ...run,
        activeExecution: undefined,
      }
      await saveRun(run)
    }

    if (resumableActiveExecution && run.activeExecution !== undefined) {
      sessionId = run.activeExecution.sessionId
      console.log(`[spec2lean] resuming active session=${sessionId} agent=${plan.agent}`)
    } else {
      const session = unwrap<Session>(
        await runtime.runtime.client.session.create({
          body: { title: `Spec2Lean ${run.runId} ${run.stage}` },
        }),
      )
      if (!session.id) throw new Error("OpenCode did not return a session ID")
      sessionId = session.id
      submitted = true

      run = {
        ...run,
        activeExecution: {
          startedAt: new Date().toISOString(),
          stage: run.stage,
          agent: plan.agent,
          model: executionModel.full,
          sessionId,
          expectedArtifact: artifact.outputPath,
          artifactBaseline: await artifactFingerprint(artifact.outputPath),
        },
      }
      await saveRun(run)

      console.log(`[spec2lean] session=${sessionId} agent=${plan.agent} submitted async`)
      await sendPromptAsync(runtime.runtime.server.url, sessionId, {
        agent: plan.agent,
        model: {
          providerID: executionModel.providerID,
          modelID: executionModel.modelID,
        },
        parts: [{ type: "text", text: prompt }],
      })
    }

    let response = ""
    let result: AgentResult | undefined
    let failureClass: AgentFailureClass | undefined
    let traceability: TraceabilityExecutionMetrics | undefined
    let proofProgress: NonNullable<RunState["executions"]>[number]["progress"]

    try {
      response = await waitForAgentResult(runtime.runtime.server.url, sessionId, {
        pollMs: 2_000,
        maxWaitMs: run.stage === "PROOF_GENERATION" ? 15 * 60 * 1000 : 30 * 60 * 1000,
        providerRetryBudgetMs: options.providerRetryBudgetMs,
        missingStatusIsTerminal: !submitted,
      })
      try {
        result = parseAgentResult(response)
      } catch (error) {
        result = await recoverResultFromVerifiedArtifact(run) ?? {
          outcome: "RETRY",
          nextStage: run.stage,
          summary:
            `Agent response did not contain a valid terminal protocol result and ` +
            `the required artifact did not establish recoverable completion: ` +
            `${error instanceof Error ? error.message : String(error)}`,
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      const recoverable =
        error instanceof ProviderRetryBudgetExceededError ||
        message.includes("timed out") ||
        message.includes("terminated without textual result") ||
        message.includes("reason=length") ||
        message.includes("status-missing")

      if (!recoverable) throw error

      await abortSession(runtime.runtime.server.url, sessionId).catch(() => {})
      response = `[ORCHESTRATOR_RECOVERY] ${message}`
      const recoveredResult = await recoverResultFromVerifiedArtifact(run)
      if (recoveredResult !== undefined) {
        result = recoveredResult
      } else {
        if (error instanceof ProviderRetryBudgetExceededError) {
          failureClass = "PROVIDER_RETRY_BUDGET_EXCEEDED"
        } else if (message.includes("reason=length")) {
          failureClass = "OUTPUT_LENGTH_EXCEEDED"
        }
        result = {
          outcome: "RETRY",
          nextStage: run.stage,
          summary: error instanceof ProviderRetryBudgetExceededError
            ? `OpenCode provider retry exceeded the bounded ${error.retryBudgetMs}ms budget: ${error.providerMessage}. The stalled session was aborted; the stage remains safely resumable and no semantic conclusion was inferred from the provider failure.`
            : message.includes("reason=length")
              ? "OpenCode terminated the response at its output-length limit before a usable artifact/result was completed. Retry once in strict bounded-output recovery mode: use only the deterministic stage inputs, do not inspect other units, stay within the stated artifact budget, write once, validate, and return the protocol result."
              : `Agent execution ended without a usable stage result (${message}). The same stage is safely resumable; any written artifact will be verified before another agent is started.`,
        }
      }
    }

    if (!result) throw new Error("No agent result available")

    if (plan.agent.endsWith("-critic")) {
      try {
        const review = await readFile(resolve(REPO_ROOT, artifact.outputPath), "utf8")
        result = normalizeCriticResultFromReview(
          result,
          review,
          plan.successStage,
          plan.revisionStages[0],
        )
        if (
          run.stage === "ARCHITECTURE_CRITIQUE" &&
          result.outcome === "SUCCESS" &&
          architectureQuestionTriageRequiresRevision(review)
        ) {
          result = {
            outcome: "REVISE",
            nextStage: "ARCHITECTURE",
            summary:
              "Deterministic Gate-A triage requires architecture repair: one or more " +
              "state-affecting open questions are speculative, out of scope, or must be reclassified. " +
              `Original summary: ${result.summary}`,
          }
        }
      } catch {
        // Missing/unreadable review artifacts remain REVISE. Artifact
        // verification must never be bypassed by disposition normalization.
      }
    }

    // Deterministic artifact verification outranks model self-reporting.
    if (run.stage === "PROOF_GENERATION") {
      const local = await finalizeProofStageLocally(run)
      result = reconcileProofStageResult(result, local)
      const afterSummary = await proofTargetSummary(run)
      const declaredBefore = proofContext === undefined
        ? afterSummary.declared
        : proofContext.total - proofContext.remaining
      if (result.outcome === "RETRY" && afterSummary.declared > declaredBefore) {
        proofProgress = {
          kind: "PROOF_BATCH_CONTINUATION",
          declarationsBefore: declaredBefore,
          declarationsAfter: afterSummary.declared,
          declarationsTotal: afterSummary.total,
        }
      }
      if (result.outcome === "SUCCESS") {
        await installProofPackage(run)
        try {
          traceability = await generateVerifiedTraceability(run, "PROOFS")
          result = {
            ...result,
            summary: `${result.summary} Deterministic theorem-to-source evidence manifest: ${traceability.manifestPath}.`,
          }
        } catch (error) {
          result = {
            outcome: "RETRY",
            nextStage: run.stage,
            summary: `Proof artifact passed verification, but deterministic traceability generation failed: ${error instanceof Error ? error.message : String(error)}`,
          }
        }
      }
    } else if (result.outcome === "SUCCESS" || result.outcome === "REVISE") {
      const verification = await verifyExpectedArtifact(run)
      if (!verification.ok) {
        const renditionIssues = verification.issues.filter(isOfficialRenditionIssue)
        if (run.stage === "SEMANTIC_EXTRACTION" && renditionIssues.length > 0) {
          run = resetGatesAfterSourceRepair(run)
          result = {
            outcome: "REVISE",
            nextStage: "SOURCE_CURATION",
            summary: `Semantic evidence is incomplete; deterministic validation routed the repair to source curation: ${renditionIssues.join(" | ")}`,
          }
        } else {
          result = {
            outcome: "RETRY",
            nextStage: run.stage,
            summary: `Agent reported SUCCESS but artifact verification failed: ${verification.issues.join(" | ")}`,
          }
        }
      } else if (
        result.outcome === "SUCCESS" &&
        run.stage === "SEMANTIC_EXTRACTION" &&
        run.semanticV2?.mode === "DELTA_FAST_PATH"
      ) {
        try {
          run = await materializeSemanticDeltaForRun(run)
        } catch (error) {
          const detail = error instanceof Error ? error.message : String(error)
          run = markSemanticV2Fallback(
            run,
            "DELTA_VALIDATION_OR_MATERIALIZATION_FAILED",
            detail,
          )
          result = {
            outcome: "RETRY",
            nextStage: "SEMANTIC_EXTRACTION",
            summary: `Semantic delta fast path failed deterministically and has switched to explicit legacy fallback: ${detail}`,
          }
        }
      }
      if (result.outcome === "SUCCESS" && run.stage === "LEAN_FORMALIZATION") {
        try {
          traceability = await generateVerifiedTraceability(run, "SEMANTICS")
          result = {
            ...result,
            summary: `${result.summary} Deterministic Lean-to-source evidence manifest: ${traceability.manifestPath}.`,
          }
        } catch (error) {
          result = {
            outcome: "RETRY",
            nextStage: run.stage,
            summary: `Lean artifact passed verification, but deterministic traceability generation failed: ${error instanceof Error ? error.message : String(error)}`,
          }
        }
      }
    }

    if (
      run.stage === "SEMANTIC_EXTRACTION" &&
      run.semanticV2?.mode === "DELTA_FAST_PATH" &&
      result.outcome !== "SUCCESS"
    ) {
      run = markSemanticV2Fallback(
        run,
        "DELTA_AGENT_DID_NOT_COMPLETE",
        `${result.outcome}: ${result.summary}`,
      )
      if (result.outcome === "BLOCKED") {
        result = {
          outcome: "RETRY",
          nextStage: "SEMANTIC_EXTRACTION",
          summary: `Delta extractor could not soundly complete; the run is switching to the full legacy Semantic Extractor for an independent determination: ${result.summary}`,
        }
      }
    }
    const criticRequestedFullReview =
      run.stage === "SEMANTIC_CRITIQUE" &&
      run.semanticV2?.mode === "DELTA_FAST_PATH" &&
      result.summary.includes("FULL_REVIEW_REQUIRED")
    if (
      run.stage === "SEMANTIC_CRITIQUE" &&
      run.semanticV2?.mode === "DELTA_FAST_PATH" &&
      (result.outcome === "REVISE" || criticRequestedFullReview)
    ) {
      run = markSemanticV2Fallback(
        run,
        "SEMANTIC_CRITIC_REQUESTED_REVISION",
        result.summary,
        "CRITIC_FALLBACK",
      )
      if (criticRequestedFullReview && result.outcome !== "REVISE") {
        result = {
          outcome: "REVISE",
          nextStage: "SEMANTIC_EXTRACTION",
          summary: result.summary,
        }
      }
    }

    result = normalizeAgentDecision(run, result)
    const nextStage = validateAgentDecision(run, result)
    const producedArtifact = artifactChanged(
      run.activeExecution?.artifactBaseline,
      await artifactFingerprint(artifact.outputPath),
    )
    const execution = {
      startedAt: run.activeExecution?.startedAt,
      at: new Date().toISOString(),
      stage: run.stage,
      agent: plan.agent,
      model: executionModel.full,
      sessionId,
      outcome: result.outcome,
      nextStage,
      response: response || (submitted ? "[no textual response]" : "[resumed session]"),
      artifactProduced: producedArtifact,
      ...(failureClass === undefined ? {} : { failureClass }),
      ...(proofProgress === undefined ? {} : { progress: proofProgress }),
      ...(traceability === undefined ? {} : { traceability }),
    }
    let nextRun = failureClass === "PROVIDER_RETRY_BUDGET_EXCEEDED"
      ? {
          ...run,
          updatedAt: new Date().toISOString(),
        }
      : result.outcome === "RETRY"
        ? retryRun(run, `${plan.agent} retry: ${result.summary}`)
        : transitionRun(run, nextStage, `${plan.agent}: ${result.summary}`)

    nextRun = {
      ...nextRun,
      activeExecution: undefined,
      executions: [
        ...(run.executions ?? []),
        execution,
      ],
    }

    await saveRun(nextRun)

    console.log(JSON.stringify({
      ok: true,
      runId: nextRun.runId,
      agent: plan.agent,
      sessionId,
      outcome: result.outcome,
      fromStage: run.stage,
      toStage: nextRun.stage,
      revision: nextRun.revision,
      summary: result.summary,
    }, null, 2))
  } finally {
    if (ownsRuntime) {
      runtime.runtime.server.close()
    }
  }
}

async function main(): Promise<void> {
  await executeTick(required("--run"), {
    dryRun: process.argv.includes("--dry-run"),
  })
}

if (
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  await main()
}
