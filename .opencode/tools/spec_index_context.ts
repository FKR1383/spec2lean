import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { readFile, realpath, stat } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"

type Section = { anchor: string; startLine: number; endLine: number; heading: string; searchText?: string }
type Index = {
  schemaVersion: number
  language: string
  specificationVersion: string
  source: { relativePath: string; sha256: string; totalLines: number }
  sections: Section[]
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
    .replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&quot;", "\"")
    .replaceAll("&#39;", "'").replaceAll("&amp;", "&").replaceAll("&nbsp;", " ")
    .replace(/\s+/g, " ").trim()
}

function safeSegment(value: string, label: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(value)) throw new Error(`unsafe ${label}`)
  return value
}

function terms(query: string): string[] {
  return [...new Set(query.toLowerCase().match(/[a-z][a-z0-9_]{1,}/g) ?? [])]
}

export default tool({
  description:
    "Search the deterministic, hash-verified source index produced during language ingestion. " +
    "Use this before broad HTML/PDF scans. Retrieval does not imply semantic interpretation or approval.",
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
      const indexPath = resolve(root, `.spec2lean-cache/${language}/${version}/source-index-v1.json`)
      ensureInside(root, indexPath)
      const index = JSON.parse(await readFile(indexPath, "utf8")) as Index
      if (
        index.schemaVersion !== 1 || index.language.toLowerCase() !== language ||
        index.specificationVersion !== args.version || !Array.isArray(index.sections)
      ) throw new Error("source index identity or schema mismatch")
      const sourcePath = resolve(root, index.source.relativePath)
      ensureInside(root, sourcePath)
      if (!(await stat(sourcePath)).isFile()) throw new Error("indexed source is not a regular file")
      const data = await readFile(sourcePath)
      const hash = createHash("sha256").update(data).digest("hex")
      if (hash !== index.source.sha256) throw new Error("indexed source hash mismatch; re-run ingest")
      const lines = data.toString("utf8").split(/\r?\n/)
      const queryTerms = terms(args.query)
      if (queryTerms.length === 0) throw new Error("query contains no searchable terms")
      const ranked = index.sections.map((section) => {
        const anchor = section.anchor.toLowerCase()
        const heading = section.heading.toLowerCase()
        const body = (section.searchText ?? section.heading).toLowerCase()
        const score = queryTerms.reduce((total, term) =>
          total + (anchor === term ? 100 : 0) + (anchor.includes(term) ? 30 : 0) +
          (heading.includes(term) ? 15 : 0) + (body.includes(term) ? 3 : 0), 0)
        return { section, score }
      }).filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score || a.section.startLine - b.section.startLine)
        .slice(0, args.maxSections ?? 3)
      return JSON.stringify({
        ok: ranked.length > 0,
        tool: "spec_index_context",
        language,
        version,
        query: args.query,
        source: index.source,
        matches: ranked.map(({ section, score }) => {
          const endLine = Math.min(section.endLine, section.startLine + 119)
          const selected = lines.slice(section.startLine - 1, endLine)
          return {
            ...section,
            endLine,
            sectionEndLine: section.endLine,
            truncated: endLine < section.endLine,
            score,
            rawLineNumberedHtml: selected.map((line, offset) => `${section.startLine + offset}: ${line}`).join("\n"),
            renderedText: stripHtml(selected.join("\n")),
          }
        }),
        policy: { interpretationPerformed: false, humanApprovalImplied: false, sourceHashVerified: true },
      }, null, 2)
    } catch (error) {
      return JSON.stringify({
        ok: false,
        tool: "spec_index_context",
        error: { code: "INDEX_CONTEXT_FAILED", message: error instanceof Error ? error.message : String(error) },
      }, null, 2)
    }
  },
})
