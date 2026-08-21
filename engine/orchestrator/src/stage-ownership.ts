import type { FormalizationStage, RunState } from "./workflow.js"

export type StageArtifactArea =
  | "architecture"
  | "source-bundles"
  | "semantics"
  | "lean"
  | "theorems"
  | "reviews"

const CRITIC_VISIBLE_AREAS:
  Partial<Record<FormalizationStage, readonly StageArtifactArea[]>> = {
    ARCHITECTURE_CRITIQUE: ["architecture", "reviews"],
    SEMANTIC_CRITIQUE: ["architecture", "source-bundles", "semantics", "reviews"],
    LEAN_MAPPING_CRITIQUE: ["architecture", "semantics", "lean", "reviews"],
    THEOREM_STRENGTH_CRITIQUE: ["architecture", "semantics", "lean", "theorems", "reviews"],
    FINAL_CRITIQUE: ["architecture", "source-bundles", "semantics", "lean", "theorems", "reviews"],
  }

/** Exact unit-artifact areas a critic is authorized to inspect at its stage. */
export function criticVisibleArtifactAreas(
  stage: FormalizationStage,
): readonly StageArtifactArea[] {
  return CRITIC_VISIBLE_AREAS[stage] ?? []
}

function referencedCandidatePaths(review: string): string[] {
  return [...review.matchAll(/candidates\/[A-Za-z0-9._+\-/]+/g)]
    .map((match) => match[0]!.replace(/[.,;:]+$/, ""))
}

/**
 * Prevent a critic from routing an upstream producer against a stale
 * downstream artifact. This is deliberately path-based: prose may discuss a
 * future Lean mapping, but a semantic review may not cite an existing Lean or
 * theorem candidate as the defect that semantic extraction must repair.
 */
export function criticStageOwnershipIssues(
  run: Pick<RunState, "stage" | "artifactRoot">,
  review: string,
): string[] {
  const allowed = new Set(criticVisibleArtifactAreas(run.stage))
  if (allowed.size === 0) return []

  const issues: string[] = []
  const prefix = `${run.artifactRoot}/`
  for (const path of referencedCandidatePaths(review)) {
    if (!path.startsWith(prefix)) {
      issues.push(`critic review cites an artifact outside the current unit: ${path}`)
      continue
    }
    const relative = path.slice(prefix.length)
    const area = relative.split("/")[0] as StageArtifactArea | undefined
    if (area === undefined || !allowed.has(area)) {
      issues.push(
        `${run.stage} review cites downstream/out-of-scope artifact ${path}; ` +
        `allowed unit areas are ${[...allowed].join(", ")}`,
      )
      continue
    }
    if (
      run.stage === "THEOREM_STRENGTH_CRITIQUE" &&
      area === "lean" &&
      /Proofs-v\d+\.lean$/i.test(path)
    ) {
      issues.push(
        `theorem-strength review cites downstream proof artifact ${path}; ` +
        "proofs do not exist at this review boundary",
      )
    }
  }
  return [...new Set(issues)].sort((left, right) => left.localeCompare(right))
}
