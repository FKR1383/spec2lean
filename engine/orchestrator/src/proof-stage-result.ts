import type { AgentResult } from "./agent-result.js"

/**
 * Local Lean verification may strengthen an agent RETRY/SUCCESS decision, but
 * it must never erase a semantic/theorem conflict reported as BLOCKED.
 */
export function reconcileProofStageResult(
  agentResult: AgentResult,
  localResult: AgentResult | undefined,
): AgentResult {
  if (agentResult.outcome === "BLOCKED") return agentResult
  return localResult ?? agentResult
}
