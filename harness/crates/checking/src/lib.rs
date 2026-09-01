//! Phase 6: does the Lean actually account for the specification, and does it
//! still trace back to it?
//!
//! Phase 5 checks a group as it is produced. This checks the finished
//! artifacts against each other and against the index — which is a different
//! question, because artifacts are written at different times and the index can
//! move underneath them. Two directions:
//!
//! * **Coverage**, forward: every semantic claim, and every piece of evidence
//!   those claims rest on, reaches at least one Lean declaration.
//! * **Traceability**, backward: every Lean declaration leads through real
//!   claims to real evidence whose exact text is still, byte for byte, what the
//!   index holds.

pub mod coverage;
pub mod traceability;

pub use coverage::{CoverageItem, CoverageReport, coverage};
pub use traceability::{BrokenLink, TraceabilityReport, traceability};

use serde::Serialize;
use serde_json::Value;
use std::collections::BTreeMap;
use std::path::Path;

use spec2lean_specdb::SpecDb;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CheckReport {
    pub status: &'static str,
    pub coverage: CoverageReport,
    pub traceability: TraceabilityReport,
}

impl CheckReport {
    pub fn passed(&self) -> bool {
        self.status == "PASS"
    }

    pub fn summary(&self) -> String {
        let mut lines = vec![format!("logical checks: {}", self.status)];
        lines.push(self.coverage.summary());
        lines.push(self.traceability.summary());
        lines.join("\n")
    }
}

/// Inputs to one group's logical check.
pub struct CheckInputs<'a> {
    /// Phase-3 bundles, keyed by unit.
    pub bundles: &'a BTreeMap<String, Value>,
    /// Phase-4 artifacts, keyed by unit.
    pub semantics: &'a BTreeMap<String, Value>,
    /// The Phase-5 translation manifest.
    pub manifest: &'a Value,
    /// The frozen core manifest, when the group has shared concepts.
    pub core_manifest: Option<&'a Value>,
    /// The Lean source the manifest describes.
    pub source: &'a str,
    /// The core's Lean source, when there is one.
    pub core_source: Option<&'a str>,
}

pub fn check(inputs: &CheckInputs<'_>, database: &Path) -> Result<CheckReport, String> {
    let db = SpecDb::open(database).map_err(|error| error.to_string())?;
    let coverage = coverage::coverage(inputs);
    let traceability = traceability::traceability(inputs, &db)?;
    let status = if coverage.passed() && traceability.passed() {
        "PASS"
    } else {
        "FAIL"
    };
    Ok(CheckReport {
        status,
        coverage,
        traceability,
    })
}
