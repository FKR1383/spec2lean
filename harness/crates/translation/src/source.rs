//! Structural analysis of Lean source.
//!
//! Everything here works on text the translator produced, before the compiler
//! ever sees it: which declarations exist, under which namespaces, and whether
//! the source reaches for an escape hatch that would make the formalization
//! vacuous.

use std::collections::BTreeMap;

/// Blank comments and string literals while preserving line structure, so
/// line-oriented scanning cannot be fooled by a `def` inside a comment or a
/// `sorry` inside a string.
pub fn without_comments_and_strings(source: &str) -> String {
    let characters: Vec<char> = source.chars().collect();
    let mut result = String::with_capacity(source.len());
    let mut index = 0;
    let mut block_depth = 0usize;
    let mut in_string = false;

    let pair = |index: usize| -> String {
        characters
            .get(index..index + 2)
            .map(|slice| slice.iter().collect())
            .unwrap_or_default()
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
                    result.push(if character == '\n' { '\n' } else { ' ' });
                    index += 1;
                }
            }
            continue;
        }
        if in_string {
            if character == '\\' && index + 1 < characters.len() {
                result.push_str("  ");
                index += 2;
            } else if character == '"' {
                in_string = false;
                result.push(' ');
                index += 1;
            } else {
                result.push(if character == '\n' { '\n' } else { ' ' });
                index += 1;
            }
            continue;
        }
        match pair(index).as_str() {
            "--" => {
                let end = characters[index..]
                    .iter()
                    .position(|c| *c == '\n')
                    .map(|offset| index + offset);
                match end {
                    Some(end) => {
                        result.extend(std::iter::repeat_n(' ', end - index));
                        result.push('\n');
                        index = end + 1;
                    }
                    None => {
                        result.extend(std::iter::repeat_n(' ', characters.len() - index));
                        break;
                    }
                }
            }
            "/-" => {
                block_depth = 1;
                result.push_str("  ");
                index += 2;
            }
            _ if character == '"' => {
                in_string = true;
                result.push(' ');
                index += 1;
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

pub fn is_lean_name(value: &str) -> bool {
    !value.is_empty()
        && value.split('.').all(|segment| {
            let mut characters = segment.chars();
            characters
                .next()
                .is_some_and(|first| first.is_ascii_alphabetic() || first == '_')
                && characters.all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '\'')
        })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeclarationEntry {
    pub name: String,
    pub kind: String,
    pub line: usize,
}

/// Named declarations in source order, qualified by enclosing namespaces.
pub fn declaration_entries(source: &str) -> Vec<DeclarationEntry> {
    let clean = without_comments_and_strings(source);
    let mut contexts: Vec<Vec<String>> = Vec::new();
    let mut found = Vec::new();

    for (offset, line) in clean.lines().enumerate() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("namespace ") {
            let name = rest.trim();
            if is_lean_name(name) {
                contexts.push(name.split('.').map(str::to_string).collect());
                continue;
            }
        }
        if trimmed == "section" || trimmed.strip_prefix("section ").is_some_and(is_lean_name) {
            contexts.push(Vec::new());
            continue;
        }
        if trimmed == "end"
            || trimmed
                .strip_prefix("end ")
                .is_some_and(|rest| is_lean_name(rest.trim()))
        {
            contexts.pop();
            continue;
        }
        // Skip leading modifiers, then require a declaration keyword and a name.
        let mut words = trimmed.split_whitespace();
        let mut keyword = words.next();
        while keyword.is_some_and(|word| MODIFIERS.contains(&word)) {
            keyword = words.next();
        }
        let Some(keyword) = keyword.filter(|word| DECLARATION_KEYWORDS.contains(word)) else {
            continue;
        };
        let Some(raw_name) = words.next() else {
            continue;
        };
        // Trim anything that can legally follow a name on the same line.
        let name = raw_name.trim_end_matches([':', '(', '{', '[']);
        if !is_lean_name(name) {
            continue;
        }
        let prefix: Vec<String> = contexts.iter().flatten().cloned().collect();
        let qualified = if prefix.is_empty() {
            name.to_string()
        } else {
            format!("{}.{name}", prefix.join("."))
        };
        found.push(DeclarationEntry {
            name: qualified,
            kind: keyword.to_string(),
            line: offset + 1,
        });
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
pub const FORBIDDEN: &[(&str, &str, &str)] = &[
    ("FORBIDDEN_SORRY", "sorry", "Lean source contains forbidden 'sorry'"),
    ("FORBIDDEN_ADMIT", "admit", "Lean source contains forbidden 'admit'"),
    ("FORBIDDEN_AXIOM", "axiom", "Lean source declares a forbidden axiom"),
    ("FORBIDDEN_CONSTANT", "constant", "Lean source declares a forbidden constant/axiom"),
    ("FORBIDDEN_UNSAFE", "unsafe", "Lean source contains forbidden unsafe code"),
    ("FORBIDDEN_PARTIAL", "partial", "Lean source contains a forbidden partial definition"),
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
