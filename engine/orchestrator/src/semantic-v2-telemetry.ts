import type { RunState } from "./workflow.js"

export function semanticV2Telemetry(run: RunState): Record<string, unknown> {
  const state = run.semanticV2
  if (state === undefined) {
    return {
      configured: false,
      mode: "UNASSESSED",
      fastPathMaterialized: false,
      fastPathReachedGateB: false,
    }
  }
  const current = state.current
  const fastPathMaterialized = state.events.some(
    (event) => event.kind === "MATERIALIZED",
  )
  const fastPathReachedGateB =
    state.mode === "DELTA_FAST_PATH" &&
    run.history.some(
      (event) => event.from === "SEMANTIC_CRITIQUE" && event.to === "WAITING_GATE_B",
    )

  return {
    configured: true,
    mode: state.mode,
    profilePath: state.profilePath,
    sharedEnvironmentPath: state.sharedEnvironmentPath,
    environment: state.environment ?? null,
    missingRequiredSemanticIds: state.missingRequiredSemanticIds,
    fallbackReason: state.fallbackReason ?? null,
    fastPathMaterialized,
    fastPathReachedGateB,
    artifacts: current === undefined
      ? null
      : {
          ...current,
          materializedToDeltaRatio:
            current.deltaBytes === undefined || current.materializedBytes === undefined
              ? null
              : Number((current.materializedBytes / current.deltaBytes).toFixed(3)),
          criticPacketToMaterializedRatio:
            current.criticPacketBytes === undefined || current.materializedBytes === undefined
              ? null
              : Number((current.criticPacketBytes / current.materializedBytes).toFixed(3)),
        },
    events: state.events,
  }
}
