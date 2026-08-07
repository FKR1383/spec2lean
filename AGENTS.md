# Spec2Lean Project Rules

## Mission

Spec2Lean is a general-purpose, agentic, human-in-the-loop,
verification-guided, and source-traceable engine for formalizing
language specifications in Lean 4.

The primary product is the Spec2Lean Agentic Engine.
PTX is only the first case study.

## Current State

The first end-to-end PTX unit (`add.u32`) has completed the manual reference
workflow, including source curation, semantic review, Lean mapping, theorem
review, machine-checked proofs, final critique, and human acceptance.

The repository now contains a persistent automated orchestrator. New bounded
units are expected to run through the orchestrator and stop at explicit human
gates. `mov.b32` is the first hardening/validation run for this automated path.

Do not invent specification evidence or placeholder semantics. Existing
accepted artifacts are reference material, not authority for a new unit unless
the current run explicitly depends on them.

## Model Policy

The project model is configured in `opencode.json`. Automated agents currently
use `opencode/deepseek-v4-flash-free` unless the project configuration and
agent definition are explicitly changed.

Do not guess or silently replace a model ID. The orchestrator must read the
project model configuration rather than hard-code a different model.

## Authority Order

1. Official specification evidence
2. Human-approved semantic interpretation
3. Human-approved Lean mapping
4. Lean type checking, evaluation, and proof checking
5. Agent suggestions

LLM output is provisional.

A successful Lean build establishes internal formal validity only.
It does not establish faithfulness to specification prose.

## Human Gates

No agent may skip or self-approve a human gate.

Human approval is required for the formalization workflow at:

- Gate A: language architecture
- Gate B: semantic interpretation
- Gate C: Lean mapping
- theorem-strength approval before proof generation
- final acceptance

Translation mode may introduce additional translation-specific gates later.

Nothing may be promoted to `accepted/` without explicit human approval.

## Repository Boundaries

- `engine/`: orchestration code
- `documents/`: specifications, indexes, and source metadata
- `ir/`: core IR and language-specific extensions
- `language_packs/`: language-specific configuration
- `.opencode/agents/`: OpenCode agent definitions
- `.opencode/tools/`: restricted custom tools
- `lean/`: Lean package
- `runs/`: execution records
- `candidates/`: mutable generated artifacts
- `accepted/`: human-approved artifacts
- `reviews/`: review artifacts
- `evaluation/`: evaluations
- `tests/`: non-Lean tests

Agents must not modify `accepted/`.

## Workflow Rules

The automated orchestrator is the default execution path for new bounded
formalization units. A run is persistent and resumable under `runs/<run-id>`.

Within one run, stages are sequential and guarded by the workflow state
machine. Do not parallelize dependent agents or skip human gates.

Keep every task bounded to one small unit, such as:

- one construct or instruction
- one source-bundle revision
- one semantic-interpretation revision
- one Lean mapping
- a small theorem set
- one proof subtask or one concrete technical error class

Do not start a dependent step before the preceding artifact and required
human decision are complete.

`add.u32` is the completed reference unit. New units must not assume its
semantics; they may reuse only explicitly approved shared infrastructure.

## Formalization Restrictions

Never introduce:

- `sorry`
- `admit`
- new `axiom` declarations
- `unsafe` to bypass verification
- weakened theorem statements
- vacuous correctness theorems
- undocumented assumptions
- semantics copied from unrelated languages

When evidence is insufficient, report the unit as blocked.

When a theorem appears false, report the conflict or counterexample.
Do not change semantics or weaken the theorem silently.

## Artifact Discipline

Mutable work belongs in `candidates/`.

Review decisions belong in `reviews/`.

Run metadata belongs in `runs/`.

Only human-approved artifacts may enter `accepted/`.

Never overwrite source evidence.

Every semantic claim must eventually be traceable to exact official
source evidence.

## Lean Commands

From the repository root, run the full Lean build with:

    cd lean && lake build

To check one Lean file:

    cd lean && lake env lean PATH/TO/FILE.lean

A successful build is necessary but not sufficient for semantic acceptance.

## Git Rules

Keep changes small and reviewable.

Do not run destructive Git commands.

Do not push, commit, tag, rewrite history, or promote artifacts unless
the human explicitly performs or approves the action.

Never expose credentials, OAuth tokens, environment secrets, or private
configuration.
