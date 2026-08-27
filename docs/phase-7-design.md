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
installed model `openai/gpt-5.6-sol` with `medium` reasoning. No model is
substituted if it is unavailable. The session receives the complete group Lean source,
compiler diagnostics, all group Phase-4 semantic artifacts, Phase-5 manifest, and Phase-6
traceability result. All ordinary file, shell, browsing, task, and editing tools
are denied. Its only capability is a local `submit_repair` tool.

The submitted candidate is deterministically checked using the Phase-5
translation validator. Every named declaration must remain mapped to existing
Phase-4 `(unitId, claimId)` pairs, forbidden Lean constructs remain forbidden, and the multiset
of declaration roles and resolved unit/claim responsibilities must be
unchanged. This permits a mechanical declaration rename while preventing a
compiler fix from silently changing semantic responsibility. A non-changing
submission is rejected.

After validation, Phase 7 atomically updates only the complete group Lean file and, when its
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
Build, Coverage, and Traceability. `troubleshoot run` remains route/repair-only;
`troubleshoot resolve` follows a bounded deterministic cascade. After each
dispatch it reruns Phase 6, and only that fresh result may authorize the next
dispatch. It stops on all-pass, repeated actionable state (no progress), or the
explicit dispatch cap (eight by default).

Build diagnostics preserve Lean's multiline actual-type/expected-type context.
Each build-repair session also receives the exact Lean version and a compact
history of earlier failed build repairs from the same bounded resolution. The
general Troubleshooter prompt treats those compiler facts as authoritative and
must not repeat or revert to a candidate state that already failed.

## Bounded upstream revisions

Phase-4 and Phase-5 creation prompts and create-only `build` commands remain
unchanged. Separate revision prompts consume the current artifact plus exact
Phase-6 diagnostics:

```text
TRACEABILITY FAIL
  -> one Semantic Extractor revision
  -> one Translator reconciliation revision
  -> one Phase-6 recheck

COVERAGE FAIL
  -> one Translator coverage revision
  -> one Phase-6 recheck

BUILD FAIL
  -> one Troubleshooter syntax/elaboration repair
  -> one Phase-6 recheck
```

Translator revisions always receive and resubmit the complete group. Each revision stores before-state artifacts, hashes, its source Phase-6 check
hash, model/session metadata, and zero automatic retries. A Phase-6 check can be
consumed only once by a given revision phase. Phase 6 now records semantic,
Lean-source, and manifest input hashes so a genuine recheck is distinguishable
from reuse of stale diagnostics.

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

Resolve the fresh-check chain within one bounded invocation:

```bash
./spec2lean troubleshoot resolve --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean troubleshoot resolution --plan-run PLAN_RUN_ID --unit UNIT_ID
```

The individual bounded commands remain available for inspection/manual control:

```bash
./spec2lean semantics revise --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean translate revise --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean check recheck --plan-run PLAN_RUN_ID --unit UNIT_ID
```

Normal tests inject a mocked repair submission and never invoke OpenCode.
