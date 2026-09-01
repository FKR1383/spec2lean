use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Value, json};
use spec2lean_translation::scope::semantics_artifact_hash;

use crate::identity::json_hash;

/// A concept the core must represent, together with everything Phase 4 said
/// about what it has to mean.
#[derive(Debug, Clone)]
pub struct SharedRequirement {
    pub dependency_id: String,
    pub name: String,
    pub kind: String,
    pub source_node_ids: Vec<String>,
    pub required_by: Vec<String>,
    /// Hash of the semantic inputs. A core is only reusable while this matches:
    /// if what the concept must mean changed, the frozen representation is no
    /// longer known to satisfy it.
    pub semantic_input_hash: String,
    pub claim_refs: Vec<(String, String)>,
    pub semantic_dependencies: Vec<Value>,
    pub claims: Vec<Value>,
    pub semantic_artifacts: Vec<Value>,
}

impl SharedRequirement {
    /// The registry entry for this concept once the core names its declarations.
    pub fn concept(&self, lean_declarations: &[String]) -> Value {
        json!({
            "dependencyId": self.dependency_id,
            "name": self.name,
            "kind": self.kind,
            "sourceNodeIds": self.source_node_ids,
            "requiredBy": self.required_by,
            "semanticInputHash": self.semantic_input_hash,
            "leanDeclarations": lean_declarations,
            "claimRefs": self.claim_refs.iter().map(|(unit_id, claim_id)| json!({
                "unitId": unit_id, "claimId": claim_id,
            })).collect::<Vec<_>>(),
        })
    }

    /// What the generator is shown: the concept plus the claims that define it.
    pub fn brief(&self) -> Value {
        json!({
            "dependencyId": self.dependency_id,
            "name": self.name,
            "kind": self.kind,
            "requiredBy": self.required_by,
            "semanticDependencies": self.semantic_dependencies,
            "claims": self.claims,
        })
    }
}

/// A shared concept that cannot be satisfied.
///
/// Raised rather than worked around: translating a group whose shared concept
/// has no agreed representation would produce Lean that only accidentally
/// agrees with its siblings.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MissingSharedAbstraction {
    pub dependency_id: String,
    pub unit_id: String,
    pub detail: String,
}

impl std::fmt::Display for MissingSharedAbstraction {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "MISSING_SHARED_ABSTRACTION for {} (unit {}): {}",
            self.dependency_id, self.unit_id, self.detail
        )
    }
}

impl std::error::Error for MissingSharedAbstraction {}

impl MissingSharedAbstraction {
    pub fn to_json(&self) -> Value {
        json!({
            "code": "MISSING_SHARED_ABSTRACTION",
            "dependencyId": self.dependency_id,
            "unitId": self.unit_id,
            "detail": self.detail,
        })
    }
}

#[derive(Debug)]
pub enum RequirementError {
    Plan(String),
    Missing(MissingSharedAbstraction),
}

impl std::fmt::Display for RequirementError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Plan(detail) => f.write_str(detail),
            Self::Missing(missing) => write!(f, "{missing}"),
        }
    }
}

impl std::error::Error for RequirementError {}

fn missing(dependency_id: &str, unit_id: &str, detail: &str) -> RequirementError {
    RequirementError::Missing(MissingSharedAbstraction {
        dependency_id: dependency_id.to_string(),
        unit_id: unit_id.to_string(),
        detail: detail.to_string(),
    })
}

/// The plan's shared prerequisites, validated and normalised.
fn shared_prerequisites(plan: &Value) -> Result<Vec<Value>, RequirementError> {
    let requested: BTreeSet<&str> = plan
        .get("requestedUnits")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.get("unitId")?.as_str())
                .collect()
        })
        .unwrap_or_default();
    let raw = match plan.get("sharedPrerequisites") {
        None => return Ok(Vec::new()),
        Some(Value::Array(items)) => items,
        Some(_) => {
            return Err(RequirementError::Plan(
                "Phase-2 sharedPrerequisites must be an array".into(),
            ));
        }
    };

    let mut seen: BTreeSet<&str> = BTreeSet::new();
    let mut result = Vec::new();
    for (index, item) in raw.iter().enumerate() {
        let bad = |detail: &str| RequirementError::Plan(format!("sharedPrerequisites[{index}] {detail}"));
        let dependency_id = item
            .get("dependencyId")
            .and_then(Value::as_str)
            .filter(|value| value.starts_with("shared:"))
            .ok_or_else(|| bad("requires a shared:* dependencyId"))?;
        if !seen.insert(dependency_id) {
            return Err(RequirementError::Plan(format!(
                "duplicate shared prerequisite: {dependency_id}"
            )));
        }
        let name = item
            .get("name")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| bad("requires a name"))?;
        let kind = item
            .get("kind")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| bad("requires an extensible kind"))?;
        let mut source_node_ids: Vec<String> = item
            .get("sourceNodeIds")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(Value::as_str)
                    .filter(|value| value.starts_with("node:"))
                    .map(str::to_string)
                    .collect()
            })
            .unwrap_or_default();
        source_node_ids.sort();
        source_node_ids.dedup();
        if source_node_ids.is_empty() {
            return Err(bad("requires sourceNodeIds"));
        }
        let required_by_raw: Vec<&str> = item
            .get("requiredBy")
            .and_then(Value::as_array)
            .map(|items| items.iter().filter_map(Value::as_str).collect())
            .unwrap_or_default();
        if required_by_raw.is_empty()
            || !required_by_raw.iter().all(|value| requested.contains(value))
        {
            return Err(bad("must be required by selected units"));
        }
        let mut required_by: Vec<String> =
            required_by_raw.iter().map(|value| (*value).to_string()).collect();
        required_by.sort();
        required_by.dedup();
        if required_by.len() != required_by_raw.len() {
            return Err(bad("has duplicate requiredBy entries"));
        }
        result.push(json!({
            "dependencyId": dependency_id,
            "name": name,
            "kind": kind,
            "sourceNodeIds": source_node_ids,
            "requiredBy": required_by,
        }));
    }
    result.sort_by_key(|item| item["dependencyId"].as_str().unwrap_or_default().to_string());
    Ok(result)
}

/// Which shared concepts a set of units actually needs.
pub fn relevant_dependency_ids(
    plan: &Value,
    unit_ids: &[String],
) -> Result<Vec<String>, RequirementError> {
    let selected: BTreeSet<&str> = unit_ids.iter().map(String::as_str).collect();
    Ok(shared_prerequisites(plan)?
        .into_iter()
        .filter(|item| {
            item["requiredBy"]
                .as_array()
                .map(Vec::as_slice)
                .unwrap_or_default()
                .iter()
                .filter_map(Value::as_str)
                .any(|unit_id| selected.contains(unit_id))
        })
        .filter_map(|item| item["dependencyId"].as_str().map(str::to_string))
        .collect())
}

/// Assemble what the core must provide, from the plan and the Phase-4
/// artifacts of every unit that needs each concept.
///
/// Every check here is a reason a core *cannot* be built rather than a reason
/// to build a weaker one: a concept whose meaning Phase 4 never pinned down
/// must not get a representation invented for it.
pub fn collect_shared_requirements(
    plan: &Value,
    semantics_by_unit: &BTreeMap<String, Value>,
    unit_ids: Option<&[String]>,
) -> Result<Vec<SharedRequirement>, RequirementError> {
    let selected: Option<BTreeSet<&str>> =
        unit_ids.map(|ids| ids.iter().map(String::as_str).collect());
    let mut requirements = Vec::new();

    for prerequisite in shared_prerequisites(plan)? {
        let dependency_id = prerequisite["dependencyId"].as_str().unwrap_or_default();
        let required_units: Vec<String> = prerequisite["requiredBy"]
            .as_array()
            .map(Vec::as_slice)
            .unwrap_or_default()
            .iter()
            .filter_map(Value::as_str)
            .filter(|unit_id| selected.as_ref().is_none_or(|set| set.contains(unit_id)))
            .map(str::to_string)
            .collect();
        if required_units.is_empty() {
            continue;
        }

        let mut semantic_dependencies = Vec::new();
        let mut claims = Vec::new();
        let mut claim_refs: Vec<(String, String)> = Vec::new();
        let mut artifacts = Vec::new();

        for unit_id in &required_units {
            let artifact = semantics_by_unit
                .get(unit_id)
                .ok_or_else(|| missing(dependency_id, unit_id, "the required Phase-4 artifact is absent"))?;
            let field = |key: &str| artifact.get(key).and_then(Value::as_str);
            if field("phase") != Some("SEMANTIC_EXTRACTOR") || field("outcome") != Some("SUCCESS") {
                return Err(missing(dependency_id, unit_id, "the required Phase-4 artifact is not successful"));
            }
            // Compare present values, never two absences: `None == None` would
            // let a plan and an artifact that both omit their identity agree
            // about belonging to the same specification.
            let identical = |key: &str| -> bool {
                match (
                    plan.get(key).and_then(Value::as_str),
                    artifact.get(key).and_then(Value::as_str),
                ) {
                    (Some(left), Some(right)) => left == right,
                    _ => false,
                }
            };
            if !identical("planRunId") {
                return Err(missing(dependency_id, unit_id, "the Phase-4 artifact belongs to another plan"));
            }
            if !identical("language") || !identical("version") {
                return Err(missing(dependency_id, unit_id, "the Phase-4 artifact belongs to another specification"));
            }
            if artifact
                .get("unit")
                .and_then(|unit| unit.get("unitId"))
                .and_then(Value::as_str)
                != Some(unit_id.as_str())
            {
                return Err(missing(dependency_id, unit_id, "the Phase-4 artifact belongs to another unit"));
            }
            let payload = artifact.get("semantics");
            let raw_dependencies = payload
                .and_then(|value| value.get("dependencies"))
                .and_then(Value::as_array)
                .ok_or_else(|| missing(dependency_id, unit_id, "Phase 4 has no semantic dependency array"))?;
            let matches: Vec<&Value> = raw_dependencies
                .iter()
                .filter(|item| item.get("dependencyId").and_then(Value::as_str) == Some(dependency_id))
                .collect();
            let [dependency] = matches[..] else {
                return Err(missing(
                    dependency_id,
                    unit_id,
                    "Phase 4 must contain exactly one dependency with this dependencyId",
                ));
            };
            if dependency
                .get("description")
                .and_then(Value::as_str)
                .map(str::trim)
                .is_none_or(str::is_empty)
            {
                return Err(missing(dependency_id, unit_id, "the semantic dependency has no description"));
            }
            let claim_ids: Vec<&str> = dependency
                .get("semanticClaimIds")
                .and_then(Value::as_array)
                .map(|items| {
                    items
                        .iter()
                        .filter_map(Value::as_str)
                        .filter(|value| value.starts_with("claim:"))
                        .collect()
                })
                .unwrap_or_default();
            let declared = dependency
                .get("semanticClaimIds")
                .and_then(Value::as_array)
                .map_or(0, Vec::len);
            if claim_ids.is_empty()
                || claim_ids.len() != declared
                || claim_ids.iter().collect::<BTreeSet<_>>().len() != claim_ids.len()
            {
                return Err(missing(
                    dependency_id,
                    unit_id,
                    "the semantic dependency requires unique, explicit semanticClaimIds",
                ));
            }

            let raw_claims = payload
                .and_then(|value| value.get("claims"))
                .and_then(Value::as_array)
                .ok_or_else(|| missing(dependency_id, unit_id, "Phase 4 has no structured semantic claim array"))?;
            let mut claims_by_id: BTreeMap<&str, &Value> = BTreeMap::new();
            for claim in raw_claims {
                let claim_id = claim
                    .get("claimId")
                    .and_then(Value::as_str)
                    .ok_or_else(|| missing(dependency_id, unit_id, "Phase 4 contains a malformed semantic claim"))?;
                if claims_by_id.insert(claim_id, claim).is_some() {
                    return Err(missing(
                        dependency_id,
                        unit_id,
                        &format!("Phase 4 contains duplicate semantic claim ID {claim_id}"),
                    ));
                }
            }
            let unresolved: Vec<&&str> = claim_ids
                .iter()
                .filter(|claim_id| !claims_by_id.contains_key(**claim_id))
                .collect();
            if !unresolved.is_empty() {
                return Err(missing(
                    dependency_id,
                    unit_id,
                    &format!(
                        "semanticClaimIds reference missing Phase-4 claims: {}",
                        unresolved.iter().map(|id| **id).collect::<Vec<_>>().join(", ")
                    ),
                ));
            }

            let mut dependency_copy = dependency.clone();
            dependency_copy["unitId"] = json!(unit_id);
            semantic_dependencies.push(dependency_copy);
            for claim_id in &claim_ids {
                claim_refs.push((unit_id.clone(), (*claim_id).to_string()));
                let mut claim = claims_by_id[*claim_id].clone();
                claim["unitId"] = json!(unit_id);
                claims.push(claim);
            }
            let run_id = field("runId")
                .filter(|value| value.starts_with("semantic-run:"))
                .ok_or_else(|| missing(dependency_id, unit_id, "the Phase-4 run ID is missing or malformed"))?;
            artifacts.push(json!({
                "planRunId": artifact["planRunId"],
                "unitId": unit_id,
                "runId": run_id,
                "artifactHash": semantics_artifact_hash(artifact),
            }));
        }

        claim_refs.sort();
        let mut sorted_dependencies = semantic_dependencies.clone();
        sorted_dependencies.sort_by_key(|item| {
            (
                item["unitId"].as_str().unwrap_or_default().to_string(),
                spec2lean_specdb::canonical_json(item),
            )
        });
        let mut sorted_claims = claims.clone();
        sorted_claims.sort_by_key(|item| {
            (
                item["unitId"].as_str().unwrap_or_default().to_string(),
                item["claimId"].as_str().unwrap_or_default().to_string(),
            )
        });
        let fingerprint = json!({
            "sourceDatabaseDigest": plan.get("sourceDatabaseDigest"),
            "prerequisite": {
                "dependencyId": prerequisite["dependencyId"],
                "name": prerequisite["name"],
                "kind": prerequisite["kind"],
                "sourceNodeIds": prerequisite["sourceNodeIds"],
            },
            "semanticDependencies": sorted_dependencies,
            "claims": sorted_claims,
        });

        requirements.push(SharedRequirement {
            dependency_id: dependency_id.to_string(),
            name: prerequisite["name"].as_str().unwrap_or_default().to_string(),
            kind: prerequisite["kind"].as_str().unwrap_or_default().to_string(),
            source_node_ids: prerequisite["sourceNodeIds"]
                .as_array()
                .map(|items| items.iter().filter_map(Value::as_str).map(str::to_string).collect())
                .unwrap_or_default(),
            required_by: required_units,
            semantic_input_hash: json_hash(&fingerprint),
            claim_refs,
            semantic_dependencies,
            claims,
            semantic_artifacts: artifacts,
        });
    }
    requirements.sort_by(|left, right| left.dependency_id.cmp(&right.dependency_id));
    Ok(requirements)
}
