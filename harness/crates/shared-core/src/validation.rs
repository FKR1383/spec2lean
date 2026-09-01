use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::{Value, json};
use spec2lean_translation::source::{
    FORBIDDEN, contains_word, declarations, is_lean_name, without_comments_and_strings,
};

use crate::requirements::SharedRequirement;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
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
}

/// What a valid core submission resolves to before it is compiled.
pub struct AcceptedCore {
    pub lean_source: String,
    pub concepts: Value,
    pub declarations: Value,
}

/// Validate a core submission against the concepts it must represent.
///
/// The invariant this protects: after freezing, a group translating any of
/// these concepts must be able to reach a declaration that *exists*, is
/// *registered*, and is traceable to the claims that said what the concept
/// means. Every check below is one way that could silently fail.
pub fn validate_submission(
    requirements: &[SharedRequirement],
    submission: &Value,
) -> Result<AcceptedCore, Vec<Diagnostic>> {
    let mut diagnostics = Vec::new();
    let Some(object) = submission.as_object() else {
        return Err(vec![Diagnostic::new(
            "EXPECTED_OBJECT",
            "submission must be an object",
            "$",
        )]);
    };
    let mut unexpected: Vec<&String> = object
        .keys()
        .filter(|key| !matches!(key.as_str(), "leanSource" | "concepts" | "declarations"))
        .collect();
    unexpected.sort();
    for key in unexpected {
        diagnostics.push(Diagnostic::new(
            "UNEXPECTED_FIELD",
            format!("unsupported submission field: {key}"),
            format!("$.{key}"),
        ));
    }

    let lean_source = object
        .get("leanSource")
        .and_then(Value::as_str)
        .filter(|value| !value.trim().is_empty());
    let Some(lean_source) = lean_source else {
        diagnostics.push(Diagnostic::new(
            "INVALID_SOURCE",
            "leanSource must be a non-empty string",
            "$.leanSource",
        ));
        return Err(diagnostics);
    };
    let clean = without_comments_and_strings(lean_source);
    for (code, word, message) in FORBIDDEN {
        if contains_word(&clean, word) {
            diagnostics.push(Diagnostic::new(code, *message, "$.leanSource"));
        }
    }
    let present = declarations(lean_source);

    // Every claim that described any of these concepts, as a lookup.
    let allowed_claims: BTreeSet<(&str, &str)> = requirements
        .iter()
        .flat_map(|requirement| {
            requirement
                .claim_refs
                .iter()
                .map(|(unit_id, claim_id)| (unit_id.as_str(), claim_id.as_str()))
        })
        .collect();

    // ---- declarations ----------------------------------------------------
    let raw_declarations = match object.get("declarations") {
        Some(Value::Array(items)) if !items.is_empty() => items.clone(),
        _ => {
            diagnostics.push(Diagnostic::new(
                "INVALID_DECLARATIONS",
                "declarations must be a non-empty array",
                "$.declarations",
            ));
            return Err(diagnostics);
        }
    };
    let mut mapped: BTreeSet<String> = BTreeSet::new();
    for (index, raw) in raw_declarations.iter().enumerate() {
        let path = format!("$.declarations[{index}]");
        let Some(mapping) = raw.as_object() else {
            diagnostics.push(Diagnostic::new(
                "EXPECTED_OBJECT",
                "declaration mapping must be an object",
                &path,
            ));
            continue;
        };
        let mut unexpected: Vec<&String> = mapping
            .keys()
            .filter(|key| !matches!(key.as_str(), "declaration" | "role" | "claimRefs" | "supportsDeclarations"))
            .collect();
        unexpected.sort();
        for key in unexpected {
            diagnostics.push(Diagnostic::new(
                "UNEXPECTED_FIELD",
                format!("unsupported declaration field: {key}"),
                format!("{path}.{key}"),
            ));
        }
        match mapping.get("declaration").and_then(Value::as_str) {
            Some(name) if is_lean_name(name) => {
                if !present.contains_key(name) {
                    diagnostics.push(Diagnostic::new(
                        "MISSING_DECLARATION",
                        format!("leanSource does not define the mapped declaration: {name}"),
                        format!("{path}.declaration"),
                    ));
                } else if !mapped.insert(name.to_string()) {
                    diagnostics.push(Diagnostic::new(
                        "DUPLICATE_DECLARATION",
                        format!("declaration is mapped more than once: {name}"),
                        format!("{path}.declaration"),
                    ));
                }
            }
            _ => diagnostics.push(Diagnostic::new(
                "INVALID_DECLARATION_NAME",
                "declaration must be a dotted Lean identifier",
                format!("{path}.declaration"),
            )),
        }
        // A core declaration must trace to a claim from a unit that actually
        // needs this concept — otherwise the core is asserting something no
        // unit asked for.
        match mapping.get("claimRefs") {
            Some(Value::Array(refs)) if !refs.is_empty() => {
                for (ref_index, reference) in refs.iter().enumerate() {
                    let ref_path = format!("{path}.claimRefs[{ref_index}]");
                    match (
                        reference.get("unitId").and_then(Value::as_str),
                        reference.get("claimId").and_then(Value::as_str),
                    ) {
                        (Some(unit_id), Some(claim_id))
                            if allowed_claims.contains(&(unit_id, claim_id)) => {}
                        (Some(unit_id), Some(claim_id)) => diagnostics.push(Diagnostic::new(
                            "UNKNOWN_CLAIM_REF",
                            format!(
                                "claim reference does not describe any required shared concept: {unit_id}/{claim_id}"
                            ),
                            ref_path,
                        )),
                        _ => diagnostics.push(Diagnostic::new(
                            "INVALID_CLAIM_REF",
                            "claim reference needs a unitId and a claimId",
                            ref_path,
                        )),
                    }
                }
            }
            _ => diagnostics.push(Diagnostic::new(
                "MISSING_CLAIM_REFS",
                "every core declaration must cite at least one semantic claim",
                format!("{path}.claimRefs"),
            )),
        }
    }
    let unmapped: Vec<&String> = present.keys().filter(|name| !mapped.contains(*name)).collect();
    if !unmapped.is_empty() {
        diagnostics.push(Diagnostic::new(
            "UNMAPPED_DECLARATION",
            format!(
                "leanSource defines declarations that are not mapped: {}",
                unmapped.iter().map(|name| name.as_str()).collect::<Vec<_>>().join(", ")
            ),
            "$.declarations",
        ));
    }

    // ---- concepts --------------------------------------------------------
    let raw_concepts = check_array(object.get("concepts"), "$.concepts", &mut diagnostics);
    let mut registered: BTreeMap<&str, Vec<String>> = BTreeMap::new();
    for (index, raw) in raw_concepts.iter().enumerate() {
        let path = format!("$.concepts[{index}]");
        let Some(concept) = raw.as_object() else {
            diagnostics.push(Diagnostic::new("EXPECTED_OBJECT", "concept must be an object", &path));
            continue;
        };
        let Some(dependency_id) = concept.get("dependencyId").and_then(Value::as_str) else {
            diagnostics.push(Diagnostic::new(
                "INVALID_DEPENDENCY_ID",
                "dependencyId must be a shared:* identifier",
                format!("{path}.dependencyId"),
            ));
            continue;
        };
        if !requirements.iter().any(|item| item.dependency_id == dependency_id) {
            diagnostics.push(Diagnostic::new(
                "UNKNOWN_SHARED_CONCEPT",
                format!("this core is not required to represent {dependency_id}"),
                format!("{path}.dependencyId"),
            ));
            continue;
        }
        if registered.contains_key(dependency_id) {
            diagnostics.push(Diagnostic::new(
                "DUPLICATE_SHARED_CONCEPT",
                format!("concept appears more than once: {dependency_id}"),
                format!("{path}.dependencyId"),
            ));
            continue;
        }
        let names: Vec<String> = concept
            .get("leanDeclarations")
            .and_then(Value::as_array)
            .map(|items| items.iter().filter_map(Value::as_str).map(str::to_string).collect())
            .unwrap_or_default();
        if names.is_empty() {
            diagnostics.push(Diagnostic::new(
                "MISSING_CONCEPT_REPRESENTATION",
                format!("{dependency_id} needs at least one Lean declaration"),
                format!("{path}.leanDeclarations"),
            ));
        }
        for name in &names {
            // Registering a declaration that is not in the file, or not
            // mapped, would freeze a reference nothing can resolve.
            if !present.contains_key(name.as_str()) {
                diagnostics.append(&mut vec![Diagnostic::new(
                    "MISSING_DECLARATION",
                    format!("registered declaration is not defined in leanSource: {name}"),
                    format!("{path}.leanDeclarations"),
                )]);
            } else if !mapped.contains(name.as_str()) {
                diagnostics.push(Diagnostic::new(
                    "UNMAPPED_CONCEPT_DECLARATION",
                    format!("registered declaration is not mapped to any claim: {name}"),
                    format!("{path}.leanDeclarations"),
                ));
            }
        }
        registered.insert(dependency_id, names);
    }

    let missing: Vec<&str> = requirements
        .iter()
        .map(|item| item.dependency_id.as_str())
        .filter(|id| !registered.contains_key(id))
        .collect();
    if !missing.is_empty() {
        diagnostics.push(Diagnostic::new(
            "MISSING_SHARED_CONCEPT",
            format!(
                "the core must represent every required shared concept; missing: {}",
                missing.join(", ")
            ),
            "$.concepts",
        ));
    }

    if !diagnostics.is_empty() {
        return Err(diagnostics);
    }

    // Rebuild the registry from the requirements so the frozen record carries
    // the full concept metadata rather than only what the generator sent.
    let concepts: Vec<Value> = requirements
        .iter()
        .map(|requirement| {
            let names = registered
                .get(requirement.dependency_id.as_str())
                .cloned()
                .unwrap_or_default();
            requirement.concept(&names)
        })
        .collect();
    Ok(AcceptedCore {
        lean_source: lean_source.to_string(),
        concepts: json!(concepts),
        declarations: json!(raw_declarations),
    })
}

fn check_array<'v>(
    value: Option<&'v Value>,
    path: &str,
    diagnostics: &mut Vec<Diagnostic>,
) -> Vec<&'v Value> {
    match value {
        Some(Value::Array(items)) => items.iter().collect(),
        _ => {
            diagnostics.push(Diagnostic::new("EXPECTED_ARRAY", format!("{path} must be an array"), path));
            Vec::new()
        }
    }
}
