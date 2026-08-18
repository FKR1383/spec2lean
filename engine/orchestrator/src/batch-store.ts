import { randomUUID } from "node:crypto"
import { mkdir, readFile, rename, writeFile } from "node:fs/promises"
import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"

export type BatchRunEntry = {
  unit: string
  runId: string
  lastExitCode?: number
  lastObservedStage?: string
  lastError?: string
  lastStatus?:
    | "RUNNING"
    | "COMPLETE"
    | "WAITING_HUMAN"
    | "PARKED_SEMANTIC_REVIEW"
    | "STOPPED"
    | "BLOCKED"
    | "NO_RUNNABLE_WORK"
  blockingIssues?: string[]
}

export const PIPELINE_POOLS = [
  "architecture",
  "evidence",
  "semantic",
  "lean",
  "theorem",
  "proof",
  "critic",
] as const

export type PipelinePool = (typeof PIPELINE_POOLS)[number]

export const PIPELINE_AGENTS = [
  "spec-architect",
  "architecture-critic",
  "source-curator-fast",
  "source-curator",
  "semantic-extractor-delta",
  "semantic-extractor",
  "semantics-critic",
  "lean-formalizer",
  "lean-mapping-critic",
  "theorem-designer",
  "theorem-strength-critic",
  "proof-engineer",
  "final-critic",
] as const

export type PipelineAgent = (typeof PIPELINE_AGENTS)[number]

export type PipelineAgentCaps = Record<PipelineAgent, number>

export type PipelineDependency = {
  role: "SOURCE_MANIFEST" | "SOURCE_INDEX" | "SEMANTIC_PROFILE" | "SHARED_ENVIRONMENT"
  path: string
  sha256: string
}

export type PipelineLease = {
  leaseId: string
  workerId: string
  runId: string
  unit: string
  stage: string
  pool: PipelinePool
  agent: PipelineAgent
  leasedAt: string
}

export type PipelineJobMetric = {
  leaseId: string
  workerId: string
  runId: string
  unit: string
  pool: PipelinePool
  agent: PipelineAgent
  fromStage: string
  toStage: string
  queuedAt: string
  startedAt: string
  finishedAt: string
  queueWaitMs: number
  serviceMs: number
  outcome?: string
  productiveProgress?: boolean
  manifestCountBefore: number
  manifestCountAfter: number
  manifestGenerationIncludedInServiceMs: true
  error?: string
}

export type PipelineRunSchedulingState = {
  readyStage?: string
  readySince?: string
  totalTicks: number
  consecutiveRetries: number
  retryStage?: string
}

export type PipelineState = {
  schemaVersion: 2
  schedulingMode: "AGENT_PINNED"
  globalWorkers: number
  agentCaps: PipelineAgentCaps
  dependencies: PipelineDependency[]
  startedAt: string
  updatedAt: string
  controller?: { pid: number; claimedAt: string }
  leases: Record<string, PipelineLease>
  runs: Record<string, PipelineRunSchedulingState>
  jobs: PipelineJobMetric[]
}

export type FormalizationBatch = {
  schemaVersion: 1
  batchId: string
  language: string
  specVersion: string
  sourceManifest: string
  autoApprove: boolean
  concurrency: number
  executionMode?: "RUN_PARALLEL" | "STAGE_PIPELINE"
  pipeline?: PipelineState
  createdAt: string
  updatedAt: string
  lastRunFinishedAt?: string
  runs: BatchRunEntry[]
}

const BATCH_ROOT = resolve(REPO_ROOT, "runs/batches")

function safeBatchId(batchId: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(batchId)) {
    throw new Error(`Unsafe batch ID: ${batchId}`)
  }
  return batchId
}

export function batchPath(batchId: string): string {
  return resolve(BATCH_ROOT, `${safeBatchId(batchId)}.json`)
}

export async function saveBatch(batch: FormalizationBatch): Promise<void> {
  await mkdir(BATCH_ROOT, { recursive: true })
  const destination = batchPath(batch.batchId)
  const temporary = `${destination}.${process.pid}.${randomUUID()}.tmp`
  await writeFile(temporary, `${JSON.stringify(batch, null, 2)}\n`, "utf8")
  await rename(temporary, destination)
}

export async function loadBatch(batchId: string): Promise<FormalizationBatch> {
  const body = await readFile(batchPath(batchId), "utf8")
  return JSON.parse(body) as FormalizationBatch
}
