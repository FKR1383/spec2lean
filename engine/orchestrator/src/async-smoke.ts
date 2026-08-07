import {
  sendPromptAsync,
  waitForAgentResult,
} from "./async-session.js"

import {
  startOpenCode,
  unwrap,
} from "./opencode.js"

type Session = {
  id: string
}

const runtime =
  await startOpenCode()

try {
  const session =
    unwrap<Session>(
      await runtime.runtime.client.session.create({
        body: {
          title:
            "Spec2Lean async transport smoke",
        },
      }),
    )

  if (!session.id) {
    throw new Error(
      "OpenCode did not return a session ID",
    )
  }

  await sendPromptAsync(
    runtime.runtime.server.url,
    session.id,
    {
      agent: "spec-manager",

      model: {
        providerID:
          runtime.model.providerID,

        modelID:
          runtime.model.modelID,
      },

      parts: [
        {
          type: "text",
          text: [
            "Do not edit any file.",
            "Do not call tools.",
            "This is only an async transport test.",
            "",
            "Your final non-empty line must be exactly:",
            'SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"ARCHITECTURE","summary":"ASYNC_SMOKE_OK"}',
          ].join("\n"),
        },
      ],
    },
  )

  const response =
    await waitForAgentResult(
      runtime.runtime.server.url,
      session.id,
      {
        pollMs: 2_000,
        maxWaitMs: 120_000,
      },
    )

  console.log(response)
} finally {
  runtime.runtime.server.close()
}
