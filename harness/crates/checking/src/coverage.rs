use std::collections::{BTreeMap, BTreeSet};

use serde::Serialize;
use serde_json::Value;

use spec2lean_translation::source::declarations;

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
            let reason = if item.item_type == "NO_CLAIMS" {
                "states nothing to cover"
            } else {
                "reaches no declaration the Lean defines"
            };
            lines.push(format!(
                "  {} {} ({}) {reason}",
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
    // Only declarations the Lean actually defines count as reaching it. A
    // manifest naming something that does not exist is caught by traceability,
    // but coverage must not report the claim as covered in the meantime.
    let mut defined: BTreeSet<String> = declarations(inputs.source).into_keys().collect();
    if let Some(core_source) = inputs.core_source {
        defined.extend(declarations(core_source).into_keys());
    }
    let index: BTreeMap<(String, String), BTreeSet<String>> = claim_declarations(inputs)
        .into_iter()
        .map(|(key, names)| {
            (
                key,
                names.into_iter().filter(|name| defined.contains(name)).collect(),
            )
        })
        .collect();
    let mut covered = Vec::new();
    let mut uncovered = Vec::new();

    for (unit_id, artifact) in inputs.semantics {
        // An artifact with no usable claim array is not "trivially covered";
        // it means nothing can be checked, which is a failure, not a pass.
        let Some(claims) = artifact
            .get("semantics")
            .and_then(|value| value.get("claims"))
            .and_then(Value::as_array)
        else {
            uncovered.push(CoverageItem {
                item_type: "NO_CLAIMS",
                item_id: "<no claim array>".to_string(),
                unit_id: unit_id.clone(),
                declarations: Vec::new(),
                semantic_claim_ids: Vec::new(),
            });
            continue;
        };
        let claims = claims.as_slice();
        // An artifact with an empty claim list states nothing about the
        // specification, so there is nothing for Lean to cover. Reporting that
        // as full coverage would make the emptiest artifact the best one.
        if claims.is_empty() {
            uncovered.push(CoverageItem {
                item_type: "NO_CLAIMS",
                item_id: "<empty claim array>".to_string(),
                unit_id: unit_id.clone(),
                declarations: Vec::new(),
                semantic_claim_ids: Vec::new(),
            });
            continue;
        }

        // evidence id -> the claims that cite it, and the declarations reached.
        let mut evidence_claims: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
        let mut evidence_declarations: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();

        for (position, claim) in claims.iter().enumerate() {
            let Some(claim_id) = claim.get("claimId").and_then(Value::as_str) else {
                // A claim without an ID cannot be covered by anything, and
                // skipping it would quietly shrink what coverage means.
                uncovered.push(CoverageItem {
                    item_type: "SEMANTIC_CLAIM",
                    item_id: format!("<malformed claim at position {position}>"),
                    unit_id: unit_id.clone(),
                    declarations: Vec::new(),
                    semantic_claim_ids: Vec::new(),
                });
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
