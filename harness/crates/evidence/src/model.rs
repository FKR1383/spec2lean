use serde::{Deserialize, Serialize};

/// Relevance labels. An enum rather than a string tuple, so an unrecognised
/// role is a parse failure at the boundary instead of a comparison that
/// silently comes out false somewhere downstream.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Role {
    Syntax,
    Operands,
    TypeRules,
    Operation,
    Algorithm,
    EdgeCase,
    StateEffect,
    Predication,
    VersionOrTargetRestriction,
    Example,
    SupportingDefinition,
    Other,
}

impl Role {
    pub const ALL: [Role; 12] = [
        Role::Syntax,
        Role::Operands,
        Role::TypeRules,
        Role::Operation,
        Role::Algorithm,
        Role::EdgeCase,
        Role::StateEffect,
        Role::Predication,
        Role::VersionOrTargetRestriction,
        Role::Example,
        Role::SupportingDefinition,
        Role::Other,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Syntax => "SYNTAX",
            Self::Operands => "OPERANDS",
            Self::TypeRules => "TYPE_RULES",
            Self::Operation => "OPERATION",
            Self::Algorithm => "ALGORITHM",
            Self::EdgeCase => "EDGE_CASE",
            Self::StateEffect => "STATE_EFFECT",
            Self::Predication => "PREDICATION",
            Self::VersionOrTargetRestriction => "VERSION_OR_TARGET_RESTRICTION",
            Self::Example => "EXAMPLE",
            Self::SupportingDefinition => "SUPPORTING_DEFINITION",
            Self::Other => "OTHER",
        }
    }
}

/// `Core` is declared first so the derived ordering reproduces the Python sort
/// key `EVIDENCE_TIERS.index(tier)` without a lookup table.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Tier {
    Core,
    Supporting,
}

impl Tier {
    pub const ALL: [Tier; 2] = [Tier::Core, Tier::Supporting];

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Core => "CORE",
            Self::Supporting => "SUPPORTING",
        }
    }
}

/// A deterministic validation finding, handed straight back to the model so it
/// can correct itself inside the same session.
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

/// Every finding the validator can produce. Closed set: a code cannot drift
/// between the validator, the schema, and the prompt, because there is only one
/// place it is spelled.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DiagnosticCode {
    ExpectedObject,
    UnexpectedField,
    WrongUnit,
    ExpectedArray,
    EmptyEvidence,
    InvalidSelection,
    InvalidSourceNodes,
    InvalidSourceNode,
    DuplicateSourceNode,
    InvalidSourceSpans,
    DuplicateSourceSpan,
    InventedSourceNode,
    NodeNotExposed,
    SpanNotExposed,
    InvalidRole,
    InvalidTier,
    EmptyRationale,
    NoncontiguousNodes,
    InventedSourceSpan,
    SpanNodeMismatch,
    NoncontiguousSpans,
    SpanNodeCoverage,
    DuplicateEvidence,
    EmptyEvidenceText,
    MissingCoreEvidence,
    MissingSourceRendition,
    UnpairedSourceRendition,
    DuplicateEvidenceId,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wire_names_match_the_python_constants() {
        assert_eq!(
            serde_json::to_string(&Role::VersionOrTargetRestriction).unwrap(),
            "\"VERSION_OR_TARGET_RESTRICTION\""
        );
        assert_eq!(serde_json::to_string(&Tier::Core).unwrap(), "\"CORE\"");
        assert_eq!(
            serde_json::to_string(&DiagnosticCode::NodeNotExposed).unwrap(),
            "\"NODE_NOT_EXPOSED\""
        );
        for role in Role::ALL {
            assert_eq!(
                serde_json::to_string(&role).unwrap(),
                format!("\"{}\"", role.as_str())
            );
        }
    }

    #[test]
    fn core_sorts_before_supporting() {
        let mut tiers = vec![Tier::Supporting, Tier::Core];
        tiers.sort();
        assert_eq!(tiers, vec![Tier::Core, Tier::Supporting]);
    }
}
