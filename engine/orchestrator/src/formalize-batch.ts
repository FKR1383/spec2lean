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
import { verifySourceManifest } from "./source-manifest.js"
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
  await verifySourceManifest(resolve(REPO_ROOT, sourceManifest))

  const units = parseBatchUnits([
    ...argumentsFor("--units"),
    ...argumentsFor("--unit"),
  ])
  const concurrency = positiveInteger("--concurrency", 2, 8)
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
    createdAt: now,
    updatedAt: now,
    runs: entries,
  }
  await saveBatch(batch)
  return batch
}

async function main(): Promise<void> {
  const batch = argument("--batch") === undefined
    ? await createBatch()
    : await loadBatch(required("--batch"))
  const options = {
    concurrency: positiveInteger("--concurrency", batch.concurrency, 8),
    maxTicks: positiveInteger("--max-ticks", 50),
    maxStageRetries: positiveInteger("--max-stage-retries", 4),
    maxStageRevisions: positiveInteger("--max-stage-revisions", 3),
    providerRetryBudgetSeconds: positiveInteger("--provider-retry-budget-seconds", 60),
  }
  batch.concurrency = options.concurrency

  console.log(JSON.stringify({
    ok: true,
    batchId: batch.batchId,
    autoApprove: batch.autoApprove,
    concurrency: options.concurrency,
    runs: batch.runs,
  }, null, 2))

  const result = await runBatch(batch, options)
  console.log(JSON.stringify({
    ok: result.exitCode === 0,
    batchId: batch.batchId,
    status: result.status,
    runs: batch.runs,
  }, null, 2))
  process.exitCode = result.exitCode
}

if (
  process.argv[1] !== undefined &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  await main()
}
