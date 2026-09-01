use std::path::PathBuf;

use serde_json::{Value, json};
use spec2lean_lean::{AxiomAudit, BuildResult, DependencyModule, audit, run_build};

use crate::identity::{core_namespace, core_run_id, json_hash, text_hash};
use crate::requirements::SharedRequirement;
use crate::validation::validate_submission;
use harness::{ToolOutcome, ToolSet, ToolSpec};

const MAX_REPORTED_ERRORS: usize = 12;

/// A core that has been validated, compiled, and frozen.
#[derive(Debug, Clone)]
pub struct FrozenCore {
    pub core_run_id: String,
    pub lean_module: String,
    pub source: String,
    pub source_hash: String,
    pub manifest_hash: String,
    pub manifest: Value,
}

impl FrozenCore {
    /// The four fields a translation manifest records to pin its core.
    pub fn reference(&self) -> Value {
        json!({
            "coreRunId": self.core_run_id,
            "manifestHash": self.manifest_hash,
            "sourceHash": self.source_hash,
            "leanModule": self.lean_module,
        })
    }

    /// Stage this core as a compile dependency for a group translation.
    pub fn dependency(&self, source_path: PathBuf) -> DependencyModule {
        DependencyModule {
            module: self.lean_module.clone(),
            source: source_path,
        }
    }
}

/// The materializer's capability surface: submit one core, get it compiled.
pub struct SharedCoreTools {
    requirements: Vec<SharedRequirement>,
    language: String,
    version: String,
    source_database_digest: String,
    generator: Value,
    workspace: PathBuf,
    lean_executable: String,
    pending: Option<crate::validation::AcceptedCore>,
    frozen: Option<FrozenCore>,
    last_build: Option<BuildResult>,
    last_audit: Option<AxiomAudit>,
    builds: u32,
}

impl SharedCoreTools {
    pub fn new(
        requirements: Vec<SharedRequirement>,
        language: impl Into<String>,
        version: impl Into<String>,
        source_database_digest: impl Into<String>,
        generator: Value,
        workspace: PathBuf,
        lean_executable: impl Into<String>,
    ) -> Self {
        Self {
            requirements,
            language: language.into(),
            version: version.into(),
            source_database_digest: source_database_digest.into(),
            generator,
            workspace,
            lean_executable: lean_executable.into(),
            pending: None,
            frozen: None,
            last_build: None,
            last_audit: None,
            builds: 0,
        }
    }

    pub fn requirements(&self) -> &[SharedRequirement] {
        &self.requirements
    }

    pub fn frozen(&self) -> Option<&FrozenCore> {
        self.frozen.as_ref()
    }

    pub fn build_count(&self) -> u32 {
        self.builds
    }

    pub fn last_build(&self) -> Option<&BuildResult> {
        self.last_build.as_ref()
    }

    pub fn last_audit(&self) -> Option<&AxiomAudit> {
        self.last_audit.as_ref()
    }

    fn submission_schema() -> Value {
        let lean_name = json!({
            "type": "string",
            "pattern": "^[A-Za-z_][A-Za-z0-9_']*(\\.[A-Za-z_][A-Za-z0-9_']*)*$",
        });
        json!({
            "type": "object",
            "additionalProperties": false,
            "required": ["leanSource", "concepts", "declarations"],
            "properties": {
                "leanSource": {"type": "string", "minLength": 1},
                "concepts": {
                    "type": "array", "minItems": 1,
                    "items": {
                        "type": "object", "additionalProperties": false,
                        "required": ["dependencyId", "leanDeclarations"],
                        "properties": {
                            "dependencyId": {"type": "string", "pattern": "^shared:"},
                            "leanDeclarations": {
                                "type": "array", "minItems": 1, "uniqueItems": true,
                                "items": lean_name,
                            },
                        },
                    },
                },
                "declarations": {
                    "type": "array", "minItems": 1,
                    "items": {
                        "type": "object", "additionalProperties": false,
                        "required": ["declaration", "claimRefs"],
                        "properties": {
                            "declaration": lean_name,
                            "role": {"type": "string", "minLength": 1},
                            "claimRefs": {
                                "type": "array", "minItems": 1,
                                "items": {
                                    "type": "object", "additionalProperties": false,
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

impl ToolSet for SharedCoreTools {
    fn specs(&self) -> Vec<ToolSpec> {
        vec![ToolSpec::new(
            "submit_core",
            "Submit one complete Lean 4 shared core: the source, the declarations that represent \
             each required shared concept, and the claim each declaration comes from. Structural \
             validation runs immediately and the source is then compiled; both results come back \
             in this same session.",
            Self::submission_schema(),
        )]
    }

    fn call(&mut self, name: &str, input: &Value) -> ToolOutcome {
        if name != "submit_core" {
            return ToolOutcome::Err(format!("unknown tool: {name}"));
        }
        match validate_submission(&self.requirements, input) {
            Err(diagnostics) => ToolOutcome::Ok(json!({
                "accepted": false, "stage": "STRUCTURE", "diagnostics": diagnostics,
            })),
            Ok(accepted) => {
                self.pending = Some(accepted);
                ToolOutcome::Ok(json!({
                    "accepted": false, "stage": "STRUCTURE",
                    "message": "Structure accepted; compiling.",
                }))
            }
        }
    }

    /// Compile the core on its own. A core that does not build cannot be
    /// frozen: every later group would import a module that fails.
    fn after_tool_call(&mut self) -> Option<String> {
        let accepted = self.pending.take()?;

        // The module name depends on the content, so it can only be computed
        // once the content exists.
        let lean_module = core_namespace(
            &self.language,
            &self.version,
            &self.source_database_digest,
            &accepted.lean_source,
            &accepted.concepts,
            &accepted.declarations,
        );
        let relative: PathBuf = lean_module
            .split('.')
            .collect::<PathBuf>()
            .with_extension("lean");
        let path = self.workspace.join(&relative);
        if let Some(parent) = path.parent()
            && let Err(error) = std::fs::create_dir_all(parent)
        {
            return Some(format!("could not prepare the core workspace: {error}"));
        }
        if let Err(error) = std::fs::write(&path, &accepted.lean_source) {
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
        if !passed {
            return Some(format!(
                "{summary}\nThe core was not frozen. Correct the source and resubmit."
            ));
        }

        // A core is imported by every group that needs these concepts, so an
        // unsound one poisons all of them. Ask the kernel before freezing.
        let names: Vec<String> = accepted
            .declarations
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
            .iter()
            .filter_map(|item| item.get("declaration")?.as_str().map(str::to_string))
            .collect();
        let report = audit(&path, &[], &names, &self.lean_executable);
        let audit_summary = report.summary();
        let sound = report.passed();
        let audit_record = serde_json::to_value(&report).unwrap_or_else(|_| json!({}));
        self.last_audit = Some(report);
        if !sound {
            return Some(format!(
                "{summary}\n{audit_summary}\nThe core was not frozen. Correct the source and resubmit."
            ));
        }

        let source_hash = text_hash(&accepted.lean_source);
        let generator_provider = self.generator["provider"].as_str().unwrap_or("unknown");
        let generator_model = self.generator["model"].as_str().unwrap_or("unknown");
        let run_id = core_run_id(
            &self.language,
            &self.version,
            &self.source_database_digest,
            generator_provider,
            generator_model,
            &source_hash,
            &accepted.concepts,
            &accepted.declarations,
        );
        let mut manifest = json!({
            "schemaVersion": crate::identity::CORE_SCHEMA_VERSION,
            "phase": "SHARED_CORE_MATERIALIZER",
            "language": self.language,
            "version": self.version,
            "sourceDatabaseDigest": self.source_database_digest,
            "coreRunId": run_id,
            "leanModule": lean_module,
            "sourceHash": source_hash,
            "generator": self.generator,
            "target": {"language": "Lean", "version": "4"},
            "build": build_record,
            "axiomAudit": audit_record,
            "concepts": accepted.concepts,
            "declarations": accepted.declarations,
        });
        // The manifest hash covers the manifest without itself.
        let manifest_hash = json_hash(&manifest);
        manifest["manifestHash"] = json!(manifest_hash);

        let concept_count = accepted.concepts.as_array().map_or(0, Vec::len);
        self.frozen = Some(FrozenCore {
            core_run_id: run_id,
            lean_module: manifest["leanModule"].as_str().unwrap_or_default().to_string(),
            source: accepted.lean_source,
            source_hash: manifest["sourceHash"].as_str().unwrap_or_default().to_string(),
            manifest_hash,
            manifest,
        });
        Some(format!(
            "{summary}\n{audit_summary}\nCore frozen: {concept_count} shared concept(s) represented."
        ))
    }

    fn finished(&self) -> bool {
        self.frozen.is_some()
    }
}
