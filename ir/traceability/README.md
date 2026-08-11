# Lean-to-source traceability

The evidence manifest is the deterministic boundary between generated Lean and
human review tooling. It maps each Lean declaration to semantic claim IDs and
then to hash-bound official source fragments. A UI consumes this manifest; it
must not infer source faithfulness from Lean comments on its own.

Generate and verify a manifest for an existing run:

```bash
./spec2lean traceability build --run <run-id> --pdf-boxes
./spec2lean traceability build --run <run-id> --document proofs --pdf-boxes
./spec2lean traceability validate \
  --manifest runs/<run-id>/traceability/evidence-<manifest-sha256>.json
./spec2lean traceability audit
```

The v2 generator reads the structured claim, architecture-design, evidence,
and theorem-obligation IDs already emitted by the pipeline. Missing or unknown
references remain explicit diagnostics and make validation fail; incomplete
manifests are useful for repair/UI inspection but are not promotion-safe. The orchestrator emits a semantics manifest after
verified Lean formalization and a proof manifest after verified proof
generation. Opening a CodeLens never launches an agent or repeats source
research. Content-addressed paths preserve every reviewed Lean revision and
every optional PDF rendition instead of overwriting an earlier mapping.

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

With `--pdf-boxes`, exact quotations are token-matched against Poppler's local
PDF geometry output. A unique match adds an official-PDF rendition with a
normalized `[x, y, width, height]` bounding box. Ambiguous and unmatched quotes
remain diagnostics; the generator never guesses a page or box.
