# Architecture Critique (PTX `shl.b32`) v6

Scope reviewed: `candidates/ptx/9.3/units/shl-b32/architecture/foundation-v5.md` against PTX 9.3 official source evidence.

## Overall verdict
No new blocking findings were identified in this revision. The architecture artifact is now materially source-grounded, and residual ambiguities (`_` destination, `srcA` source-form class, and metadata-frozen-on-skip) are explicitly tracked as assumptions/open questions rather than asserted as normative facts. It is suitable to proceed to human Gate A review.

## Finding ARC6-1
- **Severity:** NOTE
- **Affected artifact:** `architecture/foundation-v5.md`
- **Location:** `Section 8 (Predication architecture)`, `P-3`; `Section 11 (Open questions)`
- **Evidence references:**
  - `predicated-execution` (`SF-PRED-1`): guard semantics (`lines 7547-7550`)
  - `instructions` (`E-PRED-4`): all instructions may be predicated (`lines 8722-8723`)
  - `control-flow-instructions-at` (`E-PRED-3`): false-predicate behavior (`lines 21838-21839`)
- **Description:**
  Architecture correctly marks false-predicate no-op behavior as an assumption-based interpretation rather than a fully sourced normative consequence. This is non-blocking, but Gate A reviewers should verify this interpretation remains acceptable at theorem-design level.
- **Consequence:**
  Prevents over-claiming predication behavior while preserving traceability requirements; no immediate change is required.
- **Required owner for revision:** Spec Architect and Proof Engineer (for downstream consistency checks)
- **Human review required:** no

## Gate A readiness
**Proceed to human Gate A review.**

- The previously identified blocker concerns (underscore destination and shift-domain overcommitment) are no longer claimed as normative; they are deferred as open questions/assumptions.
- No additional critical or major regressions were found in this architecture pass.