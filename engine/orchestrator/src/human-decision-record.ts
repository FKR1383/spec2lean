import { createHash, randomUUID } from "node:crypto"
import {
  access,
  link,
  lstat,
  mkdir,
  readFile,
  readdir,
  realpath,
  unlink,
  writeFile,
} from "node:fs/promises"
import {
  dirname,
  isAbsolute,
  relative,
  resolve,
  sep,
} from "node:path"

import { REPO_ROOT } from "./repo.js"
import type { GateName, RunState } from "./workflow.js"

type HumanDecision = "approved" | "rejected"

type ArtifactFingerprint = {
  relativePath: string
  sha256: string
  sizeBytes: number
}

type HumanDecisionRecord = {
  schemaVersion: 1
  recordType:
    | "human_gate_decision"
    | "human_theorem_strength_decision"
  reviewId: string
  unitId: string
  gate: "A" | "B" | "C" | "FINAL"
  decision: HumanDecision
  reviewer: string
  rationale: string
  submittedAtUtc: string
  artifacts: ArtifactFingerprint[]
  humanConfirmationRecorded: true
  gateApprovalPerformed: boolean
  promotionPerformed: false
  provenance: {
    controller: "spec2lean-cli"
    runId: string
    command: "approve" | "reject"
  }
}

export type RecordHumanDecisionInput = {
  run: RunState
  gate: GateName
  decision: HumanDecision
  reviewId: string
  reviewPath: string
  reviewer: string
  rationale: string
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function ensureInside(root: string, candidate: string): void {
  const relation = relative(root, candidate)

  if (
    relation === ".." ||
    relation.startsWith(`..${sep}`) ||
    isAbsolute(relation)
  ) {
    throw new Error("path escapes its allowed root")
  }
}

function validateRelativePath(path: string): void {
  if (
    path.length === 0 ||
    path.includes("\0") ||
    path.includes("\\") ||
    isAbsolute(path)
  ) {
    throw new Error(`unsafe repository-relative path: ${path}`)
  }
}

function reviewToolGate(
  gate: GateName,
): HumanDecisionRecord["gate"] {
  // Schema v1 inherited the review_submit tool's A/B/C/D/FINAL gate enum.
  // Keep existing records compatible until that schema is deliberately
  // versioned; recordType distinguishes theorem-strength decisions from C.
  return gate === "THEOREM_STRENGTH" ? "C" : gate
}

function reviewRecordType(
  gate: GateName,
): HumanDecisionRecord["recordType"] {
  return gate === "THEOREM_STRENGTH"
    ? "human_theorem_strength_decision"
    : "human_gate_decision"
}

async function latestVersionedArtifact(
  directory: string,
  pattern: RegExp,
): Promise<string> {
  validateRelativePath(directory)
  const root = await realpath(REPO_ROOT)
  const absoluteDirectory = resolve(root, directory)
  ensureInside(root, absoluteDirectory)
  const canonicalDirectory = await realpath(absoluteDirectory)
  ensureInside(root, canonicalDirectory)
  if (canonicalDirectory !== absoluteDirectory) {
    throw new Error("gate artifact directory may not contain symbolic links")
  }

  const entries = await readdir(canonicalDirectory, {
    withFileTypes: true,
  })

  const candidates = entries
    .filter((entry) => entry.isFile() && !entry.isSymbolicLink())
    .flatMap((entry) => {
      const match = entry.name.match(pattern)
      return match?.[1] === undefined
        ? []
        : [{ name: entry.name, version: Number(match[1]) }]
    })
    .filter((entry) => Number.isSafeInteger(entry.version))
    .sort((left, right) => right.version - left.version)

  const latest = candidates[0]
  if (latest === undefined) {
    throw new Error(`No gate artifact matching ${pattern} under ${directory}`)
  }

  return `${directory}/${latest.name}`
}

export async function artifactPathsForGate(
  run: RunState,
  gate: GateName,
): Promise<string[]> {
  const root = run.artifactRoot

  switch (gate) {
    case "A":
      return await Promise.all([
        latestVersionedArtifact(
          `${root}/architecture`,
          /^foundation-v(\d+)\.md$/,
        ),
        latestVersionedArtifact(
          `${root}/reviews`,
          /^architecture-critic-v(\d+)\.md$/,
        ),
      ])

    case "B":
      return await Promise.all([
        latestVersionedArtifact(
          `${root}/semantics`,
          /^semantics-v(\d+)\.json$/,
        ),
        latestVersionedArtifact(
          `${root}/reviews`,
          /^semantics-critic-v(\d+)\.md$/,
        ),
      ])

    case "C":
      return await Promise.all([
        latestVersionedArtifact(
          `${root}/lean`,
          new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`),
        ),
        latestVersionedArtifact(
          `${root}/reviews`,
          /^lean-mapping-critic-v(\d+)\.md$/,
        ),
      ])

    case "THEOREM_STRENGTH":
      return await Promise.all([
        latestVersionedArtifact(
          `${root}/theorems`,
          /^obligations-v(\d+)\.json$/,
        ),
        latestVersionedArtifact(
          `${root}/reviews`,
          /^theorem-strength-critic-v(\d+)\.md$/,
        ),
      ])

    case "FINAL":
      return await Promise.all([
        latestVersionedArtifact(
          `${root}/lean`,
          new RegExp(`^${run.leanModuleName}Proofs-v(\\d+)\\.lean$`),
        ),
        latestVersionedArtifact(
          `${root}/reviews`,
          /^final-critic-v(\d+)\.md$/,
        ),
      ])
  }
}

async function fingerprintArtifact(
  relativePath: string,
): Promise<ArtifactFingerprint> {
  validateRelativePath(relativePath)
  const root = await realpath(REPO_ROOT)
  const allowedRoot = await realpath(resolve(root, "candidates"))
  const absolutePath = resolve(root, relativePath)
  ensureInside(allowedRoot, absolutePath)

  const metadata = await lstat(absolutePath)
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error(`reviewed artifact is not a regular file: ${relativePath}`)
  }

  const canonicalPath = await realpath(absolutePath)
  ensureInside(allowedRoot, canonicalPath)
  if (canonicalPath !== absolutePath) {
    throw new Error(`reviewed artifact path may not contain symbolic links: ${relativePath}`)
  }
  const data = await readFile(canonicalPath)

  return {
    relativePath,
    sha256: sha256(data),
    sizeBytes: data.length,
  }
}

async function ensureSafeDirectoryTree(
  root: string,
  targetDirectory: string,
): Promise<void> {
  ensureInside(root, targetDirectory)
  const relation = relative(root, targetDirectory)
  let current = root

  for (const component of relation === "" ? [] : relation.split(sep)) {
    current = resolve(current, component)
    let metadata

    try {
      metadata = await lstat(current)
    } catch (error) {
      if (
        !(error instanceof Error && "code" in error && error.code === "ENOENT")
      ) {
        throw error
      }

      try {
        await mkdir(current, { mode: 0o700 })
      } catch (mkdirError) {
        if (
          !(mkdirError instanceof Error &&
            "code" in mkdirError &&
            mkdirError.code === "EEXIST")
        ) {
          throw mkdirError
        }
      }
      metadata = await lstat(current)
    }

    if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
      throw new Error("review path contains a non-directory or symbolic link")
    }
  }
}

async function resolveReviewDestination(
  relativePath: string,
): Promise<string> {
  validateRelativePath(relativePath)
  if (!relativePath.startsWith("reviews/")) {
    throw new Error("human decision records must be under reviews/")
  }

  const root = await realpath(REPO_ROOT)
  const reviewsRoot = await realpath(resolve(root, "reviews"))
  const absolutePath = resolve(root, relativePath)
  ensureInside(reviewsRoot, absolutePath)
  const parent = dirname(absolutePath)
  await ensureSafeDirectoryTree(reviewsRoot, parent)
  return absolutePath
}

export async function writeHumanDecisionRecord(
  input: RecordHumanDecisionInput,
): Promise<void> {
  if (input.reviewer.trim().length < 2) {
    throw new Error("reviewer must contain at least two characters")
  }
  if (input.rationale.trim().length < 1) {
    throw new Error("rationale must not be empty")
  }

  const artifactPaths = await artifactPathsForGate(input.run, input.gate)
  const artifacts = await Promise.all(
    artifactPaths.map((path) => fingerprintArtifact(path)),
  )

  const record: HumanDecisionRecord = {
    schemaVersion: 1,
    recordType: reviewRecordType(input.gate),
    reviewId: input.reviewId,
    unitId: `${input.run.language}-${input.run.unitSlug}`,
    gate: reviewToolGate(input.gate),
    decision: input.decision,
    reviewer: input.reviewer,
    rationale: input.rationale,
    submittedAtUtc: new Date().toISOString(),
    artifacts,
    humanConfirmationRecorded: true,
    gateApprovalPerformed:
      input.decision === "approved" &&
      reviewRecordType(input.gate) === "human_gate_decision",
    promotionPerformed: false,
    provenance: {
      controller: "spec2lean-cli",
      runId: input.run.runId,
      command: input.decision === "approved" ? "approve" : "reject",
    },
  }

  const destination = await resolveReviewDestination(input.reviewPath)
  try {
    await access(destination)
    throw new Error(`human decision record already exists: ${input.reviewPath}`)
  } catch (error) {
    if (
      !(error instanceof Error && "code" in error && error.code === "ENOENT")
    ) {
      throw error
    }
  }

  const content = Buffer.from(`${JSON.stringify(record, null, 2)}\n`, "utf8")
  const temporary = resolve(
    dirname(destination),
    `.${randomUUID()}.human-decision.tmp`,
  )

  try {
    await writeFile(temporary, content, { flag: "wx", mode: 0o600 })
    // A hard link publishes the complete temporary file only if the immutable
    // destination does not already exist. Unlike rename, it cannot overwrite.
    await link(temporary, destination)
  } finally {
    await unlink(temporary).catch(() => undefined)
  }
}

export async function verifyHumanDecisionRecord(
  input: RecordHumanDecisionInput,
): Promise<void> {
  const destination = await resolveReviewDestination(input.reviewPath)
  const metadata = await lstat(destination)
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error("human decision record is not a regular file")
  }

  const record = JSON.parse(
    await readFile(destination, "utf8"),
  ) as Partial<HumanDecisionRecord>

  const expectedUnitId = `${input.run.language}-${input.run.unitSlug}`
  if (record.schemaVersion !== 1) throw new Error("Unsupported review schema")
  if (record.recordType !== reviewRecordType(input.gate)) {
    throw new Error("Human decision record type mismatch")
  }
  if (record.reviewId !== input.reviewId) throw new Error("Review ID mismatch")
  if (record.unitId !== expectedUnitId) throw new Error("Review unit mismatch")
  if (record.gate !== reviewToolGate(input.gate)) throw new Error("Review gate mismatch")
  if (record.decision !== input.decision) throw new Error("Review decision mismatch")
  if (record.humanConfirmationRecorded !== true) {
    throw new Error("Human confirmation was not recorded")
  }

  const expectedApprovalPerformed =
    input.decision === "approved" &&
    reviewRecordType(input.gate) === "human_gate_decision"
  if (record.gateApprovalPerformed !== expectedApprovalPerformed) {
    throw new Error("Gate-approval marker mismatch")
  }
  if (record.promotionPerformed !== false) {
    throw new Error("Human decision record must not perform promotion")
  }

  const expectedPaths = await artifactPathsForGate(input.run, input.gate)
  const artifacts = record.artifacts
  if (!Array.isArray(artifacts) || artifacts.length !== expectedPaths.length) {
    throw new Error("Human decision artifact set mismatch")
  }

  for (let index = 0; index < expectedPaths.length; index += 1) {
    const expected = await fingerprintArtifact(expectedPaths[index]!)
    const recorded = artifacts[index]
    if (
      recorded?.relativePath !== expected.relativePath ||
      recorded.sha256 !== expected.sha256 ||
      recorded.sizeBytes !== expected.sizeBytes
    ) {
      throw new Error(`Reviewed artifact fingerprint mismatch: ${expected.relativePath}`)
    }
  }
}
