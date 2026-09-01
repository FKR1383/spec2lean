//! Ask Lean what a declaration actually depends on.
//!
//! Textual scanning can always be evaded — a raw string, an interpolated
//! expression, an unusual layout. `#print axioms` cannot: it reports the
//! kernel's own view of what a declaration rests on. This is the check that
//! decides whether a formalization asserts anything.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Serialize;

use crate::build::DependencyModule;
use crate::tempdir::TempDir;

/// Axioms that are part of Lean's standard classical foundation. Depending on
/// these is ordinary mathematics; depending on anything else means the
/// formalization introduced an assumption of its own.
pub const FOUNDATIONAL: &[&str] = &["propext", "Classical.choice", "Quot.sound"];

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeclarationAxioms {
    pub declaration: String,
    pub axioms: Vec<String>,
    /// Axioms outside the foundational set — including `sorryAx`.
    pub unsound: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct AxiomAudit {
    pub status: &'static str,
    pub declarations: Vec<DeclarationAxioms>,
    /// Declarations `#print axioms` said nothing about, which usually means the
    /// name in the manifest is not the name Lean elaborated.
    pub unreported: Vec<String>,
    pub notes: Vec<String>,
}

impl AxiomAudit {
    pub fn passed(&self) -> bool {
        self.status == "PASS"
    }

    pub fn summary(&self) -> String {
        if self.passed() {
            return format!(
                "axiom audit: PASS ({} declaration(s) depend only on the standard foundation)",
                self.declarations.len()
            );
        }
        let mut lines = vec!["axiom audit: FAIL".to_string()];
        for item in self.declarations.iter().filter(|item| !item.unsound.is_empty()) {
            let reason = if item.unsound.iter().any(|name| name == "sorryAx") {
                "contains an unproved hole (sorry)"
            } else {
                "introduces an axiom of its own"
            };
            lines.push(format!(
                "{} {reason}: depends on {}",
                item.declaration,
                item.unsound.join(", ")
            ));
        }
        for name in &self.unreported {
            lines.push(format!(
                "{name}: Lean reported no axiom information; the declaration may not exist under that name"
            ));
        }
        lines.extend(self.notes.iter().cloned());
        lines.join("\n")
    }
}

/// `'name' depends on axioms: [a, b]` or `'name' does not depend on any axioms`.
fn parse_line(line: &str) -> Option<(String, Vec<String>)> {
    let rest = line.trim().strip_prefix('\'')?;
    let (name, rest) = rest.split_once('\'')?;
    let rest = rest.trim_start();
    if rest.starts_with("does not depend on any axioms") {
        return Some((name.to_string(), Vec::new()));
    }
    let list = rest.strip_prefix("depends on axioms:")?.trim();
    let list = list.strip_prefix('[')?.strip_suffix(']')?;
    Some((
        name.to_string(),
        list.split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_string)
            .collect(),
    ))
}

/// The module the audited source is staged under.
const AUDIT_MODULE: &str = "Spec2LeanAudit.Target";

/// Report the axiom dependencies of every named declaration.
///
/// The audited source is compiled to a `.olean`, and the `#print axioms`
/// queries then run from a *separate* file that imports it. That separation is
/// the point: appending the queries to the source itself lets the source write
/// into the same output stream, and a line such as
///
/// ```lean
/// #eval IO.println "'x' does not depend on any axioms"
/// ```
///
/// is indistinguishable from Lean's own answer. Probing across an import
/// removes the channel — an imported module's `#eval` does not run — and the
/// probe's exit status is checked, so a query that fails to elaborate can never
/// be read as a clean result.
pub fn audit(
    lean_file: &Path,
    dependencies: &[DependencyModule],
    declarations: &[String],
    lean_executable: &str,
) -> AxiomAudit {
    let fail = |note: String| AxiomAudit {
        status: "FAIL",
        declarations: Vec::new(),
        unreported: declarations.to_vec(),
        notes: vec![note],
    };
    if declarations.is_empty() {
        return AxiomAudit {
            status: "PASS",
            declarations: Vec::new(),
            unreported: Vec::new(),
            notes: vec!["no declarations to audit".into()],
        };
    }
    let Ok(source) = std::fs::read_to_string(lean_file) else {
        return fail(format!("could not read {}", lean_file.display()));
    };
    let Ok(temporary) = TempDir::new("spec2lean-axiom-audit") else {
        return fail("could not create an audit directory".into());
    };
    let root = temporary.path();
    let mut lean_path = root.as_os_str().to_owned();

    // Compile every module the audited source imports, then the source itself.
    let mut modules: Vec<(String, String)> = dependencies
        .iter()
        .map(|dependency| (dependency.module.clone(), String::new()))
        .collect();
    for (index, dependency) in dependencies.iter().enumerate() {
        match std::fs::read_to_string(&dependency.source) {
            Ok(text) => modules[index].1 = text,
            Err(_) => {
                return fail(format!(
                    "could not read {} for the audit",
                    dependency.source.display()
                ));
            }
        }
    }
    modules.push((AUDIT_MODULE.to_string(), source));

    for (module, text) in &modules {
        let relative: PathBuf = module.split('.').collect::<PathBuf>().with_extension("lean");
        let target = root.join(&relative);
        if let Some(parent) = target.parent()
            && std::fs::create_dir_all(parent).is_err()
        {
            return fail("could not stage a module for the audit".into());
        }
        if std::fs::write(&target, text).is_err() {
            return fail(format!("could not stage {module} for the audit"));
        }
        let built = Command::new(lean_executable)
            .args(["-R", &root.to_string_lossy()])
            .arg("-o")
            .arg(relative.with_extension("olean"))
            .arg(&relative)
            .current_dir(root)
            .env("LEAN_PATH", &lean_path)
            .output();
        // Whatever this compilation prints is ignored: it is the audited
        // source's own output, and the audit must not read it.
        match built {
            Ok(output) if output.status.success() => {}
            Ok(output) => {
                return fail(format!(
                    "{module} did not compile during the audit: {}",
                    crate::build::first_error(&output.stdout, &output.stderr)
                ));
            }
            Err(error) => return fail(format!("could not run Lean for the audit: {error}")),
        }
    }
    if let Some(existing) = std::env::var_os("LEAN_PATH") {
        lean_path.push(":");
        lean_path.push(existing);
    }

    // The probe contains nothing but an import and the queries.
    let mut probe = format!("import {AUDIT_MODULE}\n");
    for declaration in declarations {
        probe.push_str(&format!("#print axioms {declaration}\n"));
    }
    let probe_path = root.join("Spec2LeanAuditProbe.lean");
    if std::fs::write(&probe_path, probe).is_err() {
        return fail("could not write the audit probe".into());
    }
    let output = Command::new(lean_executable)
        .args(["-R", &root.to_string_lossy()])
        .arg("Spec2LeanAuditProbe.lean")
        .current_dir(root)
        .env("LEAN_PATH", &lean_path)
        .output();
    let Ok(output) = output else {
        return fail("could not run the axiom audit".into());
    };
    let text = format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    // A probe that did not elaborate cleanly has told us nothing, whatever it
    // printed on the way.
    if !output.status.success() {
        return fail(format!(
            "the axiom probe did not elaborate: {}",
            error_line(&text)
        ));
    }

    let mut reported: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for line in text.lines() {
        if let Some((name, axioms)) = parse_line(line) {
            reported.insert(name, axioms);
        }
    }

    let mut results = Vec::new();
    let mut unreported = Vec::new();
    for declaration in declarations {
        match reported.get(declaration) {
            None => unreported.push(declaration.clone()),
            Some(axioms) => {
                let unsound: Vec<String> = axioms
                    .iter()
                    .filter(|name| !FOUNDATIONAL.contains(&name.as_str()))
                    .cloned()
                    .collect();
                results.push(DeclarationAxioms {
                    declaration: declaration.clone(),
                    axioms: axioms.clone(),
                    unsound,
                });
            }
        }
    }
    let sound = results.iter().all(|item| item.unsound.is_empty()) && unreported.is_empty();
    AxiomAudit {
        status: if sound { "PASS" } else { "FAIL" },
        declarations: results,
        unreported,
        notes: Vec::new(),
    }
}

/// The first line of output that looks like a diagnostic, for error messages.
pub(crate) fn error_line(text: &str) -> String {
    text.lines()
        .find(|line| line.contains("error"))
        .unwrap_or_else(|| text.lines().next().unwrap_or("no output"))
        .trim()
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_both_forms_lean_emits() {
        assert_eq!(
            parse_line("'clean' does not depend on any axioms"),
            Some(("clean".to_string(), vec![]))
        );
        assert_eq!(
            parse_line("'x' depends on axioms: [sorryAx]"),
            Some(("x".to_string(), vec!["sorryAx".to_string()]))
        );
        assert_eq!(
            parse_line("'N.f' depends on axioms: [propext, Classical.choice, Quot.sound]"),
            Some((
                "N.f".to_string(),
                vec!["propext".into(), "Classical.choice".into(), "Quot.sound".into()]
            ))
        );
        assert_eq!(parse_line("some other output"), None);
    }
}
