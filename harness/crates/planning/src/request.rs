use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use spec2lean_specdb::NodeId;

/// How a request selects what to plan.
///
/// Exactly one selector may be populated, which the constructor enforces — a
/// request that names both an instruction list and a subtree has no defined
/// meaning, and silently preferring one would plan the wrong thing.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ScopeMode {
    ExactInstructions,
    InstructionFamily,
    SourceSubtree,
    FullSpecification,
}

impl ScopeMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::ExactInstructions => "EXACT_INSTRUCTIONS",
            Self::InstructionFamily => "INSTRUCTION_FAMILY",
            Self::SourceSubtree => "SOURCE_SUBTREE",
            Self::FullSpecification => "FULL_SPECIFICATION",
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct RequestError(pub String);

impl std::fmt::Display for RequestError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for RequestError {}

/// The selector, as a sum type rather than four optional fields. Making the
/// modes mutually exclusive in the type is what removes the "exactly one
/// populated" runtime check the Python constructor had to perform.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Selector {
    ExactInstructions(Vec<String>),
    InstructionFamily(String),
    SourceSubtree(NodeId),
    FullSpecification,
}

impl Selector {
    pub fn mode(&self) -> ScopeMode {
        match self {
            Self::ExactInstructions(_) => ScopeMode::ExactInstructions,
            Self::InstructionFamily(_) => ScopeMode::InstructionFamily,
            Self::SourceSubtree(_) => ScopeMode::SourceSubtree,
            Self::FullSpecification => ScopeMode::FullSpecification,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlanningRequest {
    pub language: String,
    pub version: String,
    pub selector: Selector,
}

impl PlanningRequest {
    pub fn new(
        language: &str,
        version: &str,
        selector: Selector,
    ) -> Result<Self, RequestError> {
        if language.trim().is_empty() || version.trim().is_empty() {
            return Err(RequestError(
                "language and version must be non-empty".into(),
            ));
        }
        let selector = match selector {
            Selector::ExactInstructions(instructions) => {
                let trimmed: Vec<String> = instructions
                    .iter()
                    .map(|item| item.trim().to_string())
                    .collect();
                if trimmed.is_empty() || trimmed.iter().any(String::is_empty) {
                    return Err(RequestError(
                        "EXACT_INSTRUCTIONS requires at least one non-empty instruction".into(),
                    ));
                }
                let mut sorted = trimmed.clone();
                sorted.sort();
                sorted.dedup();
                if sorted.len() != trimmed.len() {
                    return Err(RequestError(
                        "exact instruction requests cannot contain duplicates".into(),
                    ));
                }
                Selector::ExactInstructions(trimmed)
            }
            Selector::InstructionFamily(family) => {
                let family = family.trim().to_string();
                if family.is_empty() {
                    return Err(RequestError(
                        "INSTRUCTION_FAMILY requires a non-empty family".into(),
                    ));
                }
                Selector::InstructionFamily(family)
            }
            other => other,
        };
        Ok(Self {
            language: language.to_string(),
            version: version.to_string(),
            selector,
        })
    }

    pub fn mode(&self) -> ScopeMode {
        self.selector.mode()
    }

    pub fn to_json(&self) -> Value {
        let mut scope = json!({"mode": self.mode().as_str()});
        match &self.selector {
            Selector::ExactInstructions(instructions) => {
                scope["instructions"] = json!(instructions);
            }
            Selector::InstructionFamily(family) => scope["family"] = json!(family),
            Selector::SourceSubtree(node_id) => scope["sourceNodeId"] = json!(node_id),
            Selector::FullSpecification => {}
        }
        json!({
            "schemaVersion": 1,
            "language": self.language,
            "version": self.version,
            "scope": scope,
        })
    }

    pub fn from_json(value: &Value) -> Result<Self, RequestError> {
        let scope = value
            .get("scope")
            .and_then(Value::as_object)
            .ok_or_else(|| RequestError("request.scope must be an object".into()))?;
        let mode = scope.get("mode").and_then(Value::as_str).unwrap_or_default();
        let selector = match mode {
            "EXACT_INSTRUCTIONS" => Selector::ExactInstructions(
                scope
                    .get("instructions")
                    .and_then(Value::as_array)
                    .map(|items| {
                        items
                            .iter()
                            .filter_map(Value::as_str)
                            .map(str::to_string)
                            .collect()
                    })
                    .unwrap_or_default(),
            ),
            "INSTRUCTION_FAMILY" => Selector::InstructionFamily(
                scope
                    .get("family")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
            ),
            "SOURCE_SUBTREE" => Selector::SourceSubtree(
                NodeId::parse(scope.get("sourceNodeId").and_then(Value::as_str).unwrap_or(""))
                    .map_err(|error| RequestError(error.to_string()))?,
            ),
            "FULL_SPECIFICATION" => Selector::FullSpecification,
            other => {
                return Err(RequestError(format!(
                    "unknown planning scope mode: {other:?}"
                )));
            }
        };
        Self::new(
            value.get("language").and_then(Value::as_str).unwrap_or(""),
            value.get("version").and_then(Value::as_str).unwrap_or(""),
            selector,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_request_needs_a_language_a_version_and_content() {
        assert!(PlanningRequest::new("", "1.0", Selector::FullSpecification).is_err());
        assert!(PlanningRequest::new("ptx", " ", Selector::FullSpecification).is_err());
        assert!(PlanningRequest::new("ptx", "8.5", Selector::FullSpecification).is_ok());
    }

    #[test]
    fn exact_instructions_are_trimmed_and_must_be_distinct() {
        let request = PlanningRequest::new(
            "ptx",
            "8.5",
            Selector::ExactInstructions(vec![" add.u32 ".into(), "sub.u32".into()]),
        )
        .expect("valid");
        assert_eq!(
            request.selector,
            Selector::ExactInstructions(vec!["add.u32".into(), "sub.u32".into()])
        );

        assert!(
            PlanningRequest::new(
                "ptx",
                "8.5",
                Selector::ExactInstructions(vec!["add".into(), " add ".into()]),
            )
            .is_err()
        );
        assert!(
            PlanningRequest::new("ptx", "8.5", Selector::ExactInstructions(vec![])).is_err()
        );
    }

    #[test]
    fn json_round_trips_every_mode() {
        for selector in [
            Selector::ExactInstructions(vec!["add.u32".into()]),
            Selector::InstructionFamily("integer arithmetic".into()),
            Selector::SourceSubtree(NodeId::parse("node:abc").unwrap()),
            Selector::FullSpecification,
        ] {
            let request = PlanningRequest::new("ptx", "8.5", selector).expect("valid");
            let restored = PlanningRequest::from_json(&request.to_json()).expect("round trip");
            assert_eq!(request, restored);
        }
    }

    #[test]
    fn a_malformed_subtree_node_is_rejected_at_the_boundary() {
        let value = json!({
            "language": "ptx", "version": "8.5",
            "scope": {"mode": "SOURCE_SUBTREE", "sourceNodeId": "span:x"},
        });
        assert!(PlanningRequest::from_json(&value).is_err());
    }
}
