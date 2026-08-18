import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import {
  buildProvenanceCatalog,
  compactProvenanceCatalog,
  latestVersionedArtifact,
  type ArtifactIdentity,
} from "./provenance-catalog.js"
import { REPO_ROOT } from "./repo.js"
import {
  MAX_ARCHITECTURE_BYTES,
  MAX_ARCHITECTURE_LINES,
} from "./artifact-limits.js"
import { architectureStateAffectingOpenQuestions } from "./architecture-review.js"
import type { GateName, RunState } from "./workflow.js"

function sha256(value: Buffer | string): string {
  return createHash("sha256").update(value).digest("hex")
}

async function identity(path: string): Promise<ArtifactIdentity> {
  return { path, sha256: sha256(await readFile(resolve(REPO_ROOT, path))) }
}

async function optionalLatest(
  directory: string,
  patterns: readonly RegExp[],
): Promise<ArtifactIdentity | undefined> {
  try {
    return await identity(await latestVersionedArtifact(directory, patterns))
  } catch {
    return undefined
  }
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
}

async function sharedEnvironmentSummary(run: RunState): Promise<SharedEnvironmentSummary | undefined> {
  const profilePath = `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`
  try {
    const profile = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8")) as {
      sharedEnvironmentPath?: unknown
      supportedUnitPatterns?: unknown
    }
    if (typeof profile.sharedEnvironmentPath !== "string") return undefined
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

/** Build the exact, compact stage input contract injected into the model call. */
export async function buildStageInputContext(run: RunState): Promise<string> {
  const root = run.artifactRoot
  const [architecture, architectureReview, sourceBundle, semantics, lean, obligations, shared] = await Promise.all([
    optionalLatest(`${root}/architecture`, [/^foundation-v(\d+)\.md$/]),
    optionalLatest(`${root}/reviews`, [/^architecture-critic-v(\d+)\.md$/]),
    optionalLatest(`${root}/source-bundles`, [/^source-bundle-v(\d+)\.json$/]),
    optionalLatest(`${root}/semantics`, [/^semantics-v(\d+)\.json$/]),
    optionalLatest(`${root}/lean`, [new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`)]),
    optionalLatest(`${root}/theorems`, [/^obligations-v(\d+)\.json$/]),
    sharedEnvironmentSummary(run),
  ])

  const lines = [
    "# Deterministic Stage Input Contract",
    "",
    artifactLine("architecture", architecture),
    artifactLine("architecture critique", architectureReview),
    artifactLine("source bundle", sourceBundle),
    artifactLine("semantic authority", semantics),
    artifactLine("Lean mapping", lean),
    artifactLine("theorem obligations", obligations),
    `- Gate A authority: ${gateAuthority(run, "A")}`,
    `- Gate B authority: ${gateAuthority(run, "B")}`,
    `- Gate C authority: ${gateAuthority(run, "C")}`,
    `- Theorem authority: ${gateAuthority(run, "THEOREM_STRENGTH")}`,
    "",
    "Use exactly these versioned inputs. Do not select a different `latest` artifact by globbing.",
    "A benchmark auto-advance authorizes pipeline continuation only; never call it human approval.",
  ]

  if (shared === undefined) {
    lines.push(
      "",
      "# Shared semantic reuse",
      "",
      "No hash-bound HUMAN_APPROVED shared environment is available to this prompt.",
      "Prior unit artifacts are neither semantic dependencies nor default templates; do not inspect them unless the runtime explicitly supplies one as an input.",
    )
  } else {
    lines.push(
      "",
      "# Shared semantic reuse",
      "",
      `- Environment: ${shared.path} (sha256=${shared.sha256})`,
      `- Review status: ${shared.reviewStatus}`,
      `- Scope: ${shared.scope}`,
      `- Current unit eligible for this shared environment: ${shared.unitEligible}`,
      `- Reusable active HUMAN_APPROVED IDs: ${shared.semanticIds.join(", ") || "NONE"}`,
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
        "Any source-visible exclusion makes the Lean module BOUNDED_PARTIAL and must appear in Supported forms, Excluded forms, Evidence policy, theorem scope, and traceability.",
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
          "Use BOUNDED_PARTIAL if any source-visible form is excluded or unresolved; never hide narrowing in constructors.",
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
      "Append exactly one HTML comment containing canonical JSON:",
      "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
      '{"schemaVersion":1,"entries":[{"semanticId":"D-1","classification":"DESIGN_DEPENDENCY","statement":"...","evidenceIds":["SF-1"],"dependencyIds":["SF-1"],"stateAffecting":true,"status":"RESOLVED"}]}',
      "-->",
      "Index every architecture SOURCE_FACT, DERIVED_INTERPRETATION, DESIGN_DEPENDENCY, ASSUMPTION, and OPEN_QUESTION exactly once.",
      "Every evidenceIds/dependencyIds value must resolve to another entry in this same index; use SOURCE_FACT IDs as architecture evidence references.",
      "SOURCE_FACT entries must have empty evidenceIds and dependencyIds because they are the architecture evidence roots; cite their official locators in the human-readable section.",
      "Do one initial write, validate once, and make at most one bounded replacement for concrete diagnostics. If validation still fails, return RETRY with the exact issue instead of repeatedly rewriting.",
    )
  }
  if (run.stage === "SOURCE_CURATION") {
    lines.push(
      "",
      "# Source-bundle v2 output contract",
      "",
      "Schema: ir/source/source-bundle-v2.schema.json",
      "Use schema_version=2 with bundle_id, language, specification_version, unit, source_documents, fragments, and evidence_gaps.",
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
      "# Theorem correctness contract v2",
      "",
      "Write schema_version=2 and a source_faithfulness_boundary statement.",
      "Every theorem obligation requires correctness_kind, correctness_rationale, semantic_claim_ids, and one complete header-only Lean theorem declaration.",
      "The contract must contain at least one OPERATION_FIDELITY obligation and one EXECUTION_CORRESPONDENCE obligation.",
      "These prove that Lean implements the approved semantic IR. They do not prove that official source prose is itself true; that boundary remains evidence-, critic-, and gate-governed.",
      "Additional applicable kinds are GUARD_BEHAVIOR, STATE_UPDATE, FRAME_PROPERTY, DETERMINISM, PARTIALITY, and SCOPE_BOUNDARY.",
    )
  }
  if (run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode !== "DELTA_FAST_PATH") {
    lines.push(
      "",
      "# Full-semantics v2 output contract",
      "",
      "Schema: ir/semantic/full-semantics.schema.json",
      "Use schemaVersion=2 and documentType=spec2lean_full_semantics.",
      "Required arrays: semanticClaims, syntaxForms, operands, stateEffects, preconditions, proofFamilies; operation is required.",
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
