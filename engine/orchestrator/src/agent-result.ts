import type {
  FormalizationStage,
} from "./workflow.js"

export type AgentResult = {
  outcome:
    | "SUCCESS"
    | "REVISE"
    | "BLOCKED"

  nextStage: FormalizationStage

  summary: string
}

const PREFIX =
  "SPEC2LEAN_RESULT "

export function parseAgentResult(
  response: string,
): AgentResult {
  const lines =
    response.trim().split(/\r?\n/)

  const line =
    [...lines]
      .reverse()
      .find((item) =>
        item.startsWith(PREFIX),
      )

  if (!line) {
    throw new Error(
      "Agent response has no SPEC2LEAN_RESULT line",
    )
  }

  const payload =
    line.slice(PREFIX.length)

  let parsed: unknown

  try {
    parsed = JSON.parse(payload)
  } catch {
    throw new Error(
      "SPEC2LEAN_RESULT contains invalid JSON",
    )
  }

  if (
    typeof parsed !== "object" ||
    parsed === null
  ) {
    throw new Error(
      "SPEC2LEAN_RESULT must be an object",
    )
  }

  const result =
    parsed as Partial<AgentResult>

  if (
    result.outcome !== "SUCCESS" &&
    result.outcome !== "REVISE" &&
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
