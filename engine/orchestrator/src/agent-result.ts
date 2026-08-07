import type {
  FormalizationStage,
} from "./workflow.js"

export type AgentResult = {
  outcome:
    | "SUCCESS"
    | "REVISE"
    | "RETRY"
    | "BLOCKED"

  nextStage: FormalizationStage

  summary: string
}

const PREFIX =
  "SPEC2LEAN_RESULT"

function extractPayload(
  response: string,
): string {
  const lines =
    response
      .trim()
      .split(/\r?\n/)
      .reverse()

  for (const rawLine of lines) {
    const index =
      rawLine.indexOf(PREFIX)

    if (index === -1) {
      continue
    }

    let payload =
      rawLine
        .slice(index + PREFIX.length)
        .trim()

    // Tolerate accidental Markdown backticks/fences.
    payload =
      payload
        .replace(/^`+/, "")
        .replace(/`+$/, "")
        .trim()

    const firstBrace =
      payload.indexOf("{")

    const lastBrace =
      payload.lastIndexOf("}")

    if (
      firstBrace !== -1 &&
      lastBrace > firstBrace
    ) {
      return payload.slice(
        firstBrace,
        lastBrace + 1,
      )
    }
  }

  throw new Error(
    "Agent response has no parseable SPEC2LEAN_RESULT payload",
  )
}

export function parseAgentResult(
  response: string,
): AgentResult {
  const payload =
    extractPayload(response)

  let parsed: unknown

  try {
    parsed = JSON.parse(payload)
  } catch {
    throw new Error(
      `SPEC2LEAN_RESULT contains invalid JSON: ${payload}`,
    )
  }

  if (
    typeof parsed !== "object" ||
    parsed === null
  ) {
    throw new Error(
      "SPEC2LEAN_RESULT must contain a JSON object",
    )
  }

  const result =
    parsed as Partial<AgentResult>

  if (
    result.outcome !== "SUCCESS" &&
    result.outcome !== "REVISE" &&
    result.outcome !== "RETRY" &&
    result.outcome !== "BLOCKED"
  ) {
    throw new Error(
      `Invalid agent outcome: ${result.outcome}`,
    )
  }

  if (
    typeof result.nextStage !== "string"
  ) {
    throw new Error(
      "Agent result has no nextStage",
    )
  }

  if (
    typeof result.summary !== "string"
  ) {
    throw new Error(
      "Agent result has no summary",
    )
  }

  return result as AgentResult
}
