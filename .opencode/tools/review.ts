import { tool } from "@opencode-ai/plugin"
import { createHash, randomUUID } from "node:crypto"
import {
  lstat,
  mkdir,
  readFile,
  realpath,
  rename,
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

const TOOL_VERSION = 1
const MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
const MAX_ARTIFACTS = 20
const HUMAN_CONFIRMATION =
  "I_CONFIRM_THIS_IS_AN_EXPLICIT_HUMAN_DECISION"

const ARTIFACT_ROOTS = ["candidates", "accepted"] as const

function jsonResult(value: unknown): string {
  return JSON.stringify(value, null, 2)
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

async function exists(path: string): Promise<boolean> {
  try {
    await lstat(path)
    return true
  } catch (error) {
    if (
      error instanceof Error &&
      "code" in error &&
      error.code === "ENOENT"
    ) {
      return false
    }

    throw error
  }
}

async function resolveArtifact(
  worktree: string,
  requestedPath: string,
): Promise<{
  relativePath: string
  sha256: string
  sizeBytes: number
}> {
  if (
    requestedPath.length === 0 ||
    requestedPath.includes("\0") ||
    requestedPath.includes("\\") ||
    isAbsolute(requestedPath)
  ) {
    throw new Error("artifact path must be a relative POSIX path")
  }

  const firstComponent = requestedPath.split("/")[0]

  if (!ARTIFACT_ROOTS.includes(
    firstComponent as (typeof ARTIFACT_ROOTS)[number],
  )) {
    throw new Error(
      "review artifacts must be under candidates/ or accepted/",
    )
  }

  const projectRoot = await realpath(worktree)
  const allowedRoot = await realpath(
    resolve(projectRoot, firstComponent),
  )

  const lexicalPath = resolve(projectRoot, requestedPath)
  ensureInside(allowedRoot, lexicalPath)

  const metadata = await lstat(lexicalPath)

  if (metadata.isSymbolicLink()) {
    throw new Error("symbolic-link artifacts are not allowed")
  }

  if (!metadata.isFile()) {
    throw new Error("review artifact is not a regular file")
  }

  if (metadata.size > MAX_ARTIFACT_BYTES) {
    throw new Error(
      `artifact exceeds the ${MAX_ARTIFACT_BYTES}-byte limit`,
    )
  }

  const canonicalPath = await realpath(lexicalPath)
  ensureInside(allowedRoot, canonicalPath)

  const data = await readFile(canonicalPath)

  return {
    relativePath: requestedPath,
    sha256: sha256(data),
    sizeBytes: data.length,
  }
}

async function resolveReviewDestination(
  worktree: string,
  recordType: "human_gate_decision" | "human_assumption_decision" | "human_theorem_strength_decision" | "tool_smoke_test",
  unitId: string,
  gate: "A" | "B" | "C" | "D" | "FINAL",
  reviewId: string,
): Promise<{
  absolutePath: string
  relativePath: string
}> {
  const projectRoot = await realpath(worktree)
  const reviewsRoot = await realpath(resolve(projectRoot, "reviews"))

  const relativePath =
    recordType === "tool_smoke_test"
      ? `reviews/tool-tests/${reviewId}.json`
      : recordType === "human_assumption_decision"
        ? `reviews/${unitId}/assumptions/${reviewId}.json`
        : recordType === "human_theorem_strength_decision"
          ? `reviews/${unitId}/theorem-strength/${reviewId}.json`
          : `reviews/${unitId}/gate-${gate.toLowerCase()}/${reviewId}.json`

  const absolutePath = resolve(projectRoot, relativePath)
  ensureInside(reviewsRoot, absolutePath)

  const parent = dirname(absolutePath)

  await mkdir(parent, {
    recursive: true,
    mode: 0o700,
  })

  let current = reviewsRoot
  const relation = relative(reviewsRoot, parent)

  if (relation !== "") {
    for (const component of relation.split(sep)) {
      current = resolve(current, component)
      const metadata = await lstat(current)

      if (metadata.isSymbolicLink()) {
        throw new Error(
          "symbolic links are not allowed in review paths",
        )
      }

      if (!metadata.isDirectory()) {
        throw new Error("review parent is not a directory")
      }
    }
  }

  return {
    absolutePath,
    relativePath,
  }
}

export const submit = tool({
  description:
    "Create an immutable structured review record under reviews/. " +
    "This tool never promotes artifacts or writes to accepted/.",

  args: {
    recordType: tool.schema.enum([
      "human_gate_decision",
      "human_assumption_decision",
      "human_theorem_strength_decision",
      "tool_smoke_test",
    ]),

    reviewId: tool.schema
      .string()
      .min(3)
      .max(80)
      .regex(/^[a-z0-9][a-z0-9._-]*$/),

    unitId: tool.schema
      .string()
      .min(3)
      .max(80)
      .regex(/^[a-z0-9][a-z0-9._-]*$/),

    gate: tool.schema.enum(["A", "B", "C", "D", "FINAL"]),

    decision: tool.schema.enum([
      "approved",
      "changes_requested",
      "rejected",
      "blocked",
    ]),

    reviewer: tool.schema.string().min(2).max(120),

    rationale: tool.schema.string().min(20).max(12_000),

    artifactPaths: tool.schema
      .array(tool.schema.string().min(1).max(300))
      .max(MAX_ARTIFACTS),

    humanConfirmation: tool.schema
      .string()
      .max(100)
      .optional(),
  },

  async execute(args, context) {
    let temporaryPath: string | undefined

    try {
      if (
        args.recordType !== "tool_smoke_test" &&
        args.humanConfirmation !== HUMAN_CONFIRMATION
      ) {
        throw new Error(
          "an explicit human confirmation phrase is required",
        )
      }

      if (
        args.recordType !== "tool_smoke_test" &&
        args.artifactPaths.length === 0
      ) {
        throw new Error(
          "a human gate decision must reference at least one artifact",
        )
      }

      const artifactPaths = [...new Set(args.artifactPaths)]

      if (artifactPaths.length !== args.artifactPaths.length) {
        throw new Error("duplicate artifact paths are not allowed")
      }

      const artifacts = await Promise.all(
        artifactPaths.map(path =>
          resolveArtifact(context.worktree, path),
        ),
      )

      const destination = await resolveReviewDestination(
        context.worktree,
        args.recordType,
        args.unitId,
        args.gate,
        args.reviewId,
      )

      if (await exists(destination.absolutePath)) {
        throw new Error(
          "review record already exists and is immutable",
        )
      }

      const record = {
        schemaVersion: 1,
        recordType: args.recordType,
        reviewId: args.reviewId,
        unitId: args.unitId,
        gate: args.gate,
        decision: args.decision,
        reviewer: args.reviewer,
        rationale: args.rationale,
        submittedAtUtc: new Date().toISOString(),
        artifacts,
        humanConfirmationRecorded:
          args.recordType !== "tool_smoke_test",
        gateApprovalPerformed:
          args.recordType === "human_gate_decision" &&
          args.decision === "approved",
        promotionPerformed: false,
        provenance: {
          agent: context.agent,
          sessionID: context.sessionID,
          messageID: context.messageID,
        },
      }

      const content = Buffer.from(
        JSON.stringify(record, null, 2) + "\n",
        "utf8",
      )

      temporaryPath = resolve(
        dirname(destination.absolutePath),
        `.${randomUUID()}.review-submit.tmp`,
      )

      await writeFile(temporaryPath, content, {
        flag: "wx",
        mode: 0o600,
      })

      await rename(temporaryPath, destination.absolutePath)
      temporaryPath = undefined

      return jsonResult({
        ok: true,
        tool: "review_submit",
        version: TOOL_VERSION,
        review: {
          relativePath: destination.relativePath,
          sha256: sha256(content),
          immutable: true,
          recordType: args.recordType,
          gate: args.gate,
          decision: args.decision,
          artifactCount: artifacts.length,
          promotionPerformed: false,
        },
      })
    } catch (error) {
      if (temporaryPath !== undefined) {
        await unlink(temporaryPath).catch(() => undefined)
      }

      return jsonResult({
        ok: false,
        tool: "review_submit",
        version: TOOL_VERSION,
        error: {
          code: "REVIEW_SUBMIT_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown review-submission failure",
        },
      })
    }
  },
})
