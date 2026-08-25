# Phase 2 design: Planner

## Boundary

Phase 2 reads the frozen Phase-1 SQLite index and produces a separate
formalization plan. It identifies formalization units, instruction membership,
source-supported dependency edges, strongly connected components, and a
processing order. It does not retrieve Phase-3 evidence, extract semantics,
generate Lean, check proofs, browse the web, or mutate the specification index.

## One-shot architecture

```text
Phase-1 specification.sqlite (read-only)
  -> one OpenCode spec2lean-planner agent
  -> structured submit_plan (units + dependency edges)
  <-> same-session deterministic diagnostics/correction
  -> deterministic SCC/layer derivation
  -> plan.json + plan.md + planner-run.json
```

There is no orchestrator retry or automatic second Planner session. Each
`submit_plan` call canonicalizes harmless set-like lists and validates the
candidate immediately. Invalid submissions return concise diagnostics to the
same Planner session. If that session ends without an accepted submission, the
runner writes its last exact diagnostics to `planner-run.json` and exits
nonzero.

## Planner isolation

The project-local OpenCode role is
`.opencode/agents/spec2lean-planner.md`. It pins
`openai/gpt-5.3-codex-spark` with `reasoningEffort: low`; the runner also passes
the model and `low` variant explicitly and records both in run metadata. It
denies shell, ordinary reads/edits, web access, skills, and subagents. The only
allowed capabilities are eight bounded read-only tools over the selected
SQLite database (`spec_tree`, `spec_search`, `spec_show`, `spec_children`,
`spec_ancestors`, `spec_subtree`, `spec_definitions`, `spec_xrefs`) and the
same-session `submit_plan` tool.

Each read-only tool records every complete Phase-1 node ID it returns in an
ephemeral per-session SQLite set. Submission rejects malformed, nonexistent,
or unobserved node IDs. The session state is removed after the run; only counts
and submission attempts are retained in `planner-run.json`.

The Planner proposes units and edges. It never proposes workflow control,
SCCs, or layers. Deterministic code validates the proposal, computes Tarjan
SCCs, condenses the graph, and creates topological processing layers.

## Edge direction and provenance

An edge points from a prerequisite (`fromUnitId`) to its dependent
(`toUnitId`). Every unit and edge has at least one Phase-1 `sourceNodeId`.
Inferred dependencies are explicitly marked `INFERRED`.

For an `EXPLICIT` edge, every edge support node must be a support node of the
dependent unit and must contain a resolved Phase-1 cross-reference whose exact
target is a support node of the prerequisite unit. This makes the distinction
between indexed facts and Planner inferences mechanically checkable.

The vocabulary and canonical JSON shape are defined by
`schemas/plan.schema.json`. Operational timestamps, runtime, OpenCode version,
model ID, reasoning setting, validation diagnostics, and statistics live in
`planner-run.json`, not the deterministic `plan.json`.

## Validation

The validator checks schema identity, specification/index identity, unit IDs,
unit kinds, instruction membership, source support, dependency endpoints,
self-edges, duplicate edges, dependency vocabulary, reasons, origins, all
source-node existence, and indexed-reference evidence for explicit edges. It
then verifies that stored SCCs and layers exactly equal deterministic graph
derivation.

Cycles are never silently broken. Every SCC is represented, including trivial
components; `cyclic: true` identifies mutually dependent components.
