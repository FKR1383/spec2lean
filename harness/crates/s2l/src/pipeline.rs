//! The pipeline runner: request in, checked Lean out.
//!
//! Each phase is already a self-contained command. This composes them without
//! reimplementing any of their logic, and stops at the first phase that cannot
//! honestly continue — a plan with a cycle, a unit whose evidence is
//! insufficient, a core that will not compile. Partial results are kept, because
//! a run that got three units through and failed on the fourth is worth more
//! than a run that reports only "failed".

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::Serialize;
use serde_json::Value;

/// What a phase did, recorded whether it succeeded or not.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PhaseRecord {
    pub phase: String,
    pub target: String,
    pub status: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub steps: Option<u32>,
}

impl PhaseRecord {
    pub fn ok(phase: &str, target: impl Into<String>) -> Self {
        Self {
            phase: phase.to_string(),
            target: target.into(),
            status: "PASS",
            detail: None,
            steps: None,
        }
    }

    pub fn failed(phase: &str, target: impl Into<String>, detail: impl Into<String>) -> Self {
        Self {
            phase: phase.to_string(),
            target: target.into(),
            status: "FAIL",
            detail: Some(detail.into()),
            steps: None,
        }
    }

    pub fn skipped(phase: &str, target: impl Into<String>, detail: impl Into<String>) -> Self {
        Self {
            phase: phase.to_string(),
            target: target.into(),
            status: "SKIPPED",
            detail: Some(detail.into()),
            steps: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RunManifest {
    pub schema_version: u32,
    pub started_at: String,
    pub finished_at: String,
    pub status: &'static str,
    pub root: String,
    pub phases: Vec<PhaseRecord>,
}

impl RunManifest {
    pub fn summary(&self) -> String {
        let mut lines = vec![format!("pipeline: {}", self.status)];
        for record in &self.phases {
            let mark = match record.status {
                "PASS" => "ok",
                "SKIPPED" => "--",
                _ => "FAIL",
            };
            let detail = record
                .detail
                .as_deref()
                .map(|value| format!("  {value}"))
                .unwrap_or_default();
            lines.push(format!("  [{mark}] {:<10} {}{detail}", record.phase, record.target));
        }
        lines.push(format!("artifacts: {}", self.root));
        lines.join("\n")
    }
}

/// Where each phase's artifacts live under one run root.
pub struct Layout {
    pub root: PathBuf,
}

impl Layout {
    pub fn new(root: PathBuf) -> Self {
        Self { root }
    }

    pub fn plan(&self) -> PathBuf {
        self.root.join("plan")
    }

    /// One directory per unit, holding its bundle and its semantic artifact.
    pub fn unit(&self, unit_id: &str) -> PathBuf {
        self.root.join("units").join(slug(unit_id))
    }

    pub fn core(&self) -> PathBuf {
        self.root.join("core")
    }

    pub fn group(&self, group: &str) -> PathBuf {
        self.root.join("groups").join(slug(group))
    }
}

/// A filesystem-safe, still-recognisable name.
fn slug(value: &str) -> String {
    let cleaned: String = value
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect();
    let trimmed = cleaned.trim_matches('-').to_string();
    if trimmed.is_empty() {
        "unnamed".to_string()
    } else {
        trimmed
    }
}

/// The units of a plan, in the order the plan says they can be processed.
///
/// Units inside a cycle, and units downstream of one, are excluded: the plan
/// itself reports them as unorderable, and running them anyway would formalize
/// a dependency the specification never resolved.
pub fn processable_units(plan: &Value) -> (Vec<String>, Vec<String>) {
    let ordered: Vec<String> = plan
        .get("processingLayers")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
        .iter()
        .filter_map(|layer| layer.get("unitIds")?.as_array())
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect();
    let mut excluded: Vec<String> = plan
        .get("blockedUnitIds")
        .and_then(Value::as_array)
        .map(|items| items.iter().filter_map(Value::as_str).map(str::to_string).collect())
        .unwrap_or_default();
    excluded.extend(
        plan.get("cycles")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default()
            .iter()
            .filter_map(|cycle| cycle.get("unitIds")?.as_array())
            .flatten()
            .filter_map(Value::as_str)
            .map(str::to_string),
    );
    excluded.sort();
    excluded.dedup();
    (ordered, excluded)
}

/// A group name with the units it names.
pub type GroupMembers = (String, Vec<String>);

/// Groups whose every unit completed, and the groups that cannot be attempted.
pub fn ready_groups(
    plan: &Value,
    completed: &BTreeMap<String, Value>,
) -> (Vec<GroupMembers>, Vec<GroupMembers>) {
    let mut ready = Vec::new();
    let mut blocked = Vec::new();
    for group in plan
        .get("translationGroups")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
    {
        let Some(name) = group.get("name").and_then(Value::as_str) else {
            continue;
        };
        let members: Vec<String> = group
            .get("unitIds")
            .and_then(Value::as_array)
            .map(|items| items.iter().filter_map(Value::as_str).map(str::to_string).collect())
            .unwrap_or_default();
        let missing: Vec<String> = members
            .iter()
            .filter(|unit_id| !completed.contains_key(*unit_id))
            .cloned()
            .collect();
        if missing.is_empty() {
            ready.push((name.to_string(), members));
        } else {
            blocked.push((name.to_string(), missing));
        }
    }
    (ready, blocked)
}

pub fn write_manifest(layout: &Layout, manifest: &RunManifest) -> Result<(), String> {
    std::fs::create_dir_all(&layout.root).map_err(|error| error.to_string())?;
    let value = serde_json::to_value(manifest).map_err(|error| error.to_string())?;
    std::fs::write(
        layout.root.join("run.json"),
        format!("{}\n", serde_json::to_string_pretty(&value).unwrap_or_default()),
    )
    .map_err(|error| error.to_string())
}

/// A run that has not started any phase yet.
pub fn empty_manifest(root: &Path, started_at: String) -> RunManifest {
    RunManifest {
        schema_version: 1,
        started_at,
        finished_at: String::new(),
        status: "PASS",
        root: root.display().to_string(),
        phases: Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn slugs_stay_recognisable_and_filesystem_safe() {
        assert_eq!(slug("unit:c9bd6fe0"), "unit-c9bd6fe0");
        assert_eq!(slug("TransportBinding"), "TransportBinding");
        assert_eq!(slug("::::"), "unnamed");
    }

    #[test]
    fn units_inside_or_downstream_of_a_cycle_are_excluded() {
        let plan = json!({
            "processingLayers": [{"layer": 0, "unitIds": ["unit:a", "unit:b"]}],
            "cycles": [{"unitIds": ["unit:x", "unit:y"]}],
            "blockedUnitIds": ["unit:z"],
        });
        let (ordered, excluded) = processable_units(&plan);
        assert_eq!(ordered, vec!["unit:a", "unit:b"]);
        // The cycle members and everything downstream of them.
        assert_eq!(excluded, vec!["unit:x", "unit:y", "unit:z"]);
    }

    #[test]
    fn a_group_waits_for_every_one_of_its_units() {
        let plan = json!({"translationGroups": [
            {"name": "Whole", "unitIds": ["unit:a", "unit:b"]},
            {"name": "Other", "unitIds": ["unit:c"]},
        ]});
        let completed = BTreeMap::from([("unit:a".to_string(), json!({}))]);
        let (ready, blocked) = ready_groups(&plan, &completed);
        assert!(ready.is_empty());
        // Reported in plan order, each naming exactly what it is waiting for.
        assert_eq!(blocked[0].0, "Whole");
        assert_eq!(blocked[0].1, vec!["unit:b"]);
        assert_eq!(blocked[1].0, "Other");
        assert_eq!(blocked[1].1, vec!["unit:c"]);

        let completed = BTreeMap::from([
            ("unit:a".to_string(), json!({})),
            ("unit:b".to_string(), json!({})),
            ("unit:c".to_string(), json!({})),
        ]);
        let (ready, blocked) = ready_groups(&plan, &completed);
        assert_eq!(ready.len(), 2);
        assert!(blocked.is_empty());
    }
}
