# Lean-to-source traceability

The evidence manifest is the deterministic boundary between generated Lean and
human review tooling. It maps each Lean declaration to semantic claim IDs and
then to hash-bound official source fragments. A UI consumes this manifest; it
must not infer source faithfulness from Lean comments on its own.

Generate and verify a manifest for an existing run:

```bash
./spec2lean traceability build --run <run-id> --pdf-boxes
./spec2lean traceability validate \
  --manifest runs/<run-id>/traceability/evidence-<manifest-sha256>.json
```

The v1 generator reads the structured claim and evidence IDs already emitted
by the pipeline and the traceability comments immediately preceding Lean
declarations. Missing or unknown references remain explicit diagnostics. The
orchestrator invokes it automatically after a verified Lean-formalization
success. Content-addressed manifest paths preserve every reviewed Lean
revision and every optional PDF rendition instead of overwriting an earlier
mapping.

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
