//! The two tools a task has, and the deterministic work between them.

use std::path::PathBuf;

use serde_json::{Value, json};
use harness::{ToolOutcome, ToolSet, ToolSpec};
use spec2lean_evidence::ExposureLedger;
use spec2lean_lean::{AxiomAudit, BuildResult, DependencyModule, audit, run_build};
use spec2lean_specdb::SpecDb;
use spec2lean_translation::source;

use crate::embedder::Embedder;
use crate::task::Task;
use crate::validation::{Diagnostic, validate};

/// How many times one task may be compiled. A model that cannot make a file
/// build in this many attempts is not converging, and the transcript is more
/// useful than another round.
const MAX_BUILDS: u32 = 12;

pub struct TaskTools<'a> {
    db: &'a SpecDb,
    task: Task,
    units: Vec<Value>,
    ledger: ExposureLedger,
    workspace: PathBuf,
    lean_executable: String,
    /// Lean already accepted for the tasks this one depends on.
    dependencies: Vec<DependencyModule>,
    /// Set by `submit`, consumed by `after_tool_call`, which is what puts the
    /// compiler inside the conversation rather than after it.
    pending: Option<(String, Value)>,
    accepted: Option<Value>,
    last_build: Option<BuildResult>,
    last_audit: Option<AxiomAudit>,
    builds: u32,
    /// Absent when this index has no embeddings, or the model could not start.
    embedder: Option<Embedder>,
}

impl<'a> TaskTools<'a> {
    pub fn new(
        db: &'a SpecDb,
        task: Task,
        units: Vec<Value>,
        workspace: PathBuf,
        lean_executable: &str,
    ) -> Self {
        Self {
            db,
            task,
            units,
            ledger: ExposureLedger::default(),
            workspace,
            lean_executable: lean_executable.to_string(),
            dependencies: Vec::new(),
            pending: None,
            accepted: None,
            last_build: None,
            last_audit: None,
            builds: 0,
            embedder: None,
        }
    }

    pub fn with_embedder(mut self, embedder: Option<Embedder>) -> Self {
        self.embedder = embedder;
        self
    }

    /// Hand the embedder back so the next task can use it. The model is loaded
    /// once per run, not once per task, and the tool set is per task.
    pub fn take_embedder(&mut self) -> Option<Embedder> {
        self.embedder.take()
    }

    pub fn with_dependencies(mut self, dependencies: Vec<DependencyModule>) -> Self {
        self.dependencies = dependencies;
        self
    }

    pub fn task(&self) -> &Task {
        &self.task
    }

    pub fn units(&self) -> &[Value] {
        &self.units
    }

    pub fn accepted(&self) -> Option<&Value> {
        self.accepted.as_ref()
    }

    pub fn exposure_trace(&self) -> Value {
        self.ledger.to_json()
    }

    pub fn module_name(&self) -> String {
        format!("Spec2Lean.{}", self.task.name)
    }

    fn lean_path(&self) -> PathBuf {
        self.workspace.join(format!("{}.lean", self.task.name))
    }

    fn submission_schema() -> Value {
        json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["status"],
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["FORMALIZED", "UNDERDETERMINED"],
                    "description": "UNDERDETERMINED when the specification does not settle it."
                },
                "lean": {"type": "string", "description": "The whole Lean file."},
                "note": {
                    "type": "string",
                    "description": "For UNDERDETERMINED: precisely what the text leaves open."
                },
                "declarations": {
                    "type": "array",
                    "description": "Every declaration the file defines, with what it rests on.",
                    "items": {
                        "type": "object",
                        "additionalProperties": false,
                        "required": ["declaration", "cites"],
                        "properties": {
                            "declaration": {
                                "type": "string",
                                "description": "Fully qualified, exactly as defined."
                            },
                            "cites": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": false,
                                    "required": ["spanId", "quote"],
                                    "properties": {
                                        "spanId": {
                                            "type": "string",
                                            "description": "A span id `spec` returned to you."
                                        },
                                        "quote": {
                                            "type": "string",
                                            "description": "The words in that span being relied on."
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        })
    }
}

impl ToolSet for TaskTools<'_> {
    fn specs(&self) -> Vec<ToolSpec> {
        vec![
            ToolSpec::new("spec", crate::spec_tool::description(), crate::spec_tool::schema()),
            ToolSpec::new(
                "submit",
                "Submit the Lean file for this task, with every declaration's citations. It is \
                 validated, compiled, and audited before it is accepted; diagnostics come back \
                 for you to fix.",
                Self::submission_schema(),
            ),
        ]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        self.ledger.record_call(name, input);
        match name {
            "spec" => match crate::spec_tool::call(
                self.db,
                &mut self.ledger,
                self.embedder.as_mut(),
                input,
            ) {
                Ok(value) => ToolOutcome::Ok(value),
                Err(message) => ToolOutcome::Err(message),
            },
            "submit" => {
                if self.builds >= MAX_BUILDS {
                    return ToolOutcome::Err(format!(
                        "this task has already been compiled {MAX_BUILDS} times"
                    ));
                }
                match validate(self.db, &self.ledger, input, &self.task.unit_ids) {
                    Ok(accepted) => {
                        if accepted["status"] == "UNDERDETERMINED" {
                            self.accepted = Some(accepted.clone());
                            return ToolOutcome::Ok(json!({
                                "accepted": true,
                                "status": "UNDERDETERMINED",
                                "message": "Recorded. The specification does not determine this.",
                            }));
                        }
                        let lean = accepted["lean"].as_str().unwrap_or_default().to_string();
                        self.pending = Some((lean, accepted));
                        ToolOutcome::Ok(json!({
                            "accepted": true,
                            "message": "Validation passed; compiling.",
                        }))
                    }
                    Err(diagnostics) => ToolOutcome::Ok(json!({
                        "accepted": false,
                        "diagnostics": diagnostics.iter().map(Diagnostic::to_json)
                            .collect::<Vec<_>>(),
                    })),
                }
            }
            other => ToolOutcome::Err(format!("unknown tool: {other}")),
        }
    }

    fn finished(&self) -> bool {
        self.accepted.is_some()
    }

    /// Compile and audit the submission that this call produced, and report the
    /// outcome as part of that call's own result.
    fn after_tool_call(&mut self) -> Option<String> {
        let (lean, accepted) = self.pending.take()?;
        self.builds += 1;

        let path = self.lean_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Err(error) = std::fs::write(&path, &lean) {
            return Some(format!("could not write {}: {error}", path.display()));
        }

        let build = run_build(&path, &self.dependencies, &self.lean_executable);
        if !build.passed() {
            let summary = build.summary(8);
            self.last_build = Some(build);
            return Some(format!("BUILD FAILED\n{summary}\nFix the source and submit again."));
        }

        let declarations: Vec<String> = source::declarations(&lean).into_keys().collect();
        let audit = audit(&path, &self.dependencies, &declarations, &self.lean_executable);
        if !audit.passed() {
            let summary = audit.summary();
            self.last_build = Some(build);
            self.last_audit = Some(audit);
            return Some(format!(
                "BUILD PASSED, AXIOM AUDIT FAILED\n{summary}\nSubmit again without the hole."
            ));
        }

        let summary = format!(
            "BUILD PASSED and the kernel reports no unsound axiom in {} declaration(s). \
             This task is done.",
            declarations.len()
        );
        let mut record = accepted;
        record["module"] = json!(self.module_name());
        record["build"] = json!({"status": "PASS", "attempt": self.builds});
        record["axiomAudit"] = serde_json::to_value(&audit).unwrap_or(Value::Null);
        self.last_build = Some(build);
        self.last_audit = Some(audit);
        self.accepted = Some(record);
        Some(summary)
    }
}
