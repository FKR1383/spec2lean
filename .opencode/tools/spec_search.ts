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
const MAX_QUERY_CHARACTERS = 160
const MAX_RESULTS = 12
const SNIPPET_RADIUS = 240

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

function decodeBasicHtmlEntities(value: string): string {
  return value
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", "\"")
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&")
    .replaceAll("&nbsp;", " ")
}

function cleanSnippet(value: string): string {
  return decodeBasicHtmlEntities(value)
    .replace(/\s+/g, " ")
    .trim()
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

function buildLineStarts(text: string): number[] {
  const starts = [0]

  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "\n") {
      starts.push(index + 1)
    }
  }

  return starts
}

function locateLine(
  lineStarts: number[],
  offset: number,
): { line: number; column: number } {
  let low = 0
  let high = lineStarts.length - 1

  while (low <= high) {
    const middle = Math.floor((low + high) / 2)

    if (lineStarts[middle] <= offset) {
      low = middle + 1
    } else {
      high = middle - 1
    }
  }

  const lineIndex = Math.max(0, high)

  return {
    line: lineIndex + 1,
    column: offset - lineStarts[lineIndex] + 1,
  }
}

export default tool({
  description:
    "Search for a literal text string in a whitelisted official specification source. " +
    "The tool is read-only, performs no shell execution, and returns bounded structured JSON.",

  args: {
    source: tool.schema
      .enum(ALLOWED_SOURCES)
      .describe("Whitelisted official specification source"),

    query: tool.schema
      .string()
      .min(2)
      .max(MAX_QUERY_CHARACTERS)
      .describe("Literal case-insensitive text to search for"),

    maxResults: tool.schema
      .number()
      .int()
      .min(1)
      .max(MAX_RESULTS)
      .describe(`Maximum number of matches to return, up to ${MAX_RESULTS}`),
  },

  async execute(args, context) {
    const startedAt = Date.now()

    try {
      const query = args.query.trim()

      if (query.length < 2) {
        return jsonResult({
          ok: false,
          tool: "spec_search",
          version: TOOL_VERSION,
          error: {
            code: "QUERY_TOO_SHORT",
            message: "query must contain at least two non-space characters",
          },
        })
      }

      const sourcePath = await withTimeout(
        resolveWhitelistedSource(context.worktree, args.source),
        TIMEOUT_MS,
      )

      const data = await withTimeout(readFile(sourcePath), TIMEOUT_MS)
      const text = data.toString("utf8")
      const searchableText = text.toLocaleLowerCase("en-US")
      const searchableQuery = query.toLocaleLowerCase("en-US")
      const lineStarts = buildLineStarts(text)

      const matches: Array<{
        matchNumber: number
        byteOffset: number
        line: number
        column: number
        snippet: string
      }> = []

      let totalMatches = 0
      let searchOffset = 0

      while (searchOffset < searchableText.length) {
        if (Date.now() - startedAt > TIMEOUT_MS) {
          throw new Error(`operation exceeded ${TIMEOUT_MS} ms`)
        }

        const matchOffset = searchableText.indexOf(
          searchableQuery,
          searchOffset,
        )

        if (matchOffset === -1) {
          break
        }

        totalMatches += 1

        if (matches.length < args.maxResults) {
          const location = locateLine(lineStarts, matchOffset)
          const snippetStart = Math.max(
            0,
            matchOffset - SNIPPET_RADIUS,
          )
          const snippetEnd = Math.min(
            text.length,
            matchOffset + query.length + SNIPPET_RADIUS,
          )

          matches.push({
            matchNumber: totalMatches,
            byteOffset: Buffer.byteLength(
              text.slice(0, matchOffset),
              "utf8",
            ),
            line: location.line,
            column: location.column,
            snippet: cleanSnippet(
              text.slice(snippetStart, snippetEnd),
            ),
          })
        }

        searchOffset = matchOffset + Math.max(searchableQuery.length, 1)
      }

      return jsonResult({
        ok: true,
        tool: "spec_search",
        version: TOOL_VERSION,
        source: {
          relativePath: args.source,
          sha256: sha256(data),
          sizeBytes: data.length,
        },
        search: {
          query,
          caseSensitive: false,
          totalMatches,
          returnedMatches: matches.length,
          truncated: totalMatches > matches.length,
        },
        matches,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_search",
        version: TOOL_VERSION,
        error: {
          code: "SEARCH_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown specification-search failure",
        },
      })
    }
  },
})
