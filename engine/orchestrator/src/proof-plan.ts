import { access, readFile, readdir } from "node:fs/promises"
import { resolve } from "node:path"

import { artifactContractForRun } from "./artifact-contract.js"
import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"

export type ProofTarget = {
  obligationId: string
  name: string
  statement: string
  strengthRisks: string[]
}

type ObligationArtifact = {
  theorem_obligations?: Array<{
    obligation_id?: string
    lean_statement_sketch?: string
    strength_risks?: string[]
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

function splitTheoremSketch(sketch: string): Array<{ name: string; statement: string }> {
  const matches = [...sketch.matchAll(/^[ \t]*theorem\s+([A-Za-z0-9_']+)/gm)]
  return matches.map((match, index) => {
    const start = match.index ?? 0
    const end = index + 1 < matches.length ? (matches[index + 1]!.index ?? sketch.length) : sketch.length
    const statement = sketch.slice(start, end).trim().replace(/\n-- supporting[\s\S]*$/i, "").trim()
    return { name: match[1]!, statement }
  })
}

export function theoremDeclarationNames(source: string): Set<string> {
  return new Set(
    [...source.matchAll(/^[ \t]*theorem\s+([A-Za-z0-9_']+)/gm)]
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

  const targets: ProofTarget[] = []
  for (const obligation of artifact.theorem_obligations ?? []) {
    const id = obligation.obligation_id ?? "UNKNOWN"
    const risks = obligation.strength_risks ?? []
    for (const theorem of splitTheoremSketch(obligation.lean_statement_sketch ?? "")) {
      targets.push({
        obligationId: id,
        name: theorem.name,
        statement: theorem.statement,
        strengthRisks: risks,
      })
    }
  }

  if (targets.length === 0) {
    throw new Error(`No Lean theorem declarations found in ${obligationPath}`)
  }

  return targets
}

export function proofArtifactPath(run: RunState): string {
  return artifactContractForRun(run).outputPath
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
