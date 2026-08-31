//! Integration tests against the real Lean toolchain.
//!
//! Skipped automatically when `lean` is absent, so the suite still runs on a
//! machine without it.

use std::path::{Path, PathBuf};

use spec2lean_lean::{BuildStatus, DependencyModule, Severity, run_build};

fn lean_available() -> bool {
    std::process::Command::new("lean")
        .arg("--version")
        .output()
        .is_ok_and(|output| output.status.success())
}

struct Work(PathBuf);

impl Work {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!("s2l-lean-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("scratch directory");
        Self(path)
    }

    fn write(&self, name: &str, content: &str) -> PathBuf {
        let path = self.0.join(name);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).expect("parent directory");
        }
        std::fs::write(&path, content).expect("write source");
        path
    }
}

impl Drop for Work {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn a_well_formed_file_passes_and_reports_a_version() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("pass");
    let source = work.write("Ok.lean", "def f (n : Nat) : Nat := n + 1\n");
    let result = run_build(&source, &[], "lean");

    assert_eq!(result.status, BuildStatus::Pass, "{result:?}");
    assert_eq!(result.exit_code, 0);
    assert!(result.lean_version.as_deref().is_some_and(|v| v.contains("Lean")));
    assert!(result.errors().is_empty());
    assert_eq!(result.summary(5), "lean build: PASS");
}

#[test]
fn a_type_error_is_located_and_summarised() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("fail");
    let source = work.write("Bad.lean", "def g : Nat := \"oops\"\n");
    let result = run_build(&source, &[], "lean");

    assert_eq!(result.status, BuildStatus::Fail);
    assert_ne!(result.exit_code, 0);
    let errors = result.errors();
    assert!(!errors.is_empty(), "{result:?}");

    let first = errors[0];
    assert_eq!(first.severity, Severity::Error);
    assert_eq!(first.file.as_deref(), Some("Bad.lean"));
    assert_eq!(first.line, Some(1));
    // Lean's explanation follows on continuation lines and must survive.
    assert!(first.message.contains("String"), "{}", first.message);
    assert!(first.message.contains("Nat"), "{}", first.message);

    // The summary is what a repair loop would be handed.
    let summary = result.summary(5);
    assert!(summary.starts_with("lean build: FAIL"), "{summary}");
    assert!(summary.contains("Bad.lean:1:"), "{summary}");
}

#[test]
fn a_unit_compiles_against_a_staged_dependency_module() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("deps");
    // The shared core a translated unit imports.
    let core = work.write(
        "core.lean",
        "namespace Spec\ndef width : Nat := 32\nend Spec\n",
    );
    let unit = work.write(
        "Unit.lean",
        "import Spec.Core\nopen Spec\ndef doubled : Nat := width + width\n",
    );

    let result = run_build(
        &unit,
        &[DependencyModule {
            module: "Spec.Core".into(),
            source: core,
        }],
        "lean",
    );
    assert_eq!(result.status, BuildStatus::Pass, "{result:?}");
}

#[test]
fn a_dependency_that_fails_to_compile_stops_before_the_unit() {
    if !lean_available() {
        eprintln!("skipping: lean is not on PATH");
        return;
    }
    let work = Work::new("baddep");
    let core = work.write("core.lean", "namespace Spec\ndef width : Nat := \"32\"\nend Spec\n");
    let unit = work.write("Unit.lean", "import Spec.Core\ndef doubled : Nat := 1\n");

    let result = run_build(
        &unit,
        &[DependencyModule {
            module: "Spec.Core".into(),
            source: core,
        }],
        "lean",
    );
    assert_eq!(result.status, BuildStatus::Fail);
    // The diagnostics are the core's, not a confusing import failure in the unit.
    let errors = result.errors();
    assert!(
        errors.iter().any(|item| item
            .file
            .as_deref()
            .is_some_and(|file| file.contains("Core"))),
        "{result:?}"
    );
}

#[test]
fn a_malformed_or_duplicated_module_name_is_refused_without_running_lean() {
    let work = Work::new("badmodule");
    let core = work.write("core.lean", "def x : Nat := 1\n");
    let unit = work.write("Unit.lean", "def y : Nat := 1\n");

    for module in ["", "9bad", "Spec..Core", "Spec/Core"] {
        let result = run_build(
            &unit,
            &[DependencyModule {
                module: module.into(),
                source: core.clone(),
            }],
            "lean",
        );
        assert_eq!(result.status, BuildStatus::Fail, "accepted {module:?}");
        assert!(
            result.diagnostics[0].message.contains("invalid or duplicate"),
            "{module:?}: {result:?}"
        );
    }

    let duplicate = DependencyModule {
        module: "Spec.Core".into(),
        source: core.clone(),
    };
    let result = run_build(&unit, &[duplicate.clone(), duplicate], "lean");
    assert_eq!(result.status, BuildStatus::Fail);
    assert!(result.diagnostics[0].message.contains("invalid or duplicate"));
}

#[test]
fn a_missing_toolchain_fails_cleanly_rather_than_panicking() {
    let work = Work::new("notoolchain");
    let unit = work.write("Unit.lean", "def y : Nat := 1\n");
    let result = run_build(&unit, &[], "lean-that-does-not-exist");

    assert_eq!(result.status, BuildStatus::Fail);
    assert_eq!(result.exit_code, 127);
    assert!(result.diagnostics[0].message.contains("was not found"));
    assert!(result.lean_version.is_none());
}

#[test]
fn a_missing_dependency_source_is_reported_by_path() {
    let work = Work::new("missingdep");
    let unit = work.write("Unit.lean", "def y : Nat := 1\n");
    let result = run_build(
        &unit,
        &[DependencyModule {
            module: "Spec.Core".into(),
            source: Path::new("/nonexistent/core.lean").to_path_buf(),
        }],
        "lean",
    );
    assert_eq!(result.status, BuildStatus::Fail);
    assert!(result.diagnostics[0].message.contains("/nonexistent/core.lean"));
}
