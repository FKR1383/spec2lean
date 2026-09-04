//! Tasks, read off the plan.
//!
//! The plan already answers the two questions that make ordering hard: which
//! properties depend on which, and which concepts more than one property needs
//! to mean the same. So nothing here decides anything — a task is a translation
//! group, and its dependencies are the groups that own the units its own units
//! depend on. Deriving rather than re-deciding is the point: two components
//! that both work out an order will eventually disagree about one.

use std::collections::{BTreeMap, BTreeSet};

use serde_json::Value;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Task {
    pub name: String,
    pub unit_ids: Vec<String>,
    /// Groups that must be formalized first. Their Lean becomes this task's
    /// dependencies, which is what stops two tasks defining the same concept
    /// twice and incompatibly.
    pub depends_on: Vec<String>,
}

/// Every group in the plan, ordered so a task never runs before something it
/// depends on. A group inside a dependency cycle is returned as blocked rather
/// than ordered arbitrarily.
pub fn tasks_from_plan(plan: &Value) -> (Vec<Task>, Vec<(String, String)>) {
    let groups = plan["translationGroups"].as_array().cloned().unwrap_or_default();

    let mut owner: BTreeMap<String, String> = BTreeMap::new();
    for group in &groups {
        let Some(name) = group["name"].as_str() else {
            continue;
        };
        for unit in group["unitIds"].as_array().into_iter().flatten() {
            if let Some(unit) = unit.as_str() {
                owner.insert(unit.to_string(), name.to_string());
            }
        }
    }

    // Unit-level dependencies become group-level ones. A dependency inside a
    // group is already satisfied by being in the same file.
    let mut edges: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for group in &groups {
        if let Some(name) = group["name"].as_str() {
            edges.entry(name.to_string()).or_default();
        }
    }
    for dependency in plan["dependencies"].as_array().into_iter().flatten() {
        let (Some(from), Some(to)) = (dependency["from"].as_str(), dependency["to"].as_str())
        else {
            continue;
        };
        if let (Some(source), Some(target)) = (owner.get(from), owner.get(to))
            && source != target
        {
            edges.entry(target.clone()).or_default().insert(source.clone());
        }
    }

    let mut ordered: Vec<Task> = Vec::new();
    let mut done: BTreeSet<String> = BTreeSet::new();
    let mut remaining: Vec<&Value> = groups.iter().collect();

    while !remaining.is_empty() {
        let ready: Vec<&Value> = remaining
            .iter()
            .copied()
            .filter(|group| {
                group["name"].as_str().is_some_and(|name| {
                    edges
                        .get(name)
                        .is_none_or(|needs| needs.iter().all(|need| done.contains(need)))
                })
            })
            .collect();
        if ready.is_empty() {
            break;
        }
        for group in ready {
            let name = group["name"].as_str().unwrap_or_default().to_string();
            let unit_ids = group["unitIds"]
                .as_array()
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect();
            let depends_on = edges.get(&name).cloned().unwrap_or_default().into_iter().collect();
            done.insert(name.clone());
            ordered.push(Task { name, unit_ids, depends_on });
        }
        remaining.retain(|group| {
            group["name"].as_str().is_none_or(|name| !done.contains(name))
        });
    }

    let blocked = remaining
        .iter()
        .filter_map(|group| group["name"].as_str())
        .map(|name| {
            let waiting: Vec<String> = edges
                .get(name)
                .into_iter()
                .flatten()
                .filter(|need| !done.contains(*need))
                .cloned()
                .collect();
            (name.to_string(), waiting.join(", "))
        })
        .collect();
    (ordered, blocked)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn plan(groups: Value, dependencies: Value) -> Value {
        json!({"translationGroups": groups, "dependencies": dependencies})
    }

    #[test]
    fn a_group_runs_after_the_groups_its_units_depend_on() {
        let value = plan(
            json!([
                {"name": "Uses", "unitIds": ["unit:b"]},
                {"name": "Defines", "unitIds": ["unit:a"]},
            ]),
            json!([{"from": "unit:a", "to": "unit:b"}]),
        );
        let (tasks, blocked) = tasks_from_plan(&value);
        assert!(blocked.is_empty());
        let order: Vec<_> = tasks.iter().map(|task| task.name.as_str()).collect();
        assert_eq!(order, vec!["Defines", "Uses"]);
        assert_eq!(tasks[1].depends_on, vec!["Defines".to_string()]);
    }

    #[test]
    fn a_dependency_inside_one_group_is_not_a_dependency_between_tasks() {
        // Both units land in the same file, so the edge is already satisfied.
        let value = plan(
            json!([{"name": "Together", "unitIds": ["unit:a", "unit:b"]}]),
            json!([{"from": "unit:a", "to": "unit:b"}]),
        );
        let (tasks, _) = tasks_from_plan(&value);
        assert_eq!(tasks.len(), 1);
        assert!(tasks[0].depends_on.is_empty(), "a group cannot wait for itself");
    }

    #[test]
    fn a_cycle_is_reported_as_blocked_rather_than_given_some_order() {
        let value = plan(
            json!([
                {"name": "A", "unitIds": ["unit:a"]},
                {"name": "B", "unitIds": ["unit:b"]},
            ]),
            json!([{"from": "unit:a", "to": "unit:b"}, {"from": "unit:b", "to": "unit:a"}]),
        );
        let (tasks, blocked) = tasks_from_plan(&value);
        assert!(tasks.is_empty());
        assert_eq!(blocked.len(), 2, "neither group can go first: {blocked:?}");
    }

    #[test]
    fn an_external_prerequisite_never_becomes_a_task_dependency() {
        // Externals name documents outside the corpus. Nothing can formalize
        // them, so waiting on one would block the task for ever.
        let value = plan(
            json!([{"name": "Only", "unitIds": ["unit:a"]}]),
            json!([{"from": "prerequisite:x", "to": "unit:a"}]),
        );
        let (tasks, blocked) = tasks_from_plan(&value);
        assert!(blocked.is_empty());
        assert_eq!(tasks.len(), 1);
        assert!(tasks[0].depends_on.is_empty());
    }
}
