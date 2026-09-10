# Specification workspace and artifact explorer

The Spec2Lean GUI imports specifications, starts pipeline work, and explores
the existing pipeline artifacts in a local web application.

```bash
./spec2lean gui
```

Choose **New specification**, upload a PDF, and enter its specification identifier
and version. Enter exact desired unit names (commas or new lines), a family, an
existing indexed section, or explicitly select the full specification. Title,
publisher, and source URL are optional; the PDF title is used when available.

**Upload and prepare** saves a managed copy of the PDF, SHA-256 checksum, source
manifest, and planning request. It builds the Phase 1 index by default. Uncheck
the indexing option to prepare the source only. Uploads must contain extractable
text, have no password protection, and be at most 256 MiB. Scanned PDFs need OCR
before import. Source URLs are recorded as provenance; the GUI does not fetch them.

The specification page shows persistent status, a progress log, and buttons to
build Phase 1 or continue the full pipeline. The latter uses your installed Rust
harness or OpenCode runtime and configured model credentials. Lexical Phase 1
indexing needs no model credentials; semantic search builds embeddings. You can
refresh the page or browse artifacts while a job runs. One job runs at a time in
each GUI server. Keep the server running; stopping it stops its active job, and
you can retry using the saved artifacts. Failures retain their logs and sources.

**Specifications** also lists imports made with `spec2lean init`. Each specification
shows a CLI command to continue it with `spec2lean start`. Both interfaces share
the same intake and pipeline code. Reimporting identical bytes under the same
identifier/version reuses the source and creates a new scope request. Different
bytes require a new identifier or version; imports never overwrite existing sources.

Use `./spec2lean gui --workspace /path/to/workspace` to select a different artifact
workspace. Use the same `--workspace` with CLI `init` and `start` commands.

The run list also discovers isolated experiment jobs under
`runs/experiments/<experiment>/jobs/<job>/runs/`. Experiment cards show the
runtime and search mode recorded in each job's `state.json`. All artifact and
source reads stay within that job's own roots, including its `index/`
directory; no files are copied into the ordinary run directories. Completed
and failed runs are both visible. Refresh the page to discover new runs.

The backend is a small Python standard-library HTTP server. It normalizes
on-demand reads from the run manifest, Phase-2 plan, Phase-3 evidence, Phase-4
semantics, Phase-5 translation manifest and Lean source, Phase-6 checks,
Phase-7 repair history, and Phase-1 SQLite database. The frontend is bundled
HTML, CSS, and JavaScript, so there is no separate package installation or
frontend build.

The main interaction is:

```text
Lean declaration → semantic claims → exact evidence → official source location
```

Click a mapped declaration or its claim-count marker to select its manifest
claims. Select a claim to see every supporting evidence item. Select evidence
to resolve its Phase-1 node and source spans. HTML records show the anchor, DOM
path, and source lines; PDF records render the source page on demand with the
stored bounding box highlighted. Evidence and claim cards also show reverse
links back to declarations.

For newly generated units whose Phase-2 scope contains both official
renditions, factual and derived claims are required to cite both. The same
claim therefore exposes its HTML record and its exact highlighted PDF page in
the evidence list. Historical and genuinely single-rendition artifacts remain
readable without synthesized provenance.

The remaining tabs provide structured semantics, evidence grouped by tier and
role, Build/Coverage/Traceability results, repair history, pipeline timing when
recorded, and an optional raw-artifact panel. Missing or malformed optional
artifacts are shown as explicit empty states or broken references.

The server binds to `127.0.0.1`. Uploads accept file bytes and metadata, and job
requests accept fixed pipeline options. Requests cannot select arbitrary server
paths or shell commands. Writes require the GUI session token and matching
origin. PDF previews remain limited to evidence-linked files in the workspace.
