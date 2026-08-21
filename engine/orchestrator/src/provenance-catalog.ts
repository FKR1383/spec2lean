import { createHash } from "node:crypto"
import { readFile, readdir } from "node:fs/promises"
import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"
import { authoritativeArtifact } from "./artifact-authority.js"

export const PROVENANCE_CLASSIFICATIONS = [
  "SOURCE_FACT",
  "DERIVED_INTERPRETATION",
  "DESIGN_DEPENDENCY",
  "ASSUMPTION",
  "OPEN_QUESTION",
] as const

export type ProvenanceClassification =
  (typeof PROVENANCE_CLASSIFICATIONS)[number]

export type ProvenanceClaim = {
  semanticId: string
  classification: ProvenanceClassification
  statement: string
  evidenceIds: string[]
  dependencyIds: string[]
  humanApprovalDependencies: string[]
  stateAffecting?: boolean
  unresolved: boolean
  originPath: string
  origin: "SEMANTICS" | "ARCHITECTURE"
}

export type ProvenanceCatalog = {
  semanticDocument: ArtifactIdentity
  architectureDocument: ArtifactIdentity
  claims: ProvenanceClaim[]
  evidenceIds: string[]
}

export type ArtifactIdentity = {
  path: string
  sha256: string
}

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter(nonEmptyString) : []
}

function classification(value: unknown): ProvenanceClassification | undefined {
  if (value === "AMBIGUITY") return "OPEN_QUESTION"
  return PROVENANCE_CLASSIFICATIONS.includes(value as never)
    ? value as ProvenanceClassification
    : undefined
}

function firstString(record: UnknownRecord, keys: readonly string[]): string | undefined {
  for (const key of keys) {
    if (nonEmptyString(record[key])) return record[key]
  }
  return undefined
}

function collectIds(record: UnknownRecord, plural: readonly string[], singular: readonly string[]): string[] {
  const values = plural.flatMap((key) => stringArray(record[key]))
  for (const key of singular) {
    if (nonEmptyString(record[key])) values.push(record[key])
  }
  return [...new Set(values)].sort((left, right) => left.localeCompare(right))
}

const SEMANTIC_ID_KEYS = [
  "semanticId",
  "semantic_id",
  "claim_id",
  "dependency_id",
  "assumption_id",
  "ambiguity_id",
  "open_question_id",
  "source_fact_id",
  "design_dependency_id",
  "id",
] as const

/**
 * Normalize both the typed v2 IR and historical semantic JSON layouts into
 * one exact provenance catalog. Only records with classification + statement
 * are claims; document IDs and incidental `id` fields are deliberately ignored.
 */
export function collectSemanticProvenanceClaims(
  value: unknown,
  originPath: string,
): ProvenanceClaim[] {
  const claims = new Map<string, ProvenanceClaim>()
  const visit = (nested: unknown): void => {
    if (Array.isArray(nested)) {
      for (const item of nested) visit(item)
      return
    }
    if (!isRecord(nested)) return

    const semanticId = firstString(nested, SEMANTIC_ID_KEYS)
    const claimClassification = classification(nested.classification)
    const statement = firstString(nested, ["statement", "description"])
    if (
      semanticId !== undefined &&
      claimClassification !== undefined &&
      statement !== undefined &&
      !claims.has(semanticId)
    ) {
      const lifecycle = isRecord(nested.lifecycle) ? nested.lifecycle : undefined
      const status = firstString(nested, ["status"])
      claims.set(semanticId, {
        semanticId,
        classification: claimClassification,
        statement,
        evidenceIds: collectIds(
          nested,
          ["evidenceIds", "evidence_ids", "evidence_fragment_ids", "source_evidence_ids"],
          ["evidence_id", "evidence_fragment_id", "source_id"],
        ),
        dependencyIds: collectIds(
          nested,
          ["dependencyIds", "dependency_ids", "depends_on", "source_facts", "related_claims"],
          ["dependency", "depends_on_context"],
        ),
        humanApprovalDependencies: collectIds(
          nested,
          ["humanApprovalDependencies", "human_approval_dependencies", "review_record_ids"],
          ["human_approval_dependency", "review_record_id"],
        ),
        stateAffecting:
          typeof nested.stateAffecting === "boolean"
            ? nested.stateAffecting
            : typeof nested.state_affecting === "boolean"
              ? nested.state_affecting
              : undefined,
        unresolved:
          claimClassification === "OPEN_QUESTION" &&
          lifecycle?.status !== "SUPERSEDED" &&
          lifecycle?.status !== "INVALIDATED" &&
          status !== "RESOLVED" &&
          status !== "CLOSED",
        originPath,
        origin: "SEMANTICS",
      })
    }
    for (const child of Object.values(nested)) visit(child)
  }
  visit(value)
  return [...claims.values()].sort((left, right) =>
    left.semanticId.localeCompare(right.semanticId)
  )
}

export type ArchitectureIndex = {
  schemaVersion: 1
  entries: Array<{
    semanticId: string
    classification: ProvenanceClassification
    statement: string
    evidenceIds: string[]
    dependencyIds: string[]
    stateAffecting: boolean
    status: "RESOLVED" | "OPEN"
  }>
}

const ARCHITECTURE_INDEX_PATTERN =
  /<!--\s*SPEC2LEAN_ARCHITECTURE_INDEX\s*([\s\S]*?)\s*-->/m

export function parseArchitectureIndex(source: string): ArchitectureIndex | undefined {
  const body = source.match(ARCHITECTURE_INDEX_PATTERN)?.[1]
  if (body === undefined) return undefined
  try {
    return JSON.parse(body) as ArchitectureIndex
  } catch {
    return undefined
  }
}

export function validateArchitectureIndex(source: string): string[] {
  const issues: string[] = []
  const index = parseArchitectureIndex(source)
  if (index === undefined) {
    return ["architecture artifact lacks a valid SPEC2LEAN_ARCHITECTURE_INDEX JSON block"]
  }
  if (index.schemaVersion !== 1 || !Array.isArray(index.entries)) {
    return ["architecture index must have schemaVersion=1 and an entries array"]
  }
  const ids = new Set<string>()
  const entriesById = new Map<string, ArchitectureIndex["entries"][number]>()
  index.entries.forEach((entry, position) => {
    const path = `architecture index entry ${position}`
    if (!nonEmptyString(entry.semanticId)) issues.push(`${path} has no semanticId`)
    else if (ids.has(entry.semanticId)) issues.push(`duplicate architecture semanticId: ${entry.semanticId}`)
    else {
      ids.add(entry.semanticId)
      entriesById.set(entry.semanticId, entry)
    }
    if (!PROVENANCE_CLASSIFICATIONS.includes(entry.classification as never)) {
      issues.push(`${path} has invalid classification`)
    }
    if (!nonEmptyString(entry.statement)) issues.push(`${path} has no statement`)
    if (!Array.isArray(entry.evidenceIds) || !entry.evidenceIds.every(nonEmptyString)) {
      issues.push(`${path} has invalid evidenceIds`)
    }
    if (!Array.isArray(entry.dependencyIds) || !entry.dependencyIds.every(nonEmptyString)) {
      issues.push(`${path} has invalid dependencyIds`)
    }
    if (typeof entry.stateAffecting !== "boolean") issues.push(`${path} has no stateAffecting boolean`)
    if (entry.status !== "RESOLVED" && entry.status !== "OPEN") issues.push(`${path} has invalid status`)
    if (
      entry.classification === "SOURCE_FACT" &&
      ((Array.isArray(entry.evidenceIds) && entry.evidenceIds.length > 0) ||
        (Array.isArray(entry.dependencyIds) && entry.dependencyIds.length > 0))
    ) {
      issues.push(
        `${entry.semanticId} SOURCE_FACT must be an internal architecture-index root; ` +
        "put exact official locators in the human-readable source-fact section",
      )
    }
    if (entry.classification === "OPEN_QUESTION" && entry.status !== "OPEN") {
      issues.push(`${entry.semanticId} OPEN_QUESTION must have status OPEN`)
    }
    if (
      PROVENANCE_CLASSIFICATIONS.includes(entry.classification as never) &&
      entry.classification !== "OPEN_QUESTION" &&
      entry.status === "OPEN"
    ) {
      issues.push(`${entry.semanticId} has status OPEN but is not classified OPEN_QUESTION`)
    }
    if (
      entry.classification === "DERIVED_INTERPRETATION" &&
      Array.isArray(entry.dependencyIds) &&
      entry.dependencyIds.length === 0
    ) {
      issues.push(`${entry.semanticId} DERIVED_INTERPRETATION has no dependencyIds`)
    }
  })
  index.entries.forEach((entry) => {
    if (!nonEmptyString(entry.semanticId)) return
    for (const dependencyId of Array.isArray(entry.dependencyIds) ? entry.dependencyIds : []) {
      if (!ids.has(dependencyId)) {
        issues.push(`${entry.semanticId} references unknown dependencyId: ${dependencyId}`)
      } else if (
        entry.classification === "DERIVED_INTERPRETATION" &&
        entry.status === "RESOLVED" &&
        entriesById.get(dependencyId)?.status === "OPEN"
      ) {
        issues.push(
          `${entry.semanticId} resolved DERIVED_INTERPRETATION depends on open entry: ${dependencyId}`,
        )
      }
    }
    for (const evidenceId of Array.isArray(entry.evidenceIds) ? entry.evidenceIds : []) {
      if (!ids.has(evidenceId)) {
        issues.push(`${entry.semanticId} references unknown evidenceId: ${evidenceId}`)
      } else if (entriesById.get(evidenceId)?.classification !== "SOURCE_FACT") {
        issues.push(`${entry.semanticId} evidenceId is not a SOURCE_FACT: ${evidenceId}`)
      }
    }
  })
  return issues
}

export function collectArchitectureProvenanceClaims(
  source: string,
  originPath: string,
): ProvenanceClaim[] {
  const index = parseArchitectureIndex(source)
  if (index !== undefined) {
    return index.entries.map((entry) => ({
      semanticId: entry.semanticId,
      classification: entry.classification,
      statement: entry.statement,
      evidenceIds: [...entry.evidenceIds].sort((left, right) => left.localeCompare(right)),
      dependencyIds: [...entry.dependencyIds].sort((left, right) => left.localeCompare(right)),
      humanApprovalDependencies: [],
      stateAffecting: entry.stateAffecting,
      unresolved: entry.status === "OPEN",
      originPath,
      origin: "ARCHITECTURE" as const,
    })).sort((left, right) => left.semanticId.localeCompare(right.semanticId))
  }

  // Compatibility reader for already-reviewed pre-index architecture files.
  // It intentionally accepts only definition-shaped bullet lines, never table
  // edges or arbitrary inline references.
  const claims = new Map<string, ProvenanceClaim>()
  const patterns = [
    /^\s*[-*]\s+\**(SOURCE FACT|DERIVED INTERPRETATION|DESIGN CHOICE|DESIGN DEPENDENCY|ASSUMPTION|AMBIGUITY|OPEN QUESTION)\s*\(([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\)\**\s*:\s*(.*)$/i,
    /^\s*[-*]\s+\**([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)(?:\s+[^:*]+)?\**\s*:\s*(.*)$/i,
  ]
  for (const line of source.split(/\r?\n/)) {
    let id: string | undefined
    let statement: string | undefined
    let label: string | undefined
    const labeled = line.match(patterns[0]!)
    if (labeled !== null) {
      label = labeled[1]
      id = labeled[2]
      statement = labeled[3]
    } else {
      const compact = line.match(patterns[1]!)
      id = compact?.[1]
      statement = compact?.[2]
    }
    if (id === undefined || statement === undefined || claims.has(id)) continue
    const prefix = id.split("-")[0]?.toUpperCase()
    if (!["SF", "DI", "DD", "D", "PRE", "ASS", "A", "AMB", "OQ", "SC"].includes(prefix ?? "")) {
      continue
    }
    const normalizedLabel = label?.toUpperCase()
    const claimClassification: ProvenanceClassification =
      normalizedLabel === "SOURCE FACT" || prefix === "SF" ? "SOURCE_FACT" :
      normalizedLabel === "DERIVED INTERPRETATION" || prefix === "DI" || prefix === "PRE"
        ? "DERIVED_INTERPRETATION" :
      normalizedLabel === "ASSUMPTION" || prefix === "ASS" || prefix === "A"
        ? "ASSUMPTION" :
      normalizedLabel === "AMBIGUITY" || normalizedLabel === "OPEN QUESTION" ||
        prefix === "AMB" || prefix === "OQ"
        ? "OPEN_QUESTION" : "DESIGN_DEPENDENCY"
    claims.set(id, {
      semanticId: id,
      classification: claimClassification,
      statement: statement.trim(),
      evidenceIds: [],
      dependencyIds: [],
      humanApprovalDependencies: [],
      unresolved: claimClassification === "OPEN_QUESTION",
      originPath,
      origin: "ARCHITECTURE",
    })
  }
  return [...claims.values()].sort((left, right) =>
    left.semanticId.localeCompare(right.semanticId)
  )
}

function sha256(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex")
}

export async function latestVersionedArtifact(
  directory: string,
  patterns: readonly RegExp[],
): Promise<string> {
  const entries = await readdir(resolve(REPO_ROOT, directory), { withFileTypes: true })
  const candidates = entries.flatMap((entry) => {
    if (!entry.isFile() || entry.isSymbolicLink()) return []
    for (const pattern of patterns) {
      const version = Number(entry.name.match(pattern)?.[1])
      if (Number.isSafeInteger(version)) return [{ name: entry.name, version }]
    }
    return []
  }).sort((left, right) => right.version - left.version)
  if (candidates[0] === undefined) throw new Error(`No versioned artifact under ${directory}`)
  return `${directory}/${candidates[0].name}`
}

async function readIdentity(path: string): Promise<{ identity: ArtifactIdentity; source: string }> {
  const source = await readFile(resolve(REPO_ROOT, path), "utf8")
  return { identity: { path, sha256: sha256(source) }, source }
}

export async function semanticAuthorityPath(run: RunState): Promise<string> {
  return (await authoritativeArtifact(run, "SEMANTICS")).path
}

export async function buildProvenanceCatalog(
  run: RunState,
  paths: { semanticPath?: string; architecturePath?: string } = {},
): Promise<ProvenanceCatalog> {
  const semanticPath = paths.semanticPath ?? await semanticAuthorityPath(run)
  const architecturePath = paths.architecturePath ?? (await authoritativeArtifact(run, "ARCHITECTURE")).path
  const [semantic, architecture] = await Promise.all([
    readIdentity(semanticPath),
    readIdentity(architecturePath),
  ])
  const semanticClaims = collectSemanticProvenanceClaims(
    JSON.parse(semantic.source) as unknown,
    semanticPath,
  )
  const architectureClaims = collectArchitectureProvenanceClaims(
    architecture.source,
    architecturePath,
  )
  const claims = new Map(semanticClaims.map((claim) => [claim.semanticId, claim]))
  for (const claim of architectureClaims.filter((item) => item.classification !== "SOURCE_FACT")) {
    if (!claims.has(claim.semanticId)) claims.set(claim.semanticId, claim)
  }
  return {
    semanticDocument: semantic.identity,
    architectureDocument: architecture.identity,
    claims: [...claims.values()].sort((left, right) => left.semanticId.localeCompare(right.semanticId)),
    evidenceIds: [...new Set([...claims.values()].flatMap((claim) => claim.evidenceIds))]
      .sort((left, right) => left.localeCompare(right)),
  }
}

export function compactProvenanceCatalog(catalog: ProvenanceCatalog): string {
  return catalog.claims.map((claim) => {
    const flags = [
      claim.stateAffecting === true ? "STATE_AFFECTING" : undefined,
      claim.unresolved ? "UNRESOLVED" : undefined,
      claim.origin,
    ].filter(nonEmptyString).join(",")
    const statement = claim.statement.replace(/\s+/g, " ").slice(0, 180)
    return `- ${claim.semanticId} | ${claim.classification} | ${flags} | ${statement}`
  }).join("\n")
}
