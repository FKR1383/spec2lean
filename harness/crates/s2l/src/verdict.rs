//! Emit results in the shape EDLab's tool harness reads.
//!
//! EDLab's mechanism is "agents propose, tools decide": every verdict a user
//! sees comes from a deterministic tool run rather than a model's judgment.
//! That is the same principle this harness is built on, so it fits as a tool
//! rather than as an agent — a command on PATH that appends one JSON line per
//! run to `.edlab/verdicts.jsonl` and exits non-zero when it did not pass.

use std::path::Path;

use serde_json::{Value, json};

/// One line of `.edlab/verdicts.jsonl`.
pub fn verdict(tool: &str, passed: bool, summary: &str, detail: Option<Value>) -> Value {
    let mut value = json!({
        "tool": tool,
        "passed": passed,
        "summary": summary,
    });
    if let Some(detail) = detail {
        value["detail"] = detail;
    }
    value
}

/// Append a verdict to the workspace's log, creating it if needed.
///
/// A run that produced a verdict but could not record it has still produced the
/// verdict, so a write failure is reported without changing the outcome.
pub fn append(workspace: &Path, value: &Value) -> Result<(), String> {
    use std::io::Write;

    let directory = workspace.join(".edlab");
    std::fs::create_dir_all(&directory)
        .map_err(|error| format!("could not create {}: {error}", directory.display()))?;
    let path = directory.join("verdicts.jsonl");
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|error| format!("could not open {}: {error}", path.display()))?;
    writeln!(file, "{}", serde_json::to_string(value).map_err(|e| e.to_string())?)
        .map_err(|error| format!("could not write {}: {error}", path.display()))
}

/// Summarise a phase outcome as one line an engineer can act on.
pub fn summarise(phase: &str, outcome: &Result<(), String>) -> (bool, String) {
    match outcome {
        Ok(()) => (true, format!("{phase} passed")),
        Err(detail) => {
            // Keep it to one line: the artifacts carry the rest.
            let first = detail.lines().next().unwrap_or(detail).trim();
            (false, format!("{phase} failed: {first}"))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_verdict_carries_what_the_harness_reads() {
        let value = verdict("formalize", true, "checked", Some(json!({"units": 2})));
        assert_eq!(value["tool"], json!("formalize"));
        assert_eq!(value["passed"], json!(true));
        assert_eq!(value["summary"], json!("checked"));
        assert_eq!(value["detail"]["units"], json!(2));
    }

    #[test]
    fn a_failure_summary_is_one_actionable_line() {
        let outcome = Err("traceability: FAIL (1 broken)\n  EVIDENCE_DRIFT: ...".to_string());
        let (passed, summary) = summarise("check", &outcome);
        assert!(!passed);
        assert_eq!(summary, "check failed: traceability: FAIL (1 broken)");
        assert!(!summary.contains('\n'));
    }

    #[test]
    fn verdicts_append_rather_than_replace() {
        let workspace = std::env::temp_dir().join(format!("s2l-verdict-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&workspace);
        append(&workspace, &verdict("a", true, "one", None)).expect("first");
        append(&workspace, &verdict("b", false, "two", None)).expect("second");
        let text = std::fs::read_to_string(workspace.join(".edlab/verdicts.jsonl")).unwrap();
        assert_eq!(text.lines().count(), 2);
        assert!(text.contains("\"tool\":\"a\"") && text.contains("\"tool\":\"b\""));
        let _ = std::fs::remove_dir_all(&workspace);
    }
}
