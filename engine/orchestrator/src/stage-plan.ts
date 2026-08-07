import type {
  FormalizationStage,
  RunState,
} from "./workflow.js"

export type StagePlan = {
  agent: string

  successStage: FormalizationStage

  revisionStages: readonly FormalizationStage[]

  task: string
}

export const STAGE_PLANS:
  Partial<Record<FormalizationStage, StagePlan>> = {

  ARCHITECTURE: {
    agent: "spec-architect",
    successStage: "ARCHITECTURE_CRITIQUE",
    revisionStages: [],
    task: [
      "Produce or revise the bounded language architecture for the requested unit.",
      "Use only project-approved sources and tools.",
      "Do not approve any human gate.",
    ].join("\n"),
  },

  ARCHITECTURE_CRITIQUE: {
    agent: "semantic-critic",
    successStage: "WAITING_GATE_A",
    revisionStages: [
      "ARCHITECTURE",
    ],
    task: [
      "Independently critique the architecture candidate.",
      "If substantive changes are required, request revision.",
      "If suitable, mark it ready for Human Gate A.",
      "Do not approve Gate A yourself.",
    ].join("\n"),
  },

  SOURCE_CURATION: {
    agent: "source-curator",
    successStage: "SEMANTIC_EXTRACTION",
    revisionStages: [],
    task: [
      "Build the bounded official-source evidence bundle for the unit.",
      "Do not invent missing semantic facts.",
      "Record unresolved evidence gaps explicitly.",
    ].join("\n"),
  },

  SEMANTIC_EXTRACTION: {
    agent: "semantic-extractor",
    successStage: "SEMANTIC_CRITIQUE",
    revisionStages: [
      "SOURCE_CURATION",
    ],
    task: [
      "Produce the bounded semantic interpretation from approved evidence.",
      "Separate source facts, derived interpretations, design dependencies,",
      "human-approved assumptions, and open questions.",
      "Do not fabricate semantics.",
    ].join("\n"),
  },

  SEMANTIC_CRITIQUE: {
    agent: "semantic-critic",
    successStage: "WAITING_GATE_B",
    revisionStages: [
      "SEMANTIC_EXTRACTION",
      "SOURCE_CURATION",
    ],
    task: [
      "Independently critique the semantic interpretation.",
      "Request source revision when evidence is missing.",
      "Request semantic revision when interpretation is incorrect.",
      "Otherwise mark it ready for Human Gate B.",
      "Do not approve Gate B.",
    ].join("\n"),
  },

  LEAN_FORMALIZATION: {
    agent: "lean-formalizer",
    successStage: "LEAN_MAPPING_CRITIQUE",
    revisionStages: [],
    task: [
      "Implement the Gate-B-approved bounded semantics in Lean.",
      "Use Lean verification tools.",
      "Never use sorry, admit, new axioms, or unsafe.",
      "Do not weaken semantics to make Lean compile.",
    ].join("\n"),
  },

  LEAN_MAPPING_CRITIQUE: {
    agent: "semantic-critic",
    successStage: "WAITING_GATE_C",
    revisionStages: [
      "LEAN_FORMALIZATION",
    ],
    task: [
      "Independently compare the Lean mapping with the approved semantics.",
      "Compilation alone is not semantic correctness.",
      "If faithful, mark it ready for Human Gate C.",
      "Do not approve Gate C.",
    ].join("\n"),
  },

  THEOREM_GENERATION: {
    agent: "lean-formalizer",
    successStage: "THEOREM_STRENGTH_CRITIQUE",
    revisionStages: [],
    task: [
      "Generate a small set of meaningful theorem obligations.",
      "Do not write proofs yet.",
      "Avoid vacuous, circular, or trivially functional determinism claims.",
    ].join("\n"),
  },

  THEOREM_STRENGTH_CRITIQUE: {
    agent: "semantic-critic",
    successStage: "WAITING_THEOREM_STRENGTH_APPROVAL",
    revisionStages: [
      "THEOREM_GENERATION",
    ],
    task: [
      "Independently review theorem strength and non-vacuity.",
      "If adequate, mark the set ready for human theorem-strength approval.",
      "Do not approve it yourself.",
    ].join("\n"),
  },

  PROOF_GENERATION: {
    agent: "proof-engineer",
    successStage: "FINAL_CRITIQUE",
    revisionStages: [
      "PROOF_GENERATION",
    ],
    task: [
      "Prove exactly the human-approved theorem obligations.",
      "Technical proof repair is allowed without semantic weakening.",
      "Never use sorry, admit, new axioms, or unsafe.",
      "If a theorem requires weakening or semantic change, report BLOCKED.",
    ].join("\n"),
  },

  FINAL_CRITIQUE: {
    agent: "semantic-critic",
    successStage: "WAITING_FINAL_APPROVAL",
    revisionStages: [
      "FINAL_CRITIQUE",
      "LEAN_FORMALIZATION",
      "THEOREM_GENERATION",
      "PROOF_GENERATION",
    ],
    task: [
      "Perform the final independent semantic/proof/traceability critique.",
      "If everything is acceptable, mark ready for final HUMAN approval.",
      "Never grant final acceptance yourself.",
    ].join("\n"),
  },
}

export function planForRun(
  run: RunState,
): StagePlan {
  const plan =
    STAGE_PLANS[run.stage]

  if (!plan) {
    throw new Error(
      `Stage ${run.stage} is not an executable agent stage`,
    )
  }

  return plan
}
