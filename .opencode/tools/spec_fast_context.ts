import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { readFile, realpath, stat } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"

const TOOL_VERSION = 1
const VERSION = "9.3"

const INDEX_PATH =
  `.spec2lean-cache/ptx/${VERSION}/source-index-v1.json`

const SHARED_ANCHORS = [
  "predicated-execution",
  "control-flow-instructions-at",
  "register-state-space",
  "fundamental-types",
  "variables",
  "format-and-semantics-of-instruction-descriptions",
  "restricted-use-of-sub-word-sizes",
] as const

type Section = {
  anchor: string
  startLine: number
  endLine: number
  heading: string
}

type Index = {
  schemaVersion: number
  specificationVersion: string
  source: {
    relativePath: string
    sha256: string
    totalLines: number
  }
  sections: Section[]
}

type Loaded = {
  index: Index
  lines: string[]
}

let loadedPromise: Promise<Loaded> | undefined

function jsonResult(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function stripHtml(value: string): string {
  return value
    .replace(/<script\b[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", "\"")
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&")
    .replaceAll("&nbsp;", " ")
    .replace(/\s+/g, " ")
    .trim()
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

async function load(worktree: string): Promise<Loaded> {
  if (loadedPromise) return loadedPromise

  loadedPromise = (async () => {
    const root = await realpath(worktree)

    const indexPath = resolve(root, INDEX_PATH)
    ensureInside(root, indexPath)

    const index = JSON.parse(
      await readFile(indexPath, "utf8"),
    ) as Index

    if (index.specificationVersion !== VERSION) {
      throw new Error("cached PTX index has the wrong specification version")
    }

    const sourcePath = resolve(root, index.source.relativePath)
    ensureInside(root, sourcePath)

    const metadata = await stat(sourcePath)

    if (!metadata.isFile()) {
      throw new Error("indexed PTX source is not a regular file")
    }

    const sourceData = await readFile(sourcePath)
    const actualSha256 = sha256(sourceData)

    if (actualSha256 !== index.source.sha256) {
      throw new Error(
        "PTX source changed after indexing; rebuild the source index",
      )
    }

    return {
      index,
      lines: sourceData.toString("utf8").split(/\r?\n/),
    }
  })()

  return loadedPromise
}

function boundedContext(
  lines: string[],
  section: Section,
  maxLines: number,
) {
  const actualEnd =
    Math.min(section.endLine, section.startLine + maxLines - 1)

  const selected =
    lines.slice(section.startLine - 1, actualEnd)

  return {
    anchor: section.anchor,
    heading: section.heading,
    startLine: section.startLine,
    endLine: actualEnd,
    sectionEndLine: section.endLine,
    truncated: actualEnd < section.endLine,
    rawLineNumberedHtml: selected
      .map((line, index) => `${section.startLine + index}: ${line}`)
      .join("\n"),
    renderedText: stripHtml(selected.join("\n")),
  }
}

function scoreCandidate(section: Section, mnemonic: string): number {
  const anchor = section.anchor.toLowerCase()
  const heading = section.heading.toLowerCase()

  let score = 0

  if (anchor.endsWith(`-${mnemonic}`)) score += 100
  if (anchor.includes(`instructions-${mnemonic}`)) score += 50
  if (heading.includes(`instructions: ${mnemonic}`)) score += 40
  if (heading.includes(` ${mnemonic} `)) score += 10

  return score
}

export default tool({
  description:
    "Return a deterministic, hash-verified PTX 9.3 evidence context for one " +
    "instruction unit using the prebuilt local source index. This is the " +
    "preferred first retrieval tool for PTX source curation and critique.",

  args: {
    unit: tool.schema
      .string()
      .min(1)
      .max(120)
      .describe("PTX formalization unit, for example not.b32 or xor.b32"),
  },

  async execute(args, context) {
    try {
      const loaded = await load(context.worktree)

      const mnemonic =
        args.unit.trim().toLowerCase().split(".")[0]

      if (!mnemonic || !/^[a-z][a-z0-9_]*$/.test(mnemonic)) {
        throw new Error(`cannot derive PTX mnemonic from unit: ${args.unit}`)
      }

      const candidates = loaded.index.sections
        .filter((section) =>
          section.anchor.toLowerCase().endsWith(`-${mnemonic}`),
        )
        .map((section) => ({
          section,
          score: scoreCandidate(section, mnemonic),
        }))
        .sort((a, b) =>
          b.score - a.score ||
          (a.section.endLine - a.section.startLine) -
            (b.section.endLine - b.section.startLine),
        )

      if (candidates.length === 0) {
        return jsonResult({
          ok: false,
          tool: "spec_fast_context",
          version: TOOL_VERSION,
          error: {
            code: "INSTRUCTION_SECTION_NOT_FOUND",
            message:
              `No indexed PTX section ending in -${mnemonic} was found`,
          },
        })
      }

      const best = candidates[0]!

      const tied = candidates.filter(
        (candidate) => candidate.score === best.score,
      )

      if (tied.length > 1) {
        return jsonResult({
          ok: false,
          tool: "spec_fast_context",
          version: TOOL_VERSION,
          error: {
            code: "AMBIGUOUS_INSTRUCTION_SECTION",
            candidates: tied.slice(0, 8).map(({ section }) => ({
              anchor: section.anchor,
              startLine: section.startLine,
              endLine: section.endLine,
              heading: section.heading,
            })),
          },
        })
      }

      const shared = SHARED_ANCHORS.flatMap((anchor) => {
        const section =
          loaded.index.sections.find((item) => item.anchor === anchor)

        return section
          ? [boundedContext(loaded.lines, section, 48)]
          : []
      })

      return jsonResult({
        ok: true,
        tool: "spec_fast_context",
        version: TOOL_VERSION,
        source: loaded.index.source,
        unit: args.unit,
        mnemonic,
        target: boundedContext(loaded.lines, best.section, 120),
        shared,
        policy: {
          interpretationPerformed: false,
          sourceModified: false,
          sourceHashVerified: true,
        },
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_fast_context",
        version: TOOL_VERSION,
        error: {
          code: "FAST_CONTEXT_FAILED",
          message:
            error instanceof Error ? error.message : String(error),
        },
      })
    }
  },
})
