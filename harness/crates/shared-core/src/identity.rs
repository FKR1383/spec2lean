use serde_json::Value;
use sha2::{Digest, Sha256};
use spec2lean_specdb::{canonical_json, stable_id};

/// Bumping any of these deliberately invalidates every existing core: they are
/// part of the identity, so a policy change cannot silently reuse a core built
/// under the old rules.
pub const CORE_SCHEMA_VERSION: u32 = 2;
pub const REPRESENTATION_SCHEMA_VERSION: u32 = 2;
pub const GENERATOR_POLICY_VERSION: u32 = 3;

pub fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hasher
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

pub fn json_hash(value: &Value) -> String {
    format!("sha256:{}", sha256_hex(canonical_json(value).as_bytes()))
}

pub fn text_hash(value: &str) -> String {
    format!("sha256:{}", sha256_hex(value.as_bytes()))
}

/// Capitalised alphanumeric Lean path component.
pub fn lean_component(value: &str) -> String {
    let mut component = String::new();
    for word in value.split(|c: char| !c.is_ascii_alphanumeric()) {
        let mut characters = word.chars();
        if let Some(first) = characters.next() {
            component.push(first.to_ascii_uppercase());
            component.extend(characters);
        }
    }
    if component.is_empty() {
        component.push_str("Specification");
    }
    if component.starts_with(|c: char| c.is_ascii_digit()) {
        component.insert(0, 'V');
    }
    component
}

/// The namespace for one independent core lineage.
///
/// The trailing token hashes the core's *content*, so two different cores for
/// the same specification cannot collide in the module namespace — which is
/// what makes a core safe to freeze and reuse rather than regenerate.
pub fn core_namespace(
    language: &str,
    version: &str,
    source_database_digest: &str,
    lean_source: &str,
    concepts: &Value,
    declarations: &Value,
) -> String {
    let identity = serde_json::json!({
        "language": language,
        "version": version,
        "sourceDatabaseDigest": source_database_digest,
        "coreSchemaVersion": CORE_SCHEMA_VERSION,
        "representationSchemaVersion": REPRESENTATION_SCHEMA_VERSION,
        "generatorPolicyVersion": GENERATOR_POLICY_VERSION,
        "leanSource": lean_source,
        "concepts": concepts,
        "declarations": declarations,
    });
    let token: String = sha256_hex(canonical_json(&identity).as_bytes())
        .chars()
        .take(16)
        .collect();
    format!(
        "Spec2LeanShared.{}.{}.N{token}",
        lean_component(language),
        lean_component(version)
    )
}

/// Identity of one frozen core.
///
/// Includes the generator, because a core produced by a different model is a
/// different core even when the text happens to match — reusing one across
/// generators would silently change what "frozen" means.
#[expect(clippy::too_many_arguments)]
pub fn core_run_id(
    language: &str,
    version: &str,
    source_database_digest: &str,
    generator_provider: &str,
    generator_model: &str,
    source_hash: &str,
    concepts: &Value,
    declarations: &Value,
) -> String {
    let mut sorted_concepts = concepts.as_array().cloned().unwrap_or_default();
    sorted_concepts.sort_by_key(|item| {
        item["dependencyId"].as_str().unwrap_or_default().to_string()
    });
    let mut sorted_declarations = declarations.as_array().cloned().unwrap_or_default();
    sorted_declarations.sort_by_key(|item| {
        item["declaration"].as_str().unwrap_or_default().to_string()
    });
    let registry = serde_json::json!({
        "concepts": sorted_concepts,
        "declarations": sorted_declarations,
    });
    let registry_json = canonical_json(&registry);
    stable_id(
        "shared-core-run",
        &[
            language,
            version,
            source_database_digest,
            &CORE_SCHEMA_VERSION.to_string(),
            &REPRESENTATION_SCHEMA_VERSION.to_string(),
            &GENERATOR_POLICY_VERSION.to_string(),
            generator_provider,
            generator_model,
            source_hash,
            &registry_json,
        ],
        24,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn the_namespace_changes_with_the_content_it_freezes() {
        let one = core_namespace("PCIe", "1.0d", "abc", "def a := 1", &json!([]), &json!([]));
        let two = core_namespace("PCIe", "1.0d", "abc", "def a := 2", &json!([]), &json!([]));
        assert_ne!(one, two);
        assert!(one.starts_with("Spec2LeanShared.PCIe.V10d.N"), "{one}");
        // Stable for identical content.
        assert_eq!(
            one,
            core_namespace("PCIe", "1.0d", "abc", "def a := 1", &json!([]), &json!([]))
        );
    }

    #[test]
    fn the_run_id_is_independent_of_registry_order() {
        let concepts_a = json!([{"dependencyId": "shared:b"}, {"dependencyId": "shared:a"}]);
        let concepts_b = json!([{"dependencyId": "shared:a"}, {"dependencyId": "shared:b"}]);
        assert_eq!(
            core_run_id("PCIe", "1.0d", "d", "p", "m", "s", &concepts_a, &json!([])),
            core_run_id("PCIe", "1.0d", "d", "p", "m", "s", &concepts_b, &json!([])),
        );
    }

    #[test]
    fn a_different_generator_yields_a_different_core() {
        let base = core_run_id("PCIe", "1.0d", "d", "anthropic", "m1", "s", &json!([]), &json!([]));
        let other = core_run_id("PCIe", "1.0d", "d", "anthropic", "m2", "s", &json!([]), &json!([]));
        assert_ne!(base, other);
        assert!(base.starts_with("shared-core-run:"));
    }
}
