import {
  PIPELINE_POOLS,
  type PipelinePool,
  type PipelineWorkerCaps,
} from "./batch-store.js"
import type { FormalizationStage } from "./workflow.js"

export const DEFAULT_PIPELINE_WORKER_CAPS: PipelineWorkerCaps = {
  architecture: 1,
  evidence: 2,
  semantic: 2,
  lean: 2,
  theorem: 1,
  proof: 2,
  critic: 2,
}

const STAGE_POOLS: Partial<Record<FormalizationStage, PipelinePool>> = {
  ARCHITECTURE: "architecture",
  SOURCE_CURATION: "evidence",
  SEMANTIC_EXTRACTION: "semantic",
  LEAN_FORMALIZATION: "lean",
  THEOREM_GENERATION: "theorem",
  PROOF_GENERATION: "proof",
  ARCHITECTURE_CRITIQUE: "critic",
  SEMANTIC_CRITIQUE: "critic",
  LEAN_MAPPING_CRITIQUE: "critic",
  THEOREM_STRENGTH_CRITIQUE: "critic",
  FINAL_CRITIQUE: "critic",
}

export function poolForStage(stage: FormalizationStage): PipelinePool | undefined {
  return STAGE_POOLS[stage]
}

export type PipelineCandidate<T> = {
  value: T
  pool: PipelinePool
  readySince: string
  stableKey: string
}

export function selectPipelineCandidate<T>(
  candidates: readonly PipelineCandidate<T>[],
  poolActive: ReadonlyMap<PipelinePool, number>,
  workerCaps: PipelineWorkerCaps,
): PipelineCandidate<T> | undefined {
  return candidates
    .filter((candidate) =>
      (poolActive.get(candidate.pool) ?? 0) < workerCaps[candidate.pool]
    )
    .sort((left, right) =>
      Date.parse(left.readySince) - Date.parse(right.readySince) ||
      left.stableKey.localeCompare(right.stableKey)
    )[0]
}

export function parsePipelineWorkerCaps(
  raw: string | undefined,
  fallback: PipelineWorkerCaps = DEFAULT_PIPELINE_WORKER_CAPS,
): PipelineWorkerCaps {
  const result = { ...fallback }
  if (raw === undefined || raw.trim().length === 0) return result

  const seen = new Set<PipelinePool>()
  for (const assignment of raw.split(",")) {
    const match = assignment.trim().match(/^([a-z]+)=(\d+)$/)
    if (match?.[1] === undefined || match[2] === undefined) {
      throw new Error(`Invalid --stage-workers assignment: ${assignment}`)
    }
    const pool = match[1] as PipelinePool
    if (!PIPELINE_POOLS.includes(pool)) {
      throw new Error(`Unknown pipeline pool: ${pool}`)
    }
    if (seen.has(pool)) throw new Error(`Duplicate pipeline pool: ${pool}`)
    seen.add(pool)
    const value = Number(match[2])
    if (!Number.isInteger(value) || value < 0 || value > 8) {
      throw new Error(`Invalid worker cap for ${pool}: ${value} (range 0..8)`)
    }
    result[pool] = value
  }
  if (Object.values(result).every((value) => value === 0)) {
    throw new Error("At least one pipeline worker pool must be enabled")
  }
  return result
}
