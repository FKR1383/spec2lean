# Pipeline Runner design

## Boundary

The runner orchestrates Phases 1–7 through their public Python APIs. It does
not implement planning, retrieval, semantic extraction, translation, checking,
or repair logic itself. The unit schedule comes solely from the accepted
Phase-2 processing layers.

## Run identity and durable state

Every non-dry invocation owns
`runs/<language>/<version>/<pipeline-run-id>/run.json`. Writes are atomic and
occur after Phase 1, Phase 2, and every unit transition. A manifest records the
typed request, Phase-1 digest and disposition, referenced plan, per-unit stage
dispositions, Phase-7 outcome, timestamps, and terminal error when present.

Human-readable progress is emitted to stderr before and after potentially long
phase calls, preserving stdout for the final JSON manifest. Keyboard interrupts
are persisted as `INTERRUPTED` and include the resumable run ID.

Generated plans and unit artifacts remain owned by their original phase stores.
The run manifest references them; it does not copy or reinterpret them.

## Freshness and reuse

- Phase 1 must pass the existing deterministic validator, including source
  hashes, parser/schema versions, SQLite integrity, and page-text validation.
- Phase 2 must have the identical typed request and current Phase-1 semantic
  digest.
- Phase 3 must bind to the accepted plan, planned unit, specification identity,
  and Phase-1 digest.
- Phase 4 must validate against the current Phase-3 bundle hash.
- Phase 5 must validate the group manifest against every current member
  Phase-4 semantic-artifact hash.
- Phase 6 must contain the current semantic, Lean-source, and translation
  manifest hashes.

Incomplete or stale generated Phase-3/4 unit directories and Phase-5 group directories are moved to the
current run's `superseded/` tree before retry, making interruption recovery
inspectable and non-destructive.

## Routing and loop safety

A passing Phase-6 result advances to the next scheduled unit. Phase 5 starts
only after every requested unit has completed Phase 4, and Phase 6 builds each
group file once. A failure is
given to the existing Phase-7 resolver, which deterministically selects the
earliest owner: traceability to the Semantic Extractor, coverage to the
Translator, and build to the Troubleshooter. Phase 7 reruns all checks after
every action. Its actionable-state hash prevents no-progress loops and the
configured dispatch limit bounds the complete chain.

## Controls

`--resume [RUN_ID]` reopens a compatible manifest; without an ID it selects the
latest compatible request. `--dry-run` performs read-only inspection and does
not create a run or invoke OpenCode. `--from` permits artifact creation only at
or after a phase; `--until` stops after a phase. Cyclic or incomplete Phase-2
schedules are rejected before unit processing.
