use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::Value;
use spec2lean_evidence::validation::span_text;
use spec2lean_specdb::{NodeId, SpanId, SpecDb};
use spec2lean_translation::source::declarations;

use crate::CheckInputs;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BrokenLink {
    pub code: &'static str,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub declaration: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unit_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub claim_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub evidence_id: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TraceabilityReport {
    pub status: &'static str,
    pub declarations_checked: usize,
    pub evidence_verified: usize,
    pub broken: Vec<BrokenLink>,
}

impl TraceabilityReport {
    pub fn passed(&self) -> bool {
        self.status == "PASS"
    }

    pub fn summary(&self) -> String {
        if self.passed() {
            return format!(
                "traceability: PASS ({} declaration(s) trace to {} evidence item(s) still matching the index)",
                self.declarations_checked, self.evidence_verified
            );
        }
        let mut lines = vec![format!("traceability: FAIL ({} broken)", self.broken.len())];
        for link in self.broken.iter().take(20) {
            lines.push(format!("  {}: {}", link.code, link.message));
        }
        lines.join("\n")
    }
}

fn broken(code: &'static str, message: String) -> BrokenLink {
    BrokenLink {
        code,
        message,
        declaration: None,
        unit_id: None,
        claim_id: None,
        evidence_id: None,
    }
}

/// Re-derive an evidence record's exact text from the index and compare.
///
/// This is the check that makes the whole chain mean something. Everything
/// upstream trusts that a bundle written earlier still describes the
/// specification; here that is verified rather than assumed. It catches an
/// index rebuilt under the artifacts, a hand-edited bundle, and a record whose
/// text drifted from the nodes it names.
fn verify_evidence(db: &SpecDb, record: &Value) -> Result<(), String> {
    let node_ids: Vec<NodeId> = record
        .get("sourceNodeIds")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
        .iter()
        .filter_map(Value::as_str)
        .map(NodeId::parse)
        .collect::<Result<_, _>>()
        .map_err(|error| error.to_string())?;
    if node_ids.is_empty() {
        return Err("the record names no source nodes".into());
    }
    let span_ids: Vec<SpanId> = record
        .get("sourceSpanIds")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or_default()
        .iter()
        .filter_map(Value::as_str)
        .map(SpanId::parse)
        .collect::<Result<_, _>>()
        .map_err(|error| error.to_string())?;

    let mut rows = Vec::with_capacity(node_ids.len());
    for node_id in &node_ids {
        rows.push(
            db.node(node_id)
                .map_err(|_| format!("source node is no longer in the index: {node_id}"))?,
        );
    }

    // The document identity the record claims must still be the index's.
    if let Some(recorded) = record.get("documentSha256").and_then(Value::as_str)
        && recorded != rows[0].document_sha256
    {
        return Err(format!(
            "the document has changed since this evidence was retrieved: recorded {recorded}, index has {}",
            rows[0].document_sha256
        ));
    }

    let derived = if span_ids.is_empty() {
        rows.iter()
            .map(|row| row.raw_text.as_str())
            .collect::<Vec<_>>()
            .join("\n")
    } else {
        // Re-read the named spans and rebuild the text the same way Phase 3 did.
        let mut spans = db
            .spans_by_id(&span_ids)
            .map_err(|error| error.to_string())?;
        let order: BTreeMap<&NodeId, usize> = node_ids
            .iter()
            .enumerate()
            .map(|(index, node_id)| (node_id, index))
            .collect();
        if spans.len() != span_ids.len() {
            return Err("a named source span is no longer in the index".into());
        }
        spans.sort_by_key(|row| {
            (
                order.get(&row.node_id).copied().unwrap_or(usize::MAX),
                row.ordinal,
                row.span_id.as_str().to_string(),
            )
        });
        span_text(&spans)
    };

    let recorded = record
        .get("exactText")
        .and_then(Value::as_str)
        .ok_or("the record has no exactText")?;
    if derived != recorded {
        return Err(format!(
            "exact text no longer matches the index (recorded {} chars, index yields {})",
            recorded.chars().count(),
            derived.chars().count()
        ));
    }
    Ok(())
}

/// Backward traceability: from every Lean declaration to text still in the index.
pub fn traceability(
    inputs: &CheckInputs<'_>,
    db: &SpecDb,
) -> Result<TraceabilityReport, String> {
    let mut links: Vec<BrokenLink> = Vec::new();

    // What the Lean actually defines, in the group and in the core.
    let mut defined: BTreeSet<String> = declarations(inputs.source).into_keys().collect();
    if let Some(core_source) = inputs.core_source {
        defined.extend(declarations(core_source).into_keys());
    }

    // Claims and evidence, indexed by unit.
    let claims: BTreeMap<(&str, &str), &Value> = inputs
        .semantics
        .iter()
        .flat_map(|(unit_id, artifact)| {
            artifact
                .get("semantics")
                .and_then(|value| value.get("claims"))
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default()
                .iter()
                .filter_map(move |claim| {
                    Some(((unit_id.as_str(), claim.get("claimId")?.as_str()?), claim))
                })
        })
        .collect();
    let evidence: BTreeMap<(&str, &str), &Value> = inputs
        .bundles
        .iter()
        .flat_map(|(unit_id, bundle)| {
            let records = bundle
                .get("evidence")
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default();
            let resolutions = bundle
                .get("resolutions")
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default();
            records.iter().chain(resolutions).filter_map(move |item| {
                let id = item
                    .get("evidenceId")
                    .or_else(|| item.get("resolutionId"))?
                    .as_str()?;
                Some(((unit_id.as_str(), id), item))
            })
        })
        .collect();

    let mut declarations_checked = 0usize;
    let mut verified: BTreeSet<(String, String)> = BTreeSet::new();
    // Verify each evidence item once, whatever the outcome: several
    // declarations commonly reach the same passage, and repeating one drift
    // per declaration buries the fact that there is only one problem.
    let mut examined: BTreeSet<(String, String)> = BTreeSet::new();

    let mut walk = |manifest: &Value, links: &mut Vec<BrokenLink>, checked: &mut usize| {
        for mapping in manifest
            .get("declarations")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            let Some(name) = mapping.get("declaration").and_then(Value::as_str) else {
                links.push(broken("MALFORMED_MAPPING", "a declaration mapping has no name".into()));
                continue;
            };
            *checked += 1;
            if !defined.contains(name) {
                links.push(BrokenLink {
                    declaration: Some(name.to_string()),
                    ..broken(
                        "UNDEFINED_DECLARATION",
                        format!("the manifest names a declaration the Lean does not define: {name}"),
                    )
                });
                continue;
            }
            let refs = mapping
                .get("claimRefs")
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default();
            if refs.is_empty() {
                links.push(BrokenLink {
                    declaration: Some(name.to_string()),
                    ..broken(
                        "UNTRACEABLE_DECLARATION",
                        format!("{name} cites no semantic claim"),
                    )
                });
            }
            for reference in refs {
                let (Some(unit_id), Some(claim_id)) = (
                    reference.get("unitId").and_then(Value::as_str),
                    reference.get("claimId").and_then(Value::as_str),
                ) else {
                    links.push(BrokenLink {
                        declaration: Some(name.to_string()),
                        ..broken("MALFORMED_CLAIM_REF", format!("{name} has a malformed claim reference"))
                    });
                    continue;
                };
                let Some(claim) = claims.get(&(unit_id, claim_id)) else {
                    links.push(BrokenLink {
                        declaration: Some(name.to_string()),
                        unit_id: Some(unit_id.to_string()),
                        claim_id: Some(claim_id.to_string()),
                        ..broken(
                            "MISSING_CLAIM",
                            format!("{name} cites a claim no semantic artifact defines: {unit_id}/{claim_id}"),
                        )
                    });
                    continue;
                };
                for evidence_id in claim
                    .get("evidenceIds")
                    .and_then(Value::as_array)
                    .map(Vec::as_slice)
                    .unwrap_or_default()
                    .iter()
                    .filter_map(Value::as_str)
                {
                    let Some(record) = evidence.get(&(unit_id, evidence_id)) else {
                        links.push(BrokenLink {
                            declaration: Some(name.to_string()),
                            unit_id: Some(unit_id.to_string()),
                            claim_id: Some(claim_id.to_string()),
                            evidence_id: Some(evidence_id.to_string()),
                            ..broken(
                                "MISSING_EVIDENCE",
                                format!("{claim_id} cites evidence no bundle contains: {evidence_id}"),
                            )
                        });
                        continue;
                    };
                    if !examined.insert((unit_id.to_string(), evidence_id.to_string())) {
                        continue;
                    }
                    // A resolution is explicitly non-normative and has no
                    // Phase-1 text to verify against.
                    if evidence_id.starts_with("resolution:") {
                        verified.insert((unit_id.to_string(), evidence_id.to_string()));
                        continue;
                    }
                    match verify_evidence(db, record) {
                        Ok(()) => {
                            verified.insert((unit_id.to_string(), evidence_id.to_string()));
                        }
                        Err(detail) => links.push(BrokenLink {
                            declaration: Some(name.to_string()),
                            unit_id: Some(unit_id.to_string()),
                            claim_id: Some(claim_id.to_string()),
                            evidence_id: Some(evidence_id.to_string()),
                            ..broken(
                                "EVIDENCE_DRIFT",
                                format!("{evidence_id}: {detail}"),
                            )
                        }),
                    }
                }
            }
        }
    };

    walk(inputs.manifest, &mut links, &mut declarations_checked);
    if let Some(core) = inputs.core_manifest {
        walk(core, &mut links, &mut declarations_checked);
    }

    Ok(TraceabilityReport {
        status: if links.is_empty() { "PASS" } else { "FAIL" },
        declarations_checked,
        evidence_verified: verified.len(),
        broken: links,
    })
}
