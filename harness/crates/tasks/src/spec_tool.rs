//! One tool over the index.
//!
//! The phase pipeline advertised eight: search, show, children, ancestors,
//! subtree, xrefs, definitions, correlated. On a real run the model opened by
//! calling ten of them in a single turn, all circling the same few nodes —
//! which is one question ("what is this, and what is around it?") asked eight
//! ways, at the cost of eight schemas in every request and eight chances to
//! mistype a node id.
//!
//! This is that question. Give it text and it searches; give it a node and it
//! fetches; either way it answers with the neighbourhood rather than making the
//! caller reassemble one. Every bound the eight had is kept, because the point
//! was never that they were too strict.

use std::collections::BTreeMap;

use serde_json::{Value, json};
use spec2lean_specdb::{NodeId, NodeRow, SpecDb, truncate_chars};

use spec2lean_evidence::ExposureLedger;

use crate::embedder::{Embedder, fuse};

/// Text budget for one node, and how many neighbours to name. A neighbourhood
/// is for orienting; reading a whole subtree is what `depth` is for.
const TEXT_LIMIT: usize = 4_000;
const NEIGHBOURS: i64 = 25;

pub fn schema() -> Value {
    json!({
        "type": "object",
        "additionalProperties": false,
        "properties": {
            "query": {
                "type": "string",
                "description": "Full-text search of the specification. Use when you do not yet \
                                have a node id."
            },
            "node": {
                "type": "string",
                "description": "A node id from an earlier result. Use when you do."
            },
            "depth": {
                "type": "integer",
                "minimum": 0,
                "maximum": 3,
                "description": "How far below `node` to read whole. 0, the default, returns the \
                                node itself and names its children without their text."
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 25,
                "description": "Maximum matches for a query. Defaults to 5."
            },
            "mode": {
                "type": "string",
                "enum": ["lexical", "semantic", "hybrid"],
                "description": "How to search. `lexical` matches words, so it needs the \
                                specification's own vocabulary. `semantic` matches meaning, \
                                which finds a passage that says what you mean in other words. \
                                `hybrid`, the default where this index has embeddings, uses \
                                both. Ignored when you give `node`."
            }
        }
    })
}

pub fn description() -> &'static str {
    "Read the specification index. Give `query` to search by text or `node` to fetch a known \
     node; either returns the passage with its exact text, its span ids, its section number and \
     page, its ancestors, its children, its cross-references, and any definitions it states. \
     Cite only span ids this tool has shown you."
}

pub fn call(
    db: &SpecDb,
    ledger: &mut ExposureLedger,
    embedder: Option<&mut Embedder>,
    input: &Value,
) -> Result<Value, String> {
    let query = input.get("query").and_then(Value::as_str);
    let node = input.get("node").and_then(Value::as_str);
    let depth = input.get("depth").and_then(Value::as_i64).unwrap_or(0).clamp(0, 3);
    let limit = input.get("limit").and_then(Value::as_i64).unwrap_or(5).clamp(1, 25);

    match (query, node) {
        (Some(_), Some(_)) => Err("give `query` or `node`, not both".into()),
        (None, None) => Err("give either `query` or `node`".into()),
        (Some(text), None) => {
            if text.trim().is_empty() {
                return Err("`query` is empty".into());
            }
            let semantic_available = embedder.is_some()
                && db.embedding_build().map_err(|e| e.to_string())?.is_some();
            let requested = input.get("mode").and_then(Value::as_str);
            let mode = match requested {
                Some(mode @ ("semantic" | "hybrid")) if !semantic_available => {
                    // Silently answering lexically would make an index without
                    // embeddings look like one whose meaning search found little.
                    return Err(format!(
                        "`{mode}` needs an index built with embeddings and an embedder for this \
                         run; this one has neither. Search with `lexical`."
                    ));
                }
                Some(mode) => mode,
                None if semantic_available => "hybrid",
                None => "lexical",
            };

            let lexical = if mode == "semantic" {
                Vec::new()
            } else {
                db.search(text, limit).map_err(|e| e.to_string())?
            };
            let mut snippets: BTreeMap<String, String> = lexical
                .iter()
                .map(|hit| (hit.node.node_id.as_str().to_string(), hit.snippet.clone()))
                .collect();

            let semantic = if mode == "lexical" {
                Vec::new()
            } else {
                let embedder = embedder.expect("checked by semantic_available");
                let vector = embedder.embed(text)?;
                db.semantic_search(&vector, limit).map_err(|e| e.to_string())?
            };

            let ranked: Vec<String> = match mode {
                "lexical" => lexical
                    .iter()
                    .map(|hit| hit.node.node_id.as_str().to_string())
                    .collect(),
                "semantic" => semantic
                    .iter()
                    .map(|hit| hit.node.node_id.as_str().to_string())
                    .collect(),
                _ => fuse(
                    &lexical
                        .iter()
                        .map(|hit| hit.node.node_id.as_str().to_string())
                        .collect::<Vec<_>>(),
                    &semantic
                        .iter()
                        .map(|hit| hit.node.node_id.as_str().to_string())
                        .collect::<Vec<_>>(),
                    limit as usize,
                ),
            };
            let similarity: BTreeMap<String, f32> = semantic
                .iter()
                .map(|hit| (hit.node.node_id.as_str().to_string(), hit.similarity))
                .collect();

            let mut matches = Vec::new();
            for id in &ranked {
                let node_id = NodeId::parse(id).map_err(|e| e.to_string())?;
                let row = db.node(&node_id).map_err(|e| e.to_string())?;
                let mut value = render(db, ledger, &row, depth, snippets.remove(id).as_deref())?;
                if let Some(score) = similarity.get(id) {
                    value["similarity"] = json!((score * 1000.0).round() / 1000.0);
                }
                matches.push(value);
            }
            Ok(json!({
                "query": text,
                "mode": mode,
                "matchCount": matches.len(),
                "matches": matches,
            }))
        }
        (None, Some(id)) => {
            let node_id = NodeId::parse(id).map_err(|e| e.to_string())?;
            if !db.node_exists(&node_id).map_err(|e| e.to_string())? {
                return Err(format!(
                    "no node {id} in this index. Node ids come from this tool's own results; \
                     search by text instead of composing one."
                ));
            }
            let row = db.node(&node_id).map_err(|e| e.to_string())?;
            Ok(json!({"matchCount": 1, "matches": [render(db, ledger, &row, depth, None)?]}))
        }
    }
}

/// One node, with everything the eight tools used to return separately.
fn render(
    db: &SpecDb,
    ledger: &mut ExposureLedger,
    row: &NodeRow,
    depth: i64,
    snippet: Option<&str>,
) -> Result<Value, String> {
    let spans = db.spans(&row.node_id).map_err(|e| e.to_string())?;
    let (text, truncated) = truncate_chars(&row.raw_text, TEXT_LIMIT);

    // Only what was actually shown becomes citable, and a truncated node is
    // recorded as truncated: a citation into text the model never saw is the
    // thing the ledger exists to refuse.
    let span_ids: Vec<_> = spans.iter().map(|span| span.span_id.clone()).collect();
    ledger.expose_text(&row.node_id, "spec", &span_ids, truncated);

    let ancestors = db.ancestors(&row.node_id, NEIGHBOURS).map_err(|e| e.to_string())?;
    let children = db.children(&row.node_id, NEIGHBOURS).map_err(|e| e.to_string())?;
    let xrefs = db.xrefs(&row.node_id).map_err(|e| e.to_string())?;
    // Definitions are indexed by term, so the node's own heading is the term
    // worth offering; a node with no heading states no definition of its own.
    let definitions = match row.title.as_deref() {
        Some(title) if !title.trim().is_empty() => db
            .definitions_matching(Some(title), NEIGHBOURS)
            .map_err(|e| e.to_string())?,
        _ => Vec::new(),
    };
    let correlated = db.correlated(&row.node_id).map_err(|e| e.to_string())?;
    let (section, title) = db.section(&row.node_id).map_err(|e| e.to_string())?;

    let mut value = json!({
        "nodeId": row.node_id.as_str(),
        "nodeType": row.node_type,
        "sectionNumber": section,
        "title": title,
        "pages": {"start": row.page_start, "end": row.page_end},
        "text": text,
        "textTruncated": truncated,
        "spans": spans.iter().map(|span| json!({
            "spanId": span.span_id.as_str(),
            "page": span.page_number,
            "text": span.raw_text,
        })).collect::<Vec<_>>(),
        "ancestors": ancestors.iter().map(brief).collect::<Vec<_>>(),
        "children": children.iter().map(brief).collect::<Vec<_>>(),
        "crossReferences": xrefs.iter().map(|xref| json!({
            "kind": xref.kind,
            "text": xref.target_reference_text,
            "resolvesTo": xref.resolved_target_node_id.as_ref().map(NodeId::as_str),
            "status": xref.resolution_status,
        })).collect::<Vec<_>>(),
        "definitions": definitions.iter().map(|definition| json!({
            "term": definition.term,
            "text": definition.definition_text,
            "nodeId": definition.node_id.as_str(),
        })).collect::<Vec<_>>(),
        "otherRendition": correlated.iter().map(|other| json!({
            "nodeId": other.other_node_id.as_str(),
            "basis": other.basis,
            "confidence": other.confidence,
        })).collect::<Vec<_>>(),
    });
    if let Some(snippet) = snippet {
        value["snippet"] = json!(snippet);
    }

    if depth > 0 {
        let rows = db
            .subtree(&row.node_id, depth, NEIGHBOURS)
            .map_err(|e| e.to_string())?;
        let mut descendants = Vec::new();
        for descendant in rows.iter().filter(|other| other.node_id != row.node_id) {
            let spans = db.spans(&descendant.node_id).map_err(|e| e.to_string())?;
            let (text, truncated) = truncate_chars(&descendant.raw_text, TEXT_LIMIT);
            let span_ids: Vec<_> = spans.iter().map(|span| span.span_id.clone()).collect();
            ledger.expose_text(&descendant.node_id, "spec.depth", &span_ids, truncated);
            descendants.push(json!({
                "nodeId": descendant.node_id.as_str(),
                "nodeType": descendant.node_type,
                "sectionNumber": descendant.section_number,
                "title": descendant.title,
                "text": text,
                "textTruncated": truncated,
                "spans": spans.iter().map(|span| json!({
                    "spanId": span.span_id.as_str(),
                    "page": span.page_number,
                    "text": span.raw_text,
                })).collect::<Vec<_>>(),
            }));
        }
        value["descendants"] = json!(descendants);
    }
    Ok(value)
}

/// A neighbour is named, not quoted: enough to decide whether to ask for it.
fn brief(row: &NodeRow) -> Value {
    json!({
        "nodeId": row.node_id.as_str(),
        "nodeType": row.node_type,
        "sectionNumber": row.section_number,
        "title": row.title,
    })
}
