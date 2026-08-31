use std::path::PathBuf;

use serde_json::{Value, json};
use spec2lean_lean::{BuildResult, run_build};

use crate::scope::TranslationScope;
use crate::validation::{DECLARATION_ROLES, claim_index, validate_submission};
use harness::{ToolOutcome, ToolSet, ToolSpec};

const MAX_REPORTED_ERRORS: usize = 12;

/// Phase 5's capability surface, with the compiler wired into the loop.
///
/// `submit_translation` runs structural validation only. If that passes, the
/// harness itself compiles the source in `after_tools` and appends the
/// diagnostics to the same tool result, so a build failure arrives as a reply
/// to the submission rather than as a separate phase two processes later. The
/// session finishes only when the source is both structurally valid and builds.
pub struct TranslationTools {
    scope: TranslationScope,
    workspace: PathBuf,
    lean_executable: String,
    translator: Value,
    /// Set by `submit_translation`, consumed by `after_tools`.
    pending: Option<(String, Value)>,
    accepted: Option<Value>,
    last_build: Option<BuildResult>,
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
            pending: None,
            accepted: None,
            last_build: None,
            builds: 0,
        }
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
            Ok(declarations) => {
                let source = input["leanSource"].as_str().unwrap_or_default().to_string();
                self.pending = Some((source, declarations));
                // Deliberately not accepted yet: `after_tools` compiles it.
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
    fn after_tools(&mut self) -> Option<String> {
        let (source, declarations) = self.pending.take()?;
        if let Err(error) = std::fs::create_dir_all(&self.workspace) {
            return Some(format!("could not prepare the build workspace: {error}"));
        }
        let path = self.lean_path();
        if let Err(error) = std::fs::write(&path, &source) {
            return Some(format!("could not write {}: {error}", path.display()));
        }

        self.builds += 1;
        let result = run_build(&path, &[], &self.lean_executable);
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

        if passed {
            let mut manifest =
                self.scope
                    .manifest(&declarations, &self.translator, &build_record);
            manifest["claimIndex"] = json!(claim_index(&declarations));
            self.accepted = Some(manifest);
            Some(format!("{summary}\nTranslation accepted."))
        } else {
            Some(format!(
                "{summary}\nThe submission was not accepted. Correct the source and resubmit."
            ))
        }
    }

    fn finished(&self) -> bool {
        self.accepted.is_some()
    }
}
