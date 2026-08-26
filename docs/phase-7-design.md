# Phase 7: Troubleshooter

Phase 7 consumes one stored Phase-6 result and chooses exactly one action. It is
not a workflow engine and it never retries itself. The deterministic precedence
is:

```text
Traceability FAIL -> RETURN_TO_SEMANTIC_EXTRACTOR
else Coverage FAIL -> RETURN_TO_TRANSLATOR
else Build FAIL -> REPAIR_BUILD
else -> NO_ACTION
```

All Phase-6 findings remain in `troubleshoot.json`, including findings owned by
later phases. Returning upstream does not invoke OpenCode or mutate an artifact.
The traceability handoff contains the exact `brokenMappings` array; the coverage
handoff contains the exact `uncovered` array.

## Build repair

A build-only failure starts one restricted OpenCode session using the exact
installed model `openai/gpt-5.3-codex-spark` with `low` reasoning. No model is
substituted if it is unavailable. The session receives the existing Lean source,
compiler diagnostics, Phase-4 semantic artifact, Phase-5 manifest, and Phase-6
traceability result. All ordinary file, shell, browsing, task, and editing tools
are denied. Its only capability is a local `submit_repair` tool.

The submitted candidate is deterministically checked using the Phase-5
translation validator. Every named declaration must remain mapped to existing
Phase-4 claim IDs, forbidden Lean constructs remain forbidden, and the multiset
of declaration roles and resolved semantic-claim responsibilities must be
unchanged. This permits a mechanical declaration rename while preventing a
compiler fix from silently changing semantic responsibility. A non-changing
submission is rejected.

After validation, Phase 7 atomically updates only `Unit.lean` and, when its
declaration mappings actually changed, `translation-manifest.json`. It does not
modify Phase 1, 2, 3, or 4. Phase 7 does not run the compiler in a loop and does
not start a second session.

## Repair artifact and recheck

Each routing decision or repair writes:

```text
troubleshooting/<language>/<version>/<plan-run-id>/<unit-slug>/
  troubleshoot.json
```

The contract is `schemas/troubleshoot-result.schema.json`. Deterministic code
adds the Phase-6 artifact hash, before/after file hashes, timestamps, exact model
configuration, OpenCode version, Spec2Lean commit, changed-file list, and retry
count. The model supplies only the repaired source, declaration mappings, and
human-readable change descriptions.

A successful build repair is marked for a fresh Phase-6 run of all three checks:
Build, Coverage, and Traceability. The recheck is explicit and not automatic, so
a further repair can only follow a newly produced Phase-6 failure.

## CLI

Route a stored Phase-6 result or perform one build-only repair:

```bash
./spec2lean troubleshoot run --plan-run PLAN_RUN_ID --unit UNIT_ID
```

Inspect without starting a session:

```bash
./spec2lean troubleshoot show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean troubleshoot changes --plan-run PLAN_RUN_ID --unit UNIT_ID
```

After `REPAIR_BUILD`, rerun Phase 6 explicitly:

```bash
./spec2lean check run --plan-run PLAN_RUN_ID --unit UNIT_ID
```

Normal tests inject a mocked repair submission and never invoke OpenCode.
