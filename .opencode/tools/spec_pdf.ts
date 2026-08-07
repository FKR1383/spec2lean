import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { spawn } from "node:child_process"
import { lstat, readFile, realpath } from "node:fs/promises"
import {
  isAbsolute,
  relative,
  resolve,
  sep,
} from "node:path"

const TOOL_VERSION = 1

const PDF_SOURCE =
  "documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.pdf"

const TIMEOUT_MS = 20_000
const MAX_OUTPUT_BYTES = 24 * 1024 * 1024
const MAX_RESULTS = 12
const MAX_QUERY_LENGTH = 160
const MAX_PAGE_SPAN = 8
const MAX_RETURN_CHARS = 80_000

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
    throw new Error("path escapes project root")
  }
}

async function resolvePdf(
  worktree: string,
): Promise<{
  path: string
  data: Buffer
}> {
  const root = await realpath(worktree)
  const candidate = resolve(root, PDF_SOURCE)

  ensureInside(root, candidate)

  const metadata = await lstat(candidate)

  if (metadata.isSymbolicLink()) {
    throw new Error("symbolic-link PDF is not allowed")
  }

  if (!metadata.isFile()) {
    throw new Error("official PDF source is not a regular file")
  }

  const canonical = await realpath(candidate)

  if (canonical !== candidate) {
    throw new Error("PDF canonical path mismatch")
  }

  const data = await readFile(canonical)

  if (!data.subarray(0, 5).equals(Buffer.from("%PDF-"))) {
    throw new Error("source does not have a valid PDF header")
  }

  return {
    path: canonical,
    data,
  }
}

type PdfTextResult = {
  stdout: string
  stderr: string
  exitCode: number | null
  timedOut: boolean
}

async function runPdftotext(
  pdfPath: string,
  args: string[],
): Promise<PdfTextResult> {
  return await new Promise((resolveResult, reject) => {
    const child = spawn(
      "pdftotext",
      [
        "-layout",
        "-enc",
        "UTF-8",
        ...args,
        pdfPath,
        "-",
      ],
      {
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
        env: {
          PATH: process.env.PATH ?? "/usr/bin:/bin",
          LANG: "C.UTF-8",
        },
      },
    )

    const stdout: Buffer[] = []
    const stderr: Buffer[] = []

    let stdoutBytes = 0
    let stderrBytes = 0
    let timedOut = false
    let finished = false

    const killForLimit = () => {
      child.kill("SIGKILL")
    }

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length

      if (stdoutBytes > MAX_OUTPUT_BYTES) {
        killForLimit()
        return
      }

      stdout.push(chunk)
    })

    child.stderr.on("data", (chunk: Buffer) => {
      stderrBytes += chunk.length

      if (stderrBytes > 1024 * 1024) {
        killForLimit()
        return
      }

      stderr.push(chunk)
    })

    child.on("error", reject)

    const timer = setTimeout(() => {
      timedOut = true
      child.kill("SIGKILL")
    }, TIMEOUT_MS)

    child.on("close", exitCode => {
      if (finished) {
        return
      }

      finished = true
      clearTimeout(timer)

      resolveResult({
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
        exitCode,
        timedOut,
      })
    })
  })
}

function pageArray(text: string): string[] {
  return text.split("\f")
}

function clean(value: string): string {
  return value
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .trim()
}

export const search = tool({
  description:
    "Search literal text inside the pinned official NVIDIA PTX ISA PDF. " +
    "Returns bounded page-numbered results. No shell is used.",

  args: {
    query: tool.schema
      .string()
      .min(2)
      .max(MAX_QUERY_LENGTH),

    maxResults: tool.schema
      .number()
      .int()
      .min(1)
      .max(MAX_RESULTS),
  },

  async execute(args, context) {
    try {
      const query = args.query.trim()

      if (query.length < 2) {
        throw new Error("query is too short")
      }

      const pdf = await resolvePdf(context.worktree)

      const extraction = await runPdftotext(
        pdf.path,
        [],
      )

      if (
        extraction.timedOut ||
        extraction.exitCode !== 0
      ) {
        throw new Error(
          `pdftotext failed: ${extraction.stderr}`,
        )
      }

      const pages = pageArray(extraction.stdout)
      const needle = query.toLocaleLowerCase("en-US")

      const matches: Array<{
        page: number
        matchIndexOnPage: number
        snippet: string
      }> = []

      let totalMatches = 0

      for (
        let pageIndex = 0;
        pageIndex < pages.length;
        pageIndex += 1
      ) {
        const page = pages[pageIndex]
        const searchable =
          page.toLocaleLowerCase("en-US")

        let offset = 0
        let matchIndexOnPage = 0

        while (offset < searchable.length) {
          const found = searchable.indexOf(
            needle,
            offset,
          )

          if (found === -1) {
            break
          }

          totalMatches += 1
          matchIndexOnPage += 1

          if (matches.length < args.maxResults) {
            const start = Math.max(0, found - 280)
            const end = Math.min(
              page.length,
              found + query.length + 280,
            )

            matches.push({
              page: pageIndex + 1,
              matchIndexOnPage,
              snippet: clean(
                page.slice(start, end),
              ),
            })
          }

          offset = found + needle.length
        }
      }

      return jsonResult({
        ok: true,
        tool: "spec_pdf_search",
        version: TOOL_VERSION,
        source: {
          relativePath: PDF_SOURCE,
          sha256: sha256(pdf.data),
          sizeBytes: pdf.data.length,
        },
        search: {
          query,
          totalMatches,
          returnedMatches: matches.length,
          truncated:
            totalMatches > matches.length,
        },
        matches,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_pdf_search",
        version: TOOL_VERSION,
        error: {
          code: "PDF_SEARCH_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown error",
        },
      })
    }
  },
})

export const read_pages = tool({
  description:
    "Read a bounded page range from the pinned official NVIDIA PTX ISA PDF. " +
    "Returns page-numbered extracted text. No shell is used.",

  args: {
    startPage: tool.schema
      .number()
      .int()
      .min(1),

    endPage: tool.schema
      .number()
      .int()
      .min(1),
  },

  async execute(args, context) {
    try {
      if (args.endPage < args.startPage) {
        throw new Error(
          "endPage must be >= startPage",
        )
      }

      if (
        args.endPage -
          args.startPage +
          1 >
        MAX_PAGE_SPAN
      ) {
        throw new Error(
          `at most ${MAX_PAGE_SPAN} pages may be read`,
        )
      }

      const pdf = await resolvePdf(context.worktree)

      const extraction = await runPdftotext(
        pdf.path,
        [
          "-f",
          String(args.startPage),
          "-l",
          String(args.endPage),
        ],
      )

      if (
        extraction.timedOut ||
        extraction.exitCode !== 0
      ) {
        throw new Error(
          `pdftotext failed: ${extraction.stderr}`,
        )
      }

      const pages = pageArray(extraction.stdout)

      const resultPages = pages
        .filter(
          (_, index) =>
            index <
            args.endPage - args.startPage + 1,
        )
        .map((text, index) => ({
          page: args.startPage + index,
          text: text.replace(/\r/g, "").trim(),
        }))

      const returnedCharacters =
        resultPages.reduce(
          (sum, page) =>
            sum + page.text.length,
          0,
        )

      if (
        returnedCharacters >
        MAX_RETURN_CHARS
      ) {
        throw new Error(
          "selected PDF pages exceed output limit",
        )
      }

      return jsonResult({
        ok: true,
        tool: "spec_pdf_read_pages",
        version: TOOL_VERSION,
        source: {
          relativePath: PDF_SOURCE,
          sha256: sha256(pdf.data),
          sizeBytes: pdf.data.length,
        },
        requestedRange: {
          startPage: args.startPage,
          endPage: args.endPage,
        },
        returnedPages: resultPages,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_pdf_read_pages",
        version: TOOL_VERSION,
        error: {
          code: "PDF_READ_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown error",
        },
      })
    }
  },
})
