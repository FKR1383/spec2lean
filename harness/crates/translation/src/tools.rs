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
        vec![ToolSpec::new(
            "submit_translation",
            "Submit the complete Lean 4 source for this group together with a declaration-to-claim \
             mapping. Structural validation runs immediately, and the source is then compiled; \
             both results come back in this same session, so correct and resubmit here.",
            Self::submission_schema(),
        )]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
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
        self.accepted.is_some()
    }
}
