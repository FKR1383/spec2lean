import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { readFile, realpath, stat } from "node:fs/promises"
import {
  isAbsolute,
  relative,
  resolve,
  sep,
} from "node:path"

const TOOL_VERSION = 1
const TIMEOUT_MS = 2_000
const MAX_SPAN_LINES = 120
const MAX_OUTPUT_CHARACTERS = 50_000

const ALLOWED_SOURCES = [
  "documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html",
  "documents/sources/nvidia/ptx/9.3/source-manifest.json",
  "documents/sources/nvidia/ptx/9.3/SHA256SUMS",
] as const

type AllowedSource = (typeof ALLOWED_SOURCES)[number]

function jsonResult(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

async function withTimeout<T>(
  operation: Promise<T>,
  timeoutMs: number,
): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined

  const timeoutPromise = new Promise<never>((_, reject) => {
    timeout = setTimeout(() => {
      reject(new Error(`operation exceeded ${timeoutMs} ms`))
    }, timeoutMs)
  })

  try {
    return await Promise.race([operation, timeoutPromise])
  } finally {
    if (timeout !== undefined) {
      clearTimeout(timeout)
    }
  }
}

async function resolveWhitelistedSource(
  worktree: string,
  source: AllowedSource,
): Promise<string> {
  const root = await realpath(worktree)
  const candidate = resolve(root, source)
  const relation = relative(root, candidate)

  if (
    relation === "" ||
    relation === ".." ||
    relation.startsWith(`..${sep}`) ||
    isAbsolute(relation)
  ) {
    throw new Error("source path escapes the project worktree")
  }

  if (!ALLOWED_SOURCES.includes(source)) {
    throw new Error("source path is not in the whitelist")
  }

  const canonicalCandidate = await realpath(candidate)

  if (canonicalCandidate !== candidate) {
    throw new Error("symbolic links are not allowed for specification sources")
  }

  const metadata = await stat(canonicalCandidate)

  if (!metadata.isFile()) {
    throw new Error("whitelisted source is not a regular file")
  }

  return canonicalCandidate
}

export default tool({
  description:
    "Read a bounded line span from a whitelisted official specification text source. " +
    "This tool is read-only, performs no shell execution, and returns structured JSON.",

  args: {
    source: tool.schema
      .enum(ALLOWED_SOURCES)
      .describe("Whitelisted official source file"),

    startLine: tool.schema
      .number()
      .int()
      .min(1)
      .describe("First one-based line number to read"),

    endLine: tool.schema
      .number()
      .int()
      .min(1)
      .describe("Last one-based line number to read, inclusive"),
  },

  async execute(args, context) {
    try {
      if (args.endLine < args.startLine) {
        return jsonResult({
          ok: false,
          tool: "spec_read_span",
          version: TOOL_VERSION,
          error: {
            code: "INVALID_RANGE",
            message: "endLine must be greater than or equal to startLine",
          },
        })
      }

      const requestedLineCount = args.endLine - args.startLine + 1

      if (requestedLineCount > MAX_SPAN_LINES) {
        return jsonResult({
          ok: false,
          tool: "spec_read_span",
          version: TOOL_VERSION,
          error: {
            code: "SPAN_TOO_LARGE",
            message: `A single request may read at most ${MAX_SPAN_LINES} lines`,
          },
        })
      }

      const filePath = await withTimeout(
        resolveWhitelistedSource(context.worktree, args.source),
        TIMEOUT_MS,
      )

      const data = await withTimeout(readFile(filePath), TIMEOUT_MS)
      const text = data.toString("utf8")
      const lines = text.split(/\r?\n/)
      const totalLines = lines.length

      if (args.startLine > totalLines) {
        return jsonResult({
          ok: false,
          tool: "spec_read_span",
          version: TOOL_VERSION,
          source: args.source,
          error: {
            code: "START_LINE_OUT_OF_RANGE",
            message: `startLine exceeds the file's ${totalLines} lines`,
          },
        })
      }

      const actualEndLine = Math.min(args.endLine, totalLines)
      const selectedLines = lines.slice(args.startLine - 1, actualEndLine)

      const content = selectedLines
        .map((line, index) => {
          const lineNumber = args.startLine + index
          return `${lineNumber}: ${line}`
        })
        .join("\n")

      if (content.length > MAX_OUTPUT_CHARACTERS) {
        return jsonResult({
          ok: false,
          tool: "spec_read_span",
          version: TOOL_VERSION,
          source: args.source,
          error: {
            code: "OUTPUT_TOO_LARGE",
            message:
              "The selected lines exceed the output limit; request a smaller span",
          },
        })
      }

      return jsonResult({
        ok: true,
        tool: "spec_read_span",
        version: TOOL_VERSION,
        source: {
          relativePath: args.source,
          sha256: sha256(data),
        },
        span: {
          requestedStartLine: args.startLine,
          requestedEndLine: args.endLine,
          actualStartLine: args.startLine,
          actualEndLine,
          returnedLineCount: selectedLines.length,
          totalSourceLines: totalLines,
        },
        content,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_read_span",
        version: TOOL_VERSION,
        error: {
          code: "READ_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown source-reading failure",
        },
      })
    }
  },
})
