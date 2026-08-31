use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use spec2lean_specdb::{NodeId, UnitId};

/// Why a node is inside this session's boundary. The string form is recorded
/// verbatim in each evidence record's `selectionBasis`, so a reader can see
/// exactly how the retriever reached every passage it selected.
pub type Basis = String;

#[derive(Debug)]
pub enum ScopeError {
    UnitNotUnique { plan_run_id: String, unit_id: String },
    MissingField(&'static str),
    BadId(spec2lean_specdb::IdError),
}

impl std::fmt::Display for ScopeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::UnitNotUnique {
                plan_run_id,
                unit_id,
            } => write!(
                f,
                "unit is not uniquely present in plan {plan_run_id}: {unit_id}"
            ),
            Self::MissingField(name) => write!(f, "plan is missing the required field {name}"),
            Self::BadId(error) => write!(f, "plan contains a malformed identifier: {error}"),
        }
    }
}

impl std::error::Error for ScopeError {}

impl From<spec2lean_specdb::IdError> for ScopeError {
    fn from(error: spec2lean_specdb::IdError) -> Self {
        Self::BadId(error)
    }
}

/// The deterministic Phase-2 boundary for one retriever session.
///
/// Plan-authored payloads (`unit`, prerequisites, dependencies) stay as opaque
/// JSON because they are passed through into the bundle unchanged; only the
/// fields this phase actually reasons about are given types.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EvidenceScope {
    pub plan_run_id: String,
    pub language: String,
    pub version: String,
    pub source_database_digest: String,
    pub unit: Value,
    #[serde(rename = "relevantExternalPrerequisites", default)]
    pub prerequisites: Vec<Value>,
    #[serde(rename = "relevantSharedPrerequisites", default)]
    pub shared_prerequisites: Vec<Value>,
    #[serde(rename = "relatedDependencies", default)]
    pub dependencies: Vec<Value>,
    #[serde(rename = "seedNodes")]
    pub seed_nodes: Vec<SeedNode>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SeedNode {
    pub node_id: NodeId,
    pub basis: Basis,
}

impl EvidenceScope {
    pub fn unit_id(&self) -> Result<UnitId, spec2lean_specdb::IdError> {
        UnitId::parse(self.unit.get("unitId").and_then(Value::as_str).unwrap_or(""))
    }

    /// The node IDs Phase 2 attached directly to the unit.
    pub fn unit_source_node_ids(&self) -> Vec<NodeId> {
        node_ids(&self.unit, "sourceNodeIds")
    }

    /// Derive the boundary for one unit from a Phase-2 plan.
    pub fn from_plan(plan: &Value, unit_id: &UnitId) -> Result<Self, ScopeError> {
        let plan_run_id = string_field(plan, "planRunId")?;
        let matches: Vec<&Value> = array(plan, "requestedUnits")
            .iter()
            .filter(|item| item.get("unitId").and_then(Value::as_str) == Some(unit_id.as_str()))
            .copied()
            .collect();
        let [unit] = matches[..] else {
            return Err(ScopeError::UnitNotUnique {
                plan_run_id,
                unit_id: unit_id.to_string(),
            });
        };

        let dependencies: Vec<Value> = array(plan, "dependencies")
            .iter()
            .filter(|edge| {
                edge.get("from").and_then(Value::as_str) == Some(unit_id.as_str())
                    || edge.get("to").and_then(Value::as_str) == Some(unit_id.as_str())
            })
            .map(|edge| (*edge).clone())
            .collect();

        let mut prerequisite_ids: Vec<&str> = Vec::new();
        for edge in &dependencies {
            for key in ["from", "to"] {
                if let Some(value) = edge.get(key).and_then(Value::as_str)
                    && value.starts_with("prerequisite:")
                    && !prerequisite_ids.contains(&value)
                {
                    prerequisite_ids.push(value);
                }
            }
        }
        let prerequisites: Vec<Value> = array(plan, "externalPrerequisites")
            .iter()
            .filter(|item| {
                item.get("prerequisiteId")
                    .and_then(Value::as_str)
                    .is_some_and(|id| prerequisite_ids.contains(&id))
            })
            .map(|item| (*item).clone())
            .collect();
        let shared_prerequisites: Vec<Value> = array(plan, "sharedPrerequisites")
            .iter()
            .filter(|item| {
                item.get("requiredBy")
                    .and_then(Value::as_array)
                    .is_some_and(|required| {
                        required
                            .iter()
                            .any(|value| value.as_str() == Some(unit_id.as_str()))
                    })
            })
            .map(|item| (*item).clone())
            .collect();

        // Insertion-ordered de-duplication, matching the Python `dict.fromkeys`.
        let mut seed_nodes: Vec<SeedNode> = Vec::new();
        let push = |node_id: NodeId, basis: Basis, seeds: &mut Vec<SeedNode>| {
            if !seeds
                .iter()
                .any(|seed| seed.node_id == node_id && seed.basis == basis)
            {
                seeds.push(SeedNode { node_id, basis });
            }
        };
        for node_id in node_ids(unit, "sourceNodeIds") {
            push(node_id, "UNIT_SOURCE".to_string(), &mut seed_nodes);
        }
        for item in &prerequisites {
            let basis = format!(
                "PREREQUISITE:{}",
                item.get("prerequisiteId")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
            );
            for node_id in node_ids(item, "sourceNodeIds") {
                push(node_id, basis.clone(), &mut seed_nodes);
            }
        }
        for item in &shared_prerequisites {
            let basis = format!(
                "SHARED_PREREQUISITE:{}",
                item.get("dependencyId")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
            );
            for node_id in node_ids(item, "sourceNodeIds") {
                push(node_id, basis.clone(), &mut seed_nodes);
            }
        }
        for (index, edge) in dependencies.iter().enumerate() {
            let basis = format!("PHASE2_DEPENDENCY:{index}");
            for node_id in node_ids(edge, "supportingNodeIds") {
                push(node_id, basis.clone(), &mut seed_nodes);
            }
        }

        Ok(Self {
            plan_run_id,
            language: string_field(plan, "language")?,
            version: string_field(plan, "version")?,
            source_database_digest: string_field(plan, "sourceDatabaseDigest")?,
            unit: unit.clone(),
            prerequisites,
            shared_prerequisites,
            dependencies,
            seed_nodes,
        })
    }

    pub fn to_json(&self) -> Value {
        let mut value = serde_json::to_value(self).unwrap_or_else(|_| json!({}));
        value["schemaVersion"] = json!(1);
        value
    }
}

fn array<'a>(value: &'a Value, key: &str) -> Vec<&'a Value> {
    value
        .get(key)
        .and_then(Value::as_array)
        .map(|items| items.iter().collect())
        .unwrap_or_default()
}

fn node_ids(value: &Value, key: &str) -> Vec<NodeId> {
    value
        .get(key)
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .filter_map(|raw| NodeId::parse(raw).ok())
                .collect()
        })
        .unwrap_or_default()
}

fn string_field(value: &Value, key: &'static str) -> Result<String, ScopeError> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or(ScopeError::MissingField(key))
}
