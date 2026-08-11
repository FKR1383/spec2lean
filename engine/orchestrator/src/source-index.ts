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
}

export type SourceIndex = {
  schemaVersion: 1
  language: string
  specificationVersion: string
  sourceManifest: { relativePath: string; sha256: string }
  sourceArtifact?: { relativePath: string; sha256: string; kind: "html" | "pdf" }
  source: { relativePath: string; sha256: string; totalLines: number }
  sections: SourceIndexSection[]
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

function htmlSections(lines: string[]): SourceIndexSection[] {
  const stack: Array<{ anchor?: string; startLine: number }> = []
  const sections: SourceIndexSection[] = []
  for (let index = 0; index < lines.length; index += 1) {
    const lineNumber = index + 1
    for (const match of lines[index]!.matchAll(/<\/?section\b[^>]*>/gi)) {
      const token = match[0]
      if (/^<\/section/i.test(token)) {
        const opened = stack.pop()
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
        stack.push({ anchor, startLine: lineNumber })
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
  return `.spec2lean-cache/${safeLanguage}/${version}/source-index-v1.json`
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
  const artifact = artifacts.find((item) => String(item.kind).toLowerCase() === "html") ??
    artifacts.find((item) => String(item.kind).toLowerCase() === "pdf")
  if (artifact === undefined || typeof artifact.local_path !== "string" || typeof artifact.sha256 !== "string") {
    return { status: "NO_INDEXABLE_SOURCE", rebuilt: false }
  }

  const sourceArtifactAbsolute = resolve(dirname(manifestAbsolute), artifact.local_path)
  const sourceArtifactRelative = safeRelative(relative(REPO_ROOT, sourceArtifactAbsolute))
  const sourceArtifactData = await readFile(sourceArtifactAbsolute)
  const actualArtifactHash = sha256(sourceArtifactData)
  if (actualArtifactHash !== artifact.sha256) throw new Error("indexed source hash does not match source manifest")
  const kind = String(artifact.kind).toLowerCase() as "html" | "pdf"
  const outputRelative = sourceIndexPath(input.language, input.specificationVersion)
  const outputAbsolute = resolve(REPO_ROOT, outputRelative)
  let sourceRelative = sourceArtifactRelative
  let sourceData = sourceArtifactData
  if (kind === "pdf") {
    sourceRelative = `${dirname(outputRelative)}/source-${actualArtifactHash}.txt`
    const extractedAbsolute = resolve(REPO_ROOT, sourceRelative)
    try {
      sourceData = await readFile(extractedAbsolute)
    } catch {
      await mkdir(dirname(extractedAbsolute), { recursive: true })
      await execFileAsync("pdftotext", ["-layout", sourceArtifactAbsolute, extractedAbsolute], {
        timeout: 120_000,
        maxBuffer: 1024 * 1024,
      })
      sourceData = await readFile(extractedAbsolute)
    }
    if (sourceData.length === 0) throw new Error("PDF text extraction produced an empty index source")
  }
  const actualSourceHash = sha256(sourceData)
  try {
    const existing = JSON.parse(await readFile(outputAbsolute, "utf8")) as SourceIndex
    if (
      existing.schemaVersion === 1 &&
      existing.language.toLowerCase() === input.language.toLowerCase() &&
      existing.specificationVersion === input.specificationVersion &&
      existing.sourceManifest.relativePath === manifestRelative &&
      existing.sourceManifest.sha256 === sha256(manifestData) &&
      existing.sourceArtifact?.relativePath === sourceArtifactRelative &&
      existing.sourceArtifact.sha256 === actualArtifactHash &&
      existing.source.relativePath === sourceRelative &&
      existing.source.sha256 === actualSourceHash &&
      existing.sections.length > 0 &&
      existing.sections.every((section) => typeof section.searchText === "string")
    ) return { path: outputRelative, status: "READY", rebuilt: false }
  } catch {
    // Missing, stale, or malformed cache is deterministically rebuilt below.
  }

  const lines = sourceData.toString("utf8").split(/\r?\n/)
  const index: SourceIndex = {
    schemaVersion: 1,
    language: input.language,
    specificationVersion: input.specificationVersion,
    sourceManifest: { relativePath: manifestRelative, sha256: sha256(manifestData) },
    sourceArtifact: { relativePath: sourceArtifactRelative, sha256: actualArtifactHash, kind },
    source: { relativePath: sourceRelative, sha256: actualSourceHash, totalLines: lines.length },
    sections: kind === "html" ? htmlSections(lines) : Array.from(
      { length: Math.ceil(lines.length / 120) },
      (_, index) => {
        const startLine = index * 120 + 1
        const endLine = Math.min(lines.length, startLine + 119)
        return {
          anchor: `pdf-chunk-${String(index + 1).padStart(6, "0")}`,
          startLine,
          endLine,
          heading: lines.slice(startLine - 1, Math.min(endLine, startLine + 12)).join(" ").replace(/\s+/g, " ").trim().slice(0, 500),
          searchText: lines.slice(startLine - 1, endLine).join(" ").replace(/\s+/g, " ").trim().slice(0, 12_000),
        }
      },
    ),
  }
  await mkdir(dirname(outputAbsolute), { recursive: true })
  await writeFile(outputAbsolute, `${JSON.stringify(index, null, 2)}\n`, "utf8")
  return { path: outputRelative, status: "READY", rebuilt: true }
}
