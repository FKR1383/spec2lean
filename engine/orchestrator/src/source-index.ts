import { createHash } from "node:crypto"
import { execFile } from "node:child_process"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"
import { promisify } from "node:util"

import { REPO_ROOT } from "./repo.js"
import { verifySourceManifest } from "./source-manifest.js"

type UnknownRecord = Record<string, unknown>

export type SourceIndexSection = {
  anchor: string
  startLine: number
  endLine: number
  heading: string
  searchText: string
  page?: number
}

export type SourceIndexRendition = {
  kind: "html" | "pdf"
  artifact: { relativePath: string; sha256: string }
  source: { relativePath: string; sha256: string; totalLines: number }
  sections: SourceIndexSection[]
}

export type SourceIndex = {
  schemaVersion: 2
  language: string
  specificationVersion: string
  sourceManifest: { relativePath: string; sha256: string }
  sourceArtifact: { relativePath: string; sha256: string; kind: "html" | "pdf" }
  source: { relativePath: string; sha256: string; totalLines: number }
  sections: SourceIndexSection[]
  renditions: SourceIndexRendition[]
}

const execFileAsync = promisify(execFile)

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function safeRelative(path: string): string {
  if (!path || path.includes("\0") || path.includes("\\") || isAbsolute(path)) {
    throw new Error(`unsafe repository-relative path: ${path}`)
  }
  const relation = relative(REPO_ROOT, resolve(REPO_ROOT, path))
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`path escapes repository: ${path}`)
  }
  return relation.split(sep).join("/")
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

export function htmlSections(lines: string[]): SourceIndexSection[] {
  const stack: Array<{ tag: string; anchor?: string; startLine: number }> = []
  const sections: SourceIndexSection[] = []
  for (let index = 0; index < lines.length; index += 1) {
    const lineNumber = index + 1
    for (const match of lines[index]!.matchAll(/<\/?(?:section|article|emu-clause)\b[^>]*>/gi)) {
      const token = match[0]
      const tag = token.match(/^<\/?([A-Za-z-]+)/)?.[1]?.toLowerCase()
      if (tag === undefined) continue
      if (/^<\//i.test(token)) {
        let position = -1
        for (let candidate = stack.length - 1; candidate >= 0; candidate -= 1) {
          if (stack[candidate]!.tag === tag) {
            position = candidate
            break
          }
        }
        const opened = position < 0 ? undefined : stack.splice(position, 1)[0]
        if (opened?.anchor !== undefined) {
          const preview = lines.slice(opened.startLine - 1, Math.min(lineNumber, opened.startLine + 12)).join("\n")
          sections.push({
            anchor: opened.anchor,
            startLine: opened.startLine,
            endLine: lineNumber,
            heading: stripHtml(preview).slice(0, 500),
            searchText: stripHtml(lines.slice(opened.startLine - 1, Math.min(lineNumber, opened.startLine + 119)).join("\n")).slice(0, 12_000),
          })
        }
      } else {
        const anchor = token.match(/\bid\s*=\s*["']([^"']+)["']/i)?.[1]
        stack.push({ tag, anchor, startLine: lineNumber })
      }
    }
  }
  if (sections.length > 0) return sections.sort((a, b) => a.startLine - b.startLine)

  // HTML without section elements still gets deterministic bounded chunks.
  const chunkLines = 120
  return Array.from({ length: Math.ceil(lines.length / chunkLines) }, (_, index) => {
    const startLine = index * chunkLines + 1
    const endLine = Math.min(lines.length, startLine + chunkLines - 1)
    return {
      anchor: `chunk-${String(index + 1).padStart(6, "0")}`,
      startLine,
      endLine,
      heading: stripHtml(lines.slice(startLine - 1, Math.min(endLine, startLine + 12)).join("\n")).slice(0, 500),
      searchText: stripHtml(lines.slice(startLine - 1, endLine).join("\n")).slice(0, 12_000),
    }
  })
}

export function sourceIndexPath(language: string, version: string): string {
  const safeLanguage = language.trim().toLowerCase()
  if (!/^[a-z][a-z0-9_-]*$/.test(safeLanguage) || !/^[A-Za-z0-9._-]+$/.test(version)) {
    throw new Error("language/version is unsafe for a source-index path")
  }
  return `.spec2lean-cache/${safeLanguage}/${version}/source-index-v2.json`
}

function pdfSections(source: string): SourceIndexSection[] {
  const sections: SourceIndexSection[] = []
  let startLine = 1
  for (const [index, pageSource] of source.split("\f").entries()) {
    const pageLines = pageSource.split(/\r?\n/)
    const endLine = Math.max(startLine, startLine + pageLines.length - 1)
    const rendered = pageLines.join(" ").replace(/\s+/g, " ").trim()
    if (rendered.length > 0) {
      sections.push({
        anchor: `pdf-page-${String(index + 1).padStart(6, "0")}`,
        startLine,
        endLine,
        heading: rendered.slice(0, 500),
        searchText: rendered.slice(0, 12_000),
        page: index + 1,
      })
    }
    startLine = endLine + 1
  }
  return sections
}

async function buildRendition(input: {
  artifact: UnknownRecord
  manifestAbsolute: string
  outputRelative: string
}): Promise<SourceIndexRendition> {
  const kind = String(input.artifact.kind).toLowerCase() as "html" | "pdf"
  if (!["html", "pdf"].includes(kind) ||
      typeof input.artifact.local_path !== "string" ||
      typeof input.artifact.sha256 !== "string") {
    throw new Error("source manifest contains an invalid indexable artifact")
  }
  const artifactAbsolute = resolve(dirname(input.manifestAbsolute), input.artifact.local_path)
  const artifactRelative = safeRelative(relative(REPO_ROOT, artifactAbsolute))
  const artifactData = await readFile(artifactAbsolute)
  const artifactSha256 = sha256(artifactData)
  if (artifactSha256 !== input.artifact.sha256) {
    throw new Error(`indexed ${kind} hash does not match source manifest`)
  }

  let sourceRelative = artifactRelative
  let sourceData = artifactData
  if (kind === "pdf") {
    sourceRelative = `${dirname(input.outputRelative)}/source-${artifactSha256}.txt`
    const extractedAbsolute = resolve(REPO_ROOT, sourceRelative)
    try {
      sourceData = await readFile(extractedAbsolute)
    } catch {
      await mkdir(dirname(extractedAbsolute), { recursive: true })
      await execFileAsync("pdftotext", ["-layout", artifactAbsolute, extractedAbsolute], {
        timeout: 120_000,
        maxBuffer: 1024 * 1024,
      })
      sourceData = await readFile(extractedAbsolute)
    }
    if (sourceData.length === 0) throw new Error("PDF text extraction produced an empty index source")
  }

  const sourceText = sourceData.toString("utf8")
  const lines = sourceText.split(/\r?\n/)
  return {
    kind,
    artifact: { relativePath: artifactRelative, sha256: artifactSha256 },
    source: { relativePath: sourceRelative, sha256: sha256(sourceData), totalLines: lines.length },
    sections: kind === "html" ? htmlSections(lines) : pdfSections(sourceText),
  }
}

export async function ensureSourceIndex(input: {
  language: string
  specificationVersion: string
  sourceManifest: string
}): Promise<{ path?: string; status: "READY" | "NO_INDEXABLE_SOURCE"; rebuilt: boolean }> {
  const manifestRelative = safeRelative(input.sourceManifest)
  const manifestAbsolute = resolve(REPO_ROOT, manifestRelative)
  await verifySourceManifest(manifestAbsolute)
  const manifestData = await readFile(manifestAbsolute)
  const manifest = JSON.parse(manifestData.toString("utf8")) as UnknownRecord
  const artifacts = Array.isArray(manifest.artifacts) ? manifest.artifacts.filter(isRecord) : []
  const indexable = artifacts.filter((item) => ["html", "pdf"].includes(String(item.kind).toLowerCase()))
  if (indexable.length === 0) {
    return { status: "NO_INDEXABLE_SOURCE", rebuilt: false }
  }
  const outputRelative = sourceIndexPath(input.language, input.specificationVersion)
  const outputAbsolute = resolve(REPO_ROOT, outputRelative)
  const renditions = await Promise.all(indexable.map(async (artifact) =>
    await buildRendition({ artifact, manifestAbsolute, outputRelative })))
  const primary = renditions.find((item) => item.kind === "html") ?? renditions[0]!
  try {
    const existing = JSON.parse(await readFile(outputAbsolute, "utf8")) as SourceIndex
    if (
      existing.schemaVersion === 2 &&
      existing.language.toLowerCase() === input.language.toLowerCase() &&
      existing.specificationVersion === input.specificationVersion &&
      existing.sourceManifest.relativePath === manifestRelative &&
      existing.sourceManifest.sha256 === sha256(manifestData) &&
      existing.sourceArtifact.relativePath === primary.artifact.relativePath &&
      existing.sourceArtifact.sha256 === primary.artifact.sha256 &&
      existing.source.relativePath === primary.source.relativePath &&
      existing.source.sha256 === primary.source.sha256 &&
      existing.renditions.length === renditions.length &&
      existing.renditions.every((item, index) =>
        item.kind === renditions[index]?.kind &&
        item.artifact.relativePath === renditions[index]?.artifact.relativePath &&
        item.artifact.sha256 === renditions[index]?.artifact.sha256 &&
        item.source.relativePath === renditions[index]?.source.relativePath &&
        item.source.sha256 === renditions[index]?.source.sha256 &&
        item.sections.length > 0) &&
      existing.sections.length > 0 &&
      existing.sections.every((section) => typeof section.searchText === "string")
    ) return { path: outputRelative, status: "READY", rebuilt: false }
  } catch {
    // Missing, stale, or malformed cache is deterministically rebuilt below.
  }

  const index: SourceIndex = {
    schemaVersion: 2,
    language: input.language,
    specificationVersion: input.specificationVersion,
    sourceManifest: { relativePath: manifestRelative, sha256: sha256(manifestData) },
    sourceArtifact: { ...primary.artifact, kind: primary.kind },
    source: primary.source,
    sections: primary.sections,
    renditions,
  }
  await mkdir(dirname(outputAbsolute), { recursive: true })
  await writeFile(outputAbsolute, `${JSON.stringify(index, null, 2)}\n`, "utf8")
  return { path: outputRelative, status: "READY", rebuilt: true }
}
