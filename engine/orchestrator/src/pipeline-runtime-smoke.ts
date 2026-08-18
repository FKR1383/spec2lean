import { startOpenCode, unwrap } from "./opencode.js"
import { PIPELINE_AGENTS } from "./batch-store.js"

type Agent = { name?: string }
type Session = { id?: string }
type ToolDescription = {
  id: string
  parameters?: {
    properties?: { content?: { maxLength?: number } }
  }
}

let runtime: Awaited<ReturnType<typeof startOpenCode>> | undefined
const sessionIds: string[] = []

try {
  runtime = await startOpenCode()
  const registry = unwrap<Agent[]>(await runtime.runtime.client.app.agents())
  const toolIds = unwrap<string[]>(await runtime.runtime.client.tool.ids())
  const toolDescriptions = unwrap<ToolDescription[]>(
    await runtime.runtime.client.tool.list({
      query: {
        provider: runtime.model.providerID,
        model: runtime.model.modelID,
      },
    }),
  )
  const architectureWriter = toolDescriptions.find(
    (tool) => tool.id === "candidate_architecture_write",
  )
  const names = new Set(registry.flatMap((agent) =>
    typeof agent.name === "string" ? [agent.name] : []
  ))
  const missingAgents = PIPELINE_AGENTS.filter((agent) => !names.has(agent))

  // Concurrent session creation exercises the shared-server primitive used
  // by agent-pinned workers without submitting a model prompt.
  const sessions = await Promise.all(
    PIPELINE_AGENTS.slice(0, 4).map(async (agent) =>
      unwrap<Session>(await runtime!.runtime.client.session.create({
        body: { title: `Spec2Lean shared-runtime smoke ${agent}` },
      }))
    ),
  )
  sessionIds.push(...sessions.flatMap((session) => session.id ? [session.id] : []))
  const ok =
    missingAgents.length === 0 &&
    toolIds.includes("candidate_architecture_write") &&
    architectureWriter?.parameters?.properties?.content?.maxLength === 32 * 1024 &&
    sessionIds.length === sessions.length &&
    new Set(sessionIds).size === sessions.length
  console.log(JSON.stringify({
    ok,
    promptSubmitted: false,
    runtimeCount: 1,
    runtimeUrl: runtime.runtime.server.url,
    registrySize: registry.length,
    concurrentSessionsCreated: sessionIds.length,
    uniqueSessionIds: new Set(sessionIds).size,
    missingAgents,
    architectureWriterRegistered: toolIds.includes("candidate_architecture_write"),
    architectureWriterMaxBytes:
      architectureWriter?.parameters?.properties?.content?.maxLength,
  }, null, 2))
  if (!ok) process.exitCode = 1
} finally {
  if (runtime !== undefined) {
    await Promise.allSettled(sessionIds.map(async (id) =>
      runtime!.runtime.client.session.delete({ path: { id } })
    ))
    runtime.runtime.server.close()
  }
}
