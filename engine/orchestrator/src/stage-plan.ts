import type {
  FormalizationStage,
  RunState,
} from "./workflow.js"
import { leanDeclarationNamespace } from "./lean-language.js"

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
      "Produce or revise the complete architecture for the exact requested unit; FULL_INSTRUCTION is the default.",
      "Treat the approved shared semantic environment as the build-once language core. When it exists and is eligible, produce only a unit delta instead of redeclaring language-wide value, state, operand, guard, environment, or error models.",
      "When no approved core exists, mark a BOOTSTRAP_CANDIDATE boundary explicitly; never pretend a per-unit invention is already shared.",
      "Use only the exact shared-environment IDs listed by the deterministic input contract; per-unit accepted artifacts are examples, not shared authority.",
      "For PTX call spec_fast_context exactly once with purpose=architecture; never inspect another unit's candidate or accepted artifacts.",
      "Include the canonical SPEC2LEAN_ARCHITECTURE_INDEX and mark every behavior-affecting open entry stateAffecting=true.",
      "Include the exact nine-row SPEC2LEAN_COMPLETENESS_CONTRACT and never exclude a legal case in prose alone.",
      "Do not invent open questions from mere source silence about inapplicable hidden features; express an explicit bounded model omission as DESIGN_DEPENDENCY/ASSUMPTION, never as a source-derived absence claim.",
      "Use SOURCE_FACT entries as internal roots with empty evidence/dependency arrays; exact official locators remain mandatory in the prose.",
      "Stay within the deterministic architecture byte/line budget and use the exact required section headings.",
      "Write only through candidate_architecture_write, then run candidate_validate.",
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
      "Check bounded scope, evidence/design classification, applicable value/state model, and every behavior-affecting ambiguity; do not redesign the unit.",
      "Apply the canonical architecture classification policy from the runtime contract; in particular, do not reject root SOURCE_FACT entries for empty internal evidence arrays or reject an explicitly labeled project model boundary merely because it is not NVIDIA prose.",
      "Do not demand speculative open questions for machine features whose applicability is unsupported.",
      "Triage every runtime-listed state-affecting OPEN_QUESTION as GENUINE_HUMAN_REVIEW or REMOVE_OR_RECLASSIFY in the required machine-readable block; the latter requires a blocking finding and architecture revision.",
      "Request revision only for unresolved BLOCKER/MAJOR findings.",
      "MINOR/NOTE-only findings are non-blocking: record them and return SUCCESS to the human gate.",
      "If suitable, mark it ready for Human Gate A.",
      "End the review artifact with numeric BLOCKER, MAJOR, MINOR, NOTE counts and PRE_GATE_REVISION_REQUIRED: true|false.",
      "Do not approve Gate A yourself.",
    ].join("\n"),
  },

  SOURCE_CURATION: {
    agent: "source-curator",
    successStage: "SEMANTIC_EXTRACTION",
    revisionStages: [],
    task: [
      "Build the complete official-source evidence bundle for the exact unit.",
      "Use canonical source-bundle schema v3, its exact nine-row coverage_matrix, and exact hash-pinned PDF/HTML fragments.",
      "Close syntax, operands, types, operation branches, edge cases, guards, state effects, errors, and applicability through evidence, NOT_APPLICABLE rationale, or an explicit gap.",
      "Do not invent missing semantic facts.",
      "Classify every evidence gap LOAD_BEARING or NON_LOAD_BEARING; a load-bearing gap blocks semantic extraction.",
    ].join("\n"),
  },

  SEMANTIC_EXTRACTION: {
    agent: "semantic-extractor",
    successStage: "SEMANTIC_CRITIQUE",
    revisionStages: [
      "SOURCE_CURATION",
    ],
    task: [
      "Produce canonical full-instruction semantics from the exact curated evidence and Gate-A-authorized architecture.",
      "Use schemaVersion 3, scopeStatus=FULL_INSTRUCTION by default, the exact coverage matrix, languageCore binding, and mandatory proofRequirements.",
      "For every SOURCE_FACT, cite current-bundle evidence that covers every official rendition required by the source manifest; direct PDF fragments or deterministic PDF alignment from an exact HTML quotation are acceptable.",
      "Separate source facts, derived interpretations, design dependencies,",
      "human-approved assumptions, and open questions.",
      "Do not fabricate semantics.",
      "An unresolved state-affecting open question must remain explicit.",
      "Without an orchestrator-supplied benchmark waiver it blocks downstream Lean generation.",
      "With CONSERVATIVE_BOUNDED_SCOPE, preserve it and add an explicit DESIGN_DEPENDENCY/precondition that makes disputed cases partial or excluded; never invent their behavior.",
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
      "Do not inspect or cite existing Lean mappings, theorem obligations, proofs, or downstream reviews; they may be stale and cannot be repaired by semantic extraction.",
      "Check every SOURCE_FACT against exact evidence IDs and every derived/design claim against explicit dependencies.",
      "Build a compact behavior-branch matrix covering applicable input/type cases, errors, host variation, guards, and state effects; do not demand inapplicable machine features.",
      "A runtime-listed CONSERVATIVE_BOUNDED_SCOPE waiver is acceptable only when the OPEN_QUESTION remains unresolved and the disputed cases are explicitly partial/excluded rather than guessed.",
      "Request source or semantic revision only when the problem is BLOCKER/MAJOR.",
      "MINOR/NOTE-only findings are non-blocking: record them and return SUCCESS to the human gate.",
      "Otherwise mark it ready for Human Gate B.",
      "End the review artifact with numeric BLOCKER, MAJOR, MINOR, NOTE counts and PRE_GATE_REVISION_REQUIRED: true|false.",
      "Do not approve Gate B.",
    ].join("\n"),
  },

  LEAN_FORMALIZATION: {
    agent: "lean-formalizer",
    successStage: "LEAN_MAPPING_CRITIQUE",
    revisionStages: [],
    task: [
      "Implement the exact Gate-B-authorized full-instruction semantics in Lean; the prompt distinguishes human approval from benchmark-only auto-advance.",
      "Reuse the approved language core instead of redefining shared value/state/operand/guard machinery.",
      "Add the deterministic SPEC2LEAN_LEAN_MODEL_CONTRACT; fixed-width domains may not be represented by unconstrained Int/Nat.",
      "Every partial exclusion must be executable as a named precondition/partial result, not merely documented.",
      "For a CONSERVATIVE_BOUNDED_SCOPE benchmark waiver, encode only source-established cases, make unresolved cases partial or precondition-excluded, and mark the module PARTIAL_EXPLICIT.",
      "Enumerate exact authorized semantic IDs before writing and validate every traceability citation against them.",
      "Use only the exact deterministic provenance allowlist and the `-- spec2lean: ID` declaration comment format.",
      "On revision, read the latest Lean-mapping critic artifact first and make only its required BLOCKER/MAJOR repairs.",
      "Place all unit-specific declarations under namespace <LEAN_NAMESPACE> supplied by the orchestrator.",
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
      "Compare every executable and relational branch against the approved behavior-branch matrix, including all applicable input/type, error, host, guard, and state cases.",
      "Use small Lean probes only when needed to decide a concrete mapping question; do not begin theorem design here.",
      "Request revision only for unresolved BLOCKER/MAJOR findings; MINOR/NOTE-only findings proceed to the human gate.",
      "If faithful, mark it ready for Human Gate C.",
      "End the review artifact with numeric BLOCKER, MAJOR, MINOR, NOTE counts and PRE_GATE_REVISION_REQUIRED: true|false.",
      "Do not approve Gate C.",
    ].join("\n"),
  },

  THEOREM_GENERATION: {
    agent: "theorem-designer",
    successStage: "THEOREM_STRENGTH_CRITIQUE",
    revisionStages: [],
    task: [
      "Generate the complete, non-redundant correctness theorem set from the exact Gate-C-authorized mapping.",
      "Use theorem contract schema v3 and classify each obligation by correctness_kind.",
      "Require an operation-fidelity theorem and an execution-correspondence theorem; syntax/style/typechecking lemmas alone are insufficient.",
      "Map every semantics proofRequirement ID to exactly one independent theorem, including algorithm, result-range, guard, state-update, frame, operation, and execution-correspondence properties.",
      "Operation/algorithm/range/edge theorems must compare a separate source-level specification function/relation with implementation symbols; self-unfolding restatements are invalid.",
      "Execution correspondence must mention both executable and relational definitions from the Lean model contract.",
      "Bind every obligation to the exact semantic claim IDs it verifies and state the source-faithfulness boundary explicitly.",
      "Store each complete header-only Lean theorem declaration in theorem_obligations[].lean_statement_sketch; this JSON is the pre-proof theorem contract.",
      "Write and verify the complete obligation artifact before emitting the result protocol.",
      "Copy the exact orchestrator-supplied SUCCESS stage name; never invent or reuse a *_REVIEW alias.",
      "On revision, read the latest theorem-strength critic artifact first and repair every BLOCKER/MAJOR finding.",
      "Pin the intended Lean namespace to <LEAN_NAMESPACE> and make supporting theorem names unit-specific where collision is possible.",
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
      "Review the deterministically supplied declarations from the latest obligations JSON; theorem declarations are intentionally not written to a .lean proof file until PROOF_GENERATION.",
      "Never report declarations as missing merely because the Lean mapping file contains definitions only.",
      "Extract and count complete theorem declarations; reject placeholders, truncated statements, or duplicate names.",
      "For determinism/totality/correspondence obligations, analyze constructor overlap and missing premises and use a minimal Lean counterexample/probe when the result is not syntactically certain.",
      "For every theorem with a deterministic behavior-branch inventory, audit every supplied branch ID and emit the required SPEC2LEAN_THEOREM_BEHAVIOR_AUDIT block; a single counterexample is a blocking revision.",
      "A compiling statement is not evidence that the theorem is true or non-vacuous.",
      "Request revision only for unresolved BLOCKER/MAJOR findings; MINOR/NOTE-only findings proceed to the human gate.",
      "If adequate, mark the set ready for human theorem-strength approval.",
      "End the review artifact with numeric BLOCKER, MAJOR, MINOR, NOTE counts and PRE_GATE_REVISION_REQUIRED: true|false.",
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
      "Prove exactly the frozen theorem declarations authorized at the theorem-strength boundary; the prompt states whether authorization was human or benchmark-only.",
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
      "Do not repeat broad official-source searches that were already independently checked",
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
      "End the review artifact with numeric BLOCKER, MAJOR, MINOR, NOTE counts and PRE_GATE_REVISION_REQUIRED: true|false.",
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

  return {
    ...plan,
    task: plan.task.replaceAll("<LEAN_NAMESPACE>", leanDeclarationNamespace(run)),
  }
}
