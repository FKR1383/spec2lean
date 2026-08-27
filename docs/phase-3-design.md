# Phase 3: Retrieve Evidence

Phase 3 consumes a frozen Phase-1 SQLite database and an accepted Phase-2 plan.
It runs one bounded OpenCode Evidence Retriever session per selected planned
unit and writes a validated evidence bundle. It does not perform semantic
extraction, generate Lean, check code, or troubleshoot failures.

## Unit scope and exploration

Each session starts from the exact `sourceNodeIds` on its planned unit. It also
receives only external prerequisites connected to that unit by a Phase-2 edge
and source support on edges incident to the unit. Independent unit sessions may
run concurrently with `--jobs`; they never share a model session.

The read-only `specdb` server exposes:

- `spec_show`
- `spec_children`
- `spec_ancestors`
- `spec_subtree`
- `spec_search`
- `spec_xrefs`
- `spec_definitions`
- `spec_correlated`
- `submit_evidence`

Every session has an in-memory exposure ledger. Initial nodes are recorded with
their Phase-2 basis. Navigation tools can discover additional nodes only from
already exposed nodes; a discovered node must be shown with exact text before
it can be selected. Search is row-bounded, described as a last resort, and
requires a unit-specific justification. The ledger records tool calls, exposed
node/span IDs, and the access basis in `retriever-run.json`.

`submit_evidence` accepts source node IDs, optional source span IDs, one
controlled role, `CORE` or `SUPPORTING`, and a short relevance rationale. It
does not accept quotations, provenance, claims, interpretations, or generated
code. Invalid submissions return concise diagnostics to the same session. No
second session or automatic retry state exists.

## OpenCode isolation

The exact configuration is:

```text
model: openai/gpt-5.6-sol
reasoning/variant: medium
```

Both values are pinned on the command line, pinned in the isolated agent
configuration, and stored in run metadata. A model-catalog preflight fails
before creating evidence artifacts if that exact ID is unavailable. No model
substitution occurs. Project configuration and external skills are disabled;
shell, filesystem, internet, task/subagent, skill, and Lean capabilities are
denied. The only allowed tools are the local `specdb` tools.

## Deterministic evidence and provenance

The model never copies exact text or supplies source provenance. After a valid
selection, deterministic code reads Phase 1 and fills:

- exact text;
- source document ID, type, path, official URL, and SHA-256;
- section number/title and source node IDs;
- source span IDs;
- HTML anchor, DOM path, and source lines;
- PDF page, bounding boxes, and block/line/span indices.

A record may select one node, a contiguous span range, or a small contiguous
group of sibling nodes. Group and span contiguity are checked. Exact text is
reconstructed in source order. Detailed per-node/per-span provenance remains
in the `provenance` array even when the convenient top-level page, bounding
box, or anchor is necessarily null for a multi-location selection.

Evidence IDs are content-addressed SHA-256-derived IDs over the Phase-1
database digest, canonical node/span selection, role, and tier. They do not
depend on selection order, session time, or unit ID. Consequently, the same
shared supporting fragment selected with the same role/tier can have the same
ID in multiple unit bundles.

The validator rejects wrong units, missing nodes/spans, identifiers not exposed
in the session, noncontiguous groups, empty text, invalid roles/tiers, duplicate
source selections or IDs, missing CORE evidence, database digest mismatches,
and any mismatch in deterministic quotation, document SHA, HTML provenance,
PDF provenance, or exposure basis. Stored bundles can be replayed against the
read-only Phase-1 database.

## Artifacts and inspection

Successful unit sessions contain:

```text
evidence/<language>/<version>/<plan-run-id>/<unit-slug>-<unit-id-prefix>/
  evidence.json
  evidence.md
  retriever-run.json
```

`evidence.json` is canonical. `evidence.md` is a deterministic human-readable
view split into CORE and SUPPORTING evidence. `retriever-run.json` records the
exact model/reasoning, bounded scope, exposure trace, one-session status,
command, and OpenCode event output. Phase-1 and Phase-2 artifacts are opened
read-only and are never modified.

Inspection commands do not invoke OpenCode:

```bash
./spec2lean evidence units --plan-run PLAN_RUN_ID
./spec2lean evidence show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean evidence core --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean evidence supporting --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean evidence provenance --evidence EVIDENCE_ID
./spec2lean evidence stats --plan-run PLAN_RUN_ID
```

Normal tests use synthetic HTML and generated PDF fixtures. The runner is
tested with a fake process and never calls a real OpenCode session.
