import {
  PIPELINE_AGENTS,
  type PipelineAgent,
  type PipelineAgentCaps,
  type PipelinePool,
} from "./batch-store.js"
import { executionAgentForRun } from "./runner.js"
import { planForRun } from "./stage-plan.js"
import type { FormalizationStage, RunState } from "./workflow.js"

export const DEFAULT_PIPELINE_AGENT_CAPS: PipelineAgentCaps = Object.fromEntries(
  PIPELINE_AGENTS.map((agent) => [agent, 1]),
) as PipelineAgentCaps

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
  agent: PipelineAgent
  readySince: string
  stableKey: string
}

export function selectPipelineCandidate<T>(
  candidates: readonly PipelineCandidate<T>[],
  agent: PipelineAgent,
): PipelineCandidate<T> | undefined {
  return candidates
    .filter((candidate) => candidate.agent === agent)
    .sort((left, right) =>
      Date.parse(left.readySince) - Date.parse(right.readySince) ||
      left.stableKey.localeCompare(right.stableKey)
    )[0]
}

export function pipelineAgentForRun(run: RunState): PipelineAgent | undefined {
  if (poolForStage(run.stage) === undefined) return undefined
  const plan = planForRun(run)
  const agent = executionAgentForRun(run, plan.agent)
  if (!PIPELINE_AGENTS.includes(agent as PipelineAgent)) {
    throw new Error(`Executable stage ${run.stage} selected unregistered pipeline agent ${agent}`)
  }
  return agent as PipelineAgent
}

export function parsePipelineAgentCaps(
  raw: string | undefined,
  fallback: PipelineAgentCaps = DEFAULT_PIPELINE_AGENT_CAPS,
): PipelineAgentCaps {
  const result = { ...fallback }
  if (raw === undefined || raw.trim().length === 0) return result

  const seen = new Set<PipelineAgent>()
  for (const assignment of raw.split(",")) {
    const match = assignment.trim().match(/^([a-z][a-z0-9-]*)=(\d+)$/)
    if (match?.[1] === undefined || match[2] === undefined) {
      throw new Error(`Invalid --agent-workers assignment: ${assignment}`)
    }
    const agent = match[1] as PipelineAgent
    if (!PIPELINE_AGENTS.includes(agent)) {
      throw new Error(`Unknown pipeline agent: ${agent}`)
    }
    if (seen.has(agent)) throw new Error(`Duplicate pipeline agent: ${agent}`)
    seen.add(agent)
    const value = Number(match[2])
    if (!Number.isInteger(value) || value < 0 || value > 8) {
      throw new Error(`Invalid worker cap for ${agent}: ${value} (range 0..8)`)
    }
    result[agent] = value
  }
  if (Object.values(result).every((value) => value === 0)) {
    throw new Error("At least one pipeline agent worker must be enabled")
  }
  return result
}

export function pipelineAgentWorkerCount(caps: PipelineAgentCaps): number {
  return Object.values(caps).reduce((total, value) => total + value, 0)
}

export function pipelineAgentCapsIssues(value: unknown): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return ["agentCaps must be an object"]
  }
  const record = value as Record<string, unknown>
  const issues = Object.keys(record)
    .filter((agent) => !PIPELINE_AGENTS.includes(agent as PipelineAgent))
    .map((agent) => `unknown agent cap: ${agent}`)
  for (const agent of PIPELINE_AGENTS) {
    const cap = record[agent]
    if (!Number.isInteger(cap) || (cap as number) < 0 || (cap as number) > 8) {
      issues.push(`invalid agent cap ${agent}: ${String(cap)}`)
    }
  }
  if (
    issues.length === 0 &&
    PIPELINE_AGENTS.every((agent) => record[agent] === 0)
  ) issues.push("at least one agent cap must be positive")
  return issues.sort((left, right) => left.localeCompare(right))
}

export function pipelineAgentWorkerLayout(caps: PipelineAgentCaps): Array<{
  id: string
  agent: PipelineAgent
}> {
  return PIPELINE_AGENTS.flatMap((agent) =>
    Array.from({ length: caps[agent] }, (_, index) => ({
      id: `${agent}-${index + 1}`,
      agent,
    }))
  )
}
