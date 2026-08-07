import {
  startOpenCode,
  unwrap,
} from "./opencode.js"

type Agent = {
  name: string
}

type Session = {
  id: string
}

type Part = {
  type: string
  text?: string
}

type PromptResult = {
  parts?: Part[]
}

const AGENT = "spec-manager"

const runtime = await startOpenCode()

try {
  const { client } = runtime.runtime

  // app.agents() doubles as our first connectivity/API smoke check.
  const agents = unwrap<Agent[]>(
    await client.app.agents(),
  )

  if (!agents.some((agent) => agent.name === AGENT)) {
    throw new Error(
      `Required OpenCode agent not found: ${AGENT}`,
    )
  }

  const created = unwrap<Session>(
    await client.session.create({
      body: {
        title: "Spec2Lean Phase 4 SDK smoke test",
      },
    }),
  )

  if (!created.id) {
    throw new Error("OpenCode did not return a session ID")
  }

  const result = unwrap<PromptResult>(
    await client.session.prompt({
      path: {
        id: created.id,
      },
      body: {
        agent: AGENT,

        model: {
          providerID: runtime.model.providerID,
          modelID: runtime.model.modelID,
        },

        parts: [
          {
            type: "text",
            text: [
              "This is the first Spec2Lean Phase 4 SDK smoke test.",
              "",
              "Do not edit files.",
              "Do not invoke other agents.",
              "Do not run shell commands.",
              "Do not create artifacts.",
              "",
              "Reply with exactly:",
              "SDK_SMOKE_OK",
            ].join("\n"),
          },
        ],
      },
    }),
  )

  const response = (result.parts ?? [])
    .filter((part) => part.type === "text")
    .map((part) => part.text ?? "")
    .join("\n")
    .trim()

  if (!response.includes("SDK_SMOKE_OK")) {
    throw new Error(
      `Unexpected Spec Manager response: ${response}`,
    )
  }

  console.log(
    JSON.stringify(
      {
        ok: true,
        model: runtime.model.full,
        agent: AGENT,
        sessionID: created.id,
        response,
      },
      null,
      2,
    ),
  )
} finally {
  runtime.runtime.server.close()
}
