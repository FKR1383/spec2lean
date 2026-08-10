import { createHash, randomUUID } from "node:crypto"
import {
  access,
  link,
  lstat,
  readFile,
  realpath,
  rename,
  unlink,
  writeFile,
} from "node:fs/promises"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"

import { canonicalJson } from "./semantic-ir/canonical.js"
import { sharedEnvironmentSha256 } from "./semantic-ir/document.js"
import type {
  ContentFingerprint,
  SharedSemanticEnvironment,
} from "./semantic-ir/types.js"
import { validateSharedSemanticEnvironment } from "./semantic-ir/validate.js"
import { REPO_ROOT } from "./repo.js"
import type { SemanticProfile } from "./semantic-v2.js"

export type SharedEnvironmentApprovalRecord = {
  schemaVersion: 1
  recordType: "shared_semantic_environment_decision"
  reviewId: string
  decision: "approved"
  reviewer: string
  rationale: string
  submittedAtUtc: string
  language: string
  specificationVersion: string
  environmentId: string
  revision: number
  scopeId: string
  candidate: ContentFingerprint & { canonicalSha256: string }
  humanReviewPacket: ContentFingerprint
  approvedEnvironmentPath: string
  semanticEntries: Array<{
    semanticId: string
    classification: string
    statementSha256: string
  }>
  humanConfirmationRecorded: true
  sharedEnvironmentApprovalPerformed: true
  priorUnitApprovalsReinterpretedAsSharedApproval: false
  provenance: {
    controller: "spec2lean-cli"
    command: "approve-shared"
  }
}

function sha256(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex")
}

function ensureInside(root: string, candidate: string): void {
  const relation = relative(root, candidate)
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error("path escapes its allowed root")
  }
}

function validateRelativePath(path: string): void {
  if (path.length === 0 || path.includes("\0") || path.includes("\\") || isAbsolute(path)) {
    throw new Error(`unsafe repository-relative path: ${path}`)
  }
}

async function regularRepositoryFile(
  relativePath: string,
  allowedPrefix: string,
): Promise<{ absolutePath: string; data: Buffer }> {
  validateRelativePath(relativePath)
  if (relativePath !== allowedPrefix && !relativePath.startsWith(`${allowedPrefix}/`)) {
    throw new Error(`path is outside ${allowedPrefix}: ${relativePath}`)
  }
  const root = await realpath(REPO_ROOT)
  const absolutePath = resolve(root, relativePath)
  ensureInside(resolve(root, allowedPrefix), absolutePath)
  const metadata = await lstat(absolutePath)
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    throw new Error(`path is not a regular non-symbolic file: ${relativePath}`)
  }
  const canonicalPath = await realpath(absolutePath)
  if (canonicalPath !== absolutePath) {
    throw new Error(`path may not traverse symbolic links: ${relativePath}`)
  }
  return { absolutePath, data: await readFile(absolutePath) }
}

async function verifyFingerprint(
  fingerprint: ContentFingerprint,
  allowedPrefix: string,
): Promise<void> {
  const file = await regularRepositoryFile(fingerprint.path, allowedPrefix)
  if (sha256(file.data) !== fingerprint.sha256) {
    throw new Error(`fingerprint mismatch: ${fingerprint.path}`)
  }
}

export function sharedApprovalCandidateIssues(
  profile: SemanticProfile,
  candidate: SharedSemanticEnvironment,
): string[] {
  const issues: string[] = []
  const validation = validateSharedSemanticEnvironment(candidate)
  issues.push(...validation.issues.map((issue) => `${issue.code} ${issue.path}: ${issue.message}`))
  if (candidate.language.toLowerCase() !== profile.language.toLowerCase()) {
    issues.push("candidate language does not match semantic profile")
  }
  if (candidate.specificationVersion !== profile.specificationVersion) {
    issues.push("candidate specification version does not match semantic profile")
  }
  if (candidate.review.status !== "READY_FOR_HUMAN_REVIEW") {
    issues.push("candidate environment must be READY_FOR_HUMAN_REVIEW")
  }
  if (candidate.review.records.length !== 0) {
    issues.push("unapproved candidate environment must not contain shared approval records")
  }
  const required = new Set(profile.requiredSharedSemanticIds)
  const actual = new Set(candidate.entries.map((entry) => entry.semanticId))
  for (const semanticId of required) {
    const entry = candidate.entries.find((item) => item.semanticId === semanticId)
    if (entry === undefined) {
      issues.push(`required shared semantic entry is missing: ${semanticId}`)
      continue
    }
    if (entry.classification !== profile.requiredSharedClassifications[semanticId]) {
      issues.push(`shared semantic classification mismatch: ${semanticId}`)
    }
    if (entry.review.status !== "READY_FOR_HUMAN_REVIEW") {
      issues.push(`shared semantic entry is not ready for human review: ${semanticId}`)
    }
    if (entry.lifecycle.status !== "ACTIVE") {
      issues.push(`shared semantic entry is not active: ${semanticId}`)
    }
  }
  for (const semanticId of actual) {
    if (!required.has(semanticId)) issues.push(`candidate contains an unprofiled shared semantic entry: ${semanticId}`)
  }
  if (validation.unresolvedStateAffectingSemanticIds.length > 0) {
    issues.push(`candidate has unresolved state-affecting entries: ${validation.unresolvedStateAffectingSemanticIds.join(", ")}`)
  }
  return issues
}

export async function verifySharedApprovalCandidateFiles(
  candidate: SharedSemanticEnvironment,
): Promise<void> {
  for (const manifest of candidate.sourceManifests) {
    await verifyFingerprint(manifest, "documents/sources")
  }
  for (const evidence of candidate.evidence) {
    await verifyFingerprint(
      { path: evidence.source.sourceManifestPath, sha256: evidence.source.sourceManifestSha256 },
      "documents/sources",
    )
    await verifyFingerprint(
      { path: evidence.source.documentPath, sha256: evidence.source.documentSha256 },
      "documents/sources",
    )
  }
  for (const entry of candidate.entries) {
    for (const artifact of entry.provenance.originatingArtifacts) {
      await verifyFingerprint(artifact, "accepted")
    }
    for (const review of entry.provenance.reviewRecords) {
      await verifyFingerprint(review, "reviews")
    }
    for (const support of entry.provenance.acceptedUnitSupport) {
      for (const artifact of support.artifacts) await verifyFingerprint(artifact, "accepted")
      for (const review of support.reviewRecords) await verifyFingerprint(review, "reviews")
    }
  }
}

export function buildApprovedSharedEnvironment(
  candidate: SharedSemanticEnvironment,
  approvalRecord: ContentFingerprint,
): SharedSemanticEnvironment {
  return {
    ...candidate,
    review: {
      status: "HUMAN_APPROVED",
      records: [approvalRecord],
    },
    entries: candidate.entries.map((entry) => ({
      ...entry,
      review: { ...entry.review, status: "HUMAN_APPROVED" },
      provenance: {
        ...entry.provenance,
        reviewRecords: [...entry.provenance.reviewRecords, approvalRecord],
      },
    })),
  }
}

async function writeImmutable(relativePath: string, content: Buffer): Promise<void> {
  const prefix = relativePath.startsWith("reviews/") ? "reviews" : "language_packs"
  validateRelativePath(relativePath)
  const root = await realpath(REPO_ROOT)
  const destination = resolve(root, relativePath)
  ensureInside(resolve(root, prefix), destination)
  const parent = dirname(destination)
  const canonicalParent = await realpath(parent)
  if (canonicalParent !== parent) throw new Error(`output parent may not traverse symbolic links: ${relativePath}`)
  try {
    await access(destination)
    const existing = await readFile(destination)
    if (!existing.equals(content)) throw new Error(`immutable output collision: ${relativePath}`)
    return
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
  }
  const temporary = resolve(parent, `.${randomUUID()}.shared-approval.tmp`)
  try {
    await writeFile(temporary, content, { flag: "wx", mode: 0o600 })
    await link(temporary, destination)
  } finally {
    await unlink(temporary).catch(() => undefined)
  }
}

async function writeProfileAtomically(
  profilePath: string,
  profile: SemanticProfile,
): Promise<void> {
  const file = await regularRepositoryFile(profilePath, "language_packs")
  const temporary = resolve(dirname(file.absolutePath), `.${randomUUID()}.semantic-profile.tmp`)
  try {
    await writeFile(temporary, canonicalJson(profile), { flag: "wx", mode: 0o600 })
    await rename(temporary, file.absolutePath)
  } finally {
    await unlink(temporary).catch(() => undefined)
  }
}

function validateExistingRecord(
  record: SharedEnvironmentApprovalRecord,
  expected: Omit<SharedEnvironmentApprovalRecord, "submittedAtUtc">,
): void {
  const comparable = { ...record, submittedAtUtc: undefined }
  if (canonicalJson(comparable) !== canonicalJson(expected)) {
    throw new Error("existing shared-environment approval record does not match this request")
  }
}

export async function approveSharedEnvironment(input: {
  profilePath: string
  profile: SemanticProfile
  reviewer: string
  rationale: string
}): Promise<{ approvedEnvironmentPath: string; approvalRecordPath: string }> {
  if (input.reviewer.trim().length < 2) throw new Error("reviewer must contain at least two characters")
  if (input.rationale.trim().length < 1) throw new Error("rationale must not be empty")

  const candidateFile = await regularRepositoryFile(input.profile.approval.reviewCandidatePath, "language_packs")
  const packetFile = await regularRepositoryFile(input.profile.approval.humanReviewPacketPath, "reviews")
  const candidate = JSON.parse(candidateFile.data.toString("utf8")) as SharedSemanticEnvironment
  const issues = sharedApprovalCandidateIssues(input.profile, candidate)
  if (issues.length > 0) throw new Error(`shared approval candidate is invalid:\n${issues.join("\n")}`)
  await verifySharedApprovalCandidateFiles(candidate)
  const candidateFileSha256 = sha256(candidateFile.data)
  const candidateCanonicalSha256 = sharedEnvironmentSha256(candidate)
  const packetText = packetFile.data.toString("utf8")
  if (
    !packetText.includes(candidateFileSha256) ||
    !packetText.includes(candidateCanonicalSha256) ||
    !packetText.includes("NOT HUMAN APPROVED")
  ) {
    throw new Error("human-review packet does not identify the exact unapproved candidate hashes")
  }

  const recordWithoutTimestamp: Omit<SharedEnvironmentApprovalRecord, "submittedAtUtc"> = {
    schemaVersion: 1,
    recordType: "shared_semantic_environment_decision",
    reviewId: `${candidate.environmentId}-approval-r${candidate.revision}`,
    decision: "approved",
    reviewer: input.reviewer,
    rationale: input.rationale,
    language: candidate.language,
    specificationVersion: candidate.specificationVersion,
    environmentId: candidate.environmentId,
    revision: candidate.revision,
    scopeId: candidate.scope.scopeId,
    candidate: {
      path: input.profile.approval.reviewCandidatePath,
      sha256: candidateFileSha256,
      canonicalSha256: candidateCanonicalSha256,
    },
    humanReviewPacket: {
      path: input.profile.approval.humanReviewPacketPath,
      sha256: sha256(packetFile.data),
    },
    approvedEnvironmentPath: input.profile.approval.approvedEnvironmentPath,
    semanticEntries: [...candidate.entries]
      .sort((left, right) => left.semanticId.localeCompare(right.semanticId))
      .map((entry) => ({
        semanticId: entry.semanticId,
        classification: entry.classification,
        statementSha256: sha256(entry.statement),
      })),
    humanConfirmationRecorded: true,
    sharedEnvironmentApprovalPerformed: true,
    priorUnitApprovalsReinterpretedAsSharedApproval: false,
    provenance: { controller: "spec2lean-cli", command: "approve-shared" },
  }

  let record: SharedEnvironmentApprovalRecord
  try {
    const existing = await regularRepositoryFile(input.profile.approval.approvalRecordPath, "reviews")
    record = JSON.parse(existing.data.toString("utf8")) as SharedEnvironmentApprovalRecord
    validateExistingRecord(record, recordWithoutTimestamp)
  } catch (error) {
    if (!(error instanceof Error && "code" in error && error.code === "ENOENT")) throw error
    record = { ...recordWithoutTimestamp, submittedAtUtc: new Date().toISOString() }
    await writeImmutable(
      input.profile.approval.approvalRecordPath,
      Buffer.from(canonicalJson(record), "utf8"),
    )
  }

  const recordFile = await regularRepositoryFile(input.profile.approval.approvalRecordPath, "reviews")
  const approved = buildApprovedSharedEnvironment(candidate, {
    path: input.profile.approval.approvalRecordPath,
    sha256: sha256(recordFile.data),
  })
  const approvedValidation = validateSharedSemanticEnvironment(approved)
  if (!approvedValidation.ok || approvedValidation.unresolvedStateAffectingSemanticIds.length > 0) {
    throw new Error(`derived approved environment is invalid: ${canonicalJson(approvedValidation)}`)
  }
  await writeImmutable(
    input.profile.approval.approvedEnvironmentPath,
    Buffer.from(canonicalJson(approved), "utf8"),
  )
  await writeProfileAtomically(input.profilePath, {
    ...input.profile,
    sharedEnvironmentPath: input.profile.approval.approvedEnvironmentPath,
  })
  return {
    approvedEnvironmentPath: input.profile.approval.approvedEnvironmentPath,
    approvalRecordPath: input.profile.approval.approvalRecordPath,
  }
}
