import { createHash } from "node:crypto"
import { readFile, readdir, stat } from "node:fs/promises"
import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import type {
  ArtifactRole,
  FormalizationStage,
  PublishedArtifact,
  RunState,
} from "./workflow.js"

export class MissingPublishedArtifactBindingError extends Error {
  constructor(
    readonly runId: string,
    readonly role: ArtifactRole,
  ) {
    super(`Run ${runId} has no published artifact binding for ${role}`)
    this.name = "MissingPublishedArtifactBindingError"
  }
}

const PRIMARY_ROLE: Partial<Record<FormalizationStage, ArtifactRole>> = {
  ARCHITECTURE: "ARCHITECTURE",
  ARCHITECTURE_CRITIQUE: "ARCHITECTURE_REVIEW",
  SOURCE_CURATION: "SOURCE_BUNDLE",
  SEMANTIC_CRITIQUE: "SEMANTICS_REVIEW",
  LEAN_FORMALIZATION: "LEAN_MAPPING",
  LEAN_MAPPING_CRITIQUE: "LEAN_MAPPING_REVIEW",
  THEOREM_GENERATION: "THEOREM_OBLIGATIONS",
  THEOREM_STRENGTH_CRITIQUE: "THEOREM_STRENGTH_REVIEW",
  PROOF_GENERATION: "LEAN_PROOFS",
  FINAL_CRITIQUE: "FINAL_REVIEW",
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

export function primaryArtifactRole(run: RunState): ArtifactRole {
  if (run.stage === "SEMANTIC_EXTRACTION") {
    return run.semanticV2?.mode === "DELTA_FAST_PATH" ? "SEMANTIC_DELTA" : "SEMANTICS"
  }
  const role = PRIMARY_ROLE[run.stage]
  if (role === undefined) throw new Error(`Stage ${run.stage} does not publish an artifact`)
  return role
}

export async function publishedArtifact(
  run: RunState,
  input: {
    role: ArtifactRole
    path: string
    stage: FormalizationStage
    agent: string
    sessionId: string
    runRevision: number
  },
): Promise<PublishedArtifact> {
  const data = await readFile(resolve(REPO_ROOT, input.path))
  return {
    role: input.role,
    path: input.path,
    sha256: sha256(data),
    sizeBytes: data.length,
    stage: input.stage,
    producingExecution: {
      agent: input.agent,
      sessionId: input.sessionId,
    },
    runRevision: input.runRevision,
  }
}

export function recordedArtifact(
  run: RunState,
  role: ArtifactRole,
): PublishedArtifact | undefined {
  for (const execution of [...(run.executions ?? [])].reverse()) {
    const binding = [...(execution.publishedArtifacts ?? [])]
      .reverse()
      .find((artifact) => artifact.role === role)
    if (binding !== undefined) return binding
  }
  return undefined
}

export async function verifyPublishedArtifact(
  artifact: PublishedArtifact,
): Promise<PublishedArtifact> {
  const absolute = resolve(REPO_ROOT, artifact.path)
  const metadata = await stat(absolute)
  if (!metadata.isFile()) throw new Error(`Published artifact is not a regular file: ${artifact.path}`)
  const data = await readFile(absolute)
  const actual = sha256(data)
  if (actual !== artifact.sha256 || data.length !== artifact.sizeBytes) {
    throw new Error(
      `Published artifact changed after revision ${artifact.runRevision}: ${artifact.path}`,
    )
  }
  return artifact
}

/** Resolve a trust-boundary input from the successful execution record, never by vN ordering. */
export async function authoritativeArtifact(
  run: RunState,
  role: ArtifactRole,
): Promise<PublishedArtifact> {
  const binding = recordedArtifact(run, role) ?? await legacyRecordedArtifact(run, role)
  if (binding === undefined) {
    throw new MissingPublishedArtifactBindingError(run.runId, role)
  }
  return await verifyPublishedArtifact(binding)
}

export async function optionalAuthoritativeArtifact(
  run: RunState,
  role: ArtifactRole,
): Promise<PublishedArtifact | undefined> {
  const binding = recordedArtifact(run, role) ?? await legacyRecordedArtifact(run, role)
  return binding === undefined ? undefined : await verifyPublishedArtifact(binding)
}

type LegacyLocation = {
  stage: FormalizationStage
  directory: string
  patterns: RegExp[]
}

function legacyLocation(run: RunState, role: ArtifactRole): LegacyLocation | undefined {
  const root = run.artifactRoot
  const locations: Partial<Record<ArtifactRole, LegacyLocation>> = {
    ARCHITECTURE: { stage: "ARCHITECTURE", directory: `${root}/architecture`, patterns: [/^foundation-v(\d+)\.md$/] },
    ARCHITECTURE_REVIEW: { stage: "ARCHITECTURE_CRITIQUE", directory: `${root}/reviews`, patterns: [/^architecture-critic-v(\d+)\.md$/] },
    SOURCE_BUNDLE: { stage: "SOURCE_CURATION", directory: `${root}/source-bundles`, patterns: [/^source-bundle-v(\d+)\.json$/] },
    SEMANTIC_DELTA: { stage: "SEMANTIC_EXTRACTION", directory: `${root}/semantics`, patterns: [/^semantic-delta-v(\d+)\.json$/] },
    SEMANTICS: { stage: "SEMANTIC_EXTRACTION", directory: `${root}/semantics`, patterns: [/^semantics-v(\d+)\.json$/] },
    SEMANTICS_REVIEW: { stage: "SEMANTIC_CRITIQUE", directory: `${root}/reviews`, patterns: [/^semantics-critic-v(\d+)\.md$/] },
    LEAN_MAPPING: { stage: "LEAN_FORMALIZATION", directory: `${root}/lean`, patterns: [new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`)] },
    LEAN_MAPPING_REVIEW: { stage: "LEAN_MAPPING_CRITIQUE", directory: `${root}/reviews`, patterns: [/^lean-mapping-critic-v(\d+)\.md$/] },
    THEOREM_OBLIGATIONS: { stage: "THEOREM_GENERATION", directory: `${root}/theorems`, patterns: [/^obligations-v(\d+)\.json$/] },
    THEOREM_STRENGTH_REVIEW: { stage: "THEOREM_STRENGTH_CRITIQUE", directory: `${root}/reviews`, patterns: [/^theorem-strength-critic-v(\d+)\.md$/] },
    LEAN_PROOFS: { stage: "PROOF_GENERATION", directory: `${root}/lean`, patterns: [new RegExp(`^${run.leanModuleName}Proofs-v(\\d+)\\.lean$`)] },
    FINAL_REVIEW: { stage: "FINAL_CRITIQUE", directory: `${root}/reviews`, patterns: [/^final-critic-v(\d+)\.md$/] },
  }
  return locations[role]
}

async function legacyRecordedArtifact(
  run: RunState,
  role: ArtifactRole,
): Promise<PublishedArtifact | undefined> {
  if (role === "SEMANTICS" && run.semanticV2?.current?.materializedSha256 !== undefined) {
    const path = run.semanticV2.current.materializedPath
    const data = await readFile(resolve(REPO_ROOT, path))
    return {
      role,
      path,
      sha256: run.semanticV2.current.materializedSha256,
      sizeBytes: data.length,
      stage: "SEMANTIC_EXTRACTION",
      producingExecution: { agent: "orchestrator-semantic-materializer", sessionId: "legacy" },
      runRevision: 0,
    }
  }
  if (role === "SEMANTIC_CRITIC_PACKET" && run.semanticV2?.current?.criticPacketSha256 !== undefined) {
    const path = run.semanticV2.current.criticPacketPath
    const data = await readFile(resolve(REPO_ROOT, path))
    return {
      role,
      path,
      sha256: run.semanticV2.current.criticPacketSha256,
      sizeBytes: data.length,
      stage: "SEMANTIC_EXTRACTION",
      producingExecution: { agent: "orchestrator-semantic-materializer", sessionId: "legacy" },
      runRevision: 0,
    }
  }
  const location = legacyLocation(run, role)
  if (location === undefined) return undefined
  const execution = [...(run.executions ?? [])].reverse().find((item) =>
    item.stage === location.stage && item.outcome === "SUCCESS" && item.artifactAfterSha256 !== undefined
  )
  if (execution?.artifactAfterSha256 === undefined) {
    return await legacyHumanApprovedArtifact(run, role, location.stage)
  }
  const path = await uniquePathWithRecordedHash(
    location.directory,
    location.patterns,
    execution.artifactAfterSha256,
  )
  const data = await readFile(resolve(REPO_ROOT, path))
  return {
    role,
    path,
    sha256: execution.artifactAfterSha256,
    sizeBytes: data.length,
    stage: location.stage,
    producingExecution: { agent: execution.agent, sessionId: execution.sessionId },
    runRevision: 0,
  }
}

function approvalDirectory(run: RunState, role: ArtifactRole): string | undefined {
  const root = `reviews/${run.language}-${run.unitSlug}`
  if (role === "ARCHITECTURE" || role === "ARCHITECTURE_REVIEW") return `${root}/gate-a`
  if (role === "SEMANTICS" || role === "SEMANTICS_REVIEW") return `${root}/gate-b`
  if (role === "LEAN_MAPPING" || role === "LEAN_MAPPING_REVIEW") return `${root}/gate-c`
  if (role === "THEOREM_OBLIGATIONS" || role === "THEOREM_STRENGTH_REVIEW") return `${root}/theorem-strength`
  if (role === "LEAN_PROOFS" || role === "FINAL_REVIEW") return `${root}/gate-final`
  return undefined
}

async function legacyHumanApprovedArtifact(
  run: RunState,
  role: ArtifactRole,
  stage: FormalizationStage,
): Promise<PublishedArtifact | undefined> {
  const directory = approvalDirectory(run, role)
  if (directory === undefined) return undefined
  let names: string[]
  try {
    names = await readdir(resolve(REPO_ROOT, directory))
  } catch {
    return undefined
  }
  const candidates = new Map<string, { path: string; sha256: string; sizeBytes: number }>()
  for (const name of names.filter((item) => /approval-v\d+\.json$/.test(item))) {
    const record = JSON.parse(await readFile(resolve(REPO_ROOT, `${directory}/${name}`), "utf8")) as {
      decision?: unknown
      provenance?: { runId?: unknown }
      artifacts?: Array<{ relativePath?: unknown; sha256?: unknown; sizeBytes?: unknown }>
    }
    if (record.decision !== "approved" ||
      (record.provenance?.runId !== undefined && record.provenance.runId !== run.runId)) continue
    for (const artifact of record.artifacts ?? []) {
      if (typeof artifact.relativePath !== "string" ||
        typeof artifact.sha256 !== "string" ||
        typeof artifact.sizeBytes !== "number") continue
      const relativePath = artifact.relativePath
      if (!relativePath.startsWith(`${run.artifactRoot}/`)) continue
      const location = legacyLocation(run, role)
      if (location === undefined || !location.patterns.some((pattern) =>
        pattern.test(relativePath.split("/").at(-1) ?? "")
      )) continue
      candidates.set(relativePath, {
        path: relativePath,
        sha256: artifact.sha256,
        sizeBytes: artifact.sizeBytes,
      })
    }
  }
  if (candidates.size !== 1) return undefined
  const candidate = [...candidates.values()][0]!
  const execution = [...(run.executions ?? [])].reverse().find((item) =>
    item.stage === stage && item.outcome === "SUCCESS"
  )
  return {
    role,
    ...candidate,
    stage,
    producingExecution: {
      agent: execution?.agent ?? "legacy-human-approved-artifact",
      sessionId: execution?.sessionId ?? "legacy",
    },
    runRevision: 0,
  }
}

export function isPublishedPath(run: RunState, path: string): boolean {
  return (run.executions ?? []).some((execution) =>
    (execution.publishedArtifacts ?? []).some((artifact) => artifact.path === path)
  )
}

/**
 * Legacy migration helper: locate by the hash already recorded by the
 * orchestrator. Numeric version ordering is deliberately irrelevant.
 */
export async function uniquePathWithRecordedHash(
  directory: string,
  patterns: readonly RegExp[],
  expectedSha256: string,
): Promise<string> {
  const entries = await readdir(resolve(REPO_ROOT, directory), { withFileTypes: true })
  const matches: string[] = []
  for (const entry of entries) {
    if (!entry.isFile() || entry.isSymbolicLink() || !patterns.some((pattern) => pattern.test(entry.name))) continue
    const path = `${directory}/${entry.name}`
    if (sha256(await readFile(resolve(REPO_ROOT, path))) === expectedSha256) matches.push(path)
  }
  if (matches.length !== 1) {
    throw new Error(
      `Recorded SHA-256 resolves to ${matches.length} artifacts under ${directory}; expected exactly one`,
    )
  }
  return matches[0]!
}
