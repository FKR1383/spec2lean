import { randomUUID } from "node:crypto"
import { access } from "node:fs/promises"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

import { loadBatch, saveBatch, type FormalizationBatch } from "./batch-store.js"
import { runBatch } from "./batch-runtime.js"
import { makeLeanModuleName, makeUnitSlug } from "./artifact-contract.js"
import { REPO_ROOT } from "./repo.js"
import { createRun } from "./run-service.js"
import { saveRun } from "./run-store.js"
import { ensureSourceIndex } from "./source-index.js"
import {
  DEFAULT_PIPELINE_AGENT_CAPS,
  pipelineAgentCapsIssues,
  parsePipelineAgentCaps,
  pipelineAgentWorkerCount,
} from "./pipeline-config.js"
import { snapshotPipelineDependencies } from "./pipeline-dependencies.js"
import { runPipelinedBatch } from "./pipeline-runtime.js"
import { transitionRun } from "./workflow.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function argumentsFor(name: string): string[] {
  return process.argv.flatMap((value, index) =>
    value === name && process.argv[index + 1] !== undefined
      ? [process.argv[index + 1]!]
      : [],
  )
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function positiveInteger(name: string, fallback: number, maximum?: number): number {
  const raw = argument(name)
  const value = raw === undefined ? fallback : Number(raw)
  if (!Number.isInteger(value) || value <= 0 || (maximum !== undefined && value > maximum)) {
    throw new Error(
      `Invalid positive integer for ${name}: ${raw ?? value}` +
      (maximum === undefined ? "" : ` (maximum ${maximum})`),
    )
  }
  return value
}

export function resolveWorkerCount(
  workersRaw: string | undefined,
  concurrencyRaw: string | undefined,
  fallback: number,
  maximum = 8,
): number {
  if (
    workersRaw !== undefined &&
    concurrencyRaw !== undefined &&
    workersRaw !== concurrencyRaw
  ) {
    throw new Error(
      `--workers and --concurrency disagree: ${workersRaw} versus ${concurrencyRaw}`,
    )
  }

  const raw = workersRaw ?? concurrencyRaw
  const value = raw === undefined ? fallback : Number(raw)
  if (!Number.isInteger(value) || value <= 0 || value > maximum) {
    throw new Error(`Invalid worker count: ${raw ?? value} (maximum ${maximum})`)
  }
  return value
}

function workerCount(fallback: number, maximum = 8): number {
  return resolveWorkerCount(
    argument("--workers"),
    argument("--concurrency"),
    fallback,
    maximum,
  )
}

export function parseBatchUnits(values: readonly string[]): string[] {
  const units = values
    .flatMap((value) => value.split(","))
    .map((value) => value.trim())
    .filter((value) => value.length > 0)

  if (units.length < 2) {
    throw new Error("A batch requires at least two units")
  }
  if (new Set(units).size !== units.length) {
    throw new Error("A batch cannot contain duplicate units")
  }
  if (new Set(units.map(makeUnitSlug)).size !== units.length) {
    throw new Error("Batch units collide after artifact-path normalization")
  }
  if (new Set(units.map(makeLeanModuleName)).size !== units.length) {
    throw new Error("Batch units collide after Lean-module normalization")
  }
  return units
}

async function createBatch(): Promise<FormalizationBatch> {
  const language = required("--language")
  const specVersion = required("--version")
  const inferredManifest = language.toLowerCase() === "ptx"
    ? `documents/sources/nvidia/ptx/${specVersion}/source-manifest.json`
    : undefined
  const sourceManifest = argument("--source-manifest") ?? inferredManifest
  if (!sourceManifest) throw new Error("--source-manifest is required for this language")

  try {
    await access(resolve(REPO_ROOT, sourceManifest))
  } catch {
    throw new Error(`Source manifest does not exist: ${sourceManifest}`)
  }
  await ensureSourceIndex({ language, specificationVersion: specVersion, sourceManifest })

  const units = parseBatchUnits([
    ...argumentsFor("--units"),
    ...argumentsFor("--unit"),
  ])
  const pipelineEnabled = process.argv.includes("--pipeline")
  if (pipelineEnabled && argument("--stage-workers") !== undefined) {
    throw new Error("--stage-workers was replaced by exact --agent-workers in agent-pinned pipeline mode")
  }
  const pipelineAgentCaps = pipelineEnabled
    ? parsePipelineAgentCaps(argument("--agent-workers"), DEFAULT_PIPELINE_AGENT_CAPS)
    : undefined
  const concurrency = workerCount(
    pipelineAgentCaps === undefined ? 2 : pipelineAgentWorkerCount(pipelineAgentCaps),
    pipelineEnabled ? 16 : 8,
  )
  const pipelineDependencies = pipelineEnabled
    ? await snapshotPipelineDependencies({
        language,
        specificationVersion: specVersion,
        sourceManifest,
      })
    : undefined
  const autoApprove = process.argv.includes("--auto-approve")
  const now = new Date().toISOString()
  const batchId = `${language}-${specVersion}-batch-${randomUUID().slice(0, 8)}`
    .replace(/[^A-Za-z0-9._-]/g, "-")
  const entries = []

  for (const unit of units) {
    const run = await createRun({
      language,
      specVersion,
      unit,
      sourceManifest,
      benchmarkAutoApprove: autoApprove,
    })
    const started = transitionRun(run, "ARCHITECTURE", `batch ${batchId} formalization start`)
    await saveRun(started)
    entries.push({ unit, runId: started.runId, lastObservedStage: started.stage })
  }

  const batch: FormalizationBatch = {
    schemaVersion: 1,
    batchId,
    language,
    specVersion,
    sourceManifest,
    autoApprove,
    concurrency,
    executionMode: pipelineEnabled ? "STAGE_PIPELINE" : "RUN_PARALLEL",
    createdAt: now,
    updatedAt: now,
    runs: entries,
  }
  if (pipelineEnabled) {
    batch.pipeline = {
      schemaVersion: 2,
      schedulingMode: "AGENT_PINNED",
      globalWorkers: concurrency,
      agentCaps: pipelineAgentCaps!,
      dependencies: pipelineDependencies!,
      startedAt: now,
      updatedAt: now,
      leases: {},
      runs: Object.fromEntries(entries.map((entry) => [entry.runId, {
        totalTicks: 0,
        consecutiveRetries: 0,
      }])),
      jobs: [],
    }
  }
  await saveBatch(batch)
  return batch
}

async function ensurePipelineState(batch: FormalizationBatch): Promise<void> {
  if (batch.pipeline !== undefined) return
  if (argument("--stage-workers") !== undefined) {
    throw new Error("--stage-workers was replaced by exact --agent-workers in agent-pinned pipeline mode")
  }
  const now = new Date().toISOString()
  const agentCaps = parsePipelineAgentCaps(
    argument("--agent-workers"),
    DEFAULT_PIPELINE_AGENT_CAPS,
  )
  batch.executionMode = "STAGE_PIPELINE"
  batch.concurrency = pipelineAgentWorkerCount(agentCaps)
  batch.pipeline = {
    schemaVersion: 2,
    schedulingMode: "AGENT_PINNED",
    globalWorkers: batch.concurrency,
    agentCaps,
    dependencies: await snapshotPipelineDependencies({
      language: batch.language,
      specificationVersion: batch.specVersion,
      sourceManifest: batch.sourceManifest,
    }),
    startedAt: now,
    updatedAt: now,
    leases: {},
    runs: Object.fromEntries(batch.runs.map((entry) => [entry.runId, {
      totalTicks: 0,
      consecutiveRetries: 0,
    }])),
    jobs: [],
  }
}

async function main(): Promise<void> {
  const batch = argument("--batch") === undefined
    ? await createBatch()
    : await loadBatch(required("--batch"))
  const pipelineEnabled =
    process.argv.includes("--pipeline") || batch.executionMode === "STAGE_PIPELINE"
  if (pipelineEnabled) await ensurePipelineState(batch)
  if (batch.pipeline !== undefined && batch.pipeline.schemaVersion !== 2) {
    throw new Error("Unsupported pre-agent-pinned pipeline state; create a new pipeline batch")
  }
  if (batch.pipeline !== undefined) {
    const capIssues = pipelineAgentCapsIssues(batch.pipeline.agentCaps)
    if (
      batch.pipeline.schedulingMode !== "AGENT_PINNED" ||
      capIssues.length > 0
    ) {
      throw new Error(
        `Invalid agent-pinned pipeline state: ${[
          ...(batch.pipeline.schedulingMode === "AGENT_PINNED"
            ? []
            : [`invalid scheduling mode: ${String(batch.pipeline.schedulingMode)}`]),
          ...capIssues,
        ].join(" | ")}`,
      )
    }
  }
  const options = {
    concurrency: workerCount(batch.concurrency, pipelineEnabled ? 16 : 8),
    maxTicks: positiveInteger("--max-ticks", 50),
    maxStageRetries: positiveInteger("--max-stage-retries", 4),
    maxStageRevisions: positiveInteger("--max-stage-revisions", 3),
    providerRetryBudgetSeconds: positiveInteger("--provider-retry-budget-seconds", 60),
  }
  batch.concurrency = options.concurrency
  if (batch.pipeline !== undefined) {
    batch.pipeline.globalWorkers = options.concurrency
    const agentWorkers = argument("--agent-workers")
    if (agentWorkers !== undefined) {
      batch.pipeline.agentCaps = parsePipelineAgentCaps(
        agentWorkers,
        batch.pipeline.agentCaps,
      )
    }
    await saveBatch(batch)
  }

  console.log(JSON.stringify({
    ok: true,
    batchId: batch.batchId,
    autoApprove: batch.autoApprove,
    executionMode: batch.executionMode ?? "RUN_PARALLEL",
    concurrency: options.concurrency,
    schedulingMode: batch.pipeline?.schedulingMode,
    agentWorkers: batch.pipeline?.agentCaps,
    pinnedDependencies: batch.pipeline?.dependencies,
    runs: batch.runs,
  }, null, 2))

  const result = pipelineEnabled
    ? await runPipelinedBatch(batch, {
        globalWorkers: options.concurrency,
        maxTicks: options.maxTicks,
        maxStageRetries: options.maxStageRetries,
        maxStageRevisions: options.maxStageRevisions,
        providerRetryBudgetSeconds: options.providerRetryBudgetSeconds,
      })
    : await runBatch(batch, options)
  console.log(JSON.stringify({
    ok: result.exitCode === 0,
    batchId: batch.batchId,
    status: result.status,
    runs: result.batch.runs,
  }, null, 2))
  process.exitCode = result.exitCode
}

if (
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  await main()
}
