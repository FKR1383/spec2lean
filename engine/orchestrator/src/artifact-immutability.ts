import { readFile, readdir } from "node:fs/promises"
import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"

type ReviewRecord = {
  artifacts?: Array<{ relativePath?: unknown }>
}

async function runStates(): Promise<RunState[]> {
  const states: RunState[] = []
  for (const entry of await readdir(resolve(REPO_ROOT, "runs"), { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.isSymbolicLink() || entry.name === "batches") continue
    try {
      states.push(JSON.parse(
        await readFile(resolve(REPO_ROOT, "runs", entry.name, "run.json"), "utf8"),
      ) as RunState)
    } catch {
      // A missing/incomplete run file cannot grant write authority.
    }
  }
  return states
}

async function reviewedArtifactPaths(directory = resolve(REPO_ROOT, "reviews")): Promise<Set<string>> {
  const paths = new Set<string>()
  const visit = async (current: string): Promise<void> => {
    let entries
    try {
      entries = await readdir(current, { withFileTypes: true })
    } catch {
      return
    }
    for (const entry of entries) {
      if (entry.isSymbolicLink()) continue
      const path = resolve(current, entry.name)
      if (entry.isDirectory()) {
        await visit(path)
        continue
      }
      if (!entry.isFile() || !entry.name.endsWith(".json")) continue
      try {
        const record = JSON.parse(await readFile(path, "utf8")) as ReviewRecord
        for (const artifact of record.artifacts ?? []) {
          if (typeof artifact.relativePath === "string") paths.add(artifact.relativePath)
        }
      } catch {
        // Malformed files cannot grant replacement permission.
      }
    }
  }
  await visit(directory)
  return paths
}

/**
 * Candidate revisions may be repaired only while the exact producing session
 * is active. Successful or reviewed paths are permanently write-once.
 */
export async function candidateReplacementIssue(
  relativePath: string,
  sessionId: string,
): Promise<string | undefined> {
  const runs = await runStates()
  if (runs.some((run) => (run.executions ?? []).some((execution) =>
    (execution.publishedArtifacts ?? []).some((artifact) => artifact.path === relativePath)
  ))) {
    return `artifact revision was successfully published and is immutable: ${relativePath}`
  }
  if ((await reviewedArtifactPaths()).has(relativePath)) {
    return `artifact revision is bound by a review record and is immutable: ${relativePath}`
  }
  const owned = runs.some((run) =>
    run.activeExecution?.sessionId === sessionId &&
    run.activeExecution.expectedArtifact === relativePath
  )
  return owned
    ? undefined
    : `replacement is allowed only for the exact unpublished artifact owned by active session ${sessionId}`
}
