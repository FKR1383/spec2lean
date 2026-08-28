# Phase 2: Request-scoped Planner

Phase 2 resolves a bounded planning request against the frozen Phase 1 SQLite
database, gives that context to one restricted OpenCode Planner session, and
deterministically validates the semantic submission. It does not implement
semantic extraction or Lean generation.

## Typed requests and scope resolution

`request.json` has one, and only one, of four scope modes:

- `EXACT_INSTRUCTIONS` contains an array of exact instruction spellings.
- `INSTRUCTION_FAMILY` contains a conceptual family description.
- `SOURCE_SUBTREE` contains one exact Phase 1 `node:` ID.
- `FULL_SPECIFICATION` contains no implicit selector and is available only via
  the explicit `--all` CLI flag.

Exact instructions are resolved before OpenCode starts. Resolution locates the
instruction heading and checks the exact spelling against literal indexed text
or finite syntax alternatives (for example, `mul.mode.type` plus the indexed
`.mode` and `.type` sets). An unresolved spelling aborts the run. Source
subtrees remain rooted at the requested node. Family resolution finds bounded
structural candidates; OpenCode may select membership only from those
candidates. The full specification is never selected implicitly.

Initial context contains resolved source sections, ancestors, explicit cross
references, correlated source representations, and candidate IDs. Additional
Phase 1 access is row-, depth-, and text-bounded.

## Planner isolation

The runner launches exactly one `opencode run` process with:

```text
model: openai/gpt-5.6-sol
reasoning/variant: medium
```

The exact values are passed on the command line, pinned in the isolated agent
configuration, and recorded in `planner-run.json`. Before creating a run,
Spec2Lean checks OpenCode's model catalog and refuses to start a session if the
exact ID is unavailable; it never substitutes a similarly named model. Project
configuration, external skills, and inherited OpenCode configuration are disabled
for the session. OpenCode's built-in provider adapter remains enabled because
OpenAI OAuth authentication depends on it; `--pure` excludes external plugins.
Shell, filesystem, internet, subagent, skill, and Lean tools are disabled.

The local read-only MCP server exposes:

- `spec_search`
- `spec_show`
- `spec_children`
- `spec_ancestors`
- `spec_subtree`
- `spec_xrefs`
- `spec_definitions`
- `submit_plan`

`submit_plan` returns structural diagnostics within the same session. The
Planner may correct a submission and call the tool again. Spec2Lean never
starts a retry session; if the one session exits without an accepted
submission, the run fails.

## Plan and validation

The model submits requested candidate IDs, specification-derived translation
groups, external prerequisite concepts, and dependency edges. Every requested
unit belongs to exactly one translation group. Group names are concise
UpperCamelCase identifiers derived from indexed headings, ancestors,
terminology, and semantic cohesion; each group records a reason, `EXPLICIT` or
`INFERRED` origin, and Phase 1 source nodes supporting every member. There is no
language- or mnemonic-specific category table in later phases.

Deterministic code supplies language/version, run identity,
source database digest, timestamps, validated source identity, external
prerequisite IDs, processing layers, and cycle reporting.

An edge is directed from prerequisite to dependent. Its origin is exactly
`EXPLICIT` or `INFERRED`, and it must have a reason and existing Phase 1 source
nodes. External prerequisites are graph endpoints but are not scheduled units.

Validation rejects out-of-scope units, missing exact units, incomplete or
overlapping group partitions, invalid group/file identifiers, group support
outside a member's indexed source ancestry, invented nodes,
unknown endpoints, self edges, duplicate edges, missing reasons/support, and
invalid origins. Layers are derived from requested-unit edges, so independent
units share a layer. Strongly connected components are emitted in `cycles` and
the graph is marked `CYCLIC`; their edges are not removed and cyclic units are
not assigned a false processing layer. Requested units downstream of a cycle
are listed in `blockedUnitIds` rather than assigned a misleading layer.

Successful runs contain:

```text
plans/<language>/<version>/<plan-run-id>/
  request.json
  plan.json
  plan.md
  planner-run.json
```

Generated plan directories are ignored by Git. `planner-run.json` retains the
single session's JSON event stream and stderr for human inspection.

## Tests

Normal tests use a synthetic specification and never invoke OpenCode. The
runner test substitutes a local fake process that writes through the same
submission boundary. Fixtures cover independent units, dependencies and
layers, external prerequisites, unresolved exact instructions, scope
expansion, invented nodes, duplicate/self edges, cycles, locked model metadata,
and capability isolation.
