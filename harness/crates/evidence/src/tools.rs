use serde::Deserialize;
use serde_json::{Value, json};
use spec2lean_specdb::{NodeId, SpecDb, SpecDbError};

use crate::ledger::ExposureLedger;
use crate::render::{node_summary, planning_summary, show};
use crate::scope::EvidenceScope;
use crate::validation::validate_submission;
use harness::{ToolOutcome, ToolSet, ToolSpec};

const DEFAULT_LIMIT: i64 = 20;
const DEFAULT_MAX_DEPTH: i64 = 3;

/// Typed inputs. Deserialising into these is the guarantee that replaced the
/// MCP layer's JSON Schema round trip: a malformed call cannot reach a query,
/// and the failure the model gets back names the field.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct NodeInput {
    #[serde(rename = "nodeId")]
    node_id: NodeId,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct LimitedNodeInput {
    #[serde(rename = "nodeId")]
    node_id: NodeId,
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SubtreeInput {
    #[serde(rename = "nodeId")]
    node_id: NodeId,
    #[serde(rename = "maxDepth")]
    max_depth: Option<i64>,
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct SearchInput {
    query: String,
    justification: String,
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct DefinitionsInput {
    query: String,
    limit: Option<i64>,
}

/// The complete capability surface of one Phase-3 session.
pub struct EvidenceTools<'a> {
    db: &'a SpecDb,
    scope: EvidenceScope,
    ledger: ExposureLedger,
    bundle: Option<Value>,
}

impl<'a> EvidenceTools<'a> {
    /// Seed the ledger from the Phase-2 boundary. Every attached node is shown
    /// with its exact text up front, which is what makes it selectable.
    pub fn new(db: &'a SpecDb, scope: EvidenceScope) -> Result<Self, SpecDbError> {
        let mut ledger = ExposureLedger::default();
        for seed in &scope.seed_nodes {
            if !db.node_exists(&seed.node_id)? {
                return Err(SpecDbError::UnknownNode(format!(
                    "Phase 2 references a nonexistent Phase-1 node: {}",
                    seed.node_id
                )));
            }
            let spans: Vec<_> = db
                .spans(&seed.node_id)?
                .into_iter()
                .map(|span| span.span_id)
                .collect();
            ledger.expose_selectable(&seed.node_id, &seed.basis, &spans);
        }
        Ok(Self {
            db,
            scope,
            ledger,
            bundle: None,
        })
    }

    pub fn scope(&self) -> &EvidenceScope {
        &self.scope
    }

    pub fn ledger(&self) -> &ExposureLedger {
        &self.ledger
    }

    /// The accepted bundle, once one exists.
    pub fn bundle(&self) -> Option<&Value> {
        self.bundle.as_ref()
    }

    fn require_discovered(&self, node_id: &NodeId) -> Result<(), String> {
        if self.ledger.is_discovered(node_id) {
            Ok(())
        } else {
            Err(format!(
                "node is outside the bounded session context: {node_id}"
            ))
        }
    }

    fn dispatch(&mut self, name: &str, input: &Value) -> Result<Value, String> {
        match name {
            "spec_show" => {
                let input: NodeInput = parse(input)?;
                self.require_discovered(&input.node_id)?;
                let row = self.db.node(&input.node_id).map_err(display)?;
                let value = show(self.db, &row).map_err(display)?;
                let spans: Vec<_> = self
                    .db
                    .spans(&input.node_id)
                    .map_err(display)?
                    .into_iter()
                    .map(|span| span.span_id)
                    .collect();
                let truncated = value["textTruncated"].as_bool().unwrap_or(false);
                self.ledger
                    .expose_text(&input.node_id, "SHOW", &spans, truncated);
                Ok(value)
            }
            "spec_children" => {
                let input: LimitedNodeInput = parse(input)?;
                self.require_discovered(&input.node_id)?;
                let rows = self
                    .db
                    .children(&input.node_id, input.limit.unwrap_or(DEFAULT_LIMIT))
                    .map_err(display)?;
                let basis = format!("CHILD_OF:{}", input.node_id);
                for row in &rows {
                    self.ledger.expose(&row.node_id, &basis);
                }
                Ok(json!(
                    rows.iter().map(|row| node_summary(row, false)).collect::<Vec<_>>()
                ))
            }
            "spec_ancestors" => {
                let input: NodeInput = parse(input)?;
                self.require_discovered(&input.node_id)?;
                let rows = self.db.ancestors(&input.node_id, 30).map_err(display)?;
                let basis = format!("ANCESTOR_OF:{}", input.node_id);
                for row in &rows {
                    self.ledger.expose(&row.node_id, &basis);
                }
                Ok(json!(rows.iter().map(planning_summary).collect::<Vec<_>>()))
            }
            "spec_subtree" => {
                let input: SubtreeInput = parse(input)?;
                self.require_discovered(&input.node_id)?;
                let rows = self
                    .db
                    .subtree(
                        &input.node_id,
                        input.max_depth.unwrap_or(DEFAULT_MAX_DEPTH),
                        input.limit.unwrap_or(DEFAULT_LIMIT),
                    )
                    .map_err(display)?;
                let basis = format!("SUBTREE_OF:{}", input.node_id);
                let mut result = Vec::with_capacity(rows.len());
                for row in &rows {
                    let spans = self.db.spans(&row.node_id).map_err(display)?;
                    let span_ids: Vec<_> =
                        spans.iter().map(|span| span.span_id.clone()).collect();
                    let mut value = node_summary(row, true);
                    self.ledger.expose_text(
                        &row.node_id,
                        &basis,
                        &span_ids,
                        value["textTruncated"].as_bool().unwrap_or(false),
                    );
                    value["sourceSpanIds"] = json!(span_ids);
                    result.push(value);
                }
                Ok(json!(result))
            }
            "spec_search" => {
                let input: SearchInput = parse(input)?;
                let justification =
                    spec2lean_specdb::normalize_text(&input.justification);
                if justification.is_empty() {
                    return Err("bounded search requires a relevance justification".into());
                }
                let hits = self
                    .db
                    .search(&input.query, input.limit.unwrap_or(DEFAULT_LIMIT))
                    .map_err(display)?;
                let basis = format!("SEARCH:{justification}");
                for hit in &hits {
                    self.ledger.expose(&hit.node.node_id, &basis);
                }
                Ok(json!(
                    hits.iter()
                        .map(|hit| {
                            let mut value = planning_summary(&hit.node);
                            value["snippet"] = json!(hit.snippet);
                            value
                        })
                        .collect::<Vec<_>>()
                ))
            }
            "spec_xrefs" => {
                let input: NodeInput = parse(input)?;
                self.require_discovered(&input.node_id)?;
                let rows = self.db.xrefs(&input.node_id).map_err(display)?;
                let basis = format!("XREF_OF:{}", input.node_id);
                let mut result = Vec::with_capacity(rows.len());
                for row in &rows {
                    self.ledger.expose(&row.source_node_id, &basis);
                    let mut value = json!({
                        "reference_id": row.reference_id,
                        "source_node_id": row.source_node_id,
                        "ordinal": row.ordinal,
                        "kind": row.kind,
                        "raw_text": row.raw_text,
                        "target_reference_text": row.target_reference_text,
                        "href": row.href,
                        "resolved_target_node_id": row.resolved_target_node_id,
                        "resolution_status": row.resolution_status,
                        "candidate_count": row.candidate_count,
                    });
                    if let Some(target) = &row.resolved_target_node_id {
                        self.ledger.expose(target, &basis);
                        let target_row = self.db.node(target).map_err(display)?;
                        value["resolvedTarget"] = node_summary(&target_row, false);
                    }
                    result.push(value);
                }
                Ok(json!(result))
            }
            "spec_definitions" => {
                let input: DefinitionsInput = parse(input)?;
                let rows = self
                    .db
                    .definitions(&input.query, input.limit.unwrap_or(DEFAULT_LIMIT))
                    .map_err(display)?;
                let basis = format!(
                    "DEFINITION:{}",
                    spec2lean_specdb::normalize_text(&input.query)
                );
                for row in &rows {
                    self.ledger.expose(&row.node_id, &basis);
                }
                Ok(json!(
                    rows.iter()
                        .map(|row| json!({
                            "term": row.term,
                            "definition_text": row.definition_text,
                            "structural_basis": row.structural_basis,
                            "node_id": row.node_id,
                        }))
                        .collect::<Vec<_>>()
                ))
            }
            "spec_correlated" => {
                let input: NodeInput = parse(input)?;
                self.require_discovered(&input.node_id)?;
                let rows = self.db.correlated(&input.node_id).map_err(display)?;
                let basis = format!("CORRELATED_WITH:{}", input.node_id);
                let mut result = Vec::with_capacity(rows.len());
                for row in &rows {
                    self.ledger.expose(&row.other_node_id, &basis);
                    let other = self.db.node(&row.other_node_id).map_err(display)?;
                    result.push(json!({
                        "correlation_id": row.correlation_id,
                        "other_node_id": row.other_node_id,
                        "basis": row.basis,
                        "confidence": row.confidence,
                        "correlatedNode": node_summary(&other, false),
                    }));
                }
                Ok(json!(result))
            }
            "submit_evidence" => {
                match validate_submission(self.db, &self.scope, &self.ledger, input)
                    .map_err(display)?
                {
                    Ok(bundle) => {
                        let count = bundle["evidence"].as_array().map_or(0, Vec::len);
                        self.bundle = Some(bundle);
                        Ok(json!({
                            "accepted": true,
                            "evidenceCount": count,
                            "message": "Evidence accepted; exact text and provenance were resolved from Phase 1.",
                        }))
                    }
                    Err(diagnostics) => Ok(json!({
                        "accepted": false,
                        "diagnostics": diagnostics,
                    })),
                }
            }
            other => Err(format!("unknown tool: {other}")),
        }
    }
}

fn parse<T: for<'de> Deserialize<'de>>(input: &Value) -> Result<T, String> {
    serde_json::from_value(input.clone()).map_err(|error| format!("invalid arguments: {error}"))
}

fn display(error: impl std::fmt::Display) -> String {
    error.to_string()
}

fn object(properties: Value, required: &[&str]) -> Value {
    json!({
        "type": "object",
        "properties": properties,
        "additionalProperties": false,
        "required": required,
    })
}

impl ToolSet for EvidenceTools<'_> {
    fn specs(&self) -> Vec<ToolSpec> {
        let node_id = json!({"type": "string", "pattern": "^node:"});
        let span_id = json!({"type": "string", "pattern": "^span:"});
        let limit = json!({"type": "integer", "minimum": 1, "maximum": 100, "default": 20});
        let selection = object(
            json!({
                "sourceNodeIds": {"type": "array", "items": node_id, "minItems": 1},
                "sourceSpanIds": {"type": "array", "items": span_id},
                "role": {"type": "string", "enum": crate::model::Role::ALL.map(|role| role.as_str())},
                "tier": {"type": "string", "enum": crate::model::Tier::ALL.map(|tier| tier.as_str())},
                "rationale": {"type": "string", "minLength": 1},
            }),
            &["sourceNodeIds", "role", "tier", "rationale"],
        );
        vec![
            ToolSpec::new(
                "spec_show",
                "Show exact text, spans, and provenance for one already discovered Phase-1 node.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_children",
                "Discover bounded direct children of an exposed Phase-1 node.",
                object(json!({"nodeId": node_id, "limit": limit}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_ancestors",
                "Discover relevant ancestors of an exposed Phase-1 node.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_subtree",
                "Read a depth- and row-bounded subtree rooted at an exposed Phase-1 node.",
                object(
                    json!({
                        "nodeId": node_id,
                        "maxDepth": {"type": "integer", "minimum": 0, "maximum": 8, "default": 3},
                        "limit": limit,
                    }),
                    &["nodeId"],
                ),
            ),
            ToolSpec::new(
                "spec_search",
                "Last-resort bounded Phase-1 full-text search requiring a unit-specific justification.",
                object(
                    json!({
                        "query": {"type": "string", "minLength": 1},
                        "justification": {"type": "string", "minLength": 1},
                        "limit": limit,
                    }),
                    &["query", "justification"],
                ),
            ),
            ToolSpec::new(
                "spec_xrefs",
                "Discover explicit incoming/outgoing cross-references for an exposed node.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_definitions",
                "Discover bounded structurally indexed definitions relevant to a term.",
                object(
                    json!({"query": {"type": "string", "minLength": 1}, "limit": limit}),
                    &["query"],
                ),
            ),
            ToolSpec::new(
                "spec_correlated",
                "Discover Phase-1 correlated HTML/PDF nodes for an exposed node.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "submit_evidence",
                "Submit relevance selections only. Deterministic validation and provenance \
                 reconstruction run immediately; correct diagnostics and resubmit within this \
                 same session.",
                object(
                    json!({
                        "unitId": {"type": "string", "pattern": "^unit:"},
                        "selections": {"type": "array", "items": selection, "minItems": 1},
                    }),
                    &["unitId", "selections"],
                ),
            ),
        ]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        self.ledger.record_call(name, input);
        match self.dispatch(name, input) {
            Ok(value) => ToolOutcome::Ok(value),
            Err(message) => ToolOutcome::Err(message),
        }
    }

    fn finished(&self) -> bool {
        self.bundle.is_some()
    }
}
