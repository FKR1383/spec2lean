# PTX 9.3 shared semantic environment

`shared-environment-draft-v1.json` is the production-shaped environment
shell for PTX 9.3. It is deliberately `DRAFT` and empty: accepted instruction
reviews do not automatically establish that a claim is reusable PTX-wide.

Populating the environment requires a separate semantic migration/review
process that preserves each claim's classification, official evidence,
dependencies, originating accepted artifacts, and explicit shared-semantics
review record. Only after that human decision may the environment and every
entry be marked `HUMAN_APPROVED` and used by production materialization.

The first concrete proposal is
`shared-environment-review-candidate-v1.json`; its compact review packet is
`reviews/shared-semantics/ptx-9.3/shared-environment-first-human-review-v1.md`.
Both remain `READY_FOR_HUMAN_REVIEW`. The candidate's explicit scope is the
bounded scalar `.b32` register/predicate core, not all PTX.

The retrieval profile in the parent directory remains source-context policy,
not semantic authority.

`semantic-profile.json` defines only fast-path eligibility. Its required
semantic IDs are approval requirements, not assertions that those claims are
true. Until the environment and every required entry are human-approved, the
orchestrator records an explicit `LEGACY_FALLBACK` and uses the existing full
semantic path. The unit patterns limit the eventual v2 path to simple B32
bitwise units; other PTX features fall back even after environment approval.

The required IDs and classifications are machine-pinned in the profile and
deliberately keep source and project layers separate. They
are proposed review slots, not approved claims:

| Required semantic ID | Required classification boundary |
| --- | --- |
| `ptx.9.3.b32.domain-source` | `SOURCE_FACT` |
| `ptx.9.3.register.state-space-source` | `SOURCE_FACT` |
| `ptx.9.3.register.value-representation-design` | `DESIGN_DEPENDENCY` |
| `ptx.9.3.predication.applicability-source` | `SOURCE_FACT` |
| `ptx.9.3.predication.false-guard-source` | `SOURCE_FACT` |
| `ptx.9.3.predication.false-guard-noop-derived` | `DERIVED_INTERPRETATION` |
| `ptx.9.3.state.register-model-design` | `DESIGN_DEPENDENCY` |
| `ptx.9.3.register.lookup-partial-design` | `DESIGN_DEPENDENCY` |
| `ptx.9.3.bit-bucket.rule-source` | `SOURCE_FACT` |

Their exact statements, evidence, dependency graph, and approval record are a
human semantic-review decision. The engine does not synthesize them from
accepted unit artifacts.

After reviewing the packet, a human may record the separate shared decision
without invoking OpenCode:

```bash
./spec2lean approve-shared --language ptx --version 9.3 \
  --reviewer "<human reviewer>" \
  --rationale "<explicit shared-scope approval rationale>"
```

This command hash-verifies the candidate, official sources, accepted support,
and packet; writes immutable approval/environment artifacts; and switches the
profile to the approved environment. It must be executed only by the human
reviewer.
