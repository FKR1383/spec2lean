//! What a module offers, as seen from a module that imports it.
//!
//! Handing a later task the earlier task's source turned out to be the wrong
//! shape. It has the information — the whole file was in the prompt — but
//! reading a definition and using it across a namespace boundary are different
//! problems, and a real run spent three compiles on the second one: a structure
//! treated as having a field it does not have, an accessor guessed at the wrong
//! qualification, an argument of the wrong type. Lean already knows all three
//! answers, so it is asked rather than inferred.

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::process::Command;

use crate::build::DependencyModule;
use crate::tempdir::TempDir;

/// `name : type` for every declaration the given modules export, elaborated by
/// Lean itself. An empty map means the probe could not run; callers fall back
/// to source rather than telling the model a module offers nothing.
pub fn signatures(
    modules: &[DependencyModule],
    lean_executable: &str,
) -> BTreeMap<String, String> {
    let mut empty = BTreeMap::new();
    if modules.is_empty() {
        return empty;
    }
    let Ok(temporary) = TempDir::new("spec2lean-signatures") else {
        return empty;
    };
    let root = temporary.path();
    let mut lean_path = root.as_os_str().to_owned();

    let mut declarations: Vec<String> = Vec::new();
    for module in modules {
        let Ok(text) = std::fs::read_to_string(&module.source) else {
            return empty;
        };
        declarations.extend(crate::declaration_names(&text));

        let relative: PathBuf = module
            .module
            .split('.')
            .collect::<PathBuf>()
            .with_extension("lean");
        let target = root.join(&relative);
        if let Some(parent) = target.parent()
            && std::fs::create_dir_all(parent).is_err()
        {
            return empty;
        }
        if std::fs::write(&target, &text).is_err() {
            return empty;
        }
        let built = Command::new(lean_executable)
            .args(["-R", &root.to_string_lossy()])
            .arg("-o")
            .arg(relative.with_extension("olean"))
            .arg(&relative)
            .current_dir(root)
            .env("LEAN_PATH", &lean_path)
            .output();
        match built {
            Ok(output) if output.status.success() => {}
            _ => return empty,
        }
    }
    if declarations.is_empty() {
        return empty;
    }
    if let Some(existing) = std::env::var_os("LEAN_PATH") {
        lean_path.push(":");
        lean_path.push(existing);
    }

    let mut probe = String::new();
    for module in modules {
        probe.push_str(&format!("import {}\n", module.module));
    }
    probe.push('\n');
    for declaration in &declarations {
        probe.push_str(&format!("#check @{declaration}\n"));
    }
    let probe_path = root.join("Spec2LeanSignatureProbe.lean");
    if std::fs::write(&probe_path, probe).is_err() {
        return empty;
    }
    let Ok(output) = Command::new(lean_executable)
        .args(["-R", &root.to_string_lossy()])
        .arg("Spec2LeanSignatureProbe.lean")
        .current_dir(root)
        .env("LEAN_PATH", &lean_path)
        .output()
    else {
        return empty;
    };
    let text = format!(
        "{}{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    empty = parse(&text, &declarations);
    empty
}

/// `#check` prints `name : type`, and wraps a long type onto further lines.
/// A continuation is anything that is not the start of the next answer.
fn parse(text: &str, declarations: &[String]) -> BTreeMap<String, String> {
    let mut found = BTreeMap::new();
    let mut current: Option<(String, String)> = None;
    for line in text.lines() {
        let start = declarations.iter().find(|name| {
            line.strip_prefix(name.as_str())
                .is_some_and(|rest| rest.starts_with(" :"))
        });
        match start {
            Some(name) => {
                if let Some((name, signature)) = current.take() {
                    found.insert(name, signature.trim().to_string());
                }
                let signature = line[name.len()..].trim_start().trim_start_matches(':').trim();
                current = Some((name.clone(), signature.to_string()));
            }
            None => {
                if let Some((_, signature)) = current.as_mut()
                    && !line.trim().is_empty()
                {
                    signature.push(' ');
                    signature.push_str(line.trim());
                }
            }
        }
    }
    if let Some((name, signature)) = current {
        found.insert(name, signature.trim().to_string());
    }
    found
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_signature_is_read_back_against_the_declaration_it_belongs_to() {
        let declarations = vec!["A.f".to_string(), "A.g".to_string()];
        let text = "A.f : Nat → Nat\nA.g : ∀ {y : Q}, S y → T\n";
        let found = parse(text, &declarations);
        assert_eq!(found["A.f"], "Nat → Nat");
        assert_eq!(found["A.g"], "∀ {y : Q}, S y → T");
    }

    #[test]
    fn a_type_wrapped_over_several_lines_is_one_signature() {
        let declarations = vec!["A.long".to_string()];
        let text = "A.long : ∀ {y : QueueIdentifier},\n  SQyTDBL y →\n  Result y\n";
        let found = parse(text, &declarations);
        assert_eq!(found["A.long"], "∀ {y : QueueIdentifier}, SQyTDBL y → Result y");
    }

    #[test]
    fn output_that_names_nothing_we_asked_about_yields_nothing() {
        // A probe that failed prints errors; reporting them as signatures would
        // tell the next task an API it cannot use.
        let declarations = vec!["A.f".to_string()];
        let found = parse("error: unknown identifier 'B.q'\n", &declarations);
        assert!(found.is_empty());
    }

    #[test]
    fn no_modules_means_no_probe_and_no_signatures() {
        assert!(signatures(&[], "lean").is_empty());
    }
}
