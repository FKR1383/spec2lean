import { mkdir, rm, writeFile } from "node:fs/promises"
import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"

const LOCK_ROOT = resolve(REPO_ROOT, ".spec2lean-cache/locks")

function safeLockName(name: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(name)) {
    throw new Error(`Unsafe repository lock name: ${name}`)
  }
  return name
}

async function delay(milliseconds: number): Promise<void> {
  await new Promise<void>((resolvePromise) => {
    setTimeout(resolvePromise, milliseconds)
  })
}

/**
 * Cross-process lock for small repository-wide critical sections.
 *
 * The lock lives only in the gitignored cache. A crashed holder deliberately
 * leaves a visible lock instead of allowing another process to guess that a
 * concurrent Lean-package mutation is safe.
 */
export async function withRepositoryLock<T>(
  name: string,
  operation: () => Promise<T>,
  options: { timeoutMs?: number; pollMs?: number } = {},
): Promise<T> {
  const lockName = safeLockName(name)
  const timeoutMs = options.timeoutMs ?? 5 * 60_000
  const pollMs = options.pollMs ?? 200
  const lockPath = resolve(LOCK_ROOT, `${lockName}.lock`)
  const startedAt = Date.now()

  await mkdir(LOCK_ROOT, { recursive: true })

  while (true) {
    try {
      await mkdir(lockPath)
      break
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code
      if (code !== "EEXIST") throw error
      if (Date.now() - startedAt >= timeoutMs) {
        throw new Error(
          `Timed out waiting for repository lock ${lockName}; ` +
          `if no Spec2Lean process is running, remove ${lockPath}`,
        )
      }
      await delay(pollMs)
    }
  }

  try {
    await writeFile(
      resolve(lockPath, "owner.json"),
      `${JSON.stringify({ pid: process.pid, acquiredAt: new Date().toISOString() }, null, 2)}\n`,
      "utf8",
    )
    return await operation()
  } finally {
    await rm(lockPath, { recursive: true, force: true })
  }
}
