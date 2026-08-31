use serde_json::{Value, json};

use crate::model::{ClaimKind, Diagnostic, DiagnosticCode as Code, RestrictionKind, UnitKind};
use crate::scope::SemanticScope;
use crate::validation::validate_submission;
use harness::{ToolOutcome, ToolSet, ToolSpec};

/// The evidence fields the extractor actually needs.
///
/// Bounding the transport keeps the GUI-oriented provenance (span geometry, DOM
/// paths, document hashes) out of the model's context while preserving every
/// source passage. The bundle hash travels with it, so the artifact stays
/// pinned to the complete bundle even though the view is a projection.
const SEMANTIC_EVIDENCE_FIELDS: &[&str] = &[
    "evidenceId", "role", "tier", "rationale", "sourceType", "sectionNumber", "sectionTitle",
    "exactText", "sourceNodeIds", "htmlAnchor", "pdfPage",
];

pub fn semantic_evidence_view(scope: &SemanticScope, bundle: &Value) -> Value {
    let evidence: Vec<Value> = bundle
        .get("evidence")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter(|item| item.is_object())
                .map(|item| {
                    let projected: serde_json::Map<String, Value> = SEMANTIC_EVIDENCE_FIELDS
                        .iter()
                        .map(|field| {
                            (
                                (*field).to_string(),
                                item.get(*field).cloned().unwrap_or(Value::Null),
                            )
                        })
                        .collect();
                    Value::Object(projected)
                })
                .collect()
        })
        .unwrap_or_default();
    json!({
        "schemaVersion": 1,
        "unit": bundle.get("unit").cloned().unwrap_or_else(|| json!({})),
        "evidence": evidence,
        "resolutions": bundle.get("resolutions").cloned().unwrap_or_else(|| json!([])),
        "transport": {
            "complete": true,
            "evidenceBundleHash": scope.evidence_bundle_hash,
            "evidenceCount": evidence.len(),
        },
    })
}

/// The Phase-4 capability surface: read the evidence, submit the semantics.
pub struct SemanticTools {
    scope: SemanticScope,
    bundle: Value,
    extractor: Value,
    evidence_read: bool,
    artifact: Option<Value>,
}

impl SemanticTools {
    pub fn new(scope: SemanticScope, bundle: Value, extractor: Value) -> Self {
        Self {
            scope,
            bundle,
            extractor,
            evidence_read: false,
            artifact: None,
        }
    }

    pub fn scope(&self) -> &SemanticScope {
        &self.scope
    }

    pub fn artifact(&self) -> Option<&Value> {
        self.artifact.as_ref()
    }

    fn text() -> Value {
        json!({"type": "string", "minLength": 1})
    }

    fn evidence_ids() -> Value {
        json!({
            "type": "array",
            "items": {"type": "string", "pattern": "^(evidence|resolution):"},
        })
    }

    /// A component object: the given properties plus the mandatory citation
    /// array, with no room for invented fields.
    fn component(properties: Value, required: &[&str]) -> Value {
        let mut properties = properties;
        properties["evidenceIds"] = Self::evidence_ids();
        let mut required: Vec<&str> = required.to_vec();
        required.push("evidenceIds");
        json!({
            "type": "object",
            "properties": properties,
            "additionalProperties": false,
            "required": required,
        })
    }

    fn submission_schema() -> Value {
        let text = Self::text();
        let syntax = Self::component(
            json!({"form": text, "description": text}),
            &["form"],
        );
        let operand = Self::component(
            json!({
                "name": text, "role": text, "description": text,
                "constraints": {"type": "array", "items": text},
            }),
            &["name", "role", "description", "constraints"],
        );
        let result = Self::component(
            json!({
                "name": text, "description": text,
                "constraints": {"type": "array", "items": text},
            }),
            &["name", "description", "constraints"],
        );
        let branch = Self::component(
            json!({"condition": text, "behavior": text}),
            &["condition", "behavior"],
        );
        let operation = Self::component(
            json!({
                "description": text,
                "inputs": {"type": "array", "items": text, "minItems": 1},
                "result": text,
                "branches": {"type": "array", "items": branch},
            }),
            &["description", "inputs", "result", "branches"],
        );
        let edge = Self::component(
            json!({"condition": text, "behavior": text}),
            &["condition", "behavior"],
        );
        let state = Self::component(
            json!({"target": text, "effect": text}),
            &["target", "effect"],
        );
        let restriction = Self::component(
            json!({
                "kind": {"type": "string", "enum": RestrictionKind::ALL.map(RestrictionKind::as_str)},
                "description": text,
            }),
            &["kind", "description"],
        );
        let dependency = Self::component(
            json!({
                "dependencyId": {"type": "string", "pattern": "^shared:"},
                "concept": text,
                "description": text,
                "artifactId": text,
                "semanticClaimIds": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^claim:"},
                    "uniqueItems": true,
                },
            }),
            &["concept", "description"],
        );
        let claim = Self::component(
            json!({
                "claimId": {"type": "string", "pattern": "^claim:"},
                "kind": {"type": "string", "enum": ClaimKind::ALL.map(ClaimKind::as_str)},
                "statement": text,
            }),
            &["claimId", "kind", "statement"],
        );
        let identity = Self::component(
            json!({"name": text, "form": text, "description": text}),
            &["name"],
        );
        let predication = Self::component(
            json!({"guard": text, "whenTrue": text, "whenFalse": text}),
            &["guard", "whenTrue", "whenFalse"],
        );

        // The root stays a plain object rather than a SUCCESS/failure union:
        // the conditional requirements are enforced by the validator, which can
        // explain a rejection far better than a schema union can.
        json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["outcome"],
            "properties": {
                "outcome": {"type": "string", "enum": ["SUCCESS", "INSUFFICIENT_EVIDENCE"]},
                "unitKind": {"type": "string", "enum": UnitKind::ALL.map(UnitKind::as_str)},
                "identity": identity,
                "syntaxForms": {"type": "array", "items": syntax},
                "inputs": {"type": "array", "items": operand},
                "result": result,
                "operation": operation,
                "edgeCases": {"type": "array", "items": edge},
                "stateEffects": {"type": "array", "items": state},
                "predication": predication,
                "restrictions": {"type": "array", "items": restriction},
                "dependencies": {"type": "array", "items": dependency},
                "claims": {"type": "array", "items": claim, "minItems": 1},
                "missingAspects": {"type": "array", "items": text, "minItems": 1},
                "explanation": text,
                "evidenceIds": Self::evidence_ids(),
            },
        })
    }
}

impl ToolSet for SemanticTools {
    fn specs(&self) -> Vec<ToolSpec> {
        vec![
            ToolSpec::new(
                "get_evidence",
                "Read the complete, immutable Phase-3 evidence bundle for this one semantic unit.",
                json!({"type": "object", "properties": {}, "additionalProperties": false}),
            ),
            ToolSpec::new(
                "submit_semantics",
                "Submit semantics or a precise insufficient-evidence failure for deterministic \
                 validation.",
                Self::submission_schema(),
            ),
        ]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        match name {
            "get_evidence" => {
                if input.as_object().is_some_and(|object| !object.is_empty()) {
                    return ToolOutcome::Err("get_evidence accepts no arguments".into());
                }
                self.evidence_read = true;
                ToolOutcome::Ok(semantic_evidence_view(&self.scope, &self.bundle))
            }
            "submit_semantics" => {
                // Extracting before reading the evidence would mean extracting
                // from memory, which is the one thing this phase must not do.
                if !self.evidence_read {
                    return ToolOutcome::Ok(json!({
                        "accepted": false,
                        "diagnostics": [Diagnostic::root(
                            Code::EvidenceNotRead,
                            "call get_evidence before submitting semantics",
                        )],
                    }));
                }
                match validate_submission(&self.scope, &self.bundle, input, &self.extractor) {
                    Ok(artifact) => {
                        let outcome = artifact["outcome"].clone();
                        self.artifact = Some(artifact);
                        ToolOutcome::Ok(json!({
                            "accepted": true,
                            "outcome": outcome,
                            "message": "Semantic submission accepted.",
                        }))
                    }
                    Err(diagnostics) => ToolOutcome::Ok(json!({
                        "accepted": false,
                        "diagnostics": diagnostics,
                    })),
                }
            }
            other => ToolOutcome::Err(format!("unknown tool: {other}")),
        }
    }

    fn finished(&self) -> bool {
        self.artifact.is_some()
    }
}
