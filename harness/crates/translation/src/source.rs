//! Structural analysis of Lean source.
//!
//! Everything here works on text the translator produced, before the compiler
//! ever sees it: which declarations exist, under which namespaces, and whether
//! the source reaches for an escape hatch that would make the formalization
//! vacuous.

use std::collections::BTreeMap;

/// Blank comments and string literals while preserving line structure, so
/// line-oriented scanning cannot be fooled by a `def` inside a comment.
///
/// Two Lean features make a naive version unsound, and both were found by
/// review rather than by imagination:
///
/// * `r#"..."#` raw strings. Treating their inner `"` as a delimiter puts the
///   scanner out of phase, and it then blanks *real code* — which is how an
///   `axiom` becomes invisible.
/// * `s!"...{e}..."` interpolation. The text inside the braces is an
///   expression, not string content, so blanking it hides anything written
///   there — `sorry` included.
///
/// The kernel-level `#print axioms` audit is the authoritative soundness
/// check; this scanner is the fast, legible layer in front of it.
pub fn without_comments_and_strings(source: &str) -> String {
    let characters: Vec<char> = source.chars().collect();
    let mut result = String::with_capacity(source.len());
    let mut index = 0;
    let mut block_depth = 0usize;

    let at = |index: usize| characters.get(index).copied().unwrap_or('\0');
    let pair = |index: usize| -> String {
        characters
            .get(index..index + 2)
            .map(|slice| slice.iter().collect())
            .unwrap_or_default()
    };
    // Preserve line structure so reported line numbers stay meaningful.
    let blank = |result: &mut String, character: char| {
        result.push(if character == '\n' { '\n' } else { ' ' });
    };

    while index < characters.len() {
        let character = characters[index];
        if block_depth > 0 {
            match pair(index).as_str() {
                "/-" => {
                    block_depth += 1;
                    result.push_str("  ");
                    index += 2;
                }
                "-/" => {
                    block_depth -= 1;
                    result.push_str("  ");
                    index += 2;
                }
                _ => {
                    blank(&mut result, character);
                    index += 1;
                }
            }
            continue;
        }
        match pair(index).as_str() {
            "--" => {
                let end = characters[index..]
                    .iter()
                    .position(|c| *c == '\n')
                    .map(|offset| index + offset)
                    .unwrap_or(characters.len());
                result.extend(std::iter::repeat_n(' ', end - index));
                index = end;
            }
            "/-" => {
                block_depth = 1;
                result.push_str("  ");
                index += 2;
            }
            _ if character == 'r' && at(index + 1) == '#' => {
                // A raw string: r#"…"#, r##"…"##, and so on. The terminator is
                // a quote followed by exactly as many hashes as opened it.
                let mut hashes = 0usize;
                while at(index + 1 + hashes) == '#' {
                    hashes += 1;
                }
                if at(index + 1 + hashes) != '"' {
                    result.push(character);
                    index += 1;
                    continue;
                }
                let terminator: String =
                    std::iter::once('"').chain(std::iter::repeat_n('#', hashes)).collect();
                let mut cursor = index + 2 + hashes;
                result.extend(std::iter::repeat_n(' ', 2 + hashes));
                loop {
                    if cursor >= characters.len() {
                        break;
                    }
                    let ahead: String = characters
                        .get(cursor..cursor + terminator.len())
                        .map(|slice| slice.iter().collect())
                        .unwrap_or_default();
                    if ahead == terminator {
                        result.extend(std::iter::repeat_n(' ', terminator.len()));
                        cursor += terminator.len();
                        break;
                    }
                    blank(&mut result, characters[cursor]);
                    cursor += 1;
                }
                index = cursor;
            }
            _ if character == '"' => {
                // Only an interpolated string — `s!"..."`, `m!"..."` — treats
                // braces as code. In a plain literal `"{sorry}"` they are text,
                // and keeping them would reject a legitimate string.
                let interpolated = index > 0 && characters[index - 1] == '!';
                result.push(' ');
                index += 1;
                let mut brace_depth = 0usize;
                while index < characters.len() {
                    let character = characters[index];
                    if brace_depth == 0 && character == '\\' {
                        // An escape, including \" and \{.
                        result.push_str("  ");
                        index += 2;
                        continue;
                    }
                    if brace_depth == 0 && character == '"' {
                        result.push(' ');
                        index += 1;
                        break;
                    }
                    if interpolated && character == '{' {
                        // Interpolated code: keep it, it is not string content.
                        brace_depth += 1;
                        result.push(character);
                        index += 1;
                        continue;
                    }
                    if brace_depth > 0 {
                        if character == '}' {
                            brace_depth -= 1;
                        }
                        result.push(character);
                        index += 1;
                        continue;
                    }
                    blank(&mut result, character);
                    index += 1;
                }
            }
            _ => {
                result.push(character);
                index += 1;
            }
        }
    }
    result
}

const DECLARATION_KEYWORDS: &[&str] = &[
    "def", "abbrev", "opaque", "theorem", "lemma", "structure", "inductive", "class", "instance",
];
const MODIFIERS: &[&str] = &["private", "protected", "noncomputable", "partial"];

/// Lean identifiers are Unicode: `α`, `Γ₀`, and `x'` are all legal, and
/// specifications formalized in Lean use them freely. An ASCII-only check
/// silently skips such declarations, leaving them unmapped and unnoticed.
pub fn is_lean_name(value: &str) -> bool {
    !value.is_empty()
        && value.split('.').all(|segment| {
            let mut characters = segment.chars();
            characters
                .next()
                .is_some_and(|first| first.is_alphabetic() || first == '_')
                && characters.all(|c| {
                    c.is_alphanumeric() || c == '_' || c == '\'' || c == '!' || c == '?'
                        || ('\u{2080}'..='\u{2089}').contains(&c)
                })
        })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeclarationEntry {
    pub name: String,
    pub kind: String,
    pub line: usize,
}

/// One token of cleaned Lean source, with the line it started on.
struct Token {
    text: String,
    line: usize,
}

/// Split cleaned source into whitespace- and bracket-delimited tokens.
///
/// Token-based rather than line-based, because Lean does not care about lines:
/// `def a := 0 def b := 1` declares two things, and a `def` may sit on the line
/// above its own name. Scanning by line misses both.
fn tokenize(clean: &str) -> Vec<Token> {
    let characters: Vec<char> = clean.chars().collect();
    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut line = 1usize;
    let mut start_line = 1usize;
    let mut index = 0usize;

    fn flush(current: &mut String, start_line: usize, tokens: &mut Vec<Token>) {
        if !current.is_empty() {
            tokens.push(Token {
                text: std::mem::take(current),
                line: start_line,
            });
        }
    }

    while index < characters.len() {
        let character = characters[index];
        if character == '\n' {
            flush(&mut current, start_line, &mut tokens);
            line += 1;
            start_line = line;
            index += 1;
            continue;
        }
        // `@[...]` is an attribute; swallow it whole so `@[simp] theorem` still
        // reaches the keyword. A bare `@` is explicit-argument syntax and is
        // left alone.
        if character == '@' && characters.get(index + 1) == Some(&'[') {
            flush(&mut current, start_line, &mut tokens);
            let mut depth = 0usize;
            index += 1;
            while index < characters.len() {
                match characters[index] {
                    '[' => depth += 1,
                    ']' => {
                        depth -= 1;
                        if depth == 0 {
                            index += 1;
                            break;
                        }
                    }
                    '\n' => line += 1,
                    _ => {}
                }
                index += 1;
            }
            start_line = line;
            continue;
        }
        if character.is_whitespace() {
            flush(&mut current, start_line, &mut tokens);
            start_line = line;
            index += 1;
            continue;
        }
        if current.is_empty() {
            start_line = line;
        }
        current.push(character);
        index += 1;
    }
    flush(&mut current, start_line, &mut tokens);
    tokens
}

/// Strip what may legally follow a declaration name on the same token.
fn declaration_name(token: &str) -> Option<&str> {
    // `foo.{u}` is a universe-polymorphic declaration; `foo(` and `foo:` are
    // the name running straight into its signature.
    let name = token.split(".{").next().unwrap_or(token);
    let name = name.trim_end_matches([':', '(', '{', '[', ')', ',']);
    is_lean_name(name).then_some(name)
}

/// Named declarations in source order, qualified by enclosing namespaces.
pub fn declaration_entries(source: &str) -> Vec<DeclarationEntry> {
    let clean = without_comments_and_strings(source);
    let tokens = tokenize(&clean);
    let mut contexts: Vec<Vec<String>> = Vec::new();
    let mut found = Vec::new();
    let mut index = 0usize;

    while index < tokens.len() {
        let token = &tokens[index];
        match token.text.as_str() {
            "namespace" => {
                if let Some(next) = tokens.get(index + 1)
                    && is_lean_name(&next.text)
                {
                    contexts.push(next.text.split('.').map(str::to_string).collect());
                    index += 2;
                    continue;
                }
            }
            // `mutual` is closed by `end` like a namespace but contributes no
            // name, so treating its `end` as closing the namespace loses the
            // qualification of everything after it.
            "section" | "mutual" => {
                contexts.push(Vec::new());
                // An optional section name follows.
                index += 1;
                if tokens.get(index).is_some_and(|next| is_lean_name(&next.text))
                    && !DECLARATION_KEYWORDS.contains(&tokens[index].text.as_str())
                {
                    index += 1;
                }
                continue;
            }
            "end" => {
                contexts.pop();
                index += 1;
                if tokens.get(index).is_some_and(|next| is_lean_name(&next.text))
                    && !DECLARATION_KEYWORDS.contains(&tokens[index].text.as_str())
                {
                    index += 1;
                }
                continue;
            }
            keyword if DECLARATION_KEYWORDS.contains(&keyword) => {
                // Skip any modifiers that follow the keyword position; they may
                // also precede it, which the loop handles naturally.
                let mut cursor = index + 1;
                while tokens
                    .get(cursor)
                    .is_some_and(|next| MODIFIERS.contains(&next.text.as_str()))
                {
                    cursor += 1;
                }
                if let Some(next) = tokens.get(cursor)
                    && let Some(name) = declaration_name(&next.text)
                {
                    let prefix: Vec<String> = contexts.iter().flatten().cloned().collect();
                    let qualified = if prefix.is_empty() {
                        name.to_string()
                    } else {
                        format!("{}.{name}", prefix.join("."))
                    };
                    found.push(DeclarationEntry {
                        name: qualified,
                        kind: keyword.to_string(),
                        line: token.line,
                    });
                    index = cursor + 1;
                    continue;
                }
            }
            _ => {}
        }
        index += 1;
    }
    found
}

pub fn declarations(source: &str) -> BTreeMap<String, String> {
    declaration_entries(source)
        .into_iter()
        .map(|entry| (entry.name, entry.kind))
        .collect()
}

/// Escape hatches that would make a formalization assert nothing.
///
/// `sorry` and `admit` leave holes; `axiom` and `constant` assert without
/// justification; `unsafe` and `partial` sidestep totality. A spec formalized
/// with any of these is not formalized.
/// Escape hatches that would make a formalization assert nothing, and the
/// command-extension constructs that would let it rewrite the check that judges
/// it. Lean exports syntax and elaborators through imports, so a module that
/// defines `syntax`/`elab_rules` for `#print axioms` hijacks the axiom audit in
/// any file importing it. A formalization of a specification defines meaning,
/// not new command syntax.
pub const FORBIDDEN: &[(&str, &str, &str)] = &[
    ("FORBIDDEN_SORRY", "sorry", "Lean source contains forbidden 'sorry'"),
    ("FORBIDDEN_ADMIT", "admit", "Lean source contains forbidden 'admit'"),
    ("FORBIDDEN_AXIOM", "axiom", "Lean source declares a forbidden axiom"),
    ("FORBIDDEN_CONSTANT", "constant", "Lean source declares a forbidden constant/axiom"),
    ("FORBIDDEN_UNSAFE", "unsafe", "Lean source contains forbidden unsafe code"),
    ("FORBIDDEN_PARTIAL", "partial", "Lean source contains a forbidden partial definition"),
    ("FORBIDDEN_SYNTAX", "syntax", "Lean source declares command syntax, which can redefine the checks that judge it"),
    ("FORBIDDEN_MACRO", "macro", "Lean source declares a macro, which can redefine the checks that judge it"),
    ("FORBIDDEN_MACRO_RULES", "macro_rules", "Lean source declares macro rules, which can redefine the checks that judge it"),
    ("FORBIDDEN_ELAB", "elab", "Lean source declares an elaborator, which can redefine the checks that judge it"),
    ("FORBIDDEN_ELAB_RULES", "elab_rules", "Lean source declares elaboration rules, which can redefine the checks that judge it"),
    ("FORBIDDEN_SYNTAX_CAT", "declare_syntax_cat", "Lean source declares a syntax category"),
];

/// Whole-word search over comment- and string-stripped source, so a token in
/// prose or in an identifier like `sorryFree` does not trip the check.
pub fn contains_word(clean: &str, word: &str) -> bool {
    let bytes = clean.as_bytes();
    let mut start = 0;
    while let Some(offset) = clean[start..].find(word) {
        let at = start + offset;
        let before_ok = at == 0 || !is_word_byte(bytes[at - 1]);
        let after = at + word.len();
        // Lean pluralises two of these keywords; treat a trailing `s` as part
        // of the same word rather than a different identifier.
        let after_ok = after >= bytes.len()
            || !is_word_byte(bytes[after])
            || (bytes[after] == b's'
                && (after + 1 >= bytes.len() || !is_word_byte(bytes[after + 1])));
        if before_ok && after_ok {
            return true;
        }
        start = at + 1;
    }
    false
}

fn is_word_byte(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'\''
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn comments_and_strings_are_blanked_but_lines_are_preserved() {
        let source = "def a : Nat := 1\n-- def b : Nat := 2\n/- def c -/\ndef d := \"def e\"\n";
        let clean = without_comments_and_strings(source);
        assert_eq!(clean.lines().count(), source.lines().count());
        let names: Vec<String> = declarations(source).into_keys().collect();
        assert_eq!(names, vec!["a".to_string(), "d".to_string()]);
    }

    #[test]
    fn declarations_are_qualified_by_enclosing_namespaces() {
        let source = "namespace Spec\nnamespace Add\ndef run : Nat := 1\nend Add\ndef top : Nat := 2\nend Spec\ndef outside : Nat := 3\n";
        let found = declarations(source);
        let names: Vec<&str> = found.keys().map(String::as_str).collect();
        assert_eq!(names, ["Spec.Add.run", "Spec.top", "outside"]);
        assert_eq!(found["Spec.Add.run"], "def");
    }

    /// External review, confirmed against real `lean`: it declares `N.after`.
    #[test]
    fn a_mutual_block_does_not_close_its_namespace() {
        let source = "namespace N\nmutual\n  def even : Nat := 0\n  def odd : Nat := 1\nend\ndef after := 0\nend N\n";
        let found = declarations(source);
        let names: Vec<&str> = found.keys().map(String::as_str).collect();
        assert_eq!(names, ["N.after", "N.even", "N.odd"], "{found:?}");
    }

    #[test]
    fn sections_nest_without_contributing_a_namespace() {
        let source = "namespace Spec\nsection\ndef inner : Nat := 1\nend\ndef outer : Nat := 2\nend Spec\n";
        let names: Vec<String> = declarations(source).into_keys().collect();
        assert_eq!(names, vec!["Spec.inner".to_string(), "Spec.outer".to_string()]);
    }

    #[test]
    fn modifiers_and_trailing_punctuation_do_not_hide_a_declaration() {
        let source = "protected noncomputable def wide (n : Nat) : Nat := n\ntheorem t: True := trivial\nstructure S where\n  x : Nat\n";
        let found = declarations(source);
        assert_eq!(found["wide"], "def");
        assert_eq!(found["t"], "theorem");
        assert_eq!(found["S"], "structure");
    }

    /// Every case here was found by external review and confirmed against a
    /// real `lean` run: all of them compile, and the previous line-based
    /// scanner missed or mangled each one.
    #[test]
    fn declarations_that_evaded_line_based_scanning() {
        // Two declarations on one line.
        let found = declarations("def good := 0 def hidden := 1\n");
        assert_eq!(
            found.keys().map(String::as_str).collect::<Vec<_>>(),
            ["good", "hidden"]
        );

        // The keyword and the name on separate lines.
        let found = declarations("def\nhidden2 := 2\n");
        assert!(found.contains_key("hidden2"), "{found:?}");

        // An attribute before the keyword.
        let found = declarations("@[simp] theorem hidden3 (n : Nat) : n = n := rfl\n");
        assert_eq!(found.get("hidden3").map(String::as_str), Some("theorem"));

        // Universe polymorphism written on the name.
        let found = declarations("def hidden4.{u} (a : Sort u) := a\n");
        assert!(found.contains_key("hidden4"), "{found:?}");

        // A Unicode identifier, which Lean accepts and ASCII-only checks skip.
        let found = declarations("def \u{3b1} := 1\n");
        assert!(found.contains_key("\u{3b1}"), "{found:?}");
        assert!(is_lean_name("\u{3b1}"));
        assert!(is_lean_name("\u{393}\u{2080}"));
    }

    /// The soundness cases. Lean accepts all of these; the old scanner blanked
    /// real code and lost the forbidden construct.
    #[test]
    fn raw_strings_and_interpolation_cannot_hide_a_forbidden_construct() {
        // A raw string whose inner quote used to desynchronise the scanner,
        // blanking the axiom that follows it.
        let source = "def marker := r#\"foo\"bar\"#\naxiom hidden : False\n-- \"\ntheorem required : False := hidden\n";
        let clean = without_comments_and_strings(source);
        assert!(contains_word(&clean, "axiom"), "clean was: {clean:?}");
        assert!(declarations(source).contains_key("required"));

        // An interpolated expression is code, not string content.
        let clean = without_comments_and_strings("def x := s!\"{(sorry : Nat)}\"\n");
        assert!(contains_word(&clean, "sorry"), "clean was: {clean:?}");

        // Multi-hash raw strings terminate on the matching hash count.
        let clean = without_comments_and_strings("def a := r##\"x\"#y\"##\naxiom b : False\n");
        assert!(contains_word(&clean, "axiom"), "clean was: {clean:?}");

        // And ordinary strings still hide their contents.
        let clean = without_comments_and_strings("def a := \"axiom sorry\"\n");
        assert!(!contains_word(&clean, "axiom"), "clean was: {clean:?}");
        assert!(!contains_word(&clean, "sorry"), "clean was: {clean:?}");
    }

    #[test]
    fn forbidden_tokens_are_matched_as_whole_words_only() {
        assert!(contains_word("  exact sorry\n", "sorry"));
        assert!(contains_word("axiom foo : True", "axiom"));
        // Plural forms Lean accepts.
        assert!(contains_word("constants a b : Nat", "constant"));
        // Identifiers that merely contain the token do not count.
        assert!(!contains_word("def sorryFree : Nat := 1", "sorry"));
        assert!(!contains_word("def my_axiomatic : Nat := 1", "axiom"));
        // Neither does a token inside a comment, once stripped.
        let clean = without_comments_and_strings("-- no sorry here\ndef a := 1\n");
        assert!(!contains_word(&clean, "sorry"));
    }
}
