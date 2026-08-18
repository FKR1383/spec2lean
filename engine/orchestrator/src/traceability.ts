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
import { verifiedProofArtifactPath } from "./proof-plan.js"
import {
  collectArchitectureProvenanceClaims,
  collectSemanticProvenanceClaims,
} from "./provenance-catalog.js"

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
  alignmentMethod?: "EXACT_QUOTE_TOKEN_MATCH" | "PAGE_HINTED_EXACT_QUOTE_TOKEN_MATCH" | "DISTINCTIVE_TOKEN_WINDOW_MATCH"
}

export type TraceabilityClaim = {
  semanticId: string
  classification: TraceabilityClassification
  statement: string
  evidenceIds: string[]
  dependencyIds: string[]
  humanApprovalDependencies: string[]
  origin: "SEMANTICS" | "ARCHITECTURE"
  stateAffecting?: boolean
  unresolved: boolean
}

export type TraceabilityUncertainty = {
  semanticId: string
  statement: string
  origin: "SEMANTICS" | "ARCHITECTURE"
  stateAffecting?: boolean
  unresolved: true
  benchmarkDisposition?: {
    mode: "AUTO_APPROVE"
    policy: "CONSERVATIVE_BOUNDED_SCOPE"
    humanApproved: false
  }
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
  theoremObligationIds: string[]
  claims: TraceabilityClaim[]
  evidence: TraceabilityEvidence[]
  unresolvedReferences: string[]
  coverage: {
    directClaimIds: string[]
    transitiveClaimIds: string[]
    sourceFactIds: string[]
    projectBoundaryIds: string[]
    officialEvidenceIds: string[]
    pdfEvidenceIds: string[]
    projectEvidenceIds: string[]
    unresolvedDependencyIds: string[]
  }
}

export type ArtifactFingerprint = {
  path: string
  sha256: string
}

export type TraceabilityManifest = {
  schemaVersion: 3
  manifestType: "spec2lean_evidence_manifest"
  generator: "spec2lean-traceability-v3"
  runId: string
  language: string
  specificationVersion: string
  unit: string
  documentRole: "SEMANTICS" | "PROOFS"
  sourceManifest: ArtifactFingerprint
  leanDocument: ArtifactFingerprint
  semanticDocument: ArtifactFingerprint
  architectureDocument?: ArtifactFingerprint
  sourceBundles: ArtifactFingerprint[]
  theoremDocument?: ArtifactFingerprint
  entries: TraceabilityEntry[]
  semanticUncertainties: TraceabilityUncertainty[]
  diagnostics: {
    declarationsWithoutReferences: string[]
    unresolvedReferences: string[]
    declarationsWithoutEvidencePath: string[]
    claimsWithoutDependencyPath: string[]
    sourceFactsWithoutOfficialEvidence: string[]
    assumptionsWithoutApprovalDependency: string[]
    unresolvedOpenQuestions: string[]
    pdfAlignment?: {
      eligible: number
      matched: number
      ambiguous: string[]
      unmatched: string[]
      coverageRatio: number
      failure?: string
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

function collectArchitectureClaims(
  source: string,
  path: string,
  documentSha256: string,
  claims: Map<string, TraceabilityClaim>,
  evidence: Map<string, TraceabilityEvidence>,
): void {
  const lines = source.split(/\r?\n/)
  for (const item of collectArchitectureProvenanceClaims(source, path)) {
    const semanticId = item.semanticId
    if (claims.has(semanticId)) continue
    const lineIndex = Math.max(0, lines.findIndex((line) => line.includes(semanticId)))
    const evidenceId = `ARCH:${semanticId}`
    claims.set(semanticId, {
      semanticId,
      classification: item.classification,
      statement: item.statement,
      evidenceIds: [evidenceId],
      dependencyIds: item.dependencyIds,
      humanApprovalDependencies: item.humanApprovalDependencies,
      origin: item.origin,
      stateAffecting: item.stateAffecting,
      unresolved: item.unresolved,
    })
    evidence.set(evidenceId, {
      evidenceId,
      sourceKind: "ARTIFACT",
      documentPath: path,
      documentSha256,
      locator: { startLine: lineIndex + 1, endLine: lineIndex + 1 },
      quotation: lines[lineIndex]?.trim(),
    })
  }
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : []
}

function collectClaims(
  value: unknown,
  path: string,
  claims: Map<string, TraceabilityClaim>,
): void {
  for (const item of collectSemanticProvenanceClaims(value, path)) {
    if (!claims.has(item.semanticId)) {
      claims.set(item.semanticId, {
        semanticId: item.semanticId,
        classification: item.classification,
        statement: item.statement,
        evidenceIds: item.evidenceIds,
        dependencyIds: item.dependencyIds,
        humanApprovalDependencies: item.humanApprovalDependencies,
        origin: item.origin,
        stateAffecting: item.stateAffecting,
        unresolved: item.unresolved,
      })
    }
  }
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
  const firstDocument = (kind: "HTML" | "PDF"): UnknownRecord | undefined =>
    sourceDocuments.find((document) => isRecord(document) &&
      String(document.kind ?? document.source_kind ?? "").toUpperCase() === kind) as UnknownRecord | undefined
  const legacyEvidence = (
    evidenceId: string,
    fragment: UnknownRecord,
    preferredKind: "HTML" | "PDF" = "HTML",
  ): void => {
    const document = firstDocument(preferredKind)
    const documentPath = typeof fragment.source_file === "string"
      ? fragment.source_file
      : typeof document?.local_path === "string"
        ? document.local_path
        : undefined
    const documentSha256 = typeof fragment.source_sha256 === "string"
      ? fragment.source_sha256
      : typeof document?.sha256 === "string"
        ? document.sha256
        : undefined
    if (documentPath === undefined || documentSha256 === undefined) return
    const lines = Array.isArray(fragment.lines)
      ? fragment.lines.filter((item): item is number => typeof item === "number")
      : []
    result.set(evidenceId, {
      evidenceId,
      sourceKind: preferredKind,
      documentPath,
      documentSha256,
      locator: {
        section: typeof fragment.section_number === "string" ? fragment.section_number : undefined,
        heading: typeof fragment.heading === "string" ? fragment.heading : undefined,
        anchor: typeof fragment.anchor === "string" ? fragment.anchor : undefined,
        startLine: number(fragment.start_line) ?? lines[0],
        endLine: number(fragment.end_line) ?? lines.at(-1),
        page: number(fragment.page),
      },
      quotation: typeof fragment.quote === "string"
        ? fragment.quote
        : typeof fragment.quote_excerpt === "string"
          ? fragment.quote_excerpt
          : typeof fragment.quotation_rendered_text === "string"
            ? fragment.quotation_rendered_text
            : typeof fragment.snippet === "string"
              ? fragment.snippet
              : undefined,
    })
  }

  const coverage = Array.isArray(value.coverage) ? value.coverage : []
  for (const fragment of coverage) {
    if (isRecord(fragment) && typeof fragment.fact_id === "string") {
      legacyEvidence(fragment.fact_id, fragment)
    }
  }
  const sharedContexts = Array.isArray(value.shared_contexts) ? value.shared_contexts : []
  sharedContexts.forEach((fragment, index) => {
    if (!isRecord(fragment)) return
    const evidenceId = typeof fragment.fragment_id === "string"
      ? fragment.fragment_id
      : `CTX-${String(index + 1).padStart(2, "0")}`
    legacyEvidence(evidenceId, fragment)
  })
  if (isRecord(value.pdf_corroboration)) {
    legacyEvidence("PDF_CORROBORATION", value.pdf_corroboration, "PDF")
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
        : typeof document?.kind === "string"
          ? document.kind.toUpperCase()
        : "ARTIFACT"
    const sourceKind = rawKind === "HTML" || rawKind === "PDF" ? rawKind : "ARTIFACT"
    const canonicalLocator = isRecord(fragment.locator) ? fragment.locator : undefined
    result.set(fragment.fragment_id, {
      evidenceId: fragment.fragment_id,
      sourceKind,
      documentPath,
      documentSha256,
      locator: {
        section: typeof canonicalLocator?.section === "string"
          ? canonicalLocator.section
          : typeof fragment.section_number === "string" ? fragment.section_number : undefined,
        heading: typeof canonicalLocator?.heading === "string"
          ? canonicalLocator.heading
          : typeof fragment.section_heading === "string" ? fragment.section_heading : undefined,
        anchor: typeof canonicalLocator?.anchor === "string"
          ? canonicalLocator.anchor
          : typeof fragment.html_anchor === "string" ? fragment.html_anchor : undefined,
        startLine: number(canonicalLocator?.start_line) ?? number(fragment.html_line_start),
        endLine: number(canonicalLocator?.end_line) ?? number(fragment.html_line_end),
        page: number(canonicalLocator?.page) ?? number(fragment.pdf_page) ?? number(fragment.page),
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

type TheoremBinding = {
  obligationId: string
  semanticIds: string[]
}

function collectTheoremBindings(value: unknown): Map<string, TheoremBinding> {
  const bindings = new Map<string, TheoremBinding>()
  const visit = (nested: unknown): void => {
    if (Array.isArray(nested)) {
      for (const item of nested) visit(item)
      return
    }
    if (!isRecord(nested)) return
    const obligationId = typeof nested.obligation_id === "string"
      ? nested.obligation_id
      : typeof nested.obligationId === "string"
        ? nested.obligationId
        : undefined
    const semanticIds = [
      ...stringArray(nested.semantic_claim_ids),
      ...stringArray(nested.semanticClaimIds),
    ]
    if (obligationId !== undefined && semanticIds.length > 0) {
      const names = new Set<string>()
      if (typeof nested.proposed_name === "string") {
        const unqualifiedName = nested.proposed_name.split(".").at(-1)
        if (unqualifiedName !== undefined && /^[A-Za-z_][A-Za-z0-9_']*$/.test(unqualifiedName)) {
          names.add(unqualifiedName)
        }
      }
      const collectNames = (item: unknown): void => {
        if (typeof item === "string") {
          for (const match of item.matchAll(/\btheorem\s+([A-Za-z_][A-Za-z0-9_'.]*)/g)) {
            if (match[1] !== undefined) {
              names.add(match[1])
              names.add(match[1].split(".").at(-1)!)
            }
          }
          return
        }
        if (Array.isArray(item)) {
          for (const child of item) collectNames(child)
          return
        }
        if (isRecord(item)) {
          for (const child of Object.values(item)) collectNames(child)
        }
      }
      collectNames(nested)
      for (const name of names) {
        bindings.set(name, {
          obligationId,
          semanticIds: [...new Set(semanticIds)].sort((left, right) => left.localeCompare(right)),
        })
      }
    }
    for (const item of Object.values(nested)) visit(item)
  }
  visit(value)
  return bindings
}

export function parseLeanDeclarations(source: string): LeanDeclaration[] {
  const lines = source.split(/\r?\n/)
  const declarations: Omit<LeanDeclaration, "endLine">[] = []
  const declarationPattern = /^\s*(?:(?:private|protected|noncomputable)\s+)*(def|theorem|lemma|structure|inductive|abbrev|instance)\s+([A-Za-z_][A-Za-z0-9_'.]*)/

  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index]?.match(declarationPattern)
    if (match?.[1] === undefined || match[2] === undefined) continue
    const comments: string[] = []
    let commentLine = index - 1
    let skippedBlank = false
    while (commentLine >= 0) {
      const line = lines[commentLine] ?? ""
      const comment = line.match(/^\s*--\s?(.*)$/)
      if (comment?.[1] === undefined) {
        if (!skippedBlank && line.trim().length === 0) {
          skippedBlank = true
          commentLine -= 1
          continue
        }
        break
      }
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
    .filter((id) => {
      const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      return new RegExp(`(^|[^A-Za-z0-9_.-])${escaped}(?=$|[^A-Za-z0-9_.-])`).test(expanded)
    })
    .sort((left, right) => left.localeCompare(right))
}

export function unresolvedReferenceTokens(comment: string, known: Set<string>): string[] {
  const provenanceLines = comment.split(/\r?\n/).filter((line) =>
    /\b(?:spec2lean|traceability|provenance|semantic|evidence)\b/i.test(line)
  )
  const expanded = expandCompactReferences(provenanceLines.join("\n"))
  const tokens = expanded.match(/\b[A-Z][A-Z0-9]*(?:-[A-Z0-9.]+){2,}\b/g) ?? []
  return [...new Set(tokens.filter((token) => !known.has(token)))].sort((a, b) => a.localeCompare(b))
}

function claimClosure(
  directIds: string[],
  claims: Map<string, TraceabilityClaim>,
): { claims: TraceabilityClaim[]; unresolvedDependencyIds: string[] } {
  const selected = new Map<string, TraceabilityClaim>()
  const unresolved = new Set<string>()
  const pending = [...directIds]
  while (pending.length > 0) {
    const id = pending.pop()!
    if (selected.has(id)) continue
    const claim = claims.get(id)
    if (claim === undefined) {
      unresolved.add(id)
      continue
    }
    selected.set(id, claim)
    for (const dependencyId of claim.dependencyIds) {
      if (claims.has(dependencyId)) pending.push(dependencyId)
      else unresolved.add(dependencyId)
    }
  }
  return {
    claims: [...selected.values()].sort((left, right) => left.semanticId.localeCompare(right.semanticId)),
    unresolvedDependencyIds: [...unresolved].sort((left, right) => left.localeCompare(right)),
  }
}

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right))
}

export type BuildTraceabilityInput = {
  runId: string
  documentRole?: "SEMANTICS" | "PROOFS"
  leanPath?: string
  semanticPath?: string
  architecturePath?: string
  sourceBundlePaths?: string[]
  theoremPath?: string
  includePdfRenditions?: boolean
}

export async function buildTraceabilityManifest(
  input: BuildTraceabilityInput,
): Promise<TraceabilityManifest> {
  const run = await loadRun(input.runId)
  const documentRole = input.documentRole ?? "SEMANTICS"
  const leanPath = input.leanPath ?? (documentRole === "PROOFS"
    ? verifiedProofArtifactPath(run)
    : await latestVersionedFile(
        `${run.artifactRoot}/lean`,
        [new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`)],
      ))
  const semanticPath = input.semanticPath ?? (
    run.semanticV2?.mode === "DELTA_FAST_PATH" && run.semanticV2.current?.materializedPath !== undefined
      ? run.semanticV2.current.materializedPath
      : await latestVersionedFile(
          `${run.artifactRoot}/semantics`,
          [/^semantics-v(\d+)\.json$/],
        )
  )
  const architecturePath = input.architecturePath ?? await latestVersionedFile(
    `${run.artifactRoot}/architecture`,
    [/^foundation-v(\d+)\.md$/],
  )
  const sourceBundlePaths = input.sourceBundlePaths ?? [
    await latestVersionedFile(
      `${run.artifactRoot}/source-bundles`,
      [/^source-bundle-v(\d+)\.json$/],
    ),
  ]
  if (sourceBundlePaths.length === 0) throw new Error("At least one source bundle is required")
  const theoremPath = documentRole === "PROOFS"
    ? input.theoremPath ?? await latestVersionedFile(
        `${run.artifactRoot}/theorems`,
        [/^obligations-v(\d+)\.json$/],
      )
    : undefined

  const [leanData, semanticData, architectureData, sourceBundleData, theoremData] = await Promise.all([
    readRepositoryFile(leanPath),
    readRepositoryFile(semanticPath),
    readRepositoryFile(architecturePath),
    Promise.all(sourceBundlePaths.map(readRepositoryFile)),
    theoremPath === undefined ? undefined : readRepositoryFile(theoremPath),
  ])
  const semanticDocument: unknown = JSON.parse(semanticData.toString("utf8"))
  const strictSemanticIr = isRecord(semanticDocument) && semanticDocument.schemaVersion === 2 &&
    Array.isArray(semanticDocument.semanticClaims)
  const claims = new Map<string, TraceabilityClaim>()
  collectClaims(semanticDocument, semanticPath, claims)
  const evidence = new Map<string, TraceabilityEvidence>()
  for (const data of sourceBundleData) {
    for (const [id, item] of collectEvidence(JSON.parse(data.toString("utf8")) as unknown)) {
      evidence.set(id, item)
    }
  }
  collectArchitectureClaims(
    architectureData.toString("utf8"),
    architecturePath,
    sha256(architectureData),
    claims,
    evidence,
  )
  const theoremBindings = theoremData === undefined
    ? new Map<string, TheoremBinding>()
    : collectTheoremBindings(JSON.parse(theoremData.toString("utf8")) as unknown)
  const knownIds = new Set([
    ...claims.keys(),
    ...evidence.keys(),
    ...[...theoremBindings.values()].map((binding) => binding.obligationId),
  ])

  const sourceManifestPath = run.sourceManifest ?? (
    run.language.toLowerCase() === "ptx"
      ? `documents/sources/nvidia/ptx/${run.specVersion}/source-manifest.json`
      : undefined
  )
  if (sourceManifestPath === undefined) throw new Error("Run has no source manifest")
  const sourceManifest = await fingerprint(sourceManifestPath)
  let pdfAlignment: Awaited<ReturnType<typeof alignEvidenceToOfficialPdf>> | undefined
  let pdfAlignmentFailure: string | undefined
  if (input.includePdfRenditions) {
    try {
      pdfAlignment = await alignEvidenceToOfficialPdf({
        evidence: [...evidence.values()],
        sourceManifestPath: sourceManifest.path,
        sourceManifestSha256: sourceManifest.sha256,
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      if (!message.includes("no hash-bound official PDF artifact")) pdfAlignmentFailure = message
    }
  }
  const pdfRenditions = new Map(
    (pdfAlignment?.renditions ?? []).map((item) => [item.alignedFromEvidenceId!, item]),
  )

  const entries = parseLeanDeclarations(leanData.toString("utf8")).map((declaration) => {
    const theoremBinding = theoremBindings.get(declaration.name)
    const semanticIds = [...new Set([
      ...referencedIds(declaration.comment, claims.keys()),
      ...(theoremBinding?.semanticIds ?? []).filter((id) => claims.has(id)),
    ])].sort((left, right) => left.localeCompare(right))
    const directEvidenceIds = referencedIds(declaration.comment, evidence.keys())
    const closure = claimClosure(semanticIds, claims)
    const selectedClaims = closure.claims
    const evidenceIds = uniqueSorted([
      ...directEvidenceIds,
      ...selectedClaims.flatMap((claim) => claim.evidenceIds),
    ])
    const selectedEvidence = evidenceIds.flatMap((id) => {
      const item = evidence.get(id)
      if (item === undefined) return []
      const pdf = pdfRenditions.get(id)
      return pdf === undefined ? [item] : [item, pdf]
    })
    const officialEvidenceIds = uniqueSorted(selectedEvidence
      .filter((item) => item.sourceKind === "HTML" || item.sourceKind === "PDF")
      .map((item) => item.evidenceId))
    const projectEvidenceIds = uniqueSorted(selectedEvidence
      .filter((item) => item.sourceKind === "ARTIFACT").map((item) => item.evidenceId))
    return {
      entryId: `${declaration.kind}:${declaration.name}:${declaration.startLine}`,
      declarationKind: declaration.kind,
      declarationName: declaration.name,
      leanRange: {
        startLine: declaration.startLine,
        endLine: declaration.endLine,
      },
      semanticIds,
      theoremObligationIds: theoremBinding === undefined ? [] : [theoremBinding.obligationId],
      claims: selectedClaims,
      evidence: selectedEvidence,
      unresolvedReferences: [...new Set([
        ...unresolvedReferenceTokens(declaration.comment, knownIds),
        ...(theoremBinding?.semanticIds ?? []).filter((id) => !claims.has(id)),
        ...closure.unresolvedDependencyIds,
      ])].sort((left, right) => left.localeCompare(right)),
      coverage: {
        directClaimIds: semanticIds,
        transitiveClaimIds: selectedClaims.map((claim) => claim.semanticId),
        sourceFactIds: selectedClaims.filter((claim) => claim.classification === "SOURCE_FACT").map((claim) => claim.semanticId),
        projectBoundaryIds: selectedClaims.filter((claim) => ["DESIGN_DEPENDENCY", "ASSUMPTION", "OPEN_QUESTION"].includes(claim.classification)).map((claim) => claim.semanticId),
        officialEvidenceIds,
        pdfEvidenceIds: selectedEvidence.filter((item) => item.sourceKind === "PDF").map((item) => item.evidenceId),
        projectEvidenceIds,
        unresolvedDependencyIds: closure.unresolvedDependencyIds,
      },
    }
  })
  const benchmarkWaived =
    run.benchmark?.autoApprove === true &&
    (run.gates.A === "benchmark_auto_advanced" ||
      run.gates.B === "benchmark_auto_advanced")
  const semanticUncertainties: TraceabilityUncertainty[] = [...claims.values()]
    .filter((claim) =>
      claim.classification === "OPEN_QUESTION" && claim.unresolved
    )
    .map((claim) => ({
      semanticId: claim.semanticId,
      statement: claim.statement,
      origin: claim.origin,
      stateAffecting: claim.stateAffecting,
      unresolved: true as const,
      benchmarkDisposition: !benchmarkWaived ? undefined : {
        mode: "AUTO_APPROVE" as const,
        policy: "CONSERVATIVE_BOUNDED_SCOPE" as const,
        humanApproved: false as const,
      },
    }))
    .sort((left, right) => left.semanticId.localeCompare(right.semanticId))

  return {
    schemaVersion: 3,
    manifestType: "spec2lean_evidence_manifest",
    generator: "spec2lean-traceability-v3",
    runId: run.runId,
    language: run.language,
    specificationVersion: run.specVersion,
    unit: run.unit,
    documentRole,
    sourceManifest,
    leanDocument: { path: leanPath, sha256: sha256(leanData) },
    semanticDocument: { path: semanticPath, sha256: sha256(semanticData) },
    architectureDocument: { path: architecturePath, sha256: sha256(architectureData) },
    sourceBundles: sourceBundlePaths.map((path, index) => ({
      path,
      sha256: sha256(sourceBundleData[index]!),
    })),
    theoremDocument: theoremPath === undefined || theoremData === undefined
      ? undefined
      : { path: theoremPath, sha256: sha256(theoremData) },
    entries,
    semanticUncertainties,
    diagnostics: {
      declarationsWithoutReferences: entries
        .filter((entry) => entry.semanticIds.length === 0 && entry.evidence.length === 0)
        .map((entry) => entry.declarationName),
      unresolvedReferences: [...new Set(entries.flatMap((entry) => entry.unresolvedReferences))]
        .sort((left, right) => left.localeCompare(right)),
      declarationsWithoutEvidencePath: entries
        .filter((entry) => entry.coverage.officialEvidenceIds.length === 0 && entry.coverage.projectEvidenceIds.length === 0)
        .map((entry) => entry.declarationName),
      claimsWithoutDependencyPath: strictSemanticIr ? uniqueSorted([...claims.values()]
        .filter((claim) => claim.classification === "DERIVED_INTERPRETATION" && claim.dependencyIds.length === 0)
        .map((claim) => claim.semanticId)) : [],
      sourceFactsWithoutOfficialEvidence: strictSemanticIr ? uniqueSorted([...claims.values()]
        .filter((claim) => claim.classification === "SOURCE_FACT" && claim.origin === "SEMANTICS")
        .filter((claim) => !claim.evidenceIds.some((id) => {
          const item = evidence.get(id)
          return item?.sourceKind === "HTML" || item?.sourceKind === "PDF"
        }))
        .map((claim) => claim.semanticId)) : [],
      assumptionsWithoutApprovalDependency: strictSemanticIr ? uniqueSorted([...claims.values()]
        .filter((claim) => claim.classification === "ASSUMPTION" && claim.origin === "SEMANTICS" && claim.humanApprovalDependencies.length === 0)
        .map((claim) => claim.semanticId)) : [],
      unresolvedOpenQuestions: semanticUncertainties.map((item) => item.semanticId),
      pdfAlignment: !input.includePdfRenditions || (pdfAlignment === undefined && pdfAlignmentFailure === undefined)
        ? undefined : pdfAlignment?.metrics ?? {
        eligible: [...evidence.values()].filter((item) => item.sourceKind === "HTML" && item.quotation !== undefined).length,
        matched: 0,
        ambiguous: [],
        unmatched: [],
        coverageRatio: 0,
        failure: pdfAlignmentFailure ?? "unknown PDF alignment failure",
      },
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
  const legacy = manifest as unknown as {
    schemaVersion?: number
    generator?: string
    sourceBundle?: ArtifactFingerprint
    sourceBundles?: ArtifactFingerprint[]
    architectureDocument?: ArtifactFingerprint
    documentRole?: "SEMANTICS" | "PROOFS"
  }
  const supportedVersion =
    (legacy.schemaVersion === 1 && legacy.generator === "spec2lean-traceability-v1") ||
    (legacy.schemaVersion === 2 && legacy.generator === "spec2lean-traceability-v2") ||
    (legacy.schemaVersion === 3 && legacy.generator === "spec2lean-traceability-v3")
  if (!supportedVersion || manifest.manifestType !== "spec2lean_evidence_manifest") {
    issues.push("unsupported traceability manifest schema")
  }
  const bundles = legacy.sourceBundles ?? (legacy.sourceBundle === undefined ? [] : [legacy.sourceBundle])
  if (bundles.length === 0) issues.push("traceability manifest has no source bundle")
  for (const artifact of [
    manifest.sourceManifest,
    manifest.leanDocument,
    manifest.semanticDocument,
    ...(legacy.architectureDocument === undefined ? [] : [legacy.architectureDocument]),
    ...bundles,
    ...(manifest.theoremDocument === undefined ? [] : [manifest.theoremDocument]),
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
  if (legacy.documentRole === "PROOFS" && manifest.theoremDocument === undefined) {
    issues.push("proof traceability manifest lacks theorem obligation document")
  }
  for (const declaration of manifest.diagnostics.declarationsWithoutReferences) {
    issues.push(`Lean declaration has no provenance reference: ${declaration}`)
  }
  for (const reference of manifest.diagnostics.unresolvedReferences) {
    issues.push(`unresolved provenance reference: ${reference}`)
  }
  if (manifest.schemaVersion === 3) {
    for (const declaration of manifest.diagnostics.declarationsWithoutEvidencePath) {
      issues.push(`Lean declaration has no transitive source or project evidence path: ${declaration}`)
    }
    for (const semanticId of manifest.diagnostics.claimsWithoutDependencyPath) {
      issues.push(`derived interpretation has no dependency path: ${semanticId}`)
    }
    for (const semanticId of manifest.diagnostics.sourceFactsWithoutOfficialEvidence) {
      issues.push(`semantic SOURCE_FACT has no official HTML/PDF evidence: ${semanticId}`)
    }
    for (const semanticId of manifest.diagnostics.assumptionsWithoutApprovalDependency) {
      issues.push(`semantic ASSUMPTION has no human-approval dependency: ${semanticId}`)
    }
    if (manifest.diagnostics.pdfAlignment?.failure !== undefined) {
      issues.push(`official PDF alignment failed: ${manifest.diagnostics.pdfAlignment.failure}`)
    }
  }
  return [...new Set(issues)].sort((left, right) => left.localeCompare(right))
}
