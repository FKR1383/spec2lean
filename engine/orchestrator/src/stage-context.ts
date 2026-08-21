import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import {
  buildProvenanceCatalog,
  compactProvenanceCatalog,
  type ArtifactIdentity,
} from "./provenance-catalog.js"
import { optionalAuthoritativeArtifact } from "./artifact-authority.js"
import { REPO_ROOT } from "./repo.js"
import {
  MAX_ARCHITECTURE_BYTES,
  MAX_ARCHITECTURE_LINES,
} from "./artifact-limits.js"
import { architectureStateAffectingOpenQuestions } from "./architecture-review.js"
import { loadLanguageCore } from "./language-core.js"
import { verifyLeanFile } from "./lean-local.js"
import type { GateName, RunState } from "./workflow.js"
import {
  criticVisibleArtifactAreas,
  type StageArtifactArea,
} from "./stage-ownership.js"

function sha256(value: Buffer | string): string {
  return createHash("sha256").update(value).digest("hex")
}

function gateAuthority(run: RunState, gate: GateName): string {
  switch (run.gates[gate]) {
    case "approved":
      return "HUMAN_APPROVED"
    case "benchmark_auto_advanced":
      return "BENCHMARK_AUTO_ADVANCED_NOT_HUMAN_APPROVED"
    case "rejected":
      return "HUMAN_REJECTED"
    default:
      return "PENDING"
  }
}

type SharedEnvironmentSummary = {
  path: string
  sha256: string
  reviewStatus: string
  scope: string
  semanticIds: string[]
  unitEligible: boolean
  corePath: string
  coreSha256: string
  leanModulePath: string
  leanModuleSha256: string
  leanImportName: string
  coreRoles: string[]
}

async function sharedEnvironmentSummary(run: RunState): Promise<SharedEnvironmentSummary | undefined> {
  const profilePath = `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`
  try {
    const profile = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8")) as {
      sharedEnvironmentPath?: unknown
      languageCorePath?: unknown
      supportedUnitPatterns?: unknown
    }
    if (typeof profile.sharedEnvironmentPath !== "string" ||
      typeof profile.languageCorePath !== "string") return undefined
    const core = await loadLanguageCore(profile.languageCorePath)
    if (core.semanticEnvironment.path !== profile.sharedEnvironmentPath) return undefined
    const source = await readFile(resolve(REPO_ROOT, profile.sharedEnvironmentPath), "utf8")
    const environment = JSON.parse(source) as {
      review?: { status?: unknown }
      scope?: { statement?: unknown }
      entries?: Array<{ semanticId?: unknown; lifecycle?: { status?: unknown }; review?: { status?: unknown } }>
    }
    const unitEligible = Array.isArray(profile.supportedUnitPatterns) &&
      profile.supportedUnitPatterns.some((pattern) =>
        typeof pattern === "string" && new RegExp(pattern).test(run.unit)
      )
    const semanticIds = (environment.entries ?? []).flatMap((entry) =>
      typeof entry.semanticId === "string" &&
      unitEligible &&
      entry.lifecycle?.status === "ACTIVE" &&
      entry.review?.status === "HUMAN_APPROVED"
        ? [entry.semanticId]
        : []
    ).sort((left, right) => left.localeCompare(right))
    return {
      path: profile.sharedEnvironmentPath,
      sha256: sha256(source),
      reviewStatus: String(environment.review?.status ?? "UNKNOWN"),
      scope: String(environment.scope?.statement ?? "UNSPECIFIED"),
      semanticIds,
      unitEligible,
      corePath: profile.languageCorePath,
      coreSha256: sha256(await readFile(resolve(REPO_ROOT, profile.languageCorePath))),
      leanModulePath: core.leanModule.path,
      leanModuleSha256: core.leanModule.sha256,
      leanImportName: core.leanModule.importName,
      coreRoles: Object.entries(core.modelRoles)
        .map(([role, value]) => `${role}=${value.leanDeclaration}`)
        .sort((left, right) => left.localeCompare(right)),
    }
  } catch {
    return undefined
  }
}

function artifactLine(label: string, artifact: ArtifactIdentity | undefined): string {
  return artifact === undefined
    ? `- ${label}: NOT_AVAILABLE`
    : `- ${label}: ${artifact.path} (sha256=${artifact.sha256})`
}

type StageInputArtifact = {
  label: string
  area: StageArtifactArea
  artifact: ArtifactIdentity | undefined
}

function visibleStageInputArtifacts(
  run: RunState,
  artifacts: readonly StageInputArtifact[],
): StageInputArtifact[] {
  const visible = new Set(stageInputArtifactAreas(run.stage))
  return artifacts.filter((entry) => visible.has(entry.area))
}

export function stageInputArtifactAreas(
  stage: RunState["stage"],
): readonly StageArtifactArea[] {
  const criticAreas = criticVisibleArtifactAreas(stage)
  if (criticAreas.length > 0) return criticAreas
  const producerAreas: Partial<Record<RunState["stage"], readonly StageArtifactArea[]>> = {
    ARCHITECTURE: ["architecture", "reviews"],
    SOURCE_CURATION: ["architecture", "source-bundles", "reviews"],
    SEMANTIC_EXTRACTION: ["architecture", "source-bundles", "semantics", "reviews"],
    LEAN_FORMALIZATION: ["architecture", "semantics", "lean", "reviews"],
    THEOREM_GENERATION: ["architecture", "semantics", "lean", "theorems", "reviews"],
    PROOF_GENERATION: ["semantics", "lean", "theorems", "reviews"],
  }
  return producerAreas[stage] ?? [
    "architecture",
    "source-bundles",
    "semantics",
    "lean",
    "theorems",
    "reviews",
  ]
}

/** Build the exact, compact stage input contract injected into the model call. */
export async function buildStageInputContext(run: RunState): Promise<string> {
  const [architecture, architectureReview, sourceBundle, semantics, lean, obligations, shared] = await Promise.all([
    optionalAuthoritativeArtifact(run, "ARCHITECTURE"),
    optionalAuthoritativeArtifact(run, "ARCHITECTURE_REVIEW"),
    optionalAuthoritativeArtifact(run, "SOURCE_BUNDLE"),
    optionalAuthoritativeArtifact(
      run,
      run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode === "DELTA_FAST_PATH"
        ? "SEMANTIC_DELTA"
        : "SEMANTICS",
    ),
    optionalAuthoritativeArtifact(run, "LEAN_MAPPING"),
    optionalAuthoritativeArtifact(run, "THEOREM_OBLIGATIONS"),
    sharedEnvironmentSummary(run),
  ])

  const availableArtifacts = visibleStageInputArtifacts(run, [
    { label: "architecture", area: "architecture", artifact: architecture },
    { label: "architecture critique", area: "reviews", artifact: architectureReview },
    { label: "source bundle", area: "source-bundles", artifact: sourceBundle },
    {
      label: run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode === "DELTA_FAST_PATH"
        ? "previous semantic delta repair input"
        : "semantic authority",
      area: "semantics",
      artifact: semantics,
    },
    { label: "Lean mapping", area: "lean", artifact: lean },
    { label: "theorem obligations", area: "theorems", artifact: obligations },
  ])
  const visibleAreas = new Set(availableArtifacts.map((entry) => entry.area))

  const lines = [
    "# Deterministic Stage Input Contract",
    "",
    ...availableArtifacts.map((entry) => artifactLine(entry.label, entry.artifact)),
    `- Gate A authority: ${gateAuthority(run, "A")}`,
    `- Gate B authority: ${gateAuthority(run, "B")}`,
    `- Gate C authority: ${gateAuthority(run, "C")}`,
    `- Theorem authority: ${gateAuthority(run, "THEOREM_STRENGTH")}`,
    "",
    "Use exactly these versioned inputs. Do not select a different `latest` artifact by globbing.",
    `Authorized current-unit artifact areas: ${[...visibleAreas].join(", ") || "NONE"}.`,
    "Do not inspect or cite a current-unit artifact area omitted above, even if a stale file exists from an earlier run attempt.",
    "A critic finding must be repairable by that critic's declared upstream revision target; never route a producer against a downstream artifact it does not own.",
    "A benchmark auto-advance authorizes pipeline continuation only; never call it human approval.",
  ]

  if (run.stage === "LEAN_FORMALIZATION" && lean !== undefined) {
    const previousCheck = await verifyLeanFile(lean.path, 90_000).catch((error) => ({
      success: false,
      output: error instanceof Error ? error.message : String(error),
    }))
    lines.push(
      "",
      "# Previous immutable Lean repair input",
      "",
      `Repair ${lean.path} into the newly requested immutable revision; do not overwrite it.`,
      previousCheck.success
        ? "The previous Lean file compiles; preserve its declarations and repair only remaining contract diagnostics."
        : `Binding Lean diagnostic: ${previousCheck.output.slice(-8_000)}`,
    )
  }

  if (shared === undefined) {
    lines.push(
      "",
      "# Shared semantic reuse",
      "",
      "No hash-bound HUMAN_APPROVED language semantic core is available to this prompt.",
      "This is a first-language/core boundary. Mark languageCore.status=BOOTSTRAP_CANDIDATE and keep reusable model decisions explicit; never pretend they are already shared or approved.",
      "Prior unit artifacts are neither semantic dependencies nor default templates; do not inspect them unless the runtime explicitly supplies one as an input.",
    )
  } else {
    lines.push(
      "",
      "# Language semantic core reuse",
      "",
      `- Environment: ${shared.path} (sha256=${shared.sha256})`,
      `- Language core manifest: ${shared.corePath} (sha256=${shared.coreSha256})`,
      `- Lean core: ${shared.leanModulePath} (sha256=${shared.leanModuleSha256})`,
      `- Required Lean import: import ${shared.leanImportName}`,
      `- Model roles: ${shared.coreRoles.join(", ")}`,
      `- Review status: ${shared.reviewStatus}`,
      `- Scope: ${shared.scope}`,
      `- Current unit matches the core candidate pattern: ${shared.unitEligible}`,
      `- Reusable active HUMAN_APPROVED IDs: ${shared.semanticIds.join(", ") || "NONE"}`,
      "This environment is the build-once language core: units reuse it and describe only instruction/construct-specific deltas.",
      "When eligible, the Lean mapping must import this exact core and must not redeclare any listed model role.",
      "Pattern match is not semantic eligibility: architecture and its critic must verify every scope eligibility requirement and must use BOOTSTRAP_CANDIDATE/deep review when any requirement fails.",
      "Only those IDs may be treated as shared semantic dependencies, and only when the unit satisfies the stated scope.",
      "Do not import a per-unit accepted artifact as shared authority.",
    )
  }

  if (
    run.benchmark?.autoApprove === true &&
    run.gates.A === "benchmark_auto_advanced" &&
    architecture !== undefined
  ) {
    const questions = architectureStateAffectingOpenQuestions(
      await readFile(resolve(REPO_ROOT, architecture.path), "utf8"),
    )
    if (questions.length > 0) {
      lines.push(
        "",
        "# Benchmark semantic-assumption waiver",
        "",
        "This benchmark was allowed to continue with unresolved questions. This is not human approval and does not resolve any question:",
        ...questions.map((entry) => `- ${entry.semanticId}: ${entry.statement}`),
        "Mandatory policy: CONSERVATIVE_BOUNDED_SCOPE.",
        "Preserve every listed ID as OPEN_QUESTION and visible provenance.",
        "Do not guess an NVIDIA behavior. Add an explicit project DESIGN_DEPENDENCY that limits the executable/relational model to source-established cases.",
        "A disputed input form or corner case must be excluded by an explicit precondition or represented as partial/underspecified; never assign it an arbitrary result.",
        "Any source-visible exclusion makes the Lean module PARTIAL_EXPLICIT and must appear in Supported forms, Excluded forms, Evidence policy, theorem scope, and traceability.",
        "A benchmark waiver is not a humanApprovalDependency and cannot authorize an ASSUMPTION classification or promotion.",
      )
    }
  }

  if (["ARCHITECTURE", "ARCHITECTURE_CRITIQUE"].includes(run.stage)) {
    lines.push(
      "",
      "# Canonical architecture classification policy",
      "",
      "Architecture SOURCE_FACT entries are internal index roots: evidenceIds=[] and dependencyIds=[] are correct; exact official locators belong in the human-readable fact section.",
      "All non-root evidenceIds must name SOURCE_FACT entries. A resolved DERIVED_INTERPRETATION requires explicit dependencies and may not depend on an OPEN_QUESTION.",
      "DESIGN_DEPENDENCY and ASSUMPTION are intentionally not NVIDIA source facts. Missing source support alone is not a defect when the project-only wording and Gate-A visibility are explicit.",
      "Do not create an OPEN_QUESTION solely because specification prose omits an otherwise inapplicable flag, hidden state, error, or host feature.",
      "A bounded project model may omit unmentioned state components without claiming NVIDIA says they are absent. Express that boundary as DESIGN_DEPENDENCY/ASSUMPTION, scope theorem families to the bounded model, and link any concrete motivating OPEN_QUESTION without marking it resolved.",
      "When a HUMAN_APPROVED shared environment is eligible, its explicit state boundary is reusable and excluded features are not reopened without unit-specific evidence of applicability. When ineligible, do not import it.",
    )
  }

  if (run.stage === "ARCHITECTURE_CRITIQUE" && architecture !== undefined) {
    const questions = architectureStateAffectingOpenQuestions(
      await readFile(resolve(REPO_ROOT, architecture.path), "utf8"),
    )
    lines.push(
      "",
      "# Gate-A open-question triage contract",
      "",
      "Triage exactly the following state-affecting OPEN_QUESTION entries; do not add or omit IDs:",
      ...(questions.length === 0
        ? ["- NONE (the triage entries array must be empty)"]
        : questions.map((entry) => `- ${entry.semanticId}: ${entry.statement}`)),
      "Use GENUINE_HUMAN_REVIEW only for an applicable load-bearing question that evidence/shared policy cannot resolve.",
      "Use REMOVE_OR_RECLASSIFY for a speculative/out-of-scope question, an evidence-resolved question, or a project model boundary; add a BLOCKER/MAJOR finding and return REVISE to ARCHITECTURE.",
      "Append exactly one SPEC2LEAN_GATE_A_OQ_TRIAGE JSON comment. candidate_validate cross-checks it against the hash-pinned architecture.",
    )
  }

  if ([
    "LEAN_FORMALIZATION",
    "LEAN_MAPPING_CRITIQUE",
    "THEOREM_GENERATION",
    "THEOREM_STRENGTH_CRITIQUE",
    "PROOF_GENERATION",
    "FINAL_CRITIQUE",
  ].includes(run.stage)) {
    try {
      const catalog = await buildProvenanceCatalog(run)
      const unresolvedSemanticQuestions = catalog.claims.filter((claim) =>
        claim.classification === "OPEN_QUESTION" &&
        claim.stateAffecting === true &&
        claim.unresolved
      )
      lines.push(
        "",
        "# Exact provenance allowlist",
        "",
        `Semantic document: ${catalog.semanticDocument.path} (sha256=${catalog.semanticDocument.sha256})`,
        `Architecture document: ${catalog.architectureDocument.path} (sha256=${catalog.architectureDocument.sha256})`,
        "The IDs below are the complete declaration-provenance allowlist. Never invent or approximate an ID:",
        compactProvenanceCatalog(catalog),
        ...(run.benchmark?.autoApprove === true &&
          run.gates.B === "benchmark_auto_advanced" &&
          unresolvedSemanticQuestions.length > 0
          ? [
              "",
              "Gate-B CONSERVATIVE_BOUNDED_SCOPE questions (unresolved, NOT HUMAN APPROVED):",
              ...unresolvedSemanticQuestions.map((claim) => `- ${claim.semanticId}: ${claim.statement}`),
              "Keep these cases explicit and partial/precondition-excluded in Lean and theorem scope.",
            ]
          : []),
        "",
        "Every generated Lean declaration must use an immediately preceding comment of the exact form:",
        "-- spec2lean: ID-1, ID-2",
        ...(run.stage !== "LEAN_FORMALIZATION" ? [] : [
          "",
          "# Lean module header contract",
          "",
          `Unit: ${run.unit}`,
          `Semantic authority: ${catalog.semanticDocument.path}`,
          `Architecture authority: ${catalog.architectureDocument.path}`,
          "Also state Scope status, Supported forms, Excluded forms, and Evidence policy.",
          "Use FULL_INSTRUCTION by default. Use PARTIAL_EXPLICIT only when every exclusion is encoded by a named Lean precondition or partial-result declaration; never hide narrowing in constructors or prose.",
          "Append one SPEC2LEAN_LEAN_MODEL_CONTRACT JSON comment with schemaVersion=1, scopeStatus, languageCoreStatus, languageCoreImport, domainBindings, encodedExclusions, operationBranchBindings, edgeCaseBindings, specificationDefinitions, executableDefinitions, and relationalDefinitions.",
          "For each imported core domain, set providedByLanguageCore=true. For each unit-local domain, declare the named Lean type in this file.",
          "For BOOTSTRAP_CANDIDATE, languageCoreCandidate must repeat the semantic candidateCoreId and list reusableDeclarations plus modelRoleBindings to real declarations; this is a review candidate, never reusable authority.",
          "Bind every semantic operation branchId and edge-case caseId to exactly one list of real unit-local Lean symbols. Every semantic ID used by a COVERED row must occur in a declaration's immediate spec2lean provenance comment.",
          "A FIXED_WIDTH domain binding must name its exact width and may not map to unbounded Int/Nat without a checked subtype invariant.",
          "Reuse the approved language core when eligible. Do not redeclare its word/state/operand/guard model per unit.",
          "candidate_validate enforces this header and rejects unexplained unused def/abbrev declarations.",
        ]),
        "Run `candidate_validate` after the final write; SUCCESS is forbidden while it reports any issue.",
      )
    } catch (error) {
      lines.push(
        "",
        "# Exact provenance allowlist unavailable",
        "",
        `Deterministic catalog construction failed: ${error instanceof Error ? error.message : String(error)}`,
        "Do not invent provenance. Return BLOCKED if this stage requires Lean provenance.",
      )
    }
  }

  if (run.stage === "ARCHITECTURE") {
    lines.push(
      "",
      "# Architecture output contract",
      "",
      `Hard limit: at most ${MAX_ARCHITECTURE_BYTES} UTF-8 bytes and ${MAX_ARCHITECTURE_LINES} lines, including the index. candidate_architecture_write and candidate_validate enforce both limits.`,
      "Use candidate_architecture_write, not candidate_write, for this stage.",
      "For PTX, call spec_fast_context exactly once with purpose=architecture. Do not read, glob, grep, list, or imitate artifacts from other units.",
      "Use these exact Markdown headings once each:",
      "## Bounded scope and exclusions",
      "## Official source facts",
      "## Design dependencies",
      "## Fact-to-design mapping",
      "## Assumptions and open questions",
      "## Behavior and state effects",
      "## Validation and theorem families",
      "## Gate A checklist",
      "Keep each fact/decision concise and cite an exact anchor/page/line locator rather than reproducing long source passages.",
      "Pass the architecture index as the structured candidate_architecture_write architectureIndex argument. Do not place either SPEC2LEAN machine block in content; the tool validates and serializes both comments canonically.",
      "architectureIndex shape:",
      '{"schemaVersion":1,"entries":[{"semanticId":"D-1","classification":"DESIGN_DEPENDENCY","statement":"...","evidenceIds":["SF-1"],"dependencyIds":["SF-1"],"stateAffecting":true,"status":"RESOLVED"}]}',
      "Index every architecture SOURCE_FACT, DERIVED_INTERPRETATION, DESIGN_DEPENDENCY, ASSUMPTION, and OPEN_QUESTION exactly once.",
      "Default to FULL_INSTRUCTION for the exact requested unit. PARTIAL_EXPLICIT is allowed only when a legal case is represented by an explicit precondition/partial outcome, never by prose alone.",
      "Pass the completeness matrix as the structured candidate_architecture_write completenessContract argument:",
      '{"schemaVersion":1,"scopeStatus":"FULL_INSTRUCTION","languageCore":{"status":"REUSED_APPROVED","path":"language_packs/.../language-core.json","sha256":"<64 hex>"},"dimensions":[{"dimension":"SYNTAX","status":"COVERED","semanticIds":["SF-1"],"encodedBy":[],"rationale":"..."}]}',
      "The dimensions array must contain exactly: SYNTAX, OPERANDS, TYPES, OPERATION_BRANCHES, EDGE_CASES, GUARDS, STATE_EFFECTS, ERRORS, VERSION_APPLICABILITY.",
      "Use COVERED or NOT_APPLICABLE for FULL_INSTRUCTION. EXCLUDED_BY_ENCODED_PRECONDITION requires PARTIAL_EXPLICIT plus an encodedBy precondition ID.",
      "For BOOTSTRAP_CANDIDATE, languageCore also requires candidateCoreId, scopeStatement, and proposedSemanticIds limited to genuinely reusable language/version concepts.",
      "Every evidenceIds/dependencyIds value must resolve to another entry in this same index; use SOURCE_FACT IDs as architecture evidence references.",
      "SOURCE_FACT entries must have empty evidenceIds and dependencyIds because they are the architecture evidence roots; cite their official locators in the human-readable section.",
      "candidate_architecture_write rejects malformed structured metadata before publishing. Repair its concrete diagnostic in this same session, then run candidate_validate once. If semantic validation still fails, make at most one bounded replacement.",
    )
  }
  if (run.stage === "SOURCE_CURATION") {
    lines.push(
      "",
      "# Source-bundle v3 full-instruction contract",
      "",
      "Schema: ir/source/source-bundle-v2.schema.json",
      "Use schema_version=3 with bundle_id, language, specification_version, unit, source_documents, fragments, evidence_gaps, and coverage_matrix.",
      `Case-sensitive run identity: language=${JSON.stringify(run.language)}, specification_version=${JSON.stringify(run.specVersion)}, unit=${JSON.stringify(run.unit)}. Copy these three values byte-for-byte; display capitalization such as PTX is not interchangeable with the run identity.`,
      "The schema uses additionalProperties=false. Do not emit status, instruction_family, document_title, source_kind/url/size_bytes/read_in_this_curation_pass on source_documents, publisher/section_number/html_line_start/html_line_end/pdf_page/page/fragment_sha256/context_before/context_after/local_source_path on fragments, or any other undeclared key.",
      "Canonical source document shape: {\"document_id\":\"...\",\"publisher\":\"...\",\"kind\":\"HTML|PDF\",\"local_path\":\"...\",\"sha256\":\"<64 hex>\"}.",
      "Canonical fragment shape: {\"fragment_id\":\"...\",\"document_id\":\"...\",\"source_kind\":\"HTML|PDF\",\"source_sha256\":\"<document sha256>\",\"exact_quote\":\"at least four whitespace-separated tokens\",\"context\":\"optional\",\"locator\":{\"section\":\"optional\",\"heading\":\"optional\",\"anchor\":\"HTML optional\",\"start_line\":1,\"end_line\":1,\"page\":1},\"reason_for_inclusion\":\"...\"}. Keep only locator keys applicable to the rendition.",
      "Canonical coverage row shape: {\"dimension\":\"SYNTAX\",\"status\":\"COVERED\",\"fragment_ids\":[\"...\"],\"gap_ids\":[],\"rationale\":\"...\"}. fragment_ids and gap_ids are mandatory arrays on every row, including NOT_APPLICABLE rows where both are empty.",
      "coverage_matrix must contain exactly the nine completeness dimensions and classify each as COVERED, NOT_APPLICABLE, or GAP with fragment_ids/gap_ids and rationale.",
      "Every fragment requires fragment_id, document_id, exact_quote, source_sha256, reason_for_inclusion, and an HTML/PDF locator.",
      "When the source manifest pins both HTML and PDF, every load-bearing SOURCE_FACT needs an exact HTML quotation/anchor/line path and PDF corroboration by an explicit PDF fragment or deterministic exact-quote alignment.",
      "Do not call a source bundle complete when either required rendition is missing; candidate traceability generation enforces both paths.",
      "Every gap requires gap_id, statement, and impact=LOAD_BEARING|NON_LOAD_BEARING.",
      "A LOAD_BEARING gap that prevents operand/operation/state behavior from being stated soundly requires BLOCKED, not SUCCESS.",
    )
  }
  if (run.stage === "THEOREM_GENERATION") {
    lines.push(
      "",
      "# Theorem correctness contract v3",
      "",
      "Write schema_version=3 and a source_faithfulness_boundary statement.",
      "Every theorem obligation requires exactly one proof_requirement_id plus correctness_kind, correctness_rationale, semantic_claim_ids, independent_specification_symbols, implementation_symbols, and one complete header-only Lean theorem declaration.",
      "Every LOCAL semantics proofRequirements ID must map to exactly one independent theorem with the same correctness kind and all required semantic claim IDs. Never regenerate INHERITED_FROM_SHARED_ENVIRONMENT or NOT_APPLICABLE requirements locally.",
      "The contract must contain at least one OPERATION_FIDELITY obligation and one EXECUTION_CORRESPONDENCE obligation.",
      "OPERATION/ALGORITHM/RANGE/EDGE obligations must compare a separately defined source-level specification symbol with implementation symbols; unfolding an implementation against itself is rejected.",
      "EXECUTION_CORRESPONDENCE must mention both the executable and relational definitions named by SPEC2LEAN_LEAN_MODEL_CONTRACT.",
      "Cover every mandatory LOCAL semantics.proofRequirements correctnessKind exactly; inherited requirements require an exact approved coreDischargeId, and NOT_APPLICABLE must remain explicit.",
      "These prove that Lean implements the approved semantic IR. They do not prove that official source prose is itself true; that boundary remains evidence-, critic-, and gate-governed.",
      "Additional applicable kinds are ALGORITHM_FIDELITY, RESULT_RANGE, EDGE_CASE_BEHAVIOR, TYPE_DOMAIN, GUARD_BEHAVIOR, STATE_UPDATE, FRAME_PROPERTY, DETERMINISM, PARTIALITY, and SCOPE_BOUNDARY.",
    )
  }
  if (run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode !== "DELTA_FAST_PATH") {
    lines.push(
      "",
      "# Full-semantics v3 full-instruction contract",
      "",
      "Schema: ir/semantic/full-semantics.schema.json",
      "Use schemaVersion=3 and documentType=spec2lean_full_semantics.",
      "Required arrays: semanticClaims, syntaxForms, operands, stateEffects, preconditions, proofFamilies; operation is required.",
      "Every operand requires exhaustive legalForms, exact typeDomains, and explicit coercions. Operation requires inputDomains, outputDomain, explicit branches, and explicit edgeCases (or the corresponding coverage row must be NOT_APPLICABLE).",
      "Also require scopeStatus, languageCore, the exact nine-row coverage array, and non-empty proofRequirements.",
      "REUSED_APPROVED languageCore must contain the exact runtime-supplied core manifest path and SHA-256; otherwise use BOOTSTRAP_CANDIDATE without pretending reuse.",
      "BOOTSTRAP_CANDIDATE must be concrete: include candidateCoreId, scopeStatement, eligibilityRequirements, reusableSemanticClaimIds, and proposedModelRoles. This enables one-time human review and later promotion without silently sharing a first unit.",
      "Default scopeStatus=FULL_INSTRUCTION. PARTIAL_EXPLICIT requires every exclusion to use EXCLUDED_BY_ENCODED_PRECONDITION and name a real preconditionId.",
      "proofRequirements is the machine-enforced bridge to theorem generation; classify each requirement as LOCAL, INHERITED_FROM_SHARED_ENVIRONMENT, or NOT_APPLICABLE. Inherited is valid only with an exact approved coreDischargeId; otherwise use LOCAL.",
      "Mandatory independent proof requirements are OPERATION_FIDELITY, ALGORITHM_FIDELITY, RESULT_RANGE, GUARD_BEHAVIOR, STATE_UPDATE, FRAME_PROPERTY, and EXECUTION_CORRESPONDENCE.",
      "Every semanticClaims entry uses semanticId, classification, statement, evidenceIds, dependencyIds, stateAffecting, humanApprovalDependencies, and lifecycle.",
      "SOURCE_FACT needs exact bundle evidence IDs; DERIVED_INTERPRETATION needs exact semantic dependencies; DESIGN_DEPENDENCY is never source prose.",
      "An ACTIVE OPEN_QUESTION with stateAffecting=true is a valid research blocker and must not be concretized by Lean.",
    )
  }

  lines.push(
    "",
    "# Same-session completion check",
    "",
    `After the final ${run.stage === "ARCHITECTURE" ? "candidate_architecture_write" : "candidate_write"}, call candidate_validate with runId=${run.runId} and path=<required stage artifact>.`,
    "Repair every reported structural/provenance issue in this same session and validate again.",
    "Do not emit SUCCESS until candidate_validate returns ok=true.",
    "If validation exposes a genuine source or semantic gap, return BLOCKED instead of manufacturing content.",
  )

  return lines.join("\n")
}
