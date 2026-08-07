import { createServer } from "node:net"
import { createOpencode } from "@opencode-ai/sdk"

import { loadProjectModel, REPO_ROOT, type ModelRef } from "./repo.js"

type OpenCodeRuntime = Awaited<ReturnType<typeof createOpencode>>

export type Spec2LeanOpenCode = {
  runtime: OpenCodeRuntime
  model: ModelRef
}

async function freeLocalPort(): Promise<number> {
  return await new Promise((resolve, reject) => {
    const server = createServer()
    server.once("error", reject)
    server.listen(0, "127.0.0.1", () => {
      const address = server.address()
      if (!address || typeof address === "string") {
        server.close()
        reject(new Error("Could not allocate a local OpenCode port"))
        return
      }
      const port = address.port
      server.close((error?: Error) => error ? reject(error) : resolve(port))
    })
  })
}

export async function startOpenCode(): Promise<Spec2LeanOpenCode> {
  const model = await loadProjectModel()
  const explicitPort = process.env.SPEC2LEAN_OPENCODE_PORT
  const port = explicitPort === undefined ? await freeLocalPort() : Number(explicitPort)

  if (!Number.isInteger(port) || port <= 0 || port > 65535) {
    throw new Error(`Invalid SPEC2LEAN_OPENCODE_PORT: ${port}`)
  }

  process.chdir(REPO_ROOT)
  const runtime = await createOpencode({
    hostname: "127.0.0.1",
    port,
    timeout: 15_000,
  })

  return { runtime, model }
}

export function unwrap<T>(value: unknown): T {
  if (typeof value === "object" && value !== null && "data" in value) {
    const data = (value as { data?: unknown }).data
    if (data !== undefined && data !== null) return data as T
  }
  return value as T
}
