use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use spec2lean_specdb::{canonical_json, stable_id};

pub const TRANSLATION_SCHEMA_VERSION: u32 = 4;

pub fn semantics_artifact_hash(artifact: &Value) -> String {
    let mut hasher = Sha256::new();
    hasher.update(canonical_json(artifact).as_bytes());
    let digest = hasher.finalize();
    format!(
        "sha256:{}",
        digest.iter().map(|byte| format!("{byte:02x}")).collect::<String>()
    )
}

#[derive(Debug, PartialEq, Eq)]
pub enum ScopeError {
    Groups(String),
    Inputs(String),
    /// Shared prerequisites require the frozen shared core, which is not ported
    /// yet. Named explicitly rather than silently ignored.
    SharedCoreUnsupported(Vec<String>),
}

impl std::fmt::Display for ScopeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Groups(detail) | Self::Inputs(detail) => f.write_str(detail),
            Self::SharedCoreUnsupported(ids) => write!(
                f,
                "this group has shared prerequisites ({}), which need the frozen shared core; \
                 that phase is not ported to the Rust harness yet",
                ids.join(", ")
            ),
        }
    }
}

impl std::error::Error for ScopeError {}

/// Phase 2's validated partition of units into translation groups.
pub fn grouped_units(plan: &Value) -> Result<BTreeMap<String, Vec<Value>>, ScopeError> {
    let units: BTreeMap<&str, &Value> = plan
        .get("requestedUnits")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| Some((item.get("unitId")?.as_str()?, item)))
                .collect()
        })
        .unwrap_or_default();
    let raw = plan
        .get("translationGroups")
        .and_then(Value::as_array)
        .filter(|items| !items.is_empty())
        .ok_or_else(|| {
            ScopeError::Groups(
                "Phase-2 plan has no specification-derived translationGroups; rerun from the plan phase"
                    .into(),
            )
        })?;

    let mut groups: BTreeMap<String, Vec<Value>> = BTreeMap::new();
    let mut seen: BTreeSet<&str> = BTreeSet::new();
    for item in raw {
        let name = item
            .get("name")
            .and_then(Value::as_str)
            .ok_or_else(|| {
                ScopeError::Groups("Phase-2 plan contains a malformed translation group".into())
            })?;
        if groups.contains_key(name) {
            return Err(ScopeError::Groups(format!(
                "Phase-2 plan contains a duplicate translation group: {name}"
            )));
        }
        let members = item
            .get("unitIds")
            .and_then(Value::as_array)
            .filter(|items| !items.is_empty())
            .ok_or_else(|| {
                ScopeError::Groups(format!("Phase-2 translation group is empty: {name}"))
            })?;
        let mut resolved = Vec::new();
        for raw_id in members {
            let unit_id = raw_id.as_str().unwrap_or_default();
            let unit = units.get(unit_id).ok_or_else(|| {
                ScopeError::Groups(format!(
                    "Phase-2 translation group references an unknown unit: {unit_id}"
                ))
            })?;
            if !seen.insert(unit_id) {
                return Err(ScopeError::Groups(format!(
                    "Phase-2 unit appears in more than one translation group: {unit_id}"
                )));
            }
            resolved.push((*unit).clone());
        }
        groups.insert(name.to_string(), resolved);
    }
    let missing: Vec<&&str> = units.keys().filter(|id| !seen.contains(*id)).collect();
    if !missing.is_empty() {
        return Err(ScopeError::Groups(format!(
            "Phase-2 translation groups do not cover every requested unit: {missing:?}"
        )));
    }
    Ok(groups)
}

/// Capitalised, alphanumeric Lean path component derived from free text.
fn lean_component(value: &str) -> String {
    let mut component = String::new();
    for word in value.split(|c: char| !c.is_ascii_alphanumeric()) {
        let mut characters = word.chars();
        if let Some(first) = characters.next() {
            component.push(first.to_ascii_uppercase());
            component.extend(characters);
        }
    }
    if component.is_empty() {
        component.push_str("Unit");
    }
    if component.starts_with(|c: char| c.is_ascii_digit()) {
        component.insert(0, 'V');
    }
    component
}

/// The deterministic boundary for translating one group.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TranslationScope {
    pub plan_run_id: String,
    pub language: String,
    pub version: String,
    pub group: String,
    pub units: Vec<Value>,
    /// `(unitId, runId, artifactHash)` per unit, in group order.
    pub semantics: Vec<(String, String, String)>,
    /// Every `(unitId, claimId)` the translation may reference.
    pub claim_refs: Vec<(String, String)>,
    pub translation_run_id: String,
    pub created_at: String,
}

impl TranslationScope {
    pub fn unit_ids(&self) -> Vec<&str> {
        self.units
            .iter()
            .filter_map(|unit| unit.get("unitId")?.as_str())
            .collect()
    }

    pub fn suggested_namespace(&self) -> String {
        format!(
            "Spec2Lean.{}.{}",
            lean_component(&self.language),
            lean_component(&self.group)
        )
    }

    pub fn lean_file(&self) -> String {
        format!("{}.lean", lean_component(&self.group))
    }

    pub fn from_inputs(
        plan: &Value,
        group: &str,
        semantics_by_unit: &BTreeMap<String, Value>,
        created_at: &str,
    ) -> Result<Self, ScopeError> {
        let groups = grouped_units(plan)?;
        let units = groups.get(group).cloned().ok_or_else(|| {
            ScopeError::Groups(format!(
                "translation group is not present in the Phase-2 plan: {group}"
            ))
        })?;
        let unit_ids: Vec<String> = units
            .iter()
            .filter_map(|unit| unit.get("unitId")?.as_str().map(str::to_string))
            .collect();
        let supplied: BTreeSet<&String> = semantics_by_unit.keys().collect();
        let expected: BTreeSet<&String> = unit_ids.iter().collect();
        if supplied != expected {
            return Err(ScopeError::Inputs(
                "Phase-5 group input must contain exactly one semantic artifact per group unit"
                    .into(),
            ));
        }

        let mut semantics = Vec::new();
        let mut claim_refs = Vec::new();
        for (unit, unit_id) in units.iter().zip(&unit_ids) {
            let artifact = &semantics_by_unit[unit_id];
            let field = |key: &str| artifact.get(key).and_then(Value::as_str);
            if field("phase") != Some("SEMANTIC_EXTRACTOR") || field("outcome") != Some("SUCCESS") {
                return Err(ScopeError::Inputs(format!(
                    "Phase-5 translation requires successful semantics for {unit_id}"
                )));
            }
            if artifact.get("planRunId") != plan.get("planRunId") {
                return Err(ScopeError::Inputs(format!(
                    "Phase-4 semantic planRunId does not match Phase 2 for {unit_id}"
                )));
            }
            if artifact.get("language") != plan.get("language")
                || artifact.get("version") != plan.get("version")
            {
                return Err(ScopeError::Inputs(format!(
                    "Phase-4 semantic specification identity does not match Phase 2 for {unit_id}"
                )));
            }
            if artifact.get("unit") != Some(unit) {
                return Err(ScopeError::Inputs(format!(
                    "Phase-4 semantic unit does not match Phase 2 for {unit_id}"
                )));
            }
            let run_id = field("runId")
                .filter(|value| value.starts_with("semantic-run:"))
                .ok_or_else(|| {
                    ScopeError::Inputs(format!(
                        "Phase-4 semantic run ID is missing or malformed for {unit_id}"
                    ))
                })?;
            let claims = artifact
                .get("semantics")
                .and_then(|value| value.get("claims"))
                .and_then(Value::as_array)
                .filter(|items| !items.is_empty())
                .ok_or_else(|| {
                    ScopeError::Inputs(format!(
                        "Phase-4 semantic artifact must contain claims for {unit_id}"
                    ))
                })?;
            let ids: Vec<&str> = claims
                .iter()
                .filter_map(|item| item.get("claimId")?.as_str())
                .filter(|value| value.starts_with("claim:"))
                .collect();
            if ids.len() != claims.len() {
                return Err(ScopeError::Inputs(format!(
                    "Phase-4 semantic claim IDs are malformed for {unit_id}"
                )));
            }
            if ids.iter().collect::<BTreeSet<_>>().len() != ids.len() {
                return Err(ScopeError::Inputs(format!(
                    "Phase-4 semantic claim IDs must be unique within {unit_id}"
                )));
            }
            claim_refs.extend(
                ids.iter()
                    .map(|claim_id| (unit_id.clone(), (*claim_id).to_string())),
            );
            semantics.push((
                unit_id.clone(),
                run_id.to_string(),
                semantics_artifact_hash(artifact),
            ));
        }

        // Shared prerequisites need the frozen shared core; refuse rather than
        // translate a group whose shared concepts have no agreed representation.
        let shared: Vec<String> = plan
            .get("sharedPrerequisites")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter(|item| {
                        item.get("requiredBy")
                            .and_then(Value::as_array)
                            .is_some_and(|required| {
                                required.iter().any(|value| {
                                    value.as_str().is_some_and(|id| unit_ids.iter().any(|u| u == id))
                                })
                            })
                    })
                    .filter_map(|item| item.get("dependencyId")?.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default();
        if !shared.is_empty() {
            return Err(ScopeError::SharedCoreUnsupported(shared));
        }

        let plan_run_id = plan
            .get("planRunId")
            .and_then(Value::as_str)
            .ok_or_else(|| ScopeError::Inputs("plan has no planRunId".into()))?;
        let hash_material = canonical_json(&json!(
            semantics
                .iter()
                .map(|(unit_id, _, hash)| json!([unit_id, hash]))
                .collect::<Vec<_>>()
        ));
        Ok(Self {
            plan_run_id: plan_run_id.to_string(),
            language: plan
                .get("language")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string(),
            version: plan
                .get("version")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string(),
            group: group.to_string(),
            units,
            translation_run_id: stable_id(
                "translation-group-run",
                &[plan_run_id, group, &hash_material],
                24,
            ),
            semantics,
            claim_refs,
            created_at: created_at.to_string(),
        })
    }

    pub fn to_json(&self) -> Value {
        json!({
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "group": {"name": self.group, "unitIds": self.unit_ids()},
            "units": self.units,
            "semanticsArtifacts": self.semantics.iter().map(|(unit_id, run_id, hash)| json!({
                "unitId": unit_id, "runId": run_id, "artifactHash": hash,
            })).collect::<Vec<_>>(),
            "semanticClaimRefs": self.claim_refs.iter().map(|(unit_id, claim_id)| json!({
                "unitId": unit_id, "claimId": claim_id,
            })).collect::<Vec<_>>(),
            "translationRunId": self.translation_run_id,
            "createdAt": self.created_at,
            "suggestedNamespace": self.suggested_namespace(),
            "leanFile": self.lean_file(),
        })
    }

    /// The accepted translation manifest.
    pub fn manifest(&self, declarations: &Value, translator: &Value, build: &Value) -> Value {
        json!({
            "schemaVersion": TRANSLATION_SCHEMA_VERSION,
            "phase": "LLM_GROUP_TRANSLATOR",
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "group": {"name": self.group, "unitIds": self.unit_ids()},
            "translationRunId": self.translation_run_id,
            "semanticsArtifacts": self.semantics.iter().map(|(unit_id, run_id, hash)| json!({
                "unitId": unit_id, "runId": run_id, "artifactHash": hash,
            })).collect::<Vec<_>>(),
            "translator": translator,
            "target": {"language": "Lean", "version": "4"},
            "leanFile": self.lean_file(),
            "createdAt": self.created_at,
            "declarations": declarations,
            "build": build,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lean_components_are_capitalised_and_never_start_with_a_digit() {
        assert_eq!(lean_component("integer add"), "IntegerAdd");
        assert_eq!(lean_component("nvidia-ptx"), "NvidiaPtx");
        assert_eq!(lean_component("32bit"), "V32bit");
        assert_eq!(lean_component("!!!"), "Unit");
    }
}
