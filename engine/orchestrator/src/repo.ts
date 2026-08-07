import { readFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))

export const REPO_ROOT = resolve(here, "../../..")

type ProjectConfig = {
  model?: string
}

export type ModelRef = {
  full: string
  providerID: string
  modelID: string
}

export async function loadProjectModel(): Promise<ModelRef> {
  const path = resolve(REPO_ROOT, "opencode.json")

  const config = JSON.parse(
    await readFile(path, "utf8"),
  ) as ProjectConfig

  if (!config.model) {
    throw new Error("opencode.json has no model field")
  }

  const separator = config.model.indexOf("/")

  if (separator <= 0 || separator === config.model.length - 1) {
    throw new Error(
      `Invalid OpenCode model ID: ${config.model}`,
    )
  }

  return {
    full: config.model,
    providerID: config.model.slice(0, separator),
    modelID: config.model.slice(separator + 1),
  }
}
