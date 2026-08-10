import type { AgentResult } from "./agent-result.js"
import { planForRun } from "./stage-plan.js"
import {
  canTransition,
  type FormalizationStage,
  type RunState,
} from "./workflow.js"

export function validateAgentDecision(
  run: RunState,
  result: AgentResult,
): FormalizationStage {
  const plan = planForRun(run)
  const next = result.nextStage

  if (result.outcome === "SUCCESS" && next !== plan.successStage) {
    throw new Error(
      `Agent attempted invalid SUCCESS target: ${next}; expected ${plan.successStage}`,
    )
  }

  if (result.outcome === "REVISE" && !plan.revisionStages.includes(next)) {
    throw new Error(`Agent attempted invalid REVISE target: ${next}`)
  }

  if (result.outcome === "RETRY") {
    if (next !== run.stage) {
      throw new Error(`RETRY must remain at current stage: ${run.stage}`)
    }
    return next
  }

  if (result.outcome === "BLOCKED" && next !== "BLOCKED") {
    throw new Error("BLOCKED outcome must target BLOCKED")
  }

  if (!canTransition(run.stage, next)) {
    throw new Error(`Workflow rejects transition ${run.stage} -> ${next}`)
  }

  return next
}

export function normalizeAgentDecision(
  run: RunState,
  result: AgentResult,
): AgentResult {
  try {
    validateAgentDecision(run, result)
    return result
  } catch (error) {
    return {
      outcome: "RETRY",
      nextStage: run.stage,
      summary:
        "Agent returned an invalid workflow decision; no transition was trusted: " +
        (error instanceof Error ? error.message : String(error)),
    }
  }
}
