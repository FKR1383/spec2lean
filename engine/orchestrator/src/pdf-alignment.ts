import { execFile } from "node:child_process"
import { createHash } from "node:crypto"
import { mkdir, readFile } from "node:fs/promises"
import { dirname, relative, resolve, sep } from "node:path"
import { promisify } from "node:util"

import { REPO_ROOT } from "./repo.js"
import type { TraceabilityEvidence } from "./traceability.js"

const execFileAsync = promisify(execFile)

type PdfWord = {
  text: string
  xMin: number
  yMin: number
  xMax: number
  yMax: number
}

type PdfPage = {
  page: number
  width: number
  height: number
  words: PdfWord[]
}

export type PdfAlignmentMetrics = {
  matched: number
  ambiguous: string[]
  unmatched: string[]
}

function decodeXml(value: string): string {
  return value
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&#x([0-9a-f]+);/gi, (_whole, digits: string) => String.fromCodePoint(Number.parseInt(digits, 16)))
    .replace(/&#([0-9]+);/g, (_whole, digits: string) => String.fromCodePoint(Number.parseInt(digits, 10)))
}

function tokenize(value: string): string[] {
  return (decodeXml(value)
    .normalize("NFKC")
    .replace(/[“”]/g, "\"")
    .replace(/[‘’]/g, "'")
    .match(/[A-Za-z0-9_.%@$!]+|[=|&^~+*/{},;()[\]:<>-]/g) ?? [])
    .map((token) => token.toLowerCase())
}

function attribute(source: string, name: string): number | undefined {
  const match = source.match(new RegExp(`${name}="([0-9.]+)"`))
  const value = match?.[1] === undefined ? undefined : Number(match[1])
  return value !== undefined && Number.isFinite(value) ? value : undefined
}

export function parsePdfBboxDocument(source: string): PdfPage[] {
  const pages: PdfPage[] = []
  const pagePattern = /<page\b([^>]*)>([\s\S]*?)<\/page>/g
  let pageMatch: RegExpExecArray | null
  while ((pageMatch = pagePattern.exec(source)) !== null) {
    const attributes = pageMatch[1] ?? ""
    const body = pageMatch[2] ?? ""
    const width = attribute(attributes, "width")
    const height = attribute(attributes, "height")
    if (width === undefined || height === undefined || width <= 0 || height <= 0) continue
    const words: PdfWord[] = []
    const wordPattern = /<word\b([^>]*)>([\s\S]*?)<\/word>/g
    let wordMatch: RegExpExecArray | null
    while ((wordMatch = wordPattern.exec(body)) !== null) {
      const wordAttributes = wordMatch[1] ?? ""
      const xMin = attribute(wordAttributes, "xMin")
      const yMin = attribute(wordAttributes, "yMin")
      const xMax = attribute(wordAttributes, "xMax")
      const yMax = attribute(wordAttributes, "yMax")
      if (xMin === undefined || yMin === undefined || xMax === undefined || yMax === undefined) continue
      words.push({ text: decodeXml(wordMatch[2] ?? ""), xMin, yMin, xMax, yMax })
    }
    pages.push({ page: pages.length + 1, width, height, words })
  }
  return pages
}

type Match = {
  page: PdfPage
  words: PdfWord[]
}

function matchesForQuotation(pages: PdfPage[], quotation: string): Match[] {
  const target = tokenize(quotation)
  if (target.length === 0) return []
  const matches: Match[] = []
  for (const page of pages) {
    const tokens: Array<{ token: string; word: PdfWord }> = []
    for (const word of page.words) {
      for (const token of tokenize(word.text)) tokens.push({ token, word })
    }
    for (let start = 0; start <= tokens.length - target.length; start += 1) {
      let equal = true
      for (let offset = 0; offset < target.length; offset += 1) {
        if (tokens[start + offset]?.token !== target[offset]) {
          equal = false
          break
        }
      }
      if (equal) {
        const words = [...new Set(tokens.slice(start, start + target.length).map((item) => item.word))]
        matches.push({ page, words })
      }
    }
  }
  return matches
}

function rendition(evidence: TraceabilityEvidence, match: Match, pdfPath: string, pdfSha256: string): TraceabilityEvidence {
  const xMin = Math.min(...match.words.map((word) => word.xMin))
  const yMin = Math.min(...match.words.map((word) => word.yMin))
  const xMax = Math.max(...match.words.map((word) => word.xMax))
  const yMax = Math.max(...match.words.map((word) => word.yMax))
  return {
    evidenceId: `${evidence.evidenceId}#pdf-exact-match`,
    sourceKind: "PDF",
    documentPath: pdfPath,
    documentSha256: pdfSha256,
    locator: {
      section: evidence.locator.section,
      heading: evidence.locator.heading,
      page: match.page.page,
      bbox: [
        xMin / match.page.width,
        yMin / match.page.height,
        (xMax - xMin) / match.page.width,
        (yMax - yMin) / match.page.height,
      ],
    },
    quotation: evidence.quotation,
    alignedFromEvidenceId: evidence.evidenceId,
    alignmentMethod: "EXACT_QUOTE_TOKEN_MATCH",
  }
}

function repositoryRelative(absolute: string): string {
  const relation = relative(REPO_ROOT, absolute)
  if (relation === ".." || relation.startsWith(`..${sep}`)) {
    throw new Error("PDF source path escapes the repository")
  }
  return relation.split(sep).join("/")
}

export async function alignEvidenceToOfficialPdf(input: {
  evidence: TraceabilityEvidence[]
  sourceManifestPath: string
  sourceManifestSha256: string
}): Promise<{ renditions: TraceabilityEvidence[]; metrics: PdfAlignmentMetrics }> {
  const manifestAbsolute = resolve(REPO_ROOT, input.sourceManifestPath)
  const manifestData = await readFile(manifestAbsolute)
  const actualManifestSha256 = createHash("sha256").update(manifestData).digest("hex")
  if (actualManifestSha256 !== input.sourceManifestSha256) {
    throw new Error("Source manifest changed before PDF alignment")
  }
  const manifest = JSON.parse(manifestData.toString("utf8")) as {
    artifacts?: Array<{ kind?: string; local_path?: string; sha256?: string }>
  }
  const artifact = manifest.artifacts?.find((candidate) => candidate.kind?.toLowerCase() === "pdf")
  if (artifact?.local_path === undefined || artifact.sha256 === undefined) {
    throw new Error("Source manifest has no hash-bound official PDF artifact")
  }
  const pdfAbsolute = resolve(dirname(manifestAbsolute), artifact.local_path)
  const pdfPath = repositoryRelative(pdfAbsolute)
  const pdfData = await readFile(pdfAbsolute)
  const actualPdfSha256 = createHash("sha256").update(pdfData).digest("hex")
  if (actualPdfSha256 !== artifact.sha256) {
    throw new Error(`Official PDF hash mismatch: expected ${artifact.sha256}, got ${actualPdfSha256}`)
  }
  const cacheDirectory = resolve(REPO_ROOT, ".spec2lean-cache/traceability")
  const cachePath = resolve(cacheDirectory, `${artifact.sha256}.bbox.html`)
  await mkdir(cacheDirectory, { recursive: true })
  try {
    await readFile(cachePath)
  } catch {
    await execFileAsync("pdftotext", ["-bbox", pdfAbsolute, cachePath], {
      timeout: 120_000,
      maxBuffer: 1024 * 1024,
    })
  }
  const pages = parsePdfBboxDocument(await readFile(cachePath, "utf8"))
  if (pages.length === 0) throw new Error("pdftotext produced no PDF page geometry")

  const renditions: TraceabilityEvidence[] = []
  const ambiguous: string[] = []
  const unmatched: string[] = []
  for (const evidence of input.evidence) {
    if (evidence.quotation === undefined || evidence.quotation.trim().length === 0) {
      unmatched.push(evidence.evidenceId)
      continue
    }
    const matches = matchesForQuotation(pages, evidence.quotation)
    if (matches.length === 1) {
      renditions.push(rendition(evidence, matches[0]!, pdfPath, artifact.sha256))
    } else if (matches.length > 1) {
      ambiguous.push(evidence.evidenceId)
    } else {
      unmatched.push(evidence.evidenceId)
    }
  }
  return {
    renditions,
    metrics: {
      matched: renditions.length,
      ambiguous: ambiguous.sort((left, right) => left.localeCompare(right)),
      unmatched: unmatched.sort((left, right) => left.localeCompare(right)),
    },
  }
}
