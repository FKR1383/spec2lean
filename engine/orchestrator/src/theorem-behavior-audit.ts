import { createHash } from "node:crypto"

import type { CorrectnessKind } from "./theorem-contract.js"

export type LeanBehaviorBranch = {
  branchId: string
  definition: string
  pattern: string
}

export type BehavioralTheoremTarget = {
  name: string
  statement: string
  correctnessKind?: CorrectnessKind
}

type AuditEntry = {
  name?: unknown
  correctnessKind?: unknown
  status?: unknown
  branchIdsChecked?: unknown
  counterexample?: unknown
}

function branchId(definition: string, pattern: string): string {
  return `LEAN-BRANCH-${createHash("sha256")
    .update(`${definition}\0${pattern}`)
    .digest("hex")
    .slice(0, 12)}`
}

/** Extract stable IDs for explicit match-equation branches inside Lean defs. */
export function leanBehaviorBranches(source: string): LeanBehaviorBranch[] {
  const branches: LeanBehaviorBranch[] = []
  let definition: string | undefined
  let definitionIndent = 0

  for (const line of source.split(/\r?\n/)) {
    const declaration = line.match(/^(\s*)(?:protected\s+)?(?:def|abbrev)\s+([A-Za-z_][A-Za-z0-9_']*)\b/)
    if (declaration?.[2] !== undefined) {
      definition = declaration[2]
      definitionIndent = declaration[1]!.length
      continue
    }

    if (definition === undefined) continue
    const nonEmpty = line.trim()
    const indent = line.length - line.trimStart().length
    if (
      nonEmpty.length > 0 &&
      indent <= definitionIndent &&
      /^(?:def|abbrev|theorem|lemma|inductive|structure|namespace|end)\b/.test(nonEmpty)
    ) {
      definition = undefined
      continue
    }

    const branch = line.match(/^\s*\|\s*(.+?)\s*=>/)
    if (branch?.[1] === undefined) continue
    const pattern = branch[1].replace(/\s+/g, " ").trim()
    branches.push({
      branchId: branchId(definition, pattern),
      definition,
      pattern,
    })
  }

  return [...new Map(branches.map((branch) => [branch.branchId, branch])).values()]
}

export function requiredBehaviorBranches(
  target: BehavioralTheoremTarget,
  branches: readonly LeanBehaviorBranch[],
): LeanBehaviorBranch[] {
  return branches.filter((branch) =>
    new RegExp(`\\b${branch.definition.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`)
      .test(target.statement)
  )
}

function auditEntries(review: string): { entries: AuditEntry[]; issues: string[] } {
  const blocks = [...review.matchAll(
    /<!--\s*SPEC2LEAN_THEOREM_BEHAVIOR_AUDIT\s*([\s\S]*?)-->/g,
  )]
  if (blocks.length !== 1) {
    return {
      entries: [],
      issues: ["theorem-strength review must contain exactly one SPEC2LEAN_THEOREM_BEHAVIOR_AUDIT block"],
    }
  }
  try {
    const parsed = JSON.parse(blocks[0]![1]!.trim()) as {
      schemaVersion?: unknown
      entries?: unknown
    }
    if (parsed.schemaVersion !== 1 || !Array.isArray(parsed.entries)) {
      return {
        entries: [],
        issues: ["theorem behavior audit must use schemaVersion=1 and an entries array"],
      }
    }
    return { entries: parsed.entries as AuditEntry[], issues: [] }
  } catch (error) {
    return {
      entries: [],
      issues: [`theorem behavior audit is invalid JSON: ${error instanceof Error ? error.message : String(error)}`],
    }
  }
}

/**
 * Bind behavioral theorem review to every explicit branch of every Lean
 * definition named in that theorem. A FAIL entry is a valid blocking review;
 * a PASS entry must account for the complete deterministic branch inventory.
 */
export function theoremBehaviorAuditIssues(
  review: string,
  targets: readonly BehavioralTheoremTarget[],
  branches: readonly LeanBehaviorBranch[],
): string[] {
  const requiredTargets = targets
    .map((target) => ({ target, branches: requiredBehaviorBranches(target, branches) }))
    .filter((entry) => entry.branches.length > 0)
  if (requiredTargets.length === 0) return []

  const parsed = auditEntries(review)
  const issues = [...parsed.issues]
  if (parsed.issues.length > 0) return issues
  const entries = new Map<string, AuditEntry>()
  for (const entry of parsed.entries) {
    if (typeof entry.name !== "string" || entry.name.length === 0) {
      issues.push("theorem behavior audit entry has no theorem name")
      continue
    }
    if (entries.has(entry.name)) issues.push(`duplicate theorem behavior audit entry: ${entry.name}`)
    entries.set(entry.name, entry)
  }

  let failed = false
  for (const { target, branches: required } of requiredTargets) {
    const entry = entries.get(target.name)
    if (entry === undefined) {
      issues.push(`theorem behavior audit is missing ${target.name}`)
      continue
    }
    if (entry.correctnessKind !== target.correctnessKind) {
      issues.push(`theorem behavior audit correctness kind mismatch for ${target.name}`)
    }
    if (entry.status !== "PASS" && entry.status !== "FAIL") {
      issues.push(`theorem behavior audit has invalid status for ${target.name}`)
      continue
    }
    const checked = new Set(
      Array.isArray(entry.branchIdsChecked)
        ? entry.branchIdsChecked.filter((value): value is string => typeof value === "string")
        : [],
    )
    for (const branch of required) {
      if (!checked.has(branch.branchId)) {
        issues.push(`${target.name} behavior audit omitted ${branch.branchId} (${branch.definition}: ${branch.pattern})`)
      }
    }
    if (entry.status === "PASS") {
      if (entry.counterexample !== "NONE_FOUND") {
        issues.push(`${target.name} PASS audit must state counterexample=NONE_FOUND`)
      }
    } else {
      failed = true
      if (typeof entry.counterexample !== "string" || entry.counterexample === "NONE_FOUND" || entry.counterexample.trim().length < 8) {
        issues.push(`${target.name} FAIL audit must provide a concrete counterexample`)
      }
    }
  }

  if (failed && !/\b(?:BLOCKER|MAJOR)(?:\s+count)?\s*[:=]\s*[1-9]\d*\b/i.test(review)) {
    issues.push("a failed theorem behavior audit requires a nonzero BLOCKER or MAJOR disposition")
  }
  return [...new Set(issues)].sort((left, right) => left.localeCompare(right))
}
