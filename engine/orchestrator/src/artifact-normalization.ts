import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun } from "./artifact-contract.js"
import { authoritativeArtifact } from "./artifact-authority.js"
import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"

type UnknownRecord = Record<string, unknown>

export type ArtifactNormalization = {
  content: string
  normalizedFields: string[]
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function assign(target: UnknownRecord, field: string, value: unknown, prefix: string, changed: string[]): void {
  if (JSON.stringify(target[field]) === JSON.stringify(value)) return
  target[field] = value
  changed.push(`${prefix}.${field}`)
}

async function profileBinding(run: RunState): Promise<{ path: string; sha256: string }> {
  const path = run.semanticV2?.profilePath ??
    `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`
  const profile = JSON.parse(await readFile(resolve(REPO_ROOT, path), "utf8")) as UnknownRecord
  if (typeof profile.languageCorePath !== "string") throw new Error("semantic profile has no languageCorePath")
  const core = await readFile(resolve(REPO_ROOT, profile.languageCorePath))
  return { path: profile.languageCorePath, sha256: sha256(core) }
}

/**
 * Normalize only orchestration-owned metadata on the exact active output.
 * Semantic statements, classifications, coverage, and theorem content are
 * deliberately untouched.
 */
export async function normalizeExpectedArtifactContent(
  run: RunState,
  path: string,
  source: string,
  producerAgent: string,
): Promise<ArtifactNormalization> {
  if (!path.endsWith(".json") || path !== artifactContractForRun(run).outputPath) {
    return { content: source, normalizedFields: [] }
  }
  const document = JSON.parse(source) as unknown
  if (!isRecord(document)) return { content: source, normalizedFields: [] }
  const changed: string[] = []

  if (run.stage === "SOURCE_CURATION") {
    if (run.qualityContractVersion === 1) assign(document, "schema_version", 3, "$", changed)
    assign(document, "language", run.language, "$", changed)
    assign(document, "specification_version", run.specVersion, "$", changed)
    assign(document, "unit", run.unit, "$", changed)
  }

  if (run.stage === "SEMANTIC_EXTRACTION") {
    const unit = isRecord(document.unit) ? document.unit : {}
    document.unit = unit
    const semanticLanguage = run.semanticV2?.mode === "DELTA_FAST_PATH"
      ? JSON.parse(await readFile(resolve(REPO_ROOT, run.semanticV2.sharedEnvironmentPath), "utf8")).language
      : run.language
    assign(unit, "language", semanticLanguage, "$.unit", changed)
    assign(unit, "specificationVersion", run.specVersion, "$.unit", changed)
    assign(unit, "unit", run.unit, "$.unit", changed)
    assign(unit, "unitSlug", run.unitSlug, "$.unit", changed)

    if (run.semanticV2?.mode === "DELTA_FAST_PATH") {
      assign(document, "schemaVersion", 1, "$", changed)
      if (run.semanticV2.environment === undefined) throw new Error("semantic delta has no pinned environment")
      const shared = isRecord(document.sharedEnvironment) ? document.sharedEnvironment : {}
      document.sharedEnvironment = shared
      assign(shared, "environmentId", run.semanticV2.environment.environmentId, "$.sharedEnvironment", changed)
      assign(shared, "revision", run.semanticV2.environment.revision, "$.sharedEnvironment", changed)
      assign(shared, "sha256", run.semanticV2.environment.sha256, "$.sharedEnvironment", changed)
      const sourceBundle = await authoritativeArtifact(run, "SOURCE_BUNDLE")
      const provenance = isRecord(document.provenance) ? document.provenance : {}
      document.provenance = provenance
      assign(provenance, "sourceBundle", { path: sourceBundle.path, sha256: sourceBundle.sha256 }, "$.provenance", changed)
      assign(provenance, "generatedBy", producerAgent, "$.provenance", changed)
    } else {
      if (run.qualityContractVersion === 1) assign(document, "schemaVersion", 3, "$", changed)
      assign(document, "documentType", "spec2lean_full_semantics", "$", changed)
      const [architecture, sourceBundle] = await Promise.all([
        authoritativeArtifact(run, "ARCHITECTURE"),
        authoritativeArtifact(run, "SOURCE_BUNDLE"),
      ])
      const provenance = isRecord(document.provenance) ? document.provenance : {}
      document.provenance = provenance
      assign(provenance, "architecture", { path: architecture.path, sha256: architecture.sha256 }, "$.provenance", changed)
      assign(provenance, "sourceBundles", [{ path: sourceBundle.path, sha256: sourceBundle.sha256 }], "$.provenance", changed)
      assign(provenance, "gateAAuthority", run.gates.A === "benchmark_auto_advanced"
        ? "BENCHMARK_AUTO_ADVANCED_NOT_HUMAN_APPROVED"
        : "HUMAN_APPROVED", "$.provenance", changed)
    }

    if (isRecord(document.languageCore) && document.languageCore.status === "REUSED_APPROVED") {
      const binding = await profileBinding(run)
      assign(document.languageCore, "path", binding.path, "$.languageCore", changed)
      assign(document.languageCore, "sha256", binding.sha256, "$.languageCore", changed)
    }
  }

  if (run.stage === "THEOREM_GENERATION") {
    if (run.qualityContractVersion === 1) assign(document, "schema_version", 3, "$", changed)
    assign(document, "run_id", run.runId, "$", changed)
  }

  return changed.length === 0
    ? { content: source, normalizedFields: [] }
    : { content: `${JSON.stringify(document, null, 2)}\n`, normalizedFields: changed }
}
