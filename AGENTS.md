# Spec2Lean Project Rules

## Mission

Spec2Lean is a general-purpose, agentic, human-in-the-loop,
verification-guided, and source-traceable engine for formalizing
language specifications in Lean 4.

The primary product is the Spec2Lean Agentic Engine.
PTX is only the first case study.

## Current State

This repository is being built from scratch.

Do not assume that any document pipeline, Semantic IR, PTX semantics,
fixture, orchestrator, custom tool, accepted formalization, or theorem
library already exists.

Do not invent specification evidence or placeholder semantics.

## Model Policy

Until the first successful end-to-end formalization unit is complete,
all agents must use:

- model: `openai/gpt-5.6-sol`
- reasoning effort: `high`

Do not guess or silently replace the model ID.

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

Human approval is required for:

- language architecture
- semantic interpretation
- Lean mapping
- translation theorem design
- final acceptance

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

Work sequentially during the initial manual workflow.

Do not parallelize agents.

Keep every task bounded to one small unit, such as:

- one construct or instruction
- one source bundle
- one semantic interpretation
- one Lean file
- a small theorem set
- one technical error class per repair step

Do not start a dependent step before the preceding artifact and required
human decision are complete.

The first end-to-end case study is only PTX `add.u32`.

Do not add another instruction until `add.u32` passes all semantic,
Lean, proof, critic, and human-review stages.

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
