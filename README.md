# Spec2Lean

Current release: **1.1.0**. See [CHANGELOG.md](CHANGELOG.md) for release notes.

Spec2Lean implements **Phase 1: Parse + Index**, **Phase 2: Request-scoped
Planner**, **Phase 3: Retrieve Evidence**, **Phase 4: Semantic Extractor and
Open Question Handler**,
**Phase 5: Shared-Core Materializer and LLM Translator**, **Phase 6: Check**,
and **Phase 7: Troubleshooter**.
Phase 1 turns an official
PDF and/or HTML language specification into a deterministic, searchable,
hierarchical SQLite database. Phase 2
resolves an explicitly bounded request, invokes one restricted OpenCode Planner
session, identifies source-supported semantic concepts shared by the requested
subset, validates its dependency graph, and writes an inspectable plan. Phase 3
runs one bounded Evidence Retriever session per planned unit and deterministically
resolves its selections to exact Phase-1 text and provenance. Phase 4 runs one
evidence-bounded Semantic Extractor session per unit and validates a structured,
traceable semantic artifact. If evidence is insufficient, a separate handler
checks the canonical database first and records any internet, runtime, or LLM
fallback as explicitly non-normative before extraction restarts. Phase 4 also
binds each planned shared prerequisite to the unit-local claims that define its
meaning. Phase 5 materializes or reuses one frozen, specification-specific Lean
core, then runs one semantic-artifact-bounded session per instruction group to
generate exactly one complete Lean 4 file and cross-unit declaration
traceability. Phase 6 compiles each group against that exact core and
deterministically checks per-unit forward coverage and group-wide reverse
traceability.
Phase 7 routes semantic failures upstream and uses one compiler-guided OpenCode
session to repair build-only failures without permitting core redesign.

The top-level Pipeline Runner composes those phase APIs without duplicating
their logic. It validates or rebuilds Phase 1, reuses a matching fresh Phase-2
plan when available, completes instruction-scoped evidence and semantics first,
freezes one compatible shared core for the request, then advances grouped
translation/checking until every unit passes or bounded Phase-7 routing resolves
the failure.

Python is used because PyMuPDF exposes PDF layout/font/bounding-box data and
`lxml` preserves semantic HTML structure and source lines. SQLite and FTS5
provide a local, inspectable canonical index without an external service.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

The repository-local wrapper automatically uses `.venv/bin/python` when it is
present.

## Open the artifact explorer

After a pipeline run, launch the read-only local GUI:

```bash
./spec2lean gui
```

Then open `http://127.0.0.1:8000`. To open a particular run immediately or use
a different local port:

```bash
./spec2lean gui --run pipeline-run:RUN_ID
./spec2lean gui --port 8080
```

The explorer lists complete, partial, and failed runs. Its primary unit view
connects generated Lean declarations to their Phase-4 claims, exact Phase-3
evidence, and Phase-1 HTML/PDF provenance. PDF evidence pages are rendered on
demand with their recorded bounding boxes highlighted. When both official
renditions are attached to a planned unit, new factual claims must cite both,
so the GUI presents the matching HTML and PDF evidence together. The GUI does
not edit artifacts or run pipeline phases, and binds to localhost by default.

## Build and validate PTX 9.3

```bash
./spec2lean index build \
  --language ptx \
  --version 9.3 \
  --pdf documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.pdf \
  --html documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html

./spec2lean index validate --language ptx --version 9.3
./spec2lean index stats --language ptx --version 9.3
```

The canonical local database is `indexes/ptx/9.3/specification.sqlite`. The
same `index build` command also writes a deterministic, page-marked PDF text
representation under `indexes/ptx/9.3/text/*.pages.txt`. Later phases can read
this UTF-8 text without reopening or rendering the PDF; each source page is
delimited by `===== PDF PAGE N OF M =====`. The database remains authoritative
for hierarchy and provenance.

Generated indexes, manifests, and page-text files are intentionally Git-ignored
because they are reproducible from the hash-pinned official inputs.

```bash
# Locate and inspect the generated sequential PDF text.
find indexes/ptx/9.3/text -name '*.pages.txt' -print
less indexes/ptx/9.3/text/*.pages.txt

# Find page markers and occurrences without parsing the PDF again.
rg -n 'PDF PAGE|shl' indexes/ptx/9.3/text/*.pages.txt
```

## Run the x86 sample

Fetch Intel's official revision-092 Volume 2A instruction-set reference once:

```bash
documents/sources/intel/x86/092/fetch.sh
```

Then run the complete pipeline from Phase 1 for five simple instructions:

```bash
./spec2lean run \
  --language x86 \
  --version 092 \
  --instructions ADD,AND,CMP,DEC,INC \
  --from index
```

Volume 2A covers instructions A-L. The source PDF is cached locally and ignored
by Git; its acquisition URL, SHA-256 checksum, and metadata are preserved under
`documents/sources/intel/x86/092/`.

## Inspect without SQL

```bash
# Heading hierarchy for both source representations.
./spec2lean index tree --language ptx --version 9.3

# Select only one source representation or include all content nodes.
./spec2lean index tree --language ptx --version 9.3 --source-type html
./spec2lean index tree --language ptx --version 9.3 --source-type pdf --all-nodes --max-depth 3

# Find an instruction section, then copy a node_id from the JSON result.
./spec2lean index search --language ptx --version 9.3 --query shl

./spec2lean index show --node NODE_ID
./spec2lean index children --node NODE_ID
./spec2lean index ancestors --node NODE_ID
./spec2lean index subtree --node NODE_ID
./spec2lean index subtree --node NODE_ID --all-nodes

./spec2lean index definitions --language ptx --version 9.3 --limit 50
./spec2lean index xrefs --language ptx --version 9.3 --status UNRESOLVED

./spec2lean index dump --language ptx --version 9.3 --format tree --output /tmp/ptx-tree.txt
./spec2lean index dump --language ptx --version 9.3 --format json --output /tmp/ptx-index.json
```

`show` includes exact parser-extracted `raw_text`, the source SHA/path/URL,
PDF pages and bounding boxes, HTML anchors and DOM paths, definitions, cross
references, and any exact PDF↔HTML heading correlation.

## Inspect with SQLite

```bash
sqlite3 indexes/ptx/9.3/specification.sqlite
```

Useful queries:

```sql
.headers on
.mode column

-- Source identity and measurable text coverage.
SELECT source_type, sha256, page_count, source_text_chars,
       indexed_text_chars,
       round(1.0 * indexed_text_chars / source_text_chars, 4) AS coverage
FROM documents;

-- Top-level chapters in deterministic order.
SELECT c.node_id, c.section_number, c.title
FROM nodes AS c
JOIN nodes AS root ON root.node_id = c.parent_id
WHERE root.node_type = 'document' AND c.node_type = 'chapter'
ORDER BY c.document_id, c.ordinal;

-- Direct children of a copied node ID.
SELECT ordinal, node_id, node_type, section_number, title
FROM nodes WHERE parent_id = 'NODE_ID' ORDER BY ordinal;

-- Complete subtree of a copied node ID.
WITH RECURSIVE subtree(node_id, depth) AS (
  SELECT node_id, 0 FROM nodes WHERE node_id = 'NODE_ID'
  UNION ALL
  SELECT n.node_id, subtree.depth + 1
  FROM nodes AS n JOIN subtree ON n.parent_id = subtree.node_id
)
SELECT printf('%.*c', depth * 2, ' ') || coalesce(n.title, n.node_type) AS item,
       n.node_id
FROM subtree JOIN nodes AS n USING (node_id);

-- Exact source spans for a node (PDF bbox or HTML DOM position).
SELECT page_number, bbox_x0, bbox_y0, bbox_x1, bbox_y1,
       block_index, line_index, span_index, dom_path,
       source_line_start, raw_text
FROM source_spans WHERE node_id = 'NODE_ID' ORDER BY ordinal;

-- FTS5 instruction search.
SELECT n.node_id, n.node_type, n.section_number, n.title
FROM nodes_fts JOIN nodes AS n USING (node_id)
WHERE nodes_fts MATCH 'shl' LIMIT 20;

-- Definitions and unresolved references.
SELECT t.term, d.node_id, d.structural_basis, d.definition_text
FROM definitions AS d JOIN terms AS t USING (term_id)
ORDER BY t.normalized_term;

SELECT source_node_id, kind, raw_text, target_reference_text
FROM cross_references WHERE resolution_status = 'UNRESOLVED'
ORDER BY source_node_id, ordinal;
```

## Tests

```bash
.venv/bin/pytest
```

Synthetic HTML and generated PDF fixtures cover hierarchy, semantic element
types, anchors, page/bounding-box provenance, FTS, cross-reference resolution,
SHA invalidation, structural validation, subtrees, and deterministic rebuilds.
Generic shared-core fixtures additionally cover canonical declaration reuse,
append-only extension, stale-input invalidation, concurrent publication,
traceability through imported declarations, and multi-module Lean compilation.

See [the Phase 1 design](docs/phase-1-design.md) for schema and parser details.

## Run the end-to-end pipeline

Use the same typed scope selectors as `plan build`:

```bash
./spec2lean run \
  --language ptx \
  --version 9.3 \
  --instructions add.u32,sub.u32,shl.b32
```

The runner writes an atomic run manifest under
`runs/<language>/<version>/<pipeline-run-id>/run.json`. `./spec2lean status
--run PIPELINE_RUN_ID` shows the persisted plan, per-unit stage dispositions,
routing outcome, and terminal status.

Progress is printed immediately to stderr with the pipeline run ID, current
unit, phase, reuse decision, check result, and Phase-7 route. The final complete
manifest remains JSON on stdout. Ctrl-C records an `INTERRUPTED` manifest and
prints the exact run ID to pass back to `--resume` instead of emitting a Python
traceback.

Resume the latest compatible run by repeating its scope and adding `--resume`,
or name a run explicitly with `--resume PIPELINE_RUN_ID`:

```bash
./spec2lean run \
  --language ptx --version 9.3 --instructions add.u32,sub.u32,shl.b32 \
  --resume
```

Resume never blindly trusts a file's presence. Phase 3 is rebound to the plan
and Phase-1 digest; Phase 4 is rebound to the evidence hash; a shared core is
revalidated against its source digest, representation/generator policy, and
the exact relevant Phase-4 dependencies and claims; and each group translation
is rebound to its semantic artifacts and exact core reference. Phase 6 is
rebound to the semantic, Lean-source, and translation-manifest hashes plus the
core source and manifest hashes when a core is present. Fresh artifacts are
reused. An incomplete or stale generated unit/group directory is moved beneath
the run's `superseded/` directory before a bounded retry. Superseded core
snapshots remain immutable in their version store while the atomic current
pointer advances. Phase-7 routing stops on success, repeated actionable state,
or the `--max-dispatches` limit.

Phase 1 is checked on every invocation. The existing index is reused only when
its SQLite structure, parser/schema versions, official source hashes, and PDF
page-text sidecar validate. Otherwise it is rebuilt from the hash-pinned local
official sources. A resumed plan whose source digest no longer matches is
rejected as stale.

Use `--dry-run` to inspect projected reuse and work without creating a run or
starting OpenCode. `--from PHASE` forbids creation in earlier phases and
therefore requires their fresh artifacts; `--until PHASE` stops after the named
phase. The phase names are `index`, `plan`, `evidence`, `semantics`, `translate`,
`check`, and `troubleshoot`.

Resolve any generated Lean declaration all the way back through semantic claims
and exact source provenance with:

```bash
./spec2lean trace --declaration Spec2Lean.Ptx.AddU32.execute
```

A deliberately small real PTX experiment is:

```bash
./spec2lean run --language ptx --version 9.3 --instructions add.u32
```

This is intentionally not part of the deterministic test suite because it
starts bounded OpenCode sessions.

## Build a request-scoped plan

Phase 2 requires the exact installed OpenCode model
`openai/gpt-5.6-sol` and uses reasoning variant `medium`. Choose exactly one
scope selector. A quota-free catalog preflight fails before creating a run if
that exact model is unavailable; no fallback model is selected.

```bash
# Exact instruction spellings.
./spec2lean plan build \
  --language ptx \
  --version 9.3 \
  --instructions add.u32,sub.u32,mul.lo.u32,shl.b32

# Conceptual family (membership remains bounded by Phase 1 candidates).
./spec2lean plan build \
  --language ptx \
  --version 9.3 \
  --family "integer arithmetic instructions"

# Exact Phase 1 subtree.
./spec2lean plan build \
  --language ptx \
  --version 9.3 \
  --source-node node:PHASE_1_NODE_ID

# Full-document planning is available only when explicitly requested.
./spec2lean plan build --language ptx --version 9.3 --all
```

The build prints its run directory and plan run ID. Inspect an accepted run
without invoking OpenCode again:

```bash
./spec2lean plan show --run PLAN_RUN_ID
./spec2lean plan units --run PLAN_RUN_ID
./spec2lean plan groups --run PLAN_RUN_ID
./spec2lean plan deps --run PLAN_RUN_ID
./spec2lean plan layers --run PLAN_RUN_ID
./spec2lean plan prerequisites --run PLAN_RUN_ID
./spec2lean plan graph --run PLAN_RUN_ID --format dot --output /tmp/plan.dot
```

The schema-v3 plan keeps requested units and `sharedPrerequisites` separate. A
shared prerequisite has a stable generic `shared:*` ID, specification-derived
name and open `kind`, supporting Phase-1 nodes, and the exact requested units in
`requiredBy`. It does not schedule another unit or select a Lean representation.

See [the Phase 2 design](docs/phase-2-design.md) for scope rules, Planner
isolation, submission validation, cycles, and artifact ownership.

## Retrieve exact evidence for a planned unit

Phase 3 requires the exact installed OpenCode model
`openai/gpt-5.6-sol` with reasoning variant `medium`. The model selects
only node/span IDs and relevance labels; deterministic code supplies quotations,
hashes, anchors, pages, bounding boxes, and all other source provenance.

Start with one manually selected unit rather than the complete plan:

```bash
./spec2lean plan units --run PLAN_RUN_ID

./spec2lean evidence build \
  --plan-run PLAN_RUN_ID \
  --unit UNIT_ID
```

`--unit` may be repeated for a small subset. Omit it only when intentionally
retrieving every requested unit. Independent unit sessions default to serial
execution; set a small `--jobs N` to run them concurrently.

Inspect accepted artifacts without calling OpenCode:

```bash
./spec2lean evidence units --plan-run PLAN_RUN_ID
./spec2lean evidence show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean evidence core --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean evidence supporting --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean evidence provenance --evidence EVIDENCE_ID
./spec2lean evidence stats --plan-run PLAN_RUN_ID
```

See [the Phase 3 design](docs/phase-3-design.md) for the exposure boundary,
OpenCode isolation, schema, content-addressed IDs, provenance reconstruction,
validation, and artifacts.

## Extract structured semantics from one evidence bundle

Phase 4 requires the exact installed OpenCode model
`openai/gpt-5.6-sol` with reasoning variant `medium`. The extractor receives
only the selected unit's Phase-3 evidence bundle and exposes only the structured
`submit_semantics` tool. On `INSUFFICIENT_EVIDENCE`, a separate handler searches
the canonical Phase-1 database first. Only when the specification does not
answer the question may it use attributed internet evidence, a configured
runtime probe, or explicitly flagged LLM reasoning. The augmented bundle is
validated before a fresh extraction attempt.

Run the first experiment on one unit that already has a valid evidence bundle:

```bash
./spec2lean semantics build \
  --plan-run PLAN_RUN_ID \
  --unit UNIT_ID
```

Omitting `--unit` intentionally processes every evidence-backed unit in the
plan serially. Inspect artifacts without invoking OpenCode:

```bash
./spec2lean semantics show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics claims --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics operation --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics evidence --claim CLAIM_ID
./spec2lean semantics questions --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics stats --plan-run PLAN_RUN_ID
```

Recovery is bounded to two rounds by default. Use
`--max-question-rounds N` on `semantics build` or `run`; set
`SPEC2LEAN_RUNTIME_PROBE_COMMAND` only when a trusted JSON-stdin runtime adapter
is available. Unresolved questions stop the pipeline.

See [the Phase 4 design](docs/phase-4-design.md) for the evidence boundary,
semantic schema, claim classifications, operation/state separation,
deterministic validation, OpenCode isolation, and artifact layout.

## Materialize the shared core and translate one group

Phase 5 requires the exact installed OpenCode model
`openai/gpt-5.6-sol` with reasoning variant `medium`. When the selected group
has relevant shared prerequisites, `translate build` first collects their
authoritative Phase-4 dependency/claim links and materializes or reuses one
validated core.
The content-addressed snapshot and representation registry are frozen before
the group Translator starts. The Translator receives that exact read-only core
and every accepted `semantics.json` in the specification-derived Phase-2 group,
then exposes only the structured `submit_translation` tool. One session writes
one complete `<Group>/<Group>.lean` file; no fragments or per-instruction Lean
files are created. Group names, membership, and shared concepts all come from
validated upstream artifacts; Phase 5 has no language-specific concept or
mnemonic table.

```bash
./spec2lean translate build \
  --plan-run PLAN_RUN_ID \
  --group GROUP_FROM_PLAN
```

`--unit UNIT_ID` may be used instead to select the complete group containing
that unit. A core-backed group must import the exact generated `leanModule` and
records both its immutable `{coreRunId, manifestHash, sourceHash, leanModule}`
reference and its declaration-level `sharedUses`. A missing planned concept
raises structured `MISSING_SHARED_ABSTRACTION`; the group may not invent a local
substitute.

Core artifacts live separately from plan/group output:

```text
translations/<language>/<version>/shared/
  current.json
  versions/<shared-core-run-id>/
    core-manifest.json
    core-run.json
    modules/.../Core.lean
```

The version store is immutable and publication is atomic. A pure missing-concept
extension preserves its parent byte-for-byte; changed semantic or generator
inputs start a new lineage while leaving earlier snapshots intact. A
per-specification thread/process lock serializes materialization; after waiting,
a competing caller reloads and reuses the now-fresh snapshot. Every group in
one pipeline run that has relevant `requiredBy` consumers is therefore bound to
the same frozen core version; unrelated groups remain non-core groups.

Inspect the generated source/metadata or resolve a declaration all the way to
Phase-3 source provenance without starting OpenCode:

```bash
./spec2lean translate show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean translate manifest --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean translate trace --declaration QUALIFIED_LEAN_DECLARATION
```

See [the Phase 5 design](docs/phase-5-design.md) for the authority boundary,
Lean conventions, structured tool, manifest schema, forbidden constructs,
deterministic validation, and declaration traceability chain.

## Check one translated group

Phase 6 runs exactly three checks: Lean Build, structured Coverage, and
structured Traceability. It consumes existing artifacts only, never modifies
Lean, and does not invoke OpenCode. For a core-backed group it verifies the
recorded core identity and hashes, copies the dependency source into a temporary
module tree, compiles there without writing `.olean` files into the frozen
snapshot, and recognizes imported claims through the core registry. Selecting
any member unit builds the shared group file once and refreshes the checks for
all members:

```bash
./spec2lean check run \
  --plan-run PLAN_RUN_ID \
  --unit UNIT_ID
```

The command writes `check.json` and `check.md` under the unit-specific `checks/`
directory. Inspect the stored result without rerunning anything:

```bash
./spec2lean check show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean check coverage --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean check traceability --plan-run PLAN_RUN_ID --unit UNIT_ID
```

See [the Phase 6 design](docs/phase-6-design.md) for the three checks, artifact
contract, deterministic routing, and failure ownership.

## Route or repair a failed check

Phase 7 chooses the earliest responsible phase: Traceability returns to the
Semantic Extractor, Coverage returns to the Translator, and a build-only failure
starts one bounded Troubleshooter repair session. A repair may correct the
group's import or use of a registered core declaration, but deterministic
validation preserves the exact `sharedCore` reference and `sharedUses`; Phase 7
cannot edit, extend, or redesign the core. All passing requires no action.

```bash
./spec2lean troubleshoot run \
  --plan-run PLAN_RUN_ID \
  --unit UNIT_ID
```

Inspect the stored decision, changes, hashes, and Phase-6 recheck requirement:

```bash
./spec2lean troubleshoot show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean troubleshoot changes --plan-run PLAN_RUN_ID --unit UNIT_ID
```

See [the Phase 7 design](docs/phase-7-design.md) for routing precedence, repair
authority, the single-session OpenCode boundary, and recheck behavior.

To handle the routed revision/repair chain and rerun Phase 6 after every action:

```bash
./spec2lean troubleshoot resolve \
  --plan-run PLAN_RUN_ID \
  --unit UNIT_ID
```

Every additional action must be authorized by the newly generated Phase-6
result. The command stops on all-pass, repeated no-progress state, or eight
dispatches by default; use `--max-dispatches` to set a different explicit cap.
Manual bounded entry points are also available as `semantics revise`,
`translate revise`, and `check recheck`. The original Phase-4 and Phase-5 build
prompts remain unchanged.
