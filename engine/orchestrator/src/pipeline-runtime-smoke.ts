import { startOpenCode, unwrap } from "./opencode.js"
import { PIPELINE_AGENTS } from "./batch-store.js"

type Agent = { name?: string }

const runtimes: Awaited<ReturnType<typeof startOpenCode>>[] = []

try {
  // Two independently bound servers are sufficient to verify the primitive
  // used by every lazy agent-pinned worker. This sends no model prompt.
  runtimes.push(await startOpenCode())
  runtimes.push(await startOpenCode())

  const registries = await Promise.all(runtimes.map(async (runtime) =>
    unwrap<Agent[]>(await runtime.runtime.client.app.agents())
  ))
  const urls = runtimes.map((runtime) => runtime.runtime.server.url)
  const missingAgents = registries.flatMap((registry, index) => {
    const names = new Set(registry.flatMap((agent) =>
      typeof agent.name === "string" ? [agent.name] : []
    ))
    return PIPELINE_AGENTS
      .filter((agent) => !names.has(agent))
      .map((agent) => `runtime-${index + 1}:${agent}`)
  })
  const ok = new Set(urls).size === runtimes.length && missingAgents.length === 0
  console.log(JSON.stringify({
    ok,
    promptSubmitted: false,
    runtimeUrls: urls,
    registrySizes: registries.map((registry) => registry.length),
    missingAgents,
  }, null, 2))
  if (!ok) process.exitCode = 1
} finally {
  for (const runtime of runtimes.reverse()) runtime.runtime.server.close()
}
