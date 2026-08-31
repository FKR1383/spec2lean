use std::fmt;

use serde::{Deserialize, Deserializer, Serialize};

/// Identifiers carry their namespace in the string (`node:…`, `span:…`,
/// `unit:…`). Parsing them into distinct types once, at the boundary, is the
/// point: a `SpanId` can no longer be passed where a `NodeId` belongs, and an
/// identifier the model invented cannot reach a query without first failing to
/// parse.
macro_rules! prefixed_id {
    ($name:ident, $prefix:literal, $label:literal) => {
        #[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
        #[serde(transparent)]
        pub struct $name(String);

        impl $name {
            pub fn parse(value: &str) -> Result<Self, IdError> {
                if value.starts_with($prefix) && value.len() > $prefix.len() {
                    Ok(Self(value.to_string()))
                } else {
                    Err(IdError {
                        label: $label,
                        prefix: $prefix,
                        found: value.to_string(),
                    })
                }
            }

            pub fn as_str(&self) -> &str {
                &self.0
            }

            /// For values already read out of the database, where the prefix is
            /// a schema invariant rather than untrusted input.
            #[allow(dead_code)]
            pub(crate) fn trusted(value: String) -> Self {
                Self(value)
            }
        }

        impl fmt::Display for $name {
            fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                f.write_str(&self.0)
            }
        }

        impl<'de> Deserialize<'de> for $name {
            fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
                let raw = String::deserialize(deserializer)?;
                Self::parse(&raw).map_err(serde::de::Error::custom)
            }
        }

        impl rusqlite::ToSql for $name {
            fn to_sql(&self) -> rusqlite::Result<rusqlite::types::ToSqlOutput<'_>> {
                self.0.to_sql()
            }
        }
    };
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IdError {
    pub label: &'static str,
    pub prefix: &'static str,
    pub found: String,
}

impl fmt::Display for IdError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{} must start with `{}`: {:?}",
            self.label, self.prefix, self.found
        )
    }
}

impl std::error::Error for IdError {}

prefixed_id!(NodeId, "node:", "a source node ID");
prefixed_id!(SpanId, "span:", "a source span ID");
prefixed_id!(UnitId, "unit:", "a planned unit ID");

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_the_wrong_namespace_and_the_bare_prefix() {
        assert!(NodeId::parse("node:abc").is_ok());
        assert!(NodeId::parse("span:abc").is_err());
        assert!(NodeId::parse("node:").is_err());
        assert!(NodeId::parse("").is_err());
        assert!(UnitId::parse("unit:x").is_ok());
    }

    #[test]
    fn deserialisation_enforces_the_namespace() {
        assert!(serde_json::from_str::<NodeId>("\"node:1\"").is_ok());
        let wrong = serde_json::from_str::<NodeId>("\"span:1\"");
        assert!(wrong.is_err());
    }
}
