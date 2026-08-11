import { access, readFile, readdir } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun, stageAttempt } from "./artifact-contract.js"
import { REPO_ROOT } from "./repo.js"
import {
  compareProofWithApprovedTheorems,
  validateTheoremObligationDocument,
} from "./theorem-contract.js"
import type { RunState } from "./workflow.js"

export type ProofTarget = {
  obligationId: string
  name: string
  statement: string
  strengthRisks: string[]
  semanticIds: string[]
}

type ObligationArtifact = {
  theorem_obligations?: Array<{
    obligation_id?: string
    lean_statement_sketch?: string
    strength_risks?: string[]
    semantic_claim_ids?: string[]
  }>
}

async function latestObligationPath(run: RunState): Promise<string> {
  const dirRelative = `${run.artifactRoot}/theorems`
  const files = (await readdir(resolve(REPO_ROOT, dirRelative))) as string[]
  const candidates = files
    .map((name) => ({ name, m: name.match(/^obligations-v(\d+)\.json$/) }))
    .filter((x): x is { name: string; m: RegExpMatchArray } => x.m !== null)
    .map((x) => ({ name: x.name, version: Number(x.m[1]!) }))
    .sort((a, b) => b.version - a.version)

  if (candidates.length === 0) {
    throw new Error(`No theorem obligation artifact under ${dirRelative}`)
  }

  return `${dirRelative}/${candidates[0]!.name}`
}

export function theoremDeclarationNames(source: string): Set<string> {
  return new Set(
    [...source.matchAll(/^[ \t]*theorem\s+([A-Za-z_][A-Za-z0-9_'.]*)/gm)]
      .flatMap((match) => {
        const name = match[1]
        return name === undefined ? [] : [name]
      }),
  )
}

export async function proofTargets(run: RunState): Promise<ProofTarget[]> {
  const obligationPath = await latestObligationPath(run)
  const artifact = JSON.parse(
    await readFile(resolve(REPO_ROOT, obligationPath), "utf8"),
  ) as ObligationArtifact

  const contract = validateTheoremObligationDocument(artifact)
  if (contract.issues.length > 0) {
    throw new Error(
      `Invalid theorem obligation contract in ${obligationPath}: ${contract.issues.join(" | ")}`,
    )
  }

  const targets: ProofTarget[] = []
  const obligationByName = new Map<string, { id: string; risks: string[]; semanticIds: string[] }>()
  for (const obligation of artifact.theorem_obligations ?? []) {
    const names = [...(obligation.lean_statement_sketch ?? "").matchAll(
      /^[ \t]*theorem\s+([A-Za-z_][A-Za-z0-9_'.]*)\b/gm,
    )]
    for (const match of names) {
      obligationByName.set(match[1]!, {
        id: obligation.obligation_id ?? "UNKNOWN",
        risks: obligation.strength_risks ?? [],
        semanticIds: obligation.semantic_claim_ids ?? [],
      })
    }
  }
  for (const theorem of contract.declarations) {
    const obligation = obligationByName.get(theorem.name)
    targets.push({
      obligationId: obligation?.id ?? "UNKNOWN",
      name: theorem.name,
      statement: theorem.canonicalStatement,
      strengthRisks: obligation?.risks ?? [],
      semanticIds: obligation?.semanticIds ?? [],
    })
  }

  if (targets.length === 0) {
    throw new Error(`No Lean theorem declarations found in ${obligationPath}`)
  }

  return targets
}

export async function proofStatementContractIssues(run: RunState): Promise<string[]> {
  const obligationPath = await latestObligationPath(run)
  const obligation = JSON.parse(
    await readFile(resolve(REPO_ROOT, obligationPath), "utf8"),
  ) as unknown
  const contract = validateTheoremObligationDocument(obligation)
  if (contract.issues.length > 0) return contract.issues
  const path = proofArtifactPath(run)
  if (!(await fileExists(path))) return ["proof artifact does not exist"]
  const proofSource = await readFile(resolve(REPO_ROOT, path), "utf8")
  return compareProofWithApprovedTheorems(contract.declarations, proofSource)
}

export function proofArtifactPath(run: RunState): string {
  return artifactContractForRun(run).outputPath
}

export function verifiedProofArtifactPath(run: RunState): string {
  if (run.stage === "PROOF_GENERATION") return proofArtifactPath(run)
  const completedAttempt = stageAttempt(run, "PROOF_GENERATION") - 1
  if (completedAttempt < 1) {
    throw new Error(`Run ${run.runId} has no completed proof-generation attempt`)
  }
  return `${run.artifactRoot}/lean/${run.leanModuleName}Proofs-v${completedAttempt}.lean`
}

async function fileExists(repoRelativePath: string): Promise<boolean> {
  try {
    await access(resolve(REPO_ROOT, repoRelativePath))
    return true
  } catch {
    return false
  }
}

export async function declaredProofNames(run: RunState): Promise<Set<string>> {
  const path = proofArtifactPath(run)
  if (!(await fileExists(path))) return new Set()
  const text = await readFile(resolve(REPO_ROOT, path), "utf8")
  return theoremDeclarationNames(text)
}

export async function nextProofTarget(run: RunState): Promise<ProofTarget | undefined> {
  const targets = await proofTargets(run)
  const declared = await declaredProofNames(run)
  return targets.find((target) => !declared.has(target.name))
}

export async function proofTargetSummary(run: RunState): Promise<{
  total: number
  declared: number
  remaining: number
  next?: ProofTarget
  missing: ProofTarget[]
}> {
  const targets = await proofTargets(run)
  const declared = await declaredProofNames(run)
  const missing = targets.filter((target) => !declared.has(target.name))

  return {
    total: targets.length,
    declared: targets.length - missing.length,
    remaining: missing.length,
    next: missing[0],
    missing,
  }
}
