# ECMAScript 2025 pilot

This language pack defines source-acquisition policy for the first non-PTX
Spec2Lean portability benchmark. The bounded unit is the ECMA-262 abstract
operation `ToBoolean`; no unit semantics or Lean implementation is stored in
the pack.

`acquisition-profile.json` constrains OpenCode discovery to the official Ecma
International edition-16 source scope. OpenCode proposes the exact official
HTML/PDF URL. The orchestrator performs the download, hashing, immutable source
registration, and deterministic retrieval indexing.

The profile is source policy only. It is not semantic evidence, an
interpretation of `ToBoolean`, or human approval.
