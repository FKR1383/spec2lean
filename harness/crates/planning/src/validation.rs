use std::collections::{BTreeMap, BTreeSet};
use std::sync::LazyLock;

use regex::Regex;
use serde::Serialize;
use serde_json::{Map, Value, json};
use spec2lean_specdb::{NodeId, SpecDb, SpecDbError, normalize_text, stable_id};

use crate::graph::derive_processing_order;
use crate::request::ScopeMode;
use crate::scope::ResolvedScope;

pub const PLAN_SCHEMA_VERSION: u32 = 3;

static GROUP_NAME: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^[A-Z][A-Za-z0-9]{0,63}$").expect("valid"));

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

struct Checker {
    diagnostics: Vec<Diagnostic>,
}

impl Checker {
    fn push(&mut self, code: &str, message: impl Into<String>, path: impl Into<String>) {
        self.diagnostics.push(Diagnostic::new(code, message, path));
    }

    fn list<'v>(&mut self, value: Option<&'v Value>, path: &str) -> Vec<&'v Value> {
        match value {
            None => Vec::new(),
            Some(Value::Array(items)) => items.iter().collect(),
            Some(_) => {
                self.push("EXPECTED_ARRAY", format!("{path} must be an array"), path);
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
                "UNEXPECTED_FIELD",
                format!("unsupported planning field: {key}"),
                format!("{path}.{key}"),
            );
        }
    }

    /// Node IDs must exist in the index. This is the anti-invention rule for
    /// Phase 2: the planner cites structure, and every citation is checked.
    fn node_ids(
        &mut self,
        db: &SpecDb,
        values: &[&Value],
        path: &str,
    ) -> Result<Vec<String>, SpecDbError> {
        let mut result: Vec<String> = Vec::new();
        // Membership by set, not by rescanning the accumulated list: a
        // submission naming thousands of nodes should cost linear time.
        let mut seen: BTreeSet<String> = BTreeSet::new();
        for (index, value) in values.iter().enumerate() {
            let item_path = format!("{path}[{index}]");
            let raw = value.as_str().unwrap_or_default();
            match NodeId::parse(raw) {
                Err(_) => self.push(
                    "INVALID_SOURCE_NODE",
                    format!("invalid source node ID: {raw:?}"),
                    item_path,
                ),
                Ok(node_id) if !db.node_exists(&node_id)? => self.push(
                    "INVENTED_SOURCE_NODE",
                    format!("source node does not exist: {node_id}"),
                    item_path,
                ),
                Ok(node_id) if seen.contains(&node_id.to_string()) => self.push(
                    "DUPLICATE_SOURCE_NODE",
                    format!("duplicate source node: {node_id}"),
                    item_path,
                ),
                Ok(node_id) => {
                    seen.insert(node_id.to_string());
                    result.push(node_id.to_string());
                }
            }
        }
        result.sort();
        Ok(result)
    }
}

fn text(value: Option<&Value>) -> String {
    value
        .and_then(Value::as_str)
        .map(normalize_text)
        .unwrap_or_default()
}

/// Validate model-owned planning content and normalise it.
///
/// The planner owns judgement — which units, which groups, which shared
/// concepts, which dependencies, and why. Deterministic code owns identity:
/// every ID here is derived, never accepted from the model.
pub fn validate_submission(
    db: &SpecDb,
    scope: &ResolvedScope,
    submission: &Value,
) -> Result<Result<Value, Vec<Diagnostic>>, SpecDbError> {
    let mut check = Checker {
        diagnostics: Vec::new(),
    };
    let Some(object) = submission.as_object() else {
        return Ok(Err(vec![Diagnostic::new(
            "EXPECTED_OBJECT",
            "submission must be an object",
            "$",
        )]));
    };
    check.fields(
        object,
        &[
            "requestedUnitIds",
            "translationGroups",
            "externalPrerequisites",
            "sharedPrerequisites",
            "dependencies",
        ],
        "$",
    );

    let candidates = scope.candidate_by_id();
    let raw_unit_ids = check.list(object.get("requestedUnitIds"), "$.requestedUnitIds");
    let mut unit_ids: Vec<String> = Vec::new();
    for (index, value) in raw_unit_ids.iter().enumerate() {
        let path = format!("$.requestedUnitIds[{index}]");
        match value.as_str() {
            None => check.push("INVALID_UNIT_ID", "requested unit ID must be a string", path),
            Some(unit_id) if !candidates.contains_key(unit_id) => check.push(
                "OUT_OF_SCOPE_UNIT",
                format!("unit is not in resolved scope: {unit_id}"),
                path,
            ),
            Some(unit_id) if unit_ids.iter().any(|seen| seen == unit_id) => check.push(
                "DUPLICATE_UNIT",
                format!("requested unit is duplicated: {unit_id}"),
                path,
            ),
            Some(unit_id) => unit_ids.push(unit_id.to_string()),
        }
    }

    // Modes that named their units may not have that selection changed.
    let selected: BTreeSet<&str> = unit_ids.iter().map(String::as_str).collect();
    let required: BTreeSet<&str> = scope.exact_unit_ids.iter().map(String::as_str).collect();
    if !required.is_empty() && selected != required {
        let missing: Vec<&&str> = required.difference(&selected).collect();
        let extra: Vec<&&str> = selected.difference(&required).collect();
        check.push(
            "SCOPE_MISMATCH",
            format!("exact scope must be preserved; missing={missing:?}, extra={extra:?}"),
            "$.requestedUnitIds",
        );
    }
    if scope.request.mode() == ScopeMode::InstructionFamily && selected.is_empty() {
        check.push(
            "EMPTY_FAMILY_SELECTION",
            "family planning must select at least one candidate unit",
            "$.requestedUnitIds",
        );
    }

    let translation_groups = validate_translation_groups(
        db,
        &mut check,
        &candidates,
        &selected,
        object.get("translationGroups"),
    )?;

    // ---- shared prerequisites -------------------------------------------
    let raw_shared = check.list(object.get("sharedPrerequisites"), "$.sharedPrerequisites");
    let mut shared_prerequisites: Vec<Value> = Vec::new();
    let mut shared_keys: BTreeSet<String> = BTreeSet::new();
    let mut shared_ids: BTreeSet<String> = BTreeSet::new();
    for (index, raw) in raw_shared.iter().enumerate() {
        let path = format!("$.sharedPrerequisites[{index}]");
        let Some(value) = raw.as_object() else {
            check.push(
                "INVALID_SHARED_PREREQUISITE",
                "shared prerequisite must be an object",
                &path,
            );
            continue;
        };
        check.fields(
            value,
            &["key", "name", "kind", "reason", "sourceNodeIds", "requiredBy"],
            &path,
        );
        let key = text(value.get("key")).to_lowercase();
        let name = text(value.get("name"));
        let kind = text(value.get("kind"));
        let reason = text(value.get("reason"));
        if key.is_empty() {
            check.push(
                "INVALID_SHARED_PREREQUISITE_KEY",
                "shared prerequisite key must be non-empty",
                format!("{path}.key"),
            );
        } else if !shared_keys.insert(key.clone()) {
            check.push(
                "DUPLICATE_SHARED_PREREQUISITE_KEY",
                format!("duplicate shared prerequisite key: {}", text(value.get("key"))),
                format!("{path}.key"),
            );
        }
        if name.is_empty() {
            check.push(
                "MISSING_SHARED_PREREQUISITE_NAME",
                "shared prerequisite name must be non-empty",
                format!("{path}.name"),
            );
        }
        if kind.is_empty() {
            check.push(
                "MISSING_SHARED_PREREQUISITE_KIND",
                "shared prerequisite kind must be a non-empty extensible concept label",
                format!("{path}.kind"),
            );
        }
        if reason.is_empty() {
            check.push(
                "MISSING_SHARED_PREREQUISITE_REASON",
                "shared prerequisite reason must be non-empty",
                format!("{path}.reason"),
            );
        }
        let raw_sources = check.list(value.get("sourceNodeIds"), &format!("{path}.sourceNodeIds"));
        if raw_sources.is_empty() {
            check.push(
                "MISSING_SOURCE_SUPPORT",
                "shared prerequisite requires source node IDs",
                format!("{path}.sourceNodeIds"),
            );
        }
        let sources = check.node_ids(db, &raw_sources, &format!("{path}.sourceNodeIds"))?;

        let raw_required_by = check.list(value.get("requiredBy"), &format!("{path}.requiredBy"));
        if raw_required_by.is_empty() {
            check.push(
                "MISSING_SHARED_PREREQUISITE_CONSUMER",
                "shared prerequisite requiredBy must contain at least one requested unit",
                format!("{path}.requiredBy"),
            );
        }
        let mut required_by: Vec<String> = Vec::new();
        for (unit_index, raw_unit) in raw_required_by.iter().enumerate() {
            let unit_path = format!("{path}.requiredBy[{unit_index}]");
            match raw_unit.as_str() {
                Some(unit_id) if selected.contains(unit_id) => {
                    if required_by.iter().any(|seen| seen == unit_id) {
                        check.push(
                            "DUPLICATE_SHARED_PREREQUISITE_CONSUMER",
                            format!("shared prerequisite repeats a required unit: {unit_id}"),
                            unit_path,
                        );
                    } else {
                        required_by.push(unit_id.to_string());
                    }
                }
                other => check.push(
                    "UNKNOWN_SHARED_PREREQUISITE_CONSUMER",
                    format!(
                        "shared prerequisite references an unselected unit: {:?}",
                        other.unwrap_or_default()
                    ),
                    unit_path,
                ),
            }
        }
        required_by.sort();

        // Identity is derived from the concept and its source support, so the
        // same concept named twice resolves to the same dependency.
        let language = scope.request.language.to_lowercase();
        let name_folded = name.to_lowercase();
        let kind_folded = kind.to_lowercase();
        let mut parts: Vec<&str> = vec![
            &language,
            &scope.request.version,
            &key,
            &name_folded,
            &kind_folded,
        ];
        parts.extend(sources.iter().map(String::as_str));
        let dependency_id = stable_id("shared", &parts, 24);
        if !shared_ids.insert(dependency_id.clone()) {
            check.push(
                "DUPLICATE_SHARED_PREREQUISITE_ID",
                format!("shared prerequisites resolve to the same dependency ID: {dependency_id}"),
                &path,
            );
        }
        shared_prerequisites.push(json!({
            "dependencyId": dependency_id,
            "name": name,
            "kind": kind,
            "reason": reason,
            "sourceNodeIds": sources,
            "requiredBy": required_by,
        }));
    }

    // ---- external prerequisites -----------------------------------------
    let raw_prerequisites =
        check.list(object.get("externalPrerequisites"), "$.externalPrerequisites");
    let mut prerequisites: Vec<Value> = Vec::new();
    let mut prerequisite_keys: BTreeMap<String, String> = BTreeMap::new();
    for (index, raw) in raw_prerequisites.iter().enumerate() {
        let path = format!("$.externalPrerequisites[{index}]");
        let Some(value) = raw.as_object() else {
            check.push("INVALID_PREREQUISITE", "prerequisite must be an object", &path);
            continue;
        };
        check.fields(value, &["key", "name", "reason", "sourceNodeIds"], &path);
        let Some(key) = value
            .get("key")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            check.push(
                "INVALID_PREREQUISITE_KEY",
                "prerequisite key must be non-empty",
                format!("{path}.key"),
            );
            continue;
        };
        if prerequisite_keys.contains_key(key) {
            check.push(
                "DUPLICATE_PREREQUISITE_KEY",
                format!("duplicate prerequisite key: {key}"),
                format!("{path}.key"),
            );
            continue;
        }
        // A prerequisite key doubles as a dependency-graph endpoint, so it must
        // not shadow a unit ID.
        if candidates.contains_key(key) {
            check.push(
                "PREREQUISITE_KEY_COLLISION",
                format!("prerequisite key collides with a unit ID: {key}"),
                format!("{path}.key"),
            );
            continue;
        }
        let name = value
            .get("name")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default()
            .to_string();
        let reason = value
            .get("reason")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default()
            .to_string();
        if name.is_empty() {
            check.push(
                "MISSING_PREREQUISITE_NAME",
                "prerequisite name must be non-empty",
                format!("{path}.name"),
            );
        }
        if reason.is_empty() {
            check.push(
                "MISSING_PREREQUISITE_REASON",
                "prerequisite reason must be non-empty",
                format!("{path}.reason"),
            );
        }
        let raw_sources = check.list(value.get("sourceNodeIds"), &format!("{path}.sourceNodeIds"));
        if raw_sources.is_empty() {
            check.push(
                "MISSING_SOURCE_SUPPORT",
                "prerequisite requires source node IDs",
                format!("{path}.sourceNodeIds"),
            );
        }
        let sources = check.node_ids(db, &raw_sources, &format!("{path}.sourceNodeIds"))?;
        let mut parts: Vec<&str> = vec![key, &name];
        parts.extend(sources.iter().map(String::as_str));
        let prerequisite_id = stable_id("prerequisite", &parts, 24);
        prerequisite_keys.insert(key.to_string(), prerequisite_id.clone());
        prerequisites.push(json!({
            "prerequisiteId": prerequisite_id,
            "name": name,
            "sourceNodeIds": sources,
            "reason": reason,
        }));
    }

    // ---- dependencies ----------------------------------------------------
    let raw_dependencies = check.list(object.get("dependencies"), "$.dependencies");
    let mut dependencies: Vec<Value> = Vec::new();
    let mut seen_edges: BTreeSet<(String, String)> = BTreeSet::new();
    for (index, raw) in raw_dependencies.iter().enumerate() {
        let path = format!("$.dependencies[{index}]");
        let Some(value) = raw.as_object() else {
            check.push("INVALID_DEPENDENCY", "dependency must be an object", &path);
            continue;
        };
        check.fields(
            value,
            &["from", "to", "reason", "supportingNodeIds", "origin"],
            &path,
        );
        let source = value.get("from").and_then(Value::as_str).unwrap_or_default();
        let target = value.get("to").and_then(Value::as_str).unwrap_or_default();
        let known = |endpoint: &str| {
            selected.contains(endpoint) || prerequisite_keys.contains_key(endpoint)
        };
        if !known(source) {
            check.push(
                "UNKNOWN_EDGE_ENDPOINT",
                format!("unknown dependency source: {source:?}"),
                format!("{path}.from"),
            );
            continue;
        }
        if !known(target) {
            check.push(
                "UNKNOWN_EDGE_ENDPOINT",
                format!("unknown dependency target: {target:?}"),
                format!("{path}.to"),
            );
            continue;
        }
        // An external prerequisite is by definition outside the plan, so it
        // cannot be the thing that depends on something.
        if !selected.contains(target) {
            check.push(
                "EXTERNAL_PREREQUISITE_TARGET",
                "an external prerequisite cannot be the dependent endpoint",
                format!("{path}.to"),
            );
            continue;
        }
        if source == target {
            check.push(
                "SELF_EDGE",
                format!("dependency cannot point to itself: {source}"),
                &path,
            );
            continue;
        }
        if !seen_edges.insert((source.to_string(), target.to_string())) {
            check.push(
                "DUPLICATE_EDGE",
                format!("duplicate dependency: {source} -> {target}"),
                &path,
            );
            continue;
        }
        let reason = value
            .get("reason")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default()
            .to_string();
        if reason.is_empty() {
            check.push(
                "MISSING_EDGE_REASON",
                "dependency reason must be non-empty",
                format!("{path}.reason"),
            );
        }
        let origin = value.get("origin").and_then(Value::as_str).unwrap_or_default();
        if !matches!(origin, "EXPLICIT" | "INFERRED") {
            check.push(
                "INVALID_EDGE_ORIGIN",
                "origin must be EXPLICIT or INFERRED",
                format!("{path}.origin"),
            );
        }
        let raw_support = check.list(
            value.get("supportingNodeIds"),
            &format!("{path}.supportingNodeIds"),
        );
        if raw_support.is_empty() {
            check.push(
                "MISSING_SOURCE_SUPPORT",
                "dependency requires supporting source node IDs",
                format!("{path}.supportingNodeIds"),
            );
        }
        let support = check.node_ids(db, &raw_support, &format!("{path}.supportingNodeIds"))?;
        dependencies.push(json!({
            "from": prerequisite_keys.get(source).map(String::as_str).unwrap_or(source),
            "to": prerequisite_keys.get(target).map(String::as_str).unwrap_or(target),
            "reason": reason,
            "supportingNodeIds": support,
            "origin": origin,
        }));
    }

    if !check.diagnostics.is_empty() {
        return Ok(Err(check.diagnostics));
    }
    shared_prerequisites.sort_by_key(|item| {
        item["dependencyId"].as_str().unwrap_or_default().to_string()
    });
    Ok(Ok(json!({
        "requestedUnits": unit_ids
            .iter()
            .map(|unit_id| candidates[unit_id.as_str()].clone())
            .collect::<Vec<_>>(),
        "translationGroups": translation_groups,
        "externalPrerequisites": prerequisites,
        "sharedPrerequisites": shared_prerequisites,
        "dependencies": dependencies,
    })))
}

/// An exact partition of the selected units, each group justified by indexed
/// structure the units actually sit under.
fn validate_translation_groups(
    db: &SpecDb,
    check: &mut Checker,
    candidates: &BTreeMap<&str, &Value>,
    selected: &BTreeSet<&str>,
    raw_value: Option<&Value>,
) -> Result<Vec<Value>, SpecDbError> {
    let raw_groups = check.list(raw_value, "$.translationGroups");
    let mut seen_units: BTreeSet<String> = BTreeSet::new();
    let mut seen_names: BTreeSet<String> = BTreeSet::new();
    let mut groups: Vec<Value> = Vec::new();

    for (index, raw) in raw_groups.iter().enumerate() {
        let path = format!("$.translationGroups[{index}]");
        let Some(value) = raw.as_object() else {
            check.push(
                "INVALID_TRANSLATION_GROUP",
                "translation group must be an object",
                &path,
            );
            continue;
        };
        check.fields(
            value,
            &["name", "unitIds", "reason", "supportingNodeIds", "origin"],
            &path,
        );

        let name = value.get("name").and_then(Value::as_str).unwrap_or_default();
        let normalized_name = if GROUP_NAME.is_match(name) {
            if !seen_names.insert(name.to_lowercase()) {
                check.push(
                    "DUPLICATE_TRANSLATION_GROUP_NAME",
                    format!("duplicate translation group name: {name}"),
                    format!("{path}.name"),
                );
            }
            name.to_string()
        } else {
            check.push(
                "INVALID_TRANSLATION_GROUP_NAME",
                "translation group name must be an UpperCamelCase Lean identifier of at most 64 characters",
                format!("{path}.name"),
            );
            String::new()
        };

        let reason = value
            .get("reason")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default()
            .to_string();
        if reason.is_empty() {
            check.push(
                "MISSING_TRANSLATION_GROUP_REASON",
                "translation group requires a non-empty specification-based reason",
                format!("{path}.reason"),
            );
        }
        let origin = value.get("origin").and_then(Value::as_str).unwrap_or_default();
        if !matches!(origin, "EXPLICIT" | "INFERRED") {
            check.push(
                "INVALID_TRANSLATION_GROUP_ORIGIN",
                "translation group origin must be EXPLICIT or INFERRED",
                format!("{path}.origin"),
            );
        }

        let mut group_unit_ids: Vec<String> = Vec::new();
        let raw_unit_ids = check.list(value.get("unitIds"), &format!("{path}.unitIds"));
        for (unit_index, raw_unit) in raw_unit_ids.iter().enumerate() {
            let unit_path = format!("{path}.unitIds[{unit_index}]");
            match raw_unit.as_str() {
                Some(unit_id) if selected.contains(unit_id) => {
                    if group_unit_ids.iter().any(|seen| seen == unit_id)
                        || seen_units.contains(unit_id)
                    {
                        check.push(
                            "DUPLICATE_TRANSLATION_GROUP_UNIT",
                            format!("unit appears more than once in translation groups: {unit_id}"),
                            unit_path,
                        );
                    } else {
                        group_unit_ids.push(unit_id.to_string());
                        seen_units.insert(unit_id.to_string());
                    }
                }
                other => check.push(
                    "UNKNOWN_TRANSLATION_GROUP_UNIT",
                    format!(
                        "translation group references an unselected unit: {:?}",
                        other.unwrap_or_default()
                    ),
                    unit_path,
                ),
            }
        }
        if group_unit_ids.is_empty() {
            check.push(
                "EMPTY_TRANSLATION_GROUP",
                "translation group must contain at least one selected unit",
                format!("{path}.unitIds"),
            );
        }

        let raw_support = check.list(
            value.get("supportingNodeIds"),
            &format!("{path}.supportingNodeIds"),
        );
        let support = check.node_ids(db, &raw_support, &format!("{path}.supportingNodeIds"))?;
        if raw_support.is_empty() {
            check.push(
                "MISSING_TRANSLATION_GROUP_SUPPORT",
                "translation group requires existing Phase-1 source-node support",
                format!("{path}.supportingNodeIds"),
            );
        }
        // The justification must be structure the members actually sit under —
        // and, for a group of more than one, structure they sit under
        // *together*. Checking each member against any support node
        // independently lets a group be "justified" by listing each unit's own
        // section, which justifies nothing about grouping them.
        let support_set: BTreeSet<&str> = support.iter().map(String::as_str).collect();
        let mut common: Option<BTreeSet<String>> = None;
        for unit_id in &group_unit_ids {
            let mut ancestry: BTreeSet<String> = BTreeSet::new();
            for raw_source in candidates[unit_id.as_str()]
                .get("sourceNodeIds")
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default()
            {
                let Some(node_id) = raw_source.as_str().and_then(|v| NodeId::parse(v).ok()) else {
                    continue;
                };
                ancestry.insert(node_id.to_string());
                for row in db.ancestors(&node_id, 30)? {
                    ancestry.insert(row.node_id.to_string());
                }
            }
            if !support_set.iter().any(|value| ancestry.contains(*value)) {
                check.push(
                    "UNSUPPORTED_TRANSLATION_GROUP_MEMBER",
                    format!("group support is not in the indexed source ancestry of unit {unit_id}"),
                    format!("{path}.supportingNodeIds"),
                );
            }
            common = Some(match common {
                None => ancestry,
                Some(shared) => shared.intersection(&ancestry).cloned().collect(),
            });
        }
        if group_unit_ids.len() > 1
            && !common
                .unwrap_or_default()
                .iter()
                .any(|value| support_set.contains(value.as_str()))
        {
            check.push(
                "UNSHARED_TRANSLATION_GROUP_SUPPORT",
                "a group of several units needs support they all sit under; none of the                  supporting nodes is common to every member",
                format!("{path}.supportingNodeIds"),
            );
        }

        groups.push(json!({
            "name": normalized_name,
            "unitIds": group_unit_ids,
            "reason": reason,
            "supportingNodeIds": support,
            "origin": origin,
        }));
    }

    let missing: Vec<&&str> = selected
        .iter()
        .filter(|unit_id| !seen_units.contains(**unit_id))
        .collect();
    if !missing.is_empty() {
        check.push(
            "UNGROUPED_REQUESTED_UNITS",
            format!(
                "every requested unit must belong to exactly one translation group; missing={missing:?}"
            ),
            "$.translationGroups",
        );
    }
    groups.sort_by_key(|item| item["name"].as_str().unwrap_or_default().to_string());
    Ok(groups)
}

/// Validate, then derive everything the model must not own: processing order,
/// cycles, and the identity of the plan itself.
pub fn build_validated_plan(
    db: &SpecDb,
    scope: &ResolvedScope,
    submission: &Value,
    plan_run_id: &str,
    source_database_digest: &str,
) -> Result<Result<Value, Vec<Diagnostic>>, SpecDbError> {
    let normalized = match validate_submission(db, scope, submission)? {
        Ok(normalized) => normalized,
        Err(diagnostics) => return Ok(Err(diagnostics)),
    };
    let unit_ids: Vec<String> = normalized["requestedUnits"]
        .as_array()
        .map(Vec::as_slice)
        .unwrap_or_default()
        .iter()
        .filter_map(|unit| unit.get("unitId")?.as_str().map(str::to_string))
        .collect();
    let dependencies = normalized["dependencies"]
        .as_array()
        .cloned()
        .unwrap_or_default();
    let (layers, cycles, blocked) = derive_processing_order(&unit_ids, &dependencies);

    let mut plan = json!({
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "language": scope.request.language,
        "version": scope.request.version,
        "planRunId": plan_run_id,
        "sourceDatabaseDigest": source_database_digest,
        "request": scope.request.to_json(),
        "processingLayers": layers,
        "cycles": cycles,
        "blockedUnitIds": blocked,
        "graphStatus": if cycles.is_empty() { "ACYCLIC" } else { "CYCLIC" },
    });
    for (key, value) in normalized.as_object().expect("object") {
        plan[key] = value.clone();
    }
    Ok(Ok(plan))
}
