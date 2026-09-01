use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::{Value, json};
use spec2lean_specdb::{NodeId, SpanId};

/// Records precisely which identifiers this session actually received.
///
/// This is the anti-hallucination boundary. A node may only be *selected* if
/// the session was shown its exact text; a span may only be selected if the
/// session was shown that span. Everything the model could otherwise invent —
/// node IDs, span IDs, provenance — is rejected here rather than trusted.
#[derive(Debug, Default)]
pub struct ExposureLedger {
    nodes: BTreeMap<NodeId, BTreeSet<String>>,
    selectable: BTreeSet<NodeId>,
    /// Nodes whose exact text was shown only in part, because it exceeded the
    /// display limit. Selecting one of these without naming spans would
    /// attribute text the session never saw.
    truncated: BTreeSet<NodeId>,
    spans: BTreeSet<SpanId>,
    calls: Vec<Value>,
}

impl ExposureLedger {
    pub fn expose(&mut self, node_id: &NodeId, basis: &str) {
        self.nodes
            .entry(node_id.clone())
            .or_default()
            .insert(basis.to_string());
    }

    /// Expose a node together with its exact text, which is what makes it
    /// selectable, plus the spans that were shown alongside it.
    pub fn expose_selectable(&mut self, node_id: &NodeId, basis: &str, spans: &[SpanId]) {
        self.expose_text(node_id, basis, spans, false);
    }

    /// As above, recording whether the text shown was complete.
    pub fn expose_text(
        &mut self,
        node_id: &NodeId,
        basis: &str,
        spans: &[SpanId],
        truncated: bool,
    ) {
        self.expose(node_id, basis);
        self.selectable.insert(node_id.clone());
        self.spans.extend(spans.iter().cloned());
        if truncated {
            self.truncated.insert(node_id.clone());
        } else {
            // Seeing it in full later supersedes an earlier partial view.
            self.truncated.remove(node_id);
        }
    }

    /// Whether this node was only ever shown in part.
    pub fn is_truncated(&self, node_id: &NodeId) -> bool {
        self.truncated.contains(node_id)
    }

    pub fn is_discovered(&self, node_id: &NodeId) -> bool {
        self.nodes.contains_key(node_id)
    }

    pub fn is_selectable(&self, node_id: &NodeId) -> bool {
        self.selectable.contains(node_id)
    }

    pub fn is_span_exposed(&self, span_id: &SpanId) -> bool {
        self.spans.contains(span_id)
    }

    pub fn basis(&self, node_id: &NodeId) -> Vec<String> {
        self.nodes
            .get(node_id)
            .map(|bases| bases.iter().cloned().collect())
            .unwrap_or_default()
    }

    pub fn record_call(&mut self, name: &str, arguments: &Value) {
        self.calls
            .push(json!({"tool": name, "arguments": arguments}));
    }

    pub fn to_json(&self) -> Value {
        json!({
            "exposedNodes": self
                .nodes
                .iter()
                .map(|(node_id, bases)| json!({
                    "nodeId": node_id,
                    "basis": bases.iter().collect::<Vec<_>>(),
                    "selectable": self.selectable.contains(node_id),
                    "textTruncated": self.truncated.contains(node_id),
                }))
                .collect::<Vec<_>>(),
            "exposedSpanIds": self.spans.iter().collect::<Vec<_>>(),
            "toolCalls": self.calls,
        })
    }
}

/// Serialisable snapshot of the ledger, written next to the bundle.
#[derive(Debug, Serialize)]
pub struct ExposureTrace(pub Value);
