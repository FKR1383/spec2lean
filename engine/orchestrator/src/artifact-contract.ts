import type {
  FormalizationStage,
  RunState,
} from "./workflow.js"

export function makeUnitSlug(
  unit: string,
): string {
  return unit
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

export function makeLeanModuleName(
  unit: string,
): string {
  const parts =
    unit
      .trim()
      .split(/[^A-Za-z0-9]+/)
      .filter(Boolean)

  if (parts.length === 0) {
    throw new Error(
      `Cannot derive Lean module name from unit: ${unit}`,
    )
  }

  return parts
    .map(
      (part) =>
        part.charAt(0).toUpperCase() +
        part.slice(1),
    )
    .join("")
}

export function stageAttempt(
  run: RunState,
  stage: FormalizationStage,
): number {
  return (
    (run.executions ?? [])
      .filter(
        (execution) =>
          execution.stage === stage &&
          (
            execution.outcome === "SUCCESS" ||
            execution.outcome === "REVISE" ||
            (
              execution.outcome === "RETRY" &&
              stage !== "PROOF_GENERATION" &&
              execution.artifactProduced !== false
            )
          ),
      )
      .length + 1
  )
}

export type ArtifactContract = {
  attempt: number
  outputPath: string
}

export function artifactContractForRun(
  run: RunState,
): ArtifactContract {
  let attempt =
    stageAttempt(
      run,
      run.stage,
    )

  const root =
    run.artifactRoot

  const leanName =
    run.leanModuleName

  if (
    run.stage === "SEMANTIC_EXTRACTION" &&
    run.semanticV2?.mode === "LEGACY_FALLBACK" &&
    run.semanticV2.current !== undefined &&
    attempt <= run.semanticV2.current.attempt
  ) {
    // Preserve the failed/superseded delta attempt and any partial
    // deterministic outputs. The legacy agent always receives a fresh
    // immutable semantics revision.
    attempt = run.semanticV2.current.attempt + 1
  }

  let outputPath: string

  switch (run.stage) {
    case "ARCHITECTURE":
      outputPath =
        `${root}/architecture/foundation-v${attempt}.md`
      break

    case "ARCHITECTURE_CRITIQUE":
      outputPath =
        `${root}/reviews/architecture-critic-v${attempt}.md`
      break

    case "SOURCE_CURATION":
      outputPath =
        `${root}/source-bundles/source-bundle-v${attempt}.json`
      break

    case "SEMANTIC_EXTRACTION":
      outputPath = run.semanticV2?.mode === "DELTA_FAST_PATH"
        ? `${root}/semantics/semantic-delta-v${attempt}.json`
        : `${root}/semantics/semantics-v${attempt}.json`
      break

    case "SEMANTIC_CRITIQUE":
      outputPath =
        `${root}/reviews/semantics-critic-v${attempt}.md`
      break

    case "LEAN_FORMALIZATION":
      outputPath =
        `${root}/lean/${leanName}-v${attempt}.lean`
      break

    case "LEAN_MAPPING_CRITIQUE":
      outputPath =
        `${root}/reviews/lean-mapping-critic-v${attempt}.md`
      break

    case "THEOREM_GENERATION":
      outputPath =
        `${root}/theorems/obligations-v${attempt}.json`
      break

    case "THEOREM_STRENGTH_CRITIQUE":
      outputPath =
        `${root}/reviews/theorem-strength-critic-v${attempt}.md`
      break

    case "PROOF_GENERATION":
      outputPath =
        `${root}/lean/${leanName}Proofs-v${attempt}.lean`
      break

    case "FINAL_CRITIQUE":
      outputPath =
        `${root}/reviews/final-critic-v${attempt}.md`
      break

    default:
      throw new Error(
        `No artifact contract for stage ${run.stage}`,
      )
  }

  return {
    attempt,
    outputPath,
  }
}
