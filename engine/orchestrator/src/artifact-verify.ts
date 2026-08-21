import { createHash } from "node:crypto"
import { access, readFile, stat } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun } from "./artifact-contract.js"
import { authoritativeArtifact } from "./artifact-authority.js"
import { validateArtifactContent } from "./artifact-content.js"
import { validateArchitectureQuestionTriage } from "./architecture-review.js"
import { prohibitedLeanTokens, verifyLeanFile } from "./lean-local.js"
import { duplicateJsonKeyIssues } from "./json-integrity.js"
import { latestObligationPath, proofTargets } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import {
  artifactChainCompletenessIssues,
  leanModelContractIssues,
  theoremSemanticCoverageIssues,
} from "./quality-contract.js"
import { theoremStrengthReviewAuditIssues } from "./theorem-contract.js"
import { theoremElaborationIssues } from "./theorem-elaboration.js"
import {
  leanBehaviorBranches,
  theoremBehaviorAuditIssues,
} from "./theorem-behavior-audit.js"
import { semanticEvidenceRenditionIssues } from "./traceability.js"
import { criticStageOwnershipIssues } from "./stage-ownership.js"
import { loadLanguageCore } from "./language-core.js"
import { validateSemanticDeltaForRun } from "./semantic-v2.js"
import type { RunState } from "./workflow.js"

export type ArtifactVerification = {
  ok: boolean
  path: string
  issues: string[]
}

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

const nonEmptyString = (value: unknown): value is string => typeof value === "string" && value.length > 0

async function sourceDocumentIntegrityIssues(document: unknown): Promise<string[]> {
  const issues: string[] = []
  if (!isRecord(document)) return issues
  const documents = Array.isArray(document.source_documents) ? document.source_documents : []
  for (const [index, item] of documents.entries()) {
    if (!isRecord(item)) continue
    const path = item.local_path
    const expected = item.sha256
    if (!nonEmptyString(path) || !nonEmptyString(expected)) continue
    const absolute = resolve(REPO_ROOT, path)
    if (!absolute.startsWith(`${REPO_ROOT}/`)) {
      issues.push(`source document ${index} path escapes repository: ${path}`)
      continue
    }
    try {
      const data = await readFile(absolute)
      const actual = createHash("sha256").update(data).digest("hex")
      if (actual !== expected) issues.push(`source document ${index} SHA-256 mismatch: ${path}`)
    } catch (error) {
      issues.push(`source document ${index} cannot be read: ${error instanceof Error ? error.message : String(error)}`)
    }
  }
  return issues
}

async function semanticEvidenceIntegrityIssues(run: RunState, document: unknown): Promise<string[]> {
  const issues: string[] = []
  if (!isRecord(document)) return issues
  try {
    const bundlePath = (await authoritativeArtifact(run, "SOURCE_BUNDLE")).path
    const bundle = JSON.parse(await readFile(resolve(REPO_ROOT, bundlePath), "utf8")) as UnknownRecord
    const fragments = Array.isArray(bundle.fragments) ? bundle.fragments : []
    const fragmentIds = new Set(fragments.filter(isRecord).map((item) => item.fragment_id).filter(nonEmptyString))
    const claims = Array.isArray(document.semanticClaims) ? document.semanticClaims.filter(isRecord) : []
    for (const claim of claims) {
      if (claim.classification !== "SOURCE_FACT") continue
      const evidenceIds = Array.isArray(claim.evidenceIds) ? claim.evidenceIds.filter(nonEmptyString) : []
      for (const evidenceId of evidenceIds) {
        if (!fragmentIds.has(evidenceId)) issues.push(`${String(claim.semanticId)} references unknown source fragment: ${evidenceId}`)
      }
    }
  } catch (error) {
    issues.push(`could not verify semantic evidence against source bundle: ${error instanceof Error ? error.message : String(error)}`)
  }
  return issues
}

export async function verifyExpectedArtifact(run: RunState): Promise<ArtifactVerification> {
  const path = artifactContractForRun(run).outputPath
  const absolute = resolve(REPO_ROOT, path)
  const issues: string[] = []

  try {
    await access(absolute)
  } catch {
    return { ok: false, path, issues: ["expected artifact does not exist"] }
  }

  const fileStat = await stat(absolute)
  if (fileStat.size === 0) issues.push("artifact is empty")
  const source = await readFile(absolute, "utf8")
  let parsedJson: unknown

  if (path.endsWith(".json")) {
    try {
      parsedJson = JSON.parse(source)
      issues.push(...duplicateJsonKeyIssues(source))
    } catch (error) {
      issues.push(`invalid JSON: ${String(error)}`)
    }
  }

  issues.push(...validateArtifactContent(run, source, parsedJson))
  if (run.stage.endsWith("_CRITIQUE")) {
    issues.push(...criticStageOwnershipIssues(run, source))
  }
  if (run.stage === "SOURCE_CURATION") {
    issues.push(...await sourceDocumentIntegrityIssues(parsedJson))
  }
  if (run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode === "DELTA_FAST_PATH") {
    const semantic = await validateSemanticDeltaForRun(run)
    issues.push(...semantic.issues)
  }
  if (run.stage === "SEMANTIC_EXTRACTION" && run.semanticV2?.mode !== "DELTA_FAST_PATH") {
    issues.push(...await semanticEvidenceIntegrityIssues(run, parsedJson))
    try {
      issues.push(...await semanticEvidenceRenditionIssues({
        runId: run.runId,
        semanticDocument: parsedJson,
      }))
    } catch (error) {
      issues.push(`could not verify semantic official-rendition coverage: ${error instanceof Error ? error.message : String(error)}`)
    }
    if (run.qualityContractVersion === 1) {
      try {
        const [architecturePath, sourceBundlePath] = await Promise.all([
          authoritativeArtifact(run, "ARCHITECTURE").then((item) => item.path),
          authoritativeArtifact(run, "SOURCE_BUNDLE").then((item) => item.path),
        ])
        const [architecture, sourceBundle] = await Promise.all([
          readFile(resolve(REPO_ROOT, architecturePath), "utf8"),
          readFile(resolve(REPO_ROOT, sourceBundlePath), "utf8").then((value) => JSON.parse(value) as unknown),
        ])
        issues.push(...artifactChainCompletenessIssues(architecture, sourceBundle, parsedJson))
        if (isRecord(parsedJson) && isRecord(parsedJson.languageCore) &&
          parsedJson.languageCore.status === "REUSED_APPROVED") {
          const profilePath = `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`
          const profile = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8")) as UnknownRecord
          if (!nonEmptyString(profile.languageCorePath)) throw new Error("semantic profile has no languageCorePath")
          await loadLanguageCore(profile.languageCorePath)
          const coreSha256 = createHash("sha256")
            .update(await readFile(resolve(REPO_ROOT, profile.languageCorePath)))
            .digest("hex")
          if (parsedJson.languageCore.path !== profile.languageCorePath ||
            parsedJson.languageCore.sha256 !== coreSha256) {
            issues.push("semantics is not bound to the exact current language-core manifest")
          }
        }
      } catch (error) {
        issues.push(`could not validate architecture/source/semantics coverage: ${String(error)}`)
      }
    }
  }

  if (run.qualityContractVersion === 1 && run.stage === "LEAN_FORMALIZATION") {
    try {
      const semanticsPath = (await authoritativeArtifact(run, "SEMANTICS")).path
      const semantics = JSON.parse(
        await readFile(resolve(REPO_ROOT, semanticsPath), "utf8"),
      ) as unknown
      let expectedCoreImport: string | undefined
      if (isRecord(semantics) && isRecord(semantics.languageCore) &&
        semantics.languageCore.status === "REUSED_APPROVED") {
        const profilePath = `language_packs/${run.language.toLowerCase()}/${run.specVersion}/semantic-profile.json`
        const profile = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8")) as UnknownRecord
        if (!nonEmptyString(profile.languageCorePath)) throw new Error("semantic profile has no languageCorePath")
        const core = await loadLanguageCore(profile.languageCorePath)
        const coreSha256 = createHash("sha256")
          .update(await readFile(resolve(REPO_ROOT, profile.languageCorePath)))
          .digest("hex")
        if (semantics.languageCore.path !== profile.languageCorePath ||
          semantics.languageCore.sha256 !== coreSha256) {
          issues.push("semantics is not bound to the exact current language-core manifest")
        }
        expectedCoreImport = core.leanModule.importName
      }
      issues.push(...leanModelContractIssues(source, semantics, expectedCoreImport))
    } catch (error) {
      issues.push(`could not compare Lean model contract with semantics: ${String(error)}`)
    }
  }

  if (run.qualityContractVersion === 1 && run.stage === "THEOREM_GENERATION") {
    try {
      const [semanticsPath, leanPath] = await Promise.all([
        authoritativeArtifact(run, "SEMANTICS").then((item) => item.path),
        authoritativeArtifact(run, "LEAN_MAPPING").then((item) => item.path),
      ])
      const [semantics, leanSource] = await Promise.all([
        readFile(resolve(REPO_ROOT, semanticsPath), "utf8").then((value) => JSON.parse(value) as unknown),
        readFile(resolve(REPO_ROOT, leanPath), "utf8"),
      ])
      issues.push(...theoremSemanticCoverageIssues(parsedJson, semantics, leanSource))
      issues.push(...await theoremElaborationIssues(run, parsedJson, leanPath))
    } catch (error) {
      issues.push(`could not validate theorem coverage against semantics and Lean: ${String(error)}`)
    }
  }

  if (run.stage === "ARCHITECTURE_CRITIQUE") {
    try {
      const architecturePath = (await authoritativeArtifact(run, "ARCHITECTURE")).path
      const architecture = await readFile(resolve(REPO_ROOT, architecturePath), "utf8")
      issues.push(...validateArchitectureQuestionTriage(architecture, source))
    } catch (error) {
      issues.push(
        `could not validate architecture open-question triage: ${String(error)}`,
      )
    }
  }

  if (run.stage === "THEOREM_STRENGTH_CRITIQUE") {
    try {
      const obligationPath = await latestObligationPath(run)
      const targets = await proofTargets(run)
      issues.push(...theoremStrengthReviewAuditIssues(source, obligationPath, targets))
      const leanPath = (await authoritativeArtifact(run, "LEAN_MAPPING")).path
      const leanSource = await readFile(resolve(REPO_ROOT, leanPath), "utf8")
      issues.push(...theoremBehaviorAuditIssues(
        source,
        targets,
        leanBehaviorBranches(leanSource),
      ))
    } catch (error) {
      issues.push(
        `could not validate theorem-strength review against its obligation contract: ${String(error)}`,
      )
    }
  }

  if (path.endsWith(".lean")) {
    const banned = await prohibitedLeanTokens(path)
    if (banned.length > 0) {
      issues.push(`prohibited Lean tokens in code: ${banned.join(", ")}`)
    }

    const check = await verifyLeanFile(path)
    if (!check.success) {
      issues.push(`Lean check failed: ${check.output.slice(-6000)}`)
    }
  }

  return { ok: issues.length === 0, path, issues }
}
