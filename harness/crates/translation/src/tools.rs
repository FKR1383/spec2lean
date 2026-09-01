use std::path::PathBuf;

use serde_json::{Value, json};
use spec2lean_lean::{AxiomAudit, BuildResult, DependencyModule, audit, run_build};

use crate::scope::TranslationScope;
use crate::validation::{DECLARATION_ROLES, claim_index, validate_submission};
use harness::{ToolOutcome, ToolSet, ToolSpec};

const MAX_REPORTED_ERRORS: usize = 12;

/// Phase 5's capability surface, with the compiler wired into the loop.
///
/// `submit_translation` runs structural validation only. If that passes, the
/// harness itself compiles the source in `after_tool_call` and appends the
/// diagnostics to the same tool result, so a build failure arrives as a reply
/// to the submission rather than as a separate phase two processes later. The
/// session finishes only when the source is both structurally valid and builds.
pub struct TranslationTools {
    scope: TranslationScope,
    workspace: PathBuf,
    lean_executable: String,
    translator: Value,
    /// The frozen core this group compiles against, staged as a dependency.
    core: Option<DependencyModule>,
    /// Set by `submit_translation`, consumed by `after_tool_call`.
    pending: Option<(String, Value)>,
    accepted: Option<Value>,
    /// Set when the translator reports that the semantics do not determine a
    /// formalization. A terminal outcome, but not a translation.
    underdetermined: Option<Value>,
    last_build: Option<BuildResult>,
    last_audit: Option<AxiomAudit>,
    builds: u32,
}

impl TranslationTools {
    pub fn new(
        scope: TranslationScope,
        workspace: PathBuf,
        lean_executable: impl Into<String>,
        translator: Value,
    ) -> Self {
        Self {
            scope,
            workspace,
            lean_executable: lean_executable.into(),
            translator,
            core: None,
            pending: None,
            accepted: None,
            underdetermined: None,
            last_build: None,
            last_audit: None,
            builds: 0,
        }
    }

    /// Compile this group against a frozen core. Required whenever the group
    /// has shared concepts; the scope refuses to resolve without one.
    pub fn with_shared_core(mut self, module: &str, source: PathBuf) -> Self {
        self.core = Some(DependencyModule {
            module: module.to_string(),
            source,
        });
        self
    }

    pub fn scope(&self) -> &TranslationScope {
        &self.scope
    }

    pub fn manifest(&self) -> Option<&Value> {
        self.accepted.as_ref()
    }

    /// The recorded reason this group could not be formalized, if it could not.
    pub fn underdetermined(&self) -> Option<&Value> {
        self.underdetermined.as_ref()
    }

    pub fn last_build(&self) -> Option<&BuildResult> {
        self.last_build.as_ref()
    }

    pub fn last_audit(&self) -> Option<&AxiomAudit> {
        self.last_audit.as_ref()
    }

    /// How many times the compiler ran. In the old pipeline this was always
    /// one per phase invocation; here it is the length of the repair loop.
    pub fn build_count(&self) -> u32 {
        self.builds
    }

    pub fn lean_path(&self) -> PathBuf {
        self.workspace.join(self.scope.lean_file())
    }

    /// What the translator must supply to report that it cannot proceed.
    ///
    /// Deliberately as demanding as a successful submission: naming which
    /// claims are underdetermined and what is missing from each is the point.
    /// A vague "not enough information" would be indistinguishable from
    /// unwillingness, and would give Phase 4 nothing to act on.
    fn underdetermined_schema() -> Value {
        json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["explanation", "underdeterminedClaims"],
            "properties": {
                "explanation": {"type": "string", "minLength": 1},
                "underdeterminedClaims": {
                    "type": "array", "minItems": 1,
                    "items": {
                        "type": "object", "additionalProperties": false,
                        "required": ["unitId", "claimId", "missing"],
                        "properties": {
                            "unitId": {"type": "string", "pattern": "^unit:"},
                            "claimId": {"type": "string", "pattern": "^claim:"},
                            "missing": {"type": "string", "minLength": 1},
                        },
                    },
                },
            },
        })
    }

    /// Validate an underdetermined report against the group's own claims.
    fn validate_underdetermined(&self, input: &Value) -> Result<Value, Vec<Value>> {
        let mut diagnostics = Vec::new();
        let allowed: std::collections::BTreeSet<(&str, &str)> = self
            .scope
            .claim_refs
            .iter()
            .map(|(unit_id, claim_id)| (unit_id.as_str(), claim_id.as_str()))
            .collect();
        let explanation = input
            .get("explanation")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default();
        if explanation.is_empty() {
            diagnostics.push(json!({
                "code": "INVALID_TEXT",
                "message": "an underdetermined report requires an explanation",
                "path": "$.explanation",
            }));
        }
        let claims = input
            .get("underdeterminedClaims")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default();
        if claims.is_empty() {
            diagnostics.push(json!({
                "code": "MISSING_UNDERDETERMINED_CLAIMS",
                "message": "name at least one claim the semantics do not determine",
                "path": "$.underdeterminedClaims",
            }));
        }
        let mut seen = std::collections::BTreeSet::new();
        for (index, item) in claims.iter().enumerate() {
            let path = format!("$.underdeterminedClaims[{index}]");
            let unit_id = item.get("unitId").and_then(Value::as_str).unwrap_or_default();
            let claim_id = item.get("claimId").and_then(Value::as_str).unwrap_or_default();
            if !allowed.contains(&(unit_id, claim_id)) {
                diagnostics.push(json!({
                    "code": "UNKNOWN_CLAIM_REF",
                    "message": format!("this group has no claim {unit_id}/{claim_id}"),
                    "path": format!("{path}.claimId"),
                }));
                continue;
            }
            if !seen.insert((unit_id.to_string(), claim_id.to_string())) {
                diagnostics.push(json!({
                    "code": "DUPLICATE_CLAIM_REF",
                    "message": format!("claim named more than once: {unit_id}/{claim_id}"),
                    "path": format!("{path}.claimId"),
                }));
            }
            if item
                .get("missing")
                .and_then(Value::as_str)
                .map(str::trim)
                .is_none_or(str::is_empty)
            {
                diagnostics.push(json!({
                    "code": "INVALID_TEXT",
                    "message": "say what is missing from this claim",
                    "path": format!("{path}.missing"),
                }));
            }
        }
        if !diagnostics.is_empty() {
            return Err(diagnostics);
        }
        Ok(json!({
            "schemaVersion": crate::scope::TRANSLATION_SCHEMA_VERSION,
            "phase": "LLM_GROUP_TRANSLATOR",
            "outcome": "UNDERDETERMINED",
            "planRunId": self.scope.plan_run_id,
            "group": {"name": self.scope.group, "unitIds": self.scope.unit_ids()},
            "translationRunId": self.scope.translation_run_id,
            "translator": self.translator,
            "createdAt": self.scope.created_at,
            "explanation": explanation,
            "underdeterminedClaims": claims,
        }))
    }

    fn submission_schema() -> Value {
        let lean_name = json!({
            "type": "string",
            "pattern": "^[A-Za-z_][A-Za-z0-9_']*(\\.[A-Za-z_][A-Za-z0-9_']*)*$",
        });
        json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["leanSource", "declarations"],
            "properties": {
                "leanSource": {"type": "string", "minLength": 1},
                "declarations": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "required": ["declaration", "role", "claimRefs"],
                        "properties": {
                            "declaration": lean_name,
                            "role": {"type": "string", "enum": DECLARATION_ROLES},
                            "claimRefs": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": false,
                                    "required": ["unitId", "claimId"],
                                    "properties": {
                                        "unitId": {"type": "string", "pattern": "^unit:"},
                                        "claimId": {"type": "string", "pattern": "^claim:"},
                                    },
                                },
                            },
                            "supportsDeclarations": {"type": "array", "items": lean_name},
                        },
                    },
                },
            },
        })
    }
}

impl ToolSet for TranslationTools {
    fn specs(&self) -> Vec<ToolSpec> {
        vec![
            ToolSpec::new(
            "submit_translation",
            "Submit the complete Lean 4 source for this group together with a declaration-to-claim \
             mapping. Structural validation runs immediately, and the source is then compiled; \
             both results come back in this same session, so correct and resubmit here.",
            Self::submission_schema(),
            ),
            ToolSpec::new(
                "report_underdetermined",
                "Report that these semantic artifacts do not determine a Lean formalization, \
                 naming each claim that is underdetermined and what is missing from it. Use this \
                 instead of guessing; the report is routed back to semantic extraction.",
                Self::underdetermined_schema(),
            ),
        ]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        if name == "report_underdetermined" {
            return match self.validate_underdetermined(input) {
                Ok(report) => {
                    self.underdetermined = Some(report);
                    ToolOutcome::Ok(json!({
                        "accepted": true,
                        "outcome": "UNDERDETERMINED",
                        "message": "Recorded. This group will be routed back to semantic extraction.",
                    }))
                }
                Err(diagnostics) => ToolOutcome::Ok(json!({
                    "accepted": false, "stage": "STRUCTURE", "diagnostics": diagnostics,
                })),
            };
        }
        if name != "submit_translation" {
            return ToolOutcome::Err(format!("unknown tool: {name}"));
        }
        match validate_submission(&self.scope, input) {
            Err(diagnostics) => ToolOutcome::Ok(json!({
                "accepted": false,
                "stage": "STRUCTURE",
                "diagnostics": diagnostics,
            })),
            Ok(accepted) => {
                let source = input["leanSource"].as_str().unwrap_or_default().to_string();
                self.pending = Some((source, accepted));
                // Deliberately not accepted yet: `after_tool_call` compiles it.
                ToolOutcome::Ok(json!({
                    "accepted": false,
                    "stage": "STRUCTURE",
                    "message": "Structure accepted; compiling.",
                }))
            }
        }
    }

    /// The deterministic step. This is the whole point of the rewrite: the
    /// compiler runs here, in the harness, between turns.
    fn after_tool_call(&mut self) -> Option<String> {
        let (source, accepted) = self.pending.take()?;
        let declarations = accepted["declarations"].clone();
        let shared_uses = accepted["sharedUses"].clone();
        if let Err(error) = std::fs::create_dir_all(&self.workspace) {
            return Some(format!("could not prepare the build workspace: {error}"));
        }
        let path = self.lean_path();
        if let Err(error) = std::fs::write(&path, &source) {
            return Some(format!("could not write {}: {error}", path.display()));
        }

        self.builds += 1;
        let dependencies: Vec<DependencyModule> = self.core.iter().cloned().collect();
        let result = run_build(&path, &dependencies, &self.lean_executable);
        let summary = result.summary(MAX_REPORTED_ERRORS);
        let passed = result.passed();
        let build_record = json!({
            "status": if passed { "PASS" } else { "FAIL" },
            "exitCode": result.exit_code,
            "leanVersion": result.lean_version,
            "durationMs": result.duration_ms,
            "attempt": self.builds,
            "diagnostics": result.diagnostics,
        });
        self.last_build = Some(result);

        if !passed {
            return Some(format!(
                "{summary}\nThe submission was not accepted. Correct the source and resubmit."
            ));
        }

        // Compiling is not enough. Ask the kernel what these declarations
        // actually rest on: a file full of `sorry` compiles perfectly and
        // asserts nothing, and a textual scan can always be evaded.
        let names: Vec<String> = declarations
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
            .iter()
            .filter_map(|item| item.get("declaration")?.as_str().map(str::to_string))
            .collect();
        let report = audit(&path, &dependencies, &names, &self.lean_executable);
        let audit_summary = report.summary();
        let sound = report.passed();
        let audit_record = serde_json::to_value(&report).unwrap_or_else(|_| json!({}));
        self.last_audit = Some(report);
        if !sound {
            return Some(format!(
                "{summary}\n{audit_summary}\nThe submission was not accepted. Correct the source and resubmit."
            ));
        }

        let mut manifest = self.scope.manifest(
            &declarations,
            &self.translator,
            &build_record,
            &shared_uses,
        );
        manifest["claimIndex"] = json!(claim_index(&declarations));
        manifest["axiomAudit"] = audit_record;
        self.accepted = Some(manifest);
        Some(format!("{summary}\n{audit_summary}\nTranslation accepted."))
    }

    fn finished(&self) -> bool {
        self.accepted.is_some() || self.underdetermined.is_some()
    }
}
