# Semantic retrieval beside the hierarchical lexical index

Lexical search remains the default. It still uses the existing FTS ranking and
hierarchical navigation tools. Semantic search uses the supervisor's MiniLM
embedding approach and cosine ranking, returning the same current-main node IDs.
Evidence IDs, exact spans, claim links, manifests and GUI source mappings are
built by the existing validators, regardless of retrieval mode.

Install the optional dependency, then build vectors in an existing database:

```sh
python -m pip install -e '.[semantic]'
./spec2lean index embed --language ptx --version 9.3
./spec2lean index search --language ptx --version 9.3 \
  --index-mode semantic --query 'bitwise conjunction of two source operands'
./spec2lean run --language ptx --version 9.3 --instructions and.b32 \
  --index-mode semantic
```

For a new index, `index build --index-mode semantic ...` builds both the normal
hierarchical/lexical index and the optional vectors. `run --index-mode semantic`
ensures vectors exist in Phase 1 before planning. `index embed --model NAME
--revision COMMIT` selects an embedding model explicitly. The stored model and
revision are used for query embeddings; the formalization model is unchanged.
The default embedding model is `sentence-transformers/all-MiniLM-L6-v2`.

`--index-mode` also works on `plan build`, `evidence build`, `semantics build`,
and `troubleshoot resolve`. `SPEC2LEAN_INDEX_MODE` supplies the same selection
for Python/MCP invocation. A standalone semantic search requires a built index;
it never falls back to lexical when vectors are missing, corrupt or stale.
`index search` retains its source-type and node-type filters and existing JSON
fields; semantic results additionally include `similarity`.

Each nonempty node is embedded with its title prepended and text capped at 4,000
characters, matching the supervisor implementation. This is retrieval ranking,
not evidence: the retriever must still read exact current-main nodes/spans before
submitting evidence. SQLite holds normalized little-endian float32 vectors and
one build record containing model, revision, dimension, node count, source and
embedding-input digests. A rebuild replaces the vectors transactionally. It does
not change Phase 1's semantic digest or the canonical source tables. The existing
index-manifest format is unchanged; vector metadata lives in the same database.

The Python MCP worker caches the model across its search calls. No model loads
are needed for lexical retrieval. CPU embeddings are used; dependencies and model
weights are optional and are downloaded only when semantic mode is requested.
For large specifications, `OMP_NUM_THREADS=4 MKL_NUM_THREADS=4` can bound CPU work.
Brute-force cosine ranking is intended for specification-sized indexes, not a
large cross-document vector service. Long nodes are truncated for ranking only.

Run manifests record `indexMode`; phase session metadata records the selected
retrieval mode. Resume requires the same mode. Existing runs without that field
remain lexical. Starting a new mode does not reuse a plan created in the other
mode. Existing per-phase inspection, artifact reuse and run status commands work
as before. No hybrid default or alternate Rust spec database was imported.

Provenance: supervisor semantic commit `26b43f29b20f0963b49918468898f589b4fb2b30`,
original PR head `8836d0422ea6201237ceec5da5aa44cba7dcc3e6`, preserved by history
merge `1a56347979e6ba90290a43a1efd5431ccb1955c8`.
