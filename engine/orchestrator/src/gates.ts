import type {
  FormalizationStage,
  GateName,
} from "./workflow.js"

export type GatePlan = {
  gate: GateName
  waitingStage: FormalizationStage
  approvedStage: FormalizationStage
}

export const GATES: Record<GateName, GatePlan> = {
  A: {
    gate: "A",
    waitingStage: "WAITING_GATE_A",
    approvedStage: "SOURCE_CURATION",
  },

  B: {
    gate: "B",
    waitingStage: "WAITING_GATE_B",
    approvedStage: "LEAN_FORMALIZATION",
  },

  C: {
    gate: "C",
    waitingStage: "WAITING_GATE_C",
    approvedStage: "THEOREM_GENERATION",
  },

  THEOREM_STRENGTH: {
    gate: "THEOREM_STRENGTH",
    waitingStage: "WAITING_THEOREM_STRENGTH_APPROVAL",
    approvedStage: "PROOF_GENERATION",
  },

  FINAL: {
    gate: "FINAL",
    waitingStage: "WAITING_FINAL_APPROVAL",
    approvedStage: "ACCEPTED",
  },
}
