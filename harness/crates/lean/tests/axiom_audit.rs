//! The audit exists because textual scanning can be evaded. These tests use the
//! exact evasions that defeat the scanner.

use std::path::PathBuf;

use spec2lean_lean::{DependencyModule, audit};

fn lean_available() -> bool {
    std::process::Command::new("lean")
        .arg("--version")
        .output()
        .is_ok_and(|output| output.status.success())
}

struct Work(PathBuf);

impl Work {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!("s2l-axiom-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("dir");
        Self(path)
    }
    fn write(&self, name: &str, body: &str) -> PathBuf {
        let path = self.0.join(name);
        std::fs::write(&path, body).expect("write");
        path
    }
}

impl Drop for Work {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn an_honest_declaration_passes() {
    if !lean_available() {
        return;
    }
    let work = Work::new("clean");
    let file = work.write("Clean.lean", "def add (a b : Nat) : Nat := a + b\n");
    let report = audit(&file, &[], &["add".to_string()], "lean");
    assert!(report.passed(), "{}", report.summary());
    assert_eq!(report.declarations[0].axioms.len(), 0);
    assert!(report.summary().contains("axiom audit: PASS"));
}

/// The raw-string evasion: Lean accepts this and the text scanner blanks the
/// axiom, but the kernel knows.
#[test]
fn an_axiom_hidden_behind_a_raw_string_is_caught() {
    if !lean_available() {
        return;
    }
    let work = Work::new("rawstring");
    let file = work.write(
        "Hidden.lean",
        "def marker := r#\"foo\"bar\"#\naxiom hidden : False\n-- \"\ntheorem required : False := hidden\n",
    );
    let report = audit(&file, &[], &["required".to_string()], "lean");
    assert!(!report.passed(), "{}", report.summary());
    assert_eq!(report.declarations[0].unsound, vec!["hidden".to_string()]);
    assert!(report.summary().contains("introduces an axiom of its own"), "{}", report.summary());
}

/// The interpolation evasion: `sorry` inside `s!"{...}"`.
#[test]
fn a_sorry_hidden_in_string_interpolation_is_caught() {
    if !lean_available() {
        return;
    }
    let work = Work::new("interp");
    let file = work.write("Interp.lean", "def x := s!\"{(sorry : Nat)}\"\n");
    let report = audit(&file, &[], &["x".to_string()], "lean");
    assert!(!report.passed(), "{}", report.summary());
    assert_eq!(report.declarations[0].unsound, vec!["sorryAx".to_string()]);
    assert!(report.summary().contains("unproved hole"), "{}", report.summary());
}

#[test]
fn the_standard_classical_foundation_is_allowed() {
    if !lean_available() {
        return;
    }
    let work = Work::new("classical");
    // `Classical.em` rests on Classical.choice, propext and Quot.sound: ordinary
    // mathematics, not an assumption this formalization introduced.
    let file = work.write(
        "Classical.lean",
        "open Classical in\ntheorem decide_it (p : Prop) : p ∨ ¬p := em p\n",
    );
    let report = audit(&file, &[], &["decide_it".to_string()], "lean");
    assert!(report.passed(), "{}", report.summary());
    assert!(!report.declarations[0].axioms.is_empty());
}

#[test]
fn a_declaration_that_does_not_exist_under_its_manifest_name_is_reported() {
    if !lean_available() {
        return;
    }
    let work = Work::new("missing");
    let file = work.write("M.lean", "namespace N\ndef x := 0\nend N\n");
    // The manifest claims `x`, but Lean elaborated `N.x`.
    let report = audit(&file, &[], &["x".to_string()], "lean");
    assert!(!report.passed(), "{}", report.summary());
    assert_eq!(report.unreported, vec!["x".to_string()]);
    assert!(report.summary().contains("may not exist under that name"));

    let report = audit(&file, &[], &["N.x".to_string()], "lean");
    assert!(report.passed(), "{}", report.summary());
}

#[test]
fn the_audit_sees_through_an_imported_dependency() {
    if !lean_available() {
        return;
    }
    let work = Work::new("deps");
    // The hole is in the core, and the unit merely uses it.
    let core = work.write("core.lean", "namespace Core\ndef broken : Nat := sorry\nend Core\n");
    let unit = work.write(
        "Unit.lean",
        "import Spec.Core\nopen Core\ndef uses : Nat := broken + 1\n",
    );
    let report = audit(
        &unit,
        &[DependencyModule { module: "Spec.Core".into(), source: core }],
        &["uses".to_string()],
        "lean",
    );
    assert!(!report.passed(), "{}", report.summary());
    assert_eq!(report.declarations[0].unsound, vec!["sorryAx".to_string()]);
}
