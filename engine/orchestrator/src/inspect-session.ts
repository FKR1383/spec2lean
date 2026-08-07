import {
  startOpenCode,
} from "./opencode.js"

function argument(
  name: string,
): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1
    ? undefined
    : process.argv[index + 1]
}

const sessionId =
  argument("--session")

if (!sessionId) {
  throw new Error(
    "Usage: inspect-session.ts --session <session-id>",
  )
}

const runtime =
  await startOpenCode()

try {
  const base =
    runtime.runtime.server.url
      .replace(/\/+$/, "")

  const messagesResponse =
    await fetch(
      `${base}/session/${encodeURIComponent(sessionId)}/message?limit=200`,
    )

  if (!messagesResponse.ok) {
    throw new Error(
      `messages HTTP ${messagesResponse.status}`,
    )
  }

  const messages =
    await messagesResponse.json() as Array<{
      info?: {
        id?: string
        role?: string
      }
      parts?: Array<Record<string, unknown>>
    }>

  const statusResponse =
    await fetch(
      `${base}/session/status`,
    )

  const statuses =
    statusResponse.ok
      ? await statusResponse.json() as Record<
          string,
          unknown
        >
      : {}

  console.log(
    `SESSION: ${sessionId}`,
  )

  console.log(
    `STATUS: ${JSON.stringify(statuses[sessionId] ?? "not-listed")}`,
  )

  console.log(
    `MESSAGES: ${messages.length}`,
  )

  for (
    const message of messages.slice(-20)
  ) {
    console.log("\n--- MESSAGE ---")
    console.log(
      `role=${message.info?.role ?? "unknown"} id=${message.info?.id ?? "unknown"}`,
    )

    for (const part of message.parts ?? []) {
      const type =
        String(part.type ?? "unknown")

      console.log(
        `part.type=${type}`,
      )

      if (
        type === "text" &&
        typeof part.text === "string"
      ) {
        console.log(part.text)
      } else {
        console.log(
          JSON.stringify(
            part,
            null,
            2,
          ),
        )
      }
    }
  }
} finally {
  runtime.runtime.server.close()
}
