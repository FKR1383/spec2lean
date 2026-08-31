use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use spec2lean_specdb::{UnitId, canonical_json, stable_id};

pub const SEMANTICS_SCHEMA_VERSION: u32 = 2;

/// `sha256:` over the canonical JSON of the whole Phase-3 bundle.
///
/// This is what pins a semantic artifact to the exact evidence it was extracted
/// from: change one character of one passage and the artifact stops validating.
pub fn evidence_bundle_hash(bundle: &Value) -> String {
    let mut hasher = Sha256::new();
    hasher.update(canonical_json(bundle).as_bytes());
    let digest = hasher.finalize();
    let hex: String = digest.iter().map(|byte| format!("{byte:02x}")).collect();
    format!("sha256:{hex}")
}

/// Everything that can go wrong at the Phase-2/Phase-3 → Phase-4 boundary.
///
/// These are input-integrity failures, not model mistakes: they mean the plan
/// and the bundle disagree, so no session should start at all.
#[derive(Debug, PartialEq, Eq)]
pub enum ScopeError {
    UnitNotUnique(String),
    Malformed(String),
    Mismatch(String),
}

impl std::fmt::Display for ScopeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::UnitNotUnique(unit) => {
                write!(f, "unit is not uniquely present in Phase-2 plan: {unit}")
            }
            Self::Malformed(detail) | Self::Mismatch(detail) => f.write_str(detail),
        }
    }
}

impl std::error::Error for ScopeError {}

/// The deterministic boundary for one extractor session.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SemanticScope {
    pub plan_run_id: String,
    pub language: String,
    pub version: String,
    pub unit: Value,
    #[serde(rename = "relevantSharedPrerequisites", default)]
    pub shared_prerequisites: Vec<Value>,
    pub evidence_bundle_hash: String,
    pub evidence_ids: Vec<String>,
    pub run_id: String,
    pub created_at: String,
}

impl SemanticScope {
    pub fn unit_id(&self) -> &str {
        self.unit.get("unitId").and_then(Value::as_str).unwrap_or("")
    }

    /// Resolve the boundary, rejecting any disagreement between the plan and
    /// the bundle before a single token is spent.
    pub fn from_inputs(
        plan: &Value,
        bundle: &Value,
        unit_id: &UnitId,
        created_at: &str,
    ) -> Result<Self, ScopeError> {
        let units: Vec<&Value> = plan
            .get("requestedUnits")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter(|item| {
                        item.get("unitId").and_then(Value::as_str) == Some(unit_id.as_str())
                    })
                    .collect()
            })
            .unwrap_or_default();
        let [unit] = units[..] else {
            return Err(ScopeError::UnitNotUnique(unit_id.to_string()));
        };

        let raw_shared = match plan.get("sharedPrerequisites") {
            None => Vec::new(),
            Some(Value::Array(items)) => items.clone(),
            Some(_) => {
                return Err(ScopeError::Malformed(
                    "Phase-2 sharedPrerequisites must be an array".into(),
                ));
            }
        };
        let mut shared_prerequisites: Vec<Value> = Vec::new();
        let mut seen: Vec<String> = Vec::new();
        for item in &raw_shared {
            let Some(object) = item.as_object() else {
                return Err(ScopeError::Malformed(
                    "Phase-2 shared prerequisite must be an object".into(),
                ));
            };
            let Some(required_by) = object.get("requiredBy").and_then(Value::as_array) else {
                return Err(ScopeError::Malformed(
                    "Phase-2 shared prerequisite requiredBy must be an array".into(),
                ));
            };
            if !required_by
                .iter()
                .any(|value| value.as_str() == Some(unit_id.as_str()))
            {
                continue;
            }
            let dependency_id = object
                .get("dependencyId")
                .and_then(Value::as_str)
                .filter(|value| value.starts_with("shared:"))
                .ok_or_else(|| {
                    ScopeError::Malformed(
                        "Phase-2 shared prerequisite has a malformed dependency ID".into(),
                    )
                })?;
            if seen.iter().any(|value| value == dependency_id) {
                return Err(ScopeError::Malformed(format!(
                    "Phase-2 shared prerequisite is duplicated: {dependency_id}"
                )));
            }
            seen.push(dependency_id.to_string());
            shared_prerequisites.push(item.clone());
        }
        shared_prerequisites.sort_by_key(|item| {
            item.get("dependencyId")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string()
        });

        // The bundle must describe the same unit, plan, specification, and
        // index the plan does. Any drift here would silently formalize the
        // wrong text.
        let same = |key: &str| bundle.get(key) == plan.get(key);
        if bundle.get("unit") != Some(unit) {
            return Err(ScopeError::Mismatch(
                "Phase-3 evidence unit does not match the Phase-2 planned unit".into(),
            ));
        }
        if !same("planRunId") {
            return Err(ScopeError::Mismatch(
                "Phase-3 evidence planRunId does not match Phase 2".into(),
            ));
        }
        if !same("language") || !same("version") {
            return Err(ScopeError::Mismatch(
                "Phase-3 evidence specification identity does not match Phase 2".into(),
            ));
        }
        if !same("sourceDatabaseDigest") {
            return Err(ScopeError::Mismatch(
                "Phase-3 evidence source specification does not match Phase 2".into(),
            ));
        }

        let records = bundle
            .get("evidence")
            .and_then(Value::as_array)
            .filter(|items| !items.is_empty())
            .ok_or_else(|| {
                ScopeError::Malformed("Phase-3 evidence bundle must contain evidence".into())
            })?;
        let ids: Vec<String> = records
            .iter()
            .map(|item| {
                item.get("evidenceId")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string()
            })
            .collect();
        if ids.iter().any(|value| !value.starts_with("evidence:")) || !unique(&ids) {
            return Err(ScopeError::Malformed(
                "Phase-3 evidence IDs must be present and unique".into(),
            ));
        }
        for item in records {
            if item.get("unitId").and_then(Value::as_str) != Some(unit_id.as_str()) {
                return Err(ScopeError::Mismatch(
                    "Phase-3 evidence record belongs to a different unit".into(),
                ));
            }
            let complete = item
                .get("documentId")
                .and_then(Value::as_str)
                .is_some_and(|value| !value.is_empty())
                && item
                    .get("documentSha256")
                    .and_then(Value::as_str)
                    .is_some_and(|value| !value.is_empty())
                && matches!(
                    item.get("sourceType").and_then(Value::as_str),
                    Some("html" | "pdf")
                );
            if !complete {
                return Err(ScopeError::Malformed(
                    "Phase-3 evidence record has incomplete source specification identity".into(),
                ));
            }
        }

        // Supplemental resolutions are the Open Question Handler's output and
        // are explicitly non-normative.
        let resolutions = match bundle.get("resolutions") {
            None => Vec::new(),
            Some(Value::Array(items)) => items.clone(),
            Some(_) => {
                return Err(ScopeError::Malformed(
                    "Phase-3 supplemental resolutions must be an array".into(),
                ));
            }
        };
        let resolution_ids: Vec<String> = resolutions
            .iter()
            .map(|item| {
                item.get("resolutionId")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string()
            })
            .collect();
        if resolution_ids
            .iter()
            .any(|value| !value.starts_with("resolution:"))
        {
            return Err(ScopeError::Malformed(
                "supplemental resolution IDs must be present".into(),
            ));
        }
        let mut combined = ids.clone();
        combined.extend(resolution_ids.iter().cloned());
        if !unique(&resolution_ids) || !unique(&combined) {
            return Err(ScopeError::Malformed(
                "evidence and resolution IDs must be globally unique".into(),
            ));
        }
        for item in &resolutions {
            let valid = item.get("unitId").and_then(Value::as_str) == Some(unit_id.as_str())
                && item.get("nonNormative") == Some(&Value::Bool(true));
            if !valid {
                return Err(ScopeError::Malformed(
                    "supplemental resolution has an invalid unit or authority flag".into(),
                ));
            }
        }

        let bundle_hash = evidence_bundle_hash(bundle);
        let plan_run_id = plan
            .get("planRunId")
            .and_then(Value::as_str)
            .ok_or_else(|| ScopeError::Malformed("plan has no planRunId".into()))?;
        Ok(Self {
            plan_run_id: plan_run_id.to_string(),
            language: string(plan, "language")?,
            version: string(plan, "version")?,
            unit: unit.clone(),
            shared_prerequisites,
            run_id: stable_id(
                "semantic-run",
                &[plan_run_id, unit_id.as_str(), &bundle_hash],
                24,
            ),
            evidence_bundle_hash: bundle_hash,
            evidence_ids: combined,
            created_at: created_at.to_string(),
        })
    }

    pub fn to_json(&self) -> Value {
        let mut value = serde_json::to_value(self).unwrap_or_else(|_| json!({}));
        value["schemaVersion"] = json!(SEMANTICS_SCHEMA_VERSION);
        value
    }

    /// Wrap an accepted submission in its deterministic metadata envelope.
    ///
    /// `extractor` records the provider and model that actually ran. The Python
    /// implementation hardcoded `provider: "opencode"` and a fixed model list;
    /// with the agent runtime gone, the honest value is whatever produced it.
    pub fn artifact(&self, submission: &Value, extractor: &Value) -> Value {
        let outcome = submission
            .get("outcome")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let payload: Value = submission
            .as_object()
            .map(|object| {
                object
                    .iter()
                    .filter(|(key, _)| key.as_str() != "outcome")
                    .map(|(key, value)| (key.clone(), value.clone()))
                    .collect::<serde_json::Map<_, _>>()
            })
            .map(Value::Object)
            .unwrap_or_else(|| json!({}));

        let mut artifact = json!({
            "schemaVersion": SEMANTICS_SCHEMA_VERSION,
            "phase": "SEMANTIC_EXTRACTOR",
            "planRunId": self.plan_run_id,
            "language": self.language,
            "version": self.version,
            "unit": self.unit,
            "evidenceBundleHash": self.evidence_bundle_hash,
            "extractor": extractor,
            "runId": self.run_id,
            "createdAt": self.created_at,
            "outcome": outcome,
        });
        let key = if outcome == "SUCCESS" {
            "semantics"
        } else {
            "failure"
        };
        artifact[key] = payload;
        artifact
    }
}

fn unique(values: &[String]) -> bool {
    let mut sorted: Vec<&String> = values.iter().collect();
    sorted.sort();
    sorted.dedup();
    sorted.len() == values.len()
}

fn string(value: &Value, key: &str) -> Result<String, ScopeError> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| ScopeError::Malformed(format!("plan has no {key}")))
}
