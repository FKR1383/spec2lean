# Canonical bounded source bundle

`source-bundle-v2.schema.json` is the language-neutral contract between source
retrieval and semantic interpretation. It supports official HTML and PDF
documents, exact quotations, stable fragment IDs, hash-pinned source identity,
precise locators, and explicit evidence gaps.

Each gap is classified as `LOAD_BEARING` or `NON_LOAD_BEARING`. A load-bearing
gap prevents the semantic stage from inventing the missing behavior; it is a
research boundary, not a reason to retry the same search indefinitely.

The retrieval index locates text but is not semantic authority. The quoted,
hash-bound official document remains the evidence source.
