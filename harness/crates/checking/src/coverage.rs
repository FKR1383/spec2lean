use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::Value;

use crate::CheckInputs;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CoverageItem {
    pub item_type: &'static str,
    pub item_id: String,
    pub unit_id: String,
    pub declarations: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub semantic_claim_ids: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CoverageReport {
    pub status: &'static str,
    pub covered: Vec<CoverageItem>,
    pub uncovered: Vec<CoverageItem>,
}

impl CoverageReport {
    pub fn passed(&self) -> bool {
        self.status == "PASS"
    }

    pub fn summary(&self) -> String {
        if self.passed() {
            return format!(
                "coverage: PASS ({} claim(s) and evidence item(s) reach Lean)",
                self.covered.len()
            );
        }
        let mut lines = vec![format!("coverage: FAIL ({} uncovered)", self.uncovered.len())];
        for item in self.uncovered.iter().take(20) {
            lines.push(format!(
                "  {} {} ({}) reaches no declaration",
                item.item_type, item.item_id, item.unit_id
            ));
        }
        lines.join("\n")
    }
}

/// Which declarations cite which `(unit, claim)` pairs, across the group
/// manifest and the frozen core.
///
/// The core counts: a claim represented only by a shared declaration is still
/// represented. Ignoring the core would report every shared concept as
/// uncovered.
pub(crate) fn claim_declarations(inputs: &CheckInputs<'_>) -> BTreeMap<(String, String), BTreeSet<String>> {
    let mut index: BTreeMap<(String, String), BTreeSet<String>> = BTreeMap::new();
    let mut absorb = |manifest: &Value| {
        for mapping in manifest
            .get("declarations")
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default()
        {
            let Some(name) = mapping.get("declaration").and_then(Value::as_str) else {
                continue;
            };
            for reference in mapping
                .get("claimRefs")
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default()
            {
                if let (Some(unit_id), Some(claim_id)) = (
                    reference.get("unitId").and_then(Value::as_str),
                    reference.get("claimId").and_then(Value::as_str),
                ) {
                    index
                        .entry((unit_id.to_string(), claim_id.to_string()))
                        .or_default()
                        .insert(name.to_string());
                }
            }
        }
    };
    absorb(inputs.manifest);
    if let Some(core) = inputs.core_manifest {
        absorb(core);
    }
    index
}

/// Forward coverage: every claim, and every evidence item those claims rest on,
/// must reach Lean.
pub fn coverage(inputs: &CheckInputs<'_>) -> CoverageReport {
    let index = claim_declarations(inputs);
    let mut covered = Vec::new();
    let mut uncovered = Vec::new();

    for (unit_id, artifact) in inputs.semantics {
        let claims = artifact
            .get("semantics")
            .and_then(|value| value.get("claims"))
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default();

        // evidence id -> the claims that cite it, and the declarations reached.
        let mut evidence_claims: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        let mut evidence_declarations: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();

        for claim in claims {
            let Some(claim_id) = claim.get("claimId").and_then(Value::as_str) else {
                continue;
            };
            let declarations: Vec<String> = index
                .get(&(unit_id.clone(), claim_id.to_string()))
                .map(|names| names.iter().cloned().collect())
                .unwrap_or_default();
            let item = CoverageItem {
                item_type: "SEMANTIC_CLAIM",
                item_id: claim_id.to_string(),
                unit_id: unit_id.clone(),
                declarations: declarations.clone(),
                semantic_claim_ids: Vec::new(),
            };
            if declarations.is_empty() {
                uncovered.push(item);
            } else {
                covered.push(item);
            }
            for evidence_id in claim
                .get("evidenceIds")
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default()
                .iter()
                .filter_map(Value::as_str)
            {
                evidence_claims
                    .entry(evidence_id.to_string())
                    .or_default()
                    .insert(claim_id.to_string());
                evidence_declarations
                    .entry(evidence_id.to_string())
                    .or_default()
                    .extend(declarations.iter().cloned());
            }
        }

        // Evidence that was cited but whose claims never reached Lean means a
        // passage was read from the specification and then dropped.
        for (evidence_id, claim_ids) in evidence_claims {
            let declarations: Vec<String> = evidence_declarations
                .get(&evidence_id)
                .map(|names| names.iter().cloned().collect())
                .unwrap_or_default();
            let item = CoverageItem {
                item_type: "EVIDENCE",
                item_id: evidence_id,
                unit_id: unit_id.clone(),
                declarations: declarations.clone(),
                semantic_claim_ids: claim_ids.into_iter().collect(),
            };
            if declarations.is_empty() {
                uncovered.push(item);
            } else {
                covered.push(item);
            }
        }
    }

    CoverageReport {
        status: if uncovered.is_empty() { "PASS" } else { "FAIL" },
        covered,
        uncovered,
    }
}
