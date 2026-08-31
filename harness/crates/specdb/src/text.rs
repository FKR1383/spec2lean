use serde_json::Value;
use sha2::{Digest, Sha256};
use unicode_normalization::UnicodeNormalization;

/// NFKC, drop the anchor-link private-use glyph, collapse whitespace, trim.
///
/// Byte-for-byte equivalent to the Python `normalize_text`, because normalized
/// text feeds the stable IDs that both implementations must agree on.
pub fn normalize_text(value: &str) -> String {
    let folded: String = value.nfkc().collect();
    let mut result = String::with_capacity(folded.len());
    let mut pending_space = false;
    for character in folded.chars() {
        let character = if character == '\u{f0c1}' { ' ' } else { character };
        if character.is_whitespace() {
            pending_space = !result.is_empty();
            continue;
        }
        if pending_space {
            result.push(' ');
            pending_space = false;
        }
        result.push(character);
    }
    result
}

/// Key-sorted, separator-free JSON. `serde_json::Value` maps are BTreeMaps, so
/// key order is sorted by construction — matching Python's
/// `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
pub fn canonical_json(value: &Value) -> String {
    serde_json::to_string(value).expect("a serde_json::Value always serialises")
}

/// `prefix:<sha256(parts joined by NUL)[..length]>`, matching the Python
/// `stable_id`. Identical inputs must produce identical IDs in both languages
/// or the two implementations' artifacts stop being comparable.
pub fn stable_id(prefix: &str, parts: &[&str], length: usize) -> String {
    let mut hasher = Sha256::new();
    for (index, part) in parts.iter().enumerate() {
        if index > 0 {
            hasher.update([0u8]);
        }
        hasher.update(part.as_bytes());
    }
    let digest = hasher.finalize();
    let hex: String = digest.iter().map(|byte| format!("{byte:02x}")).collect();
    format!("{prefix}:{}", &hex[..length.min(hex.len())])
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn normalizes_like_the_python_implementation() {
        assert_eq!(normalize_text("  a\t\n b  "), "a b");
        assert_eq!(normalize_text("a\u{f0c1}b"), "a b");
        assert_eq!(normalize_text("\u{fb01}n"), "fin"); // NFKC ligature
        assert_eq!(normalize_text(""), "");
        assert_eq!(normalize_text("   "), "");
    }

    #[test]
    fn canonical_json_sorts_keys_without_spaces() {
        assert_eq!(
            canonical_json(&json!({"b": 1, "a": [1, 2]})),
            r#"{"a":[1,2],"b":1}"#
        );
    }

    #[test]
    fn stable_id_matches_the_known_python_digest() {
        // python: stable_id("evidence", "x", length=32)
        assert_eq!(
            stable_id("evidence", &["x"], 32),
            "evidence:2d711642b726b04401627ca9fbac32f5"
        );
    }
}
