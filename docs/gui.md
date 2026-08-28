# V1 artifact explorer

The Spec2Lean GUI is a read-only local web application over the existing V1
artifacts. It deliberately adds no workflow or semantic representation.

```bash
./spec2lean gui
```

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

The server binds to `127.0.0.1` and exposes neither filesystem browsing nor
shell execution. Source paths are never accepted from requests; PDF previews
are limited to evidence-linked files inside the repository.
