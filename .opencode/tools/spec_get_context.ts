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
const TIMEOUT_MS = 2_500
const MAX_FILE_BYTES = 10 * 1024 * 1024
const MAX_CONTEXT_LINES = 160
const MAX_OUTPUT_CHARACTERS = 60_000

const ALLOWED_SOURCES = [
  "documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html",
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

async function resolveWhitelistedSource(
  worktree: string,
  source: AllowedSource,
): Promise<string> {
  if (!ALLOWED_SOURCES.includes(source)) {
    throw new Error("source path is not in the whitelist")
  }

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

  const canonicalCandidate = await realpath(candidate)

  if (canonicalCandidate !== candidate) {
    throw new Error("symbolic links are not allowed")
  }

  const metadata = await stat(canonicalCandidate)

  if (!metadata.isFile()) {
    throw new Error("whitelisted source is not a regular file")
  }

  if (metadata.size > MAX_FILE_BYTES) {
    throw new Error(
      `source exceeds the ${MAX_FILE_BYTES}-byte size limit`,
    )
  }

  return canonicalCandidate
}

function findAllLiteralOffsets(
  text: string,
  literal: string,
): number[] {
  const offsets: number[] = []
  let searchOffset = 0

  while (searchOffset < text.length) {
    const matchOffset = text.indexOf(literal, searchOffset)

    if (matchOffset === -1) {
      break
    }

    offsets.push(matchOffset)
    searchOffset = matchOffset + literal.length
  }

  return offsets
}

function lineNumberAtOffset(
  text: string,
  offset: number,
): number {
  let line = 1

  for (let index = 0; index < offset; index += 1) {
    if (text[index] === "\n") {
      line += 1
    }
  }

  return line
}

export default tool({
  description:
    "Read bounded line context around an exact HTML id anchor in a " +
    "whitelisted official specification. This tool is read-only, " +
    "performs no shell execution, and returns structured JSON.",

  args: {
    source: tool.schema
      .enum(ALLOWED_SOURCES)
      .describe("Whitelisted official HTML specification source"),

    anchor: tool.schema
      .string()
      .min(2)
      .max(200)
      .describe("Exact HTML id attribute value"),

    beforeLines: tool.schema
      .number()
      .int()
      .min(0)
      .max(80)
      .describe("Number of lines before the anchor line"),

    afterLines: tool.schema
      .number()
      .int()
      .min(0)
      .max(120)
      .describe("Number of lines after the anchor line"),
  },

  async execute(args, context) {
    try {
      if (!/^[A-Za-z0-9._:-]+$/.test(args.anchor)) {
        return jsonResult({
          ok: false,
          tool: "spec_get_context",
          version: TOOL_VERSION,
          error: {
            code: "INVALID_ANCHOR",
            message:
              "anchor may contain only letters, digits, dot, underscore, colon, and hyphen",
          },
        })
      }

      const requestedLineCount =
        args.beforeLines + args.afterLines + 1

      if (requestedLineCount > MAX_CONTEXT_LINES) {
        return jsonResult({
          ok: false,
          tool: "spec_get_context",
          version: TOOL_VERSION,
          error: {
            code: "CONTEXT_TOO_LARGE",
            message:
              `A request may return at most ${MAX_CONTEXT_LINES} lines`,
          },
        })
      }

      const sourcePath = await withTimeout(
        resolveWhitelistedSource(context.worktree, args.source),
        TIMEOUT_MS,
      )

      const data = await withTimeout(readFile(sourcePath), TIMEOUT_MS)
      const text = data.toString("utf8")

      const doubleQuoted = `id="${args.anchor}"`
      const singleQuoted = `id='${args.anchor}'`

      const offsets = [
        ...findAllLiteralOffsets(text, doubleQuoted),
        ...findAllLiteralOffsets(text, singleQuoted),
      ].sort((left, right) => left - right)

      if (offsets.length === 0) {
        return jsonResult({
          ok: false,
          tool: "spec_get_context",
          version: TOOL_VERSION,
          source: args.source,
          error: {
            code: "ANCHOR_NOT_FOUND",
            message: `No exact HTML id was found for ${args.anchor}`,
          },
        })
      }

      if (offsets.length > 1) {
        return jsonResult({
          ok: false,
          tool: "spec_get_context",
          version: TOOL_VERSION,
          source: args.source,
          error: {
            code: "ANCHOR_AMBIGUOUS",
            message:
              `The exact HTML id occurs ${offsets.length} times`,
          },
        })
      }

      const anchorOffset = offsets[0]
      const anchorLine = lineNumberAtOffset(text, anchorOffset)
      const lines = text.split(/\r?\n/)
      const totalLines = lines.length

      const actualStartLine = Math.max(
        1,
        anchorLine - args.beforeLines,
      )

      const actualEndLine = Math.min(
        totalLines,
        anchorLine + args.afterLines,
      )

      const selectedLines = lines.slice(
        actualStartLine - 1,
        actualEndLine,
      )

      const content = selectedLines
        .map((line, index) => {
          const lineNumber = actualStartLine + index
          return `${lineNumber}: ${line}`
        })
        .join("\n")

      if (content.length > MAX_OUTPUT_CHARACTERS) {
        return jsonResult({
          ok: false,
          tool: "spec_get_context",
          version: TOOL_VERSION,
          source: args.source,
          error: {
            code: "OUTPUT_TOO_LARGE",
            message:
              "Anchor context exceeds the output limit; request fewer lines",
          },
        })
      }

      return jsonResult({
        ok: true,
        tool: "spec_get_context",
        version: TOOL_VERSION,
        source: {
          relativePath: args.source,
          sha256: sha256(data),
          sizeBytes: data.length,
        },
        anchor: {
          id: args.anchor,
          occurrences: offsets.length,
          line: anchorLine,
          characterOffset: anchorOffset,
        },
        context: {
          requestedBeforeLines: args.beforeLines,
          requestedAfterLines: args.afterLines,
          actualStartLine,
          actualEndLine,
          returnedLineCount: selectedLines.length,
          totalSourceLines: totalLines,
        },
        content,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_get_context",
        version: TOOL_VERSION,
        error: {
          code: "CONTEXT_READ_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown specification-context failure",
        },
      })
    }
  },
})
