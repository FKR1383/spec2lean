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
      "When approved shared architecture exists, produce an instruction-specific delta instead of rediscovering language-wide background.",
      "On revision, read the latest critic artifact first and repair every BLOCKER/MAJOR finding without unrelated redesign.",
      "Use only project-approved sources and tools.",
      "Do not approve any human gate.",
    ].join("\n"),
  },

  ARCHITECTURE_CRITIQUE: {
    agent: "architecture-critic",
    successStage: "WAITING_GATE_A",
    revisionStages: [
      "ARCHITECTURE",
    ],
    task: [
      "Independently critique the architecture candidate.",
      "Check bounded scope, evidence/design classification, state model, and every state-affecting ambiguity; do not redesign the unit.",
      "Request revision only for unresolved BLOCKER/MAJOR findings.",
      "MINOR/NOTE-only findings are non-blocking: record them and return SUCCESS to the human gate.",
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
    agent: "semantics-critic",
    successStage: "WAITING_GATE_B",
    revisionStages: [
      "SEMANTIC_EXTRACTION",
      "SOURCE_CURATION",
    ],
    task: [
      "Independently critique the semantic interpretation.",
      "Check every SOURCE_FACT against exact evidence IDs and every derived/design claim against explicit dependencies.",
      "Build a compact execution-branch matrix (guards, operand lookup failures, state writes/no-op) and report only real mismatches.",
      "Request source or semantic revision only when the problem is BLOCKER/MAJOR.",
      "MINOR/NOTE-only findings are non-blocking: record them and return SUCCESS to the human gate.",
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
      "Enumerate exact approved semantic IDs before writing and validate every traceability citation against them.",
      "On revision, read the latest Lean-mapping critic artifact first and make only its required BLOCKER/MAJOR repairs.",
      "Place all unit-specific declarations under namespace Spec2Lean.PTX.<LeanModuleName> supplied by the orchestrator.",
      "Import Spec2Lean.Basic, never the Spec2Lean root module, from a module that the root will later import.",
      "Use Lean verification tools.",
      "Never use sorry, admit, new axioms, or unsafe.",
      "Do not weaken semantics to make Lean compile.",
    ].join("\n"),
  },

  LEAN_MAPPING_CRITIQUE: {
    agent: "lean-mapping-critic",
    successStage: "WAITING_GATE_C",
    revisionStages: [
      "LEAN_FORMALIZATION",
    ],
    task: [
      "Independently compare the Lean mapping with the approved semantics.",
      "Compilation alone is not semantic correctness.",
      "Compare every executable and relational branch against the approved execution-branch matrix, including false guards and partial lookups.",
      "Use small Lean probes only when needed to decide a concrete mapping question; do not begin theorem design here.",
      "Request revision only for unresolved BLOCKER/MAJOR findings; MINOR/NOTE-only findings proceed to the human gate.",
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
      "Write and verify the complete obligation artifact before emitting the result protocol.",
      "Copy the exact orchestrator-supplied SUCCESS stage name; never invent or reuse a *_REVIEW alias.",
      "On revision, read the latest theorem-strength critic artifact first and repair every BLOCKER/MAJOR finding.",
      "Pin the intended Lean namespace to Spec2Lean.PTX.<LeanModuleName> and make supporting theorem names unit-specific where collision is possible.",
      "Do not write proofs yet.",
      "Avoid vacuous, circular, or trivially functional determinism claims.",
    ].join("\n"),
  },

  THEOREM_STRENGTH_CRITIQUE: {
    agent: "theorem-strength-critic",
    successStage: "WAITING_THEOREM_STRENGTH_APPROVAL",
    revisionStages: [
      "THEOREM_GENERATION",
    ],
    task: [
      "Independently review theorem strength and non-vacuity.",
      "Extract and count complete theorem declarations; reject placeholders, truncated statements, or duplicate names.",
      "For determinism/totality/correspondence obligations, analyze constructor overlap and missing premises and use a minimal Lean counterexample/probe when the result is not syntactically certain.",
      "A compiling statement is not evidence that the theorem is true or non-vacuous.",
      "Request revision only for unresolved BLOCKER/MAJOR findings; MINOR/NOTE-only findings proceed to the human gate.",
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
      "",
      "EXECUTION-FIRST RULE:",
      "Do not spend the session mentally planning all proofs.",
      "Do not produce long speculative reasoning about possible tactics.",
      "After reading only the minimum required artifacts, WRITE the proof candidate immediately.",
      "Then let lean_check_file / lean_get_diagnostics / lean_get_goals drive repairs.",
      "",
      "Required workflow:",
      "1. Read the theorem-obligation artifact.",
      "2. Read the theorem-strength critic/approval.",
      "3. Read the installed Lean semantics module.",
      "4. Immediately candidate_write the complete first proof attempt.",
      "5. Run lean_check_file.",
      "6. Repair concrete Lean errors only.",
      "7. Repeat until success or a genuine theorem/semantic conflict is found.",
      "",
      "Do not create scratch proof probes unless a concrete diagnostic cannot be resolved directly.",
      "Do not re-derive already-approved theorem strength.",
      "Do not re-review source evidence.",
      "Do not re-review semantic interpretation.",
      "",
      "Technical proof repair is allowed without semantic weakening.",
      "Never use sorry, admit, new axioms, or unsafe.",
      "If an approved theorem really requires weakening, a new semantic precondition,",
      "or a semantics change, report BLOCKED instead of altering it.",
    ].join("\n"),
  },

  FINAL_CRITIQUE: {
    agent: "final-critic",
    successStage: "WAITING_FINAL_APPROVAL",
    revisionStages: [
      "FINAL_CRITIQUE",
      "LEAN_FORMALIZATION",
      "THEOREM_GENERATION",
      "PROOF_GENERATION",
    ],
    task: [
      "Perform the final independent semantic/proof/traceability critique.",
      "",
      "FINAL-REVIEW DISCIPLINE:",
      "This is an aggregation review, not a fresh research pass.",
      "Do not repeat broad PTX source searches that were already independently checked",
      "by the architecture, semantic, Lean-mapping, and theorem-strength critics.",
      "",
      "Read the latest:",
      "- architecture critic",
      "- semantic critic",
      "- Lean-mapping critic",
      "- theorem-strength critic",
      "- human gate/approval records",
      "- approved semantic artifact",
      "- Lean semantics",
      "- proof artifact",
      "- deterministic semantics/proof traceability manifests and their coverage diagnostics",
      "",
      "Use Lean tools to confirm the final Lean semantics/proofs still compile.",
      "Only revisit official source evidence if the prior reviewed artifacts conflict",
      "or an unresolved state-affecting semantic claim remains.",
      "",
      "The required final-review artifact is mandatory.",
      "Write it with candidate_write at the exact orchestrator-supplied path.",
      "Then read/verify that exact artifact.",
      "Do NOT report SUCCESS until candidate_write has succeeded and the file exists.",
      "",
      "The final review must state:",
      "- BLOCKER/MAJOR/MINOR/NOTE counts",
      "- source-faithfulness status",
      "- unresolved state-affecting gaps",
      "- theorem weakening status",
      "- proof bypass status",
      "- Lean compilation status",
      "- readiness for explicit human final approval.",
      "Request revision only for unresolved BLOCKER/MAJOR findings; preserve MINOR/NOTE items as non-blocking review notes.",
      "",
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
