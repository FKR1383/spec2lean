import { createHash, randomUUID } from "node:crypto"
import {
  link,
  lstat,
  mkdir,
  readFile,
  readdir,
  unlink,
  writeFile,
} from "node:fs/promises"
import {
  basename,
  dirname,
  isAbsolute,
  relative,
  resolve,
  sep,
} from "node:path"

import { REPO_ROOT } from "./repo.js"
import { loadRun } from "./run-store.js"
import { alignEvidenceToOfficialPdf } from "./pdf-alignment.js"

export type TraceabilityClassification =
  | "SOURCE_FACT"
  | "DERIVED_INTERPRETATION"
  | "DESIGN_DEPENDENCY"
  | "ASSUMPTION"
  | "OPEN_QUESTION"

export type TraceabilityLocator = {
  section?: string
  heading?: string
  anchor?: string
  startLine?: number
  endLine?: number
  page?: number
  bbox?: [number, number, number, number]
}

export type TraceabilityEvidence = {
  evidenceId: string
  sourceKind: "HTML" | "PDF" | "ARTIFACT"
  documentPath: string
  documentSha256: string
  locator: TraceabilityLocator
  quotation?: string
  alignedFromEvidenceId?: string
  alignmentMethod?: "EXACT_QUOTE_TOKEN_MATCH"
}

export type TraceabilityClaim = {
  semanticId: string
  classification: TraceabilityClassification
  statement: string
  evidenceIds: string[]
}

export type TraceabilityEntry = {
  entryId: string
  declarationKind: string
  declarationName: string
  leanRange: {
    startLine: number
    endLine: number
  }
  semanticIds: string[]
  claims: TraceabilityClaim[]
  evidence: TraceabilityEvidence[]
  unresolvedReferences: string[]
}

export type ArtifactFingerprint = {
  path: string
  sha256: string
}

export type TraceabilityManifest = {
  schemaVersion: 1
  manifestType: "spec2lean_evidence_manifest"
  generator: "spec2lean-traceability-v1"
  runId: string
  language: string
  specificationVersion: string
  unit: string
  sourceManifest: ArtifactFingerprint
  leanDocument: ArtifactFingerprint
  semanticDocument: ArtifactFingerprint
  sourceBundle: ArtifactFingerprint
  entries: TraceabilityEntry[]
  diagnostics: {
    declarationsWithoutReferences: string[]
    unresolvedReferences: string[]
    pdfAlignment?: {
      matched: number
      ambiguous: string[]
      unmatched: string[]
    }
  }
}

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function sha256(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex")
}

function assertRepositoryRelative(path: string): void {
  if (
    path.length === 0 ||
    path.includes("\0") ||
    path.includes("\\") ||
    isAbsolute(path)
  ) {
    throw new Error(`Unsafe repository-relative path: ${path}`)
  }
  const relation = relative(REPO_ROOT, resolve(REPO_ROOT, path))
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`Path escapes repository: ${path}`)
  }
}

async function readRepositoryFile(path: string): Promise<Buffer> {
  assertRepositoryRelative(path)
  const absolute = resolve(REPO_ROOT, path)
  const metadata = await lstat(absolute)
  if (!metadata.isFile() || metadata.isSymbolicLink()) {
    throw new Error(`Traceability input is not a regular file: ${path}`)
  }
  return await readFile(absolute)
}

async function fingerprint(path: string): Promise<ArtifactFingerprint> {
  return { path, sha256: sha256(await readRepositoryFile(path)) }
}

async function latestVersionedFile(
  directory: string,
  patterns: RegExp[],
): Promise<string> {
  assertRepositoryRelative(directory)
  const entries = await readdir(resolve(REPO_ROOT, directory), { withFileTypes: true })
  const candidates = entries.flatMap((entry) => {
    if (!entry.isFile() || entry.isSymbolicLink()) return []
    for (const pattern of patterns) {
      const match = entry.name.match(pattern)
      if (match?.[1] !== undefined) {
        const version = Number(match[1])
        if (Number.isSafeInteger(version)) return [{ name: entry.name, version }]
      }
    }
    return []
  }).sort((left, right) => right.version - left.version)
  const selected = candidates[0]
  if (selected === undefined) {
    throw new Error(`No versioned traceability input found under ${directory}`)
  }
  return `${directory}/${selected.name}`
}

function classification(value: unknown): TraceabilityClassification | undefined {
  switch (value) {
    case "SOURCE_FACT":
    case "DERIVED_INTERPRETATION":
    case "DESIGN_DEPENDENCY":
    case "ASSUMPTION":
    case "OPEN_QUESTION":
      return value
    default:
      return undefined
  }
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : []
}

function collectClaims(value: unknown, claims: Map<string, TraceabilityClaim>): void {
  if (Array.isArray(value)) {
    for (const item of value) collectClaims(item, claims)
    return
  }
  if (!isRecord(value)) return

  const semanticId = typeof value.semanticId === "string"
    ? value.semanticId
    : typeof value.claim_id === "string"
      ? value.claim_id
      : undefined
  const claimClassification = classification(value.classification)
  const statement = typeof value.statement === "string" ? value.statement : undefined
  if (semanticId !== undefined && claimClassification !== undefined && statement !== undefined) {
    const evidenceIds = [
      ...stringArray(value.evidenceIds),
      ...stringArray(value.evidence_fragment_ids),
    ].sort((left, right) => left.localeCompare(right))
    if (!claims.has(semanticId)) {
      claims.set(semanticId, {
        semanticId,
        classification: claimClassification,
        statement,
        evidenceIds: [...new Set(evidenceIds)],
      })
    }
  }

  for (const nested of Object.values(value)) collectClaims(nested, claims)
}

function number(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function bbox(value: unknown): [number, number, number, number] | undefined {
  if (
    Array.isArray(value) &&
    value.length === 4 &&
    value.every((item) => typeof item === "number" && Number.isFinite(item))
  ) {
    return value as [number, number, number, number]
  }
  return undefined
}

function collectEvidence(value: unknown): Map<string, TraceabilityEvidence> {
  const result = new Map<string, TraceabilityEvidence>()
  if (!isRecord(value)) return result

  const documents = new Map<string, UnknownRecord>()
  const sourceDocuments = Array.isArray(value.source_documents) ? value.source_documents : []
  for (const document of sourceDocuments) {
    if (isRecord(document) && typeof document.document_id === "string") {
      documents.set(document.document_id, document)
    }
  }

  const fragments = Array.isArray(value.fragments) ? value.fragments : []
  for (const fragment of fragments) {
    if (!isRecord(fragment) || typeof fragment.fragment_id !== "string") continue
    const document = typeof fragment.document_id === "string"
      ? documents.get(fragment.document_id)
      : undefined
    const documentPath = typeof fragment.local_source_path === "string"
      ? fragment.local_source_path
      : typeof document?.local_path === "string"
        ? document.local_path
        : undefined
    const documentSha256 = typeof fragment.source_sha256 === "string"
      ? fragment.source_sha256
      : typeof document?.sha256 === "string"
        ? document.sha256
        : undefined
    if (documentPath === undefined || documentSha256 === undefined) continue
    const rawKind = typeof fragment.source_kind === "string"
      ? fragment.source_kind.toUpperCase()
      : typeof document?.source_kind === "string"
        ? document.source_kind.toUpperCase()
        : "ARTIFACT"
    const sourceKind = rawKind === "HTML" || rawKind === "PDF" ? rawKind : "ARTIFACT"
    result.set(fragment.fragment_id, {
      evidenceId: fragment.fragment_id,
      sourceKind,
      documentPath,
      documentSha256,
      locator: {
        section: typeof fragment.section_number === "string" ? fragment.section_number : undefined,
        heading: typeof fragment.section_heading === "string" ? fragment.section_heading : undefined,
        anchor: typeof fragment.html_anchor === "string" ? fragment.html_anchor : undefined,
        startLine: number(fragment.html_line_start),
        endLine: number(fragment.html_line_end),
        page: number(fragment.pdf_page) ?? number(fragment.page),
        bbox: bbox(fragment.pdf_bbox) ?? bbox(fragment.bbox),
      },
      quotation: typeof fragment.exact_quote === "string" ? fragment.exact_quote : undefined,
    })
  }

  const evidenceRecords = Array.isArray(value.evidence) ? value.evidence : []
  for (const record of evidenceRecords) {
    if (!isRecord(record) || typeof record.evidenceId !== "string") continue
    const source = isRecord(record.source) ? record.source : undefined
    const locator = isRecord(record.locator) ? record.locator : undefined
    if (
      source === undefined ||
      typeof source.documentPath !== "string" ||
      typeof source.documentSha256 !== "string"
    ) continue
    const rawKind = typeof source.kind === "string" ? source.kind.toUpperCase() : "ARTIFACT"
    const sourceKind = rawKind === "HTML" || rawKind === "PDF" ? rawKind : "ARTIFACT"
    result.set(record.evidenceId, {
      evidenceId: record.evidenceId,
      sourceKind,
      documentPath: source.documentPath,
      documentSha256: source.documentSha256,
      locator: {
        section: typeof locator?.section === "string" ? locator.section : undefined,
        heading: typeof locator?.heading === "string" ? locator.heading : undefined,
        anchor: typeof locator?.anchor === "string" ? locator.anchor : undefined,
        startLine: number(locator?.startLine),
        endLine: number(locator?.endLine),
        page: number(locator?.page),
        bbox: bbox(locator?.bbox),
      },
      quotation: typeof record.quotation === "string" ? record.quotation : undefined,
    })
  }
  return result
}

type LeanDeclaration = {
  kind: string
  name: string
  startLine: number
  endLine: number
  comment: string
}

function parseLeanDeclarations(source: string): LeanDeclaration[] {
  const lines = source.split(/\r?\n/)
  const declarations: Omit<LeanDeclaration, "endLine">[] = []
  const declarationPattern = /^\s*(?:(?:private|protected|noncomputable)\s+)*(def|theorem|lemma|structure|inductive|abbrev|instance)\s+([A-Za-z_][A-Za-z0-9_'.]*)/

  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index]?.match(declarationPattern)
    if (match?.[1] === undefined || match[2] === undefined) continue
    const comments: string[] = []
    let commentLine = index - 1
    while (commentLine >= 0) {
      const line = lines[commentLine] ?? ""
      const comment = line.match(/^\s*--\s?(.*)$/)
      if (comment?.[1] === undefined) break
      comments.unshift(comment[1])
      commentLine -= 1
    }
    declarations.push({
      kind: match[1],
      name: match[2],
      startLine: index + 1,
      comment: comments.join("\n"),
    })
  }

  return declarations.map((declaration, index) => ({
    ...declaration,
    endLine: (declarations[index + 1]?.startLine ?? (lines.length + 1)) - 1,
  }))
}

function expandCompactReferences(comment: string): string {
  return comment.replace(
    /\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+-)(\d+)((?:\/\d+)+)/g,
    (_whole, prefix: string, first: string, suffixes: string) =>
      [first, ...suffixes.slice(1).split("/")].map((item) => `${prefix}${item}`).join(" "),
  )
}

function referencedIds(comment: string, knownIds: Iterable<string>): string[] {
  const expanded = expandCompactReferences(comment)
  return [...knownIds]
    .filter((id) => expanded.includes(id))
    .sort((left, right) => left.localeCompare(right))
}

function unresolvedReferenceTokens(comment: string, known: Set<string>): string[] {
  const expanded = expandCompactReferences(comment)
  const tokens = expanded.match(/\b(?:SF|DI|DD|OQ|A|PTX)-[A-Z0-9.-]+(?:-[A-Z0-9.]+)+\b/g) ?? []
  return [...new Set(tokens.filter((token) => !known.has(token)))].sort((a, b) => a.localeCompare(b))
}

export type BuildTraceabilityInput = {
  runId: string
  leanPath?: string
  semanticPath?: string
  sourceBundlePath?: string
  includePdfRenditions?: boolean
}

export async function buildTraceabilityManifest(
  input: BuildTraceabilityInput,
): Promise<TraceabilityManifest> {
  const run = await loadRun(input.runId)
  const leanPath = input.leanPath ?? await latestVersionedFile(
    `${run.artifactRoot}/lean`,
    [new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`)],
  )
  const semanticPath = input.semanticPath ?? await latestVersionedFile(
    `${run.artifactRoot}/semantics`,
    [/^semantics-v(\d+)\.json$/, /^materialized-v(\d+)\.json$/],
  )
  const sourceBundlePath = input.sourceBundlePath ?? await latestVersionedFile(
    `${run.artifactRoot}/source-bundles`,
    [/^source-bundle-v(\d+)\.json$/],
  )

  const [leanData, semanticData, sourceBundleData] = await Promise.all([
    readRepositoryFile(leanPath),
    readRepositoryFile(semanticPath),
    readRepositoryFile(sourceBundlePath),
  ])
  const semanticDocument: unknown = JSON.parse(semanticData.toString("utf8"))
  const sourceBundleDocument: unknown = JSON.parse(sourceBundleData.toString("utf8"))
  const claims = new Map<string, TraceabilityClaim>()
  collectClaims(semanticDocument, claims)
  const evidence = collectEvidence(sourceBundleDocument)
  const knownIds = new Set([...claims.keys(), ...evidence.keys()])

  const sourceManifest = await fingerprint(run.sourceManifest)
  const pdfAlignment = input.includePdfRenditions
    ? await alignEvidenceToOfficialPdf({
        evidence: [...evidence.values()],
        sourceManifestPath: sourceManifest.path,
        sourceManifestSha256: sourceManifest.sha256,
      })
    : undefined
  const pdfRenditions = new Map(
    (pdfAlignment?.renditions ?? []).map((item) => [item.alignedFromEvidenceId!, item]),
  )

  const entries = parseLeanDeclarations(leanData.toString("utf8")).map((declaration) => {
    const semanticIds = referencedIds(declaration.comment, claims.keys())
    const directEvidenceIds = referencedIds(declaration.comment, evidence.keys())
    const selectedClaims = semanticIds.flatMap((id) => {
      const claim = claims.get(id)
      return claim === undefined ? [] : [claim]
    })
    const evidenceIds = [...new Set([
      ...directEvidenceIds,
      ...selectedClaims.flatMap((claim) => claim.evidenceIds),
    ])].sort((left, right) => left.localeCompare(right))
    const selectedEvidence = evidenceIds.flatMap((id) => {
      const item = evidence.get(id)
      if (item === undefined) return []
      const pdf = pdfRenditions.get(id)
      return pdf === undefined ? [item] : [item, pdf]
    })
    return {
      entryId: `${declaration.kind}:${declaration.name}:${declaration.startLine}`,
      declarationKind: declaration.kind,
      declarationName: declaration.name,
      leanRange: {
        startLine: declaration.startLine,
        endLine: declaration.endLine,
      },
      semanticIds,
      claims: selectedClaims,
      evidence: selectedEvidence,
      unresolvedReferences: unresolvedReferenceTokens(declaration.comment, knownIds),
    }
  })

  return {
    schemaVersion: 1,
    manifestType: "spec2lean_evidence_manifest",
    generator: "spec2lean-traceability-v1",
    runId: run.runId,
    language: run.language,
    specificationVersion: run.specVersion,
    unit: run.unit,
    sourceManifest,
    leanDocument: { path: leanPath, sha256: sha256(leanData) },
    semanticDocument: { path: semanticPath, sha256: sha256(semanticData) },
    sourceBundle: { path: sourceBundlePath, sha256: sha256(sourceBundleData) },
    entries,
    diagnostics: {
      declarationsWithoutReferences: entries
        .filter((entry) => entry.semanticIds.length === 0 && entry.evidence.length === 0)
        .map((entry) => entry.declarationName),
      unresolvedReferences: [...new Set(entries.flatMap((entry) => entry.unresolvedReferences))]
        .sort((left, right) => left.localeCompare(right)),
      pdfAlignment: pdfAlignment?.metrics,
    },
  }
}

export function traceabilityManifestPath(manifest: TraceabilityManifest): string {
  if (!/^[A-Za-z0-9._-]+$/.test(manifest.runId)) {
    throw new Error(`Unsafe run ID: ${manifest.runId}`)
  }
  const manifestSha256 = sha256(JSON.stringify(manifest))
  return `runs/${manifest.runId}/traceability/evidence-${manifestSha256}.json`
}

export async function writeTraceabilityManifest(
  manifest: TraceabilityManifest,
  outputPath = traceabilityManifestPath(manifest),
): Promise<string> {
  assertRepositoryRelative(outputPath)
  const destination = resolve(REPO_ROOT, outputPath)
  await mkdir(dirname(destination), { recursive: true })
  const body = `${JSON.stringify(manifest, null, 2)}\n`
  const temporary = `${destination}.${randomUUID()}.tmp`
  await writeFile(temporary, body, { encoding: "utf8", flag: "wx" })
  try {
    await link(temporary, destination)
  } catch (error) {
    const code = isRecord(error) && typeof error.code === "string" ? error.code : undefined
    if (code !== "EEXIST") throw error
    const existing = await readFile(destination, "utf8")
    if (existing !== body) {
      throw new Error(`Immutable traceability manifest collision: ${outputPath}`)
    }
  } finally {
    await unlink(temporary).catch(() => {})
  }
  return outputPath
}

export function manifestEntryForLine(
  manifest: TraceabilityManifest,
  leanPath: string,
  line: number,
): TraceabilityEntry | undefined {
  if (manifest.leanDocument.path !== leanPath && basename(manifest.leanDocument.path) !== basename(leanPath)) {
    return undefined
  }
  return manifest.entries.find((entry) =>
    line >= entry.leanRange.startLine && line <= entry.leanRange.endLine,
  )
}

export async function verifyTraceabilityManifest(
  manifest: TraceabilityManifest,
): Promise<string[]> {
  const issues: string[] = []
  if (manifest.schemaVersion !== 1 || manifest.manifestType !== "spec2lean_evidence_manifest") {
    issues.push("unsupported traceability manifest schema")
  }
  for (const artifact of [
    manifest.sourceManifest,
    manifest.leanDocument,
    manifest.semanticDocument,
    manifest.sourceBundle,
  ]) {
    try {
      const actual = sha256(await readRepositoryFile(artifact.path))
      if (actual !== artifact.sha256) issues.push(`hash mismatch: ${artifact.path}`)
    } catch (error) {
      issues.push(error instanceof Error ? error.message : String(error))
    }
  }
  for (const entry of manifest.entries) {
    if (entry.leanRange.startLine > entry.leanRange.endLine) {
      issues.push(`invalid Lean range: ${entry.entryId}`)
    }
    for (const item of entry.evidence) {
      if (item.locator.bbox?.some((coordinate) => coordinate < 0 || coordinate > 1)) {
        issues.push(`PDF bbox must be normalized to [0,1]: ${item.evidenceId}`)
      }
      if (item.alignedFromEvidenceId !== undefined && item.alignmentMethod === undefined) {
        issues.push(`aligned PDF evidence lacks an alignment method: ${item.evidenceId}`)
      }
    }
  }
  return [...new Set(issues)].sort((left, right) => left.localeCompare(right))
}
