# PTX 9.3 shared semantic environment

`shared-environment-draft-v1.json` is the production-shaped environment
shell for PTX 9.3. It is deliberately `DRAFT` and empty: accepted instruction
reviews do not automatically establish that a claim is reusable PTX-wide.

Populating the environment requires a separate semantic migration/review
process that preserves each claim's classification, official evidence,
dependencies, originating accepted artifacts, and explicit shared-semantics
review record. Only after that human decision may the environment and every
entry be marked `HUMAN_APPROVED` and used by production materialization.

The retrieval profile in the parent directory remains source-context policy,
not semantic authority.
