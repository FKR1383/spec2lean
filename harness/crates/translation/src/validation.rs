use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::{Value, json};

use crate::scope::TranslationScope;
use crate::source::{FORBIDDEN, contains_word, declarations, is_lean_name, without_comments_and_strings};

pub const DECLARATION_ROLES: &[&str] = &[
    "PRIMARY_TYPE",
    "OPERATION",
    "EXECUTION",
    "BRANCH_HELPER",
    "EDGE_CASE_HELPER",
    "SEMANTIC_HELPER",
    "IMPLEMENTATION_HELPER",
];

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

/// Structural validation of one group submission.
///
/// This runs *before* the compiler. It answers the questions the compiler
/// cannot: does every declaration the translator claims to have written
/// actually exist in the source, is every declaration in the source accounted
/// for, and does every claim reference point at a claim Phase 4 actually made.
/// A file can compile perfectly and still fail all three.
pub fn validate_submission(
    scope: &TranslationScope,
    submission: &Value,
) -> Result<Value, Vec<Diagnostic>> {
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
        .filter(|key| !matches!(key.as_str(), "leanSource" | "declarations" | "sharedUses"))
        .collect();
    unexpected.sort();
    for key in unexpected {
        diagnostics.push(Diagnostic::new(
            "UNEXPECTED_FIELD",
            format!("unsupported submission field: {key}"),
            format!("$.{key}"),
        ));
    }

    let Some(lean_source) = object.get("leanSource").and_then(Value::as_str) else {
        diagnostics.push(Diagnostic::new(
            "INVALID_SOURCE",
            "leanSource must be a non-empty string",
            "$.leanSource",
        ));
        return Err(diagnostics);
    };
    if lean_source.trim().is_empty() {
        diagnostics.push(Diagnostic::new(
            "INVALID_SOURCE",
            "leanSource must be a non-empty string",
            "$.leanSource",
        ));
        return Err(diagnostics);
    }

    // Escape hatches make a formalization assert nothing; reject before build.
    let clean = without_comments_and_strings(lean_source);
    for (code, word, message) in FORBIDDEN {
        if contains_word(&clean, word) {
            diagnostics.push(Diagnostic::new(code, *message, "$.leanSource"));
        }
    }

    let present = declarations(lean_source);
    let allowed_claims: BTreeSet<(&str, &str)> = scope
        .claim_refs
        .iter()
        .map(|(unit_id, claim_id)| (unit_id.as_str(), claim_id.as_str()))
        .collect();

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
    let mut covered_claims: BTreeSet<(String, String)> = BTreeSet::new();
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
            .filter(|key| {
                !matches!(
                    key.as_str(),
                    "declaration" | "role" | "claimRefs" | "supportsDeclarations"
                )
            })
            .collect();
        unexpected.sort();
        for key in unexpected {
            diagnostics.push(Diagnostic::new(
                "UNEXPECTED_FIELD",
                format!("unsupported declaration field: {key}"),
                format!("{path}.{key}"),
            ));
        }

        let name = mapping.get("declaration").and_then(Value::as_str);
        match name {
            Some(name) if is_lean_name(name) => {
                if !present.contains_key(name) {
                    // The translator named something the source does not define.
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

        if !mapping
            .get("role")
            .and_then(Value::as_str)
            .is_some_and(|role| DECLARATION_ROLES.contains(&role))
        {
            diagnostics.push(Diagnostic::new(
                "INVALID_ROLE",
                format!("role must be one of {DECLARATION_ROLES:?}"),
                format!("{path}.role"),
            ));
        }

        match mapping.get("claimRefs") {
            Some(Value::Array(refs)) if !refs.is_empty() => {
                for (ref_index, reference) in refs.iter().enumerate() {
                    let ref_path = format!("{path}.claimRefs[{ref_index}]");
                    let unit_id = reference.get("unitId").and_then(Value::as_str);
                    let claim_id = reference.get("claimId").and_then(Value::as_str);
                    match (unit_id, claim_id) {
                        (Some(unit_id), Some(claim_id))
                            if allowed_claims.contains(&(unit_id, claim_id)) =>
                        {
                            covered_claims.insert((unit_id.to_string(), claim_id.to_string()));
                        }
                        (Some(unit_id), Some(claim_id)) => diagnostics.push(Diagnostic::new(
                            "UNKNOWN_CLAIM_REF",
                            format!(
                                "claim reference is not in this group's semantics: {unit_id}/{claim_id}"
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
                "every declaration must cite at least one semantic claim",
                format!("{path}.claimRefs"),
            )),
        }

        // A malformed optional array is a mistake, not an absence: treating
        // `"supportsDeclarations": 42` as an empty list accepts a submission
        // whose author meant something.
        match mapping.get("supportsDeclarations") {
            None => {}
            Some(Value::Array(supports)) => {
                for (support_index, support) in supports.iter().enumerate() {
                    if !support.as_str().is_some_and(is_lean_name) {
                        diagnostics.push(Diagnostic::new(
                            "INVALID_DECLARATION_NAME",
                            "supportsDeclarations entries must be dotted Lean identifiers",
                            format!("{path}.supportsDeclarations[{support_index}]"),
                        ));
                    }
                }
            }
            Some(_) => diagnostics.push(Diagnostic::new(
                "EXPECTED_ARRAY",
                "supportsDeclarations must be an array",
                format!("{path}.supportsDeclarations"),
            )),
        }
    }

    // Every declaration in the file must be accounted for, or the manifest
    // understates what the translation actually asserts.
    let unmapped: Vec<&String> = present.keys().filter(|name| !mapped.contains(*name)).collect();
    if !unmapped.is_empty() {
        diagnostics.push(Diagnostic::new(
            "UNMAPPED_DECLARATION",
            format!(
                "leanSource defines declarations that are not mapped: {}",
                unmapped
                    .iter()
                    .map(|name| name.as_str())
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
            "$.declarations",
        ));
    }

    // Forward coverage: every claim Phase 4 made must reach the Lean.
    let uncovered: Vec<String> = scope
        .claim_refs
        .iter()
        .filter(|(unit_id, claim_id)| {
            !covered_claims.contains(&(unit_id.clone(), claim_id.clone()))
        })
        .map(|(unit_id, claim_id)| format!("{unit_id}/{claim_id}"))
        .collect();
    if !uncovered.is_empty() {
        diagnostics.push(Diagnostic::new(
            "UNCOVERED_CLAIM",
            format!(
                "every semantic claim must be represented by at least one declaration; missing: {}",
                uncovered.join(", ")
            ),
            "$.declarations",
        ));
    }

    // ---- shared uses -----------------------------------------------------
    // Every shared concept this group depends on must be bound to declarations
    // the frozen core actually registered. Without this a group could define
    // its own version of a concept its siblings import from the core, and the
    // two would agree only by luck.
    let required = scope.shared_dependency_ids();
    let raw_uses: Vec<&Value> = match object.get("sharedUses") {
        None => Vec::new(),
        Some(Value::Array(items)) => items.iter().collect(),
        Some(_) => {
            diagnostics.push(Diagnostic::new(
                "EXPECTED_ARRAY",
                "sharedUses must be an array",
                "$.sharedUses",
            ));
            Vec::new()
        }
    };
    let mut bound: BTreeSet<String> = BTreeSet::new();
    for (index, raw) in raw_uses.iter().enumerate() {
        let path = format!("$.sharedUses[{index}]");
        let Some(use_object) = raw.as_object() else {
            diagnostics.push(Diagnostic::new("EXPECTED_OBJECT", "shared use must be an object", &path));
            continue;
        };
        let Some(dependency_id) = use_object.get("dependencyId").and_then(Value::as_str) else {
            diagnostics.push(Diagnostic::new(
                "INVALID_SHARED_USE",
                "dependencyId must be a shared:* identifier",
                format!("{path}.dependencyId"),
            ));
            continue;
        };
        if !required.contains(&dependency_id) {
            diagnostics.push(Diagnostic::new(
                "UNKNOWN_SHARED_USE",
                format!("this group does not depend on {dependency_id}"),
                format!("{path}.dependencyId"),
            ));
            continue;
        }
        if !bound.insert(dependency_id.to_string()) {
            diagnostics.push(Diagnostic::new(
                "DUPLICATE_SHARED_USE",
                format!("shared concept is bound more than once: {dependency_id}"),
                format!("{path}.dependencyId"),
            ));
            continue;
        }
        let registered: BTreeSet<&str> =
            scope.registered_declarations(dependency_id).into_iter().collect();
        let raw_used = use_object.get("leanDeclarations");
        if let Some(value) = raw_used
            && !value.is_array()
        {
            diagnostics.push(Diagnostic::new(
                "EXPECTED_ARRAY",
                "leanDeclarations must be an array",
                format!("{path}.leanDeclarations"),
            ));
            continue;
        }
        let entries = raw_used.and_then(Value::as_array).map(Vec::as_slice).unwrap_or_default();
        // A non-string entry is dropped by `filter_map`, which would let
        // `["Registered.Name", 42]` pass as though it named one declaration.
        if entries.iter().any(|item| !item.is_string()) {
            diagnostics.push(Diagnostic::new(
                "INVALID_DECLARATION_NAME",
                "every leanDeclarations entry must be a dotted Lean identifier",
                format!("{path}.leanDeclarations"),
            ));
            continue;
        }
        let used: Vec<&str> = entries.iter().filter_map(Value::as_str).collect();
        if used.is_empty() {
            diagnostics.push(Diagnostic::new(
                "MISSING_SHARED_USE_DECLARATIONS",
                format!("{dependency_id} must name at least one declaration from the frozen core"),
                format!("{path}.leanDeclarations"),
            ));
        }
        for name in used {
            if !registered.contains(name) {
                diagnostics.push(Diagnostic::new(
                    "UNREGISTERED_SHARED_DECLARATION",
                    format!(
                        "the frozen core does not register {name} for {dependency_id}; registered: {}",
                        registered.iter().copied().collect::<Vec<_>>().join(", ")
                    ),
                    format!("{path}.leanDeclarations"),
                ));
            }
        }
    }
    let unbound: Vec<&&str> = required.iter().filter(|id| !bound.contains(**id)).collect();
    if !unbound.is_empty() {
        diagnostics.push(Diagnostic::new(
            "MISSING_SHARED_USE",
            format!(
                "every shared concept this group depends on must be bound to the frozen core; missing: {}",
                unbound.iter().map(|id| **id).collect::<Vec<_>>().join(", ")
            ),
            "$.sharedUses",
        ));
    }

    // The group must actually import the core it claims to use.
    if let Some(module) = scope.core_lean_module()
        && !clean.lines().any(|line| {
            line.trim().strip_prefix("import ").is_some_and(|rest| rest.trim() == module)
        })
    {
        diagnostics.push(Diagnostic::new(
            "MISSING_CORE_IMPORT",
            format!("leanSource must import the frozen shared core: import {module}"),
            "$.leanSource",
        ));
    }

    if !diagnostics.is_empty() {
        return Err(diagnostics);
    }
    Ok(json!({
        "declarations": raw_declarations,
        "sharedUses": raw_uses,
    }))
}

/// The claim-to-declaration index, for the manifest and for tracing.
pub fn claim_index(declarations: &Value) -> BTreeMap<String, Vec<String>> {
    let mut index: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for mapping in declarations.as_array().map(Vec::as_slice).unwrap_or_default() {
        let Some(name) = mapping.get("declaration").and_then(Value::as_str) else {
            continue;
        };
        for reference in mapping
            .get("claimRefs")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            if let (Some(unit_id), Some(claim_id)) = (
                reference.get("unitId").and_then(Value::as_str),
                reference.get("claimId").and_then(Value::as_str),
            ) {
                index
                    .entry(format!("{unit_id}/{claim_id}"))
                    .or_default()
                    .push(name.to_string());
            }
        }
    }
    index
}
