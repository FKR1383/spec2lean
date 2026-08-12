import { recordBenchmarkAutoAdvance } from "./benchmark-decision-record.js"
import { GATES } from "./gates.js"
import { saveRun } from "./run-store.js"
import {
  transitionRun,
  type FormalizationStage,
  type GateName,
  type RunState,
} from "./workflow.js"

const GATE_FOR_WAIT_STAGE = new Map<FormalizationStage, GateName>(
  Object.entries(GATES).map(([gate, plan]) => [
    plan.waitingStage,
    gate as GateName,
  ]),
)

export function waitingGateForStage(stage: FormalizationStage): GateName | undefined {
  return GATE_FOR_WAIT_STAGE.get(stage)
}

/**
 * Advances benchmark-only gates without turning them into human approvals.
 *
 * This is shared by the single-run loop and the pipelined batch scheduler so
 * both controllers write the exact same deterministic decision record.
 */
export async function advanceBenchmarkGate(
  run: RunState,
): Promise<{ run: RunState; gate: GateName; reviewPath: string; recovered: boolean } | undefined> {
  const gate = waitingGateForStage(run.stage)
  if (gate === undefined || run.benchmark?.autoApprove !== true) return undefined

  const decision = await recordBenchmarkAutoAdvance(run, gate)
  const target = gate === "FINAL"
    ? "BENCHMARK_COMPLETE"
    : GATES[gate].approvedStage
  let next = transitionRun(
    run,
    target,
    `${decision.recovered ? "Recovered" : "Recorded"} benchmark-only ${gate} auto-advance; review=${decision.reviewPath}; humanConfirmationRecorded=false`,
  )
  next = {
    ...next,
    gates: {
      ...next.gates,
      [gate]: "benchmark_auto_advanced",
    },
  }
  await saveRun(next)
  return {
    run: next,
    gate,
    reviewPath: decision.reviewPath,
    recovered: decision.recovered,
  }
}
