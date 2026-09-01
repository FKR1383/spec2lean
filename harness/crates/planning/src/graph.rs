use std::collections::{BTreeMap, BTreeSet};

use serde_json::{Value, json};

/// Strongly connected components, iteratively.
///
/// Tarjan's algorithm without recursion: a plan over a full specification can
/// have thousands of units, and a recursive walk would risk overflowing the
/// stack on exactly the largest, most valuable input.
pub fn strongly_connected_components(
    vertices: &[String],
    edges: &[(String, String)],
) -> Vec<Vec<String>> {
    let mut outgoing: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    for (source, target) in edges {
        outgoing.entry(source).or_default().push(target);
    }
    for targets in outgoing.values_mut() {
        targets.sort();
    }

    let mut index = 0usize;
    let mut indices: BTreeMap<&str, usize> = BTreeMap::new();
    let mut lowlinks: BTreeMap<&str, usize> = BTreeMap::new();
    let mut stack: Vec<&str> = Vec::new();
    let mut on_stack: BTreeSet<&str> = BTreeSet::new();
    let mut result: Vec<Vec<String>> = Vec::new();

    let mut ordered: Vec<&str> = vertices.iter().map(String::as_str).collect();
    ordered.sort();

    for root in ordered {
        if indices.contains_key(root) {
            continue;
        }
        // Each frame is (vertex, next child offset).
        let mut frames: Vec<(&str, usize)> = vec![(root, 0)];
        indices.insert(root, index);
        lowlinks.insert(root, index);
        index += 1;
        stack.push(root);
        on_stack.insert(root);

        while let Some((vertex, offset)) = frames.pop() {
            let children = outgoing.get(vertex).map(Vec::as_slice).unwrap_or_default();
            if offset < children.len() {
                let target = children[offset];
                frames.push((vertex, offset + 1));
                if !indices.contains_key(target) {
                    indices.insert(target, index);
                    lowlinks.insert(target, index);
                    index += 1;
                    stack.push(target);
                    on_stack.insert(target);
                    frames.push((target, 0));
                } else if on_stack.contains(target) {
                    let candidate = indices[target];
                    let current = lowlinks[vertex];
                    lowlinks.insert(vertex, current.min(candidate));
                }
                continue;
            }
            // Every child explored: fold this vertex's lowlink into its parent.
            if let Some((parent, _)) = frames.last() {
                let child = lowlinks[vertex];
                let current = lowlinks[*parent];
                lowlinks.insert(parent, current.min(child));
            }
            if lowlinks[vertex] == indices[vertex] {
                let mut component: Vec<String> = Vec::new();
                while let Some(item) = stack.pop() {
                    on_stack.remove(item);
                    component.push(item.to_string());
                    if item == vertex {
                        break;
                    }
                }
                component.sort();
                result.push(component);
            }
        }
    }
    result.sort_by(|left, right| left[0].cmp(&right[0]));
    result
}

/// Layer the requested units by dependency depth, and report what cannot be
/// ordered.
///
/// A unit inside a cycle cannot be processed, and neither can anything
/// downstream of one — reporting those separately is what lets a run proceed on
/// the healthy part of a plan instead of failing whole.
pub fn derive_processing_order(
    requested_unit_ids: &[String],
    dependencies: &[Value],
) -> (Vec<Value>, Vec<Value>, Vec<String>) {
    let requested: BTreeSet<&str> = requested_unit_ids.iter().map(String::as_str).collect();
    let edges: Vec<(String, String)> = dependencies
        .iter()
        .filter_map(|edge| {
            let source = edge.get("from")?.as_str()?;
            let target = edge.get("to")?.as_str()?;
            (requested.contains(source) && requested.contains(target))
                .then(|| (source.to_string(), target.to_string()))
        })
        .collect();

    let components = strongly_connected_components(requested_unit_ids, &edges);
    // A unit that depends on itself is a cycle of one. Tarjan reports it as a
    // singleton component like any other, so it has to be recognised by the
    // self-edge. Plan validation rejects self-edges upstream, but a graph
    // routine that silently drops such a unit from every output — no layer, no
    // cycle, no blocked list — is wrong on its own terms.
    let self_looping: BTreeSet<&str> = edges
        .iter()
        .filter(|(source, target)| source == target)
        .map(|(source, _)| source.as_str())
        .collect();
    let is_cycle = |component: &Vec<String>| {
        component.len() > 1
            || component
                .first()
                .is_some_and(|unit_id| self_looping.contains(unit_id.as_str()))
    };
    let cyclic: BTreeSet<String> = components
        .iter()
        .filter(|component| is_cycle(component))
        .flatten()
        .cloned()
        .collect();
    let cycles: Vec<Value> = components
        .iter()
        .filter(|component| is_cycle(component))
        .map(|component| json!({"unitIds": component}))
        .collect();

    let mut outgoing: BTreeMap<&str, BTreeSet<&str>> = BTreeMap::new();
    for (source, target) in &edges {
        outgoing.entry(source).or_default().insert(target);
    }

    // Anything reachable from a cycle is blocked by it.
    let mut blocked: BTreeSet<String> = cyclic.clone();
    let mut frontier: Vec<String> = cyclic.iter().cloned().collect();
    while let Some(source) = frontier.pop() {
        for target in outgoing.get(source.as_str()).into_iter().flatten() {
            if blocked.insert((*target).to_string()) {
                frontier.push((*target).to_string());
            }
        }
    }

    let mut remaining: BTreeSet<String> = requested
        .iter()
        .map(|id| (*id).to_string())
        .filter(|id| !blocked.contains(id))
        .collect();
    let mut incoming: BTreeMap<String, BTreeSet<String>> = remaining
        .iter()
        .map(|id| (id.clone(), BTreeSet::new()))
        .collect();
    let mut forward: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (source, target) in &edges {
        if remaining.contains(source) && remaining.contains(target) {
            incoming.entry(target.clone()).or_default().insert(source.clone());
            forward.entry(source.clone()).or_default().insert(target.clone());
        }
    }

    let mut layers: Vec<Value> = Vec::new();
    let mut layer_index = 0;
    while !remaining.is_empty() {
        let ready: Vec<String> = remaining
            .iter()
            .filter(|id| incoming.get(*id).is_none_or(BTreeSet::is_empty))
            .cloned()
            .collect();
        if ready.is_empty() {
            // Defensive: component detection should have removed every cycle.
            break;
        }
        layers.push(json!({"layer": layer_index, "unitIds": ready}));
        layer_index += 1;
        for source in &ready {
            remaining.remove(source);
            for target in forward.get(source).into_iter().flatten() {
                if let Some(sources) = incoming.get_mut(target) {
                    sources.remove(source);
                }
            }
        }
    }

    let blocked_only: Vec<String> = blocked
        .iter()
        .filter(|id| !cyclic.contains(*id))
        .cloned()
        .collect();
    (layers, cycles, blocked_only)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn edge(from: &str, to: &str) -> Value {
        json!({"from": from, "to": to})
    }

    #[test]
    fn independent_units_all_land_in_the_first_layer() {
        let units = vec!["unit:a".to_string(), "unit:b".to_string()];
        let (layers, cycles, blocked) = derive_processing_order(&units, &[]);
        assert_eq!(layers.len(), 1);
        assert_eq!(layers[0]["unitIds"], json!(["unit:a", "unit:b"]));
        assert!(cycles.is_empty());
        assert!(blocked.is_empty());
    }

    #[test]
    fn a_chain_is_layered_in_dependency_order() {
        let units = vec!["unit:a".into(), "unit:b".into(), "unit:c".into()];
        let edges = [edge("unit:a", "unit:b"), edge("unit:b", "unit:c")];
        let (layers, cycles, blocked) = derive_processing_order(&units, &edges);
        assert_eq!(layers.len(), 3);
        assert_eq!(layers[0]["unitIds"], json!(["unit:a"]));
        assert_eq!(layers[2]["unitIds"], json!(["unit:c"]));
        assert!(cycles.is_empty() && blocked.is_empty());
    }

    #[test]
    fn a_cycle_is_reported_and_everything_downstream_is_blocked() {
        let units = vec![
            "unit:a".into(), "unit:b".into(), "unit:c".into(), "unit:d".into(),
        ];
        let edges = [
            edge("unit:a", "unit:b"),
            edge("unit:b", "unit:a"),
            edge("unit:b", "unit:c"),
            // d is untouched by the cycle and must still be processable.
        ];
        let (layers, cycles, blocked) = derive_processing_order(&units, &edges);
        assert_eq!(cycles.len(), 1);
        assert_eq!(cycles[0]["unitIds"], json!(["unit:a", "unit:b"]));
        assert_eq!(blocked, vec!["unit:c".to_string()]);
        // The healthy part of the plan still gets an order.
        assert_eq!(layers.len(), 1);
        assert_eq!(layers[0]["unitIds"], json!(["unit:d"]));
    }

    #[test]
    fn a_unit_that_depends_on_itself_is_a_cycle_of_one() {
        let units = vec!["unit:a".to_string(), "unit:b".to_string()];
        let edges = [edge("unit:a", "unit:a")];
        let (layers, cycles, blocked) = derive_processing_order(&units, &edges);
        // It must appear somewhere: reporting no layer, no cycle and no blocked
        // unit would lose the unit entirely.
        assert_eq!(cycles.len(), 1);
        assert_eq!(cycles[0]["unitIds"], json!(["unit:a"]));
        assert!(blocked.is_empty());
        // The healthy unit still gets ordered.
        assert_eq!(layers[0]["unitIds"], json!(["unit:b"]));
    }

    #[test]
    fn components_are_found_without_recursing() {
        // A long chain would overflow a recursive implementation.
        let units: Vec<String> = (0..5000).map(|index| format!("unit:{index:05}")).collect();
        let edges: Vec<(String, String)> = units
            .windows(2)
            .map(|pair| (pair[0].clone(), pair[1].clone()))
            .collect();
        let components = strongly_connected_components(&units, &edges);
        assert_eq!(components.len(), 5000);
        assert!(components.iter().all(|component| component.len() == 1));
    }

    #[test]
    fn edges_touching_unrequested_units_are_ignored() {
        let units = vec!["unit:a".to_string()];
        let edges = [edge("prerequisite:x", "unit:a")];
        let (layers, _, _) = derive_processing_order(&units, &edges);
        assert_eq!(layers[0]["unitIds"], json!(["unit:a"]));
    }
}
