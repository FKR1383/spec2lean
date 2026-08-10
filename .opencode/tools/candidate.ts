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
  extname,
  isAbsolute,
  normalize,
  relative,
  resolve,
  sep,
} from "node:path"

const TOOL_VERSION = 1
const TIMEOUT_MS = 3_000

const MAX_READ_BYTES = 1024 * 1024
const MAX_WRITE_BYTES = 512 * 1024
const MAX_READ_LINES = 200
const MAX_OUTPUT_CHARACTERS = 80_000
const MAX_DIFF_LINES = 1_000
const MAX_DIFF_CHANGES = 400

const WRITABLE_ROOT = "candidates"
const DIFF_ROOTS = ["candidates", "accepted"] as const

const ALLOWED_EXTENSIONS = new Set([
  ".json",
  ".jsonl",
  ".md",
  ".yaml",
  ".yml",
  ".lean",
  ".txt",
  ".toml",
])

function jsonResult(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

async function withTimeout<T>(
  operation: Promise<T>,
  timeoutMs = TIMEOUT_MS,
): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined

  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      reject(new Error(`operation exceeded ${timeoutMs} ms`))
    }, timeoutMs)
  })

  try {
    return await Promise.race([operation, timeout])
  } finally {
    if (timer !== undefined) {
      clearTimeout(timer)
    }
  }
}

function normalizeProjectPath(path: string): string {
  if (
    path.length === 0 ||
    path.includes("\0") ||
    path.includes("\\") ||
    isAbsolute(path)
  ) {
    throw new Error("path must be a non-empty relative POSIX path")
  }

  const normalized = normalize(path)

  if (
    normalized === "." ||
    normalized === ".." ||
    normalized.startsWith(`..${sep}`)
  ) {
    throw new Error("path escapes the project worktree")
  }

  const extension = extname(normalized).toLowerCase()

  if (!ALLOWED_EXTENSIONS.has(extension)) {
    throw new Error(`unsupported artifact extension: ${extension || "(none)"}`)
  }

  return normalized
}

function ensureInsideRoot(root: string, candidate: string): void {
  const relation = relative(root, candidate)

  if (
    relation === ".." ||
    relation.startsWith(`..${sep}`) ||
    isAbsolute(relation)
  ) {
    throw new Error("artifact path escapes its allowed root")
  }
}

async function resolveExistingArtifact(
  worktree: string,
  path: string,
  allowedRoots: readonly string[],
): Promise<{ absolutePath: string; relativePath: string }> {
  const relativePath = normalizeProjectPath(path)
  const firstComponent = relativePath.split(sep)[0]

  if (!allowedRoots.includes(firstComponent)) {
    throw new Error(
      `artifact must be under one of: ${allowedRoots.join(", ")}`,
    )
  }

  const projectRoot = await realpath(worktree)
  const allowedRoot = await realpath(resolve(projectRoot, firstComponent))
  const lexicalPath = resolve(projectRoot, relativePath)

  ensureInsideRoot(allowedRoot, lexicalPath)

  const metadata = await lstat(lexicalPath)

  if (metadata.isSymbolicLink()) {
    throw new Error("symbolic-link artifacts are not allowed")
  }

  if (!metadata.isFile()) {
    throw new Error("artifact is not a regular file")
  }

  const canonicalPath = await realpath(lexicalPath)
  ensureInsideRoot(allowedRoot, canonicalPath)

  return {
    absolutePath: canonicalPath,
    relativePath,
  }
}

async function pathExists(path: string): Promise<boolean> {
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

async function ensureNoSymlinkAncestors(
  root: string,
  targetDirectory: string,
): Promise<void> {
  ensureInsideRoot(root, targetDirectory)

  const relation = relative(root, targetDirectory)

  if (relation === "") {
    return
  }

  let current = root

  for (const component of relation.split(sep)) {
    current = resolve(current, component)

    const metadata = await lstat(current)

    if (metadata.isSymbolicLink()) {
      throw new Error("symbolic links are not allowed in artifact paths")
    }

    if (!metadata.isDirectory()) {
      throw new Error("artifact parent is not a directory")
    }
  }
}

async function resolveWritableArtifact(
  worktree: string,
  path: string,
): Promise<{ absolutePath: string; relativePath: string }> {
  const relativePath = normalizeProjectPath(path)

  if (
    relativePath !== WRITABLE_ROOT &&
    !relativePath.startsWith(`${WRITABLE_ROOT}${sep}`)
  ) {
    throw new Error("candidate_write may write only under candidates/")
  }

  const projectRoot = await realpath(worktree)
  const candidatesRoot = resolve(projectRoot, WRITABLE_ROOT)

  const rootMetadata = await lstat(candidatesRoot)

  if (rootMetadata.isSymbolicLink() || !rootMetadata.isDirectory()) {
    throw new Error("candidates/ must be a real directory")
  }

  const absolutePath = resolve(projectRoot, relativePath)
  ensureInsideRoot(candidatesRoot, absolutePath)

  const parent = dirname(absolutePath)

  await mkdir(parent, {
    recursive: true,
    mode: 0o700,
  })

  await ensureNoSymlinkAncestors(candidatesRoot, parent)

  return {
    absolutePath,
    relativePath,
  }
}

async function readBoundedFile(
  absolutePath: string,
  maxBytes = MAX_READ_BYTES,
): Promise<Buffer> {
  const data = await withTimeout(readFile(absolutePath))

  if (data.length > maxBytes) {
    throw new Error(`artifact exceeds the ${maxBytes}-byte limit`)
  }

  return data
}

function buildLineDiff(
  oldLines: string[],
  newLines: string[],
  maxChanges: number,
) {
  if (
    oldLines.length > MAX_DIFF_LINES ||
    newLines.length > MAX_DIFF_LINES
  ) {
    throw new Error(
      `candidate_diff supports at most ${MAX_DIFF_LINES} lines per file`,
    )
  }

  const rowCount = oldLines.length + 1
  const columnCount = newLines.length + 1
  const table = new Uint32Array(rowCount * columnCount)

  for (let oldIndex = oldLines.length - 1; oldIndex >= 0; oldIndex -= 1) {
    for (
      let newIndex = newLines.length - 1;
      newIndex >= 0;
      newIndex -= 1
    ) {
      const index = oldIndex * columnCount + newIndex

      if (oldLines[oldIndex] === newLines[newIndex]) {
        table[index] =
          table[(oldIndex + 1) * columnCount + newIndex + 1] + 1
      } else {
        table[index] = Math.max(
          table[(oldIndex + 1) * columnCount + newIndex],
          table[oldIndex * columnCount + newIndex + 1],
        )
      }
    }
  }

  const changes: Array<{
    kind: "delete" | "insert"
    oldLine: number | null
    newLine: number | null
    text: string
  }> = []

  let totalChanges = 0
  let oldIndex = 0
  let newIndex = 0

  while (oldIndex < oldLines.length || newIndex < newLines.length) {
    if (
      oldIndex < oldLines.length &&
      newIndex < newLines.length &&
      oldLines[oldIndex] === newLines[newIndex]
    ) {
      oldIndex += 1
      newIndex += 1
      continue
    }

    const deleteScore =
      oldIndex < oldLines.length
        ? table[(oldIndex + 1) * columnCount + newIndex]
        : -1

    const insertScore =
      newIndex < newLines.length
        ? table[oldIndex * columnCount + newIndex + 1]
        : -1

    totalChanges += 1

    if (
      oldIndex < oldLines.length &&
      (newIndex >= newLines.length || deleteScore >= insertScore)
    ) {
      if (changes.length < maxChanges) {
        changes.push({
          kind: "delete",
          oldLine: oldIndex + 1,
          newLine: null,
          text: oldLines[oldIndex],
        })
      }

      oldIndex += 1
    } else {
      if (changes.length < maxChanges) {
        changes.push({
          kind: "insert",
          oldLine: null,
          newLine: newIndex + 1,
          text: newLines[newIndex],
        })
      }

      newIndex += 1
    }
  }

  return {
    totalChanges,
    returnedChanges: changes.length,
    truncated: totalChanges > changes.length,
    changes,
  }
}

export const read = tool({
  description:
    "Read a bounded line span from a text artifact under candidates/. " +
    "The tool is read-only and returns structured JSON.",

  args: {
    path: tool.schema
      .string()
      .min(1)
      .max(300)
      .describe("Artifact path under candidates/"),

    startLine: tool.schema.number().int().min(1),

    endLine: tool.schema.number().int().min(1),
  },

  async execute(args, context) {
    try {
      if (args.endLine < args.startLine) {
        throw new Error("endLine must be greater than or equal to startLine")
      }

      if (args.endLine - args.startLine + 1 > MAX_READ_LINES) {
        throw new Error(`at most ${MAX_READ_LINES} lines may be read`)
      }

      const artifact = await resolveExistingArtifact(
        context.worktree,
        args.path,
        [WRITABLE_ROOT],
      )

      const data = await readBoundedFile(artifact.absolutePath)
      const lines = data.toString("utf8").split(/\r?\n/)

      if (args.startLine > lines.length) {
        throw new Error(
          `startLine exceeds the artifact's ${lines.length} lines`,
        )
      }

      const actualEndLine = Math.min(args.endLine, lines.length)
      const selected = lines.slice(args.startLine - 1, actualEndLine)

      const content = selected
        .map((line, index) => `${args.startLine + index}: ${line}`)
        .join("\n")

      if (content.length > MAX_OUTPUT_CHARACTERS) {
        throw new Error("selected output exceeds the character limit")
      }

      return jsonResult({
        ok: true,
        tool: "candidate_read",
        version: TOOL_VERSION,
        artifact: {
          relativePath: artifact.relativePath,
          sha256: sha256(data),
          sizeBytes: data.length,
        },
        span: {
          requestedStartLine: args.startLine,
          requestedEndLine: args.endLine,
          actualStartLine: args.startLine,
          actualEndLine,
          returnedLineCount: selected.length,
          totalLines: lines.length,
        },
        content,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "candidate_read",
        version: TOOL_VERSION,
        error: {
          code: "CANDIDATE_READ_FAILED",
          message: error instanceof Error ? error.message : "unknown error",
        },
      })
    }
  },
})

export const write = tool({
  description:
    "Atomically create or replace a bounded text artifact under candidates/. " +
    "Replacement requires the expected current SHA-256 value.",

  args: {
    path: tool.schema
      .string()
      .min(1)
      .max(300)
      .describe("Destination path under candidates/"),

    content: tool.schema
      .string()
      .max(MAX_WRITE_BYTES)
      .describe("Complete UTF-8 artifact content"),

    mode: tool.schema
      .enum(["create", "replace"])
      .describe("Create a new file or replace an existing version"),

    expectedSha256: tool.schema
      .string()
      .regex(/^[a-f0-9]{64}$/)
      .optional()
      .describe("Required current SHA-256 when mode is replace"),
  },

  async execute(args, context) {
    let temporaryPath: string | undefined

    try {
      const artifact = await resolveWritableArtifact(
        context.worktree,
        args.path,
      )

      const content = Buffer.from(args.content, "utf8")

      if (content.length > MAX_WRITE_BYTES) {
        throw new Error(
          `content exceeds the ${MAX_WRITE_BYTES}-byte limit`,
        )
      }

      if (extname(artifact.relativePath).toLowerCase() === ".json") {
        try {
          JSON.parse(args.content)
        } catch (error) {
          throw new Error(
            `invalid JSON; artifact was not written: ${error instanceof Error ? error.message : String(error)}`,
          )
        }
      }

      const exists = await pathExists(artifact.absolutePath)

      if (args.mode === "create" && exists) {
        throw new Error("artifact already exists; use replace with its hash")
      }

      if (args.mode === "replace") {
        if (!exists) {
          throw new Error("artifact does not exist")
        }

        if (!args.expectedSha256) {
          throw new Error(
            "expectedSha256 is required when mode is replace",
          )
        }

        const metadata = await lstat(artifact.absolutePath)

        if (metadata.isSymbolicLink() || !metadata.isFile()) {
          throw new Error("existing destination is not a regular file")
        }

        const current = await readBoundedFile(artifact.absolutePath)

        if (sha256(current) !== args.expectedSha256) {
          throw new Error(
            "current artifact SHA-256 does not match expectedSha256",
          )
        }
      }

      temporaryPath = resolve(
        dirname(artifact.absolutePath),
        `.${randomUUID()}.candidate-write.tmp`,
      )

      await withTimeout(
        writeFile(temporaryPath, content, {
          flag: "wx",
          mode: 0o600,
        }),
      )

      await withTimeout(rename(temporaryPath, artifact.absolutePath))
      temporaryPath = undefined

      return jsonResult({
        ok: true,
        tool: "candidate_write",
        version: TOOL_VERSION,
        mode: args.mode,
        artifact: {
          relativePath: artifact.relativePath,
          sha256: sha256(content),
          sizeBytes: content.length,
        },
        provenance: {
          agent: context.agent,
          sessionID: context.sessionID,
          messageID: context.messageID,
        },
      })
    } catch (error) {
      if (temporaryPath !== undefined) {
        await unlink(temporaryPath).catch(() => undefined)
      }

      return jsonResult({
        ok: false,
        tool: "candidate_write",
        version: TOOL_VERSION,
        error: {
          code: "CANDIDATE_WRITE_FAILED",
          message: error instanceof Error ? error.message : "unknown error",
        },
      })
    }
  },
})

export const diff = tool({
  description:
    "Compare two bounded text artifacts under candidates/ or accepted/. " +
    "The tool is read-only and returns structured line changes.",

  args: {
    oldPath: tool.schema.string().min(1).max(300),
    newPath: tool.schema.string().min(1).max(300),

    maxChanges: tool.schema
      .number()
      .int()
      .min(1)
      .max(MAX_DIFF_CHANGES)
      .describe("Maximum number of individual changes to return"),
  },

  async execute(args, context) {
    try {
      const oldArtifact = await resolveExistingArtifact(
        context.worktree,
        args.oldPath,
        DIFF_ROOTS,
      )

      const newArtifact = await resolveExistingArtifact(
        context.worktree,
        args.newPath,
        DIFF_ROOTS,
      )

      const [oldData, newData] = await Promise.all([
        readBoundedFile(oldArtifact.absolutePath),
        readBoundedFile(newArtifact.absolutePath),
      ])

      const oldLines = oldData.toString("utf8").split(/\r?\n/)
      const newLines = newData.toString("utf8").split(/\r?\n/)

      const result = buildLineDiff(
        oldLines,
        newLines,
        args.maxChanges,
      )

      return jsonResult({
        ok: true,
        tool: "candidate_diff",
        version: TOOL_VERSION,
        oldArtifact: {
          relativePath: oldArtifact.relativePath,
          sha256: sha256(oldData),
          lineCount: oldLines.length,
        },
        newArtifact: {
          relativePath: newArtifact.relativePath,
          sha256: sha256(newData),
          lineCount: newLines.length,
        },
        summary: {
          identical: oldData.equals(newData),
          ...result,
        },
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "candidate_diff",
        version: TOOL_VERSION,
        error: {
          code: "CANDIDATE_DIFF_FAILED",
          message: error instanceof Error ? error.message : "unknown error",
        },
      })
    }
  },
})
