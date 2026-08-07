import {
  mkdir,
  readFile,
  rename,
  writeFile,
} from "node:fs/promises"

import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"

const RUNS_ROOT = resolve(REPO_ROOT, "runs")

function runDirectory(runId: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(runId)) {
    throw new Error(`Unsafe run ID: ${runId}`)
  }

  return resolve(RUNS_ROOT, runId)
}

export function runStatePath(runId: string): string {
  return resolve(runDirectory(runId), "run.json")
}

export async function saveRun(
  run: RunState,
): Promise<void> {
  const directory = runDirectory(run.runId)
  const destination = runStatePath(run.runId)
  const temporary = `${destination}.tmp`

  await mkdir(directory, {
    recursive: true,
  })

  const body =
    `${JSON.stringify(run, null, 2)}\n`

  await writeFile(
    temporary,
    body,
    "utf8",
  )

  await rename(
    temporary,
    destination,
  )
}

export async function loadRun(
  runId: string,
): Promise<RunState> {
  const body = await readFile(
    runStatePath(runId),
    "utf8",
  )

  return JSON.parse(body) as RunState
}
