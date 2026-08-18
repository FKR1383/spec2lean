# Lean-to-source traceability

The evidence manifest is the deterministic boundary between generated Lean and
human review tooling. It maps each Lean declaration to semantic claim IDs and
then to hash-bound official source fragments. A UI consumes this manifest; it
must not infer source faithfulness from Lean comments on its own.

Schema-v3 manifests also include a run-level `semanticUncertainties` list.
This prevents an unresolved OPEN_QUESTION from disappearing merely because a
particular Lean declaration does not cite it. A benchmark continuation is
labeled `CONSERVATIVE_BOUNDED_SCOPE` and `humanApproved=false`; the
question remains unresolved, disputed cases remain partial or excluded, and
the record never authorizes promotion. The VS Code view renders these
uncertainties independently of declaration-level evidence.

Generate and verify a manifest for an existing run:

```bash
./spec2lean traceability build --run <run-id> --pdf-boxes
./spec2lean traceability build --run <run-id> --document proofs --pdf-boxes
./spec2lean traceability validate \
  --manifest runs/<run-id>/traceability/evidence-<manifest-sha256>.json
./spec2lean traceability audit
```

The v3 generator reads structured claim, architecture-design, evidence,
human-approval dependency, and theorem-obligation IDs. It follows claim
dependencies transitively, so a theorem linked to a derived claim also exposes
the SOURCE_FACT leaves and project boundaries on which it depends. Diagnostics
separately report missing declaration references, unresolved dependencies,
missing official evidence, and assumptions without approval authority. Legacy
v1/v2 manifests remain readable; incomplete manifests are useful for repair
but are not promotion-safe. The orchestrator emits a semantics manifest after
verified Lean formalization and a proof manifest after verified proof
generation. Opening a CodeLens never launches an agent or repeats source
research. Content-addressed paths preserve every reviewed Lean revision and
every PDF rendition instead of overwriting an earlier mapping.

Human feedback records are immutable, hash-bound review artifacts. They never
approve a gate or promote an artifact:

```bash
./spec2lean traceability feedback \
  --manifest runs/<run-id>/traceability/evidence-<manifest-sha256>.json \
  --entry <entry-id> \
  --decision REQUEST_CHANGE \
  --reviewer <name> \
  --comment <text>
```

With `--pdf-boxes`, only official HTML fragments—not internal architecture
artifacts—are eligible for PDF alignment. Exact quotations are matched against
cached Poppler geometry. The deterministic matcher may use a source-provided
same-section page hint (bounded to ±2 pages) or a unique distinctive token
window; every rendition records its method and normalized `[x, y, width,
height]` box. Eligible/matched/ambiguous/unmatched/ratio metrics remain explicit.
HTML evidence stays authoritative when PDF layout prevents a safe match; no
ambiguous page or box is selected.
