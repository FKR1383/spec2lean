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
}

export type FormalizationBatch = {
  schemaVersion: 1
  batchId: string
  language: string
  specVersion: string
  sourceManifest: string
  autoApprove: boolean
  concurrency: number
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
