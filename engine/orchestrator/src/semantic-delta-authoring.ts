import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { authoritativeArtifact } from "./artifact-authority.js"
import { stageAttempt } from "./artifact-contract.js"
import { REPO_ROOT } from "./repo.js"
import type {
  EvidenceRecord,
  InstructionSemanticDelta,
  SemanticClaim,
  SemanticRefinement,
} from "./semantic-ir/types.js"
import type { RunState } from "./workflow.js"

type UnknownRecord = Record<string, unknown>

type SourceDocument = {
  document_id: string
  kind: string
  local_path: string
  sha256: string
}

type SourceFragment = {
  fragment_id: string
  document_id: string
  exact_quote?: string
  locator: UnknownRecord
}

export type SemanticDeltaProducer = {
  agent: string
  sessionId: string
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function sha256(value: Buffer | string): string {
  return createHash("sha256").update(value).digest("hex")
}

function requiredRecord(value: unknown, field: string): UnknownRecord {
  if (!isRecord(value)) throw new Error(`${field} must be an object`)
  return value
}

function requiredArray(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array`)
  return value
}

function requiredString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${field} must be a non-empty string`)
  }
  return value
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.length > 0)
    : []
}

function canonicalLocator(locator: UnknownRecord): EvidenceRecord["locator"] {
  const result: EvidenceRecord["locator"] = {}
  const copyString = (target: "section" | "heading" | "anchor", source: string): void => {
    if (typeof locator[source] === "string" && locator[source].length > 0) {
      result[target] = locator[source]
    }
  }
  const copyNumber = (target: "startLine" | "endLine" | "page", source: string): void => {
    if (Number.isInteger(locator[source])) result[target] = locator[source] as number
  }
  copyString("section", "section")
  copyString("heading", "heading")
  copyString("anchor", "anchor")
  copyNumber("startLine", "start_line")
  copyNumber("startLine", "startLine")
  copyNumber("endLine", "end_line")
  copyNumber("endLine", "endLine")
  copyNumber("page", "page")
  return result
}

function canonicalClaim(
  input: unknown,
  evidenceAliases: Map<string, string>,
  introducedInRevision: number,
): SemanticClaim {
  const claim = requiredRecord(input, "semantic claim")
  return {
    semanticId: requiredString(claim.semanticId, "semantic claim semanticId"),
    classification: requiredString(claim.classification, "semantic claim classification") as SemanticClaim["classification"],
    statement: requiredString(claim.statement, "semantic claim statement"),
    evidenceIds: stringArray(claim.evidenceIds).map((id) => evidenceAliases.get(id) ?? id),
    dependencyIds: stringArray(claim.dependencyIds),
    stateAffecting: claim.stateAffecting === true,
    humanApprovalDependencies: stringArray(claim.humanApprovalDependencies),
    lifecycle: {
      status: "ACTIVE",
      introducedInRevision,
    },
  }
}

function canonicalRefinement(
  input: unknown,
  evidenceAliases: Map<string, string>,
  introducedInRevision: number,
): SemanticRefinement {
  const refinement = requiredRecord(input, "semantic refinement")
  return {
    ...canonicalClaim(refinement, evidenceAliases, introducedInRevision),
    targetSharedSemanticId: requiredString(
      refinement.targetSharedSemanticId,
      "semantic refinement targetSharedSemanticId",
    ),
    kind: requiredString(refinement.kind, "semantic refinement kind") as SemanticRefinement["kind"],
    rationale: requiredString(refinement.rationale, "semantic refinement rationale"),
  }
}

async function languageCoreBinding(run: RunState): Promise<InstructionSemanticDelta["languageCore"]> {
  const profilePath = run.semanticV2?.profilePath ??
    `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`
  const profile = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8")) as unknown
  const record = requiredRecord(profile, "semantic profile")
  const path = requiredString(record.languageCorePath, "semantic profile languageCorePath")
  return {
    status: "REUSED_APPROVED",
    path,
    sha256: sha256(await readFile(resolve(REPO_ROOT, path))),
  }
}

/**
 * Build the canonical delta envelope from agent-authored semantic content.
 * Identity, provenance, evidence rendition records, and fresh lifecycle
 * metadata are derived from hash-bound run inputs rather than trusted from the
 * model payload.
 */
export async function canonicalSemanticDeltaForRun(
  run: RunState,
  input: unknown,
  producer: SemanticDeltaProducer,
): Promise<InstructionSemanticDelta> {
  if (run.stage !== "SEMANTIC_EXTRACTION" ||
    run.semanticV2?.mode !== "DELTA_FAST_PATH" ||
    run.semanticV2.current === undefined ||
    run.semanticV2.environment === undefined) {
    throw new Error("run is not an active semantic-delta extraction")
  }
  const authored = requiredRecord(input, "semantic delta content")
  const sharedEnvironment = requiredRecord(
    JSON.parse(
      await readFile(resolve(REPO_ROOT, run.semanticV2.sharedEnvironmentPath), "utf8"),
    ) as unknown,
    "shared semantic environment",
  )
  const sourceBundle = await authoritativeArtifact(run, "SOURCE_BUNDLE")
  const bundle = requiredRecord(
    JSON.parse(await readFile(resolve(REPO_ROOT, sourceBundle.path), "utf8")) as unknown,
    "source bundle",
  )
  const sourceDocuments = new Map<string, SourceDocument>()
  for (const value of requiredArray(bundle.source_documents, "source bundle source_documents")) {
    const item = requiredRecord(value, "source document")
    const document: SourceDocument = {
      document_id: requiredString(item.document_id, "source document document_id"),
      kind: requiredString(item.kind, "source document kind"),
      local_path: requiredString(item.local_path, "source document local_path"),
      sha256: requiredString(item.sha256, "source document sha256"),
    }
    const actual = sha256(await readFile(resolve(REPO_ROOT, document.local_path)))
    if (actual !== document.sha256) throw new Error(`source document hash mismatch: ${document.local_path}`)
    sourceDocuments.set(document.document_id, document)
  }
  const fragments = new Map<string, SourceFragment>()
  for (const value of requiredArray(bundle.fragments, "source bundle fragments")) {
    const item = requiredRecord(value, "source fragment")
    const fragment: SourceFragment = {
      fragment_id: requiredString(item.fragment_id, "source fragment fragment_id"),
      document_id: requiredString(item.document_id, "source fragment document_id"),
      exact_quote: typeof item.exact_quote === "string" ? item.exact_quote : undefined,
      locator: requiredRecord(item.locator, "source fragment locator"),
    }
    fragments.set(fragment.fragment_id, fragment)
  }

  const authoredEvidence = Array.isArray(authored.evidence) ? authored.evidence : []
  const requested: Array<{ fragmentId: string; aliases: string[] }> = []
  const seen = new Set<string>()
  for (const value of authoredEvidence) {
    const item = requiredRecord(value, "semantic evidence reference")
    const fragmentId = typeof item.sourceBundleEvidenceId === "string"
      ? item.sourceBundleEvidenceId
      : requiredString(item.fragmentId, "semantic evidence sourceBundleEvidenceId")
    if (seen.has(fragmentId)) continue
    seen.add(fragmentId)
    requested.push({
      fragmentId,
      aliases: [item.evidenceId, item.fragmentId, item.sourceBundleEvidenceId]
        .filter((alias): alias is string => typeof alias === "string" && alias.length > 0),
    })
  }
  for (const claimValue of [
    ...requiredArray(authored.claims, "semantic delta claims"),
    ...requiredArray(authored.refinements, "semantic delta refinements"),
  ]) {
    const claim = requiredRecord(claimValue, "semantic claim")
    for (const reference of stringArray(claim.evidenceIds)) {
      if (!seen.has(reference) && fragments.has(reference)) {
        seen.add(reference)
        requested.push({ fragmentId: reference, aliases: [reference] })
      }
    }
  }

  const sourceManifestSha256 = sha256(await readFile(resolve(REPO_ROOT, run.sourceManifest)))
  const evidenceAliases = new Map<string, string>()
  const evidence: EvidenceRecord[] = requested.map(({ fragmentId, aliases }, index) => {
    const fragment = fragments.get(fragmentId)
    if (fragment === undefined) throw new Error(`unknown source-bundle evidence fragment: ${fragmentId}`)
    const document = sourceDocuments.get(fragment.document_id)
    if (document === undefined) throw new Error(`source fragment references unknown document: ${fragment.document_id}`)
    const evidenceId = `${run.unitSlug}.evidence.${index + 1}`
    evidenceAliases.set(fragmentId, evidenceId)
    for (const alias of aliases) evidenceAliases.set(alias, evidenceId)
    const quotation = fragment.exact_quote
    return {
      evidenceId,
      sourceBundleEvidenceId: fragmentId,
      specificationVersion: run.specVersion,
      source: {
        kind: document.kind.toLowerCase() as EvidenceRecord["source"]["kind"],
        documentPath: document.local_path,
        documentSha256: document.sha256,
        sourceManifestPath: run.sourceManifest,
        sourceManifestSha256,
      },
      locator: canonicalLocator(fragment.locator),
      ...(quotation === undefined ? {} : {
        quotation,
        quotationSha256: sha256(quotation),
      }),
    }
  })

  const claims = requiredArray(authored.claims, "semantic delta claims")
    .map((claim) => canonicalClaim(claim, evidenceAliases, run.revision))
  const refinements = requiredArray(authored.refinements, "semantic delta refinements")
    .map((claim) => canonicalRefinement(claim, evidenceAliases, run.revision))
  const semanticFields = {
    sharedReferences: requiredArray(authored.sharedReferences, "semantic delta sharedReferences"),
    syntaxForms: requiredArray(authored.syntaxForms, "semantic delta syntaxForms"),
    operands: requiredArray(authored.operands, "semantic delta operands"),
    operation: requiredRecord(authored.operation, "semantic delta operation"),
    stateEffects: requiredArray(authored.stateEffects, "semantic delta stateEffects"),
    preconditions: requiredArray(authored.preconditions, "semantic delta preconditions"),
    proofFamilies: requiredArray(authored.proofFamilies, "semantic delta proofFamilies"),
  }
  return {
    schemaVersion: 1,
    deltaId: `${run.language.toLowerCase()}-${run.specVersion}-${run.unitSlug}-semantic-delta-v${stageAttempt(run, "SEMANTIC_EXTRACTION")}`,
    unit: {
      language: requiredString(sharedEnvironment.language, "shared environment language"),
      specificationVersion: run.specVersion,
      unit: run.unit,
      unitSlug: run.unitSlug,
    },
    sharedEnvironment: {
      environmentId: run.semanticV2.environment.environmentId,
      revision: run.semanticV2.environment.revision,
      sha256: run.semanticV2.environment.sha256,
    },
    provenance: {
      sourceBundle: { path: sourceBundle.path, sha256: sourceBundle.sha256 },
      generatedBy: `${producer.agent}:${producer.sessionId}`,
      migrationStatus: "AGENT_GENERATED",
    },
    sharedReferences: semanticFields.sharedReferences as InstructionSemanticDelta["sharedReferences"],
    evidence,
    claims,
    refinements,
    syntaxForms: semanticFields.syntaxForms as InstructionSemanticDelta["syntaxForms"],
    operands: semanticFields.operands as InstructionSemanticDelta["operands"],
    operation: semanticFields.operation as InstructionSemanticDelta["operation"],
    stateEffects: semanticFields.stateEffects as InstructionSemanticDelta["stateEffects"],
    preconditions: semanticFields.preconditions as InstructionSemanticDelta["preconditions"],
    proofFamilies: semanticFields.proofFamilies as InstructionSemanticDelta["proofFamilies"],
    ...(typeof authored.scopeStatus === "string"
      ? { scopeStatus: authored.scopeStatus as InstructionSemanticDelta["scopeStatus"] }
      : {}),
    ...(Array.isArray(authored.coverage)
      ? { coverage: authored.coverage as InstructionSemanticDelta["coverage"] }
      : {}),
    ...(Array.isArray(authored.proofRequirements)
      ? { proofRequirements: authored.proofRequirements as InstructionSemanticDelta["proofRequirements"] }
      : {}),
    languageCore: await languageCoreBinding(run),
  }
}
