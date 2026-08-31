use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Map, Value};
use spec2lean_specdb::normalize_text;

use crate::model::{ClaimKind, Diagnostic, DiagnosticCode as Code, RestrictionKind, UnitKind};
use crate::scope::SemanticScope;

const SUCCESS_FIELDS: &[&str] = &[
    "outcome", "unitKind", "identity", "syntaxForms", "inputs", "result", "operation",
    "edgeCases", "stateEffects", "predication", "restrictions", "dependencies", "claims",
];
const FAILURE_FIELDS: &[&str] = &["outcome", "missingAspects", "explanation", "evidenceIds"];

/// Allowed fields per component kind. Anything else is a semantic field the
/// extractor invented, which is rejected rather than silently carried into the
/// artifact.
fn component_fields(kind: &str) -> &'static [&'static str] {
    match kind {
        "identity" => &["name", "form", "description", "evidenceIds"],
        "syntax" => &["form", "description", "evidenceIds"],
        "input" => &["name", "role", "description", "constraints", "evidenceIds"],
        "result" => &["name", "description", "constraints", "evidenceIds"],
        "operation" => &["description", "inputs", "result", "branches", "evidenceIds"],
        "branch" | "edge" => &["condition", "behavior", "evidenceIds"],
        "state" => &["target", "effect", "evidenceIds"],
        "predication" => &["guard", "whenTrue", "whenFalse", "evidenceIds"],
        "restriction" => &["kind", "description", "evidenceIds"],
        "dependency" => &[
            "dependencyId", "concept", "description", "artifactId", "semanticClaimIds",
            "evidenceIds",
        ],
        "claim" => &["claimId", "kind", "statement", "evidenceIds"],
        _ => &[],
    }
}

struct Checker<'a> {
    diagnostics: Vec<Diagnostic>,
    allowed_evidence: BTreeSet<&'a str>,
}

impl<'a> Checker<'a> {
    fn push(&mut self, code: Code, message: impl Into<String>, path: impl Into<String>) {
        self.diagnostics.push(Diagnostic::new(code, message, path));
    }

    fn object<'v>(&mut self, value: &'v Value, path: &str) -> Option<&'v Map<String, Value>> {
        match value.as_object() {
            Some(object) => Some(object),
            None => {
                self.push(Code::ExpectedObject, "value must be an object", path);
                None
            }
        }
    }

    fn list<'v>(&mut self, value: Option<&'v Value>, path: &str) -> Vec<&'v Value> {
        match value {
            None => Vec::new(),
            Some(Value::Array(items)) => items.iter().collect(),
            Some(_) => {
                self.push(Code::ExpectedArray, "value must be an array", path);
                Vec::new()
            }
        }
    }

    fn fields(&mut self, value: &Map<String, Value>, allowed: &[&str], path: &str) {
        let mut unexpected: Vec<&String> = value
            .keys()
            .filter(|key| !allowed.contains(&key.as_str()))
            .collect();
        unexpected.sort();
        for key in unexpected {
            self.push(
                Code::UnexpectedField,
                format!("unsupported semantic field: {key}"),
                format!("{path}.{key}"),
            );
        }
    }

    fn text(&mut self, value: Option<&Value>, path: &str, minimum: usize) {
        let ok = value
            .and_then(Value::as_str)
            .is_some_and(|text| normalize_text(text).chars().count() >= minimum);
        if !ok {
            self.push(
                Code::InvalidText,
                format!("must be non-empty semantic text (minimum {minimum} characters)"),
                path,
            );
        }
    }

    fn texts(&mut self, value: &Map<String, Value>, names: &[&str], path: &str) {
        for name in names {
            self.text(value.get(*name), &format!("{path}.{name}"), 1);
        }
    }

    /// Every cited ID must come from this unit's bundle. This is what stops a
    /// claim from being attached to evidence that was never retrieved.
    fn evidence_ids(&mut self, value: Option<&Value>, path: &str, required: bool) -> Vec<String> {
        let items = match value {
            None => return Vec::new(),
            Some(Value::Array(items)) if items.iter().all(Value::is_string) => items,
            Some(_) => {
                self.push(
                    Code::InvalidEvidenceIds,
                    "evidenceIds must be an array of strings",
                    path,
                );
                return Vec::new();
            }
        };
        let ids: Vec<String> = items
            .iter()
            .filter_map(Value::as_str)
            .map(str::to_string)
            .collect();
        if required && ids.is_empty() {
            self.push(Code::MissingEvidence, "at least one evidence ID is required", path);
        }
        if ids.iter().collect::<BTreeSet<_>>().len() != ids.len() {
            self.push(
                Code::DuplicateEvidenceId,
                "evidenceIds contains a duplicate",
                path,
            );
        }
        for id in &ids {
            if !self.allowed_evidence.contains(id.as_str()) {
                self.push(
                    Code::UnknownEvidenceId,
                    format!("evidence ID is not in this unit bundle: {id}"),
                    path,
                );
            }
        }
        ids
    }

    fn component<'v>(
        &mut self,
        raw: &'v Value,
        kind: &str,
        path: &str,
        evidence_required: bool,
    ) -> Option<&'v Map<String, Value>> {
        let value = self.object(raw, path)?;
        self.fields(value, component_fields(kind), path);
        self.evidence_ids(
            value.get("evidenceIds"),
            &format!("{path}.evidenceIds"),
            evidence_required,
        );
        Some(value)
    }

    /// String constraint arrays appear on inputs and results and must be
    /// non-empty strings, never nulls or nested structures.
    fn constraints(&mut self, value: Option<&Value>, path: &str) {
        let ok = value.and_then(Value::as_array).is_some_and(|items| {
            items.iter().all(|item| {
                item.as_str()
                    .is_some_and(|text| !normalize_text(text).is_empty())
            })
        });
        if !ok {
            self.push(
                Code::InvalidConstraints,
                "constraints must be an array of non-empty strings",
                path,
            );
        }
    }
}

/// Every `resolution:` ID referenced anywhere in the submission.
///
/// Walks the whole tree, because a non-normative source cited in any component
/// must still be accounted for by an ASSUMPTION claim.
fn resolution_references(value: &Value, found: &mut BTreeSet<String>) {
    match value {
        Value::Object(object) => {
            if let Some(Value::Array(ids)) = object.get("evidenceIds") {
                for id in ids.iter().filter_map(Value::as_str) {
                    if id.starts_with("resolution:") {
                        found.insert(id.to_string());
                    }
                }
            }
            for item in object.values() {
                resolution_references(item, found);
            }
        }
        Value::Array(items) => {
            for item in items {
                resolution_references(item, found);
            }
        }
        _ => {}
    }
}

/// Validate a submission and, if clean, build the deterministic artifact.
pub fn validate_submission(
    scope: &SemanticScope,
    bundle: &Value,
    submission: &Value,
    extractor: &Value,
) -> Result<Value, Vec<Diagnostic>> {
    let allowed_evidence: BTreeSet<&str> = scope
        .evidence_ids
        .iter()
        .map(String::as_str)
        .collect();
    let mut check = Checker {
        diagnostics: Vec::new(),
        allowed_evidence,
    };

    let Some(value) = check.object(submission, "$") else {
        return Err(check.diagnostics);
    };
    let outcome = value.get("outcome").and_then(Value::as_str);

    // Evidence source types, used by the dual-rendition claim rule.
    let records = bundle
        .get("evidence")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default();
    let evidence_source_types: BTreeMap<&str, &str> = records
        .iter()
        .filter_map(|item| {
            Some((
                item.get("evidenceId")?.as_str()?,
                item.get("sourceType")?.as_str()?,
            ))
        })
        .collect();
    let official: BTreeSet<&str> = evidence_source_types
        .values()
        .copied()
        .filter(|value| matches!(*value, "html" | "pdf"))
        .collect();
    let dual_source = official.len() == 2;

    if outcome == Some("INSUFFICIENT_EVIDENCE") {
        check.fields(value, FAILURE_FIELDS, "$");
        let missing = check.list(value.get("missingAspects"), "$.missingAspects");
        if missing.is_empty() {
            check.push(
                Code::MissingAspect,
                "at least one missing semantic aspect is required",
                "$.missingAspects",
            );
        }
        let mut normalized: Vec<String> = Vec::new();
        for (index, item) in missing.iter().enumerate() {
            match item.as_str().map(normalize_text) {
                Some(text) if !text.is_empty() => normalized.push(text),
                _ => check.push(
                    Code::InvalidText,
                    "missing aspect must be non-empty",
                    format!("$.missingAspects[{index}]"),
                ),
            }
        }
        if normalized.iter().collect::<BTreeSet<_>>().len() != normalized.len() {
            check.push(
                Code::DuplicateMissingAspect,
                "missingAspects must contain unique normalized questions",
                "$.missingAspects",
            );
        }
        check.text(value.get("explanation"), "$.explanation", 1);
        check.evidence_ids(value.get("evidenceIds"), "$.evidenceIds", false);
        return if check.diagnostics.is_empty() {
            Ok(scope.artifact(submission, extractor))
        } else {
            Err(check.diagnostics)
        };
    }
    if outcome != Some("SUCCESS") {
        check.push(
            Code::InvalidOutcome,
            "outcome must be SUCCESS or INSUFFICIENT_EVIDENCE",
            "$.outcome",
        );
        return Err(check.diagnostics);
    }

    check.fields(value, SUCCESS_FIELDS, "$");
    let unit_kind = value
        .get("unitKind")
        .and_then(|value| serde_json::from_value::<UnitKind>(value.clone()).ok());
    if unit_kind.is_none() {
        check.push(
            Code::InvalidUnitKind,
            format!(
                "unitKind must be one of {:?}",
                UnitKind::ALL.map(UnitKind::as_str)
            ),
            "$.unitKind",
        );
    }

    // Identity is mandatory for every unit kind: an artifact that does not say
    // what it describes is not an artifact.
    let identity = value.get("identity").unwrap_or(&Value::Null);
    if let Some(identity) = check.component(identity, "identity", "$.identity", true) {
        let identity = identity.clone();
        check.text(identity.get("name"), "$.identity.name", 1);
        // The extracted identity must name the unit the plan asked for, or the
        // artifact silently describes something else.
        if identity.get("name") != scope.unit.get("name") {
            check.push(
                Code::WrongIdentity,
                "identity.name must exactly match the planned unit name",
                "$.identity.name",
            );
        }
    }

    for (field, kind, texts) in [
        ("syntaxForms", "syntax", &["form"][..]),
        ("inputs", "input", &["name", "role", "description"]),
        ("edgeCases", "edge", &["condition", "behavior"]),
        ("stateEffects", "state", &["target", "effect"]),
        ("restrictions", "restriction", &["description"]),
    ] {
        let items = check.list(value.get(field), &format!("$.{field}"));
        for (index, raw) in items.iter().enumerate() {
            let path = format!("$.{field}[{index}]");
            let Some(item) = check.component(raw, kind, &path, true) else {
                continue;
            };
            let item = item.clone();
            check.texts(&item, texts, &path);
            if kind == "restriction"
                && item
                    .get("kind")
                    .and_then(|value| serde_json::from_value::<RestrictionKind>(value.clone()).ok())
                    .is_none()
            {
                check.push(
                    Code::InvalidRestrictionKind,
                    format!(
                        "kind must be one of {:?}",
                        RestrictionKind::ALL.map(RestrictionKind::as_str)
                    ),
                    format!("{path}.kind"),
                );
            }
            if kind == "input" {
                check.constraints(item.get("constraints"), &format!("{path}.constraints"));
            }
        }
    }

    // `result` is optional here, and required only for instructions further
    // down. This is a deliberate divergence from the Python implementation,
    // which validated `result` unconditionally and so reported EXPECTED_OBJECT
    // for every LANGUAGE_CONSTRUCT and SHARED_CONCEPT unit — pushing the
    // extractor to invent a result for concepts that have none, and making its
    // own MISSING_RESULT diagnostic unreachable.
    let result_present = match value.get("result") {
        None => false,
        Some(raw) => {
            if let Some(result) = check.component(raw, "result", "$.result", true) {
                let result = result.clone();
                check.texts(&result, &["name", "description"], "$.result");
                check.constraints(result.get("constraints"), "$.result.constraints");
                true
            } else {
                false
            }
        }
    };

    let mut operation_evidence: Vec<String> = Vec::new();
    let operation_present = match value.get("operation") {
        None => false,
        Some(raw) => {
            if let Some(operation) = check.component(raw, "operation", "$.operation", true) {
                let operation = operation.clone();
                operation_evidence = operation
                    .get("evidenceIds")
                    .and_then(Value::as_array)
                    .map(|items| {
                        items
                            .iter()
                            .filter_map(Value::as_str)
                            .map(str::to_string)
                            .collect()
                    })
                    .unwrap_or_default();
                // A twelve-character floor: enough to reject "adds them".
                check.text(operation.get("description"), "$.operation.description", 12);
                let names_ok = operation
                    .get("inputs")
                    .and_then(Value::as_array)
                    .is_some_and(|items| {
                        !items.is_empty()
                            && items.iter().all(|item| {
                                item.as_str()
                                    .is_some_and(|text| !normalize_text(text).is_empty())
                            })
                    });
                if !names_ok {
                    check.push(
                        Code::MissingOperationInputs,
                        "operation.inputs must name at least one input",
                        "$.operation.inputs",
                    );
                }
                check.text(operation.get("result"), "$.operation.result", 1);
                let branches = check.list(operation.get("branches"), "$.operation.branches");
                for (index, raw) in branches.iter().enumerate() {
                    let path = format!("$.operation.branches[{index}]");
                    if let Some(branch) = check.component(raw, "branch", &path, true) {
                        let branch = branch.clone();
                        check.texts(&branch, &["condition", "behavior"], &path);
                    }
                }
                true
            } else {
                false
            }
        }
    };

    // An instruction must actually describe an instruction: inputs, a result,
    // and an operation grounded in OPERATION or ALGORITHM evidence.
    let mut evidence_roles: BTreeMap<&str, &str> = records
        .iter()
        .filter_map(|item| {
            Some((item.get("evidenceId")?.as_str()?, item.get("role")?.as_str()?))
        })
        .collect();
    for item in bundle
        .get("resolutions")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
    {
        if let (Some(id), Some(role)) = (
            item.get("resolutionId").and_then(Value::as_str),
            item.get("role").and_then(Value::as_str),
        ) {
            evidence_roles.insert(id, role);
        }
    }
    let functional = |role: &str| matches!(role, "OPERATION" | "ALGORITHM");
    let is_instruction = unit_kind == Some(UnitKind::Instruction)
        || evidence_roles.values().any(|role| functional(role));
    if is_instruction {
        if !operation_present {
            check.push(
                Code::MissingOperation,
                "instruction semantics require a core operation",
                "$.operation",
            );
        } else if !operation_evidence
            .iter()
            .any(|id| evidence_roles.get(id.as_str()).is_some_and(|role| functional(role)))
        {
            check.push(
                Code::NonfunctionalOperation,
                "instruction operation must cite OPERATION or ALGORITHM evidence",
                "$.operation.evidenceIds",
            );
        }
        if !result_present {
            check.push(
                Code::MissingResult,
                "instruction semantics require a result",
                "$.result",
            );
        }
        let has_inputs = value
            .get("inputs")
            .and_then(Value::as_array)
            .is_some_and(|items| !items.is_empty());
        if !has_inputs {
            check.push(
                Code::MissingInputs,
                "instruction semantics require inputs",
                "$.inputs",
            );
        }
    }

    if let Some(raw) = value.get("predication")
        && let Some(predication) = check.component(raw, "predication", "$.predication", true)
    {
        let predication = predication.clone();
        check.texts(
            &predication,
            &["guard", "whenTrue", "whenFalse"],
            "$.predication",
        );
    }

    // Shared dependencies: every relevant Phase-2 prerequisite must be bound
    // exactly once, by exact ID and exact name, to at least one local claim.
    let relevant_shared: BTreeMap<&str, &Value> = scope
        .shared_prerequisites
        .iter()
        .filter_map(|item| Some((item.get("dependencyId")?.as_str()?, item)))
        .collect();
    let mut seen_shared: BTreeSet<String> = BTreeSet::new();
    let mut dependency_claims: Vec<(String, Vec<String>)> = Vec::new();

    let dependencies = check.list(value.get("dependencies"), "$.dependencies");
    for (index, raw) in dependencies.iter().enumerate() {
        let path = format!("$.dependencies[{index}]");
        let Some(item) = check.component(raw, "dependency", &path, false) else {
            continue;
        };
        let item = item.clone();
        check.texts(&item, &["concept", "description"], &path);

        let mut semantic_claim_ids: Vec<String> = Vec::new();
        match item.get("semanticClaimIds") {
            None => {}
            Some(Value::Array(items)) => {
                for (claim_index, raw_claim) in items.iter().enumerate() {
                    let claim_path = format!("{path}.semanticClaimIds[{claim_index}]");
                    match raw_claim.as_str() {
                        Some(claim_id) if claim_id.starts_with("claim:") => {
                            if semantic_claim_ids.iter().any(|seen| seen == claim_id) {
                                check.push(
                                    Code::DuplicateSemanticClaimId,
                                    format!("dependency repeats semantic claim ID: {claim_id}"),
                                    claim_path,
                                );
                            } else {
                                semantic_claim_ids.push(claim_id.to_string());
                            }
                        }
                        _ => check.push(
                            Code::InvalidSemanticClaimId,
                            "semantic claim ID must start with claim:",
                            claim_path,
                        ),
                    }
                }
            }
            Some(_) => check.push(
                Code::InvalidSemanticClaimIds,
                "semanticClaimIds must be an array of claim IDs",
                format!("{path}.semanticClaimIds"),
            ),
        }

        if let Some(raw_id) = item.get("dependencyId") {
            match raw_id.as_str() {
                Some(dependency_id) if dependency_id.starts_with("shared:") => {
                    if let Some(planned) = relevant_shared.get(dependency_id) {
                        if !seen_shared.insert(dependency_id.to_string()) {
                            check.push(
                                Code::DuplicateSharedDependency,
                                format!(
                                    "shared dependency appears more than once: {dependency_id}"
                                ),
                                format!("{path}.dependencyId"),
                            );
                        } else if item.get("concept") != planned.get("name") {
                            check.push(
                                Code::SharedDependencyNameMismatch,
                                "linked dependency concept must exactly match its Phase-2 name",
                                format!("{path}.concept"),
                            );
                        }
                    } else {
                        check.push(
                            Code::UnknownSharedDependency,
                            format!(
                                "dependency is not a relevant Phase-2 shared prerequisite: {dependency_id}"
                            ),
                            format!("{path}.dependencyId"),
                        );
                    }
                }
                _ => check.push(
                    Code::InvalidSharedDependencyId,
                    "dependencyId must start with shared:",
                    format!("{path}.dependencyId"),
                ),
            }
            if semantic_claim_ids.is_empty() {
                check.push(
                    Code::MissingSharedDependencyClaims,
                    "a linked shared dependency requires at least one semanticClaimId",
                    format!("{path}.semanticClaimIds"),
                );
            }
        }
        dependency_claims.push((path, semantic_claim_ids));
    }

    // Claims.
    let mut claim_ids: BTreeSet<String> = BTreeSet::new();
    let mut claim_meanings: BTreeSet<(String, String)> = BTreeSet::new();
    let mut assumption_resolutions: BTreeSet<String> = BTreeSet::new();

    let claims = check.list(value.get("claims"), "$.claims");
    for (index, raw) in claims.iter().enumerate() {
        let path = format!("$.claims[{index}]");
        let Some(item) = check.component(raw, "claim", &path, false) else {
            continue;
        };
        let item = item.clone();

        let claim_id = item.get("claimId").and_then(Value::as_str);
        match claim_id {
            Some(id) if id.starts_with("claim:") => {
                if claim_ids.contains(id) {
                    check.push(
                        Code::DuplicateClaimId,
                        format!("duplicate claim ID: {id}"),
                        format!("{path}.claimId"),
                    );
                }
                claim_ids.insert(id.to_string());
            }
            _ => {
                check.push(
                    Code::InvalidClaimId,
                    "claimId must start with claim:",
                    format!("{path}.claimId"),
                );
                if let Some(id) = claim_id {
                    claim_ids.insert(id.to_string());
                }
            }
        }

        let kind = item
            .get("kind")
            .and_then(|value| serde_json::from_value::<ClaimKind>(value.clone()).ok());
        if kind.is_none() {
            check.push(
                Code::InvalidClaimKind,
                format!(
                    "kind must be one of {:?}",
                    ClaimKind::ALL.map(ClaimKind::as_str)
                ),
                format!("{path}.kind"),
            );
        }
        check.text(item.get("statement"), &format!("{path}.statement"), 1);

        // Two claims that say the same thing with the same authority are one
        // claim; catching that keeps the artifact honest about its own size.
        let statement = item
            .get("statement")
            .and_then(Value::as_str)
            .map(|text| normalize_text(text).to_lowercase())
            .unwrap_or_default();
        let kind_label = kind
            .map(|kind| kind.as_str().to_string())
            .unwrap_or_else(|| {
                item.get("kind")
                    .and_then(Value::as_str)
                    .unwrap_or("None")
                    .to_string()
            });
        if !statement.is_empty()
            && !claim_meanings.insert((kind_label.clone(), statement.clone()))
        {
            check.push(Code::DuplicateClaim, "duplicate semantic claim", &path);
        }

        let cited: Vec<&str> = item
            .get("evidenceIds")
            .and_then(Value::as_array)
            .map(|items| items.iter().filter_map(Value::as_str).collect())
            .unwrap_or_default();

        if kind.is_some_and(ClaimKind::is_factual) {
            if cited.is_empty() {
                check.push(
                    Code::MissingEvidence,
                    "SOURCE_FACT and DERIVED_INTERPRETATION claims require evidence",
                    format!("{path}.evidenceIds"),
                );
            }
            if dual_source {
                let cited_types: BTreeSet<&str> = cited
                    .iter()
                    .filter_map(|id| evidence_source_types.get(id).copied())
                    .collect();
                let missing: Vec<&str> = official
                    .iter()
                    .copied()
                    .filter(|value| !cited_types.contains(value))
                    .collect();
                if !missing.is_empty() {
                    check.push(
                        Code::MissingClaimRendition,
                        format!(
                            "a factual claim in a dual-source bundle must cite supporting HTML and PDF evidence; missing: {}",
                            missing.join(", ")
                        ),
                        format!("{path}.evidenceIds"),
                    );
                }
            }
        }

        // A claim resting on a non-normative resolution is an assumption, and
        // must say so. This is the rule that keeps internet or model-supplied
        // answers from being laundered into specification facts.
        let resolution_refs: Vec<String> = cited
            .iter()
            .filter(|id| id.starts_with("resolution:"))
            .map(|id| (*id).to_string())
            .collect();
        if !resolution_refs.is_empty() && kind != Some(ClaimKind::Assumption) {
            check.push(
                Code::NonNormativeClaimKind,
                "claims using internet, runtime, or LLM resolutions must be classified ASSUMPTION",
                format!("{path}.kind"),
            );
        }
        if kind == Some(ClaimKind::Assumption) {
            assumption_resolutions.extend(resolution_refs);
        }
    }

    if claims.is_empty() {
        check.push(
            Code::MissingClaims,
            "at least one structured semantic claim is required",
            "$.claims",
        );
    }

    for (path, semantic_claim_ids) in &dependency_claims {
        for (index, claim_id) in semantic_claim_ids.iter().enumerate() {
            if !claim_ids.contains(claim_id) {
                check.push(
                    Code::UnknownSemanticClaimId,
                    format!("dependency references a claim not defined by this artifact: {claim_id}"),
                    format!("{path}.semanticClaimIds[{index}]"),
                );
            }
        }
    }

    let missing_shared: Vec<&str> = relevant_shared
        .keys()
        .copied()
        .filter(|id| !seen_shared.contains(*id))
        .collect();
    if !missing_shared.is_empty() {
        check.push(
            Code::MissingSharedDependency,
            format!(
                "semantic artifact is missing relevant Phase-2 shared dependencies: {}",
                missing_shared.join(", ")
            ),
            "$.dependencies",
        );
    }

    let mut used_resolutions = BTreeSet::new();
    resolution_references(submission, &mut used_resolutions);
    let unclassified: Vec<&String> = used_resolutions
        .difference(&assumption_resolutions)
        .collect();
    if !unclassified.is_empty() {
        check.push(
            Code::UnmappedNonNormativeResolution,
            format!(
                "every used non-normative resolution must be cited by an ASSUMPTION claim: {}",
                unclassified
                    .iter()
                    .map(|value| value.as_str())
                    .collect::<Vec<_>>()
                    .join(", ")
            ),
            "$.claims",
        );
    }

    if check.diagnostics.is_empty() {
        Ok(scope.artifact(submission, extractor))
    } else {
        Err(check.diagnostics)
    }
}
