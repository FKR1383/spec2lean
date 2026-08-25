# Phase 1 design: Parse + Index

## Boundary

Phase 1 has one responsibility: preserve official specification sources in a
deterministic hierarchical database with exact provenance and deterministic
search. Planner, evidence retrieval, semantic interpretation, LLM translation,
Lean generation/checking, and troubleshooting are explicit non-goals.

## Repository layout

```text
spec2lean                 repository-local CLI wrapper
src/spec2lean/
  cli.py                  build, inspection, validation, and export commands
  database.py             normalized SQLite schema and deterministic writer
  model.py                parser-neutral document/node/source-span model
  references.py           explicit, syntactic cross-reference extraction
  validation.py           structural/source/completeness validation
  parsers/
    html.py               semantic DOM parser
    pdf.py                layout-aware PyMuPDF parser
documents/sources/        preserved official inputs and acquisition manifests
indexes/                  reproducible local SQLite outputs (Git-ignored)
tests/                    synthetic HTML/PDF and database tests
```

## Stable identity and determinism

Specification, document, node, span, term, definition, reference, and
correlation IDs are truncated SHA-256 identifiers over stable source identity
and structural position. HTML node identity uses a DOM path. PDF node identity
uses page/block or page/table coordinates. Sibling ordinals follow source
order. Rebuilding the same bytes produces the same IDs and semantic digest.

Creation and validation timestamps are stored as operational metadata and are
excluded from the semantic digest. Source SHA, parser version, and schema
version are stored in the database and sidecar manifest; validation reports a
stale source or implementation version.

## Schema

- `specifications`: logical language/version identity.
- `builds`: parser/schema versions, timestamp, status, semantic digest.
- `documents`: one PDF or HTML representation, official URL, local path,
  SHA-256, byte/page/text counts, and parser statistics.
- `pages`: PDF page dimensions and exact page text extraction.
- `nodes`: stable parent-child hierarchy, type, sibling ordinal, depth, raw and
  normalized text, heading data, page range, anchor, and deterministic metadata.
- `source_spans`: per-node PDF page/block/line/span bounding boxes or HTML
  DOM/source-line locations with exact extracted text.
- `nodes_fts`: FTS5 search over titles and raw/normalized text.
- `cross_references`: explicit reference text, optional href, resolution
  target, status, and candidate count.
- `terms`, `definitions`, `term_occurrences`: structurally identified terms;
  no inferred semantics.
- `node_correlations`: conservative PDF↔HTML heading matches based on an exact
  section-number and normalized-title pair.
- `validation_runs`: immutable JSON reports for recorded validations.

## Hierarchy reconstruction

HTML headings and nested `section` elements are authoritative for HTML.
Headingless sections are retained as generic structural containers. PDF uses a
multi-signal heading classifier: numbering depth, font size, boldness,
monospace exclusion, and title length. A heading stack assigns content to the
nearest preceding heading and makes chapter/section/subsection ancestry
reconstructable. Unknown and non-text blocks remain generic nodes.

Fixed token windows are never used as the primary representation.

## PDF strategy

PyMuPDF extracts sorted pages, blocks, lines, spans, fonts, style flags,
coordinates, and image metadata. Ruled tables are detected geometrically and
stored as row arrays plus exact extracted table text and bounding box. Prefix,
layout, and font signals classify paragraphs, definitions, notes, examples,
captions, lists, code, and syntax. Each original span remains independently
traceable to its page and rectangle.

The classifier is deterministic and conservative. A weak heading signal stays
content instead of being promoted. Images are retained as generic nodes with
type/dimension/extension metadata; Phase 1 does not perform OCR.

## HTML strategy

`lxml` starts from `articleBody`, `role=main`, or `main` rather than flattening
the whole page chrome. It recursively preserves headings, sections, paragraphs,
lists, tables and rows, pre/code, definition lists, admonitions, examples,
figures, captions, links, IDs, anchors, DOM paths, and source lines. Layout
containers are transparent. Unknown meaningful leaf content becomes generic.

## References and definitions

Only explicit structural signals are indexed. Anchor links and textual
Chapter/Section/Table/Figure/Appendix references are recorded. Resolution is
performed within the same source representation and is `RESOLVED` only for one
candidate; zero and multiple candidates remain `UNRESOLVED` and `AMBIGUOUS`.
HTML `dl`/`dfn` and PDF text explicitly labelled “Definition” or “Term” produce
definition records.

## Validation

Validation runs SQLite integrity and foreign-key checks; root/parent/depth,
cycle, uniqueness, and contiguous-sibling-order checks; source SHA checks; PDF
page sequence, bbox bounds, and text correspondence checks; HTML anchor, DOM
path, raw text, and section-count checks; and text-volume coverage thresholds.
Statistics expose discovered/indexed pages and sections, all node types,
generic blocks, definitions, spans, references, correlations, and per-source
text coverage. Successful execution is not presented as proof of perfect
classification.

