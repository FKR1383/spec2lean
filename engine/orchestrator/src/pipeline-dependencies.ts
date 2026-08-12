import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"

import type { PipelineDependency } from "./batch-store.js"
import { REPO_ROOT } from "./repo.js"
import { sourceIndexPath } from "./source-index.js"

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function repositoryPath(path: string): string {
  if (!path || path.includes("\0") || path.includes("\\") || isAbsolute(path)) {
    throw new Error(`Unsafe pipeline dependency path: ${path}`)
  }
  const absolute = resolve(REPO_ROOT, path)
  const relation = relative(REPO_ROOT, absolute)
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`Pipeline dependency escapes repository: ${path}`)
  }
  return absolute
}

async function optionalDependency(
  role: PipelineDependency["role"],
  path: string,
): Promise<PipelineDependency | undefined> {
  try {
    const data = await readFile(repositoryPath(path))
    return { role, path, sha256: sha256(data) }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined
    throw error
  }
}

/** Captures immutable language-front-end inputs before any unit is scheduled. */
export async function snapshotPipelineDependencies(input: {
  language: string
  specificationVersion: string
  sourceManifest: string
}): Promise<PipelineDependency[]> {
  const dependencies: Array<PipelineDependency | undefined> = [
    await optionalDependency("SOURCE_MANIFEST", input.sourceManifest),
    await optionalDependency(
      "SOURCE_INDEX",
      sourceIndexPath(input.language, input.specificationVersion),
    ),
  ]

  const profilePath =
    `language_packs/${input.language.toLowerCase()}/${input.specificationVersion}/semantic-profile.json`
  const profile = await optionalDependency("SEMANTIC_PROFILE", profilePath)
  dependencies.push(profile)
  if (profile !== undefined) {
    const body = JSON.parse(
      await readFile(repositoryPath(profilePath), "utf8"),
    ) as { sharedEnvironmentPath?: unknown }
    if (typeof body.sharedEnvironmentPath === "string") {
      dependencies.push(
        await optionalDependency("SHARED_ENVIRONMENT", body.sharedEnvironmentPath),
      )
    }
  }

  const available = dependencies.filter(
    (item): item is PipelineDependency => item !== undefined,
  )
  if (!available.some((item) => item.role === "SOURCE_MANIFEST")) {
    throw new Error(`Pipeline source manifest is unavailable: ${input.sourceManifest}`)
  }
  return available.sort((left, right) => left.role.localeCompare(right.role))
}

export async function verifyPipelineDependencies(
  dependencies: readonly PipelineDependency[],
): Promise<string[]> {
  const issues: string[] = []
  for (const dependency of dependencies) {
    try {
      const actual = sha256(await readFile(repositoryPath(dependency.path)))
      if (actual !== dependency.sha256) {
        issues.push(`${dependency.role} hash changed: ${dependency.path}`)
      }
    } catch (error) {
      issues.push(
        `${dependency.role} unavailable: ${dependency.path}: ` +
        (error instanceof Error ? error.message : String(error)),
      )
    }
  }
  return issues.sort((left, right) => left.localeCompare(right))
}
