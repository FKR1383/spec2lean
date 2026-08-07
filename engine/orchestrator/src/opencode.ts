import { createOpencode } from "@opencode-ai/sdk"

import {
  loadProjectModel,
  REPO_ROOT,
  type ModelRef,
} from "./repo.js"

type OpenCodeRuntime = Awaited<
  ReturnType<typeof createOpencode>
>

export type Spec2LeanOpenCode = {
  runtime: OpenCodeRuntime
  model: ModelRef
}

export async function startOpenCode(): Promise<Spec2LeanOpenCode> {
  const model = await loadProjectModel()

  const port = Number(
    process.env.SPEC2LEAN_OPENCODE_PORT ?? "4097",
  )

  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    throw new Error(
      `Invalid SPEC2LEAN_OPENCODE_PORT: ${port}`,
    )
  }

  process.chdir(REPO_ROOT)

  const runtime = await createOpencode({
    hostname: "127.0.0.1",
    port,
    timeout: 15_000,
  })

  return {
    runtime,
    model,
  }
}

export function unwrap<T>(value: unknown): T {
  if (
    typeof value === "object" &&
    value !== null &&
    "data" in value
  ) {
    const data = (value as { data?: unknown }).data

    if (data !== undefined && data !== null) {
      return data as T
    }
  }

  return value as T
}
