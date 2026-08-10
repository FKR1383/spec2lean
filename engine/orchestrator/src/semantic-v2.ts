import { createHash } from "node:crypto"
import {
  access,
  mkdir,
  readFile,
  readdir,
  stat,
  writeFile,
} from "node:fs/promises"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"

import { stageAttempt } from "./artifact-contract.js"
import { canonicalJson } from "./semantic-ir/canonical.js"
import { sharedEnvironmentSha256 } from "./semantic-ir/document.js"
import { materializeSemanticView } from "./semantic-ir/materialize.js"
import { createDeltaCriticPacket } from "./semantic-ir/review-packet.js"
import { CLAIM_CLASSIFICATIONS } from "./semantic-ir/types.js"
import type {
  ClaimClassification,
  InstructionSemanticDelta,
  MaterializedSemanticView,
  SharedSemanticEnvironment,
} from "./semantic-ir/types.js"
import {
  validateInstructionSemanticDelta,
  validateSharedSemanticEnvironment,
} from "./semantic-ir/validate.js"
import { REPO_ROOT } from "./repo.js"
import type { RunState, SemanticV2ArtifactSet } from "./workflow.js"

export type SemanticProfile = {
  schemaVersion: 1
  language: string
  specificationVersion: string
  strategy: "DELTA_PREFERRED_WITH_LEGACY_FALLBACK"
  sharedEnvironmentPath: string
  supportedUnitPatterns: string[]
  requiredSharedSemanticIds: string[]
  requiredSharedClassifications: Record<string, ClaimClassification>
  approval: {
    reviewCandidatePath: string
    humanReviewPacketPath: string
    approvedEnvironmentPath: string
    approvalRecordPath: string
  }
  safety: {
    requireHumanApprovedEnvironment: boolean
    requireActiveApprovedEntries: boolean
    blockStateAffectingOpenQuestions: boolean
    verifySourceBundleFingerprint: boolean
    verifyOfficialEvidenceFingerprints: boolean
  }
  fallback: {
    enabled: boolean
    mode: "LEGACY_FULL_SEMANTICS"
    description: string
  }
}

export type SemanticEligibility = {
  eligible: boolean
  code: string
  detail: string
  profilePath: string
  sharedEnvironmentPath: string
  missingRequiredSemanticIds: string[]
  profile?: SemanticProfile
  environment?: SharedSemanticEnvironment
  environmentSha256?: string
}

export type SemanticDeltaEvaluation = {
  ok: boolean
  issues: string[]
  unresolvedStateAffectingSemanticIds: string[]
  view?: MaterializedSemanticView
  packet?: ReturnType<typeof createDeltaCriticPacket>
}

export type SemanticV2Preflight = {
  ok: boolean
  issues: string[]
}

const profilePathFor = (run: RunState): string =>
  `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function validRequiredClassifications(value: unknown, semanticIds: string[]): boolean {
  return isRecord(value) &&
    Object.keys(value).length === semanticIds.length &&
    semanticIds.every((semanticId) =>
      CLAIM_CLASSIFICATIONS.includes(value[semanticId] as never)
    )
}

function validApprovalConfig(value: unknown): boolean {
  if (!isRecord(value)) return false
  return ["reviewCandidatePath", "humanReviewPacketPath", "approvedEnvironmentPath", "approvalRecordPath"].every(
    (field) => typeof value[field] === "string" && (value[field] as string).length > 0,
  )
}

export function validProfile(value: unknown): value is SemanticProfile {
  return isRecord(value) &&
    value.schemaVersion === 1 &&
    typeof value.language === "string" &&
    typeof value.specificationVersion === "string" &&
    value.strategy === "DELTA_PREFERRED_WITH_LEGACY_FALLBACK" &&
    typeof value.sharedEnvironmentPath === "string" && value.sharedEnvironmentPath.length > 0 &&
    Array.isArray(value.supportedUnitPatterns) &&
    value.supportedUnitPatterns.length > 0 &&
    value.supportedUnitPatterns.every((item) => typeof item === "string" && item.length > 0) &&
    Array.isArray(value.requiredSharedSemanticIds) &&
    value.requiredSharedSemanticIds.length > 0 &&
    value.requiredSharedSemanticIds.every((item) => typeof item === "string" && item.length > 0) &&
    new Set(value.requiredSharedSemanticIds).size === value.requiredSharedSemanticIds.length &&
    validRequiredClassifications(value.requiredSharedClassifications, value.requiredSharedSemanticIds) &&
    validApprovalConfig(value.approval) &&
    isRecord(value.safety) &&
    value.safety.requireHumanApprovedEnvironment === true &&
    value.safety.requireActiveApprovedEntries === true &&
    value.safety.blockStateAffectingOpenQuestions === true &&
    value.safety.verifySourceBundleFingerprint === true &&
    value.safety.verifyOfficialEvidenceFingerprints === true &&
    isRecord(value.fallback) &&
    value.fallback.enabled === true &&
    value.fallback.mode === "LEGACY_FULL_SEMANTICS"
}

function fallbackEligibility(
  profilePath: string,
  sharedEnvironmentPath: string,
  code: string,
  detail: string,
  missingRequiredSemanticIds: string[] = [],
): SemanticEligibility {
  return {
    eligible: false,
    code,
    detail,
    profilePath,
    sharedEnvironmentPath,
    missingRequiredSemanticIds: [...missingRequiredSemanticIds].sort(),
  }
}

export function assessSemanticFastPathDocuments(
  run: RunState,
  profilePath: string,
  profileInput: unknown,
  environmentInput: unknown,
): SemanticEligibility {
  if (!validProfile(profileInput)) {
    return fallbackEligibility(profilePath, "", "INVALID_SEMANTIC_PROFILE", "Semantic profile is structurally invalid")
  }
  const profile = profileInput
  if (
    profile.language.toLowerCase() !== run.language.toLowerCase() ||
    profile.specificationVersion !== run.specVersion
  ) {
    return fallbackEligibility(profilePath, profile.sharedEnvironmentPath, "SEMANTIC_PROFILE_IDENTITY_MISMATCH", "Semantic profile language/version does not match the run")
  }

  let supported = false
  try {
    supported = profile.supportedUnitPatterns.some((pattern) => new RegExp(pattern).test(run.unit))
  } catch {
    return fallbackEligibility(profilePath, profile.sharedEnvironmentPath, "INVALID_UNIT_PATTERN", "Semantic profile contains an invalid unit pattern")
  }
  if (!supported) {
    return fallbackEligibility(profilePath, profile.sharedEnvironmentPath, "UNIT_OUTSIDE_DELTA_CAPABILITY", `Unit ${run.unit} is outside the explicitly bounded delta fast path`)
  }

  const environmentResult = validateSharedSemanticEnvironment(environmentInput)
  if (!environmentResult.ok || environmentResult.value === undefined) {
    return fallbackEligibility(
      profilePath,
      profile.sharedEnvironmentPath,
      "INVALID_SHARED_ENVIRONMENT",
      environmentResult.issues.map((issue) => issue.code).join(", "),
      profile.requiredSharedSemanticIds,
    )
  }
  const environment = environmentResult.value
  if (
    environment.language.toLowerCase() !== run.language.toLowerCase() ||
    environment.specificationVersion !== run.specVersion
  ) {
    return fallbackEligibility(profilePath, profile.sharedEnvironmentPath, "SHARED_ENVIRONMENT_IDENTITY_MISMATCH", "Shared environment language/version does not match the run", profile.requiredSharedSemanticIds)
  }
  if (
    profile.safety.requireHumanApprovedEnvironment &&
    environment.review.status !== "HUMAN_APPROVED"
  ) {
    return fallbackEligibility(
      profilePath,
      profile.sharedEnvironmentPath,
      "SHARED_ENVIRONMENT_NOT_HUMAN_APPROVED",
      `Shared environment review status is ${environment.review.status}`,
      profile.requiredSharedSemanticIds,
    )
  }

  const byId = new Map(environment.entries.map((entry) => [entry.semanticId, entry]))
  const missing = profile.requiredSharedSemanticIds.filter((semanticId) => {
    const entry = byId.get(semanticId)
    return entry === undefined ||
      entry.lifecycle.status !== "ACTIVE" ||
      entry.classification !== profile.requiredSharedClassifications[semanticId] ||
      (profile.safety.requireActiveApprovedEntries && entry.review.status !== "HUMAN_APPROVED")
  })
  if (missing.length > 0) {
    return fallbackEligibility(profilePath, profile.sharedEnvironmentPath, "REQUIRED_SHARED_SEMANTICS_UNAVAILABLE", "One or more required shared semantic entries are missing, inactive, or unapproved", missing)
  }

  if (!environment.sourceManifests.some((item) => item.path === run.sourceManifest)) {
    return fallbackEligibility(profilePath, profile.sharedEnvironmentPath, "SOURCE_MANIFEST_NOT_PINNED_BY_ENVIRONMENT", "Run source manifest is not pinned by the shared environment")
  }

  return {
    eligible: true,
    code: "DELTA_FAST_PATH_ELIGIBLE",
    detail: "Shared environment and bounded unit capability satisfy the semantic v2 fast-path contract",
    profilePath,
    sharedEnvironmentPath: profile.sharedEnvironmentPath,
    missingRequiredSemanticIds: [],
    profile,
    environment,
    environmentSha256: sharedEnvironmentSha256(environment),
  }
}

export async function assessSemanticFastPath(run: RunState): Promise<SemanticEligibility> {
  const profilePath = profilePathFor(run)
  let profileInput: unknown
  try {
    profileInput = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8"))
  } catch (error) {
    return fallbackEligibility(profilePath, "", "SEMANTIC_PROFILE_UNAVAILABLE", `Cannot load semantic profile: ${String(error)}`)
  }
  if (!validProfile(profileInput)) {
    return fallbackEligibility(profilePath, "", "INVALID_SEMANTIC_PROFILE", "Semantic profile is structurally invalid")
  }
  let environmentInput: unknown
  try {
    environmentInput = JSON.parse(
      await readFile(resolve(REPO_ROOT, profileInput.sharedEnvironmentPath), "utf8"),
    )
  } catch (error) {
    return fallbackEligibility(profilePath, profileInput.sharedEnvironmentPath, "SHARED_ENVIRONMENT_UNAVAILABLE", `Cannot load shared environment: ${String(error)}`, profileInput.requiredSharedSemanticIds)
  }
  const assessment = assessSemanticFastPathDocuments(run, profilePath, profileInput, environmentInput)
  if (!assessment.eligible || assessment.environment === undefined) return assessment
  try {
    await verifySharedEnvironmentFiles(
      run,
      assessment.environment,
      profileInput.requiredSharedSemanticIds,
    )
  } catch (error) {
    return fallbackEligibility(
      profilePath,
      profileInput.sharedEnvironmentPath,
      "SHARED_PROVENANCE_VERIFICATION_FAILED",
      error instanceof Error ? error.message : String(error),
      profileInput.requiredSharedSemanticIds,
    )
  }
  return assessment
}

function semanticArtifacts(run: RunState): SemanticV2ArtifactSet {
  const attempt = stageAttempt(run, "SEMANTIC_EXTRACTION")
  return {
    attempt,
    deltaPath: `${run.artifactRoot}/semantics/semantic-delta-v${attempt}.json`,
    materializedPath: `${run.artifactRoot}/semantics/semantics-v${attempt}.json`,
    criticPacketPath: `${run.artifactRoot}/reviews/semantic-delta-critic-packet-v${attempt}.json`,
  }
}

export async function prepareSemanticV2Run(run: RunState): Promise<RunState> {
  if (run.stage !== "SEMANTIC_EXTRACTION") return run
  if (run.semanticV2?.mode === "LEGACY_FALLBACK") return run
  if (run.semanticV2?.mode === "DELTA_FAST_PATH" && run.semanticV2.current !== undefined) return run

  const assessment = await assessSemanticFastPath(run)
  const now = new Date().toISOString()
  return {
    ...run,
    semanticV2: {
      profilePath: assessment.profilePath,
      sharedEnvironmentPath: assessment.sharedEnvironmentPath,
      mode: assessment.eligible ? "DELTA_FAST_PATH" : "LEGACY_FALLBACK",
      environment: assessment.environment === undefined
        ? undefined
        : {
            environmentId: assessment.environment.environmentId,
            revision: assessment.environment.revision,
            sha256: assessment.environmentSha256!,
            reviewStatus: assessment.environment.review.status,
          },
      missingRequiredSemanticIds: assessment.missingRequiredSemanticIds,
      fallbackReason: assessment.eligible ? undefined : `${assessment.code}: ${assessment.detail}`,
      current: assessment.eligible ? semanticArtifacts(run) : undefined,
      events: [
        ...(run.semanticV2?.events ?? []),
        {
          at: now,
          kind: "ELIGIBILITY",
          code: assessment.code,
          detail: assessment.detail,
        },
      ],
    },
  }
}

export function markSemanticV2Fallback(
  run: RunState,
  code: string,
  detail: string,
  kind: "FALLBACK" | "CRITIC_FALLBACK" = "FALLBACK",
): RunState {
  const current = run.semanticV2
  if (current === undefined) return run
  return {
    ...run,
    semanticV2: {
      ...current,
      mode: "LEGACY_FALLBACK",
      fallbackReason: `${code}: ${detail}`,
      events: [
        ...current.events,
        { at: new Date().toISOString(), kind, code, detail },
      ],
    },
  }
}

export function evaluateSemanticDeltaDocuments(
  environmentInput: unknown,
  deltaInput: unknown,
): SemanticDeltaEvaluation {
  const validation = validateInstructionSemanticDelta(deltaInput, environmentInput)
  const issues = validation.issues.map((issue) => `${issue.code}@${issue.path}`)
  if (!validation.ok || validation.value === undefined) {
    return {
      ok: false,
      issues,
      unresolvedStateAffectingSemanticIds: validation.unresolvedStateAffectingSemanticIds,
    }
  }
  if (validation.unresolvedStateAffectingSemanticIds.length > 0) {
    return {
      ok: false,
      issues: ["UNRESOLVED_STATE_AFFECTING_OPEN_QUESTION"],
      unresolvedStateAffectingSemanticIds: validation.unresolvedStateAffectingSemanticIds,
    }
  }
  try {
    const view = materializeSemanticView(environmentInput, deltaInput)
    const packet = createDeltaCriticPacket(
      environmentInput as SharedSemanticEnvironment,
      deltaInput as InstructionSemanticDelta,
    )
    return { ok: true, issues: [], unresolvedStateAffectingSemanticIds: [], view, packet }
  } catch (error) {
    return {
      ok: false,
      issues: [`MATERIALIZATION_FAILED: ${String(error)}`],
      unresolvedStateAffectingSemanticIds: [],
    }
  }
}

function sha256(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex")
}

function ensureRepositoryRelative(path: string): string {
  if (path.length === 0 || path.includes("\0") || path.includes("\\") || isAbsolute(path)) {
    throw new Error(`Unsafe repository-relative path: ${path}`)
  }
  const absolute = resolve(REPO_ROOT, path)
  const relation = relative(REPO_ROOT, absolute)
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`Path escapes repository: ${path}`)
  }
  return absolute
}

async function verifiedFileHash(path: string, allowedPrefix: string): Promise<string> {
  if (path !== allowedPrefix && !path.startsWith(`${allowedPrefix}/`)) {
    throw new Error(`Path is outside ${allowedPrefix}: ${path}`)
  }
  const absolute = ensureRepositoryRelative(path)
  const metadata = await stat(absolute)
  if (!metadata.isFile()) throw new Error(`Not a regular file: ${path}`)
  return sha256(await readFile(absolute))
}

async function verifySharedEnvironmentFiles(
  run: RunState,
  environment: SharedSemanticEnvironment,
  requiredSemanticIds: string[],
): Promise<void> {
  const hashCache = new Map<string, string>()
  const fileHash = async (path: string, prefix = "documents/sources"): Promise<string> => {
    const key = `${prefix}:${path}`
    let hash = hashCache.get(key)
    if (hash === undefined) {
      hash = await verifiedFileHash(path, prefix)
      hashCache.set(key, hash)
    }
    return hash
  }
  const manifest = environment.sourceManifests.find((item) => item.path === run.sourceManifest)
  if (manifest === undefined || await fileHash(run.sourceManifest) !== manifest.sha256) {
    throw new Error("Shared environment source-manifest fingerprint does not match the run file")
  }

  const byId = new Map(environment.entries.map((entry) => [entry.semanticId, entry]))
  const selected = new Set(requiredSemanticIds)
  const pending = [...selected]
  while (pending.length > 0) {
    const semanticId = pending.pop()
    if (semanticId === undefined) continue
    for (const dependencyId of byId.get(semanticId)?.dependencyIds ?? []) {
      if (!selected.has(dependencyId)) {
        selected.add(dependencyId)
        pending.push(dependencyId)
      }
    }
  }
  const evidenceIds = new Set(
    environment.entries
      .filter((entry) => selected.has(entry.semanticId))
      .flatMap((entry) => entry.evidenceIds),
  )
  for (const record of environment.review.records) {
    if (await fileHash(record.path, "reviews") !== record.sha256) {
      throw new Error(`Shared environment review-record hash mismatch: ${record.path}`)
    }
  }
  for (const entry of environment.entries.filter((item) => selected.has(item.semanticId))) {
    for (const origin of entry.provenance.originatingArtifacts) {
      if (await fileHash(origin.path, "accepted") !== origin.sha256) {
        throw new Error(`Shared entry originating-artifact hash mismatch: ${entry.semanticId}`)
      }
    }
    for (const review of entry.provenance.reviewRecords) {
      if (await fileHash(review.path, "reviews") !== review.sha256) {
        throw new Error(`Shared entry review-record hash mismatch: ${entry.semanticId}`)
      }
    }
    for (const support of entry.provenance.acceptedUnitSupport) {
      for (const artifact of support.artifacts) {
        if (await fileHash(artifact.path, "accepted") !== artifact.sha256) {
          throw new Error(`Shared entry accepted-unit artifact hash mismatch: ${entry.semanticId}/${support.unit}`)
        }
      }
      for (const review of support.reviewRecords) {
        if (await fileHash(review.path, "reviews") !== review.sha256) {
          throw new Error(`Shared entry accepted-unit review hash mismatch: ${entry.semanticId}/${support.unit}`)
        }
      }
    }
  }
  for (const evidence of environment.evidence.filter((item) => evidenceIds.has(item.evidenceId))) {
    if (evidence.source.sourceManifestPath !== run.sourceManifest) {
      throw new Error(`Shared evidence uses a different source manifest: ${evidence.evidenceId}`)
    }
    if (await fileHash(run.sourceManifest) !== evidence.source.sourceManifestSha256) {
      throw new Error(`Shared evidence source-manifest hash mismatch: ${evidence.evidenceId}`)
    }
    if (await fileHash(evidence.source.documentPath) !== evidence.source.documentSha256) {
      throw new Error(`Shared evidence document hash mismatch: ${evidence.evidenceId}`)
    }
  }
}

async function latestSourceBundle(run: RunState): Promise<string> {
  const directory = `${run.artifactRoot}/source-bundles`
  const entries = await readdir(ensureRepositoryRelative(directory))
  const candidates = entries.flatMap((name) => {
    const match = name.match(/^source-bundle-v(\d+)\.json$/)
    return match?.[1] === undefined ? [] : [{ name, version: Number(match[1]) }]
  }).sort((left, right) => right.version - left.version)
  const latest = candidates[0]
  if (latest === undefined) throw new Error("No versioned source bundle exists")
  return `${directory}/${latest.name}`
}

function bundleEvidenceIds(bundle: unknown): Set<string> {
  if (!isRecord(bundle) || !isRecord(bundle.evidence_index) || !Array.isArray(bundle.evidence_index.fragments)) {
    throw new Error("Source bundle has no evidence_index.fragments array")
  }
  return new Set(bundle.evidence_index.fragments.flatMap((fragment) =>
    isRecord(fragment) && typeof fragment.fragment_id === "string"
      ? [fragment.fragment_id]
      : [],
  ))
}

async function verifyDeltaGrounding(
  run: RunState,
  delta: InstructionSemanticDelta,
): Promise<void> {
  const bundlePath = await latestSourceBundle(run)
  if (delta.provenance.sourceBundle.path !== bundlePath) {
    throw new Error(`Delta source bundle is not the latest run bundle: expected ${bundlePath}`)
  }
  const bundleData = await readFile(ensureRepositoryRelative(bundlePath))
  if (sha256(bundleData) !== delta.provenance.sourceBundle.sha256) {
    throw new Error("Delta source-bundle fingerprint does not match file content")
  }
  const fragments = bundleEvidenceIds(JSON.parse(bundleData.toString("utf8")))
  const sourceFactEvidenceIds = new Set(
    [...delta.claims, ...delta.refinements]
      .filter((claim) => claim.classification === "SOURCE_FACT")
      .flatMap((claim) => claim.evidenceIds),
  )
  const evidenceById = new Map(delta.evidence.map((item) => [item.evidenceId, item]))
  for (const evidenceId of sourceFactEvidenceIds) {
    const evidence = evidenceById.get(evidenceId)
    if (evidence === undefined || evidence.sourceBundleEvidenceId === undefined) {
      throw new Error(`SOURCE_FACT evidence lacks source-bundle grounding: ${evidenceId}`)
    }
    if (!fragments.has(evidence.sourceBundleEvidenceId)) {
      throw new Error(`Unknown source-bundle evidence fragment: ${evidence.sourceBundleEvidenceId}`)
    }
    if (evidence.source.sourceManifestPath !== run.sourceManifest) {
      throw new Error(`Evidence source manifest does not match the run: ${evidenceId}`)
    }
    const manifestHash = await verifiedFileHash(run.sourceManifest, "documents/sources")
    if (manifestHash !== evidence.source.sourceManifestSha256) {
      throw new Error(`Evidence source-manifest fingerprint mismatch: ${evidenceId}`)
    }
    const documentHash = await verifiedFileHash(evidence.source.documentPath, "documents/sources")
    if (documentHash !== evidence.source.documentSha256) {
      throw new Error(`Evidence document fingerprint mismatch: ${evidenceId}`)
    }
  }
}

async function writeImmutable(path: string, body: string): Promise<void> {
  const absolute = ensureRepositoryRelative(path)
  await mkdir(dirname(absolute), { recursive: true })
  try {
    await writeFile(absolute, body, { encoding: "utf8", flag: "wx" })
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "EEXIST")) throw error
    const existing = await readFile(absolute, "utf8")
    if (existing !== body) throw new Error(`Immutable semantic artifact collision: ${path}`)
  }
}

export async function materializeSemanticDeltaForRun(run: RunState): Promise<RunState> {
  const state = run.semanticV2
  if (state?.mode !== "DELTA_FAST_PATH" || state.current === undefined) {
    throw new Error("Run is not configured for semantic delta materialization")
  }
  const environmentInput = JSON.parse(
    await readFile(ensureRepositoryRelative(state.sharedEnvironmentPath), "utf8"),
  ) as unknown
  const deltaText = await readFile(ensureRepositoryRelative(state.current.deltaPath), "utf8")
  const deltaInput = JSON.parse(deltaText) as unknown
  const evaluation = evaluateSemanticDeltaDocuments(environmentInput, deltaInput)
  if (!evaluation.ok || evaluation.view === undefined || evaluation.packet === undefined) {
    throw new Error([...evaluation.issues, ...evaluation.unresolvedStateAffectingSemanticIds].join(" | "))
  }
  await verifyDeltaGrounding(run, deltaInput as InstructionSemanticDelta)

  const materializedText = canonicalJson(evaluation.view)
  const packetText = canonicalJson(evaluation.packet)
  await writeImmutable(state.current.criticPacketPath, packetText)
  // The Gate-B semantics path is written last and therefore acts as the
  // completion marker for deterministic composition.
  await writeImmutable(state.current.materializedPath, materializedText)
  const current: SemanticV2ArtifactSet = {
    ...state.current,
    deltaBytes: deltaText.length,
    materializedBytes: Buffer.byteLength(materializedText, "utf8"),
    criticPacketBytes: Buffer.byteLength(packetText, "utf8"),
    deltaSha256: sha256(deltaText),
    materializedSha256: sha256(materializedText),
    criticPacketSha256: sha256(packetText),
  }
  return {
    ...run,
    semanticV2: {
      ...state,
      current,
      events: [
        ...state.events,
        {
          at: new Date().toISOString(),
          kind: "MATERIALIZED",
          code: "DELTA_VALIDATED_AND_MATERIALIZED",
          detail: `delta=${current.deltaPath}; view=${current.materializedPath}; packet=${current.criticPacketPath}`,
        },
      ],
    },
  }
}

export async function verifySemanticV2CriticPreflight(
  run: RunState,
): Promise<SemanticV2Preflight> {
  const state = run.semanticV2
  const current = state?.current
  if (
    state?.mode !== "DELTA_FAST_PATH" ||
    state.environment === undefined ||
    current === undefined
  ) {
    return { ok: false, issues: ["DELTA_FAST_PATH_STATE_INCOMPLETE"] }
  }
  const issues: string[] = []
  try {
    const environment = JSON.parse(
      await readFile(ensureRepositoryRelative(state.sharedEnvironmentPath), "utf8"),
    ) as unknown
    const validation = validateSharedSemanticEnvironment(environment)
    if (!validation.ok || validation.value === undefined) {
      issues.push("SHARED_ENVIRONMENT_INVALID")
    } else {
      if (validation.value.review.status !== "HUMAN_APPROVED") {
        issues.push("SHARED_ENVIRONMENT_NOT_HUMAN_APPROVED")
      }
      if (sharedEnvironmentSha256(validation.value) !== state.environment.sha256) {
        issues.push("SHARED_ENVIRONMENT_HASH_DRIFT")
      }
    }
  } catch (error) {
    issues.push(`SHARED_ENVIRONMENT_UNREADABLE: ${String(error)}`)
  }

  for (const [label, path, expected] of [
    ["DELTA", current.deltaPath, current.deltaSha256],
    ["MATERIALIZED", current.materializedPath, current.materializedSha256],
    ["CRITIC_PACKET", current.criticPacketPath, current.criticPacketSha256],
  ] as const) {
    if (expected === undefined) {
      issues.push(`${label}_HASH_MISSING`)
      continue
    }
    try {
      const actual = await verifiedFileHash(path, run.artifactRoot)
      if (actual !== expected) issues.push(`${label}_HASH_DRIFT`)
    } catch (error) {
      issues.push(`${label}_UNREADABLE: ${String(error)}`)
    }
  }
  return { ok: issues.length === 0, issues }
}

export async function semanticProfileExists(run: RunState): Promise<boolean> {
  try {
    await access(resolve(REPO_ROOT, profilePathFor(run)))
    return true
  } catch {
    return false
  }
}
