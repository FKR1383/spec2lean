# Spec2Lean

Spec2Lean implements **Phase 1: Parse + Index**, **Phase 2: Request-scoped
Planner**, **Phase 3: Retrieve Evidence**, **Phase 4: Semantic Extractor**, and
**Phase 5: LLM Translator**. Phase 1 turns an official PDF and/or HTML language specification
into a deterministic, searchable, hierarchical SQLite database. Phase 2
resolves an explicitly bounded request, invokes one restricted OpenCode Planner
session, validates its dependency graph, and writes an inspectable plan. Phase 3
runs one bounded Evidence Retriever session per planned unit and deterministically
resolves its selections to exact Phase-1 text and provenance. Phase 4 runs one
evidence-bounded Semantic Extractor session per unit and validates a structured,
traceable semantic artifact. Phase 5 uses one semantic-artifact-bounded session
to generate Lean 4 and declaration traceability. Authoritative Lean checking and
troubleshooting are not implemented.

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

See [the Phase 1 design](docs/phase-1-design.md) for schema and parser details.

## Build a request-scoped plan

Phase 2 requires the exact installed OpenCode model
`openai/gpt-5.4-mini` and uses reasoning variant `low`. Choose exactly one
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
./spec2lean plan deps --run PLAN_RUN_ID
./spec2lean plan layers --run PLAN_RUN_ID
./spec2lean plan prerequisites --run PLAN_RUN_ID
./spec2lean plan graph --run PLAN_RUN_ID --format dot --output /tmp/plan.dot
```

See [the Phase 2 design](docs/phase-2-design.md) for scope rules, Planner
isolation, submission validation, cycles, and artifact ownership.

## Retrieve exact evidence for a planned unit

Phase 3 requires the exact installed OpenCode model
`openai/gpt-5.3-codex-spark` with reasoning variant `low`. The model selects
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
`openai/gpt-5.3-codex-spark` with reasoning variant `low`. It supplies only the
selected unit's Phase-3 evidence bundle and exposes only the structured
`submit_semantics` tool. It cannot retrieve additional material.

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
./spec2lean semantics stats --plan-run PLAN_RUN_ID
```

See [the Phase 4 design](docs/phase-4-design.md) for the evidence boundary,
semantic schema, claim classifications, operation/state separation,
deterministic validation, OpenCode isolation, and artifact layout.

## Translate one accepted semantic artifact to Lean 4

Phase 5 requires the exact installed OpenCode model
`openai/gpt-5.3-codex-spark` with reasoning variant `low`. It accepts exactly one
unit per command, supplies only that unit's accepted `semantics.json` and any
current-architecture shared Lean sources, and exposes only the structured
`submit_translation` tool.

```bash
./spec2lean translate build \
  --plan-run PLAN_RUN_ID \
  --unit UNIT_ID
```

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
