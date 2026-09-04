//! What makes a submission acceptable.
//!
//! Four things, and they are the same four the phase pipeline checked — the
//! phases were never what enforced them:
//!
//! 1. every declaration the submission names is really defined in the source,
//! 2. every declaration cites at least one span,
//! 3. every cited span was actually shown by the tool, and still exists,
//! 4. the quoted words are really in the span that is cited.
//!
//! Together these are what "evidence" means once it stops being a stage: a
//! declaration is admissible when it can point at text the model was shown and
//! the index still agrees with.

use serde_json::{Value, json};
use spec2lean_evidence::ExposureLedger;
use spec2lean_specdb::{SpanId, SpecDb};
use spec2lean_translation::source;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Diagnostic {
    pub code: String,
    pub message: String,
    pub path: String,
}

impl Diagnostic {
    fn new(code: &str, message: impl Into<String>, path: impl Into<String>) -> Self {
        Self {
            code: code.to_string(),
            message: message.into(),
            path: path.into(),
        }
    }

    pub fn to_json(&self) -> Value {
        json!({"code": self.code, "message": self.message, "path": self.path})
    }
}

/// Commands that let a file redefine what `#print axioms` reports, which is the
/// one thing that could make the kernel audit lie about the file auditing it.
const FORBIDDEN: &[&str] = &[
    "sorry",
    "axiom",
    "syntax",
    "macro",
    "macro_rules",
    "elab",
    "elab_rules",
    "declare_syntax_cat",
    "unsafe",
    "partial",
    "native_decide",
    "implemented_by",
];

pub fn validate(
    db: &SpecDb,
    ledger: &ExposureLedger,
    submission: &Value,
    task_units: &[String],
) -> Result<Value, Vec<Diagnostic>> {
    let mut diagnostics = Vec::new();

    let status = submission["status"].as_str().unwrap_or_default();
    if !matches!(status, "FORMALIZED" | "UNDERDETERMINED") {
        diagnostics.push(Diagnostic::new(
            "BAD_STATUS",
            "status must be FORMALIZED or UNDERDETERMINED",
            "$.status",
        ));
        return Err(diagnostics);
    }

    // Reporting that the text does not determine a formalization is a real
    // outcome, not a failure, but it has to say what is missing.
    if status == "UNDERDETERMINED" {
        let note = submission["note"].as_str().unwrap_or_default();
        if note.trim().len() < 20 {
            diagnostics.push(Diagnostic::new(
                "MISSING_NOTE",
                "UNDERDETERMINED must say, specifically, what the specification leaves open",
                "$.note",
            ));
            return Err(diagnostics);
        }
        return Ok(json!({"status": "UNDERDETERMINED", "note": note, "units": task_units}));
    }

    let lean = submission["lean"].as_str().unwrap_or_default();
    if lean.trim().is_empty() {
        diagnostics.push(Diagnostic::new("MISSING_LEAN", "`lean` is empty", "$.lean"));
        return Err(diagnostics);
    }
    let clean = source::without_comments_and_strings(lean);
    for word in FORBIDDEN {
        if source::contains_word(&clean, word) {
            diagnostics.push(Diagnostic::new(
                "FORBIDDEN_SYNTAX",
                format!(
                    "`{word}` is not allowed: it can make the file's own axiom report untrue"
                ),
                "$.lean",
            ));
        }
    }

    let defined = source::declarations(lean);
    let claimed = submission["declarations"].as_array().cloned().unwrap_or_default();
    if claimed.is_empty() {
        diagnostics.push(Diagnostic::new(
            "NO_DECLARATIONS",
            "a FORMALIZED submission must name the declarations it added",
            "$.declarations",
        ));
    }

    let mut named = Vec::new();
    for (index, entry) in claimed.iter().enumerate() {
        let path = format!("$.declarations[{index}]");
        let Some(name) = entry["declaration"].as_str() else {
            diagnostics.push(Diagnostic::new(
                "MISSING_NAME",
                "each entry needs `declaration`",
                format!("{path}.declaration"),
            ));
            continue;
        };
        if !defined.contains_key(name) {
            diagnostics.push(Diagnostic::new(
                "UNDEFINED_DECLARATION",
                format!("`{name}` is not defined in `lean`"),
                format!("{path}.declaration"),
            ));
            continue;
        }
        named.push(name.to_string());

        let citations = entry["cites"].as_array().cloned().unwrap_or_default();
        if citations.is_empty() {
            diagnostics.push(Diagnostic::new(
                "UNCITED_DECLARATION",
                format!("`{name}` cites no specification text"),
                format!("{path}.cites"),
            ));
            continue;
        }
        for (position, citation) in citations.iter().enumerate() {
            check_citation(db, ledger, citation, &format!("{path}.cites[{position}]"), &mut diagnostics);
        }
    }

    // Everything the file defines must be accounted for. A declaration nobody
    // claimed is a declaration nothing traces to.
    for name in defined.keys() {
        if !named.contains(name) {
            diagnostics.push(Diagnostic::new(
                "UNCLAIMED_DECLARATION",
                format!("`{name}` is defined but not listed with its citations"),
                "$.declarations",
            ));
        }
    }

    if diagnostics.is_empty() {
        Ok(json!({
            "status": "FORMALIZED",
            "units": task_units,
            "lean": lean,
            "declarations": claimed,
        }))
    } else {
        Err(diagnostics)
    }
}

fn check_citation(
    db: &SpecDb,
    ledger: &ExposureLedger,
    citation: &Value,
    path: &str,
    diagnostics: &mut Vec<Diagnostic>,
) {
    let Some(raw) = citation["spanId"].as_str() else {
        diagnostics.push(Diagnostic::new(
            "MISSING_SPAN",
            "each citation needs `spanId`",
            format!("{path}.spanId"),
        ));
        return;
    };
    let Ok(span_id) = SpanId::parse(raw) else {
        diagnostics.push(Diagnostic::new(
            "BAD_SPAN",
            format!("`{raw}` is not a span id"),
            format!("{path}.spanId"),
        ));
        return;
    };

    // Shown, not merely existing. A span the model never saw is one it is
    // recalling rather than reading, and that is the distinction the whole
    // exposure ledger exists to keep.
    if !ledger.is_span_exposed(&span_id) {
        diagnostics.push(Diagnostic::new(
            "UNEXPOSED_SPAN",
            format!("`{raw}` was never returned by the spec tool in this task"),
            format!("{path}.spanId"),
        ));
        return;
    }
    if !db.span_exists(&span_id).unwrap_or(false) {
        diagnostics.push(Diagnostic::new(
            "STALE_SPAN",
            format!("`{raw}` is no longer in the index"),
            format!("{path}.spanId"),
        ));
        return;
    }

    let Some(quote) = citation["quote"].as_str() else {
        diagnostics.push(Diagnostic::new(
            "MISSING_QUOTE",
            "each citation needs `quote`, the words being relied on",
            format!("{path}.quote"),
        ));
        return;
    };
    let rows = db.spans_by_id(&[span_id]).unwrap_or_default();
    let Some(row) = rows.first() else {
        return;
    };
    if !contains_normalized(&row.raw_text, quote) {
        diagnostics.push(Diagnostic::new(
            "QUOTE_NOT_IN_SPAN",
            "`quote` does not appear in the span it cites",
            format!("{path}.quote"),
        ));
    }
}

/// Whitespace is not evidence. A quotation that differs from the span only by
/// how a PDF broke its lines is the same quotation.
fn contains_normalized(haystack: &str, needle: &str) -> bool {
    let flatten = |value: &str| value.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase();
    let needle = flatten(needle);
    !needle.is_empty() && flatten(haystack).contains(&needle)
}
