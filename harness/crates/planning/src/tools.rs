use serde::Deserialize;
use serde_json::{Value, json};
use spec2lean_specdb::{
    MAX_NODE_TEXT_CHARS, NodeId, NodeRow, SpecDb, SpecDbError, truncate_chars,
};

use crate::scope::ResolvedScope;
use crate::validation::build_validated_plan;
use harness::{ToolOutcome, ToolSet, ToolSpec};

const DEFAULT_LIMIT: i64 = 20;

/// Phase 2's node view: structure and bounded text, no span geometry.
///
/// Unlike Phase 3, the planner browses the whole index — it is deciding what to
/// plan, so it cannot be confined to a pre-agreed boundary. What bounds it
/// instead is that every claim it makes is checked against the index on submit.
fn node_summary(row: &NodeRow, include_text: bool) -> Value {
    let mut value = json!({
        "nodeId": row.node_id,
        "nodeType": row.node_type,
        "title": row.title,
        "sectionNumber": row.section_number,
        "htmlAnchor": row.html_anchor,
        "pageStart": row.page_start,
        "sourceType": row.source_type.as_str(),
    });
    if include_text {
        let (text, truncated) = truncate_chars(&row.raw_text, MAX_NODE_TEXT_CHARS);
        value["text"] = json!(text);
        value["textTruncated"] = json!(truncated);
    }
    value
}

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
    limit: Option<i64>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct DefinitionsInput {
    query: Option<String>,
    limit: Option<i64>,
}

pub struct PlanningTools<'a> {
    db: &'a SpecDb,
    scope: ResolvedScope,
    plan_run_id: String,
    source_database_digest: String,
    plan: Option<Value>,
}

impl<'a> PlanningTools<'a> {
    pub fn new(
        db: &'a SpecDb,
        scope: ResolvedScope,
        plan_run_id: impl Into<String>,
        source_database_digest: impl Into<String>,
    ) -> Self {
        Self {
            db,
            scope,
            plan_run_id: plan_run_id.into(),
            source_database_digest: source_database_digest.into(),
            plan: None,
        }
    }

    pub fn scope(&self) -> &ResolvedScope {
        &self.scope
    }

    pub fn plan(&self) -> Option<&Value> {
        self.plan.as_ref()
    }

    fn dispatch(&mut self, name: &str, input: &Value) -> Result<Value, String> {
        let display = |error: SpecDbError| error.to_string();
        match name {
            "spec_search" => {
                let input: SearchInput = parse(input)?;
                let hits = self
                    .db
                    .search(&input.query, input.limit.unwrap_or(DEFAULT_LIMIT))
                    .map_err(display)?;
                Ok(json!(
                    hits.iter()
                        .map(|hit| {
                            let mut value = node_summary(&hit.node, false);
                            value["snippet"] = json!(hit.snippet);
                            value
                        })
                        .collect::<Vec<_>>()
                ))
            }
            "spec_show" => {
                let input: NodeInput = parse(input)?;
                let row = self.db.node(&input.node_id).map_err(display)?;
                let mut value = node_summary(&row, true);
                value["metadata"] =
                    serde_json::from_str(&row.metadata_json).unwrap_or_else(|_| json!({}));
                Ok(value)
            }
            "spec_children" => {
                let input: LimitedNodeInput = parse(input)?;
                let rows = self
                    .db
                    .children(&input.node_id, input.limit.unwrap_or(DEFAULT_LIMIT))
                    .map_err(display)?;
                Ok(json!(
                    rows.iter().map(|row| node_summary(row, false)).collect::<Vec<_>>()
                ))
            }
            "spec_ancestors" => {
                let input: NodeInput = parse(input)?;
                let rows = self.db.ancestors(&input.node_id, 30).map_err(display)?;
                Ok(json!(
                    rows.iter().map(|row| node_summary(row, false)).collect::<Vec<_>>()
                ))
            }
            "spec_subtree" => {
                let input: SubtreeInput = parse(input)?;
                let rows = self
                    .db
                    .subtree(
                        &input.node_id,
                        input.max_depth.unwrap_or(3),
                        input.limit.unwrap_or(DEFAULT_LIMIT),
                    )
                    .map_err(display)?;
                Ok(json!(
                    rows.iter().map(|row| node_summary(row, true)).collect::<Vec<_>>()
                ))
            }
            "spec_xrefs" => {
                let input: NodeInput = parse(input)?;
                let rows = self.db.xrefs(&input.node_id).map_err(display)?;
                Ok(json!(
                    rows.iter()
                        .map(|row| json!({
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
                        }))
                        .collect::<Vec<_>>()
                ))
            }
            "spec_definitions" => {
                let input: DefinitionsInput = parse(input)?;
                let rows = self
                    .db
                    .definitions_matching(
                        input.query.as_deref(),
                        input.limit.unwrap_or(DEFAULT_LIMIT),
                    )
                    .map_err(display)?;
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
            "submit_plan" => {
                match build_validated_plan(
                    self.db,
                    &self.scope,
                    input,
                    &self.plan_run_id,
                    &self.source_database_digest,
                )
                .map_err(display)?
                {
                    Ok(plan) => {
                        let units = plan["requestedUnits"].as_array().map_or(0, Vec::len);
                        let groups = plan["translationGroups"].as_array().map_or(0, Vec::len);
                        self.plan = Some(plan);
                        Ok(json!({
                            "accepted": true,
                            "unitCount": units,
                            "groupCount": groups,
                            "message": "Plan accepted; deterministic layers were derived.",
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

fn object(properties: Value, required: &[&str]) -> Value {
    let mut value = json!({
        "type": "object",
        "properties": properties,
        "additionalProperties": false,
    });
    if !required.is_empty() {
        value["required"] = json!(required);
    }
    value
}

impl ToolSet for PlanningTools<'_> {
    fn specs(&self) -> Vec<ToolSpec> {
        let node_id = json!({"type": "string", "pattern": "^node:"});
        let unit_id = json!({"type": "string", "pattern": "^unit:"});
        let limit = json!({"type": "integer", "minimum": 1, "maximum": 100, "default": 20});
        let text = json!({"type": "string", "minLength": 1});
        let source_nodes = json!({"type": "array", "items": node_id, "minItems": 1});

        let prerequisite = object(
            json!({"key": text, "name": text, "reason": text, "sourceNodeIds": source_nodes}),
            &["key", "name", "reason", "sourceNodeIds"],
        );
        let shared_prerequisite = object(
            json!({
                "key": {"type": "string", "minLength": 1,
                        "description": "Stable conceptual key; never a Lean declaration or representation."},
                "name": text,
                "kind": {"type": "string", "minLength": 1,
                         "description": "Open, specification-derived concept label; not a closed enum."},
                "reason": text,
                "sourceNodeIds": source_nodes,
                "requiredBy": {"type": "array", "items": unit_id, "minItems": 1, "uniqueItems": true},
            }),
            &["key", "name", "kind", "reason", "sourceNodeIds", "requiredBy"],
        );
        let dependency = object(
            json!({
                "from": text, "to": text, "reason": text,
                "supportingNodeIds": source_nodes,
                "origin": {"type": "string", "enum": ["EXPLICIT", "INFERRED"]},
            }),
            &["from", "to", "reason", "supportingNodeIds", "origin"],
        );
        let translation_group = object(
            json!({
                "name": {"type": "string", "pattern": "^[A-Z][A-Za-z0-9]{0,63}$", "maxLength": 64,
                         "description": "Concise UpperCamelCase name derived from indexed specification structure."},
                "unitIds": {"type": "array", "items": unit_id, "minItems": 1},
                "reason": text,
                "supportingNodeIds": source_nodes,
                "origin": {"type": "string", "enum": ["EXPLICIT", "INFERRED"]},
            }),
            &["name", "unitIds", "reason", "supportingNodeIds", "origin"],
        );

        vec![
            ToolSpec::new(
                "spec_search",
                "Bounded full-text search of the Phase-1 specification index.",
                object(json!({"query": text, "limit": limit}), &["query"]),
            ),
            ToolSpec::new(
                "spec_show",
                "Show one Phase-1 node with bounded source text and provenance.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_children",
                "List bounded direct children of a Phase-1 node.",
                object(json!({"nodeId": node_id, "limit": limit}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_ancestors",
                "List ancestors of a Phase-1 node from root to the node.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_subtree",
                "Read a depth- and row-bounded Phase-1 subtree.",
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
                "spec_xrefs",
                "List explicit incoming and outgoing cross-references for one node.",
                object(json!({"nodeId": node_id}), &["nodeId"]),
            ),
            ToolSpec::new(
                "spec_definitions",
                "Search structurally identified Phase-1 definitions.",
                object(json!({"query": {"type": "string"}, "limit": limit}), &[]),
            ),
            ToolSpec::new(
                "submit_plan",
                "Submit semantic planning content for deterministic validation. Diagnostics are \
                 returned without ending the session; correct and resubmit until accepted.",
                object(
                    json!({
                        "requestedUnitIds": {"type": "array", "items": unit_id},
                        "translationGroups": {"type": "array", "items": translation_group, "minItems": 1},
                        "externalPrerequisites": {"type": "array", "items": prerequisite},
                        "sharedPrerequisites": {"type": "array", "items": shared_prerequisite},
                        "dependencies": {"type": "array", "items": dependency},
                    }),
                    &[
                        "requestedUnitIds", "translationGroups", "externalPrerequisites",
                        "sharedPrerequisites", "dependencies",
                    ],
                ),
            ),
        ]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        match self.dispatch(name, input) {
            Ok(value) => ToolOutcome::Ok(value),
            Err(message) => ToolOutcome::Err(message),
        }
    }

    fn finished(&self) -> bool {
        self.plan.is_some()
    }
}
