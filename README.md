# Spec2Lean

Spec2Lean currently implements **Phase 1 only: Parse + Index**. It turns an
official PDF and/or HTML language specification into a deterministic,
searchable, hierarchical SQLite database. It does not plan formalizations,
interpret semantics, invoke an LLM, generate Lean, or check proofs.

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

The canonical local database is `indexes/ptx/9.3/specification.sqlite`.
Generated indexes are intentionally Git-ignored because they are reproducible
from the hash-pinned official inputs.

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
