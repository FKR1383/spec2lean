use serde::{Deserialize, Serialize};

/// How much authority a semantic claim carries.
///
/// The distinction is the whole point of the phase: `SourceFact` is what the
/// specification says, `Assumption` is what the extractor supplied because the
/// specification did not. Collapsing them is how a formalization quietly stops
/// being a formalization of the spec.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ClaimKind {
    SourceFact,
    DerivedInterpretation,
    DesignDependency,
    Assumption,
}

impl ClaimKind {
    pub const ALL: [ClaimKind; 4] = [
        ClaimKind::SourceFact,
        ClaimKind::DerivedInterpretation,
        ClaimKind::DesignDependency,
        ClaimKind::Assumption,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::SourceFact => "SOURCE_FACT",
            Self::DerivedInterpretation => "DERIVED_INTERPRETATION",
            Self::DesignDependency => "DESIGN_DEPENDENCY",
            Self::Assumption => "ASSUMPTION",
        }
    }

    /// Claims that assert something about the specification itself, and so must
    /// cite specification evidence.
    pub fn is_factual(self) -> bool {
        matches!(self, Self::SourceFact | Self::DerivedInterpretation)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum UnitKind {
    Instruction,
    LanguageConstruct,
    SharedConcept,
    Other,
}

impl UnitKind {
    pub const ALL: [UnitKind; 4] = [
        UnitKind::Instruction,
        UnitKind::LanguageConstruct,
        UnitKind::SharedConcept,
        UnitKind::Other,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Instruction => "INSTRUCTION",
            Self::LanguageConstruct => "LANGUAGE_CONSTRUCT",
            Self::SharedConcept => "SHARED_CONCEPT",
            Self::Other => "OTHER",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RestrictionKind {
    Version,
    Target,
    Type,
    Operand,
    Other,
}

impl RestrictionKind {
    pub const ALL: [RestrictionKind; 5] = [
        RestrictionKind::Version,
        RestrictionKind::Target,
        RestrictionKind::Type,
        RestrictionKind::Operand,
        RestrictionKind::Other,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Version => "VERSION",
            Self::Target => "TARGET",
            Self::Type => "TYPE",
            Self::Operand => "OPERAND",
            Self::Other => "OTHER",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Outcome {
    Success,
    InsufficientEvidence,
}

impl Outcome {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Success => "SUCCESS",
            Self::InsufficientEvidence => "INSUFFICIENT_EVIDENCE",
        }
    }
}

/// Every finding the Phase-4 validator can produce.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DiagnosticCode {
    EvidenceNotRead,
    ExpectedObject,
    ExpectedArray,
    UnexpectedField,
    InvalidText,
    InvalidEvidenceIds,
    MissingEvidence,
    DuplicateEvidenceId,
    UnknownEvidenceId,
    InvalidOutcome,
    InvalidUnitKind,
    WrongIdentity,
    MissingAspect,
    DuplicateMissingAspect,
    InvalidRestrictionKind,
    InvalidConstraints,
    MissingOperationInputs,
    MissingOperation,
    NonfunctionalOperation,
    MissingResult,
    MissingInputs,
    InvalidSemanticClaimIds,
    InvalidSemanticClaimId,
    DuplicateSemanticClaimId,
    UnknownSemanticClaimId,
    InvalidSharedDependencyId,
    UnknownSharedDependency,
    DuplicateSharedDependency,
    SharedDependencyNameMismatch,
    MissingSharedDependencyClaims,
    MissingSharedDependency,
    InvalidClaimId,
    DuplicateClaimId,
    InvalidClaimKind,
    DuplicateClaim,
    ConflictingClaimAuthority,
    MissingClaims,
    MissingClaimRendition,
    NonNormativeClaimKind,
    UnmappedNonNormativeResolution,
    InputBoundary,
    EvidenceHashMismatch,
    UnsupportedExtractor,
    DeterministicMismatch,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct Diagnostic {
    pub code: DiagnosticCode,
    pub message: String,
    pub path: String,
}

impl Diagnostic {
    pub fn new(code: DiagnosticCode, message: impl Into<String>, path: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            path: path.into(),
        }
    }

    pub fn root(code: DiagnosticCode, message: impl Into<String>) -> Self {
        Self::new(code, message, "$")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wire_names_match_the_python_constants() {
        for kind in ClaimKind::ALL {
            assert_eq!(
                serde_json::to_string(&kind).unwrap(),
                format!("\"{}\"", kind.as_str())
            );
        }
        for kind in UnitKind::ALL {
            assert_eq!(
                serde_json::to_string(&kind).unwrap(),
                format!("\"{}\"", kind.as_str())
            );
        }
        for kind in RestrictionKind::ALL {
            assert_eq!(
                serde_json::to_string(&kind).unwrap(),
                format!("\"{}\"", kind.as_str())
            );
        }
        assert_eq!(
            serde_json::to_string(&DiagnosticCode::UnmappedNonNormativeResolution).unwrap(),
            "\"UNMAPPED_NON_NORMATIVE_RESOLUTION\""
        );
        assert_eq!(
            serde_json::to_string(&DiagnosticCode::NonNormativeClaimKind).unwrap(),
            "\"NON_NORMATIVE_CLAIM_KIND\""
        );
    }

    #[test]
    fn only_specification_claims_are_factual() {
        assert!(ClaimKind::SourceFact.is_factual());
        assert!(ClaimKind::DerivedInterpretation.is_factual());
        assert!(!ClaimKind::Assumption.is_factual());
        assert!(!ClaimKind::DesignDependency.is_factual());
    }
}
