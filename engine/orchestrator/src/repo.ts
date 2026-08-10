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

function modelRef(full: string): ModelRef {
  const separator = full.indexOf("/")
  if (separator <= 0 || separator === full.length - 1) {
    throw new Error(`Invalid OpenCode model ID: ${full}`)
  }
  return {
    full,
    providerID: full.slice(0, separator),
    modelID: full.slice(separator + 1),
  }
}

export async function loadProjectModel(): Promise<ModelRef> {
  const path = resolve(REPO_ROOT, "opencode.json")

  const config = JSON.parse(
    await readFile(path, "utf8"),
  ) as ProjectConfig

  if (!config.model) {
    throw new Error("opencode.json has no model field")
  }

  return modelRef(config.model)
}

export async function loadAgentModel(agent: string): Promise<ModelRef> {
  if (!/^[a-z0-9-]+$/.test(agent)) throw new Error(`Unsafe agent name: ${agent}`)
  const source = await readFile(resolve(REPO_ROOT, `.opencode/agents/${agent}.md`), "utf8")
  const match = source.match(/^model:\s*(\S+)\s*$/m)
  if (match?.[1] === undefined) throw new Error(`Agent ${agent} has no model field`)
  return modelRef(match[1])
}
