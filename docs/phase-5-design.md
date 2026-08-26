# Phase 5: LLM Translator

The original translation prompt and create-only build path are unchanged by the
repair loop. Coverage failures and revised Phase-4 artifacts use a separate
bounded `translate revise` path over the current translation, exact diagnostics,
and current Phase-4 semantic authority.

Phase 5 consumes one accepted Phase-4 `semantics.json` for one planned unit and
produces a Lean 4 semantic implementation plus declaration-level traceability.
It does not reopen Phase 1, read Phase-3 evidence text, browse, prove theorem
families, perform authoritative Lean checking, retry with another session, or
troubleshoot a failed candidate.

## Session and authority boundary

`translate build` requires exactly one `--unit`. Deterministic preflight loads
that unit's successful semantic artifact, checks its plan/specification/unit
identity, requires unique `claim:` IDs, computes the canonical artifact hash,
and fails before starting OpenCode if any input is absent or inconsistent.

One isolated OpenCode Translator session receives only:

- deterministic unit/run context;
- the complete accepted Phase-4 semantic artifact (including its Phase-3
  evidence IDs, but no evidence text);
- Lean sources under `translations/<language>/<version>/shared/`, if that
  new-architecture shared directory exists.

The exact model and reasoning variant are pinned in both the agent configuration
and command line:

```text
model: openai/gpt-5.3-codex-spark
reasoning/variant: low
```

A model-catalog preflight rejects an unavailable exact model without selecting
a substitute or creating a translation run. Shell, filesystem, editing,
search, web, task/subagent, skills, and LSP tools are denied. The only allowed
tool is `submit_translation`. Rejected structural submissions may be corrected
through that tool in the same session; no second session or automatic retry is
started.

## Lean translation conventions

The prompt makes the Phase-4 artifact primary authority and centers an
instruction translation on its actual operation. Where applicable it asks for
a pure result function separated from execution/state update, with explicit
branches, edge cases, destination effects, predication, and restrictions. It
permits existing new-architecture shared Lean infrastructure, but directs the
first translation to remain local and minimal if none exists.

The output must be Lean 4 with named ASCII declarations. `sorry`, `admit`, new
`axiom` declarations, and `unsafe` code are forbidden. Phase 5 does not request
large theorem families or claim that the result is source-faithful; those are
outside the Translator's authority and Phase 6 owns authoritative checking.

## Structured submission and artifacts

`submit_translation` accepts exactly:

```json
{
  "leanSource": "namespace ...",
  "declarations": [
    {
      "declaration": "Spec2Lean.Ptx.AddU32.result",
      "role": "OPERATION",
      "semanticClaimIds": ["claim:..."]
    }
  ]
}
```

Declaration roles distinguish primary types, operation, execution, semantic
branch/edge helpers, other semantic helpers, and implementation helpers. Every
named top-level semantic declaration must map to at least one claim already in
the input artifact. A pure implementation helper may instead use
`supportsDeclarations`; deterministic validation requires that indirect chain
to terminate at semantic claims. Deterministic code—not the model—adds phase, language/version,
unit and plan IDs, translation and semantics run IDs, semantic artifact hash,
model/reasoning, Lean target/version, file name, schema version, and timestamp.

Successful output is unit-specific:

```text
translations/<language>/<version>/<plan-run-id>/<unit-slug>-<unit-id-prefix>/
  Unit.lean
  translation-manifest.json
  translator-run.json
```

The public manifest schema is
`schemas/translation-manifest.schema.json`. `translator-run.json` records the
exact command (with prompt redacted), model and reasoning, one-session/zero-
retry policy, input boundary, semantic artifact path/hash, shared Lean inputs,
timestamps, exit status, session ID, and captured process output.

## Deterministic validation and traceability

Submission and published-artifact validation checks:

- the successful Phase-4 input exists and belongs to the exact plan/unit;
- the manifest's canonical semantic artifact hash is current;
- `Unit.lean` exists, is non-empty, and has named declarations;
- forbidden `sorry`, `admit`, axiom/constant declarations, `unsafe`, and
  `partial` constructs are absent outside comments and strings;
- every manifest declaration exists in the Lean source and every discovered
  named declaration has a mapping;
- primary introduced types use `PRIMARY_TYPE`;
- all claim IDs exist in this semantic artifact and contain no duplicates;
- instructions have an `OPERATION` mapping, and stateful/predicated instructions
  also have an `EXECUTION` mapping;
- deterministic manifest fields and translator-run metadata are complete and
  exact.

These are structural checks, not a Lean compiler or semantic-correctness
judgment. Declaration tracing follows:

```text
Lean declaration
  -> translation manifest
  -> Phase-4 claim IDs
  -> Phase-3 evidence IDs
  -> source node/span IDs, document hash, and official URL
```

Use the read-only commands:

```bash
./spec2lean translate show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean translate manifest --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean translate trace --declaration QUALIFIED_LEAN_DECLARATION
```

Normal tests construct synthetic semantics, Lean source, manifests, and a fake
OpenCode process. They never invoke a real OpenCode session or Phase-6 checking.
