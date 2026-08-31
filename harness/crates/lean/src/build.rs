use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Instant;

use serde::Serialize;

use crate::diagnostic::{Diagnostic, Severity, parse_stream};
use crate::tempdir::TempDir;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum BuildStatus {
    Pass,
    Fail,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BuildResult {
    pub status: BuildStatus,
    pub exit_code: i32,
    pub lean_version: Option<String>,
    pub duration_ms: u64,
    pub diagnostics: Vec<Diagnostic>,
}

impl BuildResult {
    pub fn passed(&self) -> bool {
        self.status == BuildStatus::Pass
    }

    /// Only the errors, which is what a repair loop should be shown.
    pub fn errors(&self) -> Vec<&Diagnostic> {
        self.diagnostics
            .iter()
            .filter(|item| item.severity == Severity::Error)
            .collect()
    }

    /// A compact rendering for feeding straight back to a model mid-session.
    pub fn summary(&self, max_diagnostics: usize) -> String {
        if self.passed() {
            return "lean build: PASS".to_string();
        }
        let errors = self.errors();
        let mut lines = vec![format!(
            "lean build: FAIL (exit {}, {} error{})",
            self.exit_code,
            errors.len(),
            if errors.len() == 1 { "" } else { "s" }
        )];
        for item in errors.iter().take(max_diagnostics) {
            let location = match (&item.file, item.line, item.column) {
                (Some(file), Some(line), Some(column)) => format!("{file}:{line}:{column}"),
                _ => "<no location>".to_string(),
            };
            lines.push(format!("{location}: {}", item.message));
        }
        if errors.len() > max_diagnostics {
            lines.push(format!(
                "… {} further error(s) omitted",
                errors.len() - max_diagnostics
            ));
        }
        lines.join("\n")
    }

    fn failure(exit_code: i32, lean_version: Option<String>, message: String) -> Self {
        Self {
            status: BuildStatus::Fail,
            exit_code,
            lean_version,
            duration_ms: 0,
            diagnostics: vec![Diagnostic {
                stream: "stderr",
                severity: Severity::Error,
                file: None,
                line: None,
                column: None,
                message,
            }],
        }
    }
}

/// A generated module this unit imports, staged so Lean can resolve it.
#[derive(Debug, Clone)]
pub struct DependencyModule {
    pub module: String,
    pub source: PathBuf,
}

fn valid_module(name: &str) -> bool {
    !name.is_empty()
        && name.split('.').all(|segment| {
            let mut characters = segment.chars();
            characters
                .next()
                .is_some_and(|first| first.is_ascii_alphabetic() || first == '_')
                && characters
                    .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '\'')
        })
}

fn lean_version(executable: &str) -> Option<String> {
    let output = Command::new(executable).arg("--version").output().ok()?;
    let text = if output.stdout.is_empty() {
        String::from_utf8_lossy(&output.stderr)
    } else {
        String::from_utf8_lossy(&output.stdout)
    };
    text.trim().lines().next().map(str::to_string)
}

fn resolve(executable: &str) -> Option<String> {
    let path = Path::new(executable);
    if path.is_absolute() {
        return path.is_file().then(|| executable.to_string());
    }
    // Not on an absolute path: let the OS resolve it, and confirm it runs.
    Command::new(executable)
        .arg("--version")
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|_| executable.to_string())
}

/// Compile one Lean file, optionally staging generated dependency modules.
///
/// With no dependencies this is a single `lean <file>` in the file's own
/// directory, so diagnostics point at the published translation. With
/// dependencies, sources are staged into a scratch tree, each is compiled to an
/// `.olean` in turn, and the unit is compiled against them.
pub fn run_build(
    lean_file: &Path,
    dependencies: &[DependencyModule],
    lean_executable: &str,
) -> BuildResult {
    let Some(executable) = resolve(lean_executable) else {
        return BuildResult::failure(
            127,
            None,
            format!("Lean executable was not found: {lean_executable}"),
        );
    };
    let version = lean_version(&executable);
    let started = Instant::now();

    let elapsed = |started: Instant| started.elapsed().as_millis() as u64;

    if dependencies.is_empty() {
        let Some(directory) = lean_file.parent() else {
            return BuildResult::failure(
                2,
                version,
                format!("Lean source has no parent directory: {}", lean_file.display()),
            );
        };
        let name = lean_file.file_name().unwrap_or_default();
        let output = match Command::new(&executable)
            .arg(name)
            .current_dir(directory)
            .output()
        {
            Ok(output) => output,
            Err(error) => {
                return BuildResult::failure(2, version, format!("could not run Lean: {error}"));
            }
        };
        let exit_code = output.status.code().unwrap_or(-1);
        let mut diagnostics = parse_stream("stdout", &String::from_utf8_lossy(&output.stdout));
        diagnostics.extend(parse_stream(
            "stderr",
            &String::from_utf8_lossy(&output.stderr),
        ));
        return BuildResult {
            status: if exit_code == 0 {
                BuildStatus::Pass
            } else {
                BuildStatus::Fail
            },
            exit_code,
            lean_version: version,
            duration_ms: elapsed(started),
            diagnostics,
        };
    }

    let temporary = match TempDir::new("spec2lean-check-build") {
        Ok(temporary) => temporary,
        Err(error) => {
            return BuildResult::failure(2, version, format!("could not create a build directory: {error}"));
        }
    };
    let root = temporary.path();

    let mut seen: Vec<&str> = Vec::new();
    let mut staged: Vec<(PathBuf, PathBuf)> = Vec::new();
    for dependency in dependencies {
        if !valid_module(&dependency.module) || seen.contains(&dependency.module.as_str()) {
            return BuildResult::failure(
                2,
                version,
                format!(
                    "invalid or duplicate Lean dependency module: {}",
                    dependency.module
                ),
            );
        }
        if !dependency.source.is_file() {
            return BuildResult::failure(
                2,
                version,
                format!(
                    "Lean dependency source does not exist: {}",
                    dependency.source.display()
                ),
            );
        }
        seen.push(&dependency.module);
        let relative: PathBuf = dependency
            .module
            .split('.')
            .collect::<PathBuf>()
            .with_extension("lean");
        let target = root.join(&relative);
        if let Some(parent) = target.parent()
            && let Err(error) = std::fs::create_dir_all(parent)
        {
            return BuildResult::failure(2, version, format!("could not stage a dependency: {error}"));
        }
        if let Err(error) = std::fs::copy(&dependency.source, &target) {
            return BuildResult::failure(2, version, format!("could not stage a dependency: {error}"));
        }
        staged.push((relative.clone(), relative.with_extension("olean")));
    }

    let unit_name = lean_file.file_name().unwrap_or_default().to_owned();
    if let Err(error) = std::fs::copy(lean_file, root.join(&unit_name)) {
        return BuildResult::failure(2, version, format!("could not stage the unit: {error}"));
    }

    // LEAN_PATH lets the staged .olean files resolve as imports.
    let lean_path = match std::env::var_os("LEAN_PATH") {
        Some(existing) => {
            let mut combined = root.as_os_str().to_owned();
            combined.push(":");
            combined.push(existing);
            combined
        }
        None => root.as_os_str().to_owned(),
    };

    let mut diagnostics = Vec::new();
    let mut exit_code = 0;
    for (source, olean) in &staged {
        let output = Command::new(&executable)
            .args(["-R", &root.to_string_lossy()])
            .arg("-o")
            .arg(olean)
            .arg(source)
            .current_dir(root)
            .env("LEAN_PATH", &lean_path)
            .output();
        let Ok(output) = output else {
            return BuildResult::failure(2, version, "could not run Lean".into());
        };
        diagnostics.extend(parse_stream("stdout", &String::from_utf8_lossy(&output.stdout)));
        diagnostics.extend(parse_stream("stderr", &String::from_utf8_lossy(&output.stderr)));
        exit_code = output.status.code().unwrap_or(-1);
        if exit_code != 0 {
            // A dependency that will not compile makes the unit's own
            // diagnostics meaningless; stop and report this instead.
            return BuildResult {
                status: BuildStatus::Fail,
                exit_code,
                lean_version: version,
                duration_ms: elapsed(started),
                diagnostics,
            };
        }
    }

    let output = Command::new(&executable)
        .args(["-R", &root.to_string_lossy()])
        .arg(&unit_name)
        .current_dir(root)
        .env("LEAN_PATH", &lean_path)
        .output();
    let Ok(output) = output else {
        return BuildResult::failure(2, version, "could not run Lean".into());
    };
    diagnostics.extend(parse_stream("stdout", &String::from_utf8_lossy(&output.stdout)));
    diagnostics.extend(parse_stream("stderr", &String::from_utf8_lossy(&output.stderr)));
    exit_code = output.status.code().unwrap_or(exit_code);

    BuildResult {
        status: if exit_code == 0 {
            BuildStatus::Pass
        } else {
            BuildStatus::Fail
        },
        exit_code,
        lean_version: version,
        duration_ms: elapsed(started),
        diagnostics,
    }
}
