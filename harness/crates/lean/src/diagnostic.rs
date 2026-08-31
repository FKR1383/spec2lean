use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Severity {
    Error,
    Warning,
    Info,
}

impl Severity {
    /// Lean does not tag every line it emits, so severity is read from the raw
    /// line the way the Python implementation did — including continuation
    /// lines, which is why this looks at the whole text rather than a prefix.
    pub fn of(text: &str) -> Self {
        let lowered = text.to_lowercase();
        if lowered.contains("error") {
            Self::Error
        } else if lowered.contains("warning") {
            Self::Warning
        } else {
            Self::Info
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Diagnostic {
    pub stream: &'static str,
    pub severity: Severity,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub line: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub column: Option<u32>,
    pub message: String,
}

/// Split `path:line:column: message` without a regex engine.
///
/// Scans colons left to right and takes the first one followed by
/// `digits:digits:`, which is the non-greedy `^(.*?):(\d+):(\d+):` the Python
/// implementation used. Doing it by hand keeps the crate dependency-free and
/// makes the ambiguity explicit: a path containing a colon resolves the same
/// way in both implementations.
fn parse_location(text: &str) -> Option<(String, u32, u32, &str)> {
    for (index, _) in text.match_indices(':') {
        let rest = &text[index + 1..];
        // Every failure here must try the next colon, not abandon the line:
        // a path may itself contain colons, and the pattern is non-greedy.
        let Some((line, rest)) = take_number(rest) else {
            continue;
        };
        let Some(rest) = rest.strip_prefix(':') else {
            continue;
        };
        let Some((column, rest)) = take_number(rest) else {
            continue;
        };
        let Some(rest) = rest.strip_prefix(':') else {
            continue;
        };
        return Some((text[..index].to_string(), line, column, rest.trim_start()));
    }
    None
}

fn take_number(text: &str) -> Option<(u32, &str)> {
    let digits: String = text.chars().take_while(char::is_ascii_digit).collect();
    if digits.is_empty() {
        return None;
    }
    Some((digits.parse().ok()?, &text[digits.len()..]))
}

/// Drop a leading `error:`, `warning:`, or `error(kind):` label.
fn strip_severity_label(message: &str) -> &str {
    for label in ["error", "warning"] {
        let Some(rest) = message.strip_prefix(label) else {
            continue;
        };
        // An optional parenthesised qualifier, e.g. `error(deprecated):`.
        let rest = match rest.strip_prefix('(') {
            Some(inner) => match inner.find(')') {
                Some(end) => &inner[end + 1..],
                None => continue,
            },
            None => rest,
        };
        if let Some(rest) = rest.strip_prefix(':') {
            return rest.trim_start();
        }
    }
    message
}

/// Parse one stream into diagnostics, folding unlocated continuation lines into
/// the message of the diagnostic above them.
pub fn parse_stream(stream: &'static str, content: &str) -> Vec<Diagnostic> {
    let mut result: Vec<Diagnostic> = Vec::new();
    let mut current: Option<Diagnostic> = None;
    for text in content.lines() {
        let severity = Severity::of(text);
        match parse_location(text) {
            Some((file, line, column, message)) => {
                if let Some(previous) = current.take() {
                    result.push(previous);
                }
                current = Some(Diagnostic {
                    stream,
                    severity,
                    file: Some(file),
                    line: Some(line),
                    column: Some(column),
                    message: strip_severity_label(message).to_string(),
                });
            }
            None => match current.as_mut() {
                // A continuation of the diagnostic above: Lean prints the
                // offending term and its types on following lines.
                Some(diagnostic) => {
                    diagnostic.message.push('\n');
                    diagnostic.message.push_str(text);
                }
                None => result.push(Diagnostic {
                    stream,
                    severity,
                    file: None,
                    line: None,
                    column: None,
                    message: text.to_string(),
                }),
            },
        }
    }
    if let Some(previous) = current {
        result.push(previous);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_located_diagnostic_with_continuation_lines() {
        let output = "bad.lean:1:15: error: Type mismatch\n  \"oops\"\nhas type\n  String";
        let diagnostics = parse_stream("stderr", output);
        assert_eq!(diagnostics.len(), 1);
        let first = &diagnostics[0];
        assert_eq!(first.file.as_deref(), Some("bad.lean"));
        assert_eq!(first.line, Some(1));
        assert_eq!(first.column, Some(15));
        assert_eq!(first.severity, Severity::Error);
        // The label is stripped; the continuation is kept.
        assert_eq!(first.message, "Type mismatch\n  \"oops\"\nhas type\n  String");
    }

    #[test]
    fn separates_consecutive_diagnostics() {
        let output = "a.lean:1:0: error: first\na.lean:2:0: warning: second\n";
        let diagnostics = parse_stream("stdout", output);
        assert_eq!(diagnostics.len(), 2);
        assert_eq!(diagnostics[0].message, "first");
        assert_eq!(diagnostics[1].severity, Severity::Warning);
        assert_eq!(diagnostics[1].line, Some(2));
    }

    #[test]
    fn unlocated_output_is_kept_verbatim() {
        let diagnostics = parse_stream("stderr", "lake: no such target\n");
        assert_eq!(diagnostics.len(), 1);
        assert!(diagnostics[0].file.is_none());
        assert_eq!(diagnostics[0].message, "lake: no such target");
        assert_eq!(diagnostics[0].severity, Severity::Info);
    }

    #[test]
    fn a_path_containing_a_colon_resolves_at_the_first_location_like_pattern() {
        let diagnostics = parse_stream("stderr", "od:d/a.lean:3:4: error: boom");
        assert_eq!(diagnostics[0].file.as_deref(), Some("od:d/a.lean"));
        assert_eq!(diagnostics[0].line, Some(3));
    }

    #[test]
    fn qualified_severity_labels_are_stripped() {
        assert_eq!(strip_severity_label("error: x"), "x");
        assert_eq!(strip_severity_label("warning: y"), "y");
        assert_eq!(strip_severity_label("error(deprecated): z"), "z");
        assert_eq!(strip_severity_label("no label here"), "no label here");
    }
}
