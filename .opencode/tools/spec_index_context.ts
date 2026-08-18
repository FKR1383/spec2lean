import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { readFile, realpath, stat } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"

type Section = {
  anchor: string
  startLine: number
  endLine: number
  heading: string
  searchText?: string
  page?: number
}

type Rendition = {
  kind: "html" | "pdf"
  artifact: { relativePath: string; sha256: string }
  source: { relativePath: string; sha256: string; totalLines: number }
  sections: Section[]
}

type Index = {
  schemaVersion: number
  language: string
  specificationVersion: string
  sourceManifest: { relativePath: string; sha256: string }
  renditions: Rendition[]
}

function ensureInside(root: string, candidate: string): void {
  const relation = relative(root, candidate)
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error("path escapes project root")
  }
}

function stripHtml(value: string): string {
  return value
    .replace(/<script\b[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replaceAll("&lt;", "<").replaceAll("&gt;", ">")
    .replaceAll("&quot;", "\"").replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&").replaceAll("&nbsp;", " ")
    .replace(/\s+/g, " ").trim()
}

function safeSegment(value: string, label: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(value)) throw new Error(`unsafe ${label}`)
  return value
}

function terms(query: string): string[] {
  return [...new Set(query.toLowerCase().match(/[a-z][a-z0-9_]{1,}/g) ?? [])]
}

function rank(sections: Section[], queryTerms: string[], limit: number) {
  return sections.map((section) => {
    const anchor = section.anchor.toLowerCase()
    const heading = section.heading.toLowerCase()
    const body = (section.searchText ?? section.heading).toLowerCase()
    const score = queryTerms.reduce((total, term) =>
      total + (anchor === term ? 100 : 0) + (anchor.includes(term) ? 30 : 0) +
      (heading.includes(term) ? 15 : 0) + (body.includes(term) ? 3 : 0), 0)
    return { section, score }
  }).filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.section.startLine - b.section.startLine)
    .slice(0, limit)
}

async function loadRendition(root: string, rendition: Rendition): Promise<string[]> {
  const sourcePath = resolve(root, rendition.source.relativePath)
  ensureInside(root, sourcePath)
  if (!(await stat(sourcePath)).isFile()) {
    throw new Error(`indexed ${rendition.kind} source is not a regular file`)
  }
  const data = await readFile(sourcePath)
  const hash = createHash("sha256").update(data).digest("hex")
  if (hash !== rendition.source.sha256) {
    throw new Error(`indexed ${rendition.kind} source hash mismatch; re-run ingest`)
  }
  return data.toString("utf8").split(/\r?\n/)
}

export default tool({
  description:
    "Search every deterministic, hash-verified rendition (HTML and/or PDF text) " +
    "produced during language ingestion. Use this before broad source scans. " +
    "Retrieval does not imply semantic interpretation or approval.",
  args: {
    language: tool.schema.string().min(1).max(40),
    version: tool.schema.string().min(1).max(80),
    query: tool.schema.string().min(1).max(240),
    maxSections: tool.schema.number().int().min(1).max(6).optional(),
  },
  async execute(args, context) {
    try {
      const root = await realpath(context.worktree)
      const language = safeSegment(args.language.toLowerCase(), "language")
      const version = safeSegment(args.version, "version")
      const indexPath = resolve(root, `.spec2lean-cache/${language}/${version}/source-index-v2.json`)
      ensureInside(root, indexPath)
      const index = JSON.parse(await readFile(indexPath, "utf8")) as Index
      if (
        index.schemaVersion !== 2 || index.language.toLowerCase() !== language ||
        index.specificationVersion !== args.version || !Array.isArray(index.renditions) ||
        index.renditions.length === 0
      ) throw new Error("source index identity or schema mismatch")

      const queryTerms = terms(args.query)
      if (queryTerms.length === 0) throw new Error("query contains no searchable terms")
      const maxSections = args.maxSections ?? 3
      const renditions = []
      for (const rendition of index.renditions) {
        const lines = await loadRendition(root, rendition)
        const ranked = rank(rendition.sections, queryTerms, maxSections)
        renditions.push({
          kind: rendition.kind,
          artifact: rendition.artifact,
          indexSource: rendition.source,
          matches: ranked.map(({ section, score }) => {
            const endLine = Math.min(section.endLine, section.startLine + 119)
            const selected = lines.slice(section.startLine - 1, endLine)
            const numbered = selected
              .map((line, offset) => `${section.startLine + offset}: ${line}`)
              .join("\n")
            return {
              ...section,
              endLine,
              sectionEndLine: section.endLine,
              truncated: endLine < section.endLine,
              score,
              ...(rendition.kind === "html"
                ? { rawLineNumberedHtml: numbered, renderedText: stripHtml(selected.join("\n")) }
                : { lineNumberedPdfText: numbered, renderedText: selected.join("\n").trim() }),
            }
          }),
        })
      }

      return JSON.stringify({
        ok: renditions.some((rendition) => rendition.matches.length > 0),
        tool: "spec_index_context",
        language,
        version,
        query: args.query,
        sourceManifest: index.sourceManifest,
        renditions,
        policy: {
          interpretationPerformed: false,
          humanApprovalImplied: false,
          allRenditionHashesVerified: true,
        },
      }, null, 2)
    } catch (error) {
      return JSON.stringify({
        ok: false,
        tool: "spec_index_context",
        error: {
          code: "INDEX_CONTEXT_FAILED",
          message: error instanceof Error ? error.message : String(error),
        },
      }, null, 2)
    }
  },
})
