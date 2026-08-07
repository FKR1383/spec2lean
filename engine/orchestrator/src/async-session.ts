type MessagePart = {
  type?: string
  text?: string
  reason?: string
}

type SessionMessage = {
  info?: {
    role?: string
  }
  parts?: MessagePart[]
}

type SessionStatus =
  | { type: "idle" }
  | { type: "busy" }
  | {
      type: "retry"
      attempt: number
      message: string
      next: number
    }

export type AsyncPromptBody = {
  agent: string
  model: {
    providerID: string
    modelID: string
  }
  parts: Array<{
    type: "text"
    text: string
  }>
}

function urlJoin(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}${path}`
}

async function timedFetch(
  url: string,
  init: RequestInit,
  timeoutMs = 20_000,
): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    return await fetch(url, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

export async function sendPromptAsync(
  baseUrl: string,
  sessionId: string,
  body: AsyncPromptBody,
): Promise<void> {
  const response = await timedFetch(
    urlJoin(baseUrl, `/session/${encodeURIComponent(sessionId)}/prompt_async`),
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    },
  )

  if (response.status !== 204 && !response.ok) {
    const text = await response.text()
    throw new Error(`prompt_async failed: HTTP ${response.status}: ${text}`)
  }
}

async function listMessages(
  baseUrl: string,
  sessionId: string,
): Promise<SessionMessage[]> {
  const response = await timedFetch(
    urlJoin(baseUrl, `/session/${encodeURIComponent(sessionId)}/message?limit=100`),
    { method: "GET" },
  )

  if (!response.ok) {
    throw new Error(`message polling failed: HTTP ${response.status}`)
  }

  return (await response.json()) as SessionMessage[]
}

function textOfMessage(message: SessionMessage): string {
  return (message.parts ?? [])
    .filter((part) => part.type === "text")
    .map((part) => part.text ?? "")
    .join("\n")
    .trim()
}

function findCompletedResponse(messages: SessionMessage[]): string | undefined {
  for (const message of [...messages].reverse()) {
    if (message.info?.role !== "assistant") continue
    const text = textOfMessage(message)
    if (text.includes("SPEC2LEAN_RESULT")) return text
  }
  return undefined
}

function latestAssistantResponse(messages: SessionMessage[]): string | undefined {
  for (const message of [...messages].reverse()) {
    if (message.info?.role !== "assistant") continue
    const text = textOfMessage(message)
    if (text.length > 0) return text
  }
  return undefined
}

function latestFinishReason(messages: SessionMessage[]): string | undefined {
  for (const message of [...messages].reverse()) {
    if (message.info?.role !== "assistant") continue
    for (const part of [...(message.parts ?? [])].reverse()) {
      if (part.type === "step-finish" && typeof part.reason === "string") {
        return part.reason
      }
    }
  }
  return undefined
}

async function getSessionStatus(
  baseUrl: string,
  sessionId: string,
): Promise<SessionStatus | undefined> {
  const response = await timedFetch(urlJoin(baseUrl, "/session/status"), {
    method: "GET",
  })

  if (!response.ok) {
    throw new Error(`session status failed: HTTP ${response.status}`)
  }

  const statuses = (await response.json()) as Record<string, SessionStatus>
  return statuses[sessionId]
}

export async function abortSession(
  baseUrl: string,
  sessionId: string,
): Promise<void> {
  const response = await timedFetch(
    urlJoin(baseUrl, `/session/${encodeURIComponent(sessionId)}/abort`),
    { method: "POST" },
  )

  if (!response.ok) {
    throw new Error(`session abort failed: HTTP ${response.status}`)
  }
}

function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

export async function waitForAgentResult(
  baseUrl: string,
  sessionId: string,
  options?: {
    pollMs?: number
    maxWaitMs?: number
    ignoreResponse?: string
    missingStatusIsTerminal?: boolean
  },
): Promise<string> {
  const pollMs = options?.pollMs ?? 2_000
  const maxWaitMs = options?.maxWaitMs ?? 30 * 60 * 1000
  const ignoreResponse = options?.ignoreResponse
  const missingStatusIsTerminal = options?.missingStatusIsTerminal ?? false
  const started = Date.now()
  let lastHeartbeat = started
  let seenBusy = false
  let missingStatusPolls = 0

  while (true) {
    const messages = await listMessages(baseUrl, sessionId)
    const protocolResponse = findCompletedResponse(messages)

    if (protocolResponse && protocolResponse !== ignoreResponse) {
      return protocolResponse
    }

    const status = await getSessionStatus(baseUrl, sessionId)
    const finishReason = latestFinishReason(messages)
    const latest = latestAssistantResponse(messages)

    if (status?.type === "busy" || status?.type === "retry") {
      seenBusy = true
      missingStatusPolls = 0
    } else if (status === undefined && (seenBusy || missingStatusIsTerminal)) {
      missingStatusPolls += 1
    }

    // OpenCode may stop listing a completed session in /session/status.  The
    // step-finish part is therefore a second completion signal, especially for
    // terminal reasons such as `length`.
    const terminalByFinishReason =
      finishReason !== undefined && finishReason !== "tool-calls"

    const terminalByMissingStatus =
      status === undefined &&
      (seenBusy || missingStatusIsTerminal) &&
      missingStatusPolls >= 2

    if (status?.type === "idle" || terminalByFinishReason || terminalByMissingStatus) {
      if (latest && latest !== ignoreResponse) {
        return latest
      }

      throw new Error(
        `Agent session terminated without textual result; reason=${finishReason ?? "status-missing"}`,
      )
    }

    const now = Date.now()

    if (now - lastHeartbeat >= 30_000) {
      const elapsedSeconds = Math.floor((now - started) / 1000)
      console.log(
        `[spec2lean] session=${sessionId} status=${status?.type ?? "unknown"} finish=${finishReason ?? "none"} elapsed=${elapsedSeconds}s`,
      )
      lastHeartbeat = now
    }

    if (now - started > maxWaitMs) {
      throw new Error(
        `Agent result timed out after ${maxWaitMs}ms; session status=${status?.type ?? "unknown"}; finish=${finishReason ?? "none"}`,
      )
    }

    await sleep(pollMs)
  }
}

export async function waitForAssistantText(
  baseUrl: string,
  sessionId: string,
  options?: { pollMs?: number; maxWaitMs?: number },
): Promise<string> {
  const pollMs = options?.pollMs ?? 2_000
  const maxWaitMs = options?.maxWaitMs ?? 10 * 60 * 1000
  const started = Date.now()
  let seenBusy = false
  let missingStatusPolls = 0

  while (true) {
    const messages = await listMessages(baseUrl, sessionId)
    const status = await getSessionStatus(baseUrl, sessionId)
    const latest = latestAssistantResponse(messages)
    const finishReason = latestFinishReason(messages)

    if (status?.type === "busy" || status?.type === "retry") {
      seenBusy = true
      missingStatusPolls = 0
    } else if (status === undefined && seenBusy) {
      missingStatusPolls += 1
    }

    const terminal =
      status?.type === "idle" ||
      (finishReason !== undefined && finishReason !== "tool-calls") ||
      (status === undefined && seenBusy && missingStatusPolls >= 2)

    if (terminal && latest) return latest
    if (terminal) {
      throw new Error(`Assistant session terminated without text; reason=${finishReason ?? "status-missing"}`)
    }

    if (Date.now() - started > maxWaitMs) {
      throw new Error(`Assistant text timed out after ${maxWaitMs}ms`)
    }

    await sleep(pollMs)
  }
}
