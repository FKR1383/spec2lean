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
  const [architecture, sourceBundle, semantics, lean, obligations, shared] = await Promise.all([
    optionalLatest(`${root}/architecture`, [/^foundation-v(\d+)\.md$/]),
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
      "Prior accepted units may be inspected as examples but are not semantic dependencies.",
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
      lines.push(
        "",
        "# Exact provenance allowlist",
        "",
        `Semantic document: ${catalog.semanticDocument.path} (sha256=${catalog.semanticDocument.sha256})`,
        `Architecture document: ${catalog.architectureDocument.path} (sha256=${catalog.architectureDocument.sha256})`,
        "The IDs below are the complete declaration-provenance allowlist. Never invent or approximate an ID:",
        compactProvenanceCatalog(catalog),
        "",
        "Every generated Lean declaration must use an immediately preceding comment of the exact form:",
        "-- spec2lean: ID-1, ID-2",
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
      "Keep the concise human-readable review document, then append exactly one HTML comment containing canonical JSON:",
      "<!-- SPEC2LEAN_ARCHITECTURE_INDEX",
      '{"schemaVersion":1,"entries":[{"semanticId":"D-1","classification":"DESIGN_DEPENDENCY","statement":"...","evidenceIds":["SF-1"],"dependencyIds":["SF-1"],"stateAffecting":true,"status":"RESOLVED"}]}',
      "-->",
      "Index every architecture SOURCE_FACT, DERIVED_INTERPRETATION, DESIGN_DEPENDENCY, ASSUMPTION, and OPEN_QUESTION exactly once.",
      "Every evidenceIds/dependencyIds value must resolve to another entry in this same index; use SOURCE_FACT IDs as architecture evidence references.",
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
      "Every gap requires gap_id, statement, and impact=LOAD_BEARING|NON_LOAD_BEARING.",
      "A LOAD_BEARING gap that prevents operand/operation/state behavior from being stated soundly requires BLOCKED, not SUCCESS.",
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
    `After the final candidate_write, call candidate_validate with runId=${run.runId} and path=<required stage artifact>.`,
    "Repair every reported structural/provenance issue in this same session and validate again.",
    "Do not emit SUCCESS until candidate_validate returns ok=true.",
    "If validation exposes a genuine source or semantic gap, return BLOCKED instead of manufacturing content.",
  )

  return lines.join("\n")
}
